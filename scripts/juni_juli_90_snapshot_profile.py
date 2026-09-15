# -*- coding: utf-8 -*-
"""
juni_juli_90_snapshot_profile.py — BEKUKAN profil Agustus ke berkas JSON.

Alasan: generator Juni/Juli menurunkan semua parameternya dari Agustus. Kalau Agustus
ikut di-reset (permintaan pemilik: regenerate Juni–Agustus), basisnya hilang. Skrip ini
membekukan profil itu SEBELUM reset supaya regenerasi tetap bisa dipertanggungjawabkan.

Yang dibekukan (semua dari Agustus 2026):
  weekday      : rata-rata omzet per hari-dalam-minggu
  outlet_share : porsi omzet per OUTLET (Pallangga / Mallengkeri)
  pay_mix      : bauran metode bayar per outlet
  nlines       : distribusi jumlah baris per order
  qty          : distribusi qty per baris
  prod_weight  : frekuensi produk terjual
  prod_price   : harga efektif per produk (harga dasar take-away)

  dry-run : su odoo ... < scripts/juni_juli_90_snapshot_profile.py
  eksekusi: su odoo ... " RUN=1 odoo shell ..." < scripts/juni_juli_90_snapshot_profile.py
"""
import json
import os
from collections import Counter, defaultdict

from odoo import fields

RUN = os.environ.get("RUN") == "1"
OUT = "import_data/pos_profile_august.json"
AUG_FROM, AUG_TO = "2026-08-01", "2026-09-01"

POS = env["pos.order"]
Config = env["pos.config"]
say = lambda m="": print(m)

# ---------------------------------------------------------------- outlet (take-away) config
# Agustus hanya punya 2 config (per outlet). Config Dine In ditambahkan 13 Sep 2026.
OUTLETS = []
for c in Config.search([("name", "not like", "Dine In")], order="id"):
    pl = Config.search([("name", "=", "Dine In %s" % c.name.split(" ", 1)[-1])], limit=1)
    OUTLETS.append({
        "takeaway": c.name,
        "takeaway_id": c.id,
        "dinein": pl.name if pl else None,
        "dinein_id": pl.id if pl else None,
        "key": c.name.split(" ", 1)[-1].lower(),
    })

say("=" * 100)
say("SNAPSHOT PROFIL AGUSTUS   |   RUN=%s" % RUN)
say("=" * 100)
for o in OUTLETS:
    say("   outlet %-14s take-away='%s'(%s)  dine-in='%s'(%s)" % (
        o["key"], o["takeaway"], o["takeaway_id"], o["dinein"], o["dinein_id"])) 

aug = POS.search([("date_order", ">=", AUG_FROM), ("date_order", "<", AUG_TO)])
aug_rev = sum(aug.mapped("amount_total"))
say("")
say("Basis Agustus: %d order, omzet %s, avg/order %s" % (
    len(aug), "{:,.2f}".format(aug_rev), "{:,.0f}".format(aug_rev / len(aug))))

# ---------------------------------------------------------------- weekday
byday = defaultdict(float)
for o in aug:
    byday[o.date_order.date()] += o.amount_total
wd_sum, wd_cnt = defaultdict(float), defaultdict(int)
for d, v in byday.items():
    wd_sum[d.weekday()] += v
    wd_cnt[d.weekday()] += 1
weekday = {str(d): (wd_sum[d] / wd_cnt[d]) for d in wd_sum}

# jumlah ORDER per hari-dalam-minggu — ini yang dipakai generator 92 sebagai target,
# BUKAN omzet. Alasannya: kenaikan omzet harus murni berasal dari perbedaan harga
# per channel, sedangkan arus pelanggan (jumlah struk) tetap seperti Agustus.
wd_ord_sum, wd_ord_cnt = defaultdict(int), defaultdict(int)
for d in byday:
    wd_ord_sum[d.weekday()] += sum(1 for o in aug if o.date_order.date() == d)
    wd_ord_cnt[d.weekday()] += 1
weekday_orders = {str(d): (wd_ord_sum[d] / wd_ord_cnt[d]) for d in wd_ord_sum}

# ---------------------------------------------------------------- outlet share + pay mix
cfg_rev, cfg_n = defaultdict(float), defaultdict(int)
for o in aug:
    cfg_rev[o.session_id.config_id.id] += o.amount_total
    cfg_n[o.session_id.config_id.id] += 1
mix = defaultdict(lambda: defaultdict(float))
for o in aug:
    for p in o.payment_ids:
        mix[o.session_id.config_id.id][p.payment_method_id.id] += p.amount

outlet_data = {}
for o in OUTLETS:
    cid = o["takeaway_id"]
    if cid not in cfg_rev:
        say("   ⚠ outlet %s tidak punya data Agustus" % o["key"])
        continue
    outlet_data[o["key"]] = {
        "takeaway_id": cid,
        "dinein_id": o["dinein_id"],
        "share_rev": cfg_rev[cid] / aug_rev,
        "share_orders": cfg_n[cid] / len(aug),
        "aug_orders": cfg_n[cid],
        "pay_mix": {str(pid): amt for pid, amt in mix[cid].items()},
    }

# ---------------------------------------------------------------- struktur order
nlines_w, qty_w, prod_qty = Counter(), Counter(), Counter()
prices = defaultdict(list)
for o in aug:
    nlines_w[len(o.lines)] += 1
    for l in o.lines:
        qty_w[int(l.qty)] += 1
        prod_qty[l.product_id.id] += l.qty
        if l.qty:
            prices[l.product_id.id].append(l.price_unit)

profile = {
    "_sumber": "Agustus 2026 (beku 13 Sep 2026, sebelum regenerate Juni-Agustus)",
    "aug_orders": len(aug),
    "aug_revenue": aug_rev,
    "weekday": weekday,
    "weekday_orders": weekday_orders,
    "outlets": outlet_data,
    "nlines": {str(k): v for k, v in nlines_w.items()},
    "qty": {str(k): v for k, v in qty_w.items()},
    "prod_weight": {str(k): v for k, v in prod_qty.items()},
    "prod_price": {str(k): (sum(v) / len(v)) for k, v in prices.items()},
}

say("")
say("Ringkasan profil")
say("   weekday omzet  : %s" % " ".join("%s=%s" % (k, "{:,.0f}".format(v)) for k, v in sorted(weekday.items())))
say("   weekday ORDER  : %s" % " ".join("%s=%.1f" % (k, v) for k, v in sorted(weekday_orders.items())))
say("   outlet share   : %s" % " ".join(
    "%s omzet=%.2f%% order=%.2f%%" % (k, v["share_rev"] * 100, v["share_orders"] * 100)
    for k, v in outlet_data.items()))
say("   nlines         : %s" % sorted(((int(k), v) for k, v in profile["nlines"].items())))
say("   qty            : %s" % sorted(((int(k), v) for k, v in profile["qty"].items())))
say("   produk         : %d produk punya bobot, %d punya harga" % (
    len(prod_qty), len(prices)))

if RUN:
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=1, ensure_ascii=False)
    say("")
    say("DITULIS: %s (%d byte)" % (OUT, os.path.getsize(OUT)))
else:
    say("")
    say("DRY-RUN — tidak ada berkas ditulis.")
env.cr.rollback()
say("=" * 100)
