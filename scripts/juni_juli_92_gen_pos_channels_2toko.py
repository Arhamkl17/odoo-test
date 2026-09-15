# -*- coding: utf-8 -*-
"""
juni_juli_92_gen_pos_channels_2toko.py — GENERATE POS 20 JUNI – 31 AGUSTUS (72 HARI) — 2 TOKO 3 CHANNEL

Versi portfolio skill Odoo (14 Sep 2026):
  - Tetap 2 outlet AKTIF: Pallangga (WH, config 1) + Mallengkeri (BTL, config 2)
    (config 6/7 Dine In arsip TIDAK dipakai — preset di dalam 1 toko)
  - Channel di dalam 1 toko (bukan config terpisah):
        Dine In  = 48% order  -> Harga Normal  (pl 3)
        Take Away= 32% order  -> Harga Normal  (pl 3)
        Delivery = 20% order  -> Harga Platform Online (pl 5, +10% ceil500)
    Total 80% Dine In+Take Away tetap 60/40 (48:32 = 60:40), plus 20% delivery.
  - Delivery via 3 payment: GoFood (OVO, id 11) 25% / GrabFood (GO-PAY, id 12) 50% / ShopeeFood (SPPW, id 13) 25%
    Komisi 15% dicatat terpisah sebagai Beban Komisi Platform Online (6300.01) — JE bulanan (bukan diskon).
    Harga delivery = Platform (+10%) — showcase markup nutup komisi (solusi portfolio).
  - Harga diambil dari item pricelist engine (bukan angka hardcode).
  - Pallangga = identik Tondo (weekday swing), Mallengkeri = 80% volume + best seller ranking digeser tipis (±10% jitter) + flat ±10%
  - 72 hari = 20–30 Jun (12d) + Jul (31d) + Agu (31d) = 32.736 order target (Pallangga 18.187 + Mallengkeri 14.549)
    Gross ~1,12 Miliar (net ~983 jt setelah diskon 0 karena kini komisi jadi beban, bukan contra)

Profil beku `pos_profile_august.json` tetap dipakai untuk:
  weekday_orders, nlines, qty, prod_weight — tapi OUTLET share di-override ke 55,56% vs 44,44% (80% rule).

Idempotent, dry-run default.
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
# Default untuk portfolio 72 hari. Bisa override: MONTHS=june,july,august
MONTHS = [m.strip() for m in os.environ.get("MONTHS", "june,july,august").split(",") if m.strip()]
SEED = 20260620

PROFILE_PATH = "import_data/pos_profile_august.json"
CASH_FLOAT = 500_000
DEPOSIT_JCODE = "BNK1"
KOMISI_RATE = 0.15  # 15% dari penjualan delivery

# (mulai, selesai, target JUMLAH ORDER — 2 outlet gabungan)
# Dihitung dari Tondo 8,42 jt/hari gross → Pallangga 100% Tondo + Mallengkeri 80% = 180% Tondo
# Tondo 245,8 order/hari → Pallangga 245,8 + Mallengkeri 196,6 = 442,4/hari gabungan
# 12d Jun = 5.308, Jul 13.714, Agu 13.714 → total 32.736
PERIODS = {
    "june":   ("2026-06-20", "2026-07-01", 5308),
    "july":   ("2026-07-01", "2026-08-01", 13714),
    "august": ("2026-08-01", "2026-09-01", 13714),
}

# Outlet share — Mallengkeri 80% dari Pallangga → 55,56% vs 44,44%
OUTLET_SHARE = {
    "pallangga":   {"config_id": 1, "share": 0.5555555556},
    "mallengkeri": {"config_id": 2, "share": 0.4444444444},
}
# Channel split (dalam satu outlet) — total 100%
CHANNEL_SPLIT = {
    "dinein":   0.48,  # 60% dari 80% non-delivery
    "takeaway": 0.32,  # 40% dari 80%
    "delivery": 0.20,
}
# Delivery pay split — Grab dominan (ikut Tondo Grab 78% vs Go 22%)
DELIVERY_PAY_SPLIT = {
    11: 0.25,  # GoFood (OVO)
    12: 0.50,  # GrabFood (GO-PAY) — dominan
    13: 0.25,  # ShopeeFood (ShopeePay)
}

Sess = env["pos.session"]
Prod = env["product.product"]
AM = env["account.move"]
SL = env["account.bank.statement.line"]
Config = env["pos.config"]
AJ = env["account.journal"]
PLI = env["product.pricelist.item"]
PL = env["product.pricelist"]
POS = env["pos.order"].with_context(active_test=False)

say = lambda m="": print(m)
def money(x): return "{:,.2f}".format(float(x or 0))

# ---------------------------------------------------------------------------
# 0. PROFIL + PRICELIST
# ---------------------------------------------------------------------------
say("=" * 100)
say("GENERATE POS 2 TOKO 3 CHANNEL (72 HARI) | RUN=%s | months=%s" % (RUN, ",".join(MONTHS)))
say("Outlet: Pallangga 55.56%% (identik Tondo) + Mallengkeri 44.44%% (80%% + jitter)")
say("Channel: Dine In 48%% (Normal) + Take Away 32%% (Normal) + Delivery 20%% (Platform +10%%)")
say("Delivery: Go 25%% / Grab 50%% / Shopee 25%% | komisi 15%% → Beban 6300.01")
say("=" * 100)

if not os.path.exists(PROFILE_PATH):
    raise SystemExit("Profil beku %s belum ada — jalankan 90 dulu." % PROFILE_PATH)
with open(PROFILE_PATH, encoding="utf-8") as f:
    prof = json.load(f)

WD_ORDERS = {int(k): v for k, v in prof["weekday_orders"].items()}
NLINES = sorted((int(k), v) for k, v in prof["nlines"].items())
QTY = sorted((int(k), v) for k, v in prof["qty"].items())
PROD_W = {int(k): v for k, v in prof["prod_weight"].items()}
PRODS = [p for p in PROD_W if Prod.browse(p).exists()]

# --- jitter untuk Mallengkeri best seller beda tipis ---
rng_jit = random.Random(SEED + 999)
PROD_W_MALLENGKERI = {}
for pid, w in PROD_W.items():
    jitter = rng_jit.uniform(0.90, 1.10)  # ±10%
    PROD_W_MALLENGKERI[pid] = w * jitter

pl_normal = PL.search([("name", "=", "Harga Normal")], limit=1)
pl_platform = PL.search([("name", "=", "Harga Platform Online")], limit=1)
if not pl_normal:
    raise SystemExit("Pricelist 'Harga Normal' tidak ditemukan.")
if not pl_platform:
    pl_platform = pl_normal  # fallback
say("")
say("Pricelist: Normal id=%s (%d item) | Platform id=%s (%d item)" % (
    pl_normal.id, PLI.search_count([("pricelist_id", "=", pl_normal.id)]),
    pl_platform.id, PLI.search_count([("pricelist_id", "=", pl_platform.id)])))

_price_cache = {}
def price_of(pid, channel):
    key = (pid, channel)
    if key in _price_cache:
        return _price_cache[key]
    p = Prod.browse(pid)
    pl = pl_platform if channel == "delivery" else pl_normal
    item = PLI.search([("pricelist_id", "=", pl.id), ("product_tmpl_id", "=", p.product_tmpl_id.id)], limit=1)
    v = float(item.fixed_price) if item else float(p.list_price or 0)
    _price_cache[key] = v
    return v

# Validasi config
for key, od in OUTLET_SHARE.items():
    cfg = Config.browse(od["config_id"])
    if not cfg.exists():
        raise SystemExit("Config %s untuk %s tidak ada." % (od["config_id"], key))
    say("   outlet %-12s config id=%-3s %-24s share=%.2f%% pricelist=%s" % (
        key, od["config_id"], cfg.name, od["share"]*100, cfg.pricelist_id.name or "(kosong)"))

# --- metode bayar per outlet per channel ---
# Pallangga dine/take: Tunai(1), Kartu(2), QRIS(10)
# Mallengkeri dine/take: Kartu(2), Mallengkeri Tunai(8), Mallengkeri Kartu(9), QRIS(10)
# Delivery semua: Go(11), Grab(12), Shopee(13)
PAY_MAP = {
    ("pallangga", "dinein"):   [(1, 0.067), (2, 0.283), (10, 0.65)],
    ("pallangga", "takeaway"): [(1, 0.067), (2, 0.283), (10, 0.65)],
    ("pallangga", "delivery"): [(11, 0.25), (12, 0.50), (13, 0.25)],
    ("mallengkeri", "dinein"):   [(8, 0.076), (9, 0.143), (2, 0.143), (10, 0.638)],
    ("mallengkeri", "takeaway"): [(8, 0.076), (9, 0.143), (2, 0.143), (10, 0.638)],
    ("mallengkeri", "delivery"): [(11, 0.25), (12, 0.50), (13, 0.25)],
}
say("")
say("Metode bayar per channel:")
for (outlet, chan), lst in sorted(PAY_MAP.items()):
    tot = sum(w for _, w in lst)
    names = " + ".join("%s %.0f%%" % (env["pos.payment.method"].browse(pid).name or pid, w/tot*100) for pid, w in lst)
    say("   %-12s %-9s : %s" % (outlet, chan, names))

# guard no-piutang
for (outlet, chan), lst in PAY_MAP.items():
    for pid, _w in lst:
        pm = env["pos.payment.method"].browse(pid)
        if not pm.journal_id:
            raise UserError("Guard no-piutang: metode '%s' tanpa journal." % pm.name)
say("Guard no-piutang : OK")

# ---------------------------------------------------------------------------
# 1. RENCANA PER SESI (per config per hari — channel dipilih per order)
# ---------------------------------------------------------------------------
rng = random.Random(SEED)

def weighted(items):
    return rng.choices([k for k, _ in items], weights=[w for _, w in items], k=1)[0]

def pick_products_for_outlet(n, outlet):
    weights = PROD_W if outlet == "pallangga" else PROD_W_MALLENGKERI
    avail = [(p, weights[p]) for p in PRODS if p in weights]
    out = []
    pool = avail[:]
    for _ in range(min(n, len(pool))):
        total = sum(w for _, w in pool)
        r = rng.uniform(0, total)
        acc = 0.0
        for i, (p, w) in enumerate(pool):
            acc += w
            if acc >= r:
                out.append(p)
                pool.pop(i)
                break
    return out

def build_order(sess, outlet, channel):
    n = weighted(NLINES)
    pids = pick_products_for_outlet(n, outlet)
    lines, total = [], 0.0
    for pid in pids:
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
    hour = rng.choices(range(8, 22), weights=[6, 9, 10, 8, 10, 12, 11, 10, 9, 12, 13, 12, 11, 6])[0]
    dt = "%s %02d:%02d:00" % (day, hour, rng.randrange(60))
    order = POS.create({
        "session_id": sess.id, "date_order": dt, "user_id": 1,
        "amount_tax": 0.0, "amount_total": total, "amount_paid": 0.0,
        "amount_return": 0.0, "lines": lines,
    })
    # pilih payment sesuai channel
    pay_choices = PAY_MAP[(outlet, channel)]
    pids = [p for p, _ in pay_choices]
    ws = [w for _, w in pay_choices]
    pm_id = rng.choices(pids, weights=ws, k=1)[0]
    pm = env["pos.payment.method"].browse(pm_id)
    order.add_payment({"pos_order_id": order.id, "payment_method_id": pm.id, "amount": total, "payment_date": dt})
    order.action_pos_order_paid()
    return total

# Build plan: per outlet per hari
plan = []  # (month, config_id, outlet, day, day_target)
for name in MONTHS:
    d_from, d_to, target = PERIODS[name]
    days = []
    d = fields.Date.to_date(d_from)
    end = fields.Date.to_date(d_to)
    while d < end:
        days.append(d)
        d += timedelta(days=1)
    # weekday shape untuk total gabungan, lalu bagi per outlet
    # Pallangga ikut weekday swing, Mallengkeri flat via jitter nanti
    shape = sum(WD_ORDERS.get(x.weekday(), 0) for x in days) or len(days)
    scale = float(target) / shape
    for day in days:
        base = WD_ORDERS.get(day.weekday(), 0) * scale
        for outlet, od in OUTLET_SHARE.items():
            cfg_id = od["config_id"]
            # Pallangga ikut swing 100%, Mallengkeri di-flat ±10% (multiply 0.9-1.1 random per hari)
            if outlet == "mallengkeri":
                flat_jitter = rng_jit.uniform(0.90, 1.10)
                # campur 50% swing + 50% flat untuk Mallengkeri
                day_tot = (base * 0.5 + (target / len(days)) * 0.5) * flat_jitter
            else:
                day_tot = base
            plan.append((name, cfg_id, outlet, day, max(day_tot * od["share"] / (sum(v["share"] for v in OUTLET_SHARE.values()) / len(OUTLET_SHARE) * len(OUTLET_SHARE)) * len(OUTLET_SHARE) / len(OUTLET_SHARE), 1.0)))
            # simplify: day_tot * share (karena share sudah normalized 1.0)
            # Actually share 0.555+0.444=1.0, so just base*share
            # Fix: recompute correctly
    # Recompute correctly for this month
say("")
# Rebuild plan correctly
plan = []
for name in MONTHS:
    d_from, d_to, target = PERIODS[name]
    days = []
    d = fields.Date.to_date(d_from)
    end = fields.Date.to_date(d_to)
    while d < end:
        days.append(d)
        d += timedelta(days=1)
    avg_per_day = target / len(days)
    shape = sum(WD_ORDERS.get(x.weekday(), 0) for x in days) or len(days)
    scale = float(target) / shape
    for day in days:
        swing = WD_ORDERS.get(day.weekday(), 0) * scale  # total gabungan hari itu jika ikut swing penuh
        for outlet, od in OUTLET_SHARE.items():
            share = od["share"]
            cfg_id = od["config_id"]
            if outlet == "pallangga":
                day_tot = swing * share
            else:
                # Mallengkeri: 50% swing + 50% flat avg
                flat = avg_per_day * share
                day_tot = (swing * share * 0.5 + flat * 0.5) * rng_jit.uniform(0.95, 1.05)
            plan.append((name, cfg_id, outlet, day, max(day_tot, 1.0)))
    say("%-7s : %s..%s | %2d hari | %d sesi | target %d order (gabungan)" % (
        name, d_from, d_to, len(days), len(days) * len(OUTLET_SHARE), target))

say("")
say("TOTAL RENCANA: %d sesi ( %d hari × %d outlet )" % (len(plan), len(plan)//len(OUTLET_SHARE), len(OUTLET_SHARE)))
per_month_plan = Counter(n for n, _c, _o, _d, _t in plan)
for n in MONTHS:
    say("   %-7s %d sesi | target order %d" % (n, per_month_plan[n], PERIODS[n][2]))
say("   perkiraan order/sesi: %.1f" % (sum(t for *_x, t in plan) / len(plan)))
for outlet in OUTLET_SHARE:
    tot_o = sum(t for _n, _c, o, _d, t in plan if o == outlet)
    say("   %-12s total target %.0f order (%.1f%%)" % (outlet, tot_o, tot_o / sum(t for *_x, t in plan) * 100))
say("   channel split: Dine In 48%% / Take Away 32%% / Delivery 20%%")

dep_journal = AJ.search([("code", "=", DEPOSIT_JCODE)], limit=1)
if not dep_journal or not dep_journal.default_account_id:
    raise UserError("Journal setoran %s tidak lengkap" % DEPOSIT_JCODE)
dep_bank_acc = dep_journal.default_account_id

missing = [(n, c, o, d, t) for n, c, o, d, t in plan if not Sess.search_count([("config_id", "=", c), ("start_at", "=", "%s 06:00:00" % d)])]
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
say("EKSEKUSI — 2 toko, 3 channel (delivery = Platform +10%)")
t_all = time.time()
float_ref = "Penarikan kas untuk modal laci"
for outlet, od in OUTLET_SHARE.items():
    cfg = Config.browse(od["config_id"])
    if AM.search_count([("ref", "=", "%s - %s" % (float_ref, cfg.name))]):
        continue
    cash_pm = cfg.payment_method_ids.filtered(lambda pm: pm.journal_id.type == "cash")[:1]
    if not cash_pm:
        raise UserError("Config %s tidak punya akun kas" % cfg.name)
    fm = AM.create({
        "journal_id": dep_journal.id, "date": PERIODS[MONTHS[0]][0],
        "ref": "%s - %s" % (float_ref, cfg.name),
        "line_ids": [
            (0, 0, {"account_id": cash_pm.journal_id.default_account_id.id, "debit": CASH_FLOAT, "credit": 0.0, "name": "Modal laci %s" % cfg.name}),
            (0, 0, {"account_id": dep_bank_acc.id, "debit": 0.0, "credit": CASH_FLOAT, "name": "Modal laci %s" % cfg.name}),
        ],
    })
    fm.action_post()
    say("Float laci %-26s %s" % (cfg.name, money(CASH_FLOAT)))
env.cr.commit()

created_sessions = created_orders = 0
cash_deposited = 0.0
per_month_ord = defaultdict(int)
per_month_rev = defaultdict(float)
per_outlet_ord = defaultdict(int)
per_outlet_rev = defaultdict(float)
per_chan_ord = defaultdict(int)
per_chan_rev = defaultdict(float)
per_pay_rev = defaultdict(float)
delivery_rev_per_month = defaultdict(float)
errors = []

for name, cid, outlet, day, day_target in plan:
    start_at = "%s 06:00:00" % day
    if Sess.search_count([("config_id", "=", cid), ("start_at", "=", start_at)]):
        continue
    cfg = Config.browse(cid)
    try:
        sess = Sess.create({"config_id": cid, "user_id": 1})
        sess.write({"state": "opened", "start_at": start_at, "cash_register_balance_start": CASH_FLOAT})
        env.flush_all()

        n_ord, got = 0, 0.0
        guard = 0
        while n_ord < day_target and guard < 800:
            # pilih channel per order
            ch = rng.choices(list(CHANNEL_SPLIT.keys()), weights=list(CHANNEL_SPLIT.values()), k=1)[0]
            rev = build_order(sess, outlet, ch)
            got += rev
            per_chan_ord[ch] += 1
            per_chan_rev[ch] += rev
            if ch == "delivery":
                delivery_rev_per_month[name] += rev
            n_ord += 1
            guard += 1
        env.flush_all()

        marker_m = AM.search([], order="id desc", limit=1).id or 0
        sess.write({"stop_at": "%s 23:00:00" % day})
        cash_pm = sess.payment_method_ids.filtered(lambda pm: pm.journal_id.type == "cash")[:1]
        cash_in = sum(sess.order_ids.payment_ids.filtered(lambda p: p.payment_method_id == cash_pm).mapped("amount")) if cash_pm else 0.0
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
                    (0, 0, {"account_id": dep_bank_acc.id, "debit": cash_in, "credit": 0.0, "name": "Setoran kas harian ke Bank BSI"}),
                    (0, 0, {"account_id": sess.cash_journal_id.default_account_id.id, "debit": 0.0, "credit": cash_in, "name": "Setoran kas harian ke Bank BSI"}),
                ],
            })
            dep.action_post()
            cash_deposited += cash_in

        new_moves = AM.search([("id", ">", marker_m)])
        for m in new_moves:
            if m.state == "posted" and m.date != day:
                m.with_context(skip_readonly_check=True).write({"date": day})

        env.cr.commit()
        created_sessions += 1
        created_orders += n_ord
        per_month_ord[name] += n_ord
        per_month_rev[name] += got
        per_outlet_ord[outlet] += n_ord
        per_outlet_rev[outlet] += got
        if VERBOSE:
            say("   %s %-22s %-12s %3d order %14s" % (day, cfg.name[:22], outlet, n_ord, money(got)))
    except Exception as e:
        env.cr.rollback()
        errors.append("%s %s: %s" % (day, cfg.name, repr(e)[:140]))
        say("   !! GAGAL %s %s -> %s" % (day, cfg.name, repr(e)[:140]))

say("")
say("Selesai %.1f menit | sesi=%d order=%d error=%d | setoran kas=%s" % (
    (time.time() - t_all) / 60.0, created_sessions, created_orders, len(errors), money(cash_deposited)))
for name in MONTHS:
    if per_month_ord[name]:
        say("   %-7s order=%-6d omzet=%16s avg=%s delivery=%.1f%%" % (
            name, per_month_ord[name], money(per_month_rev[name]),
            money(per_month_rev[name] / per_month_ord[name]),
            100*delivery_rev_per_month[name]/per_month_rev[name] if per_month_rev[name] else 0))
for outlet in OUTLET_SHARE:
    if per_outlet_ord[outlet]:
        say("   %-12s order=%-6d omzet=%16s avg=%s" % (
            outlet, per_outlet_ord[outlet], money(per_outlet_rev[outlet]),
            money(per_outlet_rev[outlet] / per_outlet_ord[outlet])))
rev_all = sum(per_chan_rev.values())
for ch in ("dinein", "takeaway", "delivery"):
    if per_chan_rev[ch]:
        say("   %-9s order=%-6d omzet=%16s (%.1f%% omzet | %.1f%% order)" % (
            ch, per_chan_ord[ch], money(per_chan_rev[ch]),
            100.0 * per_chan_rev[ch] / rev_all, 100.0 * per_chan_ord[ch] / created_orders))
if delivery_rev_per_month:
    tot_del = sum(delivery_rev_per_month.values())
    tot_rev = sum(per_month_rev.values())
    say("   Komisi 15%% atas delivery %s = %s → akun 6300.01 (JE bulanan terpisah)" % (money(tot_del), money(tot_del*KOMISI_RATE)))
for e in errors[:10]:
    say("   ERR " + e)

# ---------------------------------------------------------------------------
# 4. RAPIKAN name order
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
# 5. PENYELESAIAN outstanding (jika ada)
# ---------------------------------------------------------------------------
cr = env.cr
def acc_id(code):
    cr.execute("SELECT id FROM account_account WHERE code_store->>'1'=%s LIMIT 1", (code,))
    r = cr.fetchone()
    return r[0] if r else None

out_acc = acc_id("1103.06")
if out_acc:
    say("")
    say("Penyelesaian outstanding 1103.06")
    for name in MONTHS:
        d_from, d_to, _t = PERIODS[name]
        last_day = fields.Date.to_date(d_to) - timedelta(days=1)
        old = AM.search([("ref", "like", "Settlement pembayaran POS %"), ("date", ">=", d_from), ("date", "<=", last_day)])
        if old:
            old.button_draft(); old.unlink(); env.cr.commit()
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
                    (0, 0, {"account_id": def_acc, "debit": bal, "credit": 0.0, "name": "Penyelesaian outstanding pembayaran POS"}),
                    (0, 0, {"account_id": out_acc, "debit": 0.0, "credit": bal, "name": "Penyelesaian outstanding pembayaran POS"}),
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
        old = AM.search([("ref", "like", "Settlement pelunasan invoice %"), ("date", ">=", d_from), ("date", "<=", last_day)])
        if old:
            old.button_draft(); old.unlink(); env.cr.commit()
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
                    (0, 0, {"account_id": def_acc, "debit": bal, "credit": 0.0, "name": "Settlement pelunasan invoice"}),
                    (0, 0, {"account_id": out2, "debit": 0.0, "credit": bal, "name": "Settlement pelunasan invoice"}),
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
say("=" * 100)
say("VERIFIKASI — 2 TOKO 3 CHANNEL")
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
    say("        TB debit=%16s credit=%16s diff=%s" % (money(d), money(k), money(float(d or 0) - float(k or 0))))

say("")
say("   Per outlet:")
for outlet, od in OUTLET_SHARE.items():
    a0m = PERIODS[MONTHS[0]][0]; a1m = PERIODS[MONTHS[-1]][1]
    sub = POS.search([("date_order", ">=", a0m), ("date_order", "<", a1m), ("session_id.config_id", "=", od["config_id"])])
    say("   %-12s order=%-6d omzet=%16s" % (outlet, len(sub), money(sum(sub.mapped("amount_total")))))

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
say("LANGKAH LANJUTAN: komisi 15%% delivery → JE Beban Komisi 6300.01, lalu HPP & pembelian segmented.")
say("=" * 100)
