#!/usr/bin/env python3
import xmlrpc.client

URL = "http://localhost:8069"
DB = "Test1"
USERNAME = "arhamkamal98@gmail.com"
PASSWORD = "Lowongan01"

MENU_NAMES = [
    "Ayam Geprek Indomie + Pilih Sambal + Gratis Es Teh",
    "Ayam Crispy Dada/Paha Atas + Nasi + Gratis Es Teh",
    "Ayam Crispy Sayap/Paha Bawah + Nasi + Gratis Es Teh",
    "Ayam Crispy Dada/Paha Atas + Indomie Goreng",
    "Ayam Crispy Paha Bawah/Sayap + Indomie Goreng",
    "Ayam Geprek Original + Nasi + Gratis Es Teh",
    "Ayam Geprek Sambal Korek Surabaya + Nasi + Gratis Es Teh",
    "Ayam Geprek Sambal Rica Manado + Nasi + Gratis Es Teh",
    "Single Ayam Geprek Original Dada/Paha Atas + Gratis Nasi",
    "Single Ayam Geprek Sayap/Paha Bawah + Gratis Nasi",
    "Single Ayam Geprek Sambal Korek Surabaya + Gratis Nasi",
    "Single Ayam Geprek Sambal Rica Manado + Gratis Nasi",
    "Single Ayam Geprek Andalan + Gratis Nasi",
    "Single Ayam Crispy Dada/Paha Atas + Gratis Nasi",
    "Single Ayam Crispy Paha Bawah/Sayap + Gratis Nasi",
    "Es Teh",
    "Air Mineral",
    "Ice Chocolate",
    "Orange",
    "Lemon Tea",
    "Sambal Rica Manado",
    "Sambal Korek Surabaya",
    "Tambahan Nasi",
]

common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common")
uid = common.authenticate(DB, USERNAME, PASSWORD, {})
models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object")


def execute(model, method, *args):
    return models.execute_kw(DB, uid, PASSWORD, model, method, list(args))


wrong_shops = execute("pos.config", "search", [["name", "in", MENU_NAMES]])
print(f"Ditemukan {len(wrong_shops)} shop salah.")

# Tutup paksa sesi kasir yang masih nyangkut
sessions = execute("pos.session", "search", [["config_id", "in", wrong_shops]])
print(f"Ditemukan {len(sessions)} sesi kasir yang nyangkut, mencoba tutup/hapus...")

for sid in sessions:
    try:
        execute("pos.session", "write", [sid], {"state": "closed"})
    except Exception as e:
        pass
    try:
        execute("pos.session", "unlink", [sid])
    except Exception as e:
        print(f"  Sesi {sid} tidak bisa dihapus: {e}")

# Hapus shop satu per satu
deleted = 0
failed = 0
for shop_id in wrong_shops:
    try:
        execute("pos.config", "unlink", [shop_id])
        deleted += 1
    except Exception as e:
        failed += 1
        print(f"  GAGAL hapus shop id {shop_id}: {e}")

print(f"\nSELESAI. Berhasil hapus: {deleted}, gagal: {failed}")
