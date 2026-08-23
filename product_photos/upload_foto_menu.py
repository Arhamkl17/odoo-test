"""
Upload foto menu geprekyukss ke Odoo (product.template.image_1920) via XML-RPC.

Cara pakai:
1. Extract foto_menu_geprekyukss.zip ke folder Codespace, misal: /workspaces/Odoo-mv/product_photos
2. Sesuaikan FOLDER di bawah kalau beda path
3. Jalankan: python3 upload_foto_menu.py
"""

import xmlrpc.client
import base64
import os

url = "http://localhost:8069"
db = "Test1"
username = "arhamkamal98@gmail.com"
password = "Lowongan01"

FOLDER = "/workspaces/Odoo-mv/product_photos"  # sesuaikan kalau perlu

# Mapping: nama file (tanpa .jpg) -> nama produk PERSIS seperti di Odoo
mapping = {
    "paket_geprek_indomie": "Ayam Geprek Indomie + Pilih Sambal + Gratis Es Teh",
    "paket_crispy_dada_paha_atas": "Ayam Crispy Dada/Paha Atas + Nasi + Gratis Es Teh",
    "paket_crispy_sayap_paha_bawah": "Ayam Crispy Sayap/Paha Bawah + Nasi + Gratis Es Teh",
    "paket_indomie_crispy_dada_paha_atas": "Ayam Crispy Dada/Paha Atas + Indomie Goreng",
    "paket_indomie_crispy_paha_bawah_sayap": "Ayam Crispy Paha Bawah/Sayap + Indomie Goreng",
    "paket_geprek_original": "Ayam Geprek Original + Nasi + Gratis Es Teh",
    "paket_geprek_sambal_korek": "Ayam Geprek Sambal Korek Surabaya + Nasi + Gratis Es Teh",
    "paket_geprek_sambal_rica": "Ayam Geprek Sambal Rica Manado + Nasi + Gratis Es Teh",
    "single_geprek_original": "Single Ayam Geprek Original Dada/Paha Atas + Gratis Nasi",
    "single_geprek_sayap_paha_bawah": "Single Ayam Geprek Sayap/Paha Bawah + Gratis Nasi",
    "single_geprek_sambal_korek": "Single Ayam Geprek Sambal Korek Surabaya + Gratis Nasi",
    "single_geprek_sambal_rica": "Single Ayam Geprek Sambal Rica Manado + Gratis Nasi",
    "single_geprek_andalan": "Single Ayam Geprek Andalan + Gratis Nasi",
    "single_crispy_dada_paha_atas": "Single Ayam Crispy Dada/Paha Atas + Gratis Nasi",
    "single_crispy_paha_bawah_sayap": "Single Ayam Crispy Paha Bawah/Sayap + Gratis Nasi",
    "es_teh": "Es Teh",
    "air_mineral": "Air Mineral",
    "ice_chocolate": "Ice Chocolate",
    "orange": "Orange",
    "lemon_tea": "Lemon Tea",
    "sambal_rica_manado": "Sambal Rica Manado",
    "sambal_korek_surabaya": "Sambal Korek Surabaya",
    "tambahan_nasi": "Tambahan Nasi",
}

def main():
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, password, {})
    if not uid:
        print("❌ Login gagal, cek username/password/db")
        return
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    ok, missing_file, missing_product = 0, [], []

    for filename, product_name in mapping.items():
        filepath = None
        for ext in [".jpg", ".jpeg", ".png"]:
            candidate = os.path.join(FOLDER, filename + ext)
            if os.path.exists(candidate):
                filepath = candidate
                break
        if not filepath:
            missing_file.append(product_name)
            continue

        with open(filepath, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        product_ids = models.execute_kw(
            db, uid, password,
            "product.template", "search",
            [[["name", "=", product_name]]],
        )
        if not product_ids:
            missing_product.append(product_name)
            continue

        models.execute_kw(
            db, uid, password,
            "product.template", "write",
            [product_ids, {"image_1920": image_b64}],
            {"context": {"tracking_disable": True, "mail_create_nolog": True,
                         "mail_create_nosubscribe": True, "mail_notrack": True}},
        )
        print(f"✅ {product_name}")
        ok += 1

    print(f"\nSelesai: {ok}/{len(mapping)} foto berhasil di-upload.")
    if missing_file:
        print("\n⚠️ File foto tidak ditemukan untuk:")
        for p in missing_file:
            print(f"  - {p}")
    if missing_product:
        print("\n⚠️ Produk tidak ditemukan di Odoo (cek nama persis):")
        for p in missing_product:
            print(f"  - {p}")

if __name__ == "__main__":
    main()
