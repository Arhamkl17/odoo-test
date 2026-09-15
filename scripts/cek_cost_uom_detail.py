# -*- coding: utf-8 -*-
# cek_cost_uom_detail.py — READ-ONLY. Detail temuan cek_cost_uom:
# 1) root UoM GRM vs MIL (cross-root di BOM line)  2) non-storable tanpa cost (38 vs 37 Fase 8)
def p(*a):
    print(*a)

def rows(sql, params=None):
    env.cr.execute(sql, params or ())
    return env.cr.fetchall()

def uom_root(u):
    seen = set()
    while u and u.relative_uom_id and u.id not in seen:
        seen.add(u.id)
        u = u.relative_uom_id
    return u

# ---------- 1) Root relatif UoM yang terlibat ----------
p("=== 1) Root relatif UoM (GRM vs MIL dsb) ===")
for name in ("GRM", "MIL", "KG", "LTR", "Units", "Unit(s)", "g", "ml"):
    r = env['uom.uom'].search([('name', '=', name)], limit=1)
    if r:
        root = uom_root(r)
        p(f"   {name:<10} id={r.id:<4} factor={r.factor:<10} root={root.name} (id={root.id}, factor={root.factor})")

# BOM lines cross-root: distribusi pasangan uom & komponen yg terlibat
bls = env['mrp.bom.line'].with_context(active_test=False).search([])
cross = bls.filtered(lambda l: l.product_uom_id and l.product_id.uom_id and uom_root(l.product_uom_id) != uom_root(l.product_id.uom_id))
pairs = {}
for l in cross:
    k = (l.product_uom_id.name, l.product_id.uom_id.name)
    pairs.setdefault(k, set()).add(l.product_id.display_name)
p(f"\n   Total BOM line cross-root: {len(cross)}")
for k, v in sorted(pairs.items()):
    p(f"   line_uom {k[0]} vs prod_uom {k[1]} : {len([l for l in cross if (l.product_uom_id.name, l.product_id.uom_id.name)==k])} lines, komponen: {sorted(v)}")

# apakah konversi g<->ml mungkin? coba _compute_qty
p("\n   Tes konversi core Odoo:")
try:
    grm = env['uom.uom'].search([('name', '=', 'GRM')], limit=1)
    mil = env['uom.uom'].search([('name', '=', 'MIL')], limit=1)
    res = grm._compute_quantity(100, mil, raise_if_failure=False)
    p(f"   100 GRM -> MIL (raise_if_failure=False) = {res}")
except Exception as e:
    p(f"   konversi error: {e}")

# cek stock move konsumsi utk komponen CUKA & MINYAK GORENG (apakah qty/uom konsisten)
p("\n   Sampel stock move konsumsi komponen tsb:")
mv = rows("""
    SELECT sm.id, pt.name->>'en_US' AS prod, sm.product_uom_qty, u.name AS uom, sm.state
    FROM stock_move sm
    JOIN product_product pp ON pp.id=sm.product_id
    JOIN product_template pt ON pt.id=pp.product_tmpl_id
    JOIN uom_uom u ON u.id=sm.product_uom
    WHERE pt.name->>'en_US' IN ('CUKA','MINYAK GORENG') AND sm.state='done'
    ORDER BY sm.id DESC LIMIT 6
""")
for r in mv:
    p(f"   move={r[0]:<7} {r[1][:24]:<24} qty={r[2]:<12} uom={r[3]:<6} state={r[4]}")

# ---------- 2) Non-storable tanpa cost ----------
p("\n=== 2) Non-storable tanpa cost (banding dgn Fase 8 = 37) ===")
prods = env['product.product'].with_context(active_test=False).search([])
ns_nocost = prods.filtered(lambda x: not x.is_storable and not x.standard_price)
p(f"   total: {len(ns_nocost)}")
for x in ns_nocost:
    bom = env['mrp.bom'].search([('product_tmpl_id', '=', x.product_tmpl_id.id)], limit=1)
    bom_s = env['mrp.bom'].search([('product_id', '=', x.id)], limit=1)
    p(f"   id={x.id:<5} active={int(x.active)} tmpl={x.product_tmpl_id.id:<5} {x.display_name[:42]:<42} bom_tmpl={bom.id or '-':<4} bom_prod={bom_s.id or '-'}")
p("DONE cek_cost_uom_detail — read only.")
