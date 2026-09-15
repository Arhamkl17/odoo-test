# -*- coding: utf-8 -*-
# Fase 2 recon part 2 (READ-ONLY) — references to accounts 4, 5, 117

def p(*a):
    print(*a)

p("1. account_journal columns containing 'account':")
env.cr.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name='account_journal' AND column_name ILIKE '%account%'
""")
jcols = [r[0] for r in env.cr.fetchall()]
p("   ", jcols)

p("")
p("2. Journals referencing 4/5/117:")
conds = " OR ".join([f"{c} IN (4,5,117)" for c in jcols if c.endswith('_id')])
env.cr.execute(f"""
    SELECT id, code, name->>'en_US', {', '.join([c for c in jcols if c.endswith('_id')])}
    FROM account_journal WHERE {conds}
""")
p("   columns: id, code, name, then FK columns")
for r in env.cr.fetchall():
    p("   ", r)

p("")
p("3. pos_payment_method columns + refs:")
env.cr.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name='pos_payment_method' AND column_name ILIKE '%account%'
""")
pcols = [r[0] for r in env.cr.fetchall()]
p("   ", pcols)
conds = " OR ".join([f"{c} IN (4,5,117)" for c in pcols if c.endswith('_id')])
if conds:
    env.cr.execute(f"SELECT id, name->>'en_US', {', '.join([c for c in pcols if c.endswith('_id')])} FROM pos_payment_method WHERE {conds}")
    for r in env.cr.fetchall():
        p("   ", r)

p("")
p("4. res_partner property columns (v19 company-dependent stored on model):")
env.cr.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name='res_partner' AND (column_name ILIKE '%receivable%' OR column_name ILIKE '%payable%' OR column_name ILIKE '%account%')
""")
prcols = [r[0] for r in env.cr.fetchall()]
p("   ", prcols)
for c in prcols:
    if c.endswith('_id'):
        env.cr.execute(f"""
            SELECT rp.id, rp.name FROM res_partner rp
            WHERE (rp.{c}->>'1')::int IN (4,5,117)
        """)
        rows = env.cr.fetchall()
        if rows:
            p(f"   {c}:", rows[:10])

p("")
p("5. res_company columns referencing accounts:")
env.cr.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name='res_company' AND column_name ILIKE '%account%'
""")
ccols = [r[0] for r in env.cr.fetchall()]
for c in ccols:
    if c.endswith('_id'):
        try:
            env.cr.execute(f"SELECT id FROM res_company WHERE {c} IN (4,5,117)")
            rows = env.cr.fetchall()
            if rows:
                p(f"   res_company.{c}:", rows)
        except Exception:
            env.cr.rollback()

p("")
p("6. Other tables with FK-ish columns to account 4/5/117 (scan likely config tables):")
for tn in ['pos_config','pos_session','account_fiscal_position_account_tax','res_config_settings','account_chart_template','account_payment_method','account_reconcile_model','account_reconcile_model_line']:
    try:
        env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name=%s AND column_name ILIKE '%%account%%'
        """, (tn,))
        cols = [r[0] for r in env.cr.fetchall()]
        for c in cols:
            if c.endswith('_id'):
                env.cr.execute(f'SELECT COUNT(*) FROM "{tn}" WHERE "{c}" IN (4,5,117)')
                n = env.cr.fetchone()[0]
                if n:
                    p(f"   {tn}.{c}: {n} rows!")
    except Exception:
        env.cr.rollback()

p("")
p("7. Account 117 & 4 reconcile flags + account 123 state:")
env.cr.execute("""
    SELECT id, code_store->>'1', name->>'en_US', account_type, reconcile, active
    FROM account_account WHERE id IN (4, 5, 117, 123)
""")
for r in env.cr.fetchall():
    p("   ", r)

p("")
p("8. Account 123 (1102.01) posted lines:")
env.cr.execute("""
    SELECT l.id, l.move_id, m.name, m.state, l.debit, l.credit, l.reconciled
    FROM account_move_line l JOIN account_move m ON m.id = l.move_id
    WHERE l.account_id = 123 AND m.state='posted'
""")
for r in env.cr.fetchall():
    p("   ", r)

p("")
p("9. INV/00003 (1294) current state + aml:")
env.cr.execute("""
    SELECT l.id, l.account_id, a.code_store->>'1', l.debit, l.credit, l.reconciled
    FROM account_move_line l JOIN account_account a ON a.id=l.account_id
    WHERE l.move_id = 1294
""")
for r in env.cr.fetchall():
    p("   ", r)

env.cr.rollback()
p("")
p("DONE fase2 recon part 2.")
