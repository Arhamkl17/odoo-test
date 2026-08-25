import xmlrpc.client, os

url = os.environ["ODOO_URL"]
db = os.environ["ODOO_DB"]
user = os.environ["ODOO_USER"]
password = os.environ["ODOO_PASSWORD"]

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, user, password, {})
print("UID:", uid)

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

CATEG_BAHAN_BAKU_FOOD_ID = 6

uom_grm = models.execute_kw(
    db, uid, password,
    "uom.uom", "search_read",
    [[["name", "=", "GRM"]]],
    {"fields": ["id", "name"]}
)
if not uom_grm:
    raise SystemExit("UoM 'GRM' tidak ditemukan, cek nama persisnya dulu.")
uom_grm_id = uom_grm[0]["id"]
print(f"UoM GRM id = {uom_grm_id}")

updates = {
    453: 102.79,
    452: 80.00,
    454: 102.79,
}

for pid, price in updates.items():
    result = models.execute_kw(
        db, uid, password,
        "product.product", "write",
        [[pid], {
            "categ_id": CATEG_BAHAN_BAKU_FOOD_ID,
            "uom_id": uom_grm_id,
            "standard_price": price,
        }]
    )
    print(f"Update id={pid} -> categ=Bahan Baku Food, uom=GRM, price={price} | result={result}")

print("\nVerifikasi ulang:")
check = models.execute_kw(
    db, uid, password,
    "product.product", "search_read",
    [[["id", "in", list(updates.keys())]]],
    {"fields": ["id", "name", "standard_price", "uom_id", "categ_id"]}
)
for p in check:
    uom = p["uom_id"][1] if p.get("uom_id") else "-"
    categ = p["categ_id"][1] if p.get("categ_id") else "-"
    print(f"id={p['id']} name='{p['name']}' price={p['standard_price']} uom={uom} kategori={categ}")
