# -*- coding: utf-8 -*-
# Micro-recon: HPP JE structure + stock valuation accounts + categories detail

def p(*a):
    print(*a)

p("1. HPP JE moves summary (which moves, journals, refs):")
env.cr.execute("""
    SELECT DISTINCT m.id, m.name, m.journal_id, j.code, m.date, m.ref, m.amount_total
    FROM account_move m
    JOIN account_move_line l ON l.move_id = m.id
    JOIN account_account a ON a.id = l.account_id
    JOIN account_journal j ON j.id = m.journal_id
    WHERE a.code_store->>'1' IN ('5101.01','5101.02','5101.03','5101.04') AND m.state='posted'
    ORDER BY m.id LIMIT 30
""")
for r in env.cr.fetchall():
    p(r)

p("")
p("2. Counter-accounts (credits) used in HPP JEs:")
env.cr.execute("""
    SELECT a.code_store->>'1' code, a.name->>'en_US' aname, SUM(l.debit) deb, SUM(l.credit) cred
    FROM account_move_line l
    JOIN account_account a ON a.id = l.account_id
    WHERE l.move_id IN (
        SELECT DISTINCT m.id FROM account_move m
        JOIN account_move_line l2 ON l2.move_id = m.id
        JOIN account_account a2 ON a2.id = l2.account_id
        WHERE a2.code_store->>'1' IN ('5101.01','5101.02','5101.04') AND m.state='posted'
    )
    GROUP BY code, aname ORDER BY cred DESC
""")
for r in env.cr.fetchall():
    p(r)

p("")
p("3. Persediaan / inventory accounts:")
env.cr.execute("""
    SELECT id, code_store->>'1' code, name->>'en_US' name, account_type, active
    FROM account_account
    WHERE name->>'en_US' ILIKE '%persediaan%' OR name->>'en_US' ILIKE '%inventori%' OR name->>'en_US' ILIKE '%inventory%'
       OR code_store->>'1' LIKE '1104%'
    ORDER BY code
""")
for r in env.cr.fetchall():
    p(r)

p("")
p("4. Category config detail (all fields relevant):")
env.cr.execute("""
    SELECT id, name, property_cost_method, property_valuation,
           property_stock_valuation_account_id,
           property_account_expense_categ_id,
           property_account_income_categ_id
    FROM product_category WHERE id IN (5,6,7,10,11)
""")
cols = ["id","name","cost","val","valuation_acc","expense_acc","income_acc"]
for r in env.cr.fetchall():
    p(dict(zip(cols, r)))

p("")
p("5. Company stock properties:")
env.cr.execute("""
    SELECT id FROM res_company WHERE id = 1
""")
p(env.cr.fetchone())

p("")
p("6. STJ journal:")
env.cr.execute("SELECT id, code, name->>'en_US', type, default_account_id FROM account_journal WHERE code='STJ'")
p(env.cr.fetchone())

p("")
p("7. Menu kit BOM products sold in Aug with qty: does kit itself get consumption move?")
env.cr.execute("""
    SELECT COUNT(DISTINCT sm.id), SUM(sm.value)
    FROM stock_move sm
    JOIN product_product pp ON pp.id = sm.product_id
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    JOIN stock_location ls ON ls.id = sm.location_id
    JOIN stock_location ld ON ld.id = sm.location_dest_id
    WHERE pt.categ_id IN (10,11) AND ls.usage='internal' AND ld.usage='customer'
      AND sm.date >= '2026-08-01' AND sm.date < '2026-09-01'
""")
p("   kit-product consumption moves (n, value):", env.cr.fetchone())

p("")
p("8. BOM explosion: sample GEPREK BAKAR ANDALAN (tmpl 577) bom lines:")
env.cr.execute("""
    SELECT b.id, bl.product_id, pt.name->>'en_US' comp, bl.product_qty, u.name->>'en_US' uom
    FROM mrp_bom b
    JOIN mrp_bom_line bl ON bl.bom_id = b.id
    JOIN product_product pp ON pp.id = bl.product_id
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    LEFT JOIN uom_uom u ON u.id = bl.product_uom_id
    WHERE b.product_tmpl_id = 577
""")
for r in env.cr.fetchall():
    p("   ", r)

env.cr.rollback()
p("DONE micro-recon.")
