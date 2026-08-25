import xmlrpc.client, os, json

url = os.environ["ODOO_URL"]
db = os.environ["ODOO_DB"]
user = os.environ["ODOO_USER"]
password = os.environ["ODOO_PASSWORD"]

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, user, password, {})
print("UID:", uid)

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

products = models.execute_kw(
    db, uid, password,
    "product.product", "search_read",
    [[]],
    {"fields": ["id", "name", "default_code", "standard_price", "uom_id"], "limit": 1000}
)

print(f"Total produk di Odoo: {len(products)}")
print("-" * 90)
for p in sorted(products, key=lambda x: x["name"]):
    code = p.get("default_code") or "-"
    uom = p["uom_id"][1] if p["uom_id"] else "-"
    print(f"{code:20} {p['name']:40} price={p['standard_price']:>10} uom={uom}")

with open("odoo_products_export.json", "w", encoding="utf-8") as f:
    json.dump(products, f, indent=2, ensure_ascii=False)

print("\nDisimpan ke odoo_products_export.json")
