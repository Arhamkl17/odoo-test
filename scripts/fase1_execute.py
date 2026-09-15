# -*- coding: utf-8 -*-
# Fase 1 execution — guide-perbaikan-sistem-data-1
# Scope (gated by RUN=1): category config hygiene + repost JE (HPP conversion to real consumption)
# Config-only dry-run is safe; JE only created when RUN=1.

import os
from odoo import api, fields, models
from odoo.tools import float_is_zero, float_round

def p(*a):
    print(*a)

RUN = os.environ.get('RUN') == '1'
D1, D2 = '2026-08-01', '2026-08-31'
CAT_FOOD_RAW = 6      # Bahan Baku Food        -> Persediaan 1103.02
CAT_BEV_RAW = 5       # Bahan Baku Beverage    -> Persediaan 1103.01
CAT_SUP = 7           # Bahan Pendukung Menu   -> Persediaan 1103.03
CAT_FOOD_MENU = 11    # Menu Food
CAT_BEV_MENU = 10     # Menu Beverage
ACC = {}  # code -> id, filled below

env.cr.execute("SELECT id, code_store->>'1', name->>'en_US' FROM account_account WHERE code_store->>'1' IN ('1103.01','1103.02','1103.03','5101.01','5101.02','5101.03','5101.04','23100010','5101.08')")
for aid, code, name in env.cr.fetchall():
    ACC[code] = aid
p("Accounts:", ACC)

stj = env['account.journal'].browse(8)  # STJ Penilaian Inventaris
p("Stock journal:", stj.id, stj.name)

# ---------------------------------------------------------------- 1. config hygiene
cats = env['product.category'].browse([5, 6, 7, 10, 11])
p("")
p("== 1. BEFORE:", [(c.id, c.name, c.property_cost_method, c.property_valuation) for c in cats])
if RUN:
    cats.write({'property_cost_method': 'fifo', 'property_valuation': 'real_time'})
    # flush company-dependent properties to ir_property
    env['product.category'].flush_model(['property_cost_method', 'property_valuation'])
    env['ir.property']._multi_to_check  # touch to force reload (no-op read)
    env.cr.execute("SELECT id, name, property_cost_method, property_valuation FROM product_category WHERE id IN (5,6,7,10,11)")
    p("== 1. AFTER :", env.cr.fetchall())
else:
    p("   (dry-run: no write)")

# ---------------------------------------------------------------- 2. recompute move values
p("")
p("== 2. recompute stock.move values with new cost basis")
if RUN:
    moves = env['stock.move'].search([
        ('state', '=', 'done'),
        ('date', '>=', '2026-08-01'), ('date', '<', '2026-09-01'),
    ])
    # every move of storable products that has a value already; recompute via ORM to respect fifo/avg
    valued = moves.filtered(lambda m: m.product_id.is_storable and m.value)
    p("   moves total:", len(moves), "| valued:", len(valued), "| sum value:", float_round(sum(valued.mapped('value')), 2))
    # ORM-driven recompute: write quantity/value through _set_value where applicable
    # v19: value is computed during action_done; safest recompute = set standard_price snapshot then value via write
    # NOTE: value is a stored computed field; trigger recompute by touching product cost context
    env.add_to_compute(env['stock.move']._fields['value'], valued)
    env.flush_all()
    p("   after recompute sum value:", float_round(sum(env['stock.move'].browse([m.id for m in valued]).mapped('value')), 2))
else:
    env.cr.execute("""
        SELECT COALESCE(SUM(value),0) FROM stock_move
        WHERE state='done' AND date >= %s AND date < %s
    """, (D1, '2026-09-01'))
    p("   (dry-run) current sum value:", env.cr.fetchone()[0])

# ---------------------------------------------------------------- 3. repost JE
p("")
p("== 3. HPP conversion JE")
env.cr.execute("""
    SELECT COALESCE(SUM(sm.value),0)
    FROM stock_move sm
    JOIN product_product pp ON pp.id = sm.product_id
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    JOIN stock_location ls ON ls.id = sm.location_id
    JOIN stock_location ld ON ld.id = sm.location_dest_id
    WHERE ls.usage='internal' AND ld.usage='customer'
      AND sm.state='done' AND sm.date >= %s AND sm.date < %s
      AND pt.categ_id IN (5, 6, 7)
""", (D1, '2026-09-01'))
consumption = env.cr.fetchone()[0]
p("   real consumption value Aug:", consumption)

env.cr.execute("""
    SELECT a.code_store->>'1' code, SUM(l.debit - l.credit) aug
    FROM account_account a
    JOIN account_move_line l ON l.account_id = a.id
    JOIN account_move m ON m.id = l.move_id
    WHERE m.state='posted' AND m.date >= %s AND m.date <= %s
      AND a.code_store->>'1' IN ('5101.01','5101.02','5101.04')
    GROUP BY code
""", (D1, D2))
hpp_jes = dict(env.cr.fetchall())
p("   posted HPP JEs:", hpp_jes)
hpp_total = sum(hpp_jes.values())
delta = round(consumption - hpp_total, 2)
p("   delta (consumption - HPP JEs):", delta)

if RUN and abs(delta) > 1:
    move = env['account.move'].create({
        'journal_id': stj.id,
        'date': D2,
        'ref': "Repost HPP Agustus 2026 - konversi ke konsumsi aktual (guide-perbaikan-sistem-data-1 Fase 1)",
        'move_type': 'entry',
        'line_ids': [(0, 0, {
            'account_id': ACC['5101.02'],
            'debit': delta if delta > 0 else 0,
            'credit': -delta if delta < 0 else 0,
            'name': 'Koreksi HPP Food ke konsumsi aktual Agustus 2026',
        }), (0, 0, {
            'account_id': ACC['1103.02'],
            'debit': -delta if delta < 0 else 0,
            'credit': delta if delta > 0 else 0,
            'name': 'Penyesuaian Persediaan Bahan Baku Food (repost Agustus)',
        })],
    })
    move.action_post()
    p("   CREATED JE:", move.name, "| amount:", delta)
elif RUN:
    p("   delta negligible, no JE")
else:
    p("   (dry-run: JE would be", delta, ")")

# ---------------------------------------------------------------- 4. verify ratios
p("")
p("== 4. ratio check")
env.cr.execute("""
    SELECT SUM(pol.price_subtotal_incl) FROM pos_order_line pol
    JOIN pos_order po ON po.id = pol.order_id
    JOIN product_product pp ON pp.id = pol.product_id
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    WHERE po.state IN ('done','invoiced')
      AND po.date_order AT TIME ZONE 'UTC' >= %s
      AND po.date_order AT TIME ZONE 'UTC' < (%s)::date + INTERVAL '1 day'
      AND pt.categ_id = 11
""", (D1, D2))
food_rev = env.cr.fetchone()[0]
env.cr.execute("""
    SELECT SUM(pol.price_subtotal_incl) FROM pos_order_line pol
    JOIN pos_order po ON po.id = pol.order_id
    JOIN product_product pp ON pp.id = pol.product_id
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    WHERE po.state IN ('done','invoiced')
      AND po.date_order AT TIME ZONE 'UTC' >= %s
      AND po.date_order AT TIME ZONE 'UTC' < (%s)::date + INTERVAL '1 day'
      AND pt.categ_id = 10
""", (D1, D2))
bev_rev = env.cr.fetchone()[0]
env.cr.execute("""
    SELECT SUM(CASE WHEN pt.categ_id=6 THEN sm.value ELSE 0 END),
           SUM(CASE WHEN pt.categ_id=5 THEN sm.value ELSE 0 END),
           SUM(CASE WHEN pt.categ_id=7 THEN sm.value ELSE 0 END)
    FROM stock_move sm
    JOIN product_product pp ON pp.id = sm.product_id
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    JOIN stock_location ls ON ls.id = sm.location_id
    JOIN stock_location ld ON ld.id = sm.location_dest_id
    WHERE ls.usage='internal' AND ld.usage='customer'
      AND sm.state='done' AND sm.date >= %s AND sm.date < %s AND pt.categ_id IN (5,6,7)
""", (D1, '2026-09-01'))
food_c, bev_c, sup_c = env.cr.fetchone()
p(f"   Food rev {food_rev:,.0f} | consumption {food_c:,.0f} | ratio {food_c/food_rev*100:.1f}%  (target ~40-42%)")
p(f"   Bev  rev {bev_rev:,.0f} | consumption {bev_c:,.0f} | ratio {bev_c/bev_rev*100:.1f}%")
p(f"   Pendukung consumption {sup_c:,.0f}")
total_rev = food_rev + bev_rev
p(f"   TOTAL consumption {food_c+bev_c+sup_c:,.0f} / rev {total_rev:,.0f} = {(food_c+bev_c+sup_c)/total_rev*100:.1f}%")

if not RUN:
    env.cr.rollback()
    p("")
    p("DRY-RUN ONLY — rolled back. Re-run with RUN=1 to apply.")
else:
    env.cr.commit()
    p("")
    p("COMMITTED (Fase 1 core).")
