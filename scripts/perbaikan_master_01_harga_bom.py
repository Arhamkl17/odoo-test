# -*- coding: utf-8 -*-
"""
perbaikan_master_01_harga_bom.py — PERBAIKAN HARGA JUAL & BOM (master data).

Lanjutan inspeksi `recon_kesiapan_harga_bom.py` + `recon_kesiapan_detail.py`.
Menjalankan 3 hal yang sudah disetujui pemilik (13 Sep 2026):

  FASE A — BERSIHKAN DUPLIKAT & ARTEFAK YATIM
           2 pasang produk kembar (simpan versi PRODUK KLIEN) + 5 produk yatim.
  FASE B — ISI BIAYA `SAMBAL TOMAT MALINO` (bahan tmpl 666) dengan perkiraan wajar
           = rata-rata harga 3 sambal lain yang sudah bersumber dari berkas klien.
  FASE C — SESUAIKAN HARGA menu yang harganya HASIL HITUNGAN AGEN
           (`komponen` / `komponen+lantai` / `lantai`) sampai margin >= 45%.
           Harga yang bersumber dari berkas klien (`klien`) TIDAK disentuh.

Sifat:
  * dry-run default — tanpa `RUN=1` tidak menulis apa pun
  * idempotent — dijalankan ulang: 0 perubahan
  * satu transaksi, `env.cr.commit()` hanya di akhir (kalau RUN=1)
  * tidak menyentuh transaksi/ledger (kebetulan semuanya sudah 0)

  RUN=1 su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http \
    --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
    < scripts/perbaikan_master_01_harga_bom.py

  Backup sebelum eksekusi: pg_dump -Fc Test1 (lihat CARA di dokumen spec §35.1)
"""
import csv
import math
import os
import re

import openpyxl

RUN = os.environ.get("RUN") == "1"
TARGET = 45.0          # margin minimum (HPP / harga jual)
PAKAI_VERIF = 80.0     # minimal % HPP yang komponennya bersumber berkas klien

cr = env.cr
say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))
SEP = "=" * 118

PT = env["product.template"]
PP = env["product.product"]
PLI = env["product.pricelist.item"]
BOM = env["mrp.bom"]
IMD = env["ir.model.data"]

PLAN = "import_data/pricelist_dinein_plan.csv"

# ------------------------------------------------------------------ util
def norm(s):
    return re.sub(r"[^A-Z0-9]", "", str(s or "").upper())


XLSX = next((p for p in ("product_photos/data sheet master/HARGA BAHAN BAKU GUDANG.xlsx",
                         "/root/odoo/product_photos/data sheet master/HARGA BAHAN BAKU GUDANG.xlsx")
             if os.path.exists(p)), None)
klien = set()
if XLSX:
    wb = openpyxl.load_workbook(XLSX, data_only=True, read_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    hi = next(i for i, r in enumerate(rows[:8]) if any((c or "") == "Nama Barang" for c in r))
    hdr = [("" if c is None else str(c).strip()) for c in rows[hi]]
    i_nm = hdr.index("Nama Barang")
    i_kc = next(j for j, h in enumerate(hdr) if h.upper().startswith("HRG/SAT"))
    for r in rows[hi + 1:]:
        c = list(r) + [None] * 8
        if not c[i_nm]:
            continue
        try:
            float(c[i_kc])
        except (TypeError, ValueError):
            continue
        klien.add(norm(c[i_nm]))
ALIAS = {"BUBUK LEMON TEA": "LEMON TEA", "AIR GELAS": "AIR MINERAL GELAS",
         "KEMASAN SEGEPOK": "KEMASAN SEGEPOK (BIASA)", "PLASTIK KLIP 8X5": "PLASTIK KLIP 5X8",
         "MIKA BUNDAR": "MIKA BURGER"}


def bersumber(nama):
    return norm(nama) in klien or norm(ALIAS.get(str(nama).upper(), "")) in klien


sumber = {}
if os.path.exists(PLAN):
    for r in csv.DictReader(open(PLAN, encoding="utf-8")):
        sumber[r["menu"].strip()] = r.get("sumber", "").strip()

say(SEP)
say("PERBAIKAN HARGA JUAL & BOM — %s — %s" % ("EKSEKUSI (RUN=1)" if RUN else "DRY-RUN", PLAN))
say(SEP)
if not RUN:
    say("  (dry-run: tidak ada yang ditulis. Jalankan dengan RUN=1 untuk menerapkan.)")
say("")


def hpp_dan_verif(tmpl):
    """→ (hpp, verif_pct, jumlah baris resep)."""
    cr.execute("""
        SELECT bl.product_qty, (ct.name->>'en_US'),
               COALESCE((cp.standard_price->>'1')::numeric,0)
          FROM mrp_bom b JOIN mrp_bom_line bl ON bl.bom_id=b.id
          JOIN product_product cp ON cp.id=bl.product_id
          JOIN product_template ct ON ct.id=cp.product_tmpl_id
         WHERE b.product_tmpl_id=%s AND b.active
    """, (tmpl,))
    baris = cr.fetchall()
    if not baris:
        cr.execute("SELECT COALESCE((pp.standard_price->>'1')::numeric,0) FROM product_product pp "
                   "WHERE pp.product_tmpl_id=%s LIMIT 1", (tmpl,))
        row = cr.fetchone()
        h = float(row[0] or 0) if row else 0.0
        cr.execute("SELECT (pt.name->>'en_US') FROM product_template pt WHERE pt.id=%s", (tmpl,))
        nm = cr.fetchone()
        return h, (100.0 if bersumber(nm and nm[0]) else 0.0), 0
    hpp = sum(float(q) * float(h) for q, _, h in baris)
    ver = sum(float(q) * float(h) for q, n, h in baris if bersumber(n))
    return hpp, ((ver / hpp * 100) if hpp else 0.0), len(baris)


# ================================================================== FASE A
say(SEP)
say("FASE A — BERSIHKAN DUPLIKAT & ARTEFAK YATIM")
say(SEP)
say("")
HAPUS = [
    (630, "ghost kembar `PAKET KULIT CRISPY` → disimpan `PAKET KULIT CRISPY + NASI + MINUM` (572)"),
    (618, "ghost kembar `PKG INDOMIE GEPREK SAMBAL LOKAL` → disimpan `PKG MIE (…)` (585)"),
    (584, "duplikat MEVVAH arsip → disimpan `PAKET MEVVAH BERDUA` (625)"),
    (463, "produk sambal menu LAMA `SAMBAL IJO PADANG` (tak dipakai resep/pricelist/POS)"),
    (464, "produk sambal menu LAMA `SAMBAL RICA MANADO`"),
    (465, "produk sambal menu LAMA `SAMBAL KOREK SURABAYA`"),
    (655, "`Gift Card` duplikat (tmpl 653 yang dipakai POS)"),
]
# tmpl 655 dipakai `loyalty_reward.discount_line_product_id` (reward 1) → alihkan ke
# varian `Gift Card` asli (tmpl 653 / pp 642) sebelum dihapus.
REPOINT = {655: 642}
ada = []
for tmpl, alasan in HAPUS:
    t = PT.with_context(active_test=False).browse(tmpl)
    if not t.exists():
        say("   %-4s sudah tidak ada (idempotent) — %s" % (tmpl, alasan))
        continue
    jml_bom = BOM.with_context(active_test=False).search_count([("product_tmpl_id", "=", tmpl)])
    jml_item = PLI.search_count([("product_tmpl_id", "=", tmpl)])
    say("   HAPUS tmpl=%-4s %-46s bom=%d item_pricelist=%d" % (
        tmpl, t.display_name[:46], jml_bom, jml_item))
    say("         alasan: %s" % alasan)
    ada.append((tmpl, t))

if ada:
    # GUARD: pastikan tidak ada referensi transaksi yang menggantung
    ids = tuple(t.id for _, t in ada)
    cr.execute("""SELECT count(*) FROM mrp_bom_line l JOIN product_product pp ON pp.id=l.product_id
                   WHERE pp.product_tmpl_id IN %s""", (ids,))
    g1 = cr.fetchone()[0]
    cr.execute("""SELECT count(*) FROM pos_order_line l JOIN product_product pp ON pp.id=l.product_id
                   WHERE pp.product_tmpl_id IN %s""", (ids,))
    g2 = cr.fetchone()[0]
    cr.execute("""SELECT count(*) FROM stock_move m JOIN product_product pp ON pp.id=m.product_id
                   WHERE pp.product_tmpl_id IN %s""", (ids,))
    g3 = cr.fetchone()[0]
    cr.execute("""SELECT count(*) FROM account_move_line aml JOIN product_product pp ON pp.id=aml.product_id
                   WHERE pp.product_tmpl_id IN %s""", (ids,))
    g4 = cr.fetchone()[0]
    say("")
    say("   GUARD referensi: baris BOM=%d · pos_order_line=%d · stock_move=%d · account_move_line=%d" % (
        g1, g2, g3, g4))
    if g1 or g2 or g3 or g4:
        raise Exception("GUARD GAGAL — ada referensi transaksi, berhenti tanpa menulis.")
    say("   GUARD LULUS (semua 0).")

    if RUN:
        for tmpl, tujuan in REPOINT.items():
            cr.execute("""UPDATE loyalty_reward SET discount_line_product_id=%s
                           WHERE discount_line_product_id IN
                                 (SELECT id FROM product_product WHERE product_tmpl_id=%s)""",
                       (tujuan, tmpl))
            if cr.rowcount:
                say("   REPOINT loyalty_reward: %d baris pp→%s (tmpl %s dihapus)" % (
                    cr.rowcount, tujuan, tmpl))
        for tmpl, t in ada:
            BOM.with_context(active_test=False).search(
                [("product_tmpl_id", "=", tmpl)]).unlink()
            PLI.search([("product_tmpl_id", "=", tmpl)]).unlink()
            env["product.supplierinfo"].search([("product_tmpl_id", "=", tmpl)]).unlink()
            IMD.search([("model", "=", "product.template"), ("res_id", "=", tmpl)]).unlink()
            varian = PP.with_context(active_test=False).search([("product_tmpl_id", "=", tmpl)])
            if varian:
                IMD.search([("model", "=", "product.product"),
                            ("res_id", "in", varian.ids)]).unlink()
            t.unlink()
        say("   → %d produk + BOM + item pricelist DIHAPUS." % len(ada))
else:
    say("   (tidak ada yang perlu dihapus)")

# ================================================================== FASE B
say("")
say(SEP)
say("FASE B — BIAYA `SAMBAL TOMAT MALINO` (bahan tmpl 666)")
say(SEP)
say("")
SAMBA_BARU = 666
SAMBA_ACUAN = [650, 651, 652]          # Rica · Ijo · Korek — harga bersumber klien
biaya = []
for tmpl in SAMBA_ACUAN:
    cr.execute("SELECT (pt.name->>'en_US'), COALESCE((pp.standard_price->>'1')::numeric,0) "
               "FROM product_template pt JOIN product_product pp ON pp.product_tmpl_id=pt.id "
               "WHERE pt.id=%s", (tmpl,))
    row = cr.fetchone()
    if row:
        biaya.append(float(row[1] or 0))
        say("   acuan: %-26s = %s /GRM" % (row[0], money(row[1])))
samba = PT.with_context(active_test=False).browse(SAMBA_BARU)
if samba.exists() and biaya:
    estimasi = round(sum(biaya) / len(biaya), 2)
    cr.execute("SELECT COALESCE((pp.standard_price->>'1')::numeric,0) FROM product_product pp "
               "WHERE pp.product_tmpl_id=%s LIMIT 1", (SAMBA_BARU,))
    kini = float(cr.fetchone()[0] or 0)
    say("")
    say("   estimasi = rata-rata 3 sambal = %s /GRM" % money(estimasi))
    say("   biaya sekarang = %s" % money(kini))
    if abs(kini - estimasi) < 0.005:
        say("   → sudah sama (idempotent), tidak diubah.")
    else:
        say("   → SET biaya tmpl 666 = %s" % money(estimasi))
        if RUN:
            var = PP.with_context(active_test=False).search([("product_tmpl_id", "=", SAMBA_BARU)])
            var.write({"standard_price": estimasi})
else:
    say("   (bahan tmpl 666 tidak ada — dilewati)")

# ================================================================== FASE C
say("")
say(SEP)
say("FASE C — HARGA MENU HASIL HITUNGAN AGEN → margin >= %.0f%%" % TARGET)
say(SEP)
say("")
say("   (harga bersumber `klien` dan `non-menu` TIDAK disentuh; HPP dgn verifikasi <%.0f%% dilewati)"
    % PAKAI_VERIF)
say("")

cr.execute("""
    SELECT pp.id, pt.id, (pt.name->>'en_US'), pt.list_price
      FROM product_template pt JOIN product_product pp ON pp.product_tmpl_id=pt.id
     WHERE pt.available_in_pos AND pt.active AND pt.sale_ok ORDER BY 3
""")
pos_rows = cr.fetchall()
hapus_ids = {t.id for _, t in ada}

ajust = []
for ppid, tmpl, nama, lpx in pos_rows:
    if tmpl in hapus_ids:
        continue
    src = sumber.get(nama, "")
    if src in ("klien", "non-menu"):
        continue
    px = float(lpx or 0)
    if px <= 0:
        continue
    hpp, ver, nline = hpp_dan_verif(tmpl)
    m = (1 - hpp / px) * 100
    if m >= TARGET or ver < PAKAI_VERIF or hpp <= 0:
        continue
    baru = math.ceil(hpp / (1 - TARGET / 100.0) / 500.0) * 500.0
    if baru <= px:
        baru = px + 500.0
    ajust.append((ppid, tmpl, nama, px, hpp, m, ver, baru, src))

say("   %-48s %10s %12s %8s %9s %10s" % ("menu", "jual", "HPP", "margin", "verif", "→ baru"))
say("   " + "-" * 108)
for ppid, tmpl, nama, px, hpp, m, ver, baru, src in sorted(ajust, key=lambda x: x[5]):
    say("   %-48s %10s %12s %7.1f%% %8.0f%% %10s" % (
        nama[:48], money(px), money(hpp), m, ver, money(baru)))
say("   → %d menu akan disesuaikan" % len(ajust))

if RUN and ajust:
    pl_norm = env["product.pricelist"].with_context(active_test=False).search(
        [("name", "=", "Harga Normal")], limit=1)
    pl_plat = env["product.pricelist"].with_context(active_test=False).search(
        [("name", "=", "Harga Platform Online")], limit=1)
    for ppid, tmpl, nama, px, hpp, m, ver, baru, src in ajust:
        PT.browse(tmpl).write({"list_price": baru})
        for pl in (pl_norm, pl_plat):
            if not pl:
                continue
            item = PLI.search([("pricelist_id", "=", pl.id), ("product_tmpl_id", "=", tmpl)])
            if not item:
                continue
            harga = baru if pl == pl_norm else math.ceil(baru * 1.10 / 500.0) * 500.0
            item.write({"fixed_price": harga, "compute_price": "fixed"})
    say("   → %d harga master + item `Harga Normal` & `Harga Platform Online` diperbarui." % len(ajust))

# ================================================================== VERIFIKASI
say("")
say(SEP)
say("VERIFIKASI")
say(SEP)
say("")
if RUN:
    env.flush_all()
cr.execute("SELECT count(*) FROM pos_order")
say("   transaksi pos_order                  : %s (harus 0)" % cr.fetchone()[0])
cr.execute("SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) FROM account_move_line")
d, k = cr.fetchone()
say("   buku besar debit/credit/diff         : %s / %s / %s" % (money(d), money(k), money(float(d) - float(k))))
say("   produk (template)                    : %d" % PT.with_context(active_test=False).search_count([]))
say("   BOM                                  : %d" % BOM.with_context(active_test=False).search_count([]))
cr.execute("""SELECT count(*) FROM product_template pt
               WHERE pt.available_in_pos AND pt.active AND pt.sale_ok""")
say("   produk POS aktif                     : %s" % cr.fetchone()[0])

say("")
say("   sisa margin < %.0f%% (harga agen, verif>=%.0f%%):" % (TARGET, PAKAI_VERIF))
sisa = []
for t in PT.search([("available_in_pos", "=", True), ("active", "=", True), ("sale_ok", "=", True)]):
    if t.id in hapus_ids:
        continue
    src = sumber.get(t.name, "")
    if src in ("klien", "non-menu"):
        continue
    hpp, ver, nline = hpp_dan_verif(t.id)
    px = float(t.list_price or 0)
    m = (1 - hpp / px) * 100 if px else 0
    if px > 0 and m < TARGET and ver >= PAKAI_VERIF:
        sisa.append((t.name, px, hpp, m))
for nama, px, hpp, m in sisa:
    say("      - %-44s jual=%-10s HPP=%-11s margin=%.1f%%" % (nama[:44], money(px), money(hpp), m))
say("      → %d menu%s" % (len(sisa), "" if not sisa else " (MASIH ADA — periksa!)"))

if RUN:
    env.cr.commit()
    say("")
    say("   COMMIT ✓")
else:
    env.cr.rollback()
    say("")
    say("   ROLLBACK (dry-run) — tidak ada perubahan.")
say(SEP)
