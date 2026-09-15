# -*- coding: utf-8 -*-
"""
perbaikan_master_04_takaran_resep.py — BETULKAN TAKARAN RESEP TAHU & TEMPE (13 Sep 2026).

LATAR BELAKANG
  Resep tahu/tempe memakai kuantitas yang tidak mungkin secara satuan: 3 GRM tahu dan
  4 GRM tempe per porsi. UoM barisnya sudah sama dengan UoM komponen (jadi lolos cek
  audit §3), tetapi besarannya jelas salah — kemungkinan kolom "GRM" diisi angka
  "jumlah potong".

  Dikonfirmasi pemilik 13 Sep 2026 (dasar: 1 potong ≈ 50 g; tahu Rp12.000/kg, tempe Rp15.000/kg):

  | menu         | komponen          | dari    | menjadi   | alasan                        |
  |--------------|-------------------|--------:|----------:|-------------------------------|
  | TAHU CRISPY  | TAHU              |  3 GRM  |  150 GRM  | ≈3 potong @50 g               |
  | TAHU/BIJI    | TAHU              |  3 GRM  |   50 GRM  | 1 potong                      |
  | TEMPE CRISPY | TEMPE             |  4 GRM  |  200 GRM  | ≈4 potong @50 g               |
  | TEMPE/BIJI   | TEMPE             |  4 GRM  |   50 GRM  | 1 potong                      |
  | TAHU CRISPY  | TEPUNG MIX GEYUKSSS | 20+20 GRM | 40 GRM | gabung baris dobel            |
  | TEMPE CRISPY | TEPUNG MIX GEYUKSSS | 25+20 GRM | 45 GRM | gabung baris dobel            |

  MENU NUGGET SENGAJA TIDAK DIUBAH — dikonfirmasi pemilik bahwa "NUGGET" (Rp2.000) memang
  1 buah satuan, jadi resep NUGGET AYAM 1 PCS sudah benar.

  Baris dobel digabung dengan cara: baris pertama (id terkecil) di-set ke total, sisanya
  dihapus. Nilai HPP tidak berubah oleh penggabungan — hanya kerapian.

  Idempotent. Dry-run penuh (`env.cr.rollback()`).
  Tidak menyentuh harga jual, pricelist, order, stok, atau jurnal.

  dry-run : su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/perbaikan_master_04_takaran_resep.py
  eksekusi: su odoo -s /bin/bash -c "RUN=1 odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/perbaikan_master_04_takaran_resep.py
"""
import os

RUN = os.environ.get("RUN") == "1"
PL_NORMAL = 3

# (menu, komponen, qty baru, catatan)
CHANGES = [
    ("TAHU CRISPY",  "TAHU",               150.0, "3 GRM → 150 GRM (≈3 potong @50 g)"),
    ("TAHU/BIJI",    "TAHU",                50.0, "3 GRM → 50 GRM (1 potong)"),
    ("TEMPE CRISPY", "TEMPE",              200.0, "4 GRM → 200 GRM (≈4 potong @50 g)"),
    ("TEMPE/BIJI",   "TEMPE",               50.0, "4 GRM → 50 GRM (1 potong)"),
    ("TAHU CRISPY",  "TEPUNG MIX GEYUKSSS", 40.0, "gabung 20+20 → 40 GRM"),
    ("TEMPE CRISPY", "TEPUNG MIX GEYUKSSS", 45.0, "gabung 25+20 → 45 GRM"),
]

cr = env.cr
PT = env["product.template"]
PP = env["product.product"]
BOM = env["mrp.bom"]

say = lambda m="": print(m)
money = lambda x: "{:>12,.2f}".format(float(x or 0))


def hpp_of(tmpl_id):
    cr.execute("""
        SELECT COALESCE(SUM(bl.product_qty * COALESCE((cp.standard_price->>'1')::numeric, 0)), 0)
          FROM mrp_bom b JOIN mrp_bom_line bl ON bl.bom_id = b.id
          LEFT JOIN product_product cp ON cp.id = bl.product_id
         WHERE b.product_tmpl_id = %s AND b.active
    """, (tmpl_id,))
    return float(cr.fetchone()[0] or 0)


def harga_jual(tmpl_id):
    cr.execute("SELECT fixed_price FROM product_pricelist_item "
               "WHERE pricelist_id=%s AND product_tmpl_id=%s LIMIT 1", (PL_NORMAL, tmpl_id))
    r = cr.fetchone()
    return float(r[0]) if r and r[0] is not None else 0.0


# ================================================================ GUARD + RENCANA
say("=" * 112)
say("BETULKAN TAKARAN RESEP TAHU & TEMPE   |   RUN=%s   |   %s" % (RUN, "TULIS" if RUN else "DRY-RUN"))
say("=" * 112)
say("")

rencana, masalah = [], []
menu_cache = {}
for menu, komp, qty_baru, catatan in CHANGES:
    if menu not in menu_cache:
        hits = PT.with_context(active_test=False).search([("name", "=", menu)])
        menu_cache[menu] = hits
    hits = menu_cache[menu]
    if len(hits) != 1:
        masalah.append("%s: %d template bernama itu (harus 1)" % (menu, len(hits)))
        continue
    t = hits[0]
    boms = BOM.search([("product_tmpl_id", "=", t.id), ("active", "=", True)])
    if len(boms) != 1:
        masalah.append("%s: %d BOM aktif (harus 1)" % (menu, len(boms)))
        continue
    bom = boms[0]
    cp = PP.with_context(active_test=False).search([("name", "=", komp)], limit=1)
    if not cp:
        masalah.append("%s: komponen %r tidak ditemukan" % (menu, komp))
        continue
    lines = bom.bom_line_ids.filtered(lambda l: l.product_id.id == cp.id)
    if not lines:
        masalah.append("%s: tidak ada baris %r" % (menu, komp))
        continue
    lines = lines.sorted(lambda l: l.id)
    qty_lama_total = sum(float(l.product_qty or 0) for l in lines)
    rencana.append(dict(menu=menu, tmpl=t, bom=bom, komp=komp, cp=cp, lines=lines,
                        n=len(lines), qty_lama=qty_lama_total, qty_baru=qty_baru,
                        catatan=catatan))
    # hanya "sudah benar" bila HANYA ada 1 baris dan jumlahnya sudah sesuai;
    # kalau masih ada baris dobel, penggabungan tetap harus dijalankan walau totalnya sama.
    if len(lines) == 1 and abs(qty_lama_total - qty_baru) < 1e-9:
        masalah.append("%s / %s: sudah %s di 1 baris — dilewati (idempotent)" % (menu, komp, qty_baru))

say("[GUARD]")
say("   perubahan siap diterapkan : %d dari %d" % (len(rencana), len(CHANGES)))
for m in masalah:
    say("   !! %s" % m)
if not rencana:
    say("")
    say("   Tidak ada yang perlu dikerjakan — berhenti.")
    say("=" * 112)
    cr.rollback()
    raise SystemExit(0)

say("")
say("   %-14s %-20s %8s %12s %12s  %s" % ("menu", "komponen", "baris", "qty lama", "qty baru", "catatan"))
say("   " + "-" * 104)
for r in rencana:
    say("   %-14s %-20s %8d %12s %12s  %s" % (
        r["menu"][:14], r["komp"][:20], r["n"], ("%.4g" % r["qty_lama"]), ("%.4g" % r["qty_baru"]),
        r["catatan"]))

# ================================================================ DAMPAK
say("")
say("[DAMPAK HPP & MARGIN]")
say("   %-16s %13s %13s %11s %9s %9s %8s" % (
    "menu", "HPP lama", "HPP baru", "jual", "margin", "m.baru", "delta"))
say("   " + "-" * 90)
per_menu = {}
for r in rencana:
    per_menu.setdefault(r["menu"], []).append(r)

for menu, rs in per_menu.items():
    t = rs[0]["tmpl"]
    h0 = hpp_of(t.id)
    delta = sum((r["qty_baru"] - r["qty_lama"]) * float(r["cp"].standard_price or 0) for r in rs)
    h1 = h0 + delta
    harga = harga_jual(t.id)
    m0 = (1 - h0 / harga) * 100 if harga else 0
    m1 = (1 - h1 / harga) * 100 if harga else 0
    say("   %-16s %s %s %11s %8.1f%% %8.1f%% %+8.2f" % (
        menu[:16], money(h0), money(h1), money(harga), m0, m1, delta))

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
for r in rencana:
    utama = r["lines"][0]
    if abs(float(utama.product_qty or 0) - r["qty_baru"]) > 1e-9:
        utama.write({"product_qty": r["qty_baru"]})
    for lain in r["lines"][1:]:
        say("   hapus baris dobel id=%s (%s %s) dari %s" % (
            lain.id, lain.product_qty, r["komp"], r["menu"]))
        lain.unlink()
    say("   %-14s %-20s → %s %s" % (r["menu"][:14], r["komp"][:20],
                                    ("%.4g" % r["qty_baru"]),
                                    (r["cp"].uom_id.name or "")))
cr.flush()
cr.commit()
say("   [COMMITTED] %d perubahan" % len(rencana))

# ================================================================ VERIFIKASI
say("")
say("=" * 112)
say("[VERIFIKASI]")
salah = 0
for menu, rs in per_menu.items():
    t = rs[0]["tmpl"]
    bom = BOM.search([("product_tmpl_id", "=", t.id), ("active", "=", True)], limit=1)
    for r in rs:
        ls = bom.bom_line_ids.filtered(lambda l: l.product_id.id == r["cp"].id)
        total = sum(float(l.product_qty or 0) for l in ls)
        status = "OK" if (len(ls) == 1 and abs(total - r["qty_baru"]) < 1e-9) else "SALAH"
        if status != "OK":
            salah += 1
        say("   %-5s %-14s %-20s %d baris, total %s (target %s)" % (
            status, menu[:14], r["komp"][:20], len(ls), ("%.4g" % total), ("%.4g" % r["qty_baru"])))
    h1 = hpp_of(t.id)
    harga = harga_jual(t.id)
    say("   %-16s HPP %s | jual %s | margin %5.1f%%" % (
        menu[:16], money(h1), money(harga), (1 - h1 / harga) * 100 if harga else 0))
say("")
say("   baris tidak sesuai target : %d" % salah)

say("")
say("   menu NUGGET (sengaja tidak diubah):")
nt = PT.search([("name", "=", "NUGGET")], limit=1)
if nt:
    nb = BOM.search([("product_tmpl_id", "=", nt.id), ("active", "=", True)], limit=1)
    for l in nb.bom_line_ids:
        say("     %-18s %s %s" % (l.product_id.name, l.product_qty, l.product_uom_id.name))

say("")
say("   jumlah baris BOM total (penggabungan mengurangi 2 baris):")
say("     mrp_bom_line = %d" % env["mrp.bom.line"].search_count([]))

say("")
say("   harga jual tidak disentuh:")
say("     produk POS = %d | item pricelist 3 = %d | item pricelist 5 = %d" % (
    PP.search_count([("available_in_pos", "=", True), ("sale_ok", "=", True)]),
    env["product.pricelist.item"].search_count([("pricelist_id", "=", PL_NORMAL)]),
    env["product.pricelist.item"].search_count([("pricelist_id", "=", 5)])))
say("=" * 112)
