#!/usr/bin/env python3
import xmlrpc.client

URL = "http://localhost:8069"
DB = "Test1"
USERNAME = "arhamkamal98@gmail.com"
PASSWORD = "Lowongan01"

MENU_DATA = [
    ("Ayam Geprek Indomie + Pilih Sambal + Gratis Es Teh", 20000, "Paket Geprek Recomended"),
    ("Ayam Crispy Dada/Paha Atas + Nasi + Gratis Es Teh", 18000, "Paket Crispy"),
    ("Ayam Crispy Sayap/Paha Bawah + Nasi + Gratis Es Teh", 16000, "Paket Crispy"),
    ("Ayam Crispy Dada/Paha Atas + Indomie Goreng", 18000, "Paket Indomie Crispy"),
    ("Ayam Crispy Paha Bawah/Sayap + Indomie Goreng", 17000, "Paket Indomie Crispy"),
    ("Ayam Geprek Original + Nasi + Gratis Es Teh", 19000, "Paket Geprek Sambal"),
    ("Ayam Geprek Sambal Korek Surabaya + Nasi + Gratis Es Teh", 19000, "Paket Geprek Sambal"),
    ("Ayam Geprek Sambal Rica Manado + Nasi + Gratis Es Teh", 19000, "Paket Geprek Sambal"),
    ("Single Ayam Geprek Original Dada/Paha Atas + Gratis Nasi", 16000, "Single Ayam"),
    ("Single Ayam Geprek Sayap/Paha Bawah + Gratis Nasi", 13500, "Single Ayam"),
    ("Single Ayam Geprek Sambal Korek Surabaya + Gratis Nasi", 17000, "Single Ayam"),
    ("Single Ayam Geprek Sambal Rica Manado + Gratis Nasi", 17000, "Single Ayam"),
    ("Single Ayam Geprek Andalan + Gratis Nasi", 19000, "Single Ayam"),
    ("Single Ayam Crispy Dada/Paha Atas + Gratis Nasi", 14500, "Single Ayam"),
    ("Single Ayam Crispy Paha Bawah/Sayap + Gratis Nasi", 12500, "Single Ayam"),
    ("Es Teh", 4500, "Minuman"),
    ("Air Mineral", 5500, "Minuman"),
    ("Ice Chocolate", 7000, "Minuman"),
    ("Orange", 4500, "Minuman"),
    ("Lemon Tea", 10000, "Minuman"),
    ("Sambal Rica Manado", 3500, "Sambal"),
    ("Sambal Korek Surabaya", 3500, "Sambal"),
    ("Tambahan Nasi", 5500, "Add On"),
]

CATEGORY_IDS = {
    "Add On": 13, "Sambal": 9, "Paket Geprek Sambal": 12, "Minuman": 8,
    "Paket Indomie Crispy": 11, "Paket Geprek Recomended": 7,
    "Single Ayam": 6, "Paket Crispy": 10,
}

CONTEXT = {
    "tracking_disable": True,
    "mail_create_nolog": True,
    "mail_create_nosubscribe": True,
    "mail_notrack": True,
}

common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common")
uid = common.authenticate(DB, USERNAME, PASSWORD, {})
models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object")

def execute_ctx(model, method, args_list, kwargs=None):
    kw = kwargs or {}
    kw["context"] = CONTEXT
    return models.execute_kw(DB, uid, PASSWORD, model, method, args_list, kw)

print("Membuat 23 produk dengan context tracking_disable...")
created = 0
product_ids = {}
for name, price, cat_name in MENU_DATA:
    try:
        pid = execute_ctx("product.template", "create", [{
            "name": name,
            "list_price": price,
            "available_in_pos": True,
            "sale_ok": True,
            "type": "consu",
        }])
        product_ids[pid] = cat_name
        created += 1
        print(f"  OK: {name} (id {pid})")
    except Exception as e:
        print(f"  GAGAL: {name} - {e}")

print(f"\nTotal berhasil dibuat: {created}/{len(MENU_DATA)}")

print("\nAssign kategori...")
assigned = 0
for pid, cat_name in product_ids.items():
    try:
        execute_ctx("product.template", "write", [pid, {
            "pos_categ_ids": [(6, 0, [CATEGORY_IDS[cat_name]])]
        }])
        assigned += 1
    except Exception as e:
        print(f"  GAGAL assign kategori id {pid}: {e}")

print(f"Kategori berhasil di-assign: {assigned}/{created}")
print("\nSELESAI.")
