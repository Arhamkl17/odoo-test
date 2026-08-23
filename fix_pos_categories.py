"""
Fix: matikan limit_categories di shop "Restoran" (pos.config id=1).

Root cause (dari check_pos_setup.py): shop "Restoran" punya limit_categories=True
dengan cuma 2 kategori diizinkan, padahal 23 produk menu tersebar di 8 kategori POS.
Efeknya mayoritas produk sengaja disembunyikan Odoo dari layar kasir.

Fix ini mematikan limit_categories sepenuhnya, supaya SEMUA kategori (termasuk
yang baru ditambah nanti) otomatis muncul di kasir tanpa perlu update manual.

Cara pakai:
1. Upload file ini ke repo (root Odoo-mv), lalu git pull di Codespace
2. Jalankan: python3 fix_pos_categories.py
"""

import xmlrpc.client

url = "http://localhost:8069"
db = "Test1"
username = "arhamkamal98@gmail.com"
password = "Lowongan01"

CTX = {
    "tracking_disable": True,
    "mail_create_nolog": True,
    "mail_create_nosubscribe": True,
    "mail_notrack": True,
}

SHOP_NAME = "Restoran"


def main():
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, password, {})
    if not uid:
        print("❌ Login gagal, cek username/password/db")
        return
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    def execute(model, method, *args, context=None):
        kwargs = {"context": context} if context is not None else {}
        return models.execute_kw(db, uid, password, model, method, list(args), kwargs)

    shop_ids = execute("pos.config", "search", [["name", "=", SHOP_NAME], ["active", "=", True]])
    if not shop_ids:
        print(f"❌ Shop aktif bernama '{SHOP_NAME}' tidak ditemukan. Cek ulang nama shop-nya.")
        return

    shop_id = shop_ids[0]

    before = execute("pos.config", "read", [shop_id], ["limit_categories", "iface_available_categ_ids"])[0]
    print(f"Sebelum: limit_categories={before['limit_categories']}, jumlah kategori dibatasi={len(before['iface_available_categ_ids'])}")

    execute(
        "pos.config", "write", [shop_id],
        {"limit_categories": False, "iface_available_categ_ids": [(5, 0, 0)]},
        context=CTX,
    )

    after = execute("pos.config", "read", [shop_id], ["limit_categories", "iface_available_categ_ids"])[0]
    print(f"Sesudah: limit_categories={after['limit_categories']}, jumlah kategori dibatasi={len(after['iface_available_categ_ids'])}")

    if not after["limit_categories"]:
        print(f"\n✅ Berhasil! Shop '{SHOP_NAME}' sekarang menampilkan SEMUA kategori POS di kasir.")
        print("   Refresh/muat ulang halaman kasir POS untuk melihat perubahannya.")
    else:
        print("\n⚠️  limit_categories masih True, ada yang perlu dicek manual.")


if __name__ == "__main__":
    main()
