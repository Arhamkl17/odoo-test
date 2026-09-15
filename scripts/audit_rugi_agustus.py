# -*- coding: utf-8 -*-
# Audit: kenapa Agustus 2026 masih rugi -7.755.232,15 (read-only)

def p(*a):
    print(*a)

D1, D2 = '2026-08-01', '2026-08-31'

def rows(sql, params=()):
    env.cr.execute(sql, params)
    return env.cr.fetchall()

p("=" * 78)
p("1. P&L AGUSTUS 2026 PER AKUN (posted, urut nominal)")
p("=" * 78)
p("--- REVENUE ---")
rev_rows = rows("""
    SELECT a.code_store->>'1' code, a.name->>'en_US' aname, a.account_type,
           SUM(l.credit - l.debit) amt
    FROM account_move_line l
    JOIN account_account a ON a.id = l.account_id
    JOIN account_move m ON m.id = l.move_id
    WHERE m.state='posted' AND m.date >= %s AND m.date <= %s
      AND a.account_type LIKE 'income%%' AND (l.credit - l.debit) > 0
    GROUP BY code, aname, a.account_type ORDER BY amt DESC
""", (D1, D2))
tot_rev = 0
for r in rev_rows:
    p(f"   {r[0]:<10} {r[1]:<38} {r[3]:>15,.2f}")
    tot_rev += r[3]
p(f"   {'TOTAL':<49} {tot_rev:>15,.2f}")

p("--- EXPENSE ---")
exp_rows = rows("""
    SELECT a.code_store->>'1' code, a.name->>'en_US' aname, a.account_type,
           SUM(l.debit - l.credit) amt
    FROM account_move_line l
    JOIN account_account a ON a.id = l.account_id
    JOIN account_move m ON m.id = l.move_id
    WHERE m.state='posted' AND m.date >= %s AND m.date <= %s
      AND a.account_type LIKE 'expense%%' AND (l.debit - l.credit) > 0
    GROUP BY code, aname, a.account_type ORDER BY amt DESC
""", (D1, D2))
tot_exp = 0
for r in exp_rows:
    p(f"   {r[0]:<10} {r[1]:<38} {r[3]:>15,.2f}")
    tot_exp += r[3]
p(f"   {'TOTAL':<49} {tot_exp:>15,.2f}")

p("--- EXPENSE dengan SALDO KREDIT (income-like, memperbaiki rugi) ---")
neg_rows = rows("""
    SELECT a.code_store->>'1' code, a.name->>'en_US' aname, SUM(l.credit - l.debit) amt
    FROM account_move_line l
    JOIN account_account a ON a.id = l.account_id
    JOIN account_move m ON m.id = l.move_id
    WHERE m.state='posted' AND m.date >= %s AND m.date <= %s
      AND a.account_type LIKE 'expense%%' AND (l.credit - l.debit) > 0
    GROUP BY code, aname ORDER BY amt DESC
""", (D1, D2))
for r in neg_rows:
    p(f"   {r[0]:<10} {r[1]:<38} {r[2]:>15,.2f}")

p("")
p(f"NET (rev - exp, belum termasuk kredit-offset): {tot_rev - tot_exp:,.2f}")

p("")
p("=" * 78)
p("2. RASIO TERHADAP PENDAPATAN")
p("=" * 78)
def acc_bal(code):
    r = rows("""
        SELECT COALESCE(SUM(l.debit-l.credit),0) FROM account_move_line l
        JOIN account_account a ON a.id=l.account_id JOIN account_move m ON m.id=l.move_id
        WHERE a.code_store->>'1'=%s AND m.state='posted' AND m.date >= %s AND m.date <= %s
    """, (code, D1, D2))
    return r[0][0]

hpp_total = sum(acc_bal(c) for c in ('5101.01','5101.02','5101.03','5101.04'))
items = [
    ('HPP semua (5101.0x)', hpp_total),
    ('Gaji (6101.03+04+05?)', acc_bal('6101.03') + acc_bal('6101.04') + acc_bal('6101.05')),
    ('Komisi (6300.01)', acc_bal('6300.01')),
    ('Penyusutan (6101.14-17+6200.05-07)', sum(acc_bal(c) for c in ('6101.14','6101.15','6101.16','6101.17','6200.05','6200.06','6200.07'))),
]
for label, v in items:
    p(f"   {label:<40} {v:>15,.2f}  ({v/tot_rev*100:>5.1f}%)")
sewa = rows("""
    SELECT a.code_store->>'1', a.name->>'en_US', SUM(l.debit-l.credit)
    FROM account_move_line l JOIN account_account a ON a.id=l.account_id
    JOIN account_move m ON m.id=l.move_id
    WHERE m.state='posted' AND m.date >= %s AND m.date <= %s
      AND a.name->>'en_US' ILIKE '%%sewa%%' AND a.account_type LIKE 'expense%%'
    GROUP BY 1,2
""", (D1, D2))
for r in sewa:
    p(f"   Sewa: {r[0]:<8} {r[1]:<30} {r[2]:>15,.2f}  ({r[2]/tot_rev*100:>5.1f}%)")

p("")
p("=" * 78)
p("3. CEK DOUBLE-COUNT #1: Sewa prepaid vs beban sewa")
p("=" * 78)
for code in ('1104.01','1104.02','1104.03'):
    p(f"   prepaid {code}: {acc_bal(code):,.2f}")
p("   JE yang menyentuh akun beban sewa:")
sewa_accs = rows("""
    SELECT DISTINCT a.code_store->>'1' FROM account_account a WHERE a.name->>'en_US' ILIKE '%%sewa%%'
""")
codes = [r[0] for r in sewa_accs]
p("   semua akun sewa:", codes)
mv = rows("""
    SELECT DISTINCT m.id, m.name, m.date, m.ref, m.amount_total, m.state
    FROM account_move m JOIN account_move_line l ON l.move_id=m.id
    JOIN account_account a ON a.id=l.account_id
    WHERE a.code_store->>'1' IN %s AND m.date >= %s AND m.date <= %s AND m.state='posted'
    ORDER BY m.id
""", (tuple(codes), D1, D2))
for r in mv:
    p("   ", r)

p("")
p("=" * 78)
p("4. CEK DOUBLE-COUNT #2: HPP Gas 1,8jt manual vs pembelian gas di TAGIH")
p("=" * 78)
p("   produk gas:")
gas_prod = rows("""
    SELECT pt.id, pt.name->>'en_US', pp.standard_price->>'1'
    FROM product_template pt JOIN product_product pp ON pp.product_tmpl_id=pt.id
    WHERE pt.name->>'en_US' ILIKE '%%gas%%' AND pt.name->>'en_US' NOT ILIKE '%%portable%%'
""")
for r in gas_prod:
    p("   ", r)
gas_moves = rows("""
    SELECT sm.id, sm.date, sm.product_uom_qty, sm.value, ls.usage, ld.usage
    FROM stock_move sm
    JOIN product_product pp ON pp.id=sm.product_id
    JOIN product_template pt ON pt.id=pp.product_tmpl_id
    JOIN stock_location ls ON ls.id=sm.location_id
    JOIN stock_location ld ON ld.id=sm.location_dest_id
    WHERE pt.name->>'en_US' ILIKE '%%gas%%' AND sm.date >= %s AND sm.date < %s
""", (D1, '2026-09-01'))
p("   gas stock moves Aug:", gas_moves if gas_moves else "NONE")
p("   TAGIH bills menyebut gas:")
gas_bills = rows("""
    SELECT m.id, m.name, m.amount_total FROM account_move m
    WHERE m.ref ILIKE '%%gas%%' AND m.date >= %s AND m.date <= %s AND m.state='posted'
""", (D1, D2))
for r in gas_bills:
    p("   ", r)
gas_je = rows("""
    SELECT m.id, m.name, m.ref, m.amount_total FROM account_move m
    JOIN account_move_line l ON l.move_id=m.id JOIN account_account a ON a.id=l.account_id
    WHERE a.code_store->>'1'='5101.03' AND m.state='posted'
""")
p("   JE ke 5101.03 HPP Gas:", gas_je)

p("")
p("=" * 78)
p("5. CEK #3: Konsumsi Pendukung 4,91jt & Bev 121,8% (BOM quirks)")
p("=" * 78)
p("   top konsumsi Pendukung (categ 7) Agustus:")
top7 = rows("""
    SELECT pt.name->>'en_US', SUM(sm.product_uom_qty) qty, SUM(sm.value) val
    FROM stock_move sm
    JOIN product_product pp ON pp.id=sm.product_id
    JOIN product_template pt ON pt.id=pp.product_tmpl_id
    JOIN stock_location ls ON ls.id=sm.location_id
    JOIN stock_location ld ON ld.id=sm.location_dest_id
    WHERE pt.categ_id=7 AND ls.usage='internal' AND ld.usage='customer'
      AND sm.state='done' AND sm.date >= %s AND sm.date < %s
    GROUP BY 1 ORDER BY val DESC LIMIT 12
""", (D1, '2026-09-01'))
for r in top7:
    p(f"   {r[0]:<30} qty {r[1]:>12,.1f}  val {r[2]:>13,.2f}")
p("   beverage components consumption vs bev revenue:")
bev = rows("""
    SELECT pt.name->>'en_US', SUM(sm.value) val
    FROM stock_move sm
    JOIN product_product pp ON pp.id=sm.product_id
    JOIN product_template pt ON pt.id=pp.product_tmpl_id
    JOIN stock_location ls ON ls.id=sm.location_id
    JOIN stock_location ld ON ld.id=sm.location_dest_id
    WHERE pt.categ_id=5 AND ls.usage='internal' AND ld.usage='customer'
      AND sm.state='done' AND sm.date >= %s AND sm.date < %s
    GROUP BY 1 ORDER BY val DESC LIMIT 10
""", (D1, '2026-09-01'))
for r in bev:
    p(f"   {r[0]:<30} {r[1]:>13,.2f}")

p("")
p("=" * 78)
p("6. CEK #4: Revenue completeness — POS vs posted income")
p("=" * 78)
p(f"   POS collect (amount_total):        232.683.763,00")
inv_rev = rows("""
    SELECT m.name, m.state, m.amount_total FROM account_move m
    WHERE m.move_type='out_invoice' AND m.state='posted' AND m.date >= %s AND m.date <= %s
""", (D1, D2))
p("   invoice posted Agustus:", inv_rev)
p(f"   posted income total:               {tot_rev:,.2f}")
other_inc = tot_rev - 232683763.0 - sum(r[2] for r in inv_rev)
p(f"   sisa income lain (7101.xx dsb):    {other_inc:,.2f}")
p("   JE POSS session-close revenue lines by account:")
pos_rev = rows("""
    SELECT a.code_store->>'1', a.name->>'en_US', SUM(l.credit-l.debit), COUNT(DISTINCT m.id)
    FROM account_move_line l JOIN account_account a ON a.id=l.account_id
    JOIN account_move m ON m.id=l.move_id
    JOIN account_journal j ON j.id=m.journal_id
    WHERE j.code='POSS' AND m.state='posted' AND m.date >= %s AND m.date <= %s
      AND a.account_type LIKE 'income%%'
    GROUP BY 1,2
""", (D1, D2))
for r in pos_rev:
    p("   ", r)

p("")
p("=" * 78)
p("7. CEK #5: One-off & akun aneh di Agustus")
p("=" * 78)
for code, label in [('5101.08','Penyesuaian Stok Opname (Lebih)'), ('42500010','Change in Inventory'),
                    ('7101.02','Penjualan Persediaan'), ('1103.09','Opening Inventory Balance')]:
    p(f"   {code} {label}: {acc_bal(code):,.2f}")
p("   JE ke 5101.08:")
p(rows("""
    SELECT m.name, m.ref, l.debit, l.credit FROM account_move_line l
    JOIN account_move m ON m.id=l.move_id JOIN account_account a ON a.id=l.account_id
    WHERE a.code_store->>'1'='5101.08' AND m.state='posted'
"""))

p("")
p("8. OPEX lain (top 15 di luar HPP/gaji/komisi/dep/sewa):")
known = ('5101.01','5101.02','5101.03','5101.04','6101.03','6101.04','6101.05','6300.01',
         '6101.14','6101.15','6101.16','6101.17','6200.05','6200.06','6200.07')
others = rows("""
    SELECT a.code_store->>'1' code, a.name->>'en_US' aname, SUM(l.debit-l.credit) amt
    FROM account_move_line l
    JOIN account_account a ON a.id=l.account_id JOIN account_move m ON m.id=l.move_id
    WHERE m.state='posted' AND m.date >= %s AND m.date <= %s
      AND a.account_type LIKE 'expense%%' AND a.code_store->>'1' NOT IN %s
    GROUP BY 1,2 HAVING SUM(l.debit-l.credit) > 100000 ORDER BY amt DESC LIMIT 15
""", (D1, D2, tuple(known)))
for r in others:
    p(f"   {r[0]:<10} {r[1]:<38} {r[2]:>15,.2f}")

env.cr.rollback()
p("")
p("DONE audit rugi — read only.")
