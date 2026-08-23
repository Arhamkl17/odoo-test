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

common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common")
uid = common.authenticate(DB, USERNAME, PASSWORD, {})
models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object")

def execute(model, method, *args):
    return models.execute_kw(DB, uid, PASSWORD, model, method, list(args))

# STEP 1: Hapus semua produk test & demo (coba delete, kalau gagal archive)
print("[1/4] Membersihkan produk lama (test & demo)...")
all_products = execute("product.template", "search", [])
del_count = 0
archive_count = 0
for pid in all_products:
    try:
        execute("product.template", "unlink", [pid])
        del_count += 1
    except Exception:
        try:
            execute("product.template", "write", [pid], {"active": False})
            archive_count += 1
        except Exception:
            pass
print(f"Dihapus: {del_count}, di-archive: {archive_count}")

# STEP 2: Buat kategori POS
print("\n[2/4] Membuat kategori POS...")
categories = list(set(item[2] for item in MENU_DATA))
category_ids = {}
for cat_name in categories:
    existing = execute("pos.category", "search", [["name", "=", cat_name]])
    if existing:
        category_ids[cat_name] = existing[0]
    else:
        category_ids[cat_name] = execute("pos.category", "create", [{"name": cat_name}])
    print(f"  Kategori '{cat_name}' -> id {category_ids[cat_name]}")

# STEP 3: Buat produk TANPA kategori dulu
print("\n[3/4] Membuat 23 produk (tanpa kategori dulu)...")
product_ids = {}
created = 0
for name, price, cat_name in MENU_DATA:
    try:
        pid = execute("product.template", "create", [{
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

print(f"\nTotal produk berhasil dibuat: {created}/{len(MENU_DATA)}")

# STEP 4: Assign kategori satu per satu pakai write (terpisah dari create)
print("\n[4/4] Assign kategori POS ke tiap produk...")
assigned = 0
for pid, cat_name in product_ids.items():
    try:
        execute("product.template", "write", [pid], {
            "pos_categ_ids": [(6, 0, [category_ids[cat_name]])]
        })
        assigned += 1
    except Exception as e:
        print(f"  GAGAL assign kategori untuk id {pid}: {e}")

print(f"Kategori berhasil di-assign ke: {assigned}/{created} produk")
print("\nSELESAI SEMUA.")
