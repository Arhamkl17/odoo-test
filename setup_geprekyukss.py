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

MENU_NAMES = [item[0] for item in MENU_DATA]

print("Menghubungkan ke Odoo...")
common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common")
uid = common.authenticate(DB, USERNAME, PASSWORD, {})

if not uid:
    print("GAGAL LOGIN. Cek lagi USERNAME dan PASSWORD di bagian CONFIG.")
    exit(1)

print(f"Login berhasil, uid: {uid}")
models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object")


def execute(model, method, *args):
    return models.execute_kw(DB, uid, PASSWORD, model, method, list(args))


print("\n[1/4] Menghapus produk demo (furniture)...")
all_products = execute("product.template", "search", [])
print(f"Ditemukan {len(all_products)} produk. Menghapus semua...")

deleted = 0
skipped = 0
for pid in all_products:
    try:
        execute("product.template", "unlink", [pid])
        deleted += 1
    except Exception as e:
        skipped += 1

print(f"Berhasil hapus: {deleted}, gagal/skip: {skipped}")


print("\n[2/4] Menghapus shop yang salah ke-create...")
wrong_shops = execute("pos.config", "search", [["name", "in", MENU_NAMES]])
print(f"Ditemukan {len(wrong_shops)} shop salah dari nama menu.")

if wrong_shops:
    try:
        execute("pos.config", "unlink", wrong_shops)
        print(f"Berhasil hapus {len(wrong_shops)} shop.")
    except Exception as e:
        print(f"Gagal hapus sebagian/semua shop: {e}")
        print("Coba hapus manual dari Konfigurasi > Point of Sale kalau masih ada sisa.")
else:
    print("Tidak ada shop yang perlu dihapus (mungkin sudah dihapus manual).")


print("\n[3/4] Membuat kategori POS...")
categories = list(set(item[2] for item in MENU_DATA))
category_ids = {}

for cat_name in categories:
    existing = execute("pos.category", "search", [["name", "=", cat_name]])
    if existing:
        category_ids[cat_name] = existing[0]
        print(f"Kategori '{cat_name}' sudah ada.")
    else:
        new_id = execute("pos.category", "create", [{"name": cat_name}])
        category_ids[cat_name] = new_id
        print(f"Kategori '{cat_name}' dibuat baru.")


print("\n[4/4] Membuat produk menu geprekyukss...")
created = 0
for name, price, cat_name in MENU_DATA:
    try:
        product_id = execute("product.template", "create", [{
            "name": name,
            "list_price": price,
            "available_in_pos": True,
            "sale_ok": True,
            "pos_categ_ids": [(6, 0, [category_ids[cat_name]])],
            "type": "consu",
        }])
        created += 1
        print(f"  OK: {name} - Rp{price}")
    except Exception as e:
        print(f"  GAGAL: {name} - {e}")

print(f"\nSELESAI. Total produk berhasil dibuat: {created}/{len(MENU_DATA)}")
