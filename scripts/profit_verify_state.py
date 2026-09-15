# -*- coding: utf-8 -*-
# profit_verify_state.py — READ-ONLY
# ⚠️ CATATAN: section A/B meng-agregasi BARIS (debit-credit)>0 — JEBakan: akun yang
# pernah di-reverse (mis. 6300.01 komisi) terhitung GROSS (20,48jt, bukan net 8,19jt),
# jadi "TOTAL EXP" dan "NET" di bawah BUKAN P&L benar. P&L benar (net-of-reversal,
# agregat per akun): rev 240.293.763,00 − exp 245.048.995,15 = −4.755.232,15
# (= persis angka FASE_RESULT.md; lihat scripts/profit_recon_baseline.py).
# Verifikasi ulang angka kunci P&L Agustus 2026 langsung ke DB (bukan dari MD),
# sebagai basis opsi profit demo (target margin 8-10%).
#
# Jalankan:
#   su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 --db_user odoo --db_password odoo" < scripts/profit_verify_state.py
#
# env disediakan odoo shell. Tanpa commit — rollback di akhir.

def p(*a):
    print(*a)

D1, D2 = '2026-08-01', '2026-09-01'

def rows(sql, params=None):
    if params:
        env.cr.execute(sql, params)
    else:
        env.cr.execute(sql)
    return env.cr.fetchall()

def section(title):
    p()
    p("=" * 78)
    p(title)
    p("=" * 78)

def bal(code, d1='2026-08-01', d2='2026-08-31'):
    return rows("""
        SELECT COALESCE(SUM(l.debit-l.credit),0) FROM account_move_line l
        JOIN account_account a ON a.id = l.account_id
        JOIN account_move m ON m.id = l.move_id
        WHERE a.code_store->>'1' = %s AND m.state='posted'
          AND m.date >= %s AND m.date <= %s
    """, (code, d1, d2))[0][0]

# ---------- A. P&L per akun ----------
section("A. P&L AGUSTUS — revenue & expense per akun (posted)")
rev_rows = rows("""
    SELECT a.code_store->>'1' code, a.name->>'en_US' aname,
           SUM(l.credit - l.debit) amt
    FROM account_move_line l
    JOIN account_account a ON a.id = l.account_id
    JOIN account_move m ON m.id = l.move_id
    WHERE m.state='posted' AND m.date >= %s AND m.date <= '2026-08-31'
      AND a.account_type LIKE 'income%%' AND (l.credit - l.debit) > 0
    GROUP BY code, aname ORDER BY amt DESC
""", (D1,))
tot_rev = 0.0
for r in rev_rows:
    p(f"   {r[0]:<10} {r[1]:<40} {r[2]:>15,.2f}")
    tot_rev += r[2]
p(f"   {'TOTAL REV':<51} {tot_rev:>15,.2f}")

exp_rows = rows("""
    SELECT a.code_store->>'1' code, a.name->>'en_US' aname,
           SUM(l.debit - l.credit) amt
    FROM account_move_line l
    JOIN account_account a ON a.id = l.account_id
    JOIN account_move m ON m.id = l.move_id
    WHERE m.state='posted' AND m.date >= %s AND m.date <= '2026-08-31'
      AND a.account_type LIKE 'expense%%' AND (l.debit - l.credit) > 0
    GROUP BY code, aname ORDER BY amt DESC
""", (D1,))
tot_exp = 0.0
for r in exp_rows:
    p(f"   {r[0]:<10} {r[1]:<40} {r[2]:>15,.2f}")
    tot_exp += r[2]
p(f"   {'TOTAL EXP':<51} {tot_exp:>15,>15.2f}") if False else p(f"   {'TOTAL EXP':<51} {tot_exp:>15,.2f}")
p(f"   NET: {tot_rev - tot_exp:,.2f}")

# ---------- B. Lever kunci ----------
section("B. LEVER KUNCI — penyusutan, gaji, komisi, HPP")
dep_codes = ('6101.14', '6101.15', '6101.16', '6101.17', '6200.05', '6200.06', '6200.07')
dep_total = 0.0
for c in dep_codes:
    v = bal(c)
    if v:
        p(f"   dep {c}: {v:>15,.2f}")
        dep_total += v
p(f"   DEP TOTAL: {dep_total:,.2f}")

gaji = bal('6101.03') + bal('6101.04') + bal('6101.05')
p(f"   GAJI (6101.03+04+05): {gaji:,.2f}")

kom = bal('6300.01')
p(f"   KOMISI (6300.01): {kom:,.2f}")

hpp_bev, hpp_food, hpp_gas, hpp_pend = (bal('5101.01'), bal('5101.02'),
                                        bal('5101.03'), bal('5101.04'))
p(f"   HPP Bev 5101.01: {hpp_bev:,.2f}")
p(f"   HPP Food 5101.02: {hpp_food:,.2f}")
p(f"   HPP Gas 5101.03: {hpp_gas:,.2f}")
p(f"   HPP Pend 5101.04: {hpp_pend:,.2f}")

# ---------- C. Basis komisi platform (order total per partner platform) ----------
section("C. BASIS KOMISI PLATFORM — pos_order per partner (amount_total)")
plat = rows("""
    SELECT rp.name, SUM(po.amount_total) total, COUNT(*)
    FROM pos_order po JOIN res_partner rp ON rp.id = po.partner_id
    WHERE po.state IN ('done','invoiced')
      AND po.date_order AT TIME ZONE 'UTC' >= %s
      AND po.date_order AT TIME ZONE 'UTC' < %s
      AND rp.name ILIKE '%%Platform%%'
    GROUP BY rp.name ORDER BY rp.name
""", (D1, D2))
plat_total = 0.0
for r in plat:
    p(f"   {r[0]:<28} {r[1]:>15,.2f}  ({r[2]} orders)")
    plat_total += r[1]
p(f"   PLATFORM TOTAL: {plat_total:,.2f}")
p("   (cek: 10% x basis = komisi 6300.01?)")

# ---------- D. Revenue POS per kategori menu + invariants ----------
section("D. REVENUE POS PER KATEGORI MENU + INVARIANTS")
rev_cat = rows("""
    SELECT pt.categ_id, COALESCE(SUM(l.price_subtotal),0), COUNT(*)
    FROM pos_order_line l
    JOIN pos_order o        ON o.id = l.order_id
    JOIN product_product pp ON pp.id = l.product_id
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    WHERE o.state IN ('done','invoiced')
      AND o.date_order >= %s AND o.date_order < %s
      AND pt.categ_id IN (10, 11)
    GROUP BY 1
""", (D1, D2))
rc = dict((r[0], r[1]) for r in rev_cat)
for r in rev_cat:
    p(f"   categ {r[0]}: net {r[1]:>15,.2f} ({r[2]} lines)")

pos_tot = rows("""
    SELECT COALESCE(SUM(o.amount_total),0), COUNT(*)
    FROM pos_order o
    WHERE o.state IN ('done','invoiced')
      AND o.date_order AT TIME ZONE 'UTC' >= %s
      AND o.date_order AT TIME ZONE 'UTC' < %s
""", (D1, D2))[0]
p(f"   POS amount_total total: {pos_tot[0]:,.2f} ({pos_tot[1]} orders)")

pay_tot = rows("""
    SELECT COALESCE(SUM(pos_payment.amount),0), COUNT(*)
    FROM pos_payment
    WHERE pos_payment.pos_order_id IN (
        SELECT o.id FROM pos_order o
        WHERE o.state IN ('done','invoiced')
          AND o.date_order AT TIME ZONE 'UTC' >= %s
          AND o.date_order AT TIME ZONE 'UTC' < %s)
""", (D1, D2))[0]
p(f"   pos.payment total: {pay_tot[0]:,.2f} ({pay_tot[1]} rows)")

tb = rows("""
    SELECT COALESCE(SUM(l.debit),0)-COALESCE(SUM(l.credit),0)
    FROM account_move_line l JOIN account_move m ON m.id = l.move_id
    WHERE m.state='posted'
""")[0][0]
p(f"   trial balance diff: {tb:,.2f}")

# ---------- E. OPEX lain (utk opsi reclass/adjust non-lever) ----------
section("E. OPEX LAIN > 500rb (top 15, di luar HPP/gaji/komisi/dep)")
known = ('5101.01', '5101.02', '5101.03', '5101.04', '6101.03', '6101.04', '6101.05',
         '6300.01', '6101.14', '6101.15', '6101.16', '6101.17', '6200.05', '6200.06', '6200.07')
others = rows("""
    SELECT a.code_store->>'1' code, a.name->>'en_US' aname, SUM(l.debit-l.credit) amt
    FROM account_move_line l
    JOIN account_account a ON a.id = l.account_id
    JOIN account_move m ON m.id = l.move_id
    WHERE m.state='posted' AND m.date >= %s AND m.date <= '2026-08-31'
      AND a.account_type LIKE 'expense%%' AND a.code_store->>'1' NOT IN %s
    GROUP BY 1, 2 HAVING SUM(l.debit-l.credit) > 500000
    ORDER BY amt DESC LIMIT 15
""", (D1, tuple(known)))
for r in others:
    p(f"   {r[0]:<10} {r[1]:<40} {r[2]:>15,.2f}")

env.cr.rollback()
p()
p("DONE profit_verify_state — read only, rollback OK.")
