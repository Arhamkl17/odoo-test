# -*- coding: utf-8 -*-
# READ-ONLY audit of the full state referenced by guide-perbaikan-sistem-data-1.md
# Pipe into: su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 --db_user odoo --db_password odoo" < scripts/audit_guide_data1_state.py

def p(*a):
    print(*a)

D1, D2 = '2026-08-01', '2026-08-31'

p("=" * 70)
p("A. PRODUCT CATEGORY COSTING (Menu Food / Menu Beverage)")
p("=" * 70)
env.cr.execute("""
    SELECT DISTINCT c.id, c.name, c.property_cost_method, c.property_valuation
    FROM product_category c
    JOIN product_template pt ON pt.categ_id = c.id
    WHERE c.name ILIKE '%food%' OR c.name ILIKE '%beverage%' OR c.name ILIKE '%menu%'
""")
for r in env.cr.fetchall():
    p(r)

p("")
p("=" * 70)
p("B. AUGUST POS SALES PRODUCTS: costing method, is_storable, BOM count, qty sold")
p("=" * 70)
env.cr.execute("""
    SELECT pt.id, pt.default_code, pt.name->>'en_US' AS name,
           pc.property_cost_method, pc.property_valuation,
           pt.is_storable, pt.type,
           COALESCE((SELECT COUNT(*) FROM mrp_bom b WHERE b.product_tmpl_id = pt.id), 0) AS bom_count,
           COALESCE(SUM(pol.qty), 0) AS qty_sold
    FROM pos_order_line pol
    JOIN pos_order po ON po.id = pol.order_id
    JOIN product_product p ON p.id = pol.product_id
    JOIN product_template pt ON pt.id = p.product_tmpl_id
    LEFT JOIN product_category pc ON pc.id = pt.categ_id
    WHERE po.date_order AT TIME ZONE 'UTC' >= %s AND po.date_order AT TIME ZONE 'UTC' < (%s)::date + INTERVAL '1 day'
      AND po.state IN ('done','invoiced','paid')
    GROUP BY pt.id, pt.default_code, pt.name->>'en_US', pc.property_cost_method, pc.property_valuation, pt.is_storable, pt.type
    ORDER BY qty_sold DESC
""", (D1, D2))
rows = env.cr.fetchall()
p("columns: id, code, name, cost_method, valuation, is_storable, type, bom_count, qty_sold_august")
for r in rows[:60]:
    p(r)
p("... total distinct products sold:", len(rows))

p("")
p("=" * 70)
p("C. BOM TYPES (must be 'kit' for POS auto-consume)")
p("=" * 70)
env.cr.execute("""
    SELECT b.id, b.type, pt.name->>'en_US' AS product, b.product_qty, u.name AS uom,
           (SELECT COUNT(*) FROM mrp_bom_line bl WHERE bl.bom_id = b.id) AS n_lines
    FROM mrp_bom b
    JOIN product_product p ON p.product_tmpl_id = b.product_tmpl_id
    JOIN product_template pt ON pt.id = b.product_tmpl_id
    LEFT JOIN uom_uom u ON u.id = b.product_uom_id
    ORDER BY pt.name->>'en_US'
""")
for r in env.cr.fetchall():
    p(r)

p("")
p("=" * 70)
p("D. STOCK MOVES (Aug): consume-to-scrap vs value — root cause check for stock.move.value=0")
p("=" * 70)
env.cr.execute("""
    SELECT sm.state, loc_s.usage AS src_usage, loc_d.usage AS dest_usage,
           COUNT(*) AS n, COALESCE(SUM(sm.value),0) AS total_value
    FROM stock_move sm
    JOIN stock_location loc_s ON loc_s.id = sm.location_id
    JOIN stock_location loc_d ON loc_d.id = sm.location_dest_id
    WHERE sm.date >= %s AND sm.date < (%s)::date + INTERVAL '1 day'
    GROUP BY sm.state, loc_s.usage, loc_d.usage
    ORDER BY n DESC
""", (D1, D2))
p("columns: state, src_usage, dest_usage, n_moves, sum(value)")
for r in env.cr.fetchall():
    p(r)

p("")
try:
    env.cr.execute("SELECT COUNT(*) FROM stock_valuation_layer")
    p("D2. stock_valuation_layer total rows:", env.cr.fetchone()[0])
except Exception as e:
    p("D2. stock_valuation_layer NOT AVAILABLE:", type(e).__name__)
    env.cr.rollback()  # aborted transaction would poison the rest of the script

p("")
p("=" * 70)
p("E. CUSTOMER INVOICES (out_invoice) — all statuses")
p("=" * 70)
env.cr.execute("""
    SELECT am.id, am.name, am.partner_id, rp.name AS partner, am.amount_total,
           am.state, am.invoice_date_due, am.move_type
    FROM account_move am
    LEFT JOIN res_partner rp ON rp.id = am.partner_id
    WHERE am.move_type = 'out_invoice' AND am.name NOT LIKE '%%/POS/%%'
    ORDER BY am.id
""")
p("columns: id, name, partner_id, partner, amount_total, state, due, move_type")
for r in env.cr.fetchall():
    p(r)

p("")
p("E2. AR receivable accounts + open balances:")
env.cr.execute("""
    SELECT a.id, (a.code_store->>'1'), a.name->>'en_US' AS name, a.account_type, a.active,
           COALESCE(SUM(l.debit - l.credit), 0) AS balance
    FROM account_account a
    LEFT JOIN account_move_line l ON l.account_id = a.id
    JOIN account_move m ON m.id = l.move_id
    WHERE m.state = 'posted'
      AND a.account_type IN ('asset_receivable')
    GROUP BY a.id, (a.code_store->>'1'), a.name->>'en_US', a.account_type, a.active
    ORDER BY (a.code_store->>'1')
""")
p("columns: id, code, name, type, active, posted_balance")
for r in env.cr.fetchall():
    p(r)

p("")
p("E3. MISC/2026/08/0036 details:")
env.cr.execute("""
    SELECT am.id, am.name, am.state, am.ref, am.amount_total
    FROM account_move am WHERE am.name = 'MISC/2026/08/0036'
""")
misc = env.cr.fetchall()
for r in misc:
    p(r)
if misc:
    mid = misc[0][0]
    env.cr.execute("""
        SELECT (a.code_store->>'1'), a.name->>'en_US', l.debit, l.credit
        FROM account_move_line l JOIN account_account a ON a.id = l.account_id
        WHERE l.move_id = %s ORDER BY (a.code_store->>'1')
    """, (mid,))
    for r in env.cr.fetchall():
        p("   ", r)

p("")
p("E4. Accounts mentioned in Fase 2 (11120003, 11210010, 1102.01, Beban Piutang):")
env.cr.execute("""
    SELECT a.id, (a.code_store->>'1'), a.name->>'en_US' AS name, a.account_type, a.active,
           COALESCE((SELECT SUM(l.debit - l.credit) FROM account_move_line l JOIN account_move m ON m.id=l.move_id WHERE l.account_id=a.id AND m.state='posted'),0) AS posted_bal
    FROM account_account a
    WHERE (a.code_store->>'1') IN ('11120003','11210010','1102.01')
       OR a.name->>'en_US' ILIKE '%tak tertagih%' OR a.name->>'en_US' ILIKE '%tanda terima%'
    ORDER BY (a.code_store->>'1')
""")
for r in env.cr.fetchall():
    p(r)

p("")
p("=" * 70)
p("F. POS PAYMENT METHODS + AUGUST COLLECTION + JOURNAL/GL MAPPING")
p("=" * 70)
env.cr.execute("""
    SELECT pm.id, pm.name->>'en_US' AS method,
           COALESCE(j.code,'-') AS journal_code, j.name->>'en_US' AS journal_name, j.type AS jtype,
           (SELECT COUNT(*) FROM pos_payment pp WHERE pp.payment_method_id = pm.id
              AND pp.payment_date >= %s AND pp.payment_date <= %s) AS n_aug,
           COALESCE((SELECT SUM(pp.amount) FROM pos_payment pp WHERE pp.payment_method_id = pm.id
              AND pp.payment_date >= %s AND pp.payment_date <= %s),0) AS aug_total
    FROM pos_payment_method pm
    LEFT JOIN account_journal j ON j.id = pm.journal_id
    ORDER BY aug_total DESC
""", (D1, D2, D1, D2))
p("columns: id, method, journal_code, journal_name, jtype, n_aug, aug_total")
for r in env.cr.fetchall():
    p(r)

p("")
p("F2. GL cash/bank account balances (posted):")
env.cr.execute("""
    SELECT (a.code_store->>'1'), a.name->>'en_US' AS name, a.account_type, a.active,
           COALESCE(SUM(l.debit - l.credit),0) AS posted_bal
    FROM account_account a
    JOIN account_move_line l ON l.account_id = a.id
    JOIN account_move m ON m.id = l.move_id
    WHERE m.state = 'posted' AND a.account_type IN ('asset_cash','asset_bank')
    GROUP BY (a.code_store->>'1'), a.name->>'en_US', a.account_type, a.active
    ORDER BY posted_bal DESC
""")
p("columns: code, name, type, active, posted_balance")
for r in env.cr.fetchall():
    p(r)

p("")
p("F3. Account moves referencing POS journals in Aug (settlement check):")
env.cr.execute("""
    SELECT j.code, j.name->>'en_US' AS journal, j.type, COUNT(am.id) AS n_moves,
           COALESCE(SUM(am.amount_total),0) AS total
    FROM account_move am
    JOIN account_journal j ON j.id = am.journal_id
    WHERE am.date >= %s AND am.date <= %s AND am.state = 'posted' AND j.type IN ('bank','cash')
    GROUP BY j.code, j.name->>'en_US', j.type
""", (D1, D2))
for r in env.cr.fetchall():
    p(r)

p("")
p("=" * 70)
p("G. DUPLICATE ACCOUNTS (same name) — Fase 4")
p("=" * 70)
env.cr.execute("""
    SELECT a.name->>'en_US' AS name, COUNT(*) AS n,
           string_agg((a.code_store->>'1'), ', ' ORDER BY (a.code_store->>'1')) AS codes,
           bool_or(a.active) AS any_active
    FROM account_account a
    GROUP BY a.name->>'en_US' HAVING COUNT(*) > 1
    ORDER BY n DESC, name
""")
for r in env.cr.fetchall():
    p(r)

p("")
p("G2. Specific accounts from Fase 4:")
env.cr.execute("""
    SELECT a.id, (a.code_store->>'1'), a.name->>'en_US' AS name, a.account_type, a.active,
           COALESCE((SELECT SUM(l.debit - l.credit) FROM account_move_line l JOIN account_move m ON m.id=l.move_id WHERE l.account_id=a.id AND m.state='posted'),0) AS posted_bal
    FROM account_account a
    WHERE (a.code_store->>'1') IN ('3101.02','5101.08','1111001','1112001','12210010','12210020','12210030')
       OR a.name->>'en_US' ILIKE '%prive%' OR a.name->>'en_US' ILIKE '%stok opname%'
    ORDER BY (a.code_store->>'1')
""")
for r in env.cr.fetchall():
    p(r)

p("")
p("G3. Taxes with 11/12% amounts:")
env.cr.execute("SELECT id, name, amount, type_tax_use, active FROM account_tax ORDER BY name")
for r in env.cr.fetchall():
    if '12' in str(r[1]) or '11' in str(r[1]):
        p(r)

p("")
p("=" * 70)
p("H. DEPRECIATION accounts + August amounts — Fase 4")
p("=" * 70)
env.cr.execute("""
    SELECT (a.code_store->>'1'), a.name->>'en_US' AS name, a.account_type, a.active,
           COALESCE(SUM(CASE WHEN m.date >= %s AND m.date <= %s THEN l.debit - l.credit ELSE 0 END),0) AS aug_amount,
           COALESCE(SUM(l.debit - l.credit),0) AS total_posted
    FROM account_account a
    JOIN account_move_line l ON l.account_id = a.id
    JOIN account_move m ON m.id = l.move_id
    WHERE m.state = 'posted' AND (a.name->>'en_US' ILIKE '%%penyusutan%%')
    GROUP BY (a.code_store->>'1'), a.name->>'en_US', a.account_type, a.active
    ORDER BY (a.code_store->>'1')
""", (D1, D2))
p("columns: code, name, type, active, aug_amount, total_posted")
for r in env.cr.fetchall():
    p(r)

p("")
p("H2. Asset fixed accounts:")
env.cr.execute("""
    SELECT (a.code_store->>'1'), a.name->>'en_US' AS name, a.active,
           COALESCE(SUM(l.debit - l.credit),0) AS posted_bal
    FROM account_account a
    JOIN account_move_line l ON l.account_id = a.id
    JOIN account_move m ON m.id = l.move_id
    WHERE m.state='posted' AND a.account_type = 'asset_fixed'
    GROUP BY (a.code_store->>'1'), a.name->>'en_US', a.active ORDER BY (a.code_store->>'1')
""")
for r in env.cr.fetchall():
    p(r)

p("")
p("H3. account.asset records (OCA module):")
env.cr.execute("SELECT id, name, state FROM account_asset ORDER BY id")
ar = env.cr.fetchall()
p("   count:", len(ar))
for r in ar:
    p("   ", r)

p("")
p("=" * 70)
p("I. Void/revised JE history — Fase 5")
p("=" * 70)
env.cr.execute("""
    SELECT am.id, am.name, am.state, am.ref, am.amount_total, am.date
    FROM account_move am
    WHERE am.state = 'cancel' AND am.date >= '2026-08-01' AND am.date <= '2026-08-31'
    ORDER BY am.id
""")
p("cancelled moves in August:")
for r in env.cr.fetchall():
    p("   ", r)

env.cr.execute("""
    SELECT am.id, am.name, am.state, am.ref, am.amount_total, am.date
    FROM account_move am
    WHERE (am.ref ILIKE '%komisi%' OR am.name ILIKE '%KOM%' OR am.ref ILIKE '%gaji%' OR am.ref ILIKE '%salary%')
      AND am.date >= '2026-08-01' AND am.date <= '2026-08-31'
    ORDER BY am.id
""")
p("commission/salary moves in August (any state):")
for r in env.cr.fetchall():
    p("   ", r)

p("")
p("J. Trial balance check (posted):")
env.cr.execute("""
    SELECT SUM(l.debit) AS total_debit, SUM(l.credit) AS total_credit,
           SUM(l.debit) - SUM(l.credit) AS diff
    FROM account_move_line l JOIN account_move m ON m.id = l.move_id
    WHERE m.state = 'posted'
""")
p(env.cr.fetchone())

env.cr.rollback()
p("")
p("DONE — read only, rolled back.")
