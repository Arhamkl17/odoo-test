import xmlrpc.client, os

url = os.environ["ODOO_URL"]
db = os.environ["ODOO_DB"]
user = os.environ["ODOO_USER"]
password = os.environ["ODOO_PASSWORD"]

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, user, password, {})
print("UID:", uid)

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

categs = models.execute_kw(
    db, uid, password,
    "product.category", "search_read",
    [[]],
    {"fields": ["id", "name", "complete_name"]}
)

print(f"Total kategori: {len(categs)}")
print("-" * 60)
for c in sorted(categs, key=lambda x: x["complete_name"]):
    print(f"id={c['id']:5} {c['complete_name']}")
