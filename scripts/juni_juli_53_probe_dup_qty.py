# -*- coding: utf-8 -*-
"""juni_juli_53_probe_dup_qty.py — cari produk dengan total qty identik (READ-ONLY)."""
from collections import defaultdict

cr = env.cr
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

cr.execute("""
    SELECT pol.product_id, SUM(pol.qty), SUM(pol.price_subtotal), COUNT(*)
      FROM pos_order_line pol JOIN pos_order po ON po.id = pol.order_id
     WHERE po.state IN ('paid','done','invoiced')
       AND po.date_order >= '2026-06-01' AND po.date_order < '2026-09-01'
     GROUP BY 1 ORDER BY 2 DESC""")
rows = [(int(p), float(q), float(r), int(n)) for p, q, r, n in cr.fetchall() if p]
Prod = env["product.product"]

byq = defaultdict(list)
for pid, q, r, n in rows:
    byq[round(q, 4)].append((pid, r, n))

say("=" * 110)
say("PRODUK DENGAN TOTAL QTY PERSIS SAMA (indikasi kuantitas dibangkitkan, bukan penjualan nyata)")
say("=" * 110)
hit = 0
for q, lst in sorted(byq.items(), reverse=True):
    if len(lst) > 1:
        hit += 1
        if hit <= 25:
            say("qty %6.0f  -> %s" % (q, [
                "%s [%s, %d baris, rev %s]" % (
                    (Prod.browse(p).display_name or "")[:42], p, n, money(r)) for p, r, n in lst]))
say("total kelompok qty kembar: %d" % hit)

say("")
say("=" * 110)
say("JUMLAH BARIS POS ORDER LINE per produk (distribusi)")
say("=" * 110)
cr.execute("""
    SELECT COUNT(*), MIN(cnt), MAX(cnt) FROM (
      SELECT pol.product_id, COUNT(*) cnt FROM pos_order_line pol
        JOIN pos_order po ON po.id=pol.order_id
       WHERE po.state IN ('paid','done','invoiced')
         AND po.date_order >= '2026-06-01' AND po.date_order < '2026-09-01'
       GROUP BY 1) t""")
say("   %s" % (cr.fetchone(),))

# cek genap/tidak: bila tiap produk selalu muncul tiap sesi dengan qty sama -> artefak
say("")
say("Cek pasangan PKG SAMBAL IJO PADANG (GEPREK SAMBAL +NASI) vs PKC (CRISPY DADA/PAHA ATAS+NASI+MINUM)")
for nm in ("PKG SAMBAL IJO PADANG (GEPREK SAMBAL +NASI)",
           "PKC (CRISPY DADA/PAHA ATAS+NASI+MINUM)",
           "PKG SAMBAL KOREK SURABAYA",
           "PKG SAMBAL KOREK SURABAYA (GEPREK SAMBAL +NASI)"):
    p = Prod.search([("display_name", "=", nm)], limit=1)
    if not p:
        say("   [%s] tidak ditemukan" % nm[:60])
        continue
    cr.execute("""SELECT to_char(po.date_order,'YYYY-MM-DD'), SUM(pol.qty)
                    FROM pos_order_line pol JOIN pos_order po ON po.id=pol.order_id
                   WHERE pol.product_id=%s AND po.state IN ('paid','done','invoiced')
                     AND po.date_order >= '2026-06-01' AND po.date_order < '2026-09-01'
                   GROUP BY 1 ORDER BY 1 LIMIT 6""", (p.id,))
    say("   %-52s id=%-5s contoh harian: %s" % (nm[:52], p.id, cr.fetchall()))
say("=" * 110)
env.cr.rollback()
