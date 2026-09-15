# -*- coding: utf-8 -*-
"""
juni_juli_118_review_margin_full.py — TINJAUAN HARGA & MARGIN, CAKUPAN PENUH (READ-ONLY).

KENAPA ADA SKRIP INI
  Laporan `HARGA_HITUNGAN_REVIEW.md` sebelumnya hanya memuat **93 dari 106** produk POS —
  bolong 19 produk (mis. `PKG MEVVAH (…)`, `GEPREK ORIGINAL PAHA BAWAH`, `TELUR CRISPY`).
  Akibatnya daftar "menu margin < 40%" yang disusun dari laporan itu **tidak lengkap**.
  Skrip ini menggantinya dengan cakupan 100% produk POS + satu kolom baru yang penting:

    "bahan terverifikasi" = berapa % HPP menu yang komponennya PUNYA harga di berkas klien
                            `HARGA BAHAN BAKU GUDANG.xlsx`. Makin rendah %, makin tidak
                            layak marginnya dipercaya (bisa jadi sebenarnya lebih sehat).

READ-ONLY — tidak menulis apa pun ke DB.  Menulis dua artefak:
  • HARGA_HITUNGAN_REVIEW.md   (ditimpa, cakupan penuh)
  • import_data/margin_full_2026-09-13.csv

  jalankan: su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/juni_juli_118_review_margin_full.py
"""
import csv
import os
import re

import openpyxl

XLSX = os.environ.get("XLSX") or next(
    (p for p in ("product_photos/data sheet master/HARGA BAHAN BAKU GUDANG.xlsx",
                 "/root/odoo/product_photos/data sheet master/HARGA BAHAN BAKU GUDANG.xlsx")
     if os.path.exists(p)), None)
PLAN = "import_data/pricelist_dinein_plan.csv"
PLATFORM_PRICELIST = "Harga Platform Online"
TARGET = 40.0

cr = env.cr
say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", str(s or "").upper())


# ---------- 1. harga bahan yang bersumber dari berkas klien ----------
klien = set()
if XLSX:
    wb = openpyxl.load_workbook(XLSX, data_only=True, read_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    hi = next(i for i, r in enumerate(rows[:8]) if any((c or "") == "Nama Barang" for c in r))
    hdr = [("" if c is None else str(c).strip()) for c in rows[hi]]
    i_nama = hdr.index("Nama Barang")
    i_kecil = next(j for j, h in enumerate(hdr) if h.upper().startswith("HRG/SAT"))
    for r in rows[hi + 1:]:
        cells = list(r) + [None] * 8
        if not cells[i_nama]:
            continue
        try:
            float(cells[i_kecil])
        except (TypeError, ValueError):
            continue
        klien.add(norm(cells[i_nama]))
ALIAS = {"BUBUK LEMON TEA": "LEMON TEA", "AIR GELAS": "AIR MINERAL GELAS",
         "KEMASAN SEGEPOK": "KEMASAN SEGEPOK (BIASA)", "PLASTIK KLIP 8X5": "PLASTIK KLIP 5X8",
         "MIKA BUNDAR": "MIKA BURGER", "AYAM CUT 2": "AYAM CUT 2"}


def bersumber(nama):
    return norm(nama) in klien or norm(ALIAS.get(nama.upper(), "")) in klien


# ---------- 2. asal harga (dari berkas rencana) ----------
asal = {}
if os.path.exists(PLAN):
    for r in csv.DictReader(open(PLAN, encoding="utf-8")):
        asal[r["menu"].strip()] = r.get("sumber", "").strip()

# ---------- 3. harga platform (pricelist) ----------
cr.execute("SELECT id FROM product_pricelist WHERE name->>'en_US' = %s", (PLATFORM_PRICELIST,))
row = cr.fetchone()
platform = {}
if row:
    cr.execute("""
        SELECT pt.name->>'en_US', pi.fixed_price
          FROM product_pricelist_item pi
          LEFT JOIN product_product pp ON pp.id = pi.product_id
          LEFT JOIN product_template pt ON pt.id = COALESCE(pp.product_tmpl_id, pi.product_tmpl_id)
         WHERE pi.pricelist_id = %s AND pi.compute_price = 'fixed'
    """, (row[0],))
    for n, px in cr.fetchall():
        if n:
            platform[n] = float(px or 0)

# ---------- 4. produk POS ----------
cr.execute("""
    SELECT pt.id, pp.id, (pt.name->>'en_US'), pt.list_price, COALESCE(pc.name, ''),
           COALESCE((uu.name->>'en_US'), '')
      FROM product_template pt
      JOIN product_product pp ON pp.product_tmpl_id = pt.id
      LEFT JOIN product_category pc ON pc.id = pt.categ_id
      LEFT JOIN uom_uom uu ON uu.id = pt.uom_id
     WHERE pt.available_in_pos AND pt.active AND pt.sale_ok
     ORDER BY 3
""")
produk = cr.fetchall()

hasil = []
for tmpl_id, pp_id, nama, jual, kat, uom in produk:
    jual = float(jual or 0)
    cr.execute("""
        SELECT bl.product_id, (ct.name->>'en_US'), bl.product_qty,
               COALESCE((cp.standard_price->>'1')::numeric, 0)
          FROM mrp_bom b
          JOIN mrp_bom_line bl ON bl.bom_id = b.id
          JOIN product_product cp ON cp.id = bl.product_id
          JOIN product_template ct ON ct.id = cp.product_tmpl_id
         WHERE b.product_tmpl_id = %s AND b.active
    """, (tmpl_id,))
    baris = cr.fetchall()
    if baris:
        hpp = sum(float(q) * float(h) for _, _, q, h in baris)
        ver = sum(float(q) * float(h) for _, n, q, h in baris if bersumber(n))
        kurang = sorted(("%s (%.0f%%)" % (n, (float(q) * float(h) / hpp * 100) if hpp else 0))
                        for _, n, q, h in baris if not bersumber(n) and float(q) * float(h) > 0)
        dasar = "resep"
    else:
        cr.execute("SELECT COALESCE((standard_price->>'1')::numeric, 0) FROM product_product WHERE id=%s",
                   (pp_id,))
        hpp = float(cr.fetchone()[0] or 0)
        ver = hpp if bersumber(nama) else 0.0
        kurang = [] if bersumber(nama) else ["harga beli produk itu sendiri"]
        dasar = "harga beli"
    m = (1 - hpp / jual) * 100 if jual else 0.0
    px = platform.get(nama)
    mp = ((px - hpp - px * 0.10) / px * 100) if px else None
    hasil.append({"nama": nama, "jual": jual, "hpp": hpp, "dasar": dasar, "margin": m,
                  "platform": px, "margin_platform": mp, "asal": asal.get(nama, "(tidak ada di plan)"),
                  "ver": (ver / hpp * 100) if hpp else 0.0, "kurang": kurang, "kat": kat, "uom": uom})

hasil.sort(key=lambda r: r["margin"])
rendah = [r for r in hasil if r["jual"] > 0 and r["margin"] < TARGET]

# ---------- 5. tulis MD ----------
L = []
L.append("# Tinjauan Harga & Margin — cakupan penuh (%d produk POS)" % len(hasil))
L.append("")
L.append("> Sumber: DB `Test1` setelah §33 (harga bahan klien diterapkan). Dibuat oleh")
L.append("> `scripts/juni_juli_118_review_margin_full.py` — menggantikan laporan lama yang")
L.append("> hanya memuat 93 dari 106 produk POS.")
L.append(">")
L.append("> HPP = Σ(qty komponen × harga beli) dari resep aktif. Produk tanpa resep → harga beli")
L.append("> produk itu sendiri. Angka kasar, bukan FIFO real-time.")
L.append("> Platform = harga +10%; margin platform = (platform − HPP − komisi 10%) / platform.")
L.append("")
L.append("## Kolom kunci: \"bahan terverifikasi\"")
L.append("")
L.append("Berapa **% dari HPP** yang komponennya punya harga di `HARGA BAHAN BAKU GUDANG.xlsx`")
L.append("(berkas klien). Makin rendah %, makin **tidak layak** marginnya dipercaya: harga")
L.append("komponen itu masih isian agent, jadi HPP bisa lebih rendah dari yang tampak dan")
L.append("margin sebenarnya bisa lebih sehat.")
L.append("")
vb = [r for r in hasil if r["hpp"] > 0]
L.append("| bahan terverifikasi | jumlah produk |")
L.append("|---|---:|")
for lo, hi in ((99.5, 100.1), (80, 99.5), (50, 80), (0.1, 50), (-0.1, 0.1)):
    n = sum(1 for r in vb if lo <= r["ver"] < hi)
    label = "100% (semua komponen bersumber)" if lo > 99 else \
            "80–99%" if lo == 80 else "50–79%" if lo == 50 else "1–49%" if lo == 0.1 else "0% (tanpa resep/harga beli)"
    L.append("| %s | %d |" % (label, n))
L.append("")
L.append("## Margin < %d%% — %d produk" % (TARGET, len(rendah)))
L.append("")
L.append("| menu | jual | HPP | margin | bahan terverifikasi | platform | margin platform | asal harga |")
L.append("|---|---:|---:|---:|---:|---:|---:|---|")
for r in rendah:
    L.append("| %s | %s | %s | **%.1f%%** | %.0f%% | %s | %s | %s |" % (
        r["nama"], money(r["jual"]), money(r["hpp"]), r["margin"], r["ver"],
        money(r["platform"]) if r["platform"] else "—",
        ("%.1f%%" % r["margin_platform"]) if r["margin_platform"] is not None else "—",
        r["asal"]))
L.append("")
L.append("## Semua %d produk POS (urut margin terendah)" % len(hasil))
L.append("")
L.append("| menu | jual | HPP | dasar HPP | margin | verifikasi | platform | margin platform | asal harga | komponen tanpa harga klien |")
L.append("|---|---:|---:|---|---:|---:|---:|---:|---|---|")
for r in hasil:
    L.append("| %s | %s | %s | %s | %.1f%% | %.0f%% | %s | %s | %s | %s |" % (
        r["nama"], money(r["jual"]), money(r["hpp"]), r["dasar"], r["margin"], r["ver"],
        money(r["platform"]) if r["platform"] else "—",
        ("%.1f%%" % r["margin_platform"]) if r["margin_platform"] is not None else "—",
        r["asal"], ", ".join(r["kurang"]) if r["kurang"] else "—"))
L.append("")
with open("HARGA_HITUNGAN_REVIEW.md", "w", encoding="utf-8") as f:
    f.write("\n".join(L) + "\n")

with open("import_data/margin_full_2026-09-13.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["nama", "jual", "hpp", "dasar", "margin", "platform",
                                      "margin_platform", "asal", "ver", "kurang"])
    w.writeheader()
    for r in hasil:
        d = dict(r)
        d["kurang"] = " | ".join(r["kurang"])
        w.writerow({k: d[k] for k in w.fieldnames})

say("=" * 118)
say("TINJAUAN HARGA & MARGIN — CAKUPAN PENUH (READ-ONLY)")
say("=" * 118)
say("produk POS ditinjau        : %d" % len(hasil))
say("harga bahan bersumber klien: %d nama (%s)" % (len(klien), XLSX or "berkas tidak ditemukan"))
say("")
say("margin < %d%%: %d produk" % (TARGET, len(rendah)))
say("   %-46s %10s %12s %8s %8s" % ("menu", "jual", "HPP", "margin", "terverif"))
say("   " + "-" * 90)
for r in rendah:
    say("   %-46s %s %s  %6.1f%%  %6.0f%%" % (r["nama"][:45], money(r["jual"]), money(r["hpp"]),
                                             r["margin"], r["ver"]))
say("")
say("   yang marginnya TIDAK layak dipercaya (verifikasi < 50%):")
for r in rendah:
    if r["ver"] < 50:
        say("      - %-40s verifikasi %.0f%%  | tanpa harga klien: %s" % (
            r["nama"][:39], r["ver"], ", ".join(r["kurang"])))
say("")
say("ditulis: HARGA_HITUNGAN_REVIEW.md + import_data/margin_full_2026-09-13.csv")
say("=" * 118)
env.cr.rollback()
