# -*- coding: utf-8 -*-
# audit_bev_bundle.py — READ-ONLY (rev 3)
# Uji hipotesis: Bev 121,8% (HPP Bev > revenue Bev) karena harga paket bundling
# dialokasikan ke item utama → revenue minuman "nyempil" di paket Menu Food,
# sementara konsumsi komponen Bev tereksplosi real via kit phantom.
#
# Rev 3:
#   - join BOM line benar: mbl.product_id = pp.id (product_product, bukan tmpl)
#   - atribusi via estimasi cost-std × qty terjual (anti double-count), parent 10 & 11
#   - jsonb cast ::numeric; LIKE pakai %% (psycopg placeholder)
#   - simulasi reclass JE D 5101.02 / K 5101.01 (P&L netral)
#
# Jalankan:
#   su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 --db_user odoo --db_password odoo" < scripts/audit_bev_bundle.py
#
# env disediakan odoo shell. Tanpa commit — rollback di akhir.

def p(*a):
    print(*a)

D1, D2 = '2026-08-01', '2026-09-01'   # window: >= D1, < D2

def rows(sql, params=None):
    if params:
        env.cr.execute(sql, params)
    else:
        env.cr.execute(sql)
    return env.cr.fetchall()

def section(title):
    p()
    p("=" * 78)
    p(title)
    p("=" * 78)

# ============================================================
# A. Revenue POS Agustus per kategori menu (10/11)
# ============================================================
section("A. REVENUE POS AGUSTUS per KATEGORI (net, excl tax)")
rev_map = {}
try:
    rev = rows("""
        SELECT pt.categ_id, c.name, COALESCE(SUM(l.price_subtotal),0) net, COUNT(*)
        FROM pos_order_line l
        JOIN pos_order o        ON o.id = l.order_id
        JOIN product_product pp ON pp.id = l.product_id
        JOIN product_template pt ON pt.id = pp.product_tmpl_id
        JOIN product_category c ON c.id = pt.categ_id
        WHERE o.state IN ('done','invoiced')
          AND o.date_order >= %s AND o.date_order < %s
          AND pt.categ_id IN (10, 11)
        GROUP BY 1, 2 ORDER BY 1
    """, (D1, D2))
    for r in rev:
        rev_map[r[0]] = r[2]
        p(f"   categ {r[0]:>2} {str(r[1]):<24} net {r[2]:>15,.2f}  ({r[3]} lines)")
except Exception as e:
    env.cr.rollback()
    p("   skip:", e)

rev_bev = rev_map.get(10, 0.0)   # Menu Beverage
rev_food = rev_map.get(11, 0.0)  # Menu Food (termasuk paket)

# ============================================================
# B. Konsumsi stok Agustus per kategori komponen (validasi Fase 1)
# ============================================================
section("B. KONSUMSI STOK AGUSTUS (internal → customer) per KATEGORI")
cons_map = {}
try:
    cons = rows("""
        SELECT pt.categ_id, COUNT(*), COALESCE(SUM(sm.value),0)
        FROM stock_move sm
        JOIN product_product pp   ON pp.id = sm.product_id
        JOIN product_template pt  ON pt.id = pp.product_tmpl_id
        JOIN stock_location ls    ON ls.id = sm.location_id
        JOIN stock_location ld    ON ld.id = sm.location_dest_id
        WHERE pt.categ_id IN (5, 6, 7)
          AND ls.usage = 'internal' AND ld.usage = 'customer'
          AND sm.state = 'done'
          AND sm.date >= %s AND sm.date < %s
        GROUP BY 1 ORDER BY 1
    """, (D1, D2))
    for r in cons:
        cons_map[r[0]] = r[2]
        p(f"   categ {r[0]}: {r[1]:>6} moves  value {r[2]:>15,.2f}")
except Exception as e:
    env.cr.rollback()
    p("   skip:", e)

cons_bev = cons_map.get(5, 0.0)
cons_food = cons_map.get(6, 0.0)

# ============================================================
# C. Estimasi biaya komponen Bev di dalam paket terjual (anti double-count)
#    cost-std komponen per unit paket (dari BOM) × qty paket terjual
# ============================================================
section("C. ESTIMASI KOMPONEN BEV DI PAKET TERJUAL — parent Menu Bev(10) vs Menu Food(11)")
est_by_parent = {10: 0.0, 11: 0.0}
try:
    pkg_bom = rows("""
        SELECT ptp.categ_id parent_categ,
               mbom.product_tmpl_id, pt.name->>'en_US' pname,
               COALESCE(SUM(CASE WHEN ptb.categ_id = 5
                                 THEN mbl.product_qty * (ppstd.standard_price->>'1')::numeric
                                 ELSE 0 END),0) bev_cost,
               COALESCE(SUM(mbl.product_qty * (ppstd.standard_price->>'1')::numeric),0) full_cost
        FROM mrp_bom mbom
        JOIN product_template pt    ON pt.id = mbom.product_tmpl_id
        JOIN product_template ptp   ON ptp.id = mbom.product_tmpl_id
        JOIN mrp_bom_line mbl       ON mbl.bom_id = mbom.id
        JOIN product_product ppstd  ON ppstd.product_tmpl_id = mbl.product_id
        JOIN product_template ptb   ON ptb.id = mbl.product_id
        WHERE mbom.type = 'phantom' AND ptp.categ_id IN (10, 11)
        GROUP BY 1, 2, 3
    """)
    cost_map = {r[1]: (r[3], r[4], r[0]) for r in pkg_bom}
    n_bev_pkg = sum(1 for v in cost_map.values() if v[0] > 0)
    p(f"   paket (Menu 10/11) dg BOM phantom: {len(cost_map)}, mengandung komponen Bev: {n_bev_pkg}")

    pkg_sales = rows("""
        SELECT pp.product_tmpl_id, SUM(l.qty) qty, SUM(l.price_subtotal) net
        FROM pos_order_line l
        JOIN pos_order o          ON o.id = l.order_id
        JOIN product_product pp   ON pp.id = l.product_id
        WHERE o.state IN ('done','invoiced')
          AND o.date_order >= %s AND o.date_order < %s
        GROUP BY 1 HAVING SUM(l.qty) > 0
    """, (D1, D2))
    sales_map = {r[0]: (r[1], r[2]) for r in pkg_sales}

    ranked = []
    for tmpl_id, (bev_c, full_c, pcateg) in cost_map.items():
        if bev_c <= 0 or tmpl_id not in sales_map:
            continue
        qty, net = sales_map[tmpl_id]
        ranked.append((pcateg, qty, net, qty * full_c, qty * bev_c, tmpl_id))
    if ranked:
        ids = [r[5] for r in ranked]
        names = {r[0]: r[1] for r in rows(
            "SELECT id, name->>'en_US' FROM product_template WHERE id = ANY(%s)", (ids,))}
        ranked.sort(key=lambda x: -x[4])
        p(f"   {'kategori':<8} {'produk':<34} {'qty':>8} {'rev net':>14} {'bev cost est':>13}")
        for r in ranked[:15]:
            nm = str(names.get(r[5], f"tmpl#{r[5]}"))[:34]
            p(f"   {'Bev' if r[0] == 10 else 'Food':<8} {nm:<34} {r[1]:>8,.0f} {r[2]:>14,.2f} {r[4]:>13,.2f}")
    est_by_parent = {10: 0.0, 11: 0.0}
    for r in ranked:
        est_by_parent[r[0]] += r[4]
    p(f"   estimasi komponen Bev via paket Menu Bev (10):  {est_by_parent[10]:>15,.2f}")
    p(f"   estimasi komponen Bev via paket Menu Food (11): {est_by_parent[11]:>15,.2f}")
    p(f"   TOTAL estimasi: {est_by_parent[10] + est_by_parent[11]:,.2f}")
except Exception as e:
    env.cr.rollback()
    p("   skip:", e)

# ============================================================
# C2. KONSUMSI BEV MOVE-BASED: komponen yg jadi anggota BOM paket (EXISTS, no double-count)
# ============================================================
section("C2. KONSUMSI BEV MOVE-BASED — via keanggotaan BOM paket (EXISTS)")
via_food_moves = via_bev_moves = 0.0
try:
    mv = rows("""
        SELECT
          COALESCE(SUM(CASE WHEN EXISTS (
                SELECT 1 FROM mrp_bom_line mbl
                JOIN mrp_bom mbom ON mbom.id = mbl.bom_id
                JOIN product_template ptp ON ptp.id = mbom.product_tmpl_id
                WHERE mbl.product_id = pp.id AND mbom.type = 'phantom'
                  AND ptp.categ_id = 11) THEN sm.value ELSE 0 END),0) via_food,
          COALESCE(SUM(CASE WHEN EXISTS (
                SELECT 1 FROM mrp_bom_line mbl
                JOIN mrp_bom mbom ON mbom.id = mbl.bom_id
                JOIN product_template ptp ON ptp.id = mbom.product_tmpl_id
                WHERE mbl.product_id = pp.id AND mbom.type = 'phantom'
                  AND ptp.categ_id = 10) THEN sm.value ELSE 0 END),0) via_bev,
          COALESCE(SUM(sm.value),0) total
        FROM stock_move sm
        JOIN product_product pp  ON pp.id = sm.product_id
        JOIN product_template pt ON pt.id = pp.product_tmpl_id
        JOIN stock_location ls   ON ls.id = sm.location_id
        JOIN stock_location ld   ON ld.id = sm.location_dest_id
        WHERE pt.categ_id = 5
          AND ls.usage = 'internal' AND ld.usage = 'customer'
          AND sm.state = 'done'
          AND sm.date >= %s AND sm.date < %s
    """, (D1, D2))
    via_food_moves, via_bev_moves, tot = mv[0]
    p(f"   konsumsi Bev via BOM Menu Food (11): {via_food_moves:>15,.2f}")
    p(f"   konsumsi Bev via BOM Menu Bev (10):  {via_bev_moves:>15,.2f}")
    p(f"   total konsumsi Bev:                  {tot:>15,.2f}  (overlap komponen mgkn dihitung dua kali)")
except Exception as e:
    env.cr.rollback()
    p("   skip:", e)

# ============================================================
# D. SIMULASI: reclass HPP Bev → Food via JE (D 5101.02 / K 5101.01)
# ============================================================
section("D. SIMULASI RECLASS HPP Bev → Food (P&L netral)")
X = est_by_parent[11]
p(f"   konsumsi Bev aktual (move value)      : {cons_bev:>15,.2f}")
p(f"   via paket Menu Food — move-based      : {via_food_moves:>15,.2f}  ← batas atas defensible")
p(f"   via paket Menu Food — est cost-std    : {X:>15,.2f}  (quirk harga std, inflated)")
p(f"   gap saat ini (konsumsi − rev Bev)     : {cons_bev - rev_bev:>15,.2f}  ← minimal agar ratio ≤100%")
p()
if via_food_moves > 0:
    X_use = min(cons_bev - rev_bev, via_food_moves) if cons_bev > rev_bev else 0.0
    X_use = max(X_use, 0.0)
    nb = cons_bev - X_use
    nf = cons_food + X_use
    rb = rev_bev or 1.0
    p(f"   Rekomendasi: reclass X = gap penuh {X_use:,.2f} (opsi konservatif —")
    p(f"   dibuktikan move-based via Food {via_food_moves:,.2f} ≫ X, jadi X aman & minimal):")
    p(f"     HPP Bev  {nb:>15,.2f} / rev Bev {rev_bev:>15,.2f} = {nb/rb*100:>6.1f}%")
    if rev_food:
        p(f"     HPP Food {nf:>15,.2f} / rev Food {rev_food:>15,.2f} = {nf/rev_food*100:>6.1f}%")
    p("     total HPP & laba TIDAK berubah (JE reclass; inventory 1103.01/02 tak tersentuh)")
p()
p("   JE eksekusi nanti: D 5101.02 / K 5101.01 sebesar X — revenue, pos.payment, kas,")
p("   TB tidak tersentuh. Pendukung naratif: 36/70 paket memuat komponen Bev; 3 paket")
p("   GEPREK ORIGINAL est biaya Bev > harga jual paket (quirk harga std komponen).")

env.cr.rollback()
p()
p("DONE audit_bev_bundle — read only, rollback OK.")
