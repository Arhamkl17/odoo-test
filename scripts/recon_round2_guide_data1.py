# -*- coding: utf-8 -*-
# READ-ONLY round-2 recon for guide-perbaikan-sistem-data-1

def p(*a):
    print(*a)

D1, D2 = '2026-08-01', '2026-08-31'

p("=" * 70)
p("1. INSTALLED STOCK/ACCOUNTING MODULES")
p("=" * 70)
env.cr.execute("""
    SELECT name, state, latest_version FROM ir_module_module
    WHERE name IN ('stock','stock_account','mrp','mrp_account','point_of_sale','stock_pfx','account_asset_management')
    ORDER BY name
""")
for r in env.cr.fetchall():
    p(r)

p("")
p("2. WHO CREATED AUGUST consumption moves (internal->customer) & their value")
env.cr.execute("""
    SELECT sm.create_uid, u.login, COUNT(*) n, SUM(sm.value) val, MIN(sm.create_date), MAX(sm.create_date)
    FROM stock_move sm
    JOIN stock_location ls ON ls.id = sm.location_id
    JOIN stock_location ld ON ld.id = sm.location_dest_id
    JOIN res_users u ON u.id = sm.create_uid
    WHERE ls.usage='internal' AND ld.usage='customer'
      AND sm.date >= %s AND sm.date < (%s)::date + INTERVAL '1 day'
    GROUP BY sm.create_uid, u.login
""", (D1, D2))
for r in env.cr.fetchall():
    p(r)

p("")
p("   sample consumption moves of one top product (GEPREK BAKAR ANDALAN tmpl=577):")
env.cr.execute("""
    SELECT sm.id, sm.date, sm.product_uom_qty, sm.value, sm.state, sm.origin, sm.reference
    FROM stock_move sm
    JOIN product_product pp ON pp.id = sm.product_id
    WHERE pp.product_tmpl_id = 577 AND sm.date >= %s
    ORDER BY sm.id LIMIT 5
""", (D1,))
for r in env.cr.fetchall():
    p("   ", r)

p("")
p("3. HPP JEs: accounts with HPP/pokok in August")
env.cr.execute("""
    SELECT a.id, a.code_store->>'1' AS code, a.name->>'en_US' AS aname,
           SUM(CASE WHEN m.date >= %s AND m.date <= %s THEN l.debit - l.credit ELSE 0 END) AS aug,
           COUNT(DISTINCT m.id) AS n_moves
    FROM account_account a
    JOIN account_move_line l ON l.account_id = a.id
    JOIN account_move m ON m.id = l.move_id
    WHERE m.state='posted' AND (a.name->>'en_US' ILIKE '%%pokok%%' OR a.name->>'en_US' ILIKE '%%HPP%%' OR a.name->>'en_US' ILIKE '%%hpp%%')
    GROUP BY a.id, code, aname ORDER BY code
""", (D1, D2))
for r in env.cr.fetchall():
    p(r)

p("")
p("4. RECONCILIATION STATE of the 3 customer invoices")
env.cr.execute("""
    SELECT am.id, am.name, am.state, am.amount_total,
           COALESCE(SUM(part.amount),0) AS amount_reconciled,
           COUNT(DISTINCT part.id) AS n_partial
    FROM account_move am
    LEFT JOIN account_move_line aml ON aml.move_id = am.id AND aml.account_id = 123
    LEFT JOIN account_partial_reconcile part ON part.credit_move_id = aml.id OR part.debit_move_id = aml.id
    WHERE am.id IN (1290, 1292, 1294)
    GROUP BY am.id, am.name, am.state, am.amount_total
""")
for r in env.cr.fetchall():
    p(r)

p("")
p("   receivable lines on account 123 (1102.01) not fully reconciled:")
env.cr.execute("""
    SELECT l.id, l.move_id, m.name, m.state, l.debit, l.credit,
           l.balance - COALESCE(rec.rec,0) AS open_amt
    FROM account_move_line l
    JOIN account_move m ON m.id = l.move_id
    LEFT JOIN (
        SELECT aml.id, SUM(p.amount) rec
        FROM account_move_line aml
        LEFT JOIN account_partial_reconcile p ON p.credit_move_id = aml.id OR p.debit_move_id = aml.id
        GROUP BY aml.id
    ) rec ON rec.id = l.id
    WHERE l.account_id = 123 AND m.state = 'posted'
      AND l.balance - COALESCE(rec.rec,0) > 0.01
""")
for r in env.cr.fetchall():
    p(r)

p("")
p("5. KOMISI JE structure (MISC/2026/08/0043-45) lines")
env.cr.execute("""
    SELECT m.id, m.name, a.code_store->>'1' code, a.name->>'en_US' aname, l.debit, l.credit
    FROM account_move_line l
    JOIN account_move m ON m.id = l.move_id
    JOIN account_account a ON a.id = l.account_id
    WHERE m.id IN (1305,1306,1307) ORDER BY m.id, l.debit DESC
""")
for r in env.cr.fetchall():
    p(r)

p("")
p("6. JOURNALS + default accounts")
env.cr.execute("""
    SELECT j.id, j.code, j.name->>'en_US' jname, j.type, j.active,
           a.code_store->>'1' acc_code, a.name->>'en_US' acc_name
    FROM account_journal j
    LEFT JOIN account_account a ON a.id = j.default_account_id
    ORDER BY j.type, j.code
""")
for r in env.cr.fetchall():
    p(r)

p("")
p("7. AUGUST PAYMENTS grouped by method x order platform partner")
env.cr.execute("""
    SELECT pm.id, pm.name->>'en_US' method, COALESCE(rp.name,'(walk-in)') partner,
           COUNT(*) n, SUM(pp.amount) total
    FROM pos_payment pp
    JOIN pos_payment_method pm ON pm.id = pp.payment_method_id
    JOIN pos_order po ON po.id = pp.pos_order_id
    LEFT JOIN res_partner rp ON rp.id = po.partner_id
    JOIN product_product prod ON prod.id = (SELECT product_id FROM pos_order_line WHERE order_id = po.id LIMIT 1)
    WHERE po.state IN ('done','invoiced')
      AND po.date_order AT TIME ZONE 'UTC' >= %s
      AND po.date_order AT TIME ZONE 'UTC' < (%s)::date + INTERVAL '1 day'
    GROUP BY pm.id, method, partner HAVING SUM(pp.amount) > 0
    ORDER BY pm.id, total DESC
""", (D1, D2))
for r in env.cr.fetchall():
    p(r)

p("")
p("7b. TOTAL POS collection check (state done/invoiced, date_order Aug):")
env.cr.execute("""
    SELECT COUNT(DISTINCT po.id) n_orders, COALESCE(SUM(pp.amount),0) total
    FROM pos_order po
    JOIN pos_payment pp ON pp.pos_order_id = po.id
    WHERE po.state IN ('done','invoiced')
      AND po.date_order AT TIME ZONE 'UTC' >= %s
      AND po.date_order AT TIME ZONE 'UTC' < (%s)::date + INTERVAL '1 day'
""", (D1, D2))
p(env.cr.fetchone())

p("")
p("7c. Delivery omzet by platform partner (order total):")
env.cr.execute("""
    SELECT COALESCE(rp.name,'(walk-in)') partner, COUNT(*) n, SUM(po.amount_total) total
    FROM pos_order po LEFT JOIN res_partner rp ON rp.id = po.partner_id
    WHERE po.state IN ('done','invoiced')
      AND po.date_order AT TIME ZONE 'UTC' >= %s
      AND po.date_order AT TIME ZONE 'UTC' < (%s)::date + INTERVAL '1 day'
    GROUP BY partner ORDER BY total DESC
""", (D1, D2))
for r in env.cr.fetchall():
    p(r)

p("")
p("8. NON-POS products: Modal > Harga Jual (standard_price > list_price) — cost on product_product in v19")
env.cr.execute("""
    SELECT pt.id, pt.default_code, pt.name->>'en_US' name, pp.standard_price modal, pt.list_price harga,
           pt.active, c.name categ
    FROM product_template pt
    JOIN product_product pp ON pp.product_tmpl_id = pt.id
    JOIN product_category c ON c.id = pt.categ_id
    WHERE (pp.standard_price->>'1')::numeric > pt.list_price AND pt.list_price > 0
      AND pt.id NOT IN (SELECT DISTINCT product_tmpl_id FROM product_product pp2
                        JOIN pos_order_line pol ON pol.product_id = pp2.id)
    ORDER BY (pp.standard_price->>'1')::numeric - pt.list_price DESC
    LIMIT 30
""")
p("columns: id, code, name, modal, harga, active, categ")
for r in env.cr.fetchall():
    p(r)

p("")
p("9. DEPRECIATION moves structure (moves touching 6200.05 / 6101.15)")
env.cr.execute("""
    SELECT DISTINCT m.id, m.name, m.date, m.state, m.ref, m.amount_total
    FROM account_move m
    JOIN account_move_line l ON l.move_id = m.id
    JOIN account_account a ON a.id = l.account_id
    WHERE a.code_store->>'1' IN ('6200.05','6101.15') AND m.state='posted'
""")
for r in env.cr.fetchall():
    p(r)

p("")
p("   lines of those moves:")
env.cr.execute("""
    SELECT m.name, a.code_store->>'1' code, a.name->>'en_US' aname, l.debit, l.credit
    FROM account_move_line l
    JOIN account_move m ON m.id = l.move_id
    JOIN account_account a ON a.id = l.account_id
    WHERE m.id IN (
        SELECT DISTINCT m.id FROM account_move m
        JOIN account_move_line l ON l.move_id = m.id
        JOIN account_account a ON a.id = l.account_id
        WHERE a.code_store->>'1' IN ('6200.05','6101.15') AND m.state='posted'
    ) ORDER BY m.name, l.debit DESC, l.credit
""")
for r in env.cr.fetchall():
    p("   ", r)

p("")
p("10. Air Galon & suspicious non-POS products")
env.cr.execute("""
    SELECT pt.id, pt.default_code, pt.name->>'en_US', pp.standard_price->>'1', pt.list_price, pt.active, c.name
    FROM product_template pt
    JOIN product_product pp ON pp.product_tmpl_id = pt.id
    JOIN product_category c ON c.id=pt.categ_id
    WHERE pt.name->>'en_US' ILIKE '%%galon%%' OR pt.name->>'en_US' ILIKE '%%air%%'
    ORDER BY pt.name->>'en_US' LIMIT 20
""")
for r in env.cr.fetchall():
    p(r)

p("")
p("11. Duplicate accounts detail (with type/balances):")
env.cr.execute("""
    SELECT a.id, a.code_store->>'1' code, a.name->>'en_US' name, a.account_type, a.active,
           COALESCE((SELECT SUM(l.debit-l.credit) FROM account_move_line l JOIN account_move m ON m.id=l.move_id
                     WHERE l.account_id=a.id AND m.state='posted'),0) bal
    FROM account_account a
    WHERE a.name->>'en_US' IN ('Bank Suspense Account','Office Building','Office Supplies','Vehicle')
    ORDER BY a.name->>'en_US', code
""")
for r in env.cr.fetchall():
    p(r)

p("")
p("12. Bank Suspense / Kartu-related: which account do BNK1 & BNKB journals use, and Bontoala GL usage in Aug:")
env.cr.execute("""
    SELECT a.code_store->>'1' code, a.name->>'en_US' aname,
           SUM(CASE WHEN m.date >= %s AND m.date <= %s THEN l.debit-l.credit ELSE 0 END) aug_net,
           COUNT(DISTINCT m.id) n_moves
    FROM account_account a
    JOIN account_move_line l ON l.account_id = a.id
    JOIN account_move m ON m.id = l.move_id
    WHERE a.code_store->>'1' IN ('1101.01','1100.02','1111001','1112001','1101.05','1101.03','1101.04','1101.02','1101.06','1101.07','1101.08','1101.09')
      AND m.state='posted'
    GROUP BY code, aname ORDER BY code
""", (D1, D2))
for r in env.cr.fetchall():
    p(r)

env.cr.rollback()
p("")
p("DONE round-2 — read only, rolled back.")
