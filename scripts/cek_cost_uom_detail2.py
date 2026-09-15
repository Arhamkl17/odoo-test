# -*- coding: utf-8 -*-
# cek_cost_uom_detail2.py — READ-ONLY. Lanjutan: (a) qty BOM line cross-root,
# (b) TAHU/TEMPE PTG vs GRM, (c) daftar non-storable tanpa cost (38 vs 37 Fase 8).
def p(*a):
    print(*a)

def rows(sql, params=None):
    env.cr.execute(sql, params or ())
    return env.cr.fetchall()

# ---------- (a) Detail BOM line cross-root ----------
p("=== (a) BOM line cross-root: qty, uom line vs uom produk, cost produk ===")
bls = env['mrp.bom.line'].with_context(active_test=False).search([])

def uom_root(u):
    seen = set()
    while u and u.relative_uom_id and u.id not in seen:
        seen.add(u.id)
        u = u.relative_uom_id
    return u

cross = bls.filtered(lambda l: l.product_uom_id and l.product_id.uom_id and uom_root(l.product_uom_id) != uom_root(l.product_id.uom_id))
for l in cross[:12]:
    pr = l.product_id
    p(f"   line={l.id:<5} {pr.display_name[:20]:<20} qty={l.product_qty:<10} uom_line={l.product_uom_id.name:<5} uom_prod={pr.uom_id.name:<5} cost={pr.standard_price:>10,.2f} (per {pr.uom_id.name})")
p(f"   ... total {len(cross)} lines")

# distribusi qty per komponen utk CUKA/MINYAK (GRM di line, dipakai sbg MIL?)
p("\n   Range qty line GRM (dibaca core sebagai MIL saat konsumsi):")
for nm in ("CUKA", "MINYAK GORENG"):
    qs = [l.product_qty for l in cross if l.product_id.display_name == nm and l.product_uom_id.name == "GRM"]
    if qs:
        p(f"   {nm:<14} n={len(qs):<3} min={min(qs):<10.2f} max={max(qs):<10.2f} sum={sum(qs):,.2f}")

# ---------- (b) TAHU/TEMPE ----------
p("\n=== (b) TAHU/TEMPE: PTG vs GRM ===")
for nm in ("TAHU", "TEMPE"):
    pr = env['product.product'].with_context(active_test=False).search([('display_name', '=', nm)], limit=1)
    if not pr:
        pr = env['product.product'].with_context(active_test=False).search([('display_name', 'ilike', nm)], limit=1)
    if pr:
        mv = rows("""
            SELECT COALESCE(SUM(sm.product_uom_qty),0), u.name->>'en_US'
            FROM stock_move sm JOIN uom_uom u ON u.id=sm.product_uom
            WHERE sm.product_id=%s AND sm.state='done' GROUP BY u.name->>'en_US'
        """, (pr.id,))
        p(f"   {nm}: id={pr.id} uom_prod={pr.uom_id.name} cost={pr.standard_price} | konsumsi done per uom: {[(r[1], float(r[0])) for r in mv]}")
        lines = cross.filtered(lambda l: l.product_id.id == pr.id)
        for l in lines[:4]:
            p(f"      bom_line={l.id} qty={l.product_qty} uom_line={l.product_uom_id.name} (bom {l.bom_id.display_name[:30]})")

# ---------- (c) Non-storable tanpa cost ----------
p("\n=== (c) Non-storable tanpa cost (banding dgn Fase 8 = 37) ===")
prods = env['product.product'].with_context(active_test=False).search([])
ns_nocost = prods.filtered(lambda x: not x.is_storable and not x.standard_price)
p(f"   total: {len(ns_nocost)}")
for x in ns_nocost:
    bom = env['mrp.bom'].with_context(active_test=False).search([('product_tmpl_id', '=', x.product_tmpl_id.id)], limit=1)
    has_lines = bool(bom and bom.bom_line_ids)
    sold = rows("SELECT COUNT(*) FROM pos_order_line pol WHERE pol.product_id=%s", (x.id,))[0][0]
    p(f"   id={x.id:<5} active={int(x.active)} {x.display_name[:40]:<40} bom={bom.id or '-':<5} lines={int(has_lines)} sold={sold}")
p("DONE cek_cost_uom_detail2 — read only.")
