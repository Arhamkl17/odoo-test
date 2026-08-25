import xmlrpc.client, os

url = os.environ["ODOO_URL"]
db = os.environ["ODOO_DB"]
user = os.environ["ODOO_USER"]
password = os.environ["ODOO_PASSWORD"]

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, user, password, {})
print("UID:", uid)

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# id produk (product.product) -> harga per satuan kecil, sudah divalidasi cocok nama & uom
# (Ayam Cut 2 sengaja TIDAK dimasukkan, masih perlu klarifikasi konversi ekor->potong)
updates = {
    447: 3491.8111,  # Ayam Cut 9
    448: 19309.32,  # Ayam Cut 2 (38618.63 per ekor / 2 potong, dikonfirmasi user)
    461: 28.0,  # Kulit Ayam
    458: 20.0,  # Tepung Mix Geyuksss
    473: 34.7826,  # Teh Mix
    443: 82.0,  # Bumbu Marinasi
    632: 40.0,  # Bumbu C
    442: 15.3,  # Beras
    460: 27.8267,  # Minyak Padat
    459: 23.3333,  # Minyak Goreng
    450: 89.0,  # Bubuk Bbq
    444: 12.8,  # Garam Halus
    445: 29.2308,  # Cuka
    446: 57.0,  # Saos Tiram
    455: 86.5385,  # Santan Sasa
    462: 33.0,  # Kecap ABC
    463: 3000.0,  # Indomie Goreng
    467: 37.0,  # Bihun
    474: 20.0,  # Gula Pasir
    466: 133.3333,  # Keju Mozarella
    465: 73.3333,  # Keju Parut
    456: 260.0,  # Saos Saset Cabe
    457: 260.0,  # Saos Saset Tomat
    468: 9.1935,  # Big Cola
    469: 8.3333,  # Bubuk Oranges
    471: 114.5833,  # Bubuk Milo
    637: 1541.6667,  # Air Mineral Botol
    476: 21.3333,  # Alas Nasi Bundar
    477: 127.5,  # Garpu Plastik
    478: 217.0,  # Gelas 14 OZ
    636: 700.0,  # Gelas 22 OZ
    479: 110.0,  # Kantong Gelas 1
    480: 134.0,  # Kantong Gelas 2
    481: 1070.0,  # Kemasan Geprek Yuksss
    482: 2050.0,  # Kemasan Segepok (Biasa)
    484: 196.0,  # Pembungkus Nasi Putih
    485: 34.7222,  # Pipet
    486: 5.1,  # Plastik Klip 5X8
    487: 44.8,  # Plastik Putih Takeaway Uk. 15
    488: 22.9,  # Plastik Putih Takeaway Uk. 24
    489: 315.0,  # Plastik Putih Takeaway Uk. 28
    490: 272.0,  # Plastik Segepok
    491: 88000.0,  # Roll Cup Press
    492: 125.0,  # Sendok Plastik
    493: 58.3333,  # Tray Sambal
    494: 210.8333,  # Thinwall Sauce 25 Ml
    495: 248.3333,  # Thinwall Sauce 35 Ml
    496: 166.6667,  # Kertas Nasi Kuning
    497: 120000.0,  # Alat Refill Gas Portable
    505: 100000.0,  # Baju Seragam GY
    506: 100000.0,  # Apron Kain GY
    508: 35000.0,  # Topi GY
    509: 100000.0,  # Regulator Deep Fryer
    510: 95000.0,  # Regulator High Pressure
    511: 47500.0,  # Pemantik Portable
    498: 46800.0,  # Piring Rotan
    499: 24100.0,  # Gelas Dine In
    512: 22500.0,  # Penjepit Ayam
    513: 50000.0,  # Saringan Teh
    514: 60000.0,  # Saringan Tepung
    516: 35500.0,  # Timer Digital
    523: 35000.0,  # Lampu Etalase
    517: 3666.67,  # Lakban Bening
    500: 13200.0,  # Roll Kasir Besar
    501: 2100.0,  # Roll Kasir Kecil
    502: 4500.0,  # Roll Kasir Sedang
    503: 110.0,  # Sarung Tangan Plastik
}

print(f"Total item yang akan diupdate: {len(updates)}")  # sekarang 67 item
success = 0
failed = []
for pid, price in updates.items():
    try:
        models.execute_kw(
            db, uid, password,
            "product.product", "write",
            [[pid], {"standard_price": price}]
        )
        success += 1
    except Exception as e:
        failed.append((pid, str(e)))

print(f"Berhasil update: {success}")
if failed:
    print(f"Gagal: {len(failed)}")
    for pid, err in failed:
        print(f"  id={pid}: {err}")

# Verifikasi sample
print("\n=== VERIFIKASI SAMPLE (5 produk) ===")
sample_ids = list(updates.keys())[:5]
check = models.execute_kw(
    db, uid, password,
    "product.product", "search_read",
    [[["id", "in", sample_ids]]],
    {"fields": ["id", "name", "standard_price"]}
)
for p in check:
    print(f"id={p['id']} name='{p['name']}' price={p['standard_price']}")
