# -*- coding: utf-8 -*-
# Fase 2 EXECUTION — guide-perbaikan-sistem-data-1
# 1) Reconcile account 117 (11120003): debits 4311+4315 vs credit 4322 (net 0)
# 2) Cancel INV/2026/00003 (id 1294) — the only open AR
# 3) Deactivate account 4 (11210010, fully reconciled, no config refs) and
#    account 117 (after reconcile). KEEP account 5 (11210011) — it is the live
#    company default POS receivable. KEEP account 123 (1102.01) — canonical AR.
# Run with RUN=1 to apply.

import os

def p(*a):
    print(*a)

RUN = os.environ.get('RUN') == '1'

# ---------- 1. reconcile account 117
lines117 = env['account.move.line'].browse([4311, 4315, 4322])
p("1. account 117 lines before:", [(l.id, l.balance, l.reconciled) for l in lines117])
bal = sum(lines117.mapped('balance'))
p("   net balance:", bal)
if RUN and abs(bal) < 0.01:
    lines117.reconcile()
    env.cr.execute("SELECT id, reconciled FROM account_move_line WHERE id IN (4311,4315,4322)")
    p("   AFTER reconcile:", env.cr.fetchall())
else:
    p("   (skip reconcile — dry-run or unbalanced)")

# ---------- 2. cancel INV/00003
inv = env['account.move'].browse(1294)
p("")
p("2. INV/00003 state:", inv.name, inv.state, inv.amount_total, "| payment_state:", inv.payment_state)
if RUN:
    inv.button_cancel() if hasattr(inv, 'button_cancel') else inv.action_cancel()
    p("   AFTER cancel:", inv.state)
    # reset-to-draft not needed; cancelled invoice keeps history. Revenue effect:
    # credit 4101.02 no longer counts as posted income.

# ---------- 3. deactivate accounts 4 and 117
p("")
if RUN:
    for aid in (4, 117):
        acc = env['account.account'].browse(aid)
        # safety: confirm zero balance now
        env.cr.execute("""
            SELECT COALESCE(SUM(l.debit-l.credit),0) FROM account_move_line l
            JOIN account_move m ON m.id = l.move_id
            WHERE l.account_id = %s AND m.state='posted'
        """, (aid,))
        b = env.cr.fetchone()[0]
        p(f"3. account {aid} ({acc.name}) balance before deactivate: {b}")
        if abs(b) < 0.01:
            acc.active = False
            p(f"   account {aid} deactivated")
        else:
            p(f"   SKIP deactivation — balance not zero!")

# ---------- 4. verify
p("")
p("4. VERIFY:")
env.cr.execute("""
    SELECT a.code_store->>'1' code, a.name->>'en_US' name, a.active,
           COALESCE(SUM(CASE WHEN m.state='posted' THEN l.debit-l.credit ELSE 0 END),0) posted_bal
    FROM account_account a
    LEFT JOIN account_move_line l ON l.account_id = a.id
    LEFT JOIN account_move m ON m.id = l.move_id
    WHERE a.id IN (4, 5, 117, 123)
    GROUP BY a.code_store->>'1', a.name->>'en_US', a.active
    ORDER BY code
""")
p("   accounts state:", env.cr.fetchall())

env.cr.execute("""
    SELECT l.id, m.name, l.debit, l.credit, l.reconciled
    FROM account_move_line l
    JOIN account_move m ON m.id = l.move_id
    JOIN account_account a ON a.id = l.account_id
    WHERE a.account_type = 'asset_receivable' AND m.state = 'posted'
      AND l.reconciled = False
""")
open_lines = env.cr.fetchall()
p("   open (unreconciled) receivable lines:", open_lines if open_lines else "NONE ✓")

env.cr.execute("""
    SELECT COALESCE(SUM(l.debit-l.credit),0)
    FROM account_move_line l
    JOIN account_move m ON m.id = l.move_id
    JOIN account_account a ON a.id = l.account_id
    WHERE a.account_type = 'asset_receivable' AND m.state = 'posted'
""")
p("   total AR balance (posted):", env.cr.fetchone()[0])

env.cr.execute("SELECT SUM(debit)-SUM(credit) FROM account_move_line l JOIN account_move m ON m.id=l.move_id WHERE m.state='posted'")
p("   trial balance diff:", env.cr.fetchone()[0])

if RUN:
    env.cr.commit()
    p("")
    p("COMMITTED (Fase 2).")
else:
    env.cr.rollback()
    p("")
    p("DRY-RUN ONLY — rolled back. Re-run with RUN=1.")
