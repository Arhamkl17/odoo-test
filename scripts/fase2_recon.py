# -*- coding: utf-8 -*-
# Fase 2 pre-execution recon (READ-ONLY): lock dates, exact AML pairs to reconcile,
# references to accounts 4/5/117 (journals, payment methods, partner properties, configs).

def p(*a):
    print(*a)

p("1. Lock dates:")
env.cr.execute("""
    SELECT fiscalyear_lock_date, tax_lock_date, sale_lock_date, purchase_lock_date, hard_lock_date
    FROM res_company WHERE id = 1
""")
p("   ", env.cr.fetchone())

p("")
p("2. All move lines on accounts 4 (11210010), 5 (11210011), 117 (11120003) — posted only:")
env.cr.execute("""
    SELECT l.account_id, a.code_store->>'1' code, l.id, l.move_id, m.name, m.state,
           l.debit, l.credit, l.balance, l.reconciled, l.partner_id
    FROM account_move_line l
    JOIN account_move m ON m.id = l.move_id
    JOIN account_account a ON a.id = l.account_id
    WHERE l.account_id IN (4, 5, 117) AND m.state = 'posted'
    ORDER BY l.account_id, l.move_id, l.id
""")
for r in env.cr.fetchall():
    p("   ", r)

p("")
p("3. Reconciliation state of those lines (partial reconciles touching them):")
env.cr.execute("""
    SELECT l.id, l.move_id, m.name, l.debit, l.credit, l.balance, l.reconciled,
           (SELECT COUNT(*) FROM account_partial_reconcile pr
             WHERE pr.credit_move_id = l.id OR pr.debit_move_id = l.id) n_partials
    FROM account_move_line l
    JOIN account_move m ON m.id = l.move_id
    WHERE l.account_id IN (4, 117) AND m.state = 'posted'
    ORDER BY l.id
""")
for r in env.cr.fetchall():
    p("   ", r)

p("")
p("4. References to accounts 4/5/117:")
p("   a) journal default_account / payment credit/debit accounts:")
env.cr.execute("""
    SELECT j.id, j.code, j.name->>'en_US', j.default_account_id,
           j.payment_credit_account_id, j.payment_debit_account_id, j.suspense_account_id
    FROM account_journal j
    WHERE j.default_account_id IN (4,5,117)
       OR j.payment_credit_account_id IN (4,5,117)
       OR j.payment_debit_account_id IN (4,5,117)
       OR j.suspense_account_id IN (4,5,117)
""")
for r in env.cr.fetchall():
    p("   ", r)

p("   b) pos.payment_method receivable_account:")
env.cr.execute("""
    SELECT id, name->>'en_US', journal_id, receivable_account_id
    FROM pos_payment_method WHERE receivable_account_id IN (4,5,117)
""")
for r in env.cr.fetchall():
    p("   ", r)

p("   c) payment method 'Akun Pelanggan' (id 3) full row:")
env.cr.execute("""
    SELECT id, name->>'en_US', split_payments, receivable_account_id, journal_id
    FROM pos_payment_method WHERE id = 3
""")
p("   ", env.cr.fetchone())

p("   d) journals whose 'incoming/outgoing' payment methods reference these accounts:")
env.cr.execute("""
    SELECT id, code, name->>'en_US', type FROM account_journal WHERE type IN ('bank','cash','general')
""")
p("   (manual review against a/b above)")

p("   e) res.partner receivable properties (v19 storage):")
env.cr.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'res_partner' AND column_name ILIKE '%receivable%' OR column_name ILIKE '%account%' AND table_name='res_partner'
""")
cols = [r[0] for r in env.cr.fetchall()]
p("   partner account columns:", cols)
for col in cols:
    env.cr.execute(f"SELECT id, name FROM res_partner WHERE {col} IN (4,5,117)")
    rows = env.cr.fetchall()
    if rows:
        p(f"   {col} ->", rows[:10])

p("   f) any other table FK to account_account 4/5/117 (company properties, fiscal positions):")
env.cr.execute("""
    SELECT DISTINCT t.table_name, c.column_name
    FROM information_schema.columns c
    JOIN information_schema.tables t ON t.table_name = c.table_name AND t.table_schema='public'
    WHERE c.column_name ILIKE '%account%id%'
      AND t.table_name NOT IN ('account_move_line','account_move','account_journal','account_account','res_partner')
""")
fkcols = env.cr.fetchall()
for tn, cn in fkcols:
    try:
        env.cr.execute(f"SELECT COUNT(*) FROM \"{tn}\" WHERE \"{cn}\" IN (4,5,117)")
        n = env.cr.fetchone()[0]
        if n:
            p(f"   {tn}.{cn}: {n} rows")
    except Exception:
        env.cr.rollback()

p("")
p("5. Account 123 (1102.01) current open balance (should be 5.2M pre-cancel):")
env.cr.execute("""
    SELECT l.id, l.move_id, m.name, l.debit, l.credit, l.reconciled
    FROM account_move_line l JOIN account_move m ON m.id = l.move_id
    WHERE l.account_id = 123 AND m.state='posted'
""")
for r in env.cr.fetchall():
    p("   ", r)

env.cr.rollback()
p("")
p("DONE fase2 recon — read only.")
