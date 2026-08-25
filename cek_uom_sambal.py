import xmlrpc.client, os

url = os.environ["ODOO_URL"]
db = os.environ["ODOO_DB"]
user = os.environ["ODOO_USER"]
password = os.environ["ODOO_PASSWORD"]

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, user, password, {})
print("UID:", uid)

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

target_names = [
    "SAMBAL RICA MANADO",
    "SAMBAL IJO PADANG",
    "SAMBAL KOREK SURABAYA",
    "BUBUK LEMON TEA",
    "MENU SAMBAL RICA MANADO",
    "MENU SAMBAL IJO PADANG",
    "MENU SAMBAL KOREK SURABAYA",
    "LEMON TEA",
]

for name in target_names:
    products = models.execute_kw(
        db, uid, password,
        "product.product", "search_read",
        [[["name", "=", name]]],
        {"fields": ["id", "name", "default_code", "standard_price", "uom_id", "categ_id"]}
    )
    print("-" * 90)
    print(f"Cari: '{name}' -> ditemukan {len(products)} produk")
    for p in products:
        uom = p["uom_id"][1] if p.get("uom_id") else "-"
        categ = p["categ_id"][1] if p.get("categ_id") else "-"
        print(f"  id={p['id']} name='{p['name']}' code={p.get('default_code')} "
              f"price={p['standard_price']} uom(stok)={uom} kategori={categ}")
