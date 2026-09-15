# -*- coding: utf-8 -*-
# Fase 7 — Reclass HPP Bev -> Food (alokasi biaya minuman di dalam paket bundling)
# JE: D 5101.02 (HPP Food) / K 5101.01 (HPP Bev)
# X = biaya komponen Bev yang dikonsumsi via BOM paket Menu Food (atribusi move-based,
#     batas atas defensible dari audit_bev_bundle.py: 5.321.264,19; konsumsi Bev aktual
#     6.360.442,66 — HPP Bev tetap positif setelah reclass).
# Narasi data: 36/70 BOM paket memuat komponen Bev; harga paket dialokasikan ke item
#     utama (Food) → konsumsi minuman ter-book ke HPP Food. Reclass memindahkannya balik.
# P&L netral: total HPP tetap 109.548.621,18; revenue/pos.payment/kas tidak tersentuh.
# Run with RUN=1 to apply.

import os

def p(*a):
    print(*a)

RUN = os.environ.get('RUN') == '1'
D = '2026-08-31'
MISC = 3

D1, D2 = '2026-08-01', '2026-09-01'

def rows(sql, params=None):
    if params:
        env.cr.execute(sql, params)
    else:
        env.cr.execute(sql)
    return env.cr.fetchall()

def bal(code):
    return rows("""
        SELECT COALESCE(SUM(l.debit-l.credit),0) FROM account_move_line l
        JOIN account_account a ON a.id = l.account_id
        JOIN account_move m ON m.id = l.move_id
        WHERE a.code_store->>'1' = %s AND m.state='posted'
    """, (code,))[0][0]

env.cr.execute("""
    SELECT id, code_store->>'1' FROM account_account
    WHERE code_store->>'1' IN ('5101.01','5101.02','5101.03','5101.04')
""")
A = {code: aid for aid, code in env.cr.fetchall()}
p("accounts:", A)
assert '5101.01' in A and '5101.02' in A, "akun HPP tidak ditemukan"

# ---------- 1. state BEFORE ----------
p("")
p("=== BEFORE ===")
bev_before = bal('5101.01')
food_before = bal('5101.02')
pend = bal('5101.04')
gas = bal('5101.03')
p(f"   HPP Bev  5101.01: {bev_before:,.2f}")
p(f"   HPP Food 5101.02: {food_before:,.2f}")
p(f"   HPP Gas  5101.03: {gas:,.2f}")
p(f"   HPP Pend 5101.04: {pend:,.2f}")

# revenue per kategori menu (net) untuk rasio
rev = rows("""
    SELECT pt.categ_id, COALESCE(SUM(l.price_subtotal),0)
    FROM pos_order_line l
    JOIN pos_order o        ON o.id = l.order_id
    JOIN product_product pp ON pp.id = l.product_id
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    WHERE o.state IN ('done','invoiced')
      AND o.date_order >= %s AND o.date_order < %s
      AND pt.categ_id IN (10, 11)
    GROUP BY 1
""", (D1, D2))
rev_map = dict(rev)
rev_bev, rev_food = rev_map.get(10, 0.0), rev_map.get(11, 0.0)
p(f"   rev Menu Bev (10): {rev_bev:,.2f} | rev Menu Food (11): {rev_food:,.2f}")
p(f"   ratio Bev BEFORE: {bev_before/rev_bev*100:,.1f}%")

# ---------- 2. hitung ulang X (move-based, anti double-count) ----------
p("")
p("=== HITUNG X (fresh, bukan hardcoded) ===")
r = rows("""
    SELECT
      COALESCE(SUM(CASE WHEN EXISTS (
            SELECT 1 FROM mrp_bom_line mbl
            JOIN mrp_bom mbom ON mbom.id = mbl.bom_id
            JOIN product_template ptp ON ptp.id = mbom.product_tmpl_id
            WHERE mbl.product_id = pp.id AND mbom.type = 'phantom'
              AND ptp.categ_id = 11) THEN sm.value ELSE 0 END),0),
      COALESCE(SUM(sm.value),0)
    FROM stock_move sm
    JOIN product_product pp  ON pp.id = sm.product_id
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    JOIN stock_location ls   ON ls.id = sm.location_id
    JOIN stock_location ld   ON ld.id = sm.location_dest_id
    WHERE pt.categ_id = 5
      AND ls.usage = 'internal' AND ld.usage = 'customer'
      AND sm.state = 'done'
      AND sm.date >= %s AND sm.date < %s
""", (D1, D2))[0]
via_food_moves, cons_bev_total = r
p(f"   konsumsi Bev via BOM Menu Food (11): {via_food_moves:,.2f}")
p(f"   konsumsi Bev total:                  {cons_bev_total:,.2f}")

X = round(min(via_food_moves, bev_before), 2)   # guard: HPP Bev tidak boleh negatif
p(f"   X final (reclass 5101.01 -> 5101.02): {X:,.2f}")

if X <= 0:
    p("FATAL: X <= 0 — tidak ada yang direclass. Stop.")
    env.cr.rollback()
    raise SystemExit(1)

# ---------- 3. eksekusi ----------
if RUN:
    p("")
    p("=== POSTING JE reclass ===")
    move = env['account.move'].create({
        'journal_id': MISC,
        'date': D,
        'ref': 'Reclass HPP komponen minuman dalam paket Menu Food - Agustus 2026 '
               '(alokasi harga paket bundling; Fase 7)',
        'move_type': 'entry',
        'line_ids': [
            (0, 0, {'account_id': A['5101.02'], 'debit': X, 'credit': 0.0,
                    'name': 'Reclass biaya komponen minuman dalam paket Menu Food '
                            f'(move-based {via_food_moves:,.2f}, dibatasi saldo Bev)'}),
            (0, 0, {'account_id': A['5101.01'], 'debit': 0.0, 'credit': X,
                    'name': 'Reclass HPP Bev -> Food: biaya minuman di paket bundling '
                            'dialokasikan ke kategori paket (Fase 7)'}),
        ],
    })
    move.action_post()
    p("   CREATED:", move.name, "| amount:", f"{X:,.2f}")

    # flush ORM agar verify SQL tidak stale (gotcha fase 2)
    try:
        env.flush_all()
    except AttributeError:
        env['account.move'].flush_model()

# ---------- 4. verifikasi ----------
p("")
p("=== AFTER / VERIFY ===")
bev_after = bal('5101.01')
food_after = bal('5101.02')
p(f"   HPP Bev  5101.01: {bev_before:,.2f} -> {bev_after:,.2f}")
p(f"   HPP Food 5101.02: {food_before:,.2f} -> {food_after:,.2f}")
hpp_total = bev_after + food_after + pend
p(f"   HPP total (Bev+Food+Pend): {hpp_total:,.2f}  (harus 109.548.621,18; Gas {gas:,.2f} di luar)")
p(f"   ratio Bev AFTER : {bev_after/rev_bev*100:,.1f}%  (rev {rev_bev:,.2f})")
p(f"   ratio Food AFTER: {food_after/rev_food*100:,.1f}%  (rev {rev_food:,.2f})")

tb = rows("""
    SELECT COALESCE(SUM(l.debit),0)-COALESCE(SUM(l.credit),0)
    FROM account_move_line l JOIN account_move m ON m.id = l.move_id
    WHERE m.state='posted'
""")[0][0]
p(f"   trial balance diff: {tb:,.2f}  (harus 0)")

pl = rows("""
    SELECT
      (SELECT COALESCE(SUM(l.credit-l.debit),0) FROM account_move_line l
         JOIN account_account a ON a.id=l.account_id JOIN account_move m ON m.id=l.move_id
         WHERE m.state='posted' AND m.date >= '2026-08-01' AND m.date <= '2026-08-31'
           AND a.account_type LIKE 'income%'),
      (SELECT COALESCE(SUM(l.debit-l.credit),0) FROM account_move_line l
         JOIN account_account a ON a.id=l.account_id JOIN account_move m ON m.id=l.move_id
         WHERE m.state='posted' AND m.date >= '2026-08-01' AND m.date <= '2026-08-31'
           AND a.account_type LIKE 'expense%')
""")[0]
p(f"   P&L Agustus: rev {pl[0]:,.2f} - exp {pl[1]:,.2f} = {pl[0]-pl[1]:,.2f}")
p("   (harus tetap rev 240.293.763,00 | net -4.755.232,15 — P&L netral)")

if RUN:
    assert abs(hpp_total - 109548621.18) < 1.0, "HPP total bergeser — bukan reclass!"
    assert abs(tb) < 0.01, "TB tidak balance!"
    assert abs((pl[0]-pl[1]) - (-4755232.15)) < 1.0, "P&L berubah — bukan reclass netral!"
    env.cr.commit()
    p("")
    p("COMMITTED. Fase 7 selesai.")
else:
    p("")
    p("DRY-RUN — re-run with RUN=1.")
    env.cr.rollback()
