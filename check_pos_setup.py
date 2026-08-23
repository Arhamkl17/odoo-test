"""
Diagnostik kenapa produk tidak muncul di layar kasir POS.

Cek via XML-RPC:
1. Semua pos.config (shop) yang ada — nama, active/archived, limit kategori
2. 23 produk menu geprekyukss — apakah available_in_pos=True, pos_categ_ids terisi
3. Semua pos.category yang ada di database

Cara pakai:
1. Upload file ini ke repo (root Odoo-mv), lalu git pull di Codespace
2. Jalankan: python3 check_pos_setup.py
"""

import xmlrpc.client

url = "http://localhost:8069"
db = "Test1"
username = "arhamkamal98@gmail.com"
password = "Lowongan01"

# Nama 23 menu geprekyukss (buat cek satu-satu)
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

    # 1. Cek semua pos.config (shop), termasuk yang archived
    print("=" * 60)
    print("1. DAFTAR SHOP (pos.config)")
    print("=" * 60)
    shop_ids = execute("pos.config", "search", [], context={"active_test": False})
    shops = execute(
        "pos.config", "read", shop_ids,
        ["name", "active", "limit_categories", "iface_available_categ_ids"],
    )
    for s in shops:
        status = "AKTIF" if s["active"] else "ARCHIVED"
        limited = "YA" if s.get("limit_categories") else "TIDAK"
        categ_ids = s.get("iface_available_categ_ids", [])
        print(f"  [{status}] id={s['id']} | {s['name']} | limit_categories={limited} | jumlah kategori dibatasi={len(categ_ids)}")

    # 2. Cek semua pos.category
    print("\n" + "=" * 60)
    print("2. DAFTAR KATEGORI POS (pos.category)")
    print("=" * 60)
    categ_ids_all = execute("pos.category", "search", [])
    categs = execute("pos.category", "read", categ_ids_all, ["name"])
    for c in categs:
        print(f"  id={c['id']} | {c['name']}")

    # 3. Cek tiap produk menu: available_in_pos, pos_categ_ids, sale_ok, active
    print("\n" + "=" * 60)
    print("3. STATUS 23 PRODUK MENU")
    print("=" * 60)
    missing, not_available, no_categ, ok = [], [], [], []
    for name in MENU_NAMES:
        tmpl_ids = execute("product.template", "search", [["name", "=", name]], context={"active_test": False})
        if not tmpl_ids:
            missing.append(name)
            print(f"  ❌ TIDAK DITEMUKAN: {name}")
            continue
        tmpl = execute(
            "product.template", "read", tmpl_ids,
            ["active", "sale_ok", "available_in_pos", "pos_categ_ids"],
        )[0]
        flags = []
        if not tmpl["active"]:
            flags.append("ARCHIVED")
        if not tmpl["sale_ok"]:
            flags.append("sale_ok=False")
        if not tmpl["available_in_pos"]:
            flags.append("available_in_pos=False")
            not_available.append(name)
        if not tmpl["pos_categ_ids"]:
            flags.append("TANPA KATEGORI POS")
            no_categ.append(name)
        if flags:
            print(f"  ⚠️  {name} -> {', '.join(flags)}")
        else:
            ok.append(name)
            print(f"  ✅ {name}")

    # Ringkasan
    print("\n" + "=" * 60)
    print("RINGKASAN")
    print("=" * 60)
    print(f"OK (harusnya muncul di kasir): {len(ok)}/{len(MENU_NAMES)}")
    if missing:
        print(f"\n❌ Tidak ditemukan sama sekali ({len(missing)}):")
        for m in missing:
            print(f"  - {m}")
    if not_available:
        print(f"\n⚠️  available_in_pos=False ({len(not_available)}) -> INI KEMUNGKINAN BESAR PENYEBAB PRODUK TIDAK MUNCUL:")
        for m in not_available:
            print(f"  - {m}")
    if no_categ:
        print(f"\n⚠️  Tidak ada kategori POS ({len(no_categ)}):")
        for m in no_categ:
            print(f"  - {m}")


if __name__ == "__main__":
    main()
