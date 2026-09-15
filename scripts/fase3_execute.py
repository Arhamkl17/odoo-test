# -*- coding: utf-8 -*-
# Fase 3 EXECUTION — guide-perbaikan-sistem-data-1
# A) cancel komisi 15% (1305-1307)  B) post komisi 10% x3 -> kredit BSI
# C) transfer saldo e-wallet (1101.03/04/05) -> BSI  D) transfer bank lama (1101.06-09) -> BSI
# E) deaktivasi akun e-wallet & bank lama  F) rename Bontoala -> Mallengkeri
# G) reclass pos.payment: PM 11,12 -> 10 (QRIS); PM 14-17 -> 2 (Kartu/BSI)
# H) PM 13 jurnal -> BNK1; deaktivasi PM 11,12,14,15,16,17 + jurnal OVOW/GPYW/SPPW/BCA/BNI/BRI/BMR
# Run with RUN=1 to apply.

import os
from odoo.tools import float_round

def p(*a):
    print(*a)

RUN = os.environ.get('RUN') == '1'
D = '2026-08-31'

def bal(code):
    env.cr.execute("""
        SELECT COALESCE(SUM(l.debit-l.credit),0) FROM account_move_line l
        JOIN account_account a ON a.id = l.account_id
        JOIN account_move m ON m.id = l.move_id
        WHERE a.code_store->>'1' = %s AND m.state='posted'
    """, (code,))
    return env.cr.fetchone()[0]

env.cr.execute("""
    SELECT id, code_store->>'1' FROM account_account
    WHERE code_store->>'1' IN ('1101.01','1101.02','1101.03','1101.04','1101.05',
                               '1101.06','1101.07','1101.08','1101.09',
                               '1111001','1112001','6300.01')
""")
A = {code: aid for aid, code in env.cr.fetchall()}
p("accounts:", A)

MISC, BNK1 = 3, 6

# ---------- A. reverse 15% komisi JEs (MISC journal is hash-secured -> cancel blocked;
# accounting-correct alternative: reversal JEs, keeping audit trail + hash chain)
p("")
p("A. reverse komisi 15% via JE reversal:")
old = env['account.move'].browse([1305, 1306, 1307])
for m in old:
    p("   ", m.name, m.state, m.amount_total, "|", m.ref)
if RUN:
    total_rev = 0.0
    for m in old:
        rev = m._reverse_moves([
            {'journal_id': MISC, 'date': D,
             'ref': f'REVERSAL {m.ref} - konversi komisi 15% ke 10% (Fase 3)'}],
            cancel=False)
        rev.action_post()
        total_rev += rev.amount_total
        p(f"   CREATED {rev.name}: reversal of {m.name} = {rev.amount_total:,.2f}")
    p("   total reversed:", f"{total_rev:,.2f}")

# ---------- B. komisi 10% JEs
p("")
p("B. platform omzet (basis komisi):")
env.cr.execute("""
    SELECT po.partner_id, rp.name, SUM(po.amount_total) total
    FROM pos_order po JOIN res_partner rp ON rp.id = po.partner_id
    WHERE po.state IN ('done','invoiced')
      AND po.date_order AT TIME ZONE 'UTC' >= '2026-08-01'
      AND po.date_order AT TIME ZONE 'UTC' < '2026-09-01'
      AND rp.name ILIKE '%Platform%'
    GROUP BY po.partner_id, rp.name ORDER BY rp.name
""")
plat = env.cr.fetchall()
for r in plat:
    p("   ", r)

if RUN:
    for pid, pname, total in plat:
        amt = round(total * 0.10, 2)
        move = env['account.move'].create({
            'journal_id': MISC,
            'date': D,
            'ref': f'Komisi Platform {pname} - Agustus 2026 (revisi 10%, final)',
            'move_type': 'entry',
            'line_ids': [
                (0, 0, {'account_id': A['6300.01'], 'debit': amt, 'credit': 0.0,
                        'name': f'Beban komisi {pname} 10% x omzet {total:,.2f}'}),
                (0, 0, {'account_id': A['1101.01'], 'debit': 0.0, 'credit': amt,
                        'name': f'Net payout delivery {pname} via Bank BSI'}),
            ],
        })
        move.action_post()
        p(f"   CREATED {move.name}: {pname} komisi 10% = {amt:,.2f}")

# ---------- C. e-wallet -> BSI
p("")
p("C. e-wallet balances after cancel:")
wallets = {}
for code, label in [('1101.03', 'OVO'), ('1101.04', 'GOPAY'), ('1101.05', 'SHOPEE PAY')]:
    b = round(bal(code), 2)
    wallets[code] = b
    p(f"   {code} {label}: {b:,.2f}")
if RUN:
    lines = [(0, 0, {'account_id': A['1101.01'], 'debit': round(sum(wallets.values()), 2), 'credit': 0.0,
                     'name': 'Settlement e-wallet ke Bank BSI - Agustus 2026 (OVO+GOPAY+ShopeePay)'})]
    for code in wallets:
        lines.append((0, 0, {'account_id': A[code], 'debit': 0.0, 'credit': wallets[code],
                             'name': f'Clearing saldo {code} ke BSI (Fase 3)'}))
    mv = env['account.move'].create({'journal_id': MISC, 'date': D, 'move_type': 'entry',
        'ref': 'Settlement e-wallet (OVO/GOPAY/ShopeePay) ke Bank BSI - Agustus 2026',
        'line_ids': lines})
    mv.action_post()
    p("   CREATED:", mv.name, "| total:", f"{sum(wallets.values()):,.2f}")

# ---------- D. bank lama -> BSI
p("")
p("D. old bank balances:")
banks = {}
for code, label in [('1101.06', 'BCA'), ('1101.07', 'BNI'), ('1101.08', 'BRI'), ('1101.09', 'Mandiri')]:
    b = round(bal(code), 2)
    banks[code] = b
    p(f"   {code} {label}: {b:,.2f}")
if RUN:
    lines = [(0, 0, {'account_id': A['1101.01'], 'debit': round(sum(banks.values()), 2), 'credit': 0.0,
                     'name': 'Konsolidasi bank lama ke Bank BSI - Agustus 2026'})]
    for code in banks:
        lines.append((0, 0, {'account_id': A[code], 'debit': 0.0, 'credit': banks[code],
                             'name': f'Clearing saldo {code} ke BSI (Fase 3)'}))
    mv = env['account.move'].create({'journal_id': MISC, 'date': D, 'move_type': 'entry',
        'ref': 'Konsolidasi bank BCA/BNI/BRI/Mandiri ke Bank BSI - Agustus 2026',
        'line_ids': lines})
    mv.action_post()
    p("   CREATED:", mv.name, "| total:", f"{sum(banks.values()):,.2f}")

# ---------- E. deactivate zeroed accounts
p("")
if RUN:
    for code in list(wallets) + list(banks):
        b = round(bal(code), 2)
        acc = env['account.account'].browse(A[code])
        if abs(b) < 0.01:
            acc.active = False
            p(f"E. {code} {acc.name} deactivated")
        else:
            p(f"E. SKIP {code} — balance {b}")

# ---------- F. rename Bontoala -> Mallengkeri
if RUN:
    env['account.account'].browse(A['1111001']).name = "Kas Mallengkeri"
    env['account.account'].browse(A['1112001']).name = "Bank Mallengkeri"
    p("F. renamed 1111001 -> Kas Mallengkeri, 1112001 -> Bank Mallengkeri")
else:
    p("F. (dry-run) would rename 1111001/1112001")

# ---------- G. pos.payment reclass
env.cr.execute("SELECT payment_method_id, COUNT(*), SUM(amount) FROM pos_payment GROUP BY payment_method_id ORDER BY 1")
p("")
p("G. pos.payment before:", env.cr.fetchall())
if RUN:
    env.cr.execute("UPDATE pos_payment SET payment_method_id = 10 WHERE payment_method_id IN (11, 12)")
    p("   reclassed OVO/GOPAY rows -> QRIS:", env.cr.rowcount)
    env.cr.execute("UPDATE pos_payment SET payment_method_id = 2 WHERE payment_method_id IN (14, 15, 16, 17)")
    p("   reclassed BCA/BNI/BRI/Mandiri rows -> Kartu:", env.cr.rowcount)
    env.cr.execute("SELECT payment_method_id, COUNT(*), SUM(amount) FROM pos_payment GROUP BY payment_method_id ORDER BY 1")
    p("   pos.payment after:", env.cr.fetchall())

# ---------- H. PM 13 journal -> BNK1, deactivate unused PMs & journals
if RUN:
    env['pos.payment.method'].browse(13).journal_id = BNK1
    p("H. PM 13 (ShopeeFood) journal -> BNK1")
    for pmid in (11, 12, 14, 15, 16, 17):
        env['pos.payment.method'].browse(pmid).active = False
    p("   PMs 11,12,14,15,16,17 deactivated")
    for jid in (18, 19, 20, 21, 22, 23, 24):
        env['account.journal'].browse(jid).active = False
    p("   journals OVOW/GPYW/SPPW/BCA/BNI/BRI/BMR deactivated")

# ---------- I. verify
p("")
p("I. VERIFY:")
env.cr.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM pos_payment")
p("   total pos.payment rows & amount (harus 4.515-ish / 232.683.763):", env.cr.fetchone())
for code, label in [('1101.01', 'BSI'), ('1101.02', 'QRIS'), ('1101.03', 'OVO'), ('1101.04', 'GOPAY'),
                    ('1101.05', 'SPPAY'), ('1101.06', 'BCA'), ('1101.07', 'BNI'), ('1101.08', 'BRI'),
                    ('1101.09', 'Mandiri'), ('1111001', 'Kas Mallengkeri'), ('1112001', 'Bank Mallengkeri')]:
    p(f"   {code} {label}: {bal(code):,.2f}")
env.cr.execute("""
    SELECT COALESCE(SUM(l.debit),0)-COALESCE(SUM(l.credit),0)
    FROM account_move_line l JOIN account_move m ON m.id = l.move_id WHERE m.state='posted'
""")
p("   trial balance diff:", env.cr.fetchone()[0])
env.cr.execute("SELECT COALESCE(SUM(debit-credit),0) FROM account_move_line l JOIN account_account a ON a.id=l.account_id JOIN account_move m ON m.id=l.move_id WHERE a.code_store->>'1'='6300.01' AND m.state='posted'")
p("   total beban komisi posted:", env.cr.fetchone()[0])

if RUN:
    env.cr.commit()
    p("")
    p("COMMITTED (Fase 3).")
else:
    env.cr.rollback()
    p("")
    p("DRY-RUN ONLY — rolled back. Re-run with RUN=1.")
