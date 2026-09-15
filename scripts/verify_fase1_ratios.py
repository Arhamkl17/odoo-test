# -*- coding: utf-8 -*-
# Fase 1 verification (read-only): HPP ratio, consumption vs HPP JE, storable state

def p(*a):
    print(*a)

D1, D2 = '2026-08-01', '2026-08-31'

p("=" * 70)
p("1. REVENUE by category (POS Aug, posted orders)")
p("=" * 70)
env.cr.execute("""
    SELECT c.id, c.name AS categ, SUM(pol.price_subtotal_incl) gross, SUM(pol.price_subtotal) net,
           SUM(pol.qty) qty
    FROM pos_order_line pol
    JOIN pos_order po ON po.id = pol.order_id
    JOIN product_product pp ON pp.id = pol.product_id
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    JOIN product_category c ON c.id = pt.categ_id
    WHERE po.state IN ('done','invoiced')
      AND po.date_order AT TIME ZONE 'UTC' >= %s
      AND po.date_order AT TIME ZONE 'UTC' < (%s)::date + INTERVAL '1 day'
    GROUP BY c.id, c.name ORDER BY gross DESC
""", (D1, D2))
tot = 0.0
for r in env.cr.fetchall():
    p(r)
    tot += r[2]
p("TOTAL gross:", tot)

p("")
p("2. REVENUE Menu Food vs Menu Beverage only (incl kit parents)")
env.cr.execute("""
    SELECT c.name, SUM(pol.price_subtotal_incl) gross
    FROM pos_order_line pol
    JOIN pos_order po ON po.id = pol.order_id
    JOIN product_product pp ON pp.id = pol.product_id
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    JOIN product_category c ON c.id = pt.categ_id
    WHERE po.state IN ('done','invoiced')
      AND po.date_order AT TIME ZONE 'UTC' >= %s
      AND po.date_order AT TIME ZONE 'UTC' < (%s)::date + INTERVAL '1 day'
      AND c.id IN (10, 11)
    GROUP BY c.name
""", (D1, D2))
for r in env.cr.fetchall():
    p(r)

p("")
p("3. CONSUMPTION VALUE (internal->customer moves) vs HPP JEs (Aug)")
env.cr.execute("""
    SELECT COALESCE(SUM(sm.value),0) FROM stock_move sm
    JOIN stock_location ls ON ls.id = sm.location_id
    JOIN stock_location ld ON ld.id = sm.location_dest_id
    WHERE ls.usage='internal' AND ld.usage='customer'
      AND sm.date >= %s AND sm.date < (%s)::date + INTERVAL '1 day'
""", (D1, D2))
p("   total consumption move value:", env.cr.fetchone()[0])

env.cr.execute("""
    SELECT a.code_store->>'1' code, a.name->>'en_US' aname,
           SUM(l.debit - l.credit) aug
    FROM account_account a
    JOIN account_move_line l ON l.account_id = a.id
    JOIN account_move m ON m.id = l.move_id
    WHERE m.state='posted' AND m.date >= %s AND m.date <= %s
      AND a.code_store->>'1' IN ('5101.01','5101.02','5101.03','5101.04')
    GROUP BY code, aname ORDER BY code
""", (D1, D2))
for r in env.cr.fetchall():
    p("   JE:", r)

p("")
p("4. RAW MATERIAL products: storable? quants? (sample)")
env.cr.execute("""
    SELECT pt.id, pt.name->>'en_US' name, pt.is_storable, pt.type, c.name categ,
           (SELECT COUNT(*) FROM stock_quant q WHERE q.product_id = pp.id) n_quants
    FROM product_template pt
    JOIN product_product pp ON pp.product_tmpl_id = pt.id
    JOIN product_category c ON c.id = pt.categ_id
    WHERE c.id IN (5, 6, 7)
    ORDER BY pt.id LIMIT 15
""")
p("columns: id, name, is_storable, type, categ, n_quants")
for r in env.cr.fetchall():
    p(r)

env.cr.execute("SELECT pt.is_storable, COUNT(*) FROM product_template pt JOIN product_category c ON c.id=pt.categ_id WHERE c.id IN (5,6,7) GROUP BY pt.is_storable")
p("   raw-material storable distribution:", env.cr.fetchall())

p("")
p("5. CONSUMPTION moves by product category (top 15 by value, Aug)")
env.cr.execute("""
    SELECT c.name categ, COUNT(*) n, SUM(sm.value) val
    FROM stock_move sm
    JOIN product_product pp ON pp.id = sm.product_id
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    JOIN product_category c ON c.id = pt.categ_id
    JOIN stock_location ls ON ls.id = sm.location_id
    JOIN stock_location ld ON ld.id = sm.location_dest_id
    WHERE ls.usage='internal' AND ld.usage='customer'
      AND sm.date >= %s AND sm.date < (%s)::date + INTERVAL '1 day'
    GROUP BY c.name ORDER BY val DESC LIMIT 15
""", (D1, D2))
for r in env.cr.fetchall():
    p(r)

p("")
p("6. Menu kit products: category + storable + sold-with-consumption check")
env.cr.execute("""
    SELECT pt.is_storable, c.name, COUNT(DISTINCT pt.id)
    FROM product_template pt
    JOIN product_category c ON c.id = pt.categ_id
    WHERE pt.id IN (SELECT product_tmpl_id FROM mrp_bom)
    GROUP BY pt.is_storable, c.name
""")
p("   bom-product storable/category distribution:", env.cr.fetchall())

p("")
p("7. Which receivable account do INV/00001/2 lines use (Fase 2 prep)")
env.cr.execute("""
    SELECT m.id, m.name, a.code_store->>'1' code, a.name->>'en_US' aname, l.debit, l.credit
    FROM account_move_line l
    JOIN account_move m ON m.id = l.move_id
    JOIN account_account a ON a.id = l.account_id
    WHERE m.id IN (1290, 1292, 1294)
    ORDER BY m.id, l.debit DESC, l.credit DESC
""")
for r in env.cr.fetchall():
    p(r)

p("")
p("8. Payment JEs for the invoices? moves reconciling with 11120003 activity (Aug)")
env.cr.execute("""
    SELECT m.id, m.name, m.state, m.ref, a.code_store->>'1' code, l.debit, l.credit
    FROM account_move_line l
    JOIN account_move m ON m.id = l.move_id
    JOIN account_account a ON a.id = l.account_id
    WHERE a.code_store->>'1' = '11120003' AND m.state IN ('posted','cancel')
    ORDER BY m.id
""")
for r in env.cr.fetchall():
    p(r)

env.cr.rollback()
p("")
p("DONE fase1 verify — read only.")
