# -*- coding: utf-8 -*-
# tmp_diskon_counter.py — READ-ONLY. Lihat komposisi lengkap lines MISC/2026/08/0022
# (Diskon Dine In) utk tahu kredit counter-nya ke mana -> menentukan apakah diskon
# mengurangi laba atau hanya reclass presentasi.

def p(*a):
    print(*a)

def rows(sql, params=None):
    if params:
        env.cr.execute(sql, params)
    else:
        env.cr.execute(sql)
    return env.cr.fetchall()

p("=== Lines lengkap MISC/2026/08/0022 (Diskon Dine In) ===")
for r in rows("""
    SELECT a.code_store->>'1', a.name->>'en_US', a.account_type, l.debit, l.credit, l.name
    FROM account_move_line l
    JOIN account_account a ON a.id=l.account_id
    JOIN account_move m ON m.id=l.move_id
    WHERE m.name='MISC/2026/08/0022'
    ORDER BY l.id
"""):
    p(f"   {str(r[0]):<10} {str(r[1])[:34]:<34} {str(r[2])[:16]:<16} dr {r[3]:>13,.2f}  cr {r[4]:>13,.2f}  | {str(r[5])[:40]}")
env.cr.rollback()

p()
p("=== Lines lengkap MISC/2026/08/0027 (Retur ShopeeFood) ===")
for r in rows("""
    SELECT a.code_store->>'1', a.name->>'en_US', a.account_type, l.debit, l.credit
    FROM account_move_line l
    JOIN account_account a ON a.id=l.account_id
    JOIN account_move m ON m.id=l.move_id
    WHERE m.name='MISC/2026/08/0027'
    ORDER BY l.id
"""):
    p(f"   {str(r[0]):<10} {str(r[1])[:34]:<34} {str(r[2])[:16]:<16} dr {r[3]:>13,.2f}  cr {r[4]:>13,.2f}")
env.cr.rollback()

p()
p("=== Total debit 4101.xx (pendapatan) Agustus — siapa yang mendebit pendapatan? ===")
for r in rows("""
    SELECT a.code_store->>'1', a.name->>'en_US', SUM(l.debit), SUM(l.credit)
    FROM account_move_line l
    JOIN account_account a ON a.id=l.account_id
    JOIN account_move m ON m.id=l.move_id
    WHERE m.state='posted' AND m.date BETWEEN '2026-08-01' AND '2026-08-31'
      AND a.code_store->>'1' LIKE '4101%'
    GROUP BY 1,2 HAVING SUM(l.debit) > 0 ORDER BY 3 DESC
"""):
    p(f"   {r[0]:<10} {str(r[1])[:36]:<36} dr {r[2]:>13,.2f}  cr {r[3]:>15,.2f}")
env.cr.rollback()

p()
p("DONE tmp_diskon_counter — read only.")
