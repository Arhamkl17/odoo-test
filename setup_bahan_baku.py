"""
Setup 18 Bahan Baku (Raw Material) untuk Geprekyukss di Odoo via XML-RPC.

- Tipe produk: Storable Product (Goods + is_storable=True)
- Can be Sold: OFF (bahan baku, tidak dijual langsung ke customer)
- Can be Purchased: ON
- UoM: gram / mL / Units (dibuat otomatis kalau belum ada di database)
- Cost (standard_price): harga placeholder hasil riset pasar Agustus 2026,
  BISA & PERLU diupdate manual nanti sesuai harga beli aktual dari supplier.

Cara pakai:
1. Upload file ini ke repo (root Odoo-mv), lalu git pull di Codespace
   (sama caranya kayak upload_foto_menu.py kemarin)
2. Jalankan: python3 setup_bahan_baku.py
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

# (nama_bahan, satuan, cost_placeholder)
# satuan: "gram" | "ml" | "pcs"
RAW_MATERIALS = [
    ("Ayam Dada/Paha Atas (mentah)", "pcs", 10000),
    ("Ayam Sayap/Paha Bawah (mentah)", "pcs", 7000),
    ("Tepung Crispy", "gram", 25),
    ("Minyak Goreng", "ml", 22),
    ("Beras", "gram", 16),
    ("Indomie Goreng", "pcs", 3500),
    ("Bumbu Bakar Andalan", "gram", 40),
    ("Bumbu Sambal Original", "gram", 45),
    ("Bumbu Sambal Korek Surabaya", "gram", 45),
    ("Bumbu Sambal Rica Manado", "gram", 45),
    ("Teh Celup/Bubuk", "gram", 30),
    ("Gula", "gram", 19),
    ("Es Batu", "gram", 3),
    ("Air Mineral Kemasan", "pcs", 4000),
    ("Sirup/Bubuk Coklat", "ml", 30),
    ("Susu Cair", "ml", 15),
    ("Sirup Orange", "ml", 25),
    ("Lemon (buah)", "pcs", 2500),
]


def get_or_create_uom(models, db, uid, password, satuan):
    """Cari UoM yang sesuai, kalau belum ada, buat baru di kategori yang tepat."""
    if satuan == "gram":
        name_candidates = ["g", "Gram", "gram"]
        category_name = "Weight"
        factor = 1000.0  # 1 kg (reference) = 1000 gram
        uom_type = "smaller"
    elif satuan == "ml":
        name_candidates = ["mL", "ml", "Milliliter", "Mililiter"]
        category_name = "Volume"
        factor = 1000.0  # 1 L (reference) = 1000 mL
        uom_type = "smaller"
    elif satuan == "pcs":
        name_candidates = ["Units", "Unit(s)", "pcs", "Pieces"]
        category_name = "Unit"
        factor = 1.0
        uom_type = "reference"
    else:
        raise ValueError(f"Satuan tidak dikenal: {satuan}")

    # 1. Coba cari UoM yang sudah ada
    uom_ids = models.execute_kw(
        db, uid, password, "uom.uom", "search",
        [[["name", "in", name_candidates]]],
    )
    if uom_ids:
        return uom_ids[0]

    # 2. Belum ada -> cari kategori-nya, lalu buat UoM baru
    category_ids = models.execute_kw(
        db, uid, password, "uom.category", "search",
        [[["name", "=", category_name]]],
    )
    if not category_ids:
        # fallback: cari kategori "Unit" default kalau kategori spesifik tidak ketemu
        category_ids = models.execute_kw(
            db, uid, password, "uom.category", "search", [[]], {"limit": 1}
        )

    new_uom_id = models.execute_kw(
        db, uid, password, "uom.uom", "create",
        [{
            "name": name_candidates[0],
            "category_id": category_ids[0],
            "factor": factor,
            "uom_type": uom_type,
        }],
        {"context": CTX},
    )
    print(f"  (UoM '{name_candidates[0]}' belum ada, sudah dibuat baru)")
    return new_uom_id


def main():
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, password, {})
    if not uid:
        print("❌ Login gagal, cek username/password/db")
        return
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    # Cache UoM per satuan supaya tidak query berulang-ulang
    uom_cache = {}
    for satuan in ["gram", "ml", "pcs"]:
        uom_cache[satuan] = get_or_create_uom(models, db, uid, password, satuan)

    ok, skipped = 0, []

    for name, satuan, cost in RAW_MATERIALS:
        # Skip kalau produk dengan nama sama sudah ada (hindari duplikat kalau script di-rerun)
        existing = models.execute_kw(
            db, uid, password, "product.template", "search",
            [[["name", "=", name]]],
        )
        if existing:
            skipped.append(name)
            continue

        uom_id = uom_cache[satuan]

        models.execute_kw(
            db, uid, password, "product.template", "create",
            [{
                "name": name,
                "type": "consu",
                "is_storable": True,
                "sale_ok": False,
                "purchase_ok": True,
                "uom_id": uom_id,
                "standard_price": cost,
            }],
            {"context": CTX},
        )
        print(f"✅ {name} ({satuan}, Rp{cost:,}/{satuan})".replace(",", "."))
        ok += 1

    print(f"\nSelesai: {ok}/{len(RAW_MATERIALS)} bahan baku berhasil dibuat.")
    if skipped:
        print("\n⚠️ Sudah ada sebelumnya (dilewati, tidak dibuat duplikat):")
        for s in skipped:
            print(f"  - {s}")


if __name__ == "__main__":
    main()
