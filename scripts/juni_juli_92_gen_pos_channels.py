# -*- coding: utf-8 -*-
"""
juni_juli_92_gen_pos_channels.py — regenerate POS Jun/JUL dengan DUA CHANNEL HARGA.

Beda dari `05_gen_pos.py`:

  1. Parameter diambil dari **beku profil** `import_data/pos_profile_august.json`
     (skrip 90), bukan langsung dari order Agustus — supaya tetap jalan walau Agustus
     ikut di-reset.
  2. Target per hari = **JUMLAH ORDER**, bukan omzet. Jadi kenaikan omzet murni berasal
     dari perbedaan harga per channel; arus pelanggan tetap.
  3. **4 POS config**: 2 outlet x 2 channel.
        Dine In   = 60% order  -> harga dari pricelist `Harga Dine In`
        Take Away = 40% order  -> harga dari pricelist `Harga Dasar (Take Away)`
     (pembagian 60/40 adalah keputusan pemilik, 13 Sep 2026)
  4. Harga diambil dari **item pricelist** (engine Odoo), bukan angka yang ditulis di
     skrip — jadi kalau pricelist diubah, datanya ikut.
  5. Float laci + setoran kas harian dibuat **per config** (dulu 2, sekarang 4).

Idempotent: sesi (config, start_at) yang sudah ada DILEWATI.

  dry-run : su odoo ... < scripts/juni_juli_92_gen_pos_channels.py
  eksekusi: su odoo ... " RUN=1 odoo shell ..." < scripts/juni_juli_92_gen_pos_channels.py

Env:
  RUN=1                  eksekusi (default dry-run)
  MONTHS=june,july       bulan yang digenerate (DEFAULT; august harus dipilih sadar)
  CH_DINEIN_REV=0.60     porsi OMZET untuk Dine In (default 0,60) — ini yang dipakai
  VERBOSE=1              cetak ringkasan per sesi

CATATAN PENTING soal 60/40:
  Angka yang disetujui pemilik ("60% Dine In") adalah **porsi OMZET**, karena itulah
  dasar perhitungan dampak +17,3% di spec §23.4. Kalau yang dibagi 60% adalah
  JUMLAH ORDER, porsi omzetnya otomatis membengkak (~66%) karena struk Dine In
  lebih besar. Skrip ini karena itu membagi OMZET, bukan order:
      d = R / (u*(1-R) + R)      R = porsi omzet target, u = rasio harga Dine In/dasar
  dengan `u` diukur dari item pricelist dan bobot produk Agustus.
"""
import json
import os
import random
import time
from collections import Counter, defaultdict
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError

RUN = os.environ.get("RUN") == "1"
VERBOSE = os.environ.get("VERBOSE") == "1"
MONTHS = [m.strip() for m in os.environ.get("MONTHS", "june,july").split(",") if m.strip()]
CH_DINEIN_REV = float(os.environ.get("CH_DINEIN_REV", "0.60"))
SEED = 20260620

PROFILE_PATH = "import_data/pos_profile_august.json"
CASH_FLOAT = 500_000
DEPOSIT_JCODE = "BNK1"

# (mulai, selesai, target JUMLAH ORDER)
PERIODS = {
    "june":   ("2026-06-20", "2026-07-01", 1582),
    "july":   ("2026-07-01", "2026-08-01", 4405),
    "august": ("2026-08-01", "2026-09-01", 4507),
}

Sess = env["pos.session"]
Prod = env["product.product"]
AM = env["account.move"]
SL = env["account.bank.statement.line"]
Config = env["pos.config"]
AA = env["account.account"]
AJ = env["account.journal"]
PLI = env["product.pricelist.item"]
PL = env["product.pricelist"]
POS = env["pos.order"].with_context(active_test=False)

say = lambda m="": print(m)


def money(x):
    return "{:,.2f}".format(float(x or 0))


# ---------------------------------------------------------------------------
# 0. PROFIL BEKU + PRICELIST
# ---------------------------------------------------------------------------
say("=" * 96)
say("GENERATE POS DUA CHANNEL   |   RUN=%s | months=%s | dine-in=%.0f%% OMZET" % (
    RUN, ",".join(MONTHS), CH_DINEIN_REV * 100))
say("=" * 96)

if not os.path.exists(PROFILE_PATH):
    raise SystemExit("Profil beku %s belum ada — jalankan 90 dulu." % PROFILE_PATH)
with open(PROFILE_PATH, encoding="utf-8") as f:
    prof = json.load(f)

WD_ORDERS = {int(k): v for k, v in prof["weekday_orders"].items()}
NLINES = sorted((int(k), v) for k, v in prof["nlines"].items())
QTY = sorted((int(k), v) for k, v in prof["qty"].items())
PROD_W = {int(k): v for k, v in prof["prod_weight"].items()}
PRODS = [p for p in PROD_W if Prod.browse(p).exists()]

# PATCH 14 Sep 2026 — struktur "harga tunggal + markup platform 10%"
# Pricelist "Harga Dasar (Take Away)" sudah di-rename jadi "Harga Normal" oleh juni_juli_112.
# "Harga Dine In" (id 4) arsip — tetap ada tapi tidak dipakai; fallback ke Normal.
pl_take = PL.search([("name", "=", "Harga Normal")], limit=1)
pl_dine = PL.search([("name", "=", "Harga Dine In")], limit=1)
pl_platform = PL.search([("name", "=", "Harga Platform Online")], limit=1)
if not pl_take:
    raise SystemExit("Pricelist 'Harga Normal' tidak ditemukan.")
# Fallback: kalau Dine In arsip/kosong, pakai Normal (harga tunggal)
if not pl_dine:
    pl_dine = pl_take
if not pl_platform:
    pl_platform = pl_take

_price_cache = {}


def price_of(pid, channel):
    key = (pid, channel)
    if key in _price_cache:
        return _price_cache[key]
    p = Prod.browse(pid)
    pl = pl_take if channel == "takeaway" else pl_dine
    item = PLI.search([("pricelist_id", "=", pl.id),
                       ("product_tmpl_id", "=", p.product_tmpl_id.id)], limit=1)
    v = float(item.fixed_price) if item else float(p.list_price or 0)
    _price_cache[key] = v
    return v


# --- rasio harga Dine In / dasar, diukur dari komposisi produk Agustus ---------------
_num = sum(PROD_W[p] * price_of(p, "dinein") for p in PRODS if price_of(p, "takeaway") > 0)
_den = sum(PROD_W[p] * price_of(p, "takeaway") for p in PRODS if price_of(p, "takeaway") > 0)
UPLIFT = (_num / _den) if _den else 1.0
# bagi OMZET, bukan order: d = R / (u(1-R) + R)
CH_DINEIN = CH_DINEIN_REV / (UPLIFT * (1 - CH_DINEIN_REV) + CH_DINEIN_REV)
CH_TAKEAWAY = 1.0 - CH_DINEIN
say("")
say("Rasio harga Dine In / dasar (bobot Agustus) : %.4fx" % UPLIFT)
say("Porsi OMZET Dine In target                   : %.1f%%" % (CH_DINEIN_REV * 100))
say("=> porsi JUMLAH ORDER Dine In                 : %.1f%% (sisanya %.1f%%)" % (
    CH_DINEIN * 100, CH_TAKEAWAY * 100))

# ---------------------------------------------------------------------------
# 1. CONFIG PER CHANNEL
# ---------------------------------------------------------------------------
CHANNELS = {}          # cfg_id -> {"channel":..., "outlet":..., "weight":...}
for key, od in prof["outlets"].items():
    share = od["share_orders"]
    for chan, frac in (("dinein", CH_DINEIN), ("takeaway", CH_TAKEAWAY)):
        cid = od["dinein_id"] if chan == "dinein" else od["takeaway_id"]
        if not cid or not Config.browse(cid).exists():
            raise SystemExit("Config %s untuk %s/%s tidak ada." % (cid, key, chan))
        CHANNELS[cid] = {"channel": chan, "outlet": key,
                         "weight": share * frac, "pay_mix": od["pay_mix"]}

say("")
say("Config yang dipakai")
tot_w = sum(c["weight"] for c in CHANNELS.values())
for cid, c in sorted(CHANNELS.items()):
    cfg = Config.browse(cid)
    say("   id=%-3s %-24s channel=%-9s bobot order=%5.2f%%  pricelist=%s" % (
        cid, cfg.name, c["channel"], 100.0 * c["weight"] / tot_w,
        cfg.pricelist_id.name or "(kosong)"))


# --- bauran metode bayar: petakan per KELUARGA, lalu ambil metode milik config --------
def family(pm):
    j = pm.journal_id
    if j and j.type == "cash":
        return "cash"
    n = (pm.name or "").upper()
    if "QRIS" in n:
        return "qris"
    if "SHOPEE" in n or "DELIVERY" in n:
        return "delivery"
    return "card"


def pay_weights(cid):
    """Bobot = bauran Agustus, tapi hanya untuk metode yang BENAR-BENAR dipakai.

    Catatan: `Akun Pelanggan` (pay_later) terdaftar di config 1 tetapi tidak pernah
    dipakai Agustus. Kalau ikut dimasukkan, guard no-piutang (§14) memicu — dan itu
    memang benar. Jadi metode yang tidak ada di bauran Agustus hanya boleh masuk
    kalau ia adalah KAS milik config ini (yang baru dibuat untuk channel Dine In).
    """
    c = CHANNELS[cid]
    dipakai = {int(pid) for pid in c["pay_mix"]}
    fam_w = defaultdict(float)
    for pid, amt in c["pay_mix"].items():
        fam_w[family(env["pos.payment.method"].browse(int(pid)))] += float(amt)
    cfg = Config.browse(cid)
    per_fam = defaultdict(list)
    for pm in cfg.payment_method_ids:
        if pm.id in dipakai or family(pm) == "cash":
            per_fam[family(pm)].append(pm)
        else:
            say("      (dilewati: '%s' tidak dipakai Agustus)" % pm.name)
    out = []
    for fam, pms in per_fam.items():
        w = fam_w.get(fam, 0.0)
        if w <= 0 or not pms:
            continue
        for pm in pms:
            out.append((pm, w / len(pms)))
    if not out:
        raise UserError("Config %s tidak punya metode bayar yang cocok." % cfg.name)
    return out


PAY = {cid: pay_weights(cid) for cid in CHANNELS}
say("")
say("Bauran metode bayar per config")
for cid, lst in sorted(PAY.items()):
    tot = sum(w for _p, w in lst)
    say("   %-24s %s" % (Config.browse(cid).name, " ".join(
        "%s %.1f%%" % (pm.name, 100 * w / tot) for pm, w in lst)))

# --- guard §14: tidak boleh ada piutang ------------------------------------------
for cid, lst in PAY.items():
    for pm, _w in lst:
        if pm.type == "pay_later" or not pm.journal_id:
            raise UserError("Guard no-piutang (§14): metode '%s' bikin piutang." % pm.name)
say("Guard no-piutang : OK")

# ---------------------------------------------------------------------------
# 2. RENCANA PER SESI
# ---------------------------------------------------------------------------
rng = random.Random(SEED)


def weighted(items):
    return rng.choices([k for k, _ in items], weights=[w for _, w in items], k=1)[0]


def pick_products(n):
    pool = [(p, PROD_W[p]) for p in PRODS]
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
    return out


def build_order(sess, cid, channel):
    n = weighted(NLINES)
    lines, total = [], 0.0
    for pid in pick_products(n):
        q = weighted(QTY)
        price = price_of(pid, channel)
        lines.append((0, 0, {
            "product_id": pid, "qty": q, "price_unit": price,
            "price_subtotal": price * q, "price_subtotal_incl": price * q,
            "tax_ids": [(6, 0, [])], "price_type": "original",
        }))
        total += price * q
    total = round(total)
    if total <= 0:
        pid = PRODS[0]
        total = 1000
        lines = [(0, 0, {"product_id": pid, "qty": 1, "price_unit": 1000,
                         "price_subtotal": 1000, "price_subtotal_incl": 1000,
                         "tax_ids": [(6, 0, [])], "price_type": "original"})]

    day = sess.start_at.date()
    hour = rng.choices(range(8, 22),
                       weights=[6, 9, 10, 8, 10, 12, 11, 10, 9, 12, 13, 12, 11, 6])[0]
    dt = "%s %02d:%02d:00" % (day, hour, rng.randrange(60))

    order = POS.create({
        "session_id": sess.id, "date_order": dt, "user_id": 1,
        "amount_tax": 0.0, "amount_total": total, "amount_paid": 0.0,
        "amount_return": 0.0, "lines": lines,
    })
    pm = rng.choices([p for p, _ in PAY[cid]], weights=[w for _, w in PAY[cid]])[0]
    order.add_payment({"pos_order_id": order.id, "payment_method_id": pm.id,
                       "amount": total, "payment_date": dt})
    order.action_pos_order_paid()
    return total


plan = []
for name in MONTHS:
    d_from, d_to, target = PERIODS[name]
    days = []
    d = fields.Date.to_date(d_from)
    end = fields.Date.to_date(d_to)
    while d < end:
        days.append(d)
        d += timedelta(days=1)
    # sebar target ORDER bulan itu ke hari menurut profil weekday Agustus
    shape = sum(WD_ORDERS.get(x.weekday(), 0) for x in days) or len(days)
    scale = float(target) / shape
    for day in days:
        day_tot = WD_ORDERS.get(day.weekday(), 0) * scale
        for cid, c in CHANNELS.items():
            plan.append((name, cid, c["channel"], day, max(day_tot * c["weight"] / tot_w, 1.0)))
    say("")
    say("%-7s : %s..%s | %2d hari | %d sesi | target %d order" % (
        name, d_from, d_to, len(days), len(days) * len(CHANNELS), target))

say("")
say("TOTAL RENCANA: %d sesi" % len(plan))
per_month_plan = Counter(n for n, _c, _ch, _d, _t in plan)
for n in MONTHS:
    say("   %-7s %d sesi | target order %d" % (n, per_month_plan[n], PERIODS[n][2]))
say("   perkiraan order/ sesi: %.1f" % (
    sum(t for *_x, t in plan) / len(plan)))
_plan_ord = sum(t for *_x, t in plan)
_plan_dn = sum(t for _n, _c, ch, _d, t in plan if ch == "dinein")
say("   perkiraan porsi ORDER dine-in: %.1f%%" % (100.0 * _plan_dn / _plan_ord))
for n in MONTHS:
    say("   %-7s target %.0f order => %.0f dine-in / %.0f take-away" % (
        n, PERIODS[n][2], PERIODS[n][2] * CH_DINEIN, PERIODS[n][2] * CH_TAKEAWAY))

dep_journal = AJ.search([("code", "=", DEPOSIT_JCODE)], limit=1)
if not dep_journal or not dep_journal.default_account_id:
    raise UserError("Journal setoran %s tidak lengkap" % DEPOSIT_JCODE)
dep_bank_acc = dep_journal.default_account_id

missing = [(n, c, ch, d, t) for n, c, ch, d, t in plan
           if not Sess.search_count([("config_id", "=", c), ("start_at", "=", "%s 06:00:00" % d)])]
say("Sesi baru: %d | sudah ada (dilewati): %d" % (len(missing), len(plan) - len(missing)))

if not RUN:
    say("")
    say("DRY-RUN — tidak ada data ditulis. Jalankan dengan RUN=1 untuk eksekusi.")
    env.cr.rollback()
    raise SystemExit(0)

# ---------------------------------------------------------------------------
# 3. EKSEKUSI
# ---------------------------------------------------------------------------
say("")
say("EKSEKUSI")
t_all = time.time()
float_ref = "Penarikan kas untuk modal laci"
for cid in CHANNELS:
    cfg = Config.browse(cid)
    if AM.search_count([("ref", "=", "%s - %s" % (float_ref, cfg.name))]):
        continue
    cash_pm = cfg.payment_method_ids.filtered(lambda pm: pm.journal_id.type == "cash")[:1]
    if not cash_pm:
        raise UserError("Config %s tidak punya akun kas" % cfg.name)
    fm = AM.create({
        "journal_id": dep_journal.id, "date": PERIODS[MONTHS[0]][0],
        "ref": "%s - %s" % (float_ref, cfg.name),
        "line_ids": [
            (0, 0, {"account_id": cash_pm.journal_id.default_account_id.id,
                    "debit": CASH_FLOAT, "credit": 0.0, "name": "Modal laci %s" % cfg.name}),
            (0, 0, {"account_id": dep_bank_acc.id, "debit": 0.0, "credit": CASH_FLOAT,
                    "name": "Modal laci %s" % cfg.name}),
        ],
    })
    fm.action_post()
    say("Float laci %-26s %s" % (cfg.name, money(CASH_FLOAT)))
env.cr.commit()

created_sessions = created_orders = 0
cash_deposited = 0.0
per_month_ord = defaultdict(int)
per_month_rev = defaultdict(float)
per_chan_ord = defaultdict(int)
per_chan_rev = defaultdict(float)
errors = []

for name, cid, channel, day, day_target in plan:
    start_at = "%s 06:00:00" % day
    if Sess.search_count([("config_id", "=", cid), ("start_at", "=", start_at)]):
        continue
    cfg = Config.browse(cid)
    try:
        sess = Sess.create({"config_id": cid, "user_id": 1})
        sess.write({"state": "opened", "start_at": start_at,
                    "cash_register_balance_start": CASH_FLOAT})
        env.flush_all()

        n_ord, got, guard = 0, 0.0, 0
        while n_ord < day_target and guard < 600:
            got += build_order(sess, cid, channel)
            n_ord += 1
            guard += 1
        env.flush_all()

        marker_m = AM.search([], order="id desc", limit=1).id or 0
        marker_s = SL.search([], order="id desc", limit=1).id or 0
        sess.write({"stop_at": "%s 23:00:00" % day})
        cash_pm = sess.payment_method_ids.filtered(lambda pm: pm.journal_id.type == "cash")[:1]
        cash_in = sum(sess.order_ids.payment_ids.filtered(
            lambda p: p.payment_method_id == cash_pm).mapped("amount")) if cash_pm else 0.0
        if sess.config_id.cash_control:
            sess.write({"cash_register_balance_end_real": CASH_FLOAT + cash_in})
            env.flush_all()
        sess.action_pos_session_closing_control()
        env.flush_all()

        if cash_in:
            dep = AM.create({
                "journal_id": dep_journal.id, "date": day,
                "ref": "Setoran kas %s" % cfg.name,
                "line_ids": [
                    (0, 0, {"account_id": dep_bank_acc.id, "debit": cash_in, "credit": 0.0,
                            "name": "Setoran kas harian ke Bank BSI"}),
                    (0, 0, {"account_id": sess.cash_journal_id.default_account_id.id,
                            "debit": 0.0, "credit": cash_in,
                            "name": "Setoran kas harian ke Bank BSI"}),
                ],
            })
            dep.action_post()
            cash_deposited += cash_in

        # Odoo menstempel tanggal HARI INI; tulis ulang ke tanggal sesi
        new_moves = AM.search([("id", ">", marker_m)])
        for m in new_moves:
            if m.state == "posted" and m.date != day:
                m.with_context(skip_readonly_check=True).write({"date": day})

        env.cr.commit()
        created_sessions += 1
        created_orders += n_ord
        per_month_ord[name] += n_ord
        per_month_rev[name] += got
        per_chan_ord[channel] += n_ord
        per_chan_rev[channel] += got
        if VERBOSE:
            say("   %s %-22s %-9s %3d order %14s" % (day, cfg.name[:22], channel, n_ord, money(got)))
    except Exception as e:
        env.cr.rollback()
        errors.append("%s %s: %s" % (day, cfg.name, repr(e)[:140]))
        say("   !! GAGAL %s %s -> %s" % (day, cfg.name, repr(e)[:140]))

say("")
say("Selesai %.1f menit | sesi=%d order=%d error=%d | setoran kas=%s" % (
    (time.time() - t_all) / 60.0, created_sessions, created_orders, len(errors), money(cash_deposited)))
for name in MONTHS:
    if per_month_ord[name]:
        say("   %-7s order=%-6d omzet=%16s avg=%s" % (
            name, per_month_ord[name], money(per_month_rev[name]),
            money(per_month_rev[name] / per_month_ord[name])))
rev_all = sum(per_chan_rev.values())
for chan in ("dinein", "takeaway"):
    if per_chan_rev[chan]:
        say("   %-9s order=%-6d omzet=%16s (%.1f%% omzet)" % (
            chan, per_chan_ord[chan], money(per_chan_rev[chan]),
            100.0 * per_chan_rev[chan] / rev_all))
for e in errors[:10]:
    say("   ERR " + e)

# ---------------------------------------------------------------------------
# 4. RAPIKAN name order (kosmetik, format Agustus)
# ---------------------------------------------------------------------------
a0 = PERIODS[MONTHS[0]][0]
a1 = PERIODS[MONTHS[-1]][1]
env.cr.execute("""
    UPDATE pos_order o
       SET name = c.name || ' - ' || split_part(o.pos_reference, '-', 3)
      FROM pos_session s JOIN pos_config c ON c.id = s.config_id
     WHERE o.session_id = s.id AND o.date_order >= %s AND o.date_order < %s
       AND (o.name IS NULL OR o.name = '/' OR o.name = '')
""", (a0, a1))
say("name order dirapikan: %d baris" % env.cr.rowcount)
env.cr.commit()

# ---------------------------------------------------------------------------
# 5. PENYELESAIAN 1103.06 + 11120003 per akhir bulan (constraint §14)
# ---------------------------------------------------------------------------
cr = env.cr


def acc_id(code):
    cr.execute("SELECT id FROM account_account WHERE code_store->>'1'=%s LIMIT 1", (code,))
    r = cr.fetchone()
    return r[0] if r else None


out_acc = acc_id("1103.06")
say("")
say("Penyelesaian outstanding 1103.06")
for name in MONTHS:
    d_from, d_to, _t = PERIODS[name]
    last_day = fields.Date.to_date(d_to) - timedelta(days=1)
    old = AM.search([("ref", "like", "Settlement pembayaran POS %"),
                     ("date", ">=", d_from), ("date", "<=", last_day)])
    if old:
        old.button_draft()
        old.unlink()
        env.cr.commit()
    cr.execute("""
        SELECT aj.id, aj.code, aj.default_account_id, SUM(aml.balance)
          FROM account_move_line aml
          JOIN account_move am ON am.id = aml.move_id
          JOIN account_journal aj ON aj.id = am.journal_id
         WHERE aml.account_id = %s AND am.state='posted'
           AND am.date >= %s AND am.date < %s
         GROUP BY 1,2,3 HAVING SUM(aml.balance) <> 0
    """, (out_acc, d_from, d_to))
    for jid, jcode, def_acc, bal in cr.fetchall():
        if abs(bal) < 0.01 or not def_acc:
            continue
        mv = AM.create({
            "journal_id": jid, "date": last_day,
            "ref": "Settlement pembayaran POS %s" % jcode,
            "line_ids": [
                (0, 0, {"account_id": def_acc, "debit": bal, "credit": 0.0,
                        "name": "Penyelesaian outstanding pembayaran POS"}),
                (0, 0, {"account_id": out_acc, "debit": 0.0, "credit": bal,
                        "name": "Penyelesaian outstanding pembayaran POS"}),
            ],
        })
        mv.action_post()
        say("   %-7s %-6s %16s -> %s" % (name, jcode, money(bal), mv.name))
    env.cr.commit()
    env.invalidate_all()

out2 = acc_id("11120003")
if out2:
    say("")
    say("Penyelesaian outstanding 11120003")
    for name in MONTHS:
        d_from, d_to, _t = PERIODS[name]
        last_day = fields.Date.to_date(d_to) - timedelta(days=1)
        old = AM.search([("ref", "like", "Settlement pelunasan invoice %"),
                         ("date", ">=", d_from), ("date", "<=", last_day)])
        if old:
            old.button_draft()
            old.unlink()
            env.cr.commit()
        cr.execute("""
            SELECT aj.id, aj.code, aj.default_account_id, SUM(aml.balance)
              FROM account_move_line aml
              JOIN account_move am ON am.id = aml.move_id
              JOIN account_journal aj ON aj.id = am.journal_id
             WHERE aml.account_id = %s AND am.state='posted'
               AND am.date >= %s AND am.date < %s
             GROUP BY 1,2,3 HAVING SUM(aml.balance) <> 0
        """, (out2, d_from, d_to))
        for jid, jcode, def_acc, bal in cr.fetchall():
            if abs(bal) < 0.01 or not def_acc:
                continue
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
            say("   %-7s %-6s %16s -> %s" % (name, jcode, money(bal), mv.name))
        env.cr.commit()
        env.invalidate_all()

# ---------------------------------------------------------------------------
# 6. VERIFIKASI
# ---------------------------------------------------------------------------
say("")
say("=" * 96)
say("VERIFIKASI")
for name in MONTHS:
    a, b, _t = PERIODS[name]
    sub = POS.search([("date_order", ">=", a), ("date_order", "<", b)])
    ss = Sess.search([("start_at", ">=", a), ("start_at", "<", b)])
    say("   %-7s order=%-6d omzet=%16s | sesi=%-4d draft=%d" % (
        name, len(sub), money(sum(sub.mapped("amount_total"))), len(ss),
        sum(1 for x in sub if x.state == "draft")))
    cr.execute("""SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0)
                    FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                   WHERE am.state='posted' AND am.date >= %s AND am.date < %s""", (a, b))
    d, k = cr.fetchone()
    say("        TB debit=%16s credit=%16s diff=%s" % (
        money(d), money(k), money(float(d or 0) - float(k or 0))))

say("")
say("   GUARD no-piutang (§14)")
for name in MONTHS:
    d_from, d_to, _t = PERIODS[name]
    last = fields.Date.to_date(d_to) - timedelta(days=1)
    cr.execute("""SELECT COALESCE(SUM(aml.balance),0)
                    FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND am.date<=%s
                     AND aa.account_type='asset_receivable'""", (last,))
    piutang = cr.fetchone()[0]
    cr.execute("""SELECT COALESCE(SUM(aml.balance),0)
                    FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                   WHERE am.state='posted' AND am.date<=%s AND aml.account_id=%s""", (last, out_acc))
    out = cr.fetchone()[0]
    say("      %-7s s/d %s | piutang=%16s | 1103.06=%16s  %s" % (
        name, last, money(piutang), money(out),
        "OK" if (abs(float(piutang)) < 0.01 and abs(float(out)) < 0.01) else ">>> BELUM BERSIH"))
say("")
say("LANGKAH LANJUTAN: 21_hpp_generate.py (MONTHS=june,july) lalu 34_pembelian_tunai.py.")
say("=" * 96)
