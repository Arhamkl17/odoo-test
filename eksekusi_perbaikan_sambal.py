import xmlrpc.client, os, json

url = os.environ["ODOO_URL"]
db = os.environ["ODOO_DB"]
user = os.environ["ODOO_USER"]
password = os.environ["ODOO_PASSWORD"]

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, user, password, {})
print("UID:", uid)

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

CATEG_BAHAN_BAKU_FOOD_ID = 6
UOM_GRM_ID = 134

old_products = {
    453: ("SAMBAL RICA MANADO", 102.79),
    452: ("SAMBAL IJO PADANG", 80.00),
    454: ("SAMBAL KOREK SURABAYA", 102.79),
}

old_ids = list(old_products.keys())
lines_before = models.execute_kw(
    db, uid, password,
    "mrp.bom.line", "search_read",
    [[["product_id", "in", old_ids]]],
    {"fields": ["id", "product_id", "product_qty", "product_uom_id", "bom_id"]}
)
with open("backup_bom_lines_before_fix.json", "w", encoding="utf-8") as f:
    json.dump(lines_before, f, indent=2, ensure_ascii=False)
print(f"Backup {len(lines_before)} baris BOM disimpan ke backup_bom_lines_before_fix.json")

models.execute_kw(
    db, uid, password,
    "product.product", "write",
    [old_ids, {"active": False}]
)
print(f"Produk lama diarsipkan: {old_ids}")

old_to_new = {}
for old_id, (name, price) in old_products.items():
    tmpl_id = models.execute_kw(
        db, uid, password,
        "product.template", "create",
        [{
            "name": name,
            "categ_id": CATEG_BAHAN_BAKU_FOOD_ID,
            "uom_id": UOM_GRM_ID,
            "standard_price": price,
        }]
    )
    tmpl = models.execute_kw(
        db, uid, password,
        "product.template", "read",
        [tmpl_id], {"fields": ["product_variant_id"]}
    )[0]
    new_product_id = tmpl["product_variant_id"][0]
    old_to_new[old_id] = new_product_id
    print(f"Produk baru dibuat: '{name}' template_id={tmpl_id} product_id={new_product_id} price={price}")

updated_count = 0
for line in lines_before:
    old_pid = line["product_id"][0]
    new_pid = old_to_new[old_pid]
    models.execute_kw(
        db, uid, password,
        "mrp.bom.line", "write",
        [[line["id"]], {"product_id": new_pid}]
    )
    updated_count += 1

print(f"Total baris BOM di-update: {updated_count}")

print("\n=== VERIFIKASI PRODUK BARU ===")
new_ids = list(old_to_new.values())
check = models.execute_kw(
    db, uid, password,
    "product.product", "search_read",
    [[["id", "in", new_ids]]],
    {"fields": ["id", "name", "standard_price", "uom_id", "categ_id"]}
)
for p in check:
    uom = p["uom_id"][1] if p.get("uom_id") else "-"
    categ = p["categ_id"][1] if p.get("categ_id") else "-"
    print(f"id={p['id']} name='{p['name']}' price={p['standard_price']} uom={uom} kategori={categ}")

print("\n=== VERIFIKASI BARIS BOM (sample 5) ===")
lines_after = models.execute_kw(
    db, uid, password,
    "mrp.bom.line", "search_read",
    [[["product_id", "in", new_ids]]],
    {"fields": ["id", "product_id", "product_qty", "product_uom_id", "bom_id"], "limit": 5}
)
for l in lines_after:
    bom_name = l["bom_id"][1] if l.get("bom_id") else "-"
    uom = l["product_uom_id"][1] if l.get("product_uom_id") else "-"
    print(f"bom_line_id={l['id']} bom='{bom_name}' product='{l['product_id'][1]}' qty={l['product_qty']} uom={uom}")

print(f"\nTotal baris BOM sekarang menunjuk ke produk baru: {len(models.execute_kw(db, uid, password, 'mrp.bom.line', 'search', [[['product_id', 'in', new_ids]]]))}")

with open("mapping_old_to_new_sambal.json", "w", encoding="utf-8") as f:
    json.dump(old_to_new, f, indent=2)
print("\nMapping id lama->baru disimpan ke mapping_old_to_new_sambal.json")
