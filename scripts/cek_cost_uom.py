# -*- coding: utf-8 -*-
# cek_cost_uom.py — READ-ONLY. Cek kelengkapan UoM utk semua produk (Odoo 19:
# tidak ada lagi uom_category; uom_po_id dihapus — produk hanya punya uom_id).
def p(*a):
    print(*a)

def rows(sql, params=None):
    env.cr.execute(sql, params or ())
    return env.cr.fetchall()

def uom_root(u):
    # ikuti rantai relative_uom_id sampai root
    seen = set()
    while u and u.relative_uom_id and u.id not in seen:
        seen.add(u.id)
        u = u.relative_uom_id
    return u

# ---------- UoM master ----------
n_uom = rows("SELECT COUNT(*) FROM uom_uom")[0][0]
p(f"=== Master UoM: {n_uom} uom (Odoo 19, model relatif) ===")

# ---------- Produk: UoM & cost ----------
prods = env['product.product'].with_context(active_test=False).search([])
no_uom    = prods.filtered(lambda x: not x.uom_id)
with_cost = prods.filtered(lambda x: x.standard_price)

p(f"\n=== Produk (incl arsip): {len(prods)} ===")
p(f"   dgn cost (standard_price>0) : {len(with_cost)}")
p(f"   tanpa uom_id                : {len(no_uom)}")

no_uom_cost = with_cost.filtered(lambda x: not x.uom_id)
p(f"   COST>0 tapi tanpa uom_id    : {len(no_uom_cost)}")
if no_uom:
    p("\n   -- Produk tanpa uom_id --")
    for x in no_uom:
        p(f"   id={x.id:<5} {x.display_name[:48]:<48} cost={x.standard_price} storable={x.is_storable}")
if no_uom_cost:
    p("\n   !! COST>0 TANPA UOM (harus 0) !!")
    for x in no_uom_cost:
        p(f"   id={x.id:<5} {x.display_name[:48]:<48} cost={x.standard_price}")

# ---------- BOM lines ----------
bls = env['mrp.bom.line'].with_context(active_test=False).search([])
bl_no_uom = bls.filtered(lambda l: not l.product_uom_id)
bl_root   = bls.filtered(lambda l: l.product_uom_id and l.product_id.uom_id and uom_root(l.product_uom_id) != uom_root(l.product_id.uom_id))
p(f"\n=== BOM lines: {len(bls)} ===")
p(f"   tanpa product_uom_id        : {len(bl_no_uom)}")
p(f"   root uom != root produk     : {len(bl_root)}")
for l in bl_root[:15]:
    p(f"   bom_line={l.id:<6} {l.product_id.display_name[:36]:<36} line_uom={l.product_uom_id.name} vs prod_uom={l.product_id.uom_id.name}")
for l in bl_no_uom[:15]:
    p(f"   bom_line={l.id:<6} {l.product_id.display_name[:36]:<36} TANPA uom (bom={l.bom_id.display_name[:30]})")

# ---------- Cross-check Fase 8 ----------
storable_cost  = with_cost.filtered(lambda x: x.is_storable)
nonstorb_cost  = with_cost.filtered(lambda x: not x.is_storable)
nonstorb_all   = prods.filtered(lambda x: not x.is_storable)
p(f"\n=== Cross-check Fase 8 ===")
p(f"   storable dgn cost        : {len(storable_cost)}  (harus 99)")
p(f"   non-storable dgn cost    : {len(nonstorb_cost)}  (70 pasca-Fase 10b = 69 + SAOS KEJU)")
p(f"   non-storable tanpa cost  : {len(nonstorb_all) - len(nonstorb_cost)}  (37 = tanpa BoM + item non-menu)")

ok = not no_uom and not no_uom_cost and not bl_no_uom and not bl_root
p(f"\nVERDICT: {'SEMUA UoM LENGKAP ✓' if ok else 'ADA YANG KURANG — lihat daftar di atas'}")
p("DONE cek_cost_uom — read only.")
