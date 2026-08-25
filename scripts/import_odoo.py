#!/usr/bin/env python3
"""
Import data ke Odoo 19 (geprekyukss_pos) lewat XML-RPC `load()`.

Urutan wajib: UoM -> COA -> Kategori -> Produk -> Update Harga.
Jalankan satu tahap dulu, cek hasilnya di Odoo UI, baru lanjut ke tahap berikutnya
via --step, atau jalankan semua sekaligus (tanpa --step).

KREDENSIAL: WAJIB via environment variable, jangan hardcode.
    export ODOO_URL="http://localhost:8069"
    export ODOO_DB="Test1"
    export ODOO_USER="admin@example.com"
    export ODOO_PASSWORD="xxxxx"

Cara pakai:
    python3 scripts/import_odoo.py --step uom
    python3 scripts/import_odoo.py --step coa
    python3 scripts/import_odoo.py --step categories
    python3 scripts/import_odoo.py --step products
    python3 scripts/import_odoo.py --step price
    python3 scripts/import_odoo.py --step all      # semua tahap berurutan
"""
import argparse
import base64
import csv
import os
import sys
import xmlrpc.client

CSV_DIR = os.path.join(os.path.dirname(__file__), "..", "import_data", "csv")


def connect():
    url = os.environ.get("ODOO_URL")
    db = os.environ.get("ODOO_DB")
    user = os.environ.get("ODOO_USER")
    password = os.environ.get("ODOO_PASSWORD")
    missing = [k for k, v in [("ODOO_URL", url), ("ODOO_DB", db),
                               ("ODOO_USER", user), ("ODOO_PASSWORD", password)] if not v]
    if missing:
        sys.exit(f"ERROR: environment variable belum di-set: {', '.join(missing)}")

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, user, password, {})
    if not uid:
        sys.exit("ERROR: autentikasi gagal - cek ODOO_USER/ODOO_PASSWORD/ODOO_DB")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return db, user, password, models, uid


def get_model_fields(models, db, uid, password, model_name):
    """Return dict of technical field names available on a model."""
    return models.execute_kw(db, uid, password, model_name, "fields_get", [], {"attributes": ["string"]})


def resolve_field(available_fields, candidates, label):
    """Pick the first candidate technical field name that actually exists on the model."""
    for c in candidates:
        if c in available_fields:
            return c
    print(f"  [SKIP] Tidak ketemu field teknis untuk kolom '{label}'. "
          f"Dicoba: {candidates}. Field ini akan DILEWATI.")
    return None


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def do_load(models, db, uid, password, model, field_names, rows, label):
    if not rows:
        print(f"  Tidak ada data untuk {label}, skip.")
        return
    print(f"  Mengirim {len(rows)} baris ke model '{model}' ({label})...")
    result = models.execute_kw(db, uid, password, model, "load", [field_names, rows])
    ids = result.get("ids") or []
    messages = result.get("messages") or []
    print(f"  -> Berhasil: {len(ids)} record.")
    if messages:
        print(f"  -> {len(messages)} pesan/warning dari Odoo:")
        for m in messages[:20]:
            print(f"     [{m.get('type')}] baris {m.get('record')}: {m.get('message')}")
        if len(messages) > 20:
            print(f"     ...dan {len(messages) - 20} pesan lainnya.")


# ---------------------------------------------------------------------------
# STEP 1: UoM
# ---------------------------------------------------------------------------
def uom_ext_id(name):
    return f"import_geprek.uom_{name.strip().replace(' ', '_')}"


def collect_all_unit_names():
    """Gabungkan semua nama satuan yang perlu ada: dari 01_uom.csv (nama + unit referensi)
    DAN semua kode satuan yang dipakai di file produk (04_*), supaya tidak ada yang
    'menggantung' tanpa uom.uom yang cocok saat step_products jalan."""
    names = set()

    rows = read_csv(os.path.join(CSV_DIR, "01_uom.csv"))
    for row in rows[1:]:
        if not row or not row[0]:
            continue
        names.add(row[0].strip())
        if len(row) > 2 and row[2].strip():
            names.add(row[2].strip())  # Unit Referensi (satuan dasar, mis. GRM, PCS)

    for csv_file in ["04_products_bahan.csv", "04_products_menu.csv"]:
        rows = read_csv(os.path.join(CSV_DIR, csv_file))
        for row in rows[1:]:
            if len(row) > 2 and row[2].strip():
                names.add(row[2].strip())

    return sorted(names)


def step_uom(models, db, uid, password):
    print("\n=== STEP 1: Satuan (uom.uom) ===")
    fields = get_model_fields(models, db, uid, password, "uom.uom")
    f_name = resolve_field(fields, ["name"], "Nama Unit")

    all_names = collect_all_unit_names()
    print(f"  Total {len(all_names)} nama satuan unik terkumpul (termasuk satuan dasar")
    print(f"  seperti GRM/PCS/PTG yang direferensikan produk tapi tidak eksplisit di file satuan).")

    field_names = ["id", f_name]
    out_rows = [[uom_ext_id(n), n] for n in all_names]
    do_load(models, db, uid, password, "uom.uom", field_names, out_rows, "Satuan")
    print("  CATATAN: rasio konversi (kolom 'Memiliki'/'Unit Referensi') TIDAK di-import otomatis.")
    print("  Set manual di Inventory > Configuration > Units of Measure setelah ini,")
    print("  karena struktur field UoM beda-beda tergantung versi Odoo.")


# ---------------------------------------------------------------------------
# STEP 2: Chart of Accounts
# ---------------------------------------------------------------------------
ACCOUNT_TYPE_MAP = {
    "bank and cash": "asset_cash",
    "aktiva terkini": "asset_current",
    "current assets": "asset_current",
    "ekuitas": "equity",
    "equity": "equity",
    "piutang": "asset_receivable",
    "receivable": "asset_receivable",
    "current liabilities": "liability_current",
    "prepayments": "asset_prepayments",
    "expenses": "expense",
    "other expenses": "expense",
    "income": "income",
    "other income": "income_other",
    "payable": "liability_payable",
    "cost of revenue": "expense_direct_cost",
    "fixed assets": "asset_fixed",
}


def step_coa(models, db, uid, password):
    print("\n=== STEP 2: Chart of Accounts (account.account) ===")
    fields = get_model_fields(models, db, uid, password, "account.account")
    f_code = resolve_field(fields, ["code"], "Code")
    f_name = resolve_field(fields, ["name"], "Account Name")
    f_type = resolve_field(fields, ["account_type"], "Type")

    field_names = ["id", f_code, f_name, f_type]
    out_rows = []
    skipped_types = set()
    for csv_file in ["02_coa_main.csv", "02_coa_ovo.csv"]:
        rows = read_csv(os.path.join(CSV_DIR, csv_file))
        for row in rows[1:]:
            if not row or not row[1]:  # need at least Code
                continue
            type_raw, code, name = row[0].strip(), row[1].strip(), row[2].strip()
            mapped_type = ACCOUNT_TYPE_MAP.get(type_raw.lower())
            if not mapped_type:
                skipped_types.add(type_raw)
                continue
            ext_id = f"import_geprek.account_{code.replace('.', '_')}"
            out_rows.append([ext_id, code, name, mapped_type])
    if skipped_types:
        print(f"  [PERHATIAN] Tipe akun tidak dikenal, baris ini DILEWATI: {skipped_types}")
        print("  Tambahkan mapping-nya di ACCOUNT_TYPE_MAP dalam script ini kalau perlu.")
    do_load(models, db, uid, password, "account.account", field_names, out_rows, "Chart of Accounts")


# ---------------------------------------------------------------------------
# STEP 3: Product Categories
# ---------------------------------------------------------------------------
def find_account_ext_id(code_or_name_hint):
    """Categories reference accounts by NAME (e.g. '5101.01 HPP Beverage').
    We map back to the external id we generated in step_coa using the code prefix."""
    if not code_or_name_hint:
        return False
    code = code_or_name_hint.split(" ", 1)[0].strip()
    return f"import_geprek.account_{code.replace('.', '_')}"


def step_categories(models, db, uid, password):
    print("\n=== STEP 3: Kategori Produk (product.category) ===")
    fields = get_model_fields(models, db, uid, password, "product.category")
    f_name = resolve_field(fields, ["name"], "Nama Tampilan")
    f_expense = resolve_field(fields, ["property_account_expense_categ_id"], "Akun Beban")
    f_income = resolve_field(fields, ["property_account_income_categ_id"], "Akun Laba")
    f_valuation = resolve_field(fields, ["property_stock_valuation_account_id"], "Akun Valuasi stok")

    cols = ["id", f_name]
    if f_expense:
        cols.append(f_expense + "/id")
    if f_income:
        cols.append(f_income + "/id")
    if f_valuation:
        cols.append(f_valuation + "/id")

    rows = read_csv(os.path.join(CSV_DIR, "03_categories.csv"))
    out_rows = []
    for row in rows[1:]:
        if not row or not row[0]:
            continue
        name, expense, income, _diff, _prod, valuation = (row + [""] * 6)[:6]
        ext_id = f"import_geprek.categ_{name.strip().replace(' ', '_')}"
        data_row = [ext_id, name.strip()]
        if f_expense:
            data_row.append(find_account_ext_id(expense) if expense.strip() else False)
        if f_income:
            data_row.append(find_account_ext_id(income) if income.strip() else False)
        if f_valuation:
            data_row.append(find_account_ext_id(valuation) if valuation.strip() else False)
        out_rows.append(data_row)
    do_load(models, db, uid, password, "product.category", cols, out_rows, "Kategori Produk")
    print("  CATATAN: 'Akun Perbedaan Harga' & 'Akun Produksi' tidak di-map (field custom/")
    print("  tidak standar di product.category) - set manual di UI kalau memang dipakai.")


# ---------------------------------------------------------------------------
# STEP 4: Products (new, from category-grouped files)
# ---------------------------------------------------------------------------
def step_products(models, db, uid, password):
    print("\n=== STEP 4: Produk Baru (product.template) ===")
    fields = get_model_fields(models, db, uid, password, "product.template")
    f_name = resolve_field(fields, ["name"], "Nama")
    f_categ = resolve_field(fields, ["categ_id"], "Kategori Produk")
    f_uom = resolve_field(fields, ["uom_id"], "Unit")
    f_uom_po = resolve_field(fields, ["uom_po_id"], "Unit Pembelian")
    f_pos = resolve_field(fields, ["available_in_pos"], "Available in POS")
    f_pos_categ = resolve_field(fields, ["pos_categ_ids"], "Kategori Produk POS")

    # Mapping product.category (dari file produk) -> pos.category (Food/Drinks)
    # yang sudah ada di Odoo kamu (dilihat dari screenshot: "Food", "Drinks").
    POS_CATEG_MAP = {
        "Menu Food": "Food",
        "Menu Beverage": "Drinks",
    }
    pos_categ_id_by_name = {}
    if f_pos_categ:
        existing = models.execute_kw(db, uid, password, "pos.category", "search_read",
                                      [[]], {"fields": ["id", "name"]})
        pos_categ_id_by_name = {c["name"]: c["id"] for c in existing}

    cols = ["id", f_name]
    if f_categ:
        cols.append(f_categ + "/id")
    if f_uom:
        cols.append(f_uom + "/id")
    if f_uom_po:
        cols.append(f_uom_po + "/id")
    if f_pos:
        cols.append(f_pos)

    out_rows = []
    for csv_file in ["04_products_bahan.csv", "04_products_menu.csv"]:
        rows = read_csv(os.path.join(CSV_DIR, csv_file))
        header = rows[0]
        for row in rows[1:]:
            if not row or not row[1]:  # need Nama at index 1
                continue
            categ, name, uom = (row + [""] * 3)[:3]
            if not name.strip():
                continue
            ext_id = f"import_geprek.product_{name.strip().replace(' ', '_').replace('/', '_')}"
            data_row = [ext_id, name.strip()]
            if f_categ:
                data_row.append(f"import_geprek.categ_{categ.strip().replace(' ', '_')}" if categ.strip() else False)
            if f_uom:
                data_row.append(uom_ext_id(uom) if uom.strip() else False)
            if f_uom_po:
                data_row.append(uom_ext_id(uom) if uom.strip() else False)
            if f_pos:
                is_menu = csv_file == "04_products_menu.csv"
                data_row.append("1" if is_menu else "0")
            out_rows.append(data_row)
    do_load(models, db, uid, password, "product.template", cols, out_rows, "Produk Baru")

    # --- Set pos_categ_ids (many2many) lewat write(), pakai ID numerik asli ---
    if f_pos_categ and pos_categ_id_by_name:
        print("  Menyambungkan produk menu ke Kategori Produk POS (Food/Drinks)...")
        updated_pc, skipped_pc = 0, 0
        for csv_file in ["04_products_menu.csv"]:
            rows = read_csv(os.path.join(CSV_DIR, csv_file))
            for row in rows[1:]:
                if not row or not row[1]:
                    continue
                categ, name = row[0].strip(), row[1].strip()
                pos_categ_name = POS_CATEG_MAP.get(categ)
                pos_categ_id = pos_categ_id_by_name.get(pos_categ_name) if pos_categ_name else None
                if not pos_categ_id:
                    skipped_pc += 1
                    continue
                matches = models.execute_kw(db, uid, password, "product.template", "search_read",
                                             [[["name", "=", name]]], {"fields": ["id"]})
                if len(matches) == 1:
                    models.execute_kw(db, uid, password, "product.template", "write",
                                       [[matches[0]["id"]], {f_pos_categ: [(6, 0, [pos_categ_id])]}])
                    updated_pc += 1
                else:
                    skipped_pc += 1
        print(f"  -> {updated_pc} produk disambungkan ke Kategori POS, {skipped_pc} dilewati "
              f"(kategori tidak ada di POS_CATEG_MAP, atau nama produk ambigu/tidak ketemu).")
    do_load(models, db, uid, password, "product.template", cols, out_rows, "Produk Baru")


# ---------------------------------------------------------------------------
# STEP 5: Price update (existing exported products)
# ---------------------------------------------------------------------------
def step_price(models, db, uid, password):
    print("\n=== STEP 5: Update Harga (product.template, matching by NAMA) ===")
    fields = get_model_fields(models, db, uid, password, "product.template")
    f_price = resolve_field(fields, ["list_price"], "Harga Jual")
    if not f_price:
        return

    rows = read_csv(os.path.join(CSV_DIR, "06_price_update.csv"))
    updated, not_found, ambiguous = 0, [], []

    for row in rows[1:]:
        if not row or len(row) < 3:
            continue
        _old_ext_id, name, price = row[0].strip(), row[1].strip(), row[2].strip()
        if not name or not price:
            continue

        # Cari produk berdasarkan nama PERSIS (case-insensitive, trimmed)
        matches = models.execute_kw(
            db, uid, password, "product.template", "search_read",
            [[["name", "=", name]]],
            {"fields": ["id", "name"]}
        )
        if not matches:
            not_found.append(name)
            continue
        if len(matches) > 1:
            ambiguous.append(name)
            continue

        product_id = matches[0]["id"]
        models.execute_kw(
            db, uid, password, "product.template", "write",
            [[product_id], {f_price: float(price)}]
        )
        updated += 1

    print(f"  -> Berhasil update harga: {updated} produk.")
    if not_found:
        print(f"  -> Tidak ketemu (nama tidak cocok persis), {len(not_found)} produk:")
        for n in not_found:
            print(f"     - {n}")
    if ambiguous:
        print(f"  -> Nama ganda/ambigu (dilewati), {len(ambiguous)} produk:")
        for n in ambiguous:
            print(f"     - {n}")


PHOTOS_DIR = os.path.join(os.path.dirname(__file__), "..", "import_data", "photos")

# Mapping nama file foto -> nama produk PERSIS (harus cocok dengan product.template.name)
PHOTO_PRODUCT_MAP = {
    "09_single_geprek_original.jpg": "GEPREK ORIGINAL DADA/PAHA ATAS",
    "10_single_geprek_sayap.jpg": "GEPREK ORIGINAL SAYAP",
    "11_single_geprek_korek.jpg": "GEPREK SAMBAL KOREK SURABAYA",
    "12_single_geprek_rica.jpg": "GEPREK SAMBAL RICA MANADO",
    "13_single_geprek_andalan.jpg": "GEPREK BAKAR ANDALAN",
    "14_single_crispy_dada.jpg": "AYAM CRISPY DADA/PAHA ATAS",
    "15_single_crispy_sayap.jpg": "AYAM CRISPY SAYAP",
    "01_ayam_geprek_indomie.jpg": "PKG MIE (AYAM GEPREK+SAMBAL LOKAL+INDOMIE)",
    "02_ayam_crispy_dada_nasi.jpg": "PKC (CRISPY DADA/PAHA ATAS+NASI+MINUM)",
    "03_ayam_crispy_sayap_nasi.jpg": "PKC (SAYAP+NASI+MINUM)",
    "04_ayam_crispy_dada_indomie.jpg": "PKC MIE (CRISPY DADA/PAHA ATAS+INDOMIE)",
    "05_ayam_crispy_sayap_indomie.jpg": "PKC MIE (CRISPY SAYAP/PAHA BAWAH+INDOMIE)",
    "06_ayam_geprek_original_nasi.jpg": "GEPREK ANDALAN + NASI",
    "07_ayam_geprek_korek_nasi.jpg": "PKG SAMBAL KOREK SURABAYA (GEPREK SAMBAL +NASI)",
    "08_ayam_geprek_rica_nasi.jpg": "PKG SAMBAL RICA MANADO (GEPREK SAMBAL +NASI)",
    "16_es_teh.jpg": "ES TEH",
    "18_ice_chocolate.jpg": "ICE CHOCOLATE",
    "19_orange.jpg": "ORANGE",
    "20_lemon_tea.jpg": "LEMON TEA",
    "21_sambal_rica.jpg": "SAMBAL RICA MANADO",
    "22_sambal_korek.jpg": "SAMBAL KOREK SURABAYA",
    # 17_air_mineral.jpg sengaja tidak dimasukkan - tidak ada produk yang cocok.
}


def step_photos(models, db, uid, password):
    print("\n=== STEP 6: Foto Produk (product.template.image_1920) ===")
    fields = get_model_fields(models, db, uid, password, "product.template")
    f_image = resolve_field(fields, ["image_1920"], "Gambar Produk")
    if not f_image:
        return

    updated, not_found, ambiguous, missing_file = 0, [], [], []
    for filename, product_name in PHOTO_PRODUCT_MAP.items():
        filepath = os.path.join(PHOTOS_DIR, filename)
        if not os.path.isfile(filepath):
            missing_file.append(filename)
            continue

        matches = models.execute_kw(
            db, uid, password, "product.template", "search_read",
            [[["name", "=", product_name]]], {"fields": ["id"]}
        )
        if not matches:
            not_found.append(product_name)
            continue
        if len(matches) > 1:
            ambiguous.append(product_name)
            continue

        with open(filepath, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")

        models.execute_kw(
            db, uid, password, "product.template", "write",
            [[matches[0]["id"]], {f_image: b64_data}]
        )
        updated += 1
        print(f"  [OK] {filename} -> {product_name}")

    print(f"\n  -> Berhasil upload foto: {updated} produk.")
    if not_found:
        print(f"  -> Produk tidak ketemu: {not_found}")
    if ambiguous:
        print(f"  -> Nama produk ambigu (dilewati): {ambiguous}")
    if missing_file:
        print(f"  -> File foto tidak ditemukan di {PHOTOS_DIR}: {missing_file}")


def step_uom_fix(models, db, uid, password):
    print("\n=== STEP 1b: Perbaiki UoM (rasio konversi, struktur Odoo 19) ===")
    print("  Sumber: 01_uom_resolved.csv (update record yang SUDAH ADA, bukan buat baru)")
    print("  Odoo 19 tidak punya uom.category/uom_type - cuma relative_uom_id + relative_factor.")

    fields = get_model_fields(models, db, uid, password, "uom.uom")
    f_name = resolve_field(fields, ["name"], "Unit Name")
    f_relative_uom = resolve_field(fields, ["relative_uom_id"], "Reference Unit")
    f_relative_factor = resolve_field(fields, ["relative_factor"], "Contains")
    if not f_relative_uom or not f_relative_factor:
        print("  Field tidak ketemu, batal.")
        return

    rows = read_csv(os.path.join(CSV_DIR, "01_uom_resolved.csv"))
    header, data = rows[0], rows[1:]
    # header: uom_ext_id, name, category_ext_id, category_name, uom_type, factor, note

    # 1. Cari satuan REFERENSI per kategori (uom_type == "reference")
    reference_by_category = {}
    for row in data:
        if len(row) < 5:
            continue
        uom_ext_id_val, _name, category_ext_id, _catname, uom_type = row[:5]
        if uom_type.strip() == "reference":
            reference_by_category[category_ext_id.strip()] = uom_ext_id_val.strip()

    # 2. Untuk satuan non-referensi, ambil angka "Memiliki=N" dari kolom note
    import re
    out_rows = []
    skipped = []
    for row in data:
        if len(row) < 7:
            continue
        uom_ext_id_val, name, category_ext_id, _catname, uom_type, _factor, note = row[:7]
        uom_ext_id_val = uom_ext_id_val.strip()
        if uom_type.strip() == "reference":
            continue  # satuan referensi tidak perlu di-set relative_uom_id ke dirinya sendiri

        ref_uom = reference_by_category.get(category_ext_id.strip())
        m = re.search(r"Memiliki=(\d+(?:\.\d+)?)", note)
        if not ref_uom or not m:
            skipped.append(uom_ext_id_val)
            continue

        ext_id = f"import_geprek.{uom_ext_id_val}"
        ref_ext_id = f"import_geprek.{ref_uom}"
        qty = m.group(1)
        out_rows.append([ext_id, name.strip(), ref_ext_id, qty])

    if skipped:
        print(f"  [SKIP] {len(skipped)} satuan tidak punya info 'Memiliki=N' yang jelas: {skipped}")

    cols = ["id", f_name, f_relative_uom + "/id", f_relative_factor]
    do_load(models, db, uid, password, "uom.uom", cols, out_rows, "Update rasio konversi UoM")
    print("  Selesai. UoM lama TETAP DIPAKAI (external id sama), 148 produk yang sudah")
    print("  pakai satuan ini otomatis ikut ter-update, tidak perlu re-run step products.")


BOM_PRODUCT_GROUPS = {
    "Paket Ayam Geprek/Crispy": [
        "PAKET AYAM CRISPY DADA/PAHA ATAS", "PAKET AYAM CRISPY PAHA BAWAH",
        "PAKET AYAM CRISPY SAYAP", "PAKET GEPREK BAKAR", "PAKET GEPREK LUMER",
        "PKG GEPREK BAKAR ANDALAN", "PKG GEPREK MEVVAH", "PKG SAMBAL IJO PADANG",
        "PKG SAMBAL KOREK SURABAYA", "PKG SAMBAL ORI DADA/PAHA ATAS",
        "PKG SAMBAL ORI PAHA BAWAH", "PKG SAMBAL ORI SAYAP", "PKG SAMBAL RICA MANADO",
        "PKG SMOKEY BBQ", "AYAM SEGEPOK SINGLE", "PAKET AYAM SEGEPOK BEREMPAT",
        "SEGEPOK BERLIMA", "GEPREK SAOS KEJU LUMER", "GEPREK SMOKEY BBQ",
    ],
    "Paket Indomie": [
        "PAKET INDOMIE CRISPY DADA/PAHA ATAS", "PAKET INDOMIE CRISPY PAHA BAWAH",
        "PKG INDOMIE CRISPY SAYAP", "PKG INDOMIE GEPREK SAMBAL LOKAL",
    ],
    "Paket Hemat/Spesial": [
        "BIG HEMAT 1", "BIG HEMAT 2", "BIG HEMAT 3", "BIG HEMAT 4",
        "PAKET SETIA AC", "PAKET SETIA GO", "PAKET MEVVAH BERDUA",
        "PAKET YUKSSS MABAR", "YUKSSS RAMA 1", "YUKSSS RAMA 2", "YUKSSS RAMA 3",
        "PAKET KULIT CRISPY", "PKG LOKAL DUO", "PAKET BIG ORDER CRISPY MIX",
    ],
    "Add-ons": [
        "MOZZARELLA", "KEMASAN VARIAN AYAM", "KEMASAN VARIAN INDOMIE",
        "MENU SAMBAL IJO PADANG", "MENU SAMBAL KOREK SURABAYA",
        "MENU SAMBAL ORIGINAL", "MENU SAMBAL RICA MANADO",
    ],
}


def step_bom_products(models, db, uid, password):
    print("\n=== STEP: Daftarkan 44 Produk Paket/Combo/Add-ons (harga sementara Rp 1) ===")

    # 1. Buat 4 kategori POS baru
    pos_fields = get_model_fields(models, db, uid, password, "pos.category")
    f_pos_name = resolve_field(pos_fields, ["name"], "Nama Kategori POS")
    pos_cat_rows = [[f"import_geprek.poscateg_{name.replace(' ', '_').replace('/', '_')}", name]
                     for name in BOM_PRODUCT_GROUPS.keys()]
    do_load(models, db, uid, password, "pos.category", ["id", f_pos_name], pos_cat_rows, "Kategori POS baru")

    # 2. Cari id kategori produk "Menu Food" (semua 44 item ini makanan)
    categ_ids = models.execute_kw(db, uid, password, "product.category", "search",
        [[["name", "=", "Menu Food"]]])
    if not categ_ids:
        print("  [ERROR] Kategori Produk 'Menu Food' tidak ketemu, batal.")
        return
    categ_ext_id = "import_geprek.categ_Menu_Food"

    # 3. Buat 44 produk
    tmpl_fields = get_model_fields(models, db, uid, password, "product.template")
    f_name = resolve_field(tmpl_fields, ["name"], "Nama")
    f_categ = resolve_field(tmpl_fields, ["categ_id"], "Kategori Produk")
    f_price = resolve_field(tmpl_fields, ["list_price"], "Harga Jual")
    f_pos = resolve_field(tmpl_fields, ["available_in_pos"], "Available in POS")
    f_pos_categ = resolve_field(tmpl_fields, ["pos_categ_ids"], "Kategori Produk POS")

    cols = ["id", f_name, f_categ + "/id", f_price, f_pos, f_pos_categ + "/id"]
    out_rows = []
    for group_name, products in BOM_PRODUCT_GROUPS.items():
        pos_ext_id = f"import_geprek.poscateg_{group_name.replace(' ', '_').replace('/', '_')}"
        for name in products:
            ext_id = f"import_geprek.product_{name.strip().replace(' ', '_').replace('/', '_')}"
            out_rows.append([ext_id, name, categ_ext_id, "1", "1", pos_ext_id])

    do_load(models, db, uid, password, "product.template", cols, out_rows, "44 Produk Paket/Combo")
    print("  Selesai. Semua diberi harga sementara Rp 1 - UPDATE setelah data harga dari tim masuk.")
    print("  Gunakan step 'price' (matching by nama) setelah CSV harga baru tersedia.")


def step_bom(models, db, uid, password):
    print("\n=== STEP: Import BOM (resep) dari bom_parsed_v2.json ===")
    import json as json_lib
    bom_path = os.path.join(os.path.dirname(__file__), "..", "import_data", "bom_parsed_v2.json")
    with open(bom_path) as f:
        all_boms = json_lib.load(f)
    all_boms = [b for b in all_boms if b["produk"] != "Produk"]

    # Dedup: kalau ada nama produk sama 2x, pakai yang resepnya PALING BANYAK bahan
    by_name = {}
    for b in all_boms:
        if b["produk"] not in by_name or len(b["lines"]) > len(by_name[b["produk"]]["lines"]):
            by_name[b["produk"]] = b
    all_boms = list(by_name.values())

    def find_id(model, domain):
        r = models.execute_kw(db, uid, password, model, "search", [domain])
        return r[0] if r else None

    bom_fields = get_model_fields(models, db, uid, password, "mrp.bom")
    f_product_tmpl = resolve_field(bom_fields, ["product_tmpl_id"], "Produk")
    f_qty = resolve_field(bom_fields, ["product_qty"], "Kuantitas")
    f_type = resolve_field(bom_fields, ["type"], "Jenis BoM")
    f_lines = resolve_field(bom_fields, ["bom_line_ids"], "Baris BoM")

    line_fields = get_model_fields(models, db, uid, password, "mrp.bom.line")
    f_line_product = resolve_field(line_fields, ["product_id"], "Komponen")
    f_line_qty = resolve_field(line_fields, ["product_qty"], "Kuantitas Komponen")
    f_line_uom = resolve_field(line_fields, ["product_uom_id"], "Unit Komponen")

    BOM_TYPE_MAP = {"Kit": "phantom", "Manufacture this product": "normal", "Normal": "normal"}

    created, skipped, errors = 0, [], []
    for b in all_boms:
        tmpl_id = find_id("product.template", [["name", "=", b["produk"]]])
        if not tmpl_id:
            skipped.append((b["produk"], "produk tidak ketemu"))
            continue

        # Cek sudah ada BOM buat produk ini atau belum (skip biar tidak duplikat)
        existing_bom = find_id("mrp.bom", [[f_product_tmpl, "=", tmpl_id]])
        if existing_bom:
            skipped.append((b["produk"], "BOM sudah ada, dilewati"))
            continue

        line_vals = []
        ok = True
        for line in b["lines"]:
            comp_id = find_id("product.product", [["name", "=", line["komponen"]]])
            if not comp_id:
                # Coba di product.template lalu ambil variantnya
                comp_tmpl_id = find_id("product.template", [["name", "=", line["komponen"]]])
                if comp_tmpl_id:
                    variants = models.execute_kw(db, uid, password, "product.product", "search",
                        [[["product_tmpl_id", "=", comp_tmpl_id]]])
                    comp_id = variants[0] if variants else None
            if not comp_id:
                errors.append((b["produk"], f"komponen '{line['komponen']}' tidak ketemu"))
                ok = False
                break
            uom_id = find_id("uom.uom", [["name", "=", line["unit"]]]) if line["unit"] else False
            line_val = {f_line_product: comp_id, f_line_qty: line["qty"] or 1}
            if uom_id:
                line_val[f_line_uom] = uom_id
            line_vals.append((0, 0, line_val))

        if not ok:
            continue

        bom_type = BOM_TYPE_MAP.get(b["jenis"], "normal")
        vals = {
            f_product_tmpl: tmpl_id,
            f_qty: b["kuantitas"] or 1,
            f_type: bom_type,
            f_lines: line_vals,
        }
        try:
            models.execute_kw(db, uid, password, "mrp.bom", "create", [vals])
            created += 1
            print(f"  [OK] {b['produk']} ({len(line_vals)} bahan)")
        except Exception as e:
            errors.append((b["produk"], str(e)[:150]))

    print(f"\n  Berhasil buat BOM: {created}")
    print(f"  Dilewati (sudah ada / produk tidak ketemu): {len(skipped)}")
    for p, r in skipped:
        print(f"    - {p}: {r}")
    print(f"  Error (komponen tidak ketemu, dll): {len(errors)}")
    for p, r in errors:
        print(f"    - {p}: {r}")


STEPS = {
    "uom": step_uom,
    "uom_fix": step_uom_fix,
    "coa": step_coa,
    "categories": step_categories,
    "products": step_products,
    "price": step_price,
    "photos": step_photos,
    "bom_products": step_bom_products,
    "bom": step_bom,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", choices=list(STEPS.keys()) + ["all"], default="all")
    args = parser.parse_args()

    db, user, password, models, uid = connect()
    print(f"Connected to {os.environ['ODOO_URL']} (db={db}, user={user}, uid={uid})")

    if args.step == "all":
        for name, fn in STEPS.items():
            fn(models, db, uid, password)
    else:
        STEPS[args.step](models, db, uid, password)

    print("\nSelesai.")


if __name__ == "__main__":
    main()
