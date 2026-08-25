import xmlrpc.client, os

url = os.environ["ODOO_URL"]
db = os.environ["ODOO_DB"]
user = os.environ["ODOO_USER"]
password = os.environ["ODOO_PASSWORD"]

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, user, password, {})
print("UID:", uid)

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

check_names = [
    "TEPUNG MIX GEYUKSSS",
    "MINYAK PADAT",
    "MINYAK GORENG",
    "BUMBU MARINASI",
    "BUMBU C",
    "GARAM HALUS",
    "TEH MIX",
    "BUBUK BBQ",
    "BUBUK KEJU",
]

for name in check_names:
    products = models.execute_kw(
        db, uid, password,
        "product.product", "search_read",
        [[["name", "=", name]]],
        {"fields": ["id", "name", "standard_price", "uom_id", "categ_id"]}
    )
    for p in products:
        uom = p["uom_id"][1] if p.get("uom_id") else "-"
        categ = p["categ_id"][1] if p.get("categ_id") else "-"
        print(f"id={p['id']:5} name='{p['name']:25}' uom={uom:8} kategori={categ}")
