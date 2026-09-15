# -*- coding: utf-8 -*-
# profit_recon_baseline.py — READ-ONLY
# 1) Rekon GL posted Agustus vs angka MD (FASE_RESULT.md): dari mana +15,96jt revenue
#    dan +21,6jt expense yang tidak masuk cerita MD (duga: JE Diskon/Retur 15,7jt +
#    bucket beban kecil <500k).
# 2) Data simulasi repricing 14 menu x777 (laporan_margin_profit.md) terhadap
#    pos_order_line Agustus + interaksi komisi platform.
# 3) Saldo kas/bank GL utk mekanisme JE opsi.
#
# Jalankan:
#   su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 --db_user odoo --db_password odoo" < scripts/profit_recon_baseline.py

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

# ============================================================
# A. SEMUA akun income-type Agustus: credit, debit, net
# ============================================================
section("A. AKUN INCOME-TYPE AGUSTUS (credit / debit / net)")
inc = rows("""
    SELECT a.code_store->>'1' code, a.name->>'en_US' aname, a.account_type,
           SUM(l.credit) cr, SUM(l.debit) dr
    FROM account_move_line l
    JOIN account_account a ON a.id = l.account_id
    JOIN account_move m ON m.id = l.move_id
    WHERE m.state='posted' AND m.date >= %s AND m.date <= '2026-08-31'
      AND a.account_type LIKE 'income%%'
    GROUP BY 1,2,3 ORDER BY 1
""", (D1,))
for r in inc:
    p(f"   {r[0]:<10} {str(r[1])[:38]:<38} {r[2]:<18} cr {r[3]:>15,.2f}  dr {r[4]:>14,.2f}  net {r[3]-r[4]:>15,.2f}")

# ============================================================
# B. JE non-POS yang menyentuh 4101.xx (duga: JE Diskon/Retur + MISC/0036)
# ============================================================
section("B. JE NON-POS yang menyentuh 4101.xx Agustus (per move)")
try:
    mv = rows("""
        SELECT m.name, m.ref, j.code, m.date, m.pos_session_id,
               SUM(l.credit-l.debit) amt, COUNT(*)
        FROM account_move_line l
        JOIN account_account a ON a.id = l.account_id
        JOIN account_move m ON m.id = l.move_id
        JOIN account_journal j ON j.id = m.journal_id
        WHERE m.state='posted' AND m.date >= %s AND m.date <= '2026-08-31'
          AND a.code_store->>'1' LIKE '4101.%%'
        GROUP BY m.id, m.name, m.ref, j.code, m.date, m.pos_session_id
        ORDER BY m.date, m.name
    """, (D1,))
    tot_pos = tot_nonpos = 0.0
    for r in mv:
        tag = "POS" if r[4] else "NON-POS"
        if r[4]:
            tot_pos += r[5]
        else:
            tot_nonpos += r[5]
        p(f"   [{tag}] {str(r[0]):<22} {str(r[1])[:30]:<30} {str(r[2]):<6} {r[5]:>15,.2f}")
    p(f"   subtotal POS-close JE : {tot_pos:>15,.2f}")
    p(f"   subtotal NON-POS JE   : {tot_nonpos:>15,.2f}")
except Exception as e:
    env.cr.rollback()
    p("   skip:", e)

# ============================================================
# C. SEMUA akun expense Agustus (tanpa filter 500k) — cari bucket 22jt kecil
#    + posisi 4102.xx/4103.xx (kali ini expense-type?)
# ============================================================
section("C. SEMUA AKUN EXPENSE AGUSTUS >= 100rb (cari bucket kecil + 4102/4103)")
exp = rows("""
    SELECT a.code_store->>'1' code, a.name->>'en_US' aname, a.account_type,
           SUM(l.debit-l.credit) amt
    FROM account_move_line l
    JOIN account_account a ON a.id = l.account_id
    JOIN account_move m ON m.id = l.move_id
    WHERE m.state='posted' AND m.date >= %s AND m.date <= '2026-08-31'
      AND a.account_type LIKE 'expense%%'
    GROUP BY 1,2,3 HAVING SUM(l.debit-l.credit) >= 100000
    ORDER BY amt DESC
""", (D1,))
tot = 0.0
for r in exp:
    tot += r[3]
    p(f"   {r[0]:<10} {str(r[1])[:40]:<40} {r[3]:>15,.2f}")
p(f"   SUBTOTAL (>=100rb, {len(exp)} akun): {tot:,.2f}")
small = rows("""
    SELECT COALESCE(SUM(l.debit-l.credit),0), COUNT(DISTINCT a.id)
    FROM account_move_line l
    JOIN account_account a ON a.id = l.account_id
    JOIN account_move m ON m.id = l.move_id
    WHERE m.state='posted' AND m.date >= %s AND m.date <= '2026-08-31'
      AND a.account_type LIKE 'expense%%'
    GROUP BY a.id HAVING SUM(l.debit-l.credit) < 100000
""", (D1,))
if small:
    p(f"   sisanya (akun <100rb): {sum(r[0] for r in small):,.2f} di {len(small)} akun")

# ============================================================
# D. REKON GL vs MD — net line by line
# ============================================================
section("D. REKON NET: GL vs MD")
rev_income_type = sum(r[3] - r[4] for r in inc if r[0].startswith('4101') or r[0].startswith('7101'))
p(f"   rev income-type 4101+7101 (net)      : {rev_income_type:>15,.2f}")
contra = [(r[0], r[1], r[3]-r[4]) for r in inc if not (r[0].startswith('4101') or r[0].startswith('7101'))]
for c in contra:
    p(f"   contra income {c[0]} {str(c[1])[:30]:<30} net {c[2]:>15,.2f}")
p(f"   MD pendapatan                        : {'240,293,763.00':>15}")
p(f"   GL net P&L (A vs C section lama)     : -10,774,333.10")
p(f"   MD rugi bersih                       : -4,755,232.15")

# ============================================================
# E. SIMULASI REPRICING 14 MENU x777 (harga < cost / margin tipis)
# ============================================================
section("E. REPRICING x777 — pos_order_line Agustus per menu")
SARAN = {
    'MENU SAMBAL RICA MANADO': 4777,
    'MOZZARELLA': 11777,
    'AIR GELAS': 1777,
    'MENU SAMBAL KOREK SURABAYA': 5777,
    'MENU SAMBAL ORIGINAL': 5777,
    'KEMASAN VARIAN AYAM': 2777,
    'PARUTAN KEJU': 6777,
    'YUKSSS RAMA 1': 18777,
    'PKG LOKAL DUO': 40777,
    'PAKET MEVVAH BERDUA': 38777,
    'PAKET GEPREK BAKAR': 38777,
    'SEGEPOK BERLIMA': 100777,
    'PAKET YUKSSS MABAR': 36777,
    'GEPREK ORIGINAL PAHA BAWAH': 14777,
    'GEPREK ORIGINAL SAYAP': 14777,
}
try:
    names = list(SARAN.keys())
    pats = tuple('%' + n + '%' for n in names)
    r = rows("""
        SELECT pt.name->>'en_US' pname, COUNT(*) lines, SUM(l.qty) qty,
               SUM(l.price_subtotal) rev_now,
               SUM(l.qty * %s::numeric) -- placeholder replaced below
        FROM pos_order_line l
        JOIN pos_order o ON o.id = l.order_id
        JOIN product_product pp ON pp.id = l.product_id
        JOIN product_template pt ON pt.id = pp.product_tmpl_id
        WHERE o.state IN ('done','invoiced')
          AND o.date_order >= %s AND o.date_order < %s
          AND pt.name->>'en_US' ILIKE ANY(%s)
        GROUP BY 1 ORDER BY 1
    """, (0, D1, D2, pats))
    env.cr.rollback()
except Exception:
    env.cr.rollback()

# per menu: qty, revenue now, revenue at saran (qty * saran), delta; + platform split
tot_delta = 0.0
per_menu = []
for nm, newprice in SARAN.items():
    try:
        r = rows("""
            SELECT COUNT(*), COALESCE(SUM(l.qty),0), COALESCE(SUM(l.price_subtotal),0)
            FROM pos_order_line l
            JOIN pos_order o ON o.id = l.order_id
            JOIN product_product pp ON pp.id = l.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE o.state IN ('done','invoiced')
              AND o.date_order >= %s AND o.date_order < %s
              AND pt.name->>'en_US' ILIKE %s
        """, (D1, D2, '%' + nm + '%'))
        env.cr.rollback()
    except Exception:
        env.cr.rollback()
        continue
    n, qty, rev = r[0]
    if n == 0:
        p(f"   {nm[:34]:<34} TIDAK TERJUAL di Agustus")
        continue
    new_rev = qty * newprice
    delta = new_rev - rev
    tot_delta += delta
    per_menu.append((nm, qty, rev, new_rev, delta))
    p(f"   {nm[:34]:<34} qty {qty:>7,.0f}  rev {rev:>13,.2f} -> {new_rev:>13,.2f}  Δ {delta:>+13,.2f}")
p(f"   TOTAL Δ revenue repricing x777       : {tot_delta:>+15,.2f}")

# platform split dari menu-menu tsb (interaksi komisi 10%)
plat_delta = {}
for nm, newprice in SARAN.items():
    try:
        r = rows("""
            SELECT rp.name, COALESCE(SUM(l.qty),0), COALESCE(SUM(l.price_subtotal),0)
            FROM pos_order_line l
            JOIN pos_order o ON o.id = l.order_id
            JOIN res_partner rp ON rp.id = o.partner_id
            JOIN product_product pp ON pp.id = l.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE o.state IN ('done','invoiced')
              AND o.date_order >= %s AND o.date_order < %s
              AND pt.name->>'en_US' ILIKE %s
            GROUP BY 1
        """, (D1, D2, '%' + nm + '%'))
        env.cr.rollback()
    except Exception:
        env.cr.rollback()
        continue
    for pname, qty, rev in r:
        if 'Platform' in (pname or ''):
            new_rev = qty * newprice
            plat_delta[pname] = plat_delta.get(pname, 0.0) + (new_rev - rev)
p("   Δ revenue x777 per platform (basis komisi):")
for k, v in plat_delta.items():
    p(f"      {k:<28} Δ {v:>14,.2f}  (Δ komisi 10% = {v*0.10:,.2f})")
plat_delta_tot = sum(v for v in plat_delta.values())
p(f"   TOTAL Δ basis komisi: {plat_delta_tot:,.2f} → Δ komisi 10% = {plat_delta_tot*0.10:,.2f}")

# ============================================================
# F. SALDO KAS/BANK GL (posted, kumulatif) — utk mekanisme JE opsi
# ============================================================
section("F. SALDO KAS/BANK GL AKTIF (posted, kumulatif s.d. 31 Agu)")
banks = rows("""
    SELECT a.code_store->>'1' code, a.name->>'en_US' aname,
           SUM(l.debit-l.credit) bal
    FROM account_move_line l
    JOIN account_account a ON a.id = l.account_id
    JOIN account_move m ON m.id = l.move_id
    WHERE m.state='posted' AND m.date <= '2026-08-31'
      AND a.account_type = 'asset_cash'
    GROUP BY 1,2 HAVING SUM(l.debit-l.credit) <> 0 ORDER BY bal DESC
""")
for r in banks:
    p(f"   {r[0]:<10} {str(r[1])[:36]:<36} {r[2]:>15,.2f}")

# ============================================================
# G. PAYMENT METHOD MIX Agustus (post-Fase3) — utk opsi scale pos.payment
# ============================================================
section("G. POS PAYMENT METHOD MIX AGUSTUS")
pm = rows("""
    SELECT pm.name->>'en_US' pname, COUNT(*), SUM(pay.amount)
    FROM pos_payment pay
    JOIN pos_payment_method pm ON pm.id = pay.payment_method_id
    JOIN pos_order o ON o.id = pay.pos_order_id
    WHERE o.state IN ('done','invoiced')
      AND o.date_order >= %s AND o.date_order < %s
    GROUP BY 1 ORDER BY 3 DESC
""", (D1, D2))
for r in pm:
    p(f"   {str(r[0])[:32]:<32} {r[1]:>5} rows  {r[2]:>15,.2f}")

env.cr.rollback()
p()
p("DONE profit_recon_baseline — read only, rollback OK.")
