# -*- coding: utf-8 -*-
# tmp_profit_levers_recon.py — READ-ONLY. Data basis utk skenario profit >=8%.
# A. Gaji: akun 6101.03/04/05 + label JE + hr.employee/contract (kalau ada)
# B. Diskon POS Agustus (per channel walk-in vs platform)
# C. 15 menu repriced: split platform vs walk-in (basis markup komisi)
# D. Simulasi harga x777 -> x000 (2 varian bacaan) dgn qty Agustus
def p(*a):
    print(*a)

def rows(sql, params=None):
    if params:
        env.cr.execute(sql, params)
    else:
        env.cr.execute(sql)
    return env.cr.fetchall()

D1, D2 = '2026-08-01', '2026-09-01'
CHECK = [628, 622, 630, 626, 627, 623, 576, 616, 620, 614, 588, 601, 615, 548, 547]

# ---------- A. GAJI ----------
p("=== A1. Akun gaji (6101.03/04/05) Agustus ===")
for r in rows("""
    SELECT a.code_store->>'1', a.name->>'en_US', SUM(l.debit-l.credit)
    FROM account_move_line l JOIN account_account a ON a.id=l.account_id
    JOIN account_move m ON m.id=l.move_id
    WHERE m.state='posted' AND m.date BETWEEN '2026-08-01' AND '2026-08-31'
      AND a.code_store->>'1' IN ('6101.03','6101.04','6101.05')
    GROUP BY 1,2 ORDER BY 1
"""):
    p(f"   {r[0]}  {str(r[1])[:42]:<42} {r[2]:>13,.2f}")
env.cr.rollback()

p()
p("=== A2. JE gaji posted: nama move + label lines (struktur beban) ===")
for r in rows("""
    SELECT m.name, l.name, l.debit-l.credit
    FROM account_move_line l JOIN account_move m ON m.id=l.move_id
    JOIN account_account a ON a.id=l.account_id
    WHERE m.state='posted' AND m.date BETWEEN '2026-08-01' AND '2026-08-31'
      AND a.code_store->>'1' IN ('6101.03','6101.04','6101.05')
    ORDER BY m.name, l.id
"""):
    p(f"   {str(r[0]):<18} {str(r[1])[:52]:<52} {r[2]:>13,.2f}")
env.cr.rollback()

p()
p("=== A3. Model HR ada? ===")
mods = rows("""
    SELECT model FROM ir_model
    WHERE model IN ('hr.employee','hr.department','hr.contract','hr.job')
""")
have = [r[0] for r in mods]
p(f"   models: {have}")
if 'hr.employee' in have:
    n_emp = rows("SELECT COUNT(*) FROM hr_employee WHERE active")[0][0]
    p(f"   TOTAL karyawan aktif: {n_emp}")
    env.cr.rollback()
    for r in rows("SELECT id, name FROM hr_employee WHERE active ORDER BY id"):
        p(f"   emp {r[0]:<4} {str(r[1])[:40]}")
    env.cr.rollback()
if 'hr.contract' in have:
    n = rows("SELECT COUNT(*) FROM hr_contract")[0][0]
    p(f"   hr_contract rows: {n}")
    if n:
        for r in rows("""
            SELECT c.id, c.name, c.wage, e.name, c.state
            FROM hr_contract c JOIN hr_employee e ON e.id=c.employee_id LIMIT 20
        """):
            p(f"   contract {r[0]} {str(r[1])[:24]:<24} wage={r[2]} emp={str(r[3])[:20]} state={r[4]}")
    env.cr.rollback()

# ---------- B. DISKON ----------
p()
p("=== B. Diskon POS Agustus (line dgn discount>0) ===")
r = rows("""
    SELECT COUNT(*), COALESCE(SUM(l.qty*l.price_unit*l.discount/100),0),
           COALESCE(SUM(l.price_subtotal),0)
    FROM pos_order_line l JOIN pos_order o ON o.id=l.order_id
    WHERE o.state IN ('done','invoiced') AND o.date_order >= %s AND o.date_order < %s
      AND l.discount > 0
""", (D1, D2))
p(f"   lines diskon : {r[0][0]}")
p(f"   nilai diskon : {r[0][1]:,.2f}")
p(f"   rev net line : {r[0][2]:,.2f}")
env.cr.rollback()
p("   per channel:")
for r in rows("""
    SELECT CASE WHEN rp.name ILIKE '%%Platform%%' THEN rp.name ELSE 'walk-in/other' END ch,
           COUNT(*), COALESCE(SUM(l.qty*l.price_unit*l.discount/100),0)
    FROM pos_order_line l JOIN pos_order o ON o.id=l.order_id
    LEFT JOIN res_partner rp ON rp.id=o.partner_id
    WHERE o.state IN ('done','invoiced') AND o.date_order >= %s AND o.date_order < %s
      AND l.discount > 0
    GROUP BY 1 ORDER BY 3 DESC
""", (D1, D2)):
    p(f"   {str(r[0])[:24]:<24} {r[1]:>5} lines  diskon {r[2]:>13,.2f}")
env.cr.rollback()
p("   top 10 menu terdiskon:")
for r in rows("""
    SELECT pt.name->>'en_US', COUNT(*), COALESCE(SUM(l.qty*l.price_unit*l.discount/100),0)
    FROM pos_order_line l JOIN pos_order o ON o.id=l.order_id
    JOIN product_product pp ON pp.id=l.product_id
    JOIN product_template pt ON pt.id=pp.product_tmpl_id
    WHERE o.state IN ('done','invoiced') AND o.date_order >= %s AND o.date_order < %s
      AND l.discount > 0
    GROUP BY 1 ORDER BY 3 DESC LIMIT 10
""", (D1, D2)):
    p(f"   {str(r[0])[:38]:<38} {r[1]:>4} lines  diskon {r[2]:>12,.2f}")
env.cr.rollback()

# ---------- C. SPLIT PLATFORM 15 MENU ----------
p()
p("=== C. 15 menu repriced: qty & rev Agustus per channel ===")
tot_all = tot_plat = 0.0
qty_all = qty_plat = 0.0
for r in rows("""
    SELECT l.product_id,
           CASE WHEN rp.name ILIKE '%%Platform%%' THEN rp.name ELSE 'walk-in' END ch,
           SUM(l.qty), SUM(l.price_subtotal)
    FROM pos_order_line l JOIN pos_order o ON o.id=l.order_id
    LEFT JOIN res_partner rp ON rp.id=o.partner_id
    WHERE o.state IN ('done','invoiced') AND o.date_order >= %s AND o.date_order < %s
      AND l.product_id = ANY(%s)
    GROUP BY 1,2 ORDER BY 1
""", (D1, D2, CHECK)):
    if r[1] == 'walk-in':
        tot_all += r[3]; qty_all += r[2]
    else:
        tot_plat += r[3]; qty_plat += r[2]
        p(f"   id={r[0]:<5} {str(r[1])[:16]:<16} qty {r[2]:>6,.0f} rev {r[3]:>12,.2f}")
env.cr.rollback()
p(f"   TOTAL platform: qty {qty_plat:,.0f}  rev {tot_plat:,.2f}")
p(f"   TOTAL walk-in : qty {qty_all:,.0f}  rev {tot_all:,.2f}")
p(f"   (semua channel utk 15 menu: {tot_all+tot_plat:,.2f})")

# ---------- D. SIMULASI HARGA ----------
p()
p("=== D. Simulasi x777 -> x000 (qty Agustus konstan, tanpa elastisitas) ===")
info = {}
for r in rows("""
    SELECT pp.id, pt.name->>'en_US', pt.list_price FROM product_product pp
    JOIN product_template pt ON pt.id=pp.product_tmpl_id WHERE pp.id = ANY(%s)
""", (CHECK,)):
    info[r[0]] = (r[1], r[2])
env.cr.rollback()
qtymap = dict((r[0], (r[1], r[2])) for r in rows("""
    SELECT l.product_id, SUM(l.qty), SUM(l.price_subtotal)
    FROM pos_order_line l JOIN pos_order o ON o.id=l.order_id
    WHERE o.state IN ('done','invoiced') AND o.date_order >= %s AND o.date_order < %s
      AND l.product_id = ANY(%s) GROUP BY 1
""", (D1, D2, CHECK)))
env.cr.rollback()
d_ceil = d_plus = 0.0
p(f"   {'menu':<32}{'now':>9}{'x000':>9}{'x000+1000':>11}{'qty':>7}{'Δceil':>10}{'Δ+1000':>10}")
for pid in CHECK:
    nm, cur = info[pid]
    q = qtymap.get(pid, (0, 0))[0]
    ceilk = (int(cur // 1000) + 1) * 1000        # 4.777 -> 5.000
    plusk = ceilk + 1000                          # -> 6.000
    d_ceil += q * (ceilk - cur)
    d_plus += q * (plusk - cur)
    p(f"   {str(nm)[:32]:<32}{cur:>9,.0f}{ceilk:>9,.0f}{plusk:>11,.0f}{q:>7,.0f}{q*(ceilk-cur):>+10,.0f}{q*(plusk-cur):>+10,.0f}")
p(f"   Δ revenue x000 (ceil)      : {d_ceil:>+15,.2f}")
p(f"   Δ revenue x000+1000        : {d_plus:>+15,.2f}")

# ---------- E. GAP ----------
p()
p("=== E. Gap ke target 8% ===")
rev, exp = 240293763.00, 245048995.15
net = rev - exp
p(f"   net sekarang    : {net:>15,.2f}  ({net/rev*100:>5.2f}%)")
for label, r2 in [("x000 ceil", d_ceil), ("x000+1000", d_plus)]:
    rev2 = rev + r2
    p(f"   jika +{label:<10}: net {net + r2:>15,.2f} ({(net+r2)/rev2*100:>5.2f}%)  → butuh tambahan {0.08*rev2-(net+r2):>13,.2f} utk capai 8%")

env.cr.rollback()
p()
p("DONE tmp_profit_levers_recon — read only.")
