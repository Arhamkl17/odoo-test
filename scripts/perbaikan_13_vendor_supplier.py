# -*- coding: utf-8 -*-
"""perbaikan_13_vendor_supplier.py — F3b: lengkapi nama vendor (supplier) + supplierinfo

Latar (temuan inspeksi & keputusan 15 Sep 2026):
  * 21 dari 52 bahan tidak punya `product.supplierinfo` sama sekali;
  * baris supplier yang ada harganya **beda** dari `standard_price` yang dipakai sistem;
  * sebagian baris menunjuk **produk menu** (bukan barang beli) → menyesatkan;
  * 2.404 stock move pembelian & JE-nya tidak menyebut vendor mana pun.

Yang dilakukan (semua metadata — nominal jurnal TIDAK berubah):
  1. buat vendor baru bergaya supplier Makassar untuk kategori yang belum punya
     (mis. `PT Sumber Plastik`, `UD Tahu Tempe Sehati`, `UD Bumbu & Sambal Pasar Terong`);
  2. pastikan tiap **bahan** punya supplierinfo: harga disinkronkan ke `standard_price`,
     `delay` 1 hari (fresh: ayam/tahu/tempe/telur) atau 3 hari (dry);
  3. (opsional `CLEAN_MENU=1`) hapus baris supplierinfo milik produk **menu** (bukan barang beli);
  4. tempel `partner_id` vendor pada stock move pembelian + baris jurnalnya.

Jalankan (default DRY-RUN):
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 \
    --db_user odoo --db_password odoo --log-level=warn" < scripts/perbaikan_13_vendor_supplier.py

Eksekusi:
  RUN=1 su odoo -s /bin/bash -c "odoo shell ..." < scripts/perbaikan_13_vendor_supplier.py
  RUN=1 CLEAN_MENU=1 ...   # sekaligus bersihkan baris supplier produk menu

Catatan: jalankan skrip ini SEBELUM period lock (F3) karena ia menulis ke jurnal Jun–Agu.
"""
import os
from collections import defaultdict

RUN = os.environ.get("RUN") == "1"
CLEAN_MENU = os.environ.get("CLEAN_MENU") == "1"

say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))

cr = env.cr
Partner = env["res.partner"]
PT = env["product.template"]
SI = env["product.supplierinfo"]

# ---------------------------------------------------------------- pemetaan vendor
# Hanya untuk bahan yang BELUM punya supplier (+ melengkapi kategori). Vendor lama
# (UD Berkah Tani, CV Aneka Kemasan Utama, Toko Bahan Kue Andalan, CV Sumber Pangan
# Makassar, PT Sinar Niaga Abadi) tetap dipakai apa adanya.
NEW_VENDORS = [
    ("PT Sumber Plastik", "Jl. Perintis Kemerdekaan KM 15, Daya", "Plastik & kemasan sekali pakai", [
        "PLASTIK KLIP 8X5", "PLASTIK SEGEPOK", "KEMASAN GEPREK YUKSSS", "KEMASAN SEGEPOK",
        "MIKA BUNDAR", "KERTAS NASI KUNING", "PEMBUNGKUS NASI PUTIH", "GELAS 22 OZ", "KANTONG GELAS 1",
    ]),
    ("UD Tahu Tempe Sehati", "Jl. Toddopuli Raya Timur, Panakkukang", "Tahu, tempe & olahan kedelai", [
        "TAHU", "TEMPE",
    ]),
    ("UD Bumbu & Sambal Pasar Terong", "Pasar Terong, Wajo", "Bumbu dapur, sambal & saus", [
        "BUMBU C", "BUMBU MARINASI", "GARAM HALUS", "CUKA", "KECAP ABC", "SAOS TIRAM",
        "SAMBAL TOMAT MALINO",
    ]),
    ("Toko Bahan Kue Andalan", None, None, [            # vendor lama → dipakai untuk bubuk minuman
        "BUBUK ORANGES", "BUBUK BLACKCURRENT",
    ]),
]
FALLBACK_VENDOR = ("CV Sumber Rejeki Makassar", "Jl. Rappocini Raya, Makassar", "Supplier umum bahan dapur")

say("=" * 110)
say("F3b — VENDOR & SUPPLIERINFO | RUN=%s | CLEAN_MENU=%s" % (RUN, CLEAN_MENU))
say("=" * 110)

# ---------------------------------------------------------------- 1) bahan yang benar-benar dibeli
cr.execute("""
    SELECT DISTINCT pt.id, pt.name->>'en_US', pt.is_storable, pc.name
    FROM stock_move sm
    JOIN stock_location sl ON sl.id = sm.location_id
    JOIN product_product pp ON pp.id = sm.product_id
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    JOIN product_category pc ON pc.id = pt.categ_id
    WHERE sl.usage = 'supplier' AND sm.state = 'done'
""")
purchased = {r[0]: {"name": r[1], "storable": r[2], "categ": r[3]} for r in cr.fetchall()}
say("")
say("[1] Produk yang pernah dibeli (punya mutasi dari lokasi supplier): %d" % len(purchased))

# supplierinfo existing per produk
existing_si = defaultdict(list)
for si in SI.search([]):
    if si.product_tmpl_id:
        existing_si[si.product_tmpl_id.id].append(si)

have_supplier = {tid for tid in purchased if existing_si.get(tid)}
missing_supplier = sorted(set(purchased) - have_supplier, key=lambda t: purchased[t]["name"])
say("    punya supplierinfo : %d" % len(have_supplier))
say("    BELUM punya        : %d -> %s" % (len(missing_supplier), ", ".join(purchased[t]["name"] for t in missing_supplier)))

# ---------------------------------------------------------------- 2) vendor baru yang kurang
say("")
say("[2] Vendor yang akan dipakai (nama dummy gaya supplier Makassar)")
cr.execute("SELECT id, name FROM res_partner WHERE is_company AND supplier_rank > 0 ORDER BY name")
vendor_rows = cr.fetchall()
say("    sudah ada: %s" % ", ".join(n for _, n in vendor_rows))

plan_assign = {}          # tmpl_id -> (vendor_name, alasan)
if missing_supplier:
    for vname, street, note, products in NEW_VENDORS:
        for pname in products:
            for tid in missing_supplier:
                if purchased[tid]["name"] == pname:
                    plan_assign[tid] = vname
    # sisa yang belum dipetakan → fallback umum
    for tid in missing_supplier:
        plan_assign.setdefault(tid, FALLBACK_VENDOR[0])

say("")
if plan_assign:
    grouped = defaultdict(list)
    for tid, vname in plan_assign.items():
        grouped[vname].append(purchased[tid]["name"])
    for vname in sorted(grouped):
        tag = "BARU " if vname in [v[0] for v in NEW_VENDORS] + [FALLBACK_VENDOR[0]] else "lama "
        say("    [%s] %-34s <- %s" % (tag, vname, ", ".join(sorted(grouped[vname]))))
else:
    say("    semua bahan sudah punya supplier — tidak ada vendor baru yang dibutuhkan.")

# ---------------------------------------------------------------- 3) tag move pembelian
cr.execute("""
    SELECT sm.id, pt.id, pt.name->>'en_US', sm.account_move_id
    FROM stock_move sm
    JOIN stock_location sl ON sl.id = sm.location_id
    JOIN product_product pp ON pp.id = sm.product_id
    JOIN product_template pt ON pt.id = pp.product_tmpl_id
    WHERE sl.usage = 'supplier' AND sm.state = 'done'
""")
moves = cr.fetchall()
move_by_tmpl = defaultdict(list)
for mid, tid, nm, je in moves:
    move_by_tmpl[tid].append((mid, je))
say("")
say("[3] Stock move pembelian yang akan diberi nama vendor: %d move (%d produk)" % (len(moves), len(move_by_tmpl)))
cr.execute("""
    SELECT COUNT(*) FROM account_move_line aml
    JOIN account_move am ON am.id = aml.move_id
    WHERE am.id IN (SELECT DISTINCT sm.account_move_id FROM stock_move sm
                    JOIN stock_location sl ON sl.id = sm.location_id
                    WHERE sl.usage = 'supplier' AND sm.state = 'done')
""")
n_lines = cr.fetchone()[0]
say("    baris jurnal yang ikut ditandai vendor: %d" % n_lines)

# baris supplierinfo untuk produk MENU (bukan barang beli)
menu_si = [si for si in SI.search([]) if si.product_tmpl_id and not si.product_tmpl_id.is_storable]
say("")
say("[4] Baris supplierinfo pada produk MENU (non-storable) = %d %s"
    % (len(menu_si), "(akan dihapus)" if CLEAN_MENU else "(dibiarkan; set CLEAN_MENU=1 untuk membersihkan)"))

# harga supplierinfo bahan yang tidak sinkron dengan standard_price
stale = []
for tid in have_supplier:
    sp = PT.browse(tid).standard_price
    for si in existing_si[tid]:
        if abs((si.price or 0.0) - sp) > 0.01:
            stale.append((si, purchased[tid]["name"], si.partner_id.name, si.price, sp))
say("[5] Baris supplierinfo harga ≠ standard_price: %d %s" % (len(stale), "(akan disinkronkan)"))

if not RUN:
    say("")
    say("DRY-RUN — tidak ada data ditulis. Jalankan RUN=1 untuk eksekusi.")
    env.cr.rollback()
    import sys
    sys.exit(0)

# ---------------------------------------------------------------- EKSEKUSI
Country = env["res.country"].search([("code", "=", "ID")], limit=1)
created_vendors = {}
for vname, street, note, _products in NEW_VENDORS + [(FALLBACK_VENDOR[0], FALLBACK_VENDOR[1], FALLBACK_VENDOR[2], [])]:
    p = Partner.search([("name", "=", vname), ("is_company", "=", True)], limit=1)
    if not p:
        code = "".join(w[0] for w in vname.split()[:3]).upper()
        p = Partner.create({
            "name": vname, "is_company": True, "supplier_rank": 1, "city": "Makassar",
            "street": street, "country_id": Country.id, "ref": code if code else False,
            "comment": note or "",
        })
    created_vendors[vname] = p
env.cr.commit()
say("")
say("  vendor tersedia: %s" % ", ".join(sorted(created_vendors)))

# 1) supplierinfo untuk bahan yang belum punya + sinkron harga yang basi
n_created = n_synced = 0
for tid in plan_assign:
    vname = plan_assign[tid]
    vendor = created_vendors.get(vname) or Partner.search([("name", "=", vname)], limit=1)
    tmpl = PT.browse(tid)
    price = tmpl.standard_price
    vals = {
        "partner_id": vendor.id, "product_tmpl_id": tid, "price": price,
        "min_qty": 1.0, "delay": 1 if purchased[tid]["categ"] == "Bahan Baku Food" else 3,
        "sequence": 1,
    }
    if existing_si.get(tid):
        si = existing_si[tid][0]
        si.write({"price": price, "partner_id": si.partner_id.id})
        n_synced += 1
    else:
        SI.create(vals)
        n_created += 1
for si, _nm, _v, old, sp in stale:
    si.write({"price": sp})
    n_synced += 1
env.cr.commit()
say("  supplierinfo baru: %d | baris harga disinkronkan: %d" % (n_created, n_synced))

# 2) bersihkan baris supplierinfo produk menu
if CLEAN_MENU and menu_si:
    for si in menu_si:
        si.unlink()
    env.cr.commit()
    say("  baris supplierinfo produk menu dihapus: %d" % len(menu_si))

# 3) tempel vendor pada stock move + baris jurnal
#    vendor utama per produk = supplierinfo dengan id terkecil (relasi lama diprioritaskan).
#    Diambil ulang via SQL karena baris supplierinfo produk menu sudah dihapus di atas.
cr.execute("SELECT product_tmpl_id, MIN(partner_id) FROM product_supplierinfo GROUP BY 1")
vendor_of_tmpl = {tid: Partner.browse(pid) for tid, pid in cr.fetchall()}
n_move = n_line = 0
untagged = []
for tid, pairs in move_by_tmpl.items():
    vendor = vendor_of_tmpl.get(tid)
    if not vendor:
        untagged.extend(pairs)
        continue
    move_ids = [p[0] for p in pairs]
    je_ids = [p[1] for p in pairs if p[1]]
    cr.execute("UPDATE stock_move SET partner_id = %s WHERE id IN %s", (vendor.id, tuple(move_ids)))
    n_move += len(move_ids)
    if je_ids:
        cr.execute("UPDATE account_move_line SET partner_id = %s WHERE move_id IN %s", (vendor.id, tuple(je_ids)))
        n_line += cr.rowcount
env.cr.commit()
say("  stock move ditandai vendor: %d | baris jurnal: %d%s"
    % (n_move, n_line, ("" if not untagged else " | tanpa vendor: %d" % len(untagged))))

# ---------------------------------------------------------------- VERIFIKASI
say("")
say("[VERIFIKASI]")
cr.execute("""
    SELECT p.name, COUNT(DISTINCT si.id), COUNT(DISTINCT si.product_tmpl_id)
    FROM product_supplierinfo si JOIN res_partner p ON p.id = si.partner_id
    GROUP BY p.name ORDER BY 2 DESC, 1
""")
for nm, n_si, n_tmpl in cr.fetchall():
    say("    %-34s supplierinfo %-4d produk %d" % (nm, n_si, n_tmpl))
cr.execute("""
    SELECT COUNT(*) FROM stock_move sm JOIN stock_location sl ON sl.id = sm.location_id
    WHERE sl.usage = 'supplier' AND sm.state = 'done' AND sm.partner_id IS NULL
""")
say("    stock move pembelian tanpa vendor: %d" % cr.fetchone()[0])
cr.execute("""
    SELECT COUNT(*) FROM product_supplierinfo si JOIN product_template pt ON pt.id = si.product_tmpl_id
    WHERE NOT pt.is_storable
""")
say("    supplierinfo pada produk menu (non-storable): %d" % cr.fetchone()[0])
cr.execute("SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id WHERE am.state='posted'")
d, k = cr.fetchone()
say("    TB debit %s = credit %s (diff %s)" % (money(d), money(k), money(float(d or 0) - float(k or 0))))
say("=" * 110)
