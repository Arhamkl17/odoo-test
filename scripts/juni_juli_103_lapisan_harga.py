# -*- coding: utf-8 -*-
"""
juni_juli_103_lapisan_harga.py — berapa lapisan harga yang sebenarnya ada di sistem (READ-ONLY).

Menjawab pertanyaan pemilik: "kenapa ada harga Dine In, apakah ada harga lain?"
"""
cr = env.cr
PP = env["product.product"]
PL = env["product.pricelist"]
PPI = env["product.pricelist.item"]

say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

say("=" * 118)
say("LAPISAN HARGA YANG ADA DI SISTEM   (read-only)")
say("=" * 118)

say("")
say("[1] DAFTAR HARGA (product.pricelist)")
say("")
for pl in PL.search([]):
    n = PPI.search_count([("pricelist_id", "=", pl.id)])
    say("   id=%-3s %-28s %3d item   aktif=%s" % (pl.id, pl.name, n, pl.active))
say("")
say("   → hanya ADA DUA daftar harga di sistem.")

# ---------------------------------------------------------------- tiga lapisan
say("")
say("[2] TIGA LAPISAN HARGA YANG SEBENARNYA BERLAKU")
say("")
say("   1. `product.template.list_price`  → harga master produk (dipakai kalau tidak ada pricelist)")
say("   2. pricelist id 3 'Harga Dasar (Take Away)'")
say("   3. pricelist id 4 'Harga Dine In'")
say("")

cr.execute("""
    SELECT p.id, t.name->>'en_US', t.list_price,
           (SELECT i.fixed_price FROM product_pricelist_item i
             WHERE i.pricelist_id=3 AND (i.product_id=p.id
                OR (i.product_tmpl_id=t.id AND i.applied_on='1_product')) LIMIT 1) AS ta,
           (SELECT i.fixed_price FROM product_pricelist_item i
             WHERE i.pricelist_id=4 AND (i.product_id=p.id
                OR (i.product_tmpl_id=t.id AND i.applied_on='1_product')) LIMIT 1) AS di
      FROM product_product p JOIN product_template t ON t.id=p.product_tmpl_id
     WHERE t.active AND t.available_in_pos
     ORDER BY t.list_price DESC, 2
""")
rows = cr.fetchall()

beda_master = [r for r in rows if r[3] is not None and abs(float(r[2]) - float(r[3])) > 0.01]
tanpa_di = [r for r in rows if r[4] is None]
say("   %-52s %10s %10s %10s %7s" % ("produk", "list_price", "TakeAway", "DineIn", "DineIn/TA"))
say("   " + "-" * 96)
for pid, nm, lp, ta, di in rows[:14]:
    rasio = ("%.2fx" % (float(di) / float(ta))) if (ta and di) else "—"
    say("   %-52s %10s %10s %10s %7s" % (
        (nm or "")[:52], money(lp),
        money(ta) if ta is not None else "—",
        money(di) if di is not None else "—", rasio))
say("   … total %d produk POS" % len(rows))

say("")
say("   ── harga master vs 'Harga Dasar (Take Away)': %d produk BERBEDA dari %d" % (
    len(beda_master), len(rows)))
for pid, nm, lp, ta, di in beda_master[:10]:
    say("        %-52s master %8s  vs  TakeAway %8s" % ((nm or "")[:52], money(lp), money(ta)))
say("")
say("   ── produk POS yang belum punya harga Dine In: %d" % len(tanpa_di))
for pid, nm, lp, ta, di in tanpa_di:
    say("        %-52s master %8s  TakeAway %8s" % (
        (nm or "")[:52], money(lp), money(ta) if ta is not None else "—"))

# ---------------------------------------------------------------- sebaran rasio
say("")
say("[3] SEBARAN RASIO Dine In ÷ Take Away")
say("")
say("")
rasio = [float(r[4]) / float(r[3]) for r in rows if r[3] and r[4] and float(r[3]) > 0]
if rasio:
    rasio.sort()
    n = len(rasio)
    say("   jumlah produk  : %d" % n)
    say("   terendah       : %.2fx" % rasio[0])
    say("   p25 / median   : %.2fx / %.2fx" % (rasio[n // 4], rasio[n // 2]))
    say("   p75 / tertinggi: %.2fx / %.2fx" % (rasio[3 * n // 4], rasio[-1]))
    sama = sum(1 for x in rasio if abs(x - 1.0) < 0.005)
    say("   rasio 1,00x    : %d produk (harga Dine In = Take Away)" % sama)

say("")
say("[4] DARI MANA HARGA-HARGA ITU BERASAL")
say("")
say("   PENTING: `TERONG CRISPY` (master Rp 9.000) TIDAK PUNYA item di kedua pricelist,")
say("   jadi di POS harganya jatuh ke harga master. Ini temuan lama, bukan akibat R1.")
say("")
say("   Take Away (106 item) :")
say("      • 35 item dari `06_price_update.csv` (dari product.product export klien)")
say("      • 9 item add-on baru (BARBEQUE/IJO/KOREK/RICA/KEJU LUMER/NUGGET/TAHU/TEMPE/TELUR)")
say("      • sisanya dari harga master yang diselaraskan (R3) + perbaikan paket (R7)")
say("")
say("   Dine In (106 item) :")
say("      • 25 item langsung dari `TEMPLATE IMPORT HARGA DINE IN.xlsx` (nama cocok)")
say("      • 60 item dihitung dari komponen nama + lantai paket 1,25x")
say("      • 13 item memakai lantai 1,25x")
say("      • 8 item bukan menu (Gift Card / Top-up) — harga tidak diubah")
say("")
say("=" * 118)
