# -*- coding: utf-8 -*-
# Reverse JE Sewa Gudang 3jt (MISC/2026/08/0005, id 1210) — keputusan user 11 Sep 2026
# Run with RUN=1 to apply.

import os

def p(*a):
    print(*a)

RUN = os.environ.get('RUN') == '1'

env.cr.execute("SELECT id, name, state, amount_total FROM account_move WHERE id = 1210")
p("target:", env.cr.fetchone())

env.cr.execute("""
    SELECT COALESCE(SUM(l.debit-l.credit),0) FROM account_move_line l
    JOIN account_account a ON a.id=l.account_id JOIN account_move m ON m.id=l.move_id
    WHERE a.code_store->>'1'='6101.06' AND m.state='posted'
""")
p("6101.06 balance before:", env.cr.fetchone()[0])

if RUN:
    mv = env['account.move'].browse(1210)
    rev = mv._reverse_moves([
        {'journal_id': mv.journal_id.id, 'date': '2026-08-31',
         'ref': 'REVERSAL Sewa Gudang - Agustus 2026 (gudang aset sendiri, double expense; keputusan user 11 Sep)'}],
        cancel=False)
    rev.action_post()
    p("CREATED:", rev.name, rev.amount_total)

    env.cr.execute("""
        SELECT COALESCE(SUM(l.debit-l.credit),0) FROM account_move_line l
        JOIN account_account a ON a.id=l.account_id JOIN account_move m ON m.id=l.move_id
        WHERE a.code_store->>'1'='6101.06' AND m.state='posted'
    """)
    p("6101.06 balance after:", env.cr.fetchone()[0])

    env.cr.execute("""
        SELECT COALESCE(SUM(l.debit-l.credit),0) FROM account_move_line l
        JOIN account_account a ON a.id=l.account_id JOIN account_move m ON m.id=l.move_id
        WHERE a.code_store->>'1'='1101.01' AND m.state='posted'
    """)
    p("Bank BSI after:", env.cr.fetchone()[0])

    env.cr.execute("""
        SELECT COALESCE(SUM(l.debit),0)-COALESCE(SUM(l.credit),0)
        FROM account_move_line l JOIN account_move m ON m.id=l.move_id WHERE m.state='posted'
    """)
    p("trial balance diff:", env.cr.fetchone()[0])

    # P&L check
    env.cr.execute("""
        SELECT
          (SELECT COALESCE(SUM(l.credit-l.debit),0) FROM account_move_line l
             JOIN account_account a ON a.id=l.account_id JOIN account_move m ON m.id=l.move_id
             WHERE m.state='posted' AND m.date >= '2026-08-01' AND m.date <= '2026-08-31'
               AND a.account_type LIKE 'income%'),
          (SELECT COALESCE(SUM(l.debit-l.credit),0) FROM account_move_line l
             JOIN account_account a ON a.id=l.account_id JOIN account_move m ON m.id=l.move_id
             WHERE m.state='posted' AND m.date >= '2026-08-01' AND m.date <= '2026-08-31'
               AND a.account_type LIKE 'expense%')
    """)
    r, e = env.cr.fetchone()
    p(f"P&L Agustus final: rev {r:,.2f} - exp {e:,.2f} = {r-e:,.2f}")

    env.cr.commit()
    p("COMMITTED.")
else:
    p("DRY-RUN — re-run with RUN=1.")
    env.cr.rollback()
