# -*- coding: utf-8 -*-
# Fase 4 EXECUTION — guide-perbaikan-sistem-data-1
# 1) Rename 3101.02 -> "Modal Disetor"; 5101.08 -> "Penyesuaian Stok Opname (Lebih)"
# 2) Tax "12% (Non-Luxury Good)" (id 1,2): amount 11 -> 12
# 3) Deactivate duplicate zero accounts: 12210010/12210020/12210030 (aset, 0) & 11120002 (suspense dup)
# 4) Depreciation adjustment JEs (retroaktif Agu 2026):
#    Bangunan Gudang: 1.000.000 -> 500.000/bln  (JE -500.000: D 1200.11 / K 6200.05)
#    Peralatan Kantor: 2.500.000 -> 2.000.000/bln (JE -500.000: D 1106.02 / K 6101.15)
# Run with RUN=1 to apply.

import os

def p(*a):
    print(*a)

RUN = os.environ.get('RUN') == '1'
D = '2026-08-31'
MISC = 3

def bal(code):
    env.cr.execute("""
        SELECT COALESCE(SUM(l.debit-l.credit),0) FROM account_move_line l
        JOIN account_account a ON a.id=l.account_id JOIN account_move m ON m.id=l.move_id
        WHERE a.code_store->>'1'=%s AND m.state='posted'
    """, (code,))
    return env.cr.fetchone()[0]

# ---------- 1. renames
env.cr.execute("SELECT id, code_store->>'1', name->>'en_US' FROM account_account WHERE code_store->>'1' IN ('3101.02','5101.08')")
for aid, code, name in env.cr.fetchall():
    p("1. before:", code, name)
if RUN:
    env.cr.execute("SELECT id FROM account_account WHERE code_store->>'1'='3101.02'")
    env['account.account'].browse(env.cr.fetchone()[0]).name = "Modal Disetor"
    env.cr.execute("SELECT id FROM account_account WHERE code_store->>'1'='5101.08'")
    env['account.account'].browse(env.cr.fetchone()[0]).name = "Penyesuaian Stok Opname (Lebih)"
    env.cr.execute("SELECT code_store->>'1', name->>'en_US' FROM account_account WHERE code_store->>'1' IN ('3101.02','5101.08')")
    p("   after:", env.cr.fetchall())

# ---------- 2. tax fix
env.cr.execute("SELECT id, name, amount FROM account_tax WHERE id IN (1,2)")
p("2. tax before:", env.cr.fetchall())
if RUN:
    env['account.tax'].browse([1, 2]).write({'amount': 12.0})
    env.cr.execute("SELECT id, name, amount FROM account_tax WHERE id IN (1,2)")
    p("   after:", env.cr.fetchall())

# ---------- 3. duplicate accounts
env.cr.execute("""
    SELECT a.id, a.code_store->>'1' code, a.name->>'en_US', a.active,
           COALESCE((SELECT SUM(l.debit-l.credit) FROM account_move_line l JOIN account_move m ON m.id=l.move_id
                     WHERE l.account_id=a.id AND m.state='posted'),0) bal
    FROM account_account a WHERE a.code_store->>'1' IN ('12210010','12210020','12210030','11120002','1103.08','67100010','67100020','67100030')
    ORDER BY code
""")
p("3. dup accounts:", env.cr.fetchall())
if RUN:
    env.cr.execute("SELECT id FROM account_account WHERE code_store->>'1' IN ('12210010','12210020','12210030','11120002')")
    ids = [r[0] for r in env.cr.fetchall()]
    env['account.account'].browse(ids).active = False
    p("   deactivated:", ids)

# ---------- 4. depreciation adjustments
env.cr.execute("SELECT id, code_store->>'1' FROM account_account WHERE code_store->>'1' IN ('1200.11','6200.05','1106.02','6101.15')")
AD = {code: aid for aid, code in env.cr.fetchall()}
p("4. dep accounts:", AD)
p("   bal before: 1200.11", f"{bal('1200.11'):,.2f}", "| 6200.05", f"{bal('6200.05'):,.2f}",
  "| 1106.02", f"{bal('1106.02'):,.2f}", "| 6101.15", f"{bal('6101.15'):,.2f}")

# monthly dep = original JE amounts posted in August:
# Bangunan Gudang 1.000.000 (target 500.000) -> adjust -500.000
# Peralatan Kantor 2.500.000 (target 2.000.000) -> adjust -500.000
ADJ = [
    # (debit_acc, credit_acc, amount, label)
    ('1200.11', '6200.05', -500000.0, 'Koreksi penyusutan Bangunan Gudang Agu 2026: 10%/th -> 5%/th (1jt -> 500rb)'),
    ('1106.02', '6101.15', -500000.0, 'Koreksi penyusutan Peralatan Kantor Agu 2026: 25%/th -> 20%/th (2,5jt -> 2jt)'),
]
if RUN:
    lines = []
    for dacc, cacc, amt, label in ADJ:
        # amt negative = reduce expense & reduce accumulated dep
        lines.append((0, 0, {'account_id': AD[dacc], 'debit': -amt if amt < 0 else amt,
                             'credit': amt if amt > 0 else 0.0, 'name': label}))
        lines.append((0, 0, {'account_id': AD[cacc], 'debit': 0.0,
                             'credit': -amt if amt < 0 else amt, 'name': label}))
    mv = env['account.move'].create({
        'journal_id': MISC, 'date': D, 'move_type': 'entry',
        'ref': 'Koreksi beban penyusutan Agustus 2026 - umur aset: Bangunan Gudang 20th (5%/th), Peralatan Kantor 5-8th (20%/th)',
        'line_ids': lines,
    })
    mv.action_post()
    p("   CREATED:", mv.name, "| total adj: -1.000.000,00 (beban bulanan)")
    p("   bal after: 1200.11", f"{bal('1200.11'):,.2f}", "| 6200.05", f"{bal('6200.05'):,.2f}",
      "| 1106.02", f"{bal('1106.02'):,.2f}", "| 6101.15", f"{bal('6101.15'):,.2f}")

env.cr.execute("SELECT COALESCE(SUM(l.debit),0)-COALESCE(SUM(l.credit),0) FROM account_move_line l JOIN account_move m ON m.id=l.move_id WHERE m.state='posted'")
p("")
p("trial balance diff:", env.cr.fetchone()[0])

if RUN:
    env.cr.commit()
    p("COMMITTED (Fase 4).")
else:
    env.cr.rollback()
    p("DRY-RUN ONLY — rolled back. Re-run with RUN=1.")
