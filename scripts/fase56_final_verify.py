# -*- coding: utf-8 -*-
# Fase 5+6 — final verification (read-only) + P&L delta summary

def p(*a):
    print(*a)

D1, D2 = '2026-08-01', '2026-08-31'

def bal(code, d1=None, d2=None):
    extra = ""
    params = [code]
    if d1:
        extra = " AND m.date >= %s AND m.date <= %s"
        params += [d1, d2]
    env.cr.execute(f"""
        SELECT COALESCE(SUM(l.debit-l.credit),0) FROM account_move_line l
        JOIN account_account a ON a.id=l.account_id JOIN account_move m ON m.id=l.move_id
        WHERE a.code_store->>'1'=%s AND m.state='posted'{extra}
    """, params)
    return env.cr.fetchone()[0]

p("=" * 70)
p("FASE 5 — Data hygiene")
p("=" * 70)
p("1. Komisi final (10%):")
env.cr.execute("""
    SELECT m.name, m.state, m.ref, m.amount_total FROM account_move m
    WHERE m.ref ILIKE '%komisi%' AND m.state IN ('posted','cancel') ORDER BY m.id
""")
for r in env.cr.fetchall():
    p("   ", r)
p("   net komisi posted:", f"{bal('6300.01'):,.2f}", "(target 8.192.974,60)")

p("")
p("2. Gaji final:")
env.cr.execute("""
    SELECT m.name, m.state, m.ref, m.amount_total FROM account_move m
    WHERE (m.ref ILIKE '%gaji%' OR m.ref ILIKE '%salary%') ORDER BY m.id
""")
for r in env.cr.fetchall():
    p("   ", r)

p("")
p("3. Histori cancelled JE: DIPERTAHANKAN (keputusan default, audit trail)")

p("")
p("=" * 70)
p("FASE 6 — Re-audit lengkap (post all phases)")
p("=" * 70)

p("4. Trial balance:")
env.cr.execute("""
    SELECT COALESCE(SUM(l.debit),0), COALESCE(SUM(l.credit),0),
           COALESCE(SUM(l.debit),0)-COALESCE(SUM(l.credit),0)
    FROM account_move_line l JOIN account_move m ON m.id=l.move_id WHERE m.state='posted'
""")
p("   ", env.cr.fetchone())

p("")
p("5. AR aging (open receivable):")
env.cr.execute("""
    SELECT COUNT(*) FROM account_move_line l
    JOIN account_move m ON m.id=l.move_id JOIN account_account a ON a.id=l.account_id
    WHERE a.account_type='asset_receivable' AND m.state='posted' AND NOT l.reconciled
""")
p("   open lines:", env.cr.fetchone()[0], "(harus 0)")

p("")
p("6. Kas & bank final (active accounts):")
env.cr.execute("""
    SELECT a.code_store->>'1' code, a.name->>'en_US' aname, a.active,
           COALESCE(SUM(l.debit-l.credit),0) bal
    FROM account_account a
    JOIN account_move_line l ON l.account_id=a.id
    JOIN account_move m ON m.id=l.move_id AND m.state='posted'
    WHERE a.account_type IN ('asset_cash','asset_bank')
    GROUP BY code, aname, a.active ORDER BY bal DESC
""")
for r in env.cr.fetchall():
    p("   ", r)

p("")
p("7. HPP final (harus = konsumsi aktual):")
for code, label in [('5101.02','Food'), ('5101.01','Bev'), ('5101.04','Pendukung'), ('5101.03','Gas')]:
    p(f"   {code} {label}: {bal(code, D1, D2):,.2f}")

env.cr.execute("""
    SELECT SUM(pol.price_subtotal_incl) FROM pos_order_line pol
    JOIN pos_order po ON po.id=pol.order_id
    JOIN product_product pp ON pp.id=pol.product_id
    JOIN product_template pt ON pt.id=pp.product_tmpl_id
    WHERE po.state IN ('done','invoiced') AND pt.categ_id=11
      AND po.date_order AT TIME ZONE 'UTC' >= %s
      AND po.date_order AT TIME ZONE 'UTC' < (%s)::date + INTERVAL '1 day'
""", (D1, D2))
food_rev = env.cr.fetchone()[0]
hpp_food = bal('5101.02', D1, D2)
p(f"   Food ratio: {hpp_food/food_rev*100:.1f}% (target ~40-42%, hasil {hpp_food:,.0f}/{food_rev:,.0f})")

p("")
p("8. POS collection integrity:")
env.cr.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM pos_payment")
p("   rows & total (harus 4515 / 232.683.763):", env.cr.fetchone())

p("")
p("9. Beban penyusutan final Agustus:")
for code, label in [('6101.14','Kendaraan'), ('6101.15','Peralatan Kantor'), ('6101.16','Peralatan Resto'),
                    ('6101.17','Renovasi'), ('6200.05','Bangunan Gudang'), ('6200.06','Peralatan Gudang'),
                    ('6200.07','IT & POS')]:
    p(f"   {code} {label}: {bal(code, D1, D2):,.2f}")
tot_dep = sum(bal(c, D1, D2) for c in ['6101.14','6101.15','6101.16','6101.17','6200.05','6200.06','6200.07'])
p(f"   TOTAL: {tot_dep:,.2f} (dari 20.870.000,00)")

p("")
p("10. Revenue final Agustus (posted income accounts):")
env.cr.execute("""
    SELECT COALESCE(SUM(l.credit-l.debit),0) FROM account_move_line l
    JOIN account_account a ON a.id=l.account_id JOIN account_move m ON m.id=l.move_id
    WHERE m.state='posted' AND m.date >= %s AND m.date <= %s AND a.account_type IN ('income','income_other')
""", (D1, D2))
rev = env.cr.fetchone()[0]
env.cr.execute("""
    SELECT COALESCE(SUM(l.debit-l.credit),0) FROM account_move_line l
    JOIN account_account a ON a.id=l.account_id JOIN account_move m ON m.id=l.move_id
    WHERE m.state='posted' AND m.date >= %s AND m.date <= %s
      AND a.account_type IN ('expense','expense_direct_cost','expense_depreciation')
""", (D1, D2))
exp = env.cr.fetchone()[0]
p(f"   Pendapatan Agustus: {rev:,.2f}")
p(f"   Beban Agustus     : {exp:,.2f}")
p(f"   Laba/(Rugi) Agustus (P&L accounts only): {rev-exp:,.2f}")

p("")
p("11. Struktur payment final:")
env.cr.execute("""
    SELECT pm.name->>'en_US', COUNT(pp.id), COALESCE(SUM(pp.amount),0)
    FROM pos_payment_method pm LEFT JOIN pos_payment pp ON pp.payment_method_id=pm.id
    WHERE pm.active GROUP BY pm.name->>'en_US' ORDER BY 3 DESC
""")
for r in env.cr.fetchall():
    p("   ", r)

env.cr.rollback()
p("")
p("DONE fase 5-6 verify.")
