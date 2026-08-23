"""
Setup 23 BoM (Bill of Materials) untuk Geprekyukss di Odoo via XML-RPC.

Menghubungkan tiap menu jadi (product.template, sudah dibuat lewat
final_setup2.py) ke bahan baku (product.template, sudah dibuat lewat
setup_bahan_baku.py) dengan takaran per porsi.

⚠️ SEMUA TAKARAN DI BAWAH INI PLACEHOLDER/PERKIRAAN, BUKAN RESEP ASLI.
Setelah script jalan, cek & edit manual di GUI:
Manufacturing → Products → Bills of Materials, kalau perlu koreksi takaran.

Cara pakai:
1. Pastikan modul "Manufacturing" sudah di-Install lewat Apps (manual di GUI)
2. Upload file ini ke repo (root Odoo-mv), lalu git pull di Codespace
3. Jalankan: python3 setup_bom.py
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

# (nama_produk_jadi, [(nama_bahan_baku, qty_per_porsi), ...])
BOM_DATA = [
    ("Ayam Geprek Indomie + Pilih Sambal + Gratis Es Teh", [
        ("Ayam Dada/Paha Atas (mentah)", 1),
        ("Indomie Goreng", 1),
        ("Bumbu Sambal Original", 30),
        ("Teh Celup/Bubuk", 5),
        ("Gula", 15),
        ("Es Batu", 50),
    ]),
    ("Ayam Crispy Dada/Paha Atas + Nasi + Gratis Es Teh", [
        ("Ayam Dada/Paha Atas (mentah)", 1),
        ("Tepung Crispy", 50),
        ("Minyak Goreng", 30),
        ("Beras", 150),
        ("Teh Celup/Bubuk", 5),
        ("Gula", 15),
        ("Es Batu", 50),
    ]),
    ("Ayam Crispy Sayap/Paha Bawah + Nasi + Gratis Es Teh", [
        ("Ayam Sayap/Paha Bawah (mentah)", 1),
        ("Tepung Crispy", 50),
        ("Minyak Goreng", 30),
        ("Beras", 150),
        ("Teh Celup/Bubuk", 5),
        ("Gula", 15),
        ("Es Batu", 50),
    ]),
    ("Ayam Crispy Dada/Paha Atas + Indomie Goreng", [
        ("Ayam Dada/Paha Atas (mentah)", 1),
        ("Tepung Crispy", 50),
        ("Minyak Goreng", 30),
        ("Indomie Goreng", 1),
    ]),
    ("Ayam Crispy Paha Bawah/Sayap + Indomie Goreng", [
        ("Ayam Sayap/Paha Bawah (mentah)", 1),
        ("Tepung Crispy", 50),
        ("Minyak Goreng", 30),
        ("Indomie Goreng", 1),
    ]),
    ("Ayam Geprek Original + Nasi + Gratis Es Teh", [
        ("Ayam Dada/Paha Atas (mentah)", 1),
        ("Bumbu Sambal Original", 30),
        ("Beras", 150),
        ("Teh Celup/Bubuk", 5),
        ("Gula", 15),
        ("Es Batu", 50),
    ]),
    ("Ayam Geprek Sambal Korek Surabaya + Nasi + Gratis Es Teh", [
        ("Ayam Dada/Paha Atas (mentah)", 1),
        ("Bumbu Sambal Korek Surabaya", 30),
        ("Beras", 150),
        ("Teh Celup/Bubuk", 5),
        ("Gula", 15),
        ("Es Batu", 50),
    ]),
    ("Ayam Geprek Sambal Rica Manado + Nasi + Gratis Es Teh", [
        ("Ayam Dada/Paha Atas (mentah)", 1),
        ("Bumbu Sambal Rica Manado", 30),
        ("Beras", 150),
        ("Teh Celup/Bubuk", 5),
        ("Gula", 15),
        ("Es Batu", 50),
    ]),
    ("Single Ayam Geprek Original Dada/Paha Atas + Gratis Nasi", [
        ("Ayam Dada/Paha Atas (mentah)", 1),
        ("Bumbu Sambal Original", 30),
        ("Beras", 150),
    ]),
    ("Single Ayam Geprek Sayap/Paha Bawah + Gratis Nasi", [
        ("Ayam Sayap/Paha Bawah (mentah)", 1),
        ("Bumbu Sambal Original", 30),
        ("Beras", 150),
    ]),
    ("Single Ayam Geprek Sambal Korek Surabaya + Gratis Nasi", [
        ("Ayam Dada/Paha Atas (mentah)", 1),
        ("Bumbu Sambal Korek Surabaya", 30),
        ("Beras", 150),
    ]),
    ("Single Ayam Geprek Sambal Rica Manado + Gratis Nasi", [
        ("Ayam Dada/Paha Atas (mentah)", 1),
        ("Bumbu Sambal Rica Manado", 30),
        ("Beras", 150),
    ]),
    ("Single Ayam Geprek Andalan + Gratis Nasi", [
        ("Ayam Dada/Paha Atas (mentah)", 1),
        ("Bumbu Bakar Andalan", 30),
        ("Beras", 150),
    ]),
    ("Single Ayam Crispy Dada/Paha Atas + Gratis Nasi", [
        ("Ayam Dada/Paha Atas (mentah)", 1),
        ("Tepung Crispy", 50),
        ("Minyak Goreng", 30),
        ("Beras", 150),
    ]),
    ("Single Ayam Crispy Paha Bawah/Sayap + Gratis Nasi", [
        ("Ayam Sayap/Paha Bawah (mentah)", 1),
        ("Tepung Crispy", 50),
        ("Minyak Goreng", 30),
        ("Beras", 150),
    ]),
    ("Es Teh", [
        ("Teh Celup/Bubuk", 5),
        ("Gula", 15),
        ("Es Batu", 50),
    ]),
    ("Air Mineral", [
        ("Air Mineral Kemasan", 1),
    ]),
    ("Ice Chocolate", [
        ("Sirup/Bubuk Coklat", 30),
        ("Susu Cair", 50),
        ("Es Batu", 50),
    ]),
    ("Orange", [
        ("Sirup Orange", 30),
        ("Es Batu", 50),
    ]),
    ("Lemon Tea", [
        ("Teh Celup/Bubuk", 5),
        ("Gula", 15),
        ("Lemon (buah)", 0.5),
        ("Es Batu", 50),
    ]),
    ("Sambal Rica Manado", [
        ("Bumbu Sambal Rica Manado", 40),
    ]),
    ("Sambal Korek Surabaya", [
        ("Bumbu Sambal Korek Surabaya", 40),
    ]),
    ("Tambahan Nasi", [
        ("Beras", 150),
    ]),
]


def get_tmpl_id(models, db, uid, password, name):
    ids = models.execute_kw(
        db, uid, password, "product.template", "search",
        [[["name", "=", name]]],
    )
    return ids[0] if ids else None


def get_variant_id(models, db, uid, password, tmpl_id):
    ids = models.execute_kw(
        db, uid, password, "product.product", "search",
        [[["product_tmpl_id", "=", tmpl_id]]],
        {"limit": 1},
    )
    return ids[0] if ids else None


def main():
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, password, {})
    if not uid:
        print("❌ Login gagal, cek username/password/db")
        return
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    ok, skipped, errors = 0, [], []

    for product_name, components in BOM_DATA:
        tmpl_id = get_tmpl_id(models, db, uid, password, product_name)
        if not tmpl_id:
            errors.append(f"{product_name} -> produk jadi tidak ditemukan di Odoo")
            continue

        # Skip kalau BoM untuk produk ini sudah ada (hindari duplikat kalau di-rerun)
        existing_bom = models.execute_kw(
            db, uid, password, "mrp.bom", "search",
            [[["product_tmpl_id", "=", tmpl_id]]],
        )
        if existing_bom:
            skipped.append(product_name)
            continue

        bom_line_ids = []
        missing = []
        for material_name, qty in components:
            mat_tmpl_id = get_tmpl_id(models, db, uid, password, material_name)
            if not mat_tmpl_id:
                missing.append(material_name)
                continue
            variant_id = get_variant_id(models, db, uid, password, mat_tmpl_id)
            if not variant_id:
                missing.append(material_name)
                continue
            bom_line_ids.append((0, 0, {"product_id": variant_id, "product_qty": qty}))

        if missing:
            errors.append(f"{product_name} -> bahan tidak ditemukan: {', '.join(missing)}")
            continue

        models.execute_kw(
            db, uid, password, "mrp.bom", "create",
            [{
                "product_tmpl_id": tmpl_id,
                "product_qty": 1.0,
                "type": "normal",
                "bom_line_ids": bom_line_ids,
            }],
            {"context": CTX},
        )
        print(f"✅ BoM: {product_name} ({len(bom_line_ids)} bahan)")
        ok += 1

    print(f"\nSelesai: {ok}/{len(BOM_DATA)} BoM berhasil dibuat.")
    if skipped:
        print("\n⚠️ Sudah ada sebelumnya (dilewati):")
        for s in skipped:
            print(f"  - {s}")
    if errors:
        print("\n❌ Gagal / perlu dicek manual:")
        for e in errors:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
