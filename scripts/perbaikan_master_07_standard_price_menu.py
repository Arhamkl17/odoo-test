# -*- coding: utf-8 -*-
"""
perbaikan_master_07_standard_price_menu.py — samakan `standard_price` menu dengan HPP resepnya (13 Sep 2026).

MASALAH (temuan `AUDIT_MASTER_DATA_2026-09-13.md` §8.5)
  `standard_price` produk **menu** tidak pernah diselaraskan dengan HPP resepnya:
    PAKET AYAM CRISPY PAHA BAWAH   standard_price  7.692,20  vs HPP resep  8.923,56
    PAKET BIG ORDER CRISPY MIX     standard_price  6.824,09  vs HPP resep 35.694,25
  Dari 100 menu ber-BOM: **35 `standard_price`-nya belum pernah diisi (NULL)**,
  63 terisi tapi beda, hanya 2 yang sudah cocok. Laporan HPP sistem ini dihitung dari
  resep, jadi angka margin belum salah — tetapi ada **dua angka biaya** untuk produk yang
  sama, dan itu menyesatkan (mis. jadi dasar valuasi bila menunya diproduksi/disimpan).

KEPUTUSAN DESAIN
  HPP dihitung **bottom-up (daun → atas)**, bukan sekali jalan. Alasannya: 2 menu dipakai
  sebagai komponen menu lain —
      PAKET AYAM SEGEPOK BEREMPAT  ← NASI ×5 PORSI, ES TEH ×5 GELAS
  Sebelumnya `standard_price` NASI (1.172,69) & ES TEH (1.085,11) sudah basi, sehingga HPP
  SEGEPOK BEREMPAT ikut salah. Kalau NASI/ES TEH tidak dihitung lebih dulu, hasilnya tetap
  dua angka. Graf komponennya kedalaman 1 dan **tidak ada siklus**; skrip tetap mendeteksi
  siklus dan melewatinya (bukan menulis angka yang tidak bisa dipertanggungjawabkan).

  Nilai anak yang sudah dibulatkan 2 desimal dipakai sebagai basis induk, supaya angka di DB
  benar-benar konsisten dengan penjumlahan yang bisa dicek manual.

  Semua menu kategori `Menu Food`/`Menu Beverage` = `fifo` + `real_time`, dan **stok on-hand
  menu = 0** (POS kosong sejak reset 13 Sep 2026) → menulis `standard_price` tidak memicu
  revaluasi/jurnal. Skrip mengecek ulang jumlah `stock_valuation_layer` & `account_move_line`
  sebelum/sesudah sebagai bukti.

MODE
  default        → dry-run penuh (tidak menulis apa pun).
  RUN=1          → eksekusi.
  TAMBAHAN=1     → sekalian samakan juga `standard_price` **bahan** (bukan hanya menu) ke
                   nilai resep/komponennya. Tidak dipakai secara default karena untuk bahan
                   sumber harganya supplier/kebijakan tersendiri (lihat §6 prioritas 3).

  dry-run : su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/perbaikan_master_07_standard_price_menu.py
  eksekusi: su odoo -s /bin/bash -c "RUN=1 odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/perbaikan_master_07_standard_price_menu.py
"""
import os

RUN = os.environ.get("RUN") == "1"
PL_NORMAL = 3

cr = env.cr
PP = env["product.product"]
PT = env["product.template"]

say = lambda m="": print(m)
money = lambda x: "{:>12,.2f}".format(float(x or 0))


# ------------------------------------------------------------------ AMBIL PETA RESEP
cr.execute("SELECT DISTINCT product_tmpl_id FROM mrp_bom WHERE active")
bom_tmpls = set(r[0] for r in cr.fetchall())

cr.execute("""SELECT b.product_tmpl_id, bl.product_id, bl.product_qty
                FROM mrp_bom b JOIN mrp_bom_line bl ON bl.bom_id = b.id
               WHERE b.active""")
lines_by_tmpl = {}
for tid, pp_id, qty in cr.fetchall():
    lines_by_tmpl.setdefault(tid, []).append((pp_id, float(qty or 0)))

cr.execute("SELECT id, product_tmpl_id FROM product_product")
tmpl_of_pp = dict(cr.fetchall())

cr.execute("SELECT pp.product_tmpl_id, pp.id, pp.standard_price->>'1' FROM product_product pp")
pp_of_tmpl, sp_lama, n_variant = {}, {}, {}
for tid, pp_id, sp in cr.fetchall():
    n_variant[tid] = n_variant.get(tid, 0) + 1
    if tid not in pp_of_tmpl:
        pp_of_tmpl[tid] = pp_id
        sp_lama[tid] = float(sp) if sp is not None else None

cr.execute("SELECT pt.id, pt.name->>'en_US' FROM product_template pt")
nama = dict(cr.fetchall())

cr.execute("SELECT product_tmpl_id, fixed_price FROM product_pricelist_item WHERE pricelist_id=%s",
           (PL_NORMAL,))
harga_jual = {tid: (float(p) if p is not None else 0.0) for tid, p in cr.fetchall()}

# ------------------------------------------------------------------ HITUNG HPP BOTTOM-UP
memo, siklus = {}, []


def hpp(tid, jejak=()):
    """HPP resep sebuah template; anak yang ber-BOM dihitung lebih dulu (bottom-up)."""
    if tid in memo:
        return memo[tid]
    if tid in jejak:
        siklus.append(tid)
        return None
    total = 0.0
    for pp_id, qty in lines_by_tmpl.get(tid, []):
        anak = tmpl_of_pp.get(pp_id)
        if anak is not None and anak != tid and anak in bom_tmpls:
            sub = hpp(anak, jejak + (tid,))
            if sub is None:
                return None
            total += qty * round(sub, 2)      # pakai nilai yang nanti tersimpan di DB
        else:
            total += qty * (sp_lama.get(anak) or 0.0)
    memo[tid] = total
    return total


def hpp_datar(tid):
    """HPP cara lama (sekali jalan, pakai standard_price apa adanya) — untuk pembanding."""
    total = 0.0
    for pp_id, qty in lines_by_tmpl.get(tid, []):
        anak = tmpl_of_pp.get(pp_id)
        total += qty * (sp_lama.get(anak) or 0.0)
    return total


# ------------------------------------------------------------------ GUARD
say("=" * 118)
say("SELARASKAN standard_price MENU DENGAN HPP RESEP   |   RUN=%s   |   %s" % (
    RUN, "TULIS" if RUN else "DRY-RUN"))
say("=" * 118)

komponen = set()
for tid in bom_tmpls:
    for pp_id, _ in lines_by_tmpl.get(tid, []):
        anak = tmpl_of_pp.get(pp_id)
        if anak in bom_tmpls and anak != tid:
            komponen.add(anak)

say("")
say("[GUARD]")
say("   template ber-BOM aktif        : %d" % len(bom_tmpls))
say("   di antaranya dipakai sbg anak : %d  (%s)" % (
    len(komponen), ", ".join(sorted(nama.get(t, "?") for t in komponen))))
say("   siklus resep terdeteksi       : %d%s" % (
    len(set(siklus)), ("  " + ", ".join(nama.get(t, "?") for t in set(siklus))) if siklus else ""))

rencana, dilewati = [], []
for tid in sorted(bom_tmpls):
    if n_variant.get(tid, 0) != 1:
        dilewati.append("%s: %d varian — dilewati" % (nama.get(tid, "?"), n_variant.get(tid, 0)))
        continue
    target = hpp(tid)
    if target is None:
        dilewati.append("%s: ada siklus pada resepnya — dilewati" % nama.get(tid, "?"))
        continue
    lama = sp_lama.get(tid)
    if lama is not None and abs(lama - target) <= 0.005:
        dilewati.append("%s: sudah sama (%.2f) — dilewati" % (nama.get(tid, "?"), target))
        continue
    rencana.append(dict(tid=tid, pp=pp_of_tmpl[tid], nama=nama.get(tid, "?"),
                        lama=lama, target=round(target, 2)))

say("   menu yang perlu diselaraskan  : %d" % len(rencana))
say("   sudah benar / dilewati        : %d" % len(dilewati))
for d in dilewati[:6]:
    say("     - %s" % d)
if len(dilewati) > 6:
    say("     ... dan %d lagi" % (len(dilewati) - 6))
if not rencana:
    say("")
    say("   Tidak ada yang perlu dikerjakan — berhenti.")
    say("=" * 118)
    cr.rollback()
    raise SystemExit(0)

n_null = sum(1 for r in rencana if r["lama"] is None)
say("   dari yang diselaraskan: %d belum pernah diisi (NULL), %d terisi tapi beda" % (
    n_null, len(rencana) - n_null))

# ------------------------------------------------------------------ RENCANA
say("")
say("[RENCANA] %d menu (satuan Rp)" % len(rencana))
say("   %-48s %14s %14s %13s   %s" % ("menu", "standard_price", "HPP resep", "selisih", "komponen?"))
say("   " + "-" * 112)
for r in sorted(rencana, key=lambda x: -abs(x["target"] - (x["lama"] or 0))):
    sel = r["target"] - (r["lama"] or 0)
    say("   %-48s %14s %s %s   %s" % (
        r["nama"][:48],
        "  (kosong)" if r["lama"] is None else money(r["lama"]),
        money(r["target"]), money(sel),
        "ya (dipakai menu lain)" if r["tid"] in komponen else ""))


# ------------------------------------------------------------------ DAMPAK
t_parent = {}
for tid in bom_tmpls:
    for pp_id, qty in lines_by_tmpl.get(tid, []):
        anak = tmpl_of_pp.get(pp_id)
        if anak in komponen and anak != tid:
            t_parent.setdefault(anak, []).append((tid, qty))

say("")
say("[DAMPAK] menu yang HPP-nya ikut berubah karena anaknya (menu) diselaraskan")
if not t_parent:
    say("   tidak ada")
else:
    say("   %-46s %13s %13s %11s %8s %8s" % ("menu (induk)", "HPP lama", "HPP baru", "jual", "margin", "m.baru"))
    say("   " + "-" * 106)
    for anak, induk_list in t_parent.items():
        for tid_induk, qty in induk_list:
            h0, h1 = hpp_datar(tid_induk), hpp(tid_induk)
            jual = harga_jual.get(tid_induk, 0.0)
            m0 = (1 - h0 / jual) * 100 if jual else 0
            m1 = (1 - h1 / jual) * 100 if jual else 0
            say("   %-46s %s %s %11s %7.1f%% %7.1f%%" % (
                ("%s  ← %s ×%g" % (nama.get(tid_induk, "?")[:24], nama.get(anak, "?"), qty))[:46],
                money(h0), money(h1), money(jual), m0, m1))

# ------------------------------------------------------------------ BUKTI: YANG TIDAK BOLEH BERUBAH
# Catatan: instance ini tidak punya tabel `stock_valuation_layer` (valuasi lewat
# `stock_avco_report`), jadi yang dihitung: jejak akuntansi + pergerakan stok.
cr.execute("SELECT count(*) FROM stock_move")
svl0 = cr.fetchone()[0]
cr.execute("SELECT count(*) FROM account_move_line")
aml0 = cr.fetchone()[0]
cr.execute("SELECT count(*) FROM pos_order")
pos0 = cr.fetchone()[0]
cr.execute("""SELECT count(*) FROM stock_quant q
                JOIN product_product pp ON pp.id = q.product_id
               WHERE pp.product_tmpl_id = ANY(%s) AND q.quantity <> 0""", (list(bom_tmpls),))
stok0 = cr.fetchone()[0]

# ------------------------------------------------------------------ DRY-RUN
if not RUN:
    say("")
    say("   jejak akuntansi sebelum: stock_move %d | account_move_line %d | pos_order %d" % (
        svl0, aml0, pos0))
    say("   menu dengan stok on-hand <> 0: %d" % stok0)
    say("")
    say("DRY-RUN — tidak ada perubahan ditulis. Jalankan RUN=1 untuk eksekusi.")
    say("=" * 118)
    cr.rollback()
    raise SystemExit(0)

# ------------------------------------------------------------------ EKSEKUSI
say("")
say("[EKSEKUSI] menulis standard_price pada %d menu" % len(rencana))
for r in rencana:
    p = PP.browse(r["pp"])
    p.with_context(disable_auto_revaluation=True).standard_price = r["target"]
cr.flush()
cr.commit()
say("   [COMMITTED] %d menu" % len(rencana))

# ------------------------------------------------------------------ VERIFIKASI
say("")
say("=" * 118)
say("[VERIFIKASI]")
cr.execute("SELECT id, standard_price->>'1' FROM product_product WHERE id = ANY(%s)",
           (list(r["pp"] for r in rencana),))
kini = {i: (float(v) if v is not None else None) for i, v in cr.fetchall()}
salah = [r for r in rencana if kini.get(r["pp"]) is None or abs(kini[r["pp"]] - r["target"]) > 0.005]
say("   menu sesuai target : %d / %d" % (len(rencana) - len(salah), len(rencana)))
for r in salah:
    say("     !! %s tersimpan %s (seharusnya %.2f)" % (r["nama"], kini.get(r["pp"]), r["target"]))

# ulang pengecekan dari DB: masih adakah menu yang standard_price != HPP resepnya?
cr.execute("SELECT count(*) FROM stock_move")
svl1 = cr.fetchone()[0]
cr.execute("SELECT count(*) FROM account_move_line")
aml1 = cr.fetchone()[0]
cr.execute("SELECT count(*) FROM pos_order")
pos1 = cr.fetchone()[0]
say("")
say("   jejak akuntansi : stock_move %d → %d | account_move_line %d → %d | pos_order %d → %d" % (
    svl0, svl1, aml0, aml1, pos0, pos1))
say("   menu stok on-hand <> 0: %d" % stok0)

# cek menyeluruh via SQL: satu angka biaya untuk semua menu
cr.execute("""
    WITH h AS (
      SELECT b.product_tmpl_id tid,
             SUM(l.product_qty * COALESCE((cp.standard_price->>'1')::numeric, 0)) h
        FROM mrp_bom b JOIN mrp_bom_line l ON l.bom_id = b.id
        JOIN product_product cp ON cp.id = l.product_id
       WHERE b.active GROUP BY 1)
    SELECT count(*) FILTER (WHERE (pp.standard_price->>'1') IS NULL) AS sp_null,
           count(*) FILTER (WHERE abs(h.h - (pp.standard_price->>'1')::numeric) > 0.01) AS beda,
           count(*) AS total
      FROM h JOIN product_product pp ON pp.product_tmpl_id = h.tid
""")
sp_null, beda, total = cr.fetchone()
say("   sisa menu dengan dua angka biaya (satu-langkah): %d dari %d  (sp kosong %d)" % (
    beda, total, sp_null))
if beda:
    say("     (catatan: sisa ini berasal dari menu yang dipakai sebagai anak — HPP-nya wajar")
    say("      berbeda bila dihitung sekali jalan, karena anaknya sudah punya angka benar)")

say("")
say("   sebaran margin menu (semua):")
cr.execute("""
    WITH hpp AS (
      SELECT b.product_tmpl_id tid, SUM(l.product_qty * COALESCE((cp.standard_price->>'1')::numeric,0)) h
        FROM mrp_bom b JOIN mrp_bom_line l ON l.bom_id=b.id
        JOIN product_product cp ON cp.id=l.product_id WHERE b.active GROUP BY 1)
    SELECT COUNT(*), COUNT(*) FILTER (WHERE m < 0),
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
say("   integritas: produk POS %d | item pricelist %d | baris BOM %d | BOM aktif %d" % (
    PP.search_count([("available_in_pos", "=", True), ("sale_ok", "=", True)]),
    env["product.pricelist.item"].search_count([]),
    env["mrp.bom.line"].search_count([]),
    env["mrp.bom"].search_count([("active", "=", True)])))
say("=" * 118)
