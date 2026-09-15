# -*- coding: utf-8 -*-
"""READ-ONLY recon BOM: struktur resep Agustus + 27 menu tanpa BOM."""
from collections import Counter, defaultdict

AUG_FROM, AUG_TO = "2026-08-01", "2026-09-01"
Bom = env["mrp.bom"]
Prod = env["product.product"]
POSm = env["pos.order"]

aug = POSm.search([("date_order", ">=", AUG_FROM), ("date_order", "<", AUG_TO)])
sold = Counter()
for o in aug:
    for l in o.lines:
        sold[l.product_id.id] += l.qty

boms = Bom.search([])
print("=" * 78)
print("A. BOM yg ADA: %d header, %d baris" % (
    len(boms), env["mrp.bom.line"].search_count([])))
print("   type:", Counter(b.type for b in boms))
comp_of = defaultdict(list)
for b in boms:
    comp_of[b.product_tmpl_id.product_variant_ids[0].id] = [
        (l.product_id.display_name, l.product_qty, l.product_uom_id.name) for l in b.bom_line_ids]
for pid, q in sold.most_common():
    p = Prod.browse(pid)
    if pid in comp_of:
        print("   %-44s qty=%-5s -> %s" % (
            p.display_name[:44], q,
            " + ".join("%s×%g" % (n[:26], qq) for n, qq, _ in comp_of[pid])))

print()
print("=" * 78)
print("B. 27 MENU TANPA BOM")
nobom = []
for pid, q in sold.most_common():
    p = Prod.browse(pid)
    if not Bom.search_count([("product_tmpl_id", "=", p.product_tmpl_id.id)]):
        nobom.append(p)
for p in nobom:
    print("   id=%-5s %-46s qty=%-5s categ=%-14s price=%s" % (
        p.id, p.display_name[:46], sold[p.id], (p.categ_id.name or "")[:14],
        "{:,.0f}".format(p.list_price or 0)))

print()
print("=" * 78)
print("C. KOMPONEN yang sudah dipakai di BOM (kandidat bahan)")
used = Counter()
for b in boms:
    for l in b.bom_line_ids:
        used[l.product_id.id] += 1
for pid, n in used.most_common():
    p = Prod.browse(pid)
    print("   id=%-5s %-40s dipakai_di=%-4s onhand=%s uom=%s" % (
        pid, p.display_name[:40], n, p.qty_available, p.uom_id.name))

print()
print("=" * 78)
print("D. SEMUA produk yg BUKAN menu (kandidat bahan mentah)")
menucat = set()
for p in Prod.search([("available_in_pos", "=", True)]):
    menucat.add(p.categ_id.name)
print("   kategori menu:", sorted(menucat))
other = Prod.search([("available_in_pos", "=", False)])
print("   produk tidak dijual di POS: %d" % len(other))
for c, n in Counter(p.categ_id.name for p in other).most_common():
    print("      %-34s %d" % ((c or "-")[:34], n))
print("   --- daftar (50 pertama) ---")
for p in other[:50]:
    print("      id=%-5s %-42s categ=%-20s uom=%s" % (
        p.id, p.display_name[:42], (p.categ_id.name or "")[:20], p.uom_id.name))

print()
print("=" * 78)
print("E. Menu yg punya BOM tapi JUGA punya baris bahan langsung? (cek tipe BOM)")
print("   normal:", sum(1 for b in boms if b.type == "normal"),
      "| phantom:", sum(1 for b in boms if b.type == "phantom"))
print("   kategori produk menu:", Counter(
    (Prod.browse(pid).categ_id.name or "-") for pid in sold).most_common())
env.cr.rollback()
