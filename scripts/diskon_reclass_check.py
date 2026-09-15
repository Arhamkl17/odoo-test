# -*- coding: utf-8 -*-
# tmp_diskon_check.py — READ-ONLY. (1) Apa sebenarnya JE "Diskon/Retur" 4102/4103?
# (2) Simulasi markup platform +11% (net setelah komisi 10%). (3) Basis penyusutan.

def p(*a):
    print(*a)

def rows(sql, params=None):
    if params:
        env.cr.execute(sql, params)
    else:
        env.cr.execute(sql)
    return env.cr.fetchall()

p("=== 1. Saldo akun Diskon/Retur (4102/4103) Agustus ===")
for r in rows("""
    SELECT a.code_store->>'1', a.name->>'en_US', a.account_type,
           SUM(l.debit), SUM(l.credit), SUM(l.debit-l.credit)
    FROM account_move_line l JOIN account_account a ON a.id=l.account_id
    JOIN account_move m ON m.id=l.move_id
    WHERE m.state='posted' AND m.date BETWEEN '2026-08-01' AND '2026-08-31'
      AND (a.code_store->>'1' LIKE '4102%' OR a.code_store->>'1' LIKE '4103%')
    GROUP BY 1,2,3 ORDER BY 1
"""):
    p(f"   {r[0]:<10} {str(r[1])[:34]:<34} {str(r[2])[:22]:<22} dr {r[3]:>13,.2f}  cr {r[4]:>13,.2f}  net {r[5]:>13,.2f}")
env.cr.rollback()

p()
p("=== 2. JE yang menyentuh 4102/4103 (per move) ===")
for r in rows("""
    SELECT m.name, m.ref, j.code, SUM(l.debit-l.credit)
    FROM account_move_line l
    JOIN account_move m ON m.id=l.move_id
    JOIN account_journal j ON j.id=m.journal_id
    JOIN account_account a ON a.id=l.account_id
    WHERE m.state='posted' AND m.date BETWEEN '2026-08-01' AND '2026-08-31'
      AND (a.code_store->>'1' LIKE '4102%' OR a.code_store->>'1' LIKE '4103%')
    GROUP BY m.id, m.name, m.ref, j.code ORDER BY m.name
"""):
    p(f"   {str(r[0]):<20} {str(r[1])[:44]:<44} {str(r[2]):<6} {r[3]:>13,.2f}")
env.cr.rollback()

p()
p("=== 3. Simulasi markup platform +11% (komisi 10%) — per platform Agustus ===")
tot_net = 0.0
for r in rows("""
    SELECT rp.name, SUM(po.amount_total), COUNT(*)
    FROM pos_order po JOIN res_partner rp ON rp.id=po.partner_id
    WHERE po.state IN ('done','invoiced')
      AND po.date_order >= '2026-08-01' AND po.date_order < '2026-09-01'
      AND rp.name ILIKE '%Platform%'
    GROUP BY 1 ORDER BY 1
"""):
    rev, n = float(r[1]), r[2]
    mk = rev * 0.11
    kom = mk * 0.10
    tot_net += mk - kom
    p(f"   {str(r[0])[:24]:<24} rev {rev:>13,.2f}  markup+11% {mk:>12,.2f}  komisi naik {kom:>10,.2f}  net {mk-kom:>+12,.2f}")
p(f"   TOTAL net gain markup +11%: {tot_net:>+13,.2f}")
env.cr.rollback()

p()
p("=== 4. Basis penyusutan: beban per akun Agustus (bln ini) ===")
for r in rows("""
    SELECT a.code_store->>'1', a.name->>'en_US', SUM(l.debit-l.credit)
    FROM account_move_line l JOIN account_account a ON a.id=l.account_id
    JOIN account_move m ON m.id=l.move_id
    WHERE m.state='posted' AND m.date BETWEEN '2026-08-01' AND '2026-08-31'
      AND a.name->>'en_US' ILIKE '%nyusut%'
    GROUP BY 1,2 ORDER BY 1
"""):
    p(f"   {r[0]:<10} {str(r[1])[:44]:<44} {r[2]:>13,.2f}")
env.cr.rollback()

p()
p("=== 5. Aset tetap (saldo akun asset_fixed, posted) ===")
for r in rows("""
    SELECT a.code_store->>'1', a.name->>'en_US', SUM(l.debit-l.credit)
    FROM account_move_line l JOIN account_account a ON a.id=l.account_id
    JOIN account_move m ON m.id=l.move_id
    WHERE m.state='posted' AND a.account_type='asset_fixed'
    GROUP BY 1,2 HAVING SUM(l.debit-l.credit) <> 0 ORDER BY 3 DESC
"""):
    p(f"   {r[0]:<12} {str(r[1])[:44]:<44} {r[2]:>15,.2f}")
env.cr.rollback()

p()
p("DONE tmp_diskon_check — read only.")
