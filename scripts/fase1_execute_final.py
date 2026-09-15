# -*- coding: utf-8 -*-
# Fase 1 EXECUTION — guide-perbaikan-sistem-data-1
# 1) Categories -> FIFO + real_time  (config hygiene)
# 2) Repost JE: HPP -> actual consumption, per category pair
# is_storable on menu kit parents: intentionally NOT flipped (phantom kits already
# consume storable components at POS sale; parent tracking would be redundant).
# Run with RUN=1 to apply. Commits at the end.

import os
from odoo.tools import float_round

def p(*a):
    print(*a)

RUN = os.environ.get('RUN') == '1'
D1, D2 = '2026-08-01', '2026-08-31'
PAIRS = [  # (hpp_code, persediaan_code, categ_id, label)
    ('5101.02', '1103.02', 6, 'Food'),
    ('5101.01', '1103.01', 5, 'Beverage'),
    ('5101.04', '1103.03', 7, 'Pendukung'),
]

env.cr.execute("SELECT id, code_store->>'1' FROM account_account WHERE code_store->>'1' IN ('1103.01','1103.02','1103.03','5101.01','5101.02','5101.04')")
ACC = {code: aid for aid, code in env.cr.fetchall()}
stj = env['account.journal'].browse(8)

# ---- 1. config
cats = env['product.category'].browse([5, 6, 7, 10, 11])
p("BEFORE:", [(c.id, c.name, c.property_cost_method, c.property_valuation) for c in cats])
if RUN:
    cats.write({'property_cost_method': 'fifo', 'property_valuation': 'real_time'})
    env['product.category'].flush_model(['property_cost_method', 'property_valuation'])
    env.cr.execute("SELECT id, name, property_cost_method, property_valuation FROM product_category WHERE id IN (5,6,7,10,11)")
    p("AFTER :", env.cr.fetchall())

# ---- 2. per-category deltas
env.cr.execute("""
    SELECT pt.categ_id, COALESCE(SUM(sm.value),0)
    FROM stock_move sm
    JOIN product_product pp ON pp.id = sm.product_id
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    JOIN stock_location ls ON ls.id = sm.location_id
    JOIN stock_location ld ON ld.id = sm.location_dest_id
    WHERE ls.usage='internal' AND ld.usage='customer'
      AND sm.state='done' AND sm.date >= %s AND sm.date < %s
      AND pt.categ_id IN (5,6,7)
    GROUP BY pt.categ_id
""", (D1, '2026-09-01'))
consumption = dict(env.cr.fetchall())

env.cr.execute("""
    SELECT a.code_store->>'1', SUM(l.debit - l.credit)
    FROM account_account a
    JOIN account_move_line l ON l.account_id = a.id
    JOIN account_move m ON m.id = l.move_id
    WHERE m.state='posted' AND m.date >= %s AND m.date <= %s
      AND a.code_store->>'1' IN ('5101.01','5101.02','5101.04')
    GROUP BY a.code_store->>'1'
""", (D1, D2))
hpp_jes = dict(env.cr.fetchall())
p("consumption:", consumption, "| posted HPP JEs:", hpp_jes)

lines = []
deltas = {}
for hpp_code, pers_code, categ, label in PAIRS:
    delta = round(consumption.get(categ, 0.0) - hpp_jes.get(hpp_code, 0.0), 2)
    deltas[label] = delta
    p(f"   {label}: consumption {consumption.get(categ,0):,.2f} - JE {hpp_jes.get(hpp_code,0):,.2f} = {delta:,.2f}")

total_delta = round(sum(deltas.values()), 2)
p("TOTAL delta:", f"{total_delta:,.2f}")

if RUN:
    line_vals = []
    for hpp_code, pers_code, categ, label in PAIRS:
        d = deltas[label]
        if abs(d) < 0.01:
            continue
        line_vals.append((0, 0, {
            'account_id': ACC[hpp_code],
            'debit': d if d > 0 else 0.0,
            'credit': -d if d < 0 else 0.0,
            'name': f'Repost HPP {label} ke konsumsi aktual Agustus 2026 (Fase 1)',
        }))
        line_vals.append((0, 0, {
            'account_id': ACC[pers_code],
            'debit': -d if d < 0 else 0.0,
            'credit': d if d > 0 else 0.0,
            'name': f'Penyesuaian Persediaan {label} (repost konsumsi Agustus 2026)',
        }))
    move = env['account.move'].create({
        'journal_id': stj.id,
        'date': D2,
        'ref': "Repost HPP Agustus 2026 — konversi ke konsumsi aktual per kategori (guide-perbaikan-sistem-data-1 Fase 1)",
        'move_type': 'entry',
        'line_ids': line_vals,
    })
    move.action_post()
    p("CREATED JE:", move.name, "| total:", f"{total_delta:,.2f}")

    # ---- 3. post-verify
    env.cr.execute("""
        SELECT a.code_store->>'1', SUM(l.debit - l.credit)
        FROM account_account a
        JOIN account_move_line l ON l.account_id = a.id
        JOIN account_move m ON m.id = l.move_id
        WHERE m.state='posted' AND m.date >= %s AND m.date <= %s
          AND a.code_store->>'1' IN ('5101.01','5101.02','5101.04','1103.01','1103.02','1103.03')
        GROUP BY a.code_store->>'1' ORDER BY 1
    """, (D1, D2))
    p("POSTED balances (Aug) after repost:", env.cr.fetchall())

    env.cr.execute("SELECT SUM(debit)-SUM(credit) FROM account_move_line WHERE move_id = %s", (move.id,))
    p("JE balance check (must be 0):", env.cr.fetchone()[0])
    env.cr.commit()
    p("COMMITTED.")
else:
    p("DRY-RUN — nothing written.")
    env.cr.rollback()
