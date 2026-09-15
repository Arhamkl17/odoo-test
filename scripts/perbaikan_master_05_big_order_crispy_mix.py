# -*- coding: utf-8 -*-
"""
perbaikan_master_05_big_order_crispy_mix.py — LENGKAPI RESEP PAKET BIG ORDER CRISPY MIX (13 Sep 2026).

MASALAH (temuan audit `AUDIT_MASTER_DATA_2026-09-13.md` §8.5)
  `PAKET BIG ORDER CRISPY MIX` (tmpl 632) dijual **Rp 59.500**, tetapi resepnya hanya
  12 baris = **resep 1 porsi** `PAKET AYAM CRISPY` (yg dijual Rp 17.000) dikurangi bagian
  minuman. Akibatnya HPP hanya Rp 7.297,53 (margin 87,7%) — jauh di luar pola paket lain
  yang cost ratio-nya 46–53%.

  Berkas draft klien `mrp_bom Barang Combo.xlsx` sheet 'PAKET BIG ORDER CRISPY MIX' juga
  berisi 12 baris yang SAMA, dan paket ini TIDAK ada di sheet `FIX BOM GANTI COMBO`
  (32 produk) — jadi tidak ada sumber resmi untuk melengkapinya.

KEPUTUSAN PEMILIK (13 Sep 2026)
  "4 porsi crispy mix" → paket ini = **4 × resep 1 porsi PAKET AYAM CRISPY**.

  Resep acuan `PAKET AYAM CRISPY PAHA BAWAH` (tmpl 597) — 16 baris, HPP Rp 8.838,23 —
  dipakai apa adanya lalu dikalikan 4 (termasuk minuman: TEH MIX, AIR GALON, ES KRISTAL,
  PIPET). Ketiga varian crispy (596/597/598) resepnya identik, jadi susunan variannya
  tidak memengaruhi HPP.

  Hasil yang diharapkan: HPP 4 × 8.838,23 = **Rp 35.352,92** → margin **40,6%**
  (cost ratio 59,4%), sejalan dengan paket lain.

CATATAN DESAIN — kenapa resep RATA, bukan sub-kit
  Alternatif memakai `PAKET AYAM CRISPY` sebagai komponen (nested phantom) ditolak karena
  `standard_price` menu itu = Rp 7.692,20, TIDAK sama dengan HPP resepnya (Rp 8.838,23),
  sehingga HPP paket jadi salah. Paket lain di sistem ini (SEGEPOK BERLIMA,
  PAKET YUKSSS MABAR) juga rata. Kebetulan ini menghindari pula pola "resep datar"
  yang sudah dicatat sebagai temuan audit §3 B2.

  Idempotent (dijalankan ulang menghasilkan HPP yang sama). Dry-run penuh.
  Tidak menyentuh harga jual, pricelist, order, stok, atau jurnal.

  dry-run : su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/perbaikan_master_05_big_order_crispy_mix.py
  eksekusi: su odoo -s /bin/bash -c "RUN=1 odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/perbaikan_master_05_big_order_crispy_mix.py
"""
import os

RUN = os.environ.get("RUN") == "1"

MULT = float(os.environ.get("MULT") or 4)      # jumlah porsi
TARGET_MENU = "PAKET BIG ORDER CRISPY MIX"     # tmpl 632
REF_MENU = "PAKET AYAM CRISPY PAHA BAWAH"      # tmpl 597 — resep 1 porsi acuan
PL_NORMAL = 3

cr = env.cr
PT = env["product.template"]
BOM = env["mrp.bom"]

say = lambda m="": print(m)
money = lambda x: "{:>12,.2f}".format(float(x or 0))


def bom_of(tmpl):
    boms = BOM.search([("product_tmpl_id", "=", tmpl.id), ("active", "=", True)])
    return boms


def harga_jual(tmpl_id):
    cr.execute("SELECT fixed_price FROM product_pricelist_item "
               "WHERE pricelist_id=%s AND product_tmpl_id=%s LIMIT 1", (PL_NORMAL, tmpl_id))
    r = cr.fetchone()
    return float(r[0]) if r and r[0] is not None else 0.0


# ================================================================ GUARD
say("=" * 112)
say("LENGKAPI RESEP %s  (%s porsi)   |   RUN=%s   |   %s" % (
    TARGET_MENU, ("%g" % MULT), RUN, "TULIS" if RUN else "DRY-RUN"))
say("=" * 112)
say("")
say("[GUARD]")

t_target = PT.search([("name", "=", TARGET_MENU)])
t_ref = PT.search([("name", "=", REF_MENU)])
if len(t_target) != 1:
    raise SystemExit("!! %s: %d template (harus 1)" % (TARGET_MENU, len(t_target)))
if len(t_ref) != 1:
    raise SystemExit("!! %s: %d template (harus 1)" % (REF_MENU, len(t_ref)))
t_target, t_ref = t_target[0], t_ref[0]

bom_target = bom_of(t_target)
bom_ref = bom_of(t_ref)
if len(bom_target) != 1:
    raise SystemExit("!! %s: %d BOM aktif (harus 1)" % (TARGET_MENU, len(bom_target)))
if len(bom_ref) != 1:
    raise SystemExit("!! %s: %d BOM aktif (harus 1)" % (REF_MENU, len(bom_ref)))
bom_target, bom_ref = bom_target[0], bom_ref[0]

say("   %-34s tmpl=%-4s BOM=%-4s %d baris" % (
    TARGET_MENU, t_target.id, bom_target.id, len(bom_target.bom_line_ids)))
say("   %-34s tmpl=%-4s BOM=%-4s %d baris" % (
    REF_MENU, t_ref.id, bom_ref.id, len(bom_ref.bom_line_ids)))

# resep acuan → target (x MULT), urutan & struktur dipertahankan apa adanya
ref_lines = bom_ref.bom_line_ids.sorted(lambda l: l.id)
target_spec = []
for l in ref_lines:
    target_spec.append(dict(
        product=l.product_id,
        qty=round(float(l.product_qty or 0) * MULT, 4),
        uom=l.product_uom_id or l.product_id.uom_id,
    ))

# HPP target dihitung dari harga komponen
hpp_target = 0.0
for s in target_spec:
    hpp_target += s["qty"] * float(s["product"].standard_price or 0)

hpp_lama = sum(float(l.product_qty or 0) * float(l.product_id.standard_price or 0)
               for l in bom_target.bom_line_ids)
harga = harga_jual(t_target.id)

say("")
say("   resep acuan      : %d baris" % len(ref_lines))
say("   resep target     : %d baris (%d × %g)" % (len(target_spec), len(ref_lines), MULT))
say("   HPP sekarang     : %s   (jual %s → margin %.1f%%)" % (
    money(hpp_lama), money(harga), (1 - hpp_lama / harga) * 100 if harga else 0))
say("   HPP sesudah      : %s   (jual %s → margin %.1f%%)" % (
    money(hpp_target), money(harga), (1 - hpp_target / harga) * 100 if harga else 0))
say("   selisih HPP      : %+.2f" % (hpp_target - hpp_lama))

say("")
say("   %-22s %-6s %12s %12s" % ("komponen", "UoM", "qty/lama", "qty/baru"))
say("   " + "-" * 58)
for s in target_spec:
    lama = sum(float(l.product_qty or 0) for l in bom_target.bom_line_ids
               if l.product_id.id == s["product"].id)
    say("   %-22s %-6s %12s %12s" % (
        s["product"].name[:22], s["uom"].name or "", ("%.4g" % lama), ("%.4g" % s["qty"])))
say("   " + "-" * 58)
say("   total                                    %s" % money(hpp_target))

# ================================================================ DRY-RUN
if not RUN:
    say("")
    say("DRY-RUN — tidak ada perubahan ditulis. Jalankan RUN=1 untuk eksekusi.")
    say("=" * 112)
    cr.rollback()
    raise SystemExit(0)

# ================================================================ EKSEKUSI
say("")
say("[EKSEKUSI]")
lama = bom_target.bom_line_ids
for l in lama:
    say("   hapus baris lama: %-22s %8s %s" % (
        l.product_id.name[:22], l.product_qty, l.product_uom_id.name or ""))
for s in target_spec:
    env["mrp.bom.line"].create({
        "bom_id": bom_target.id,
        "product_id": s["product"].id,
        "product_qty": s["qty"],
        "product_uom_id": s["uom"].id,
    })
say("   buat %d baris baru dari resep acuan ×%g" % (len(target_spec), MULT))
if lama:
    lama.unlink()
cr.flush()
cr.commit()
say("   [COMMITTED]")

# ================================================================ VERIFIKASI
say("")
say("=" * 112)
say("[VERIFIKASI]")
bom_target.invalidate_recordset()
lines = bom_target.bom_line_ids
hpp = sum(float(l.product_qty or 0) * float(l.product_id.standard_price or 0) for l in lines)
say("   %-34s %d baris | HPP %s | jual %s | margin %.1f%%" % (
    TARGET_MENU, len(lines), money(hpp), money(harga),
    (1 - hpp / harga) * 100 if harga else 0))
say("   target baris %d, target HPP %s → selisih %s" % (
    len(target_spec), money(hpp_target), money(hpp - hpp_target)))

say("")
say("   perbandingan paket besar:")
cr.execute("""
    SELECT pt.name->>'en_US', i.fixed_price,
           SUM(l.product_qty * COALESCE((cp.standard_price->>'1')::numeric, 0)) hpp,
           COUNT(l.id)
      FROM product_template pt
      JOIN product_pricelist_item i ON i.product_tmpl_id = pt.id AND i.pricelist_id = 3
      JOIN mrp_bom b ON b.product_tmpl_id = pt.id AND b.active
      JOIN mrp_bom_line l ON l.bom_id = b.id
      JOIN product_product cp ON cp.id = l.product_id
     WHERE i.fixed_price >= 40000 AND pt.active AND pt.available_in_pos
     GROUP BY 1,2 ORDER BY 2 DESC
""")
for nama, jual, h, nb in cr.fetchall():
    say("     %-30s %10s  HPP %12s  margin %5.1f%%  (%d baris)" % (
        (nama or "")[:30], money(jual), money(h), (1 - float(h) / float(jual)) * 100, nb))

say("")
say("   sebaran margin menu (semua):")
cr.execute("""
    WITH hpp AS (
      SELECT b.product_tmpl_id tid, SUM(l.product_qty * COALESCE((cp.standard_price->>'1')::numeric,0)) h
        FROM mrp_bom b JOIN mrp_bom_line l ON l.bom_id=b.id
        JOIN product_product cp ON cp.id=l.product_id WHERE b.active GROUP BY 1)
    SELECT COUNT(*),
           COUNT(*) FILTER (WHERE m < 0),
           COUNT(*) FILTER (WHERE m >= 0 AND m < 30),
           COUNT(*) FILTER (WHERE m >= 30 AND m < 40),
           COUNT(*) FILTER (WHERE m >= 40 AND m < 45),
           COUNT(*) FILTER (WHERE m >= 45),
           ROUND(AVG(m),1), ROUND(AVG(100-m),1)
      FROM (SELECT (1 - COALESCE(hpp.h,(cp.standard_price->>'1')::numeric)/NULLIF(i.fixed_price,0))*100 m
              FROM product_template pt JOIN product_product cp ON cp.product_tmpl_id=pt.id
              JOIN product_pricelist_item i ON i.product_tmpl_id=pt.id AND i.pricelist_id=3
              LEFT JOIN hpp ON hpp.tid=pt.id
             WHERE pt.active AND pt.available_in_pos AND pt.sale_ok AND pt.type<>'service') x
""")
tot, rugi, b30, b40, b45, atas, avg_m, avg_c = cr.fetchone()
say("     total %d | rugi %d | 0-30%% %d | 30-40%% %d | 40-45%% %d | >=45%% %d | rata margin %.1f%% (cost ratio %.1f%%)" % (
    tot, rugi, b30, b40, b45, atas, avg_m, avg_c))

say("")
say("   integritas: baris BOM %d | BOM aktif %d | produk POS %d | item pricelist %d" % (
    env["mrp.bom.line"].search_count([]),
    env["mrp.bom"].search_count([("active", "=", True)]),
    env["product.product"].search_count([("available_in_pos", "=", True), ("sale_ok", "=", True)]),
    env["product.pricelist.item"].search_count([])))

say("")
say("   CATATAN temuan tambahan: standard_price menu ≠ HPP resepnya")
for nm in (REF_MENU, TARGET_MENU):
    tt = PT.search([("name", "=", nm)], limit=1)
    bb = bom_of(tt)
    if bb:
        h = sum(float(l.product_qty or 0) * float(l.product_id.standard_price or 0)
                for l in bb.bom_line_ids)
        say("     %-34s standard_price %12s  vs  HPP resep %12s" % (
            nm[:34], money(float(tt.product_variant_id.standard_price or 0)), money(h)))
say("=" * 112)
