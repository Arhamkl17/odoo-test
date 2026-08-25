import xmlrpc.client, os, json

url = os.environ["ODOO_URL"]
db = os.environ["ODOO_DB"]
user = os.environ["ODOO_USER"]
password = os.environ["ODOO_PASSWORD"]

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, user, password, {})
print("UID:", uid)

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

sambal_ids = [453, 452, 454]

lines = models.execute_kw(
    db, uid, password,
    "mrp.bom.line", "search_read",
    [[["product_id", "in", sambal_ids]]],
    {"fields": ["id", "product_id", "product_qty", "product_uom_id", "bom_id"]}
)

print(f"Total baris BOM yang pakai produk ini: {len(lines)}")
print("-" * 90)
for l in lines:
    bom_name = l["bom_id"][1] if l.get("bom_id") else "-"
    uom = l["product_uom_id"][1] if l.get("product_uom_id") else "-"
    print(f"bom_line_id={l['id']:5} bom='{bom_name}' product='{l['product_id'][1]}' "
          f"qty={l['product_qty']} uom={uom}")

with open("backup_bom_lines_sambal.json", "w", encoding="utf-8") as f:
    json.dump(lines, f, indent=2, ensure_ascii=False)
print("\nBackup disimpan ke backup_bom_lines_sambal.json")
