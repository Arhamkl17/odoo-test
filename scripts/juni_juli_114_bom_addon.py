# -*- coding: utf-8 -*-
"""
juni_juli_114_bom_addon.py — LENGKAPI BOM + RAPIKAN UOM HEADER BOM (13 Sep 2026).

Latar (temuan skrip 111):
  • 13 produk POS tanpa BOM — 2 di antaranya jasa (Gift Card / Top-up) yang memang
    tidak perlu BOM, 1 (`SAMBAL TOMAT MALINO`) belum bisa (bahan tidak ada).
  • 52 BOM punya `product_uom_id` (Units) BEDA dengan UOM produknya (PORSI/PAKET).

Yang dilakukan:
  A. **Rapikan header 52 BOM** → `product_uom_id` disamakan dengan UOM produk.
  B. **Buat BOM** untuk 10 produk, SEMUA meniru resep yang sudah ada di sistem
     (tidak ada angka yang dikarang tanpa acuan):

     | produk (id) | komponen | qty | UOM | acuan |
     |---|---|---:|---|---|
     | IJO (658)          | SAMBAL IJO PADANG (651)      | 17,20 | GRM | GEPREK SAMBAL IJO PADANG |
     | KOREK (659)        | SAMBAL KOREK SURABAYA (652)  | 28,60 | GRM | GEPREK/MENU SAMBAL KOREK |
     | RICA (660)         | SAMBAL RICA MANADO (650)     | 23,29 | GRM | GEPREK/MENU SAMBAL RICA |
     | KEJU LUMER (661)   | BUBUK KEJU (462) + AIR GALON (640) | 8 GRM + 15 MIL | SAOS KEJU (589) |
     | BARBEQUE (657)     | BUBUK BBQ (461) + AIR GALON (640)  | 8 GRM + 15 MIL | SAOS BBQ (590) |
     | NUGGET (662)       | NUGGET AYAM (649)            | 1     | PCS | 1:1 bahan |
     | TAHU/BIJI (663)    | TAHU (646)                   | 3     | GRM | TAHU CRISPY (549) |
     | TEMPE/BIJI (664)   | TEMPE (645)                  | 4     | GRM | TEMPE CRISPY (548) |
     | TELUR KRISPI (665) | TELUR (475)                  | 1     | BUTIR | TELUR CRISPY (547) |
     | AIR GELAS (641)    | AIR GALON (640)              | 200   | MIL | segelas air (asumsi) |

  C. **TIDAK dibuat** (dilaporkan): `Gift Card`, `Top-up eWallet` (kategori Services),
     dan `SAMBAL TOMAT MALINO` (tidak ada produk bahan-nya; sekarang malah dipakai
     sebagai komponen oleh GEPREK SAMBAL TOMAT MALINO → perlu keputusan pemilik).

Idempotent. Tidak menyentuh harga & order historis.

  dry-run : su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/juni_juli_114_bom_addon.py
  eksekusi: su odoo -s /bin/bash -c "RUN=1 odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/juni_juli_114_bom_addon.py
"""
import os

RUN = os.environ.get("RUN") == "1"

PT = env["product.template"]
PP = env["product.product"]
BOM = env["mrp.bom"]
UOM = env["uom.uom"]

say = lambda m="": print(m)
num = lambda x: "{:,.2f}".format(float(x)).rstrip("0").rstrip(".")


def pp_of(tmpl_id):
    p = PP.search([("product_tmpl_id", "=", tmpl_id)], limit=1)
    if not p:
        raise SystemExit("!! product.product untuk template %s tidak ada." % tmpl_id)
    return p


def uom(nama):
    u = UOM.search([("name", "=", nama)], limit=1)
    if not u:
        raise SystemExit("!! UOM %r tidak ada." % nama)
    return u


# (produk_id, [(komponen_tmpl_id, qty, uom_nama)], acuan)
RENCANA = [
    (658, [(651, 17.20, "GRM")], "GEPREK SAMBAL IJO PADANG"),
    (659, [(652, 28.60, "GRM")], "GEPREK SAMBAL KOREK SURABAYA"),
    (660, [(650, 23.29, "GRM")], "GEPREK SAMBAL RICA MANADO"),
    (661, [(462, 8.0, "GRM"), (640, 15.0, "MIL")], "SAOS KEJU"),
    (657, [(461, 8.0, "GRM"), (640, 15.0, "MIL")], "SAOS BBQ"),
    (662, [(649, 1.0, "PCS")], "1:1 bahan"),
    (663, [(646, 3.0, "GRM")], "TAHU CRISPY"),
    (664, [(645, 4.0, "GRM")], "TEMPE CRISPY"),
    (665, [(475, 1.0, "BUTIR")], "TELUR CRISPY"),
    (641, [(640, 200.0, "MIL")], "segelas air (asumsi)"),
]

TAK_DIBUAT = [
    (653, "Gift Card", "kategori Services — bukan produk fisik"),
    (654, "Top-up eWallet", "kategori Services — bukan produk fisik"),
    (552, "SAMBAL TOMAT MALINO", "tidak ada produk bahan 'SAMBAL TOMAT MALINO'; "
                                  "produk ini justru dipakai sebagai komponen oleh "
                                  "GEPREK SAMBAL TOMAT MALINO — perlu keputusan pemilik"),
]

say("=" * 116)
say("LENGKAPI BOM + RAPIKAN UOM HEADER BOM   |   RUN=%s" % RUN)
say("=" * 116)

# ---------------------------------------------------------------- A. header UOM
cr = env.cr
cr.execute("""
    SELECT b.id, (t.name->>'en_US'), (ub.name->>'en_US'), (ut.name->>'en_US'), t.uom_id
      FROM mrp_bom b
      JOIN product_template t ON t.id=b.product_tmpl_id
      LEFT JOIN uom_uom ub ON ub.id=b.product_uom_id
      LEFT JOIN uom_uom ut ON ut.id=t.uom_id
     WHERE b.product_uom_id IS DISTINCT FROM t.uom_id
     ORDER BY 1
""")
header_rows = cr.fetchall()

say("")
say("[A] HEADER BOM yang UOM-nya beda dari produk: %d" % len(header_rows))
for bid, nama, uom_bom, uom_prod, _uid in header_rows[:10]:
    say("   bom=%-4s %-48s %-7s → %-7s" % (bid, (nama or "")[:48], uom_bom, uom_prod))
if len(header_rows) > 10:
    say("   … %d baris lain" % (len(header_rows) - 10))

# ---------------------------------------------------------------- B. BOM baru
say("")
say("[B] BOM YANG AKAN DIBUAT: %d" % len(RENCANA))
for tid, lines, acuan in RENCANA:
    t = PT.browse(tid)
    n_bom = BOM.search_count([("product_tmpl_id", "=", tid)])
    say("   %-22s [%s bom existing]  acuan: %s" % (
        t.display_name[:22], n_bom, acuan))
    for cid, qty, un in lines:
        say("        %-26s %8s %s" % (PT.browse(cid).display_name[:26], num(qty), un))

say("")
say("[C] TIDAK DIBUAT:")
for tid, nama, alasan in TAK_DIBUAT:
    say("   %-22s %s" % (nama, alasan))

if not RUN:
    say("")
    say("DRY-RUN — tidak ada perubahan. Jalankan RUN=1 untuk eksekusi.")
    say("=" * 116)
    env.cr.rollback()
    raise SystemExit(0)

# ---------------------------------------------------------------- eksekusi
say("")
say("[EKSEKUSI]")
n_head = 0
for bid, _n, _ub, _ut, uom_id in header_rows:
    BOM.browse(bid).write({"product_uom_id": uom_id})
    n_head += 1
say("   header BOM dirapikan : %d" % n_head)

n_new = 0
for tid, lines, _acuan in RENCANA:
    t = PT.browse(tid)
    if BOM.search_count([("product_tmpl_id", "=", tid)]):
        say("   %-22s sudah punya BOM — dilewati" % t.display_name[:22])
        continue
    bom = BOM.create({
        "product_tmpl_id": tid,
        "product_qty": 1.0,
        "product_uom_id": t.uom_id.id,
        "type": "phantom",
        "company_id": env.company.id,
        "consumption": "warning",
    })
    for cid, qty, un in lines:
        bom.write({"bom_line_ids": [(0, 0, {
            "product_id": pp_of(cid).id,
            "product_qty": qty,
            "product_uom_id": uom(un).id,
        })]})
    n_new += 1
    say("   %-22s BOM dibuat: %s" % (t.display_name[:22], bom.display_name))
env.cr.flush()
env.cr.commit()
say("   [COMMITTED]")

# ---------------------------------------------------------------- verifikasi
say("")
say("=" * 116)
say("[VERIFIKASI]")
cr.execute("""
    SELECT count(*) FROM mrp_bom b JOIN product_template t ON t.id=b.product_tmpl_id
     WHERE b.product_uom_id IS DISTINCT FROM t.uom_id
""")
say("   BOM yang UOM-nya masih beda dari produk : %d" % cr.fetchone()[0])
cr.execute("""
    SELECT count(*) FROM product_template t
     WHERE t.available_in_pos AND t.active AND t.sale_ok
       AND NOT EXISTS (SELECT 1 FROM mrp_bom b WHERE b.product_tmpl_id=t.id)
""")
say("   produk POS yang masih tanpa BOM         : %d" % cr.fetchone()[0])
say("")
say("   HPP kasar produk baru (dari komponen):")
cr.execute("""
    SELECT (t.name->>'en_US'), t.list_price,
           COALESCE(SUM(bl.product_qty * COALESCE((cp.standard_price->>'1')::numeric, 0)), 0) AS hpp
      FROM product_template t
      JOIN mrp_bom b ON b.product_tmpl_id=t.id
      LEFT JOIN mrp_bom_line bl ON bl.bom_id=b.id
      LEFT JOIN product_product cp ON cp.id=bl.product_id
     WHERE t.id = ANY(%s)
     GROUP BY t.id, t.list_price, t.name
     ORDER BY t.id
""", ([tid for tid, _l, _a in RENCANA],))
for nama, harga, hpp in cr.fetchall():
    say("     %-22s jual %10s | hpp %10s | margin %s" % (
        (nama or "")[:22], "{:,.0f}".format(harga), "{:,.0f}".format(hpp or 0),
        "%.0f%%" % ((1 - (hpp or 0) / float(harga)) * 100) if harga else "-"))
say("")
say("   catatan: HPP di atas memakai standard_price komponen apa adanya, bukan")
say("   hitungan FIFO/real — angka final tetap dari modul persediaan.")
say("=" * 116)
