# -*- coding: utf-8 -*-
"""
juni_juli_05_gen_pos.py — Generator data POS Juni + Juli 2026 (portofolio 2 bulan).

Meniru **bentuk** data Agustus 2026 (satu-satunya bulan berisi) lalu menskalakan
volumenya. Semua parameter diturunkan dari Agustus saat runtime — tidak ada angka
omzet yang di-hardcode selain TARGET bulanan.

Yang dibuat:
  * pos.session  : 1 sesi per config per hari, 06:00 -> 23:00 (pola Agustus)
  * pos.order    : struktur line 1-4 produk, qty 1-2, tanpa pajak
  * pos.payment  : mix metode bayar per config (pola Agustus)
  * tutup sesi   : action_pos_session_closing_control() -> JE POSS + account.payment
                   + statement line kas, persis alur Agustus
  * re-date      : Odoo menstempel JE dengan tanggal HARI INI; semua move yang lahir
                   dari sesi ditulis ulang ke tanggal sesi (butuh hash POSS nonaktif,
                   sudah dilakukan di P3)

Idempotent: sesi (config_id, start_at) yang sudah ada akan DILEWATI.

Jalankan (pola repo §2 PROGRESS_DASHBOARD.md):

  # DRY-RUN (default) — hanya cetak rencana, tidak menulis apa pun
  su odoo -s /bin/bash -c "cd /workspaces/odoo-test && odoo shell -d Test1 --no-http \\
      --db_host db --db_port 5432 --db_user odoo --db_password odoo" < scripts/juni_juli_05_gen_pos.py

  # EKSEKUSI
  su odoo -s /bin/bash -c "cd /workspaces/odoo-test && RUN=1 odoo shell -d Test1 --no-http \\
      --db_host db --db_port 5432 --db_user odoo --db_password odoo" < scripts/juni_juli_05_gen_pos.py

Env var:
  RUN=1         eksekusi sungguhan (default: dry-run)
  MONTHS=june   hanya Juni (default: june,july)
  VERBOSE=1     cetak ringkasan per sesi
"""
import os
import random
import time
from collections import Counter, defaultdict
from datetime import timedelta

from odoo import fields

RUN = os.environ.get("RUN") == "1"
VERBOSE = os.environ.get("VERBOSE") == "1"
MONTHS = [m.strip() for m in os.environ.get("MONTHS", "june,july").split(",") if m.strip()]
SEED = 20260620

AUG_FROM, AUG_TO = "2026-08-01", "2026-09-01"          # basis pembanding
PERIODS = {
    "june": ("2026-06-20", "2026-07-01", 80_000_000),        # 11 hari, pemanasan
    "july": ("2026-07-01", "2026-08-01", None),              # 31 hari, 97% Agustus
}
JULY_RATIO = 0.97
CASH_FLOAT = 500_000        # kas awal (float) yang ditinggal di laci setiap sesi
DEPOSIT_JCODE = "BNK1"      # setoran kas harian masuk ke Bank BSI

POS = env["pos.order"].with_context(active_test=False)
Sess = env["pos.session"]
Prod = env["product.product"]
AM = env["account.move"]
SL = env["account.bank.statement.line"]
Config = env["pos.config"]
AA = env["account.account"]

from odoo.exceptions import UserError

log = []


def say(msg=""):
    log.append(msg)
    print(msg)


# ---------------------------------------------------------------------------
# 0. GUARD
# ---------------------------------------------------------------------------
say("=" * 78)
say("GENERATOR POS JUNI + JULI 2026   |   RUN=%s | months=%s" % (RUN, ",".join(MONTHS)))
say("=" * 78)

if not POS.search_count([("date_order", ">=", AUG_FROM), ("date_order", "<", AUG_TO)]):
    raise UserError("Agustus tidak punya order — basis pembanding hilang, generator dibatalkan.")

rng = random.Random(SEED)

# ---------------------------------------------------------------------------
# 1. TURUNKAN PARAMETER DARI AGUSTUS
# ---------------------------------------------------------------------------
aug = POS.search([("date_order", ">=", AUG_FROM), ("date_order", "<", AUG_TO)])
aug_rev = sum(aug.mapped("amount_total"))
aug_n = len(aug)
say("Basis Agustus: %d order, omzet %s, avg/order %s" % (
    aug_n, "{:,.2f}".format(aug_rev), "{:,.0f}".format(aug_rev / aug_n)))

# --- 1a. profil weekday (rata-rata omzet per hari-dalam-minggu) ---
byday = defaultdict(float)
for o in aug:
    byday[o.date_order.date()] += o.amount_total
wd_sum, wd_cnt = defaultdict(float), defaultdict(int)
for d, v in byday.items():
    wd_sum[d.weekday()] += v
    wd_cnt[d.weekday()] += 1
WD_PROFILE = {d: (wd_sum[d] / wd_cnt[d]) for d in wd_sum}

# --- 1b. split omzet per config ---
cfg_rev, cfg_n = defaultdict(float), defaultdict(int)
for o in aug:
    cid = o.session_id.config_id.id
    cfg_rev[cid] += o.amount_total
    cfg_n[cid] += 1
CFG_SHARE = {cid: cfg_rev[cid] / aug_rev for cid in cfg_rev}
cfg_ids = sorted(cfg_rev)

# --- 1c. mix metode bayar per config ---
mix = defaultdict(lambda: defaultdict(float))
for o in aug:
    cid = o.session_id.config_id.id
    for p in o.payment_ids:
        mix[cid][p.payment_method_id.id] += p.amount
PM_MIX = {cid: sorted(d.items(), key=lambda x: -x[1]) for cid, d in mix.items()}

# --- 1d. struktur order ---
nlines_w, qty_w = Counter(), Counter()
prod_qty = Counter()
for o in aug:
    nlines_w[len(o.lines)] += 1
    for l in o.lines:
        qty_w[int(l.qty)] += 1
        prod_qty[l.product_id.id] += l.qty
PRODS = list(prod_qty.keys())
PROD_W = [prod_qty[p] for p in PRODS]

# Harga efektif per produk dari Agustus. Order Agustus sudah ber-diskon, jadi memakai
# list_price membuat rata-rata order 7,6% lebih tinggi (55.217 vs 51.292) dan jumlah
# order ikut tertekan. Ini memakai harga yang benar-benar terjadi.
_prices = defaultdict(list)
for _o in aug:
    for _l in _o.lines:
        if _l.qty:
            _prices[_l.product_id.id].append(_l.price_unit)
PROD_PRICE = {pid: (sum(v) / len(v)) for pid, v in _prices.items()}
NLINES = sorted(nlines_w.items())
QTY = sorted(qty_w.items())
avgsale = aug_rev / aug_n

say("Weekday profile : " + "  ".join(
    "%s=%s" % (d, "{:,.0f}".format(WD_PROFILE[d])) for d in sorted(WD_PROFILE)))
say("Config share    : " + "  ".join(
    "%s=%.2f%% (%d order)" % (Config.browse(c).name, CFG_SHARE[c] * 100, cfg_n[c]) for c in cfg_ids))
say("Order structure : lines=%s | qty=%s | %d produk" % (NLINES, QTY, len(PRODS)))
_avg_price = sum(PROD_PRICE.get(p, 0) * prod_qty[p] for p in PRODS) / sum(PROD_W)
_exp_ord = (sum(k * v for k, v in NLINES) / sum(w for _k, w in NLINES)) * \
           (sum(k * v for k, v in QTY) / sum(w for _k, w in QTY)) * _avg_price
say("Harga efektif   : %s/unit -> rata-rata order ~%s (Agustus %s)" % (
    "{:,.0f}".format(_avg_price), "{:,.0f}".format(_exp_ord), "{:,.0f}".format(avgsale)))

# --- guard §14: TIDAK BOLEH ada penjualan kredit (piutang) ------------------
say("")
bad_pm = []
for cid in cfg_ids:
    for pid, _amt in PM_MIX[cid]:
        pm = env["pos.payment.method"].browse(pid)
        if pm.type == "pay_later" or not pm.journal_id:
            bad_pm.append("%s (type=%s)" % (pm.name, pm.type))
if bad_pm:
    raise UserError("Guard no-piutang (§14): metode bayar berikut bikin piutang -> %s" %
                    sorted(set(bad_pm)))
say("Guard no-piutang : OK — %d metode, semuanya lunas di titik transaksi (tidak ada pay_later)" %
    len(set(pid for cid in cfg_ids for pid, _ in PM_MIX[cid])))

# --- pastikan setiap metode yang akan dipakai memang diizinkan di config-nya --
# Temuan: data Agustus memakai 'Kartu' di Restoran Mallengkeri, tapi metode itu
# belum terdaftar di config 2 -> Odoo menolak (pos_payment._check_payment_method_id).
to_add = []
for cid in cfg_ids:
    cfg = Config.browse(cid)
    for pid, _amt in PM_MIX[cid]:
        if pid not in cfg.payment_method_ids.ids:
            pm = env["pos.payment.method"].browse(pid)
            to_add.append((cid, pid))
            say("   config %-22s: metode '%s' dipakai Agustus tapi belum terdaftar -> akan ditambahkan" % (
                cfg.name, pm.name))
if to_add:
    if RUN:
        for cid, pid in to_add:
            Config.browse(cid).write({"payment_method_ids": [(4, pid)]})
        env.cr.commit()
        say("   %d metode ditambahkan ke config" % len(to_add))
for cid in cfg_ids:
    tot = sum(v for _, v in PM_MIX[cid])
    say("   mix %-22s %s" % (Config.browse(cid).name, " ".join(
        "%s %.1f%%" % (env["pos.payment.method"].browse(pid).name, 100 * v / tot)
        for pid, v in PM_MIX[cid])))

# ---------------------------------------------------------------------------
# 2. RENCANA PER SESI
# ---------------------------------------------------------------------------
def weighted(items):
    vals = [k for k, _ in items]
    wts = [w for _, w in items]
    return rng.choices(vals, weights=wts, k=1)[0]


def pick_products(n):
    """Ambil n produk TANPA pengembalian, dengan bobot frekuensi penjualan Agustus.

    Catatan: random.sample() mengabaikan bobot -> dulu semua produk berpeluang sama,
    sehingga paket mahal terpilih sesering menu murah dan rata-rata order menggelembung
    (59.563 vs 51.292 Agustus). Ini penggantinya.
    """
    pool = list(zip(PRODS, PROD_W))
    out = []
    for _ in range(min(n, len(pool))):
        total = sum(w for _p, w in pool)
        r = rng.uniform(0, total)
        acc = 0.0
        for i, (p, w) in enumerate(pool):
            acc += w
            if acc >= r:
                out.append(p)
                pool.pop(i)
                break
    return Prod.browse(out)


def build_order(session, cfg, session_target_left):
    """Buat 1 order + payment, kembalikan totalnya."""
    n = weighted(NLINES)
    prods = pick_products(n)
    lines, total = [], 0.0
    for p in prods:
        q = weighted(QTY)
        price = PROD_PRICE.get(p.id) or p.list_price or 0.0
        lines.append((0, 0, {
            "product_id": p.id, "qty": q, "price_unit": price,
            "price_subtotal": price * q, "price_subtotal_incl": price * q,
            "tax_ids": [(6, 0, [])], "price_type": "original",
        }))
        total += price * q
    total = round(total)
    if total <= 0:
        total = 1000
        lines = [(0, 0, {"product_id": PRODS[0], "qty": 1, "price_unit": 1000,
                         "price_subtotal": 1000, "price_subtotal_incl": 1000,
                         "tax_ids": [(6, 0, [])], "price_type": "original"})]

    day = session.start_at.date()
    hour = rng.choices(range(8, 22), weights=[6, 9, 10, 8, 10, 12, 11, 10, 9, 12, 13, 12, 11, 6])[0]
    dt = "%s %02d:%02d:00" % (day, hour, rng.randrange(60))

    order = POS.create({
        "session_id": session.id, "date_order": dt, "user_id": 1,
        "amount_tax": 0.0, "amount_total": total, "amount_paid": 0.0,
        "amount_return": 0.0, "lines": lines,
    })
    pm_id = rng.choices([p for p, _ in PM_MIX[cfg.id]], weights=[v for _, v in PM_MIX[cfg.id]])[0]
    order.add_payment({"pos_order_id": order.id, "payment_method_id": pm_id,
                       "amount": total, "payment_date": dt})
    order.action_pos_order_paid()
    return total


def fix_dates(marker_move_id, marker_sl_id, day_dt):
    """Odoo menstempel 'hari ini'; tulis ulang ke tanggal sesi."""
    new_moves = AM.search([("id", ">", marker_move_id)])
    for m in new_moves:
        if m.state == "posted" and m.date != day_dt:
            # Odoo menstempel tanggal HARI INI saat close; 'date' readonly utk move
            # posted -> pakai context resmi (bukan draft/repost yang bikin ulang nomor).
            m.with_context(skip_readonly_check=True).write({"date": day_dt})
    new_sl = SL.search([("id", ">", marker_sl_id)])
    return len(new_moves), len(new_sl)


plan = []          # (period, cfg_id, day)
for name in MONTHS:
    d_from, d_to, target = PERIODS[name]
    if target is None:
        target = round(aug_rev * JULY_RATIO)
    days = []
    d = fields.Date.to_date(d_from)
    end = fields.Date.to_date(d_to)
    while d < end:
        days.append(d)
        d += timedelta(days=1)
    shape = sum(WD_PROFILE.get(x.weekday(), 0) for x in days)
    scale = target / shape if shape else 0
    # Tiap sesi selalu kelebihan ~setengah order terakhir (loop berhenti setelah
    # >= target). Kompensasi: kurangi target per sesi sebesar setengah nilai order
    # rata-rata, supaya total bulan mendekati target, bukan selalu di atasnya.
    bias = avgsale / 2.0
    for day in days:
        day_target = WD_PROFILE.get(day.weekday(), 0) * scale
        for cid in cfg_ids:
            plan.append((name, cid, day, max(day_target * CFG_SHARE[cid] - bias, avgsale)))
    say("%-5s : %s..%s | %2d hari | %d sesi | target omzet %s (skala %.4f)" % (
        name, d_from, d_to, len(days), len(days) * len(cfg_ids),
        "{:,.0f}".format(target), scale))

say("-" * 78)
say("TOTAL RENCANA: %d sesi" % len(plan))

dep_journal = env["account.journal"].search([("code", "=", DEPOSIT_JCODE)], limit=1)
if not dep_journal:
    raise UserError("Journal setoran %s tidak ditemukan" % DEPOSIT_JCODE)
dep_bank_acc = dep_journal.default_account_id
if not dep_bank_acc:
    raise UserError("Journal %s tidak punya default_account_id" % DEPOSIT_JCODE)

# --- modal laci (float) sekali di awal periode ---------------------------------
# Setiap sesi dimulai dengan CASH_FLOAT di laci, tapi uang itu harus benar-benar
# keluar dari bank -> satu JE penarikan per config. Tanpa ini laci punya Rp 500.000
# secara fisik tetapi Rp 0 di ledger (selisih phantom).
float_day = PERIODS[MONTHS[0]][0]
float_ref = "Penarikan kas untuk modal laci"
if RUN and CASH_FLOAT and not AM.search_count([("ref", "=", float_ref)]):
    for cid in cfg_ids:
        cfg = Config.browse(cid)
        cash_pm_cfg = cfg.payment_method_ids.filtered(lambda pm: pm.type == "cash")[:1]
        cash_acc = cash_pm_cfg.journal_id.default_account_id if cash_pm_cfg else False
        if not cash_acc:
            raise UserError("Config %s tidak punya akun kas" % cfg.name)
        fm = AM.create({
            "journal_id": dep_journal.id, "date": float_day, "ref": float_ref,
            "line_ids": [
                (0, 0, {"account_id": cash_acc.id, "debit": CASH_FLOAT, "credit": 0.0,
                        "name": "Modal laci %s" % cfg.name}),
                (0, 0, {"account_id": dep_bank_acc.id, "debit": 0.0, "credit": CASH_FLOAT,
                        "name": "Modal laci %s" % cfg.name}),
            ],
        })
        fm.action_post()
        say("Float laci %-22s %s -> %s" % (cfg.name, "{:,.2f}".format(CASH_FLOAT),
                                            cash_acc.display_name))
    env.cr.commit()

missing = [(n, c, d) for n, c, d, _ in plan
           if not Sess.search_count([("config_id", "=", c), ("start_at", "=", "%s 06:00:00" % d)])]
per_month = Counter(n for n, _c, _d in missing)
say("Sesi baru: %d | sudah ada (dilewati): %d" % (len(missing), len(plan) - len(missing)))
for n in MONTHS:
    say("   %-5s sesi baru = %d" % (n, per_month.get(n, 0)))

if not RUN:
    say()
    say("DRY-RUN — tidak ada data ditulis. Jalankan ulang dgn RUN=1 untuk eksekusi.")
    env.cr.rollback()
    raise SystemExit(0)

# ---------------------------------------------------------------------------
# 3. EKSEKUSI
# ---------------------------------------------------------------------------
say("=" * 78)
say("EKSEKUSI")
t_all = time.time()
created_orders = 0
created_sessions = 0
cash_deposited = 0.0
per_month_rev = defaultdict(float)
per_month_ord = defaultdict(int)
errors = []

for name, cid, day, day_target in plan:
    cfg = Config.browse(cid)
    start_at = "%s 06:00:00" % day
    if Sess.search_count([("config_id", "=", cid), ("start_at", "=", start_at)]):
        continue
    t0 = time.time()
    try:
        sess = Sess.create({"config_id": cid, "user_id": 1})
        # cash_register_balance_start WAJIB eksplisit. Kalau dibiarkan, nilainya 0 saat
        # kita menulis end_real, lalu berubah jadi nilai lain saat close -> Odoo
        # memposting seluruh saldo laci sebagai "selisih kas" ke 6101.23.
        sess.write({"state": "opened", "start_at": start_at,
                    "cash_register_balance_start": CASH_FLOAT})
        env.flush_all()

        got = 0.0
        guard = 0
        while got < day_target and guard < 400:
            got += build_order(sess, cfg, day_target - got)
            guard += 1
        env.flush_all()

        marker_m = AM.search([], order="id desc", limit=1).id or 0
        marker_s = SL.search([], order="id desc", limit=1).id or 0
        sess.write({"stop_at": "%s 23:00:00" % day})
        # Kasir HARUS dihitung = float + penjualan TUNAI hari itu. Kalau tidak, Odoo
        # menganggap seluruh saldo laci sebagai "selisih kas" dan membebankannya ke
        # 6101.23 Beban Operasional Lainnya (Juni+Juli sempat kena Rp 477 juta).
        cash_pm = sess.payment_method_ids.filtered(lambda pm: pm.type == "cash")[:1]
        cash_in = sum(sess.order_ids.payment_ids.filtered(
            lambda p: p.payment_method_id == cash_pm).mapped("amount")) if cash_pm else 0.0
        if sess.config_id.cash_control:
            sess.write({"cash_register_balance_end_real": CASH_FLOAT + cash_in})
            env.flush_all()
        sess.action_pos_session_closing_control()
        env.flush_all()
        # Setoran kas harian ke Bank BSI -> laci kembali ke float (pola warung nyata).
        # Tanpa ini uang tunai menumpuk di laci selama sebulan dan tidak pernah
        # masuk bank, padahal inilah arus kas masuk yang sesungguhnya.
        if cash_in:
            cash_acc = sess.cash_journal_id.default_account_id
            dep = AM.create({
                "journal_id": dep_journal.id, "date": day,
                "ref": "Setoran kas %s" % sess.config_id.name,
                "line_ids": [
                    (0, 0, {"account_id": dep_bank_acc.id, "debit": cash_in, "credit": 0.0,
                            "name": "Setoran kas harian ke Bank BSI"}),
                    (0, 0, {"account_id": cash_acc.id, "debit": 0.0, "credit": cash_in,
                            "name": "Setoran kas harian ke Bank BSI"}),
                ],
            })
            dep.action_post()
            cash_deposited += cash_in
        fix_dates(marker_m, marker_s, day)

        env.cr.commit()
        created_sessions += 1
        created_orders += guard
        per_month_rev[name] += got
        per_month_ord[name] += guard
        if VERBOSE:
            say("   %s %s %-22s %3d order  %14s  (%.1fs)" % (
                day, cfg.name[:22], "", guard, "{:,.0f}".format(got), time.time() - t0))
    except Exception as e:
        env.cr.rollback()
        errors.append("%s %s: %s" % (day, cfg.name, repr(e)[:160]))
        say("   !! GAGAL %s %s -> %s" % (day, cfg.name, repr(e)[:160]))

say("-" * 78)
say("Selesai dalam %.1f menit. sesi=%d order=%d error=%d | setoran kas ke bank=%s" % (
    (time.time() - t_all) / 60.0, created_sessions, created_orders, len(errors),
    "{:,.2f}".format(cash_deposited)))
for name in MONTHS:
    if per_month_ord[name]:
        say("   %-5s order=%-5d omzet=%16s" % (
            name, per_month_ord[name], "{:,.2f}".format(per_month_rev[name])))
for e in errors[:10]:
    say("   ERR " + e)

# ---------------------------------------------------------------------------
# 3b. PENYELESAIAN Outstanding Receipts tiap AKHIR BULAN  (constraint §14)
# ---------------------------------------------------------------------------
# Pembayaran non-tunai lewat POS mendarat di 1103.06 (Outstanding Receipts).
# Kalau dibiarkan, akun itu jadi "piutang" yang menggantung di neraca akhir bulan
# (persis masalah Agustus: Rp 26.088.951 baru dibereskan 1 Sep).
# Solusi: setelah SEMUA sesi bulan itu ditutup, posting per journal:
#     Dr <akun bank journal>  /  Cr 1103.06      bertanggal HARI TERAKHIR bulan itu.
say("")
say("-" * 78)
say("PENYELESAIAN 1103.06 per akhir bulan")
cr = env.cr


def acc_id(code):
    cr.execute("SELECT id FROM account_account WHERE code_store->>'1'=%s LIMIT 1", (code,))
    r = cr.fetchone()
    return r[0] if r else None


out_acc = acc_id("1103.06")
for name in MONTHS:
    d_from, d_to, _t = PERIODS[name]
    last_day = (fields.Date.to_date(d_to) - timedelta(days=1))

    # idempoten: buang dulu settlement lama di bulan ini supaya saldo 1103.06
    # yang dihitung di bawah adalah saldo "mentah" dari pembayaran POS saja.
    old = AM.search([("ref", "like", "Settlement pembayaran POS %"),
                     ("date", ">=", d_from), ("date", "<=", last_day)])
    if old and RUN:
        old.button_draft()
        old.unlink()
        env.cr.commit()
        say("   %-5s %d settlement lama dibersihkan" % (name, len(old)))

    cr.execute("""
        SELECT aj.id, aj.code, aj.default_account_id, SUM(aml.balance)
        FROM account_move_line aml
        JOIN account_move am ON am.id = aml.move_id
        JOIN account_journal aj ON aj.id = am.journal_id
        WHERE aml.account_id = %s AND am.state = 'posted'
          AND am.date >= %s AND am.date < %s
        GROUP BY 1,2,3 HAVING SUM(aml.balance) <> 0
    """, (out_acc, d_from, d_to))
    rows = cr.fetchall()
    if not rows:
        say("   %-5s (tidak ada saldo 1103.06)" % name)
        continue
    for jid, jcode, def_acc, bal in rows:
        # 1103.06 bersaldo DEBIT (Dr 1103.06 / Cr AR dari account.payment POS)
        # -> untuk menutup: Dr akun bank, Cr 1103.06 sebesar saldo debit tsb.
        amt = bal
        if abs(amt) < 0.01:
            continue
        # aj.name = JSONB (translated) -> psycopg2 mengembalikan dict, jangan di-slice
        say("   %-5s %-6s %-28s -> %s  %s" % (
            name, jcode, (env["account.journal"].browse(jid).name or "")[:28],
            AA.browse(def_acc).display_name if def_acc else "TANPA AKUN DEFAULT",
            "{:,.2f}".format(amt)))
        if not def_acc:
            raise UserError("Journal %s tidak punya default_account_id" % jcode)
        if RUN:
            mv = AM.create({
                "journal_id": jid, "date": last_day,
                "ref": "Settlement pembayaran POS %s" % jcode,
                "line_ids": [
                    (0, 0, {"account_id": def_acc, "debit": amt, "credit": 0.0,
                            "name": "Penyelesaian outstanding pembayaran POS"}),
                    (0, 0, {"account_id": out_acc, "debit": 0.0, "credit": amt,
                            "name": "Penyelesaian outstanding pembayaran POS"}),
                ],
            })
            mv.action_post()
            say("         JE %s posted @%s" % (mv.name, last_day))
    if RUN:
        env.cr.commit()
        env.invalidate_all()

# --- pass 2: Outstanding pelunasan invoice (11120003) ----------------------
# Pelunasan invoice lewat account.payment mendarat di 11120003, bukan langsung ke
# bank. Di Agustus ini diselesaikan MISC/2026/08/0036 (Dr Bank BSI / Cr 11120003).
# Tanpa langkah ini saldo 11120003 menggantung ("piutang") di akhir bulan.
out2 = acc_id("11120003")
if out2:
    for name in MONTHS:
        d_from, d_to, _t = PERIODS[name]
        last_day = (fields.Date.to_date(d_to) - timedelta(days=1))
        old = AM.search([("ref", "like", "Settlement pelunasan invoice %"),
                         ("date", ">=", d_from), ("date", "<=", last_day)])
        if old and RUN:
            old.button_draft()
            old.unlink()
            env.cr.commit()
        cr.execute("""
            SELECT aj.id, aj.code, aj.default_account_id, SUM(aml.balance)
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN account_journal aj ON aj.id = am.journal_id
            WHERE aml.account_id = %s AND am.state = 'posted'
              AND am.date >= %s AND am.date < %s
            GROUP BY 1,2,3 HAVING SUM(aml.balance) <> 0
        """, (out2, d_from, d_to))
        for jid, jcode, def_acc, bal in cr.fetchall():
            if abs(bal) < 0.01 or not def_acc:
                continue
            say("   %-5s %-6s %-28s -> %s  %s" % (
                name, jcode, (env["account.journal"].browse(jid).name or "")[:28],
                AA.browse(def_acc).display_name, "{:,.2f}".format(bal)))
            if RUN:
                mv = AM.create({
                    "journal_id": jid, "date": last_day,
                    "ref": "Settlement pelunasan invoice %s" % jcode,
                    "line_ids": [
                        (0, 0, {"account_id": def_acc, "debit": bal, "credit": 0.0,
                                "name": "Settlement pelunasan invoice"}),
                        (0, 0, {"account_id": out2, "debit": 0.0, "credit": bal,
                                "name": "Settlement pelunasan invoice"}),
                    ],
                })
                mv.action_post()
                say("         JE %s posted @%s" % (mv.name, last_day))
        if RUN:
            env.cr.commit()
            env.invalidate_all()

# ---------------------------------------------------------------------------
# 4. RAPIKAN name order (kosmetik, meniru format Agustus)
# ---------------------------------------------------------------------------
env.cr.execute("""
    UPDATE pos_order o
       SET name = c.name || ' - ' || split_part(o.pos_reference, '-', 3)
      FROM pos_session s JOIN pos_config c ON c.id = s.config_id
     WHERE o.session_id = s.id
       AND o.date_order >= '2026-06-01' AND o.date_order < '2026-08-01'
       AND (o.name IS NULL OR o.name = '/' OR o.name = '')
""")
say("name order dirapikan: %d baris" % env.cr.rowcount)
env.cr.commit()

# ---------------------------------------------------------------------------
# 5. VERIFIKASI
# ---------------------------------------------------------------------------
say("=" * 78)
say("VERIFIKASI")
for name, (a, b, _) in PERIODS.items():
    if name not in MONTHS:
        continue
    sub = POS.search([("date_order", ">=", a), ("date_order", "<", b)])
    ss = Sess.search([("start_at", ">=", a), ("start_at", "<", b)])
    say("   %-5s order=%-5d omzet=%16s | sesi=%-3d draft=%d" % (
        name, len(sub), "{:,.2f}".format(sum(sub.mapped("amount_total"))), len(ss),
        sum(1 for x in sub if x.state == "draft")))
    say("        JE POSS=%d | statement line=%d" % (
        env["account.move"].search_count([
            ("journal_id", "=", cfg.journal_id.id), ("date", ">=", a), ("date", "<", b)]),
        SL.search_count([("move_id.date", ">=", a), ("move_id.date", "<", b)])))

cr = env.cr
for label, a, b in (("Jun", "2026-06-01", "2026-07-01"), ("Jul", "2026-07-01", "2026-08-01")):
    cr.execute("""SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0)
                  FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                  WHERE am.state='posted' AND am.date >= %s AND am.date < %s""", (a, b))
    d, k = cr.fetchone()
    say("   %s TB debit=%16s credit=%16s diff=%s" % (
        label, "{:,.2f}".format(d), "{:,.2f}".format(k), "{:,.2f}".format(d - k)))

cr.execute("""SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0)
              FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
              WHERE am.state='posted'""")
d, k = cr.fetchone()
say("   TOTAL TB debit=%16s credit=%16s diff=%s" % (
    "{:,.2f}".format(d), "{:,.2f}".format(k), "{:,.2f}".format(d - k)))

# --- guard §14: piutang & outstanding HARUS nol di akhir tiap bulan ---------
say("")
say("   GUARD no-piutang (constraint §14):")
for name in MONTHS:
    d_from, d_to, _t = PERIODS[name]
    last = (fields.Date.to_date(d_to) - timedelta(days=1))
    cr.execute("""SELECT COALESCE(SUM(aml.balance),0)
                  FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                  JOIN account_account aa ON aa.id=aml.account_id
                  WHERE am.state='posted' AND am.date<=%s AND aa.account_type='asset_receivable'""",
               (last,))
    piutang = cr.fetchone()[0]
    cr.execute("""SELECT COALESCE(SUM(aml.balance),0)
                  FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                  WHERE am.state='posted' AND am.date<=%s AND aml.account_id=%s""",
               (last, out_acc))
    out = cr.fetchone()[0]
    flag = "OK" if (abs(piutang) < 0.01 and abs(out) < 0.01) else ">>> BELUM BERSIH"
    say("      %-5s s/d %s | piutang=%16s | 1103.06=%16s  %s" % (
        name, last, "{:,.2f}".format(piutang), "{:,.2f}".format(out), flag))

aug_after = POS.search([("date_order", ">=", AUG_FROM), ("date_order", "<", AUG_TO)])
say("   AGUSTUS tetap: %d order, omzet %s (semula %d / %s)" % (
    len(aug_after), "{:,.2f}".format(sum(aug_after.mapped("amount_total"))),
    aug_n, "{:,.2f}".format(aug_rev)))
say("=" * 78)
