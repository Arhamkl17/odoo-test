# -*- coding: utf-8 -*-
"""
juni_juli_50_list_hpp_tinggi.py — DAFTAR MENU dengan rasio HPP > ambang (READ-ONLY).

HPP dihitung dari BOM (API native mrp.bom.explode, filter komponen daun),
dibandingkan harga jual master. Ditampilkan juga qty & omzet Juni-Agustus
supaya bisa diprioritaskan berdasarkan dampak rupiah, bukan hanya persen.

Pemakaian:
  su odoo -s /bin/bash -c "cd /workspaces/odoo-test && \
    THRESHOLD=45 odoo shell -d Test1 --no-http --db_host db --db_port 5432 \
    --db_user odoo --db_password odoo" < scripts/juni_juli_50_list_hpp_tinggi.py
"""
import os
from collections import defaultdict

THRESHOLD = float(os.environ.get("THRESHOLD", "45"))
COMM = float(os.environ.get("COMM", "10"))      # komisi platform (%) untuk kolom net
cr = env.cr
Bom = env["mrp.bom"]
Prod = env["product.product"]
say = lambda m="": print(m)


def money(x):
    return "{:,.0f}".format(float(x or 0))


def bom_cost(tmpl, qty=1.0):
    """Biaya bahan 1 porsi dari BOM. None kalau tidak ada BOM."""
    bom = Bom.search([("product_tmpl_id", "=", tmpl.id),
                      ("type", "in", ("phantom", "normal"))], limit=1)
    if not bom:
        return None
    _b, lines = bom.explode(bom.product_tmpl_id, qty)
    tot = 0.0
    for bl, vals in lines:
        comp = bl.product_id
        if not comp:
            continue
        # buang node perantara (yang punya BOM sendiri = bukan daun)
        if Bom.search_count([("product_tmpl_id", "=", comp.product_tmpl_id.id)]):
            continue
        c = comp.standard_price
        c = c.get("1") if isinstance(c, dict) else c
        tot += float(c or 0.0) * (vals.get("qty") or 0.0)
    return tot


# ---- penjualan 3 bulan per produk (POS order line) -------------------------
cr.execute("""
    SELECT pol.product_id, SUM(pol.qty), SUM(pol.price_subtotal)
      FROM pos_order_line pol JOIN pos_order po ON po.id = pol.order_id
     WHERE po.state IN ('paid','done','invoiced')
       AND po.date_order >= '2026-06-01' AND po.date_order < '2026-09-01'
     GROUP BY 1""")
sales = {int(pid): (float(q or 0), float(r or 0)) for pid, q, r in cr.fetchall() if pid}

rows = []
no_bom = []
for p in Prod.search([("sale_ok", "=", True), ("available_in_pos", "=", True)]):
    tmpl = p.product_tmpl_id
    price = tmpl.list_price or 0.0
    cost = bom_cost(tmpl)
    qty, rev = sales.get(p.id, (0.0, 0.0))
    if cost is None or cost <= 0 or price <= 0:
        if qty > 0:
            no_bom.append((qty, rev, tmpl.display_name, price, cost))
        continue
    ratio = cost / price * 100
    net = price * (1 - COMM / 100.0)
    net_ratio = cost / net * 100 if net else 999
    rows.append((ratio, net_ratio, tmpl.display_name, price, cost, qty, rev))

rows.sort(key=lambda r: -r[0])
over = [r for r in rows if r[0] > THRESHOLD]

say("=" * 118)
say("MENU DENGAN RASIO HPP > %.0f%%   (HPP dari BOM vs harga jual master)" % THRESHOLD)
say("   ambang dihitung HPP/harga jual. Kolom net = HPP/(harga x %.0f%%) — skenario komisi platform." % (100 - COMM))
say("=" * 118)
say("%-46s %10s %10s %7s %7s %8s %14s" % (
    "menu", "harga", "HPP", "HPP%", "net%", "qty 3bln", "omzet 3bln"))
say("-" * 118)
tot_rev = tot_gap = 0.0
for ratio, net_ratio, nm, price, cost, qty, rev in over:
    gap = rev * (ratio / 100.0)
    tot_rev += rev
    tot_gap += gap
    say("%-46s %10s %10s %6.1f%% %6.1f%% %8.0f %14s" % (
        (nm or "")[:46], money(price), money(cost), ratio, net_ratio, qty, money(rev)))
say("-" * 118)
say("%d menu di atas %.0f%%  |  omzet 3 bulan %s  |  nilai HPP terkait %s" % (
    len(over), THRESHOLD, money(tot_rev), money(tot_gap)))

say("")
say("SEBARAN SEMUA MENU BER-BOM (%d menu)" % len(rows))
bands = [(0, 35), (35, 40), (40, 45), (45, 50), (50, 60), (60, 100), (100, 1e9)]
for lo, hi in bands:
    sel = [r for r in rows if lo <= r[0] < hi]
    nrev = sum(r[6] for r in sel)
    say("   HPP %3d-%3s %% : %3d menu | omzet 3bln %14s" % (
        lo, ("%.0f" % hi) if hi < 1e9 else "inf", len(sel), money(nrev)))

if no_bom:
    say("")
    say("PERHATIAN — %d produk POS terjual TAPI tidak punya BOM/biaya (HPP tidak terhitung):" % len(no_bom))
    no_bom.sort(key=lambda x: -x[1])
    for qty, rev, nm, price, cost in no_bom[:25]:
        say("   %-46s harga %10s  qty %6.0f  omzet %14s" % (
            (nm or "")[:46], money(price), qty, money(rev)))
    say("   ... total %d produk, omzet %s" % (len(no_bom), money(sum(x[1] for x in no_bom))))
say("=" * 118)
env.cr.rollback()
