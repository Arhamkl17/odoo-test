# -*- coding: utf-8 -*-
"""
juni_juli_99c_ghost_origin.py — asal-usul 6 produk "pendek" (READ-ONLY).

Petunjuk yang diuji: di `Produk (product.template).xlsx` KEENAM produk bernama pendek
punya "Terakhir Diperbarui pada" yang SAMA PERSIS (2026-08-25 08:55:25), sedangkan
pasangan panjangnya tersebar di 2026-08-24. Detik yang sama = satu operasi massal.

Di sini kita cek apakah timestamp di database Test1 cocok, dan kapan BOM-nya dibuat.
"""
cr = env.cr
PT = env["product.template"]
PP = env["product.product"]
BOM = env["mrp.bom"]

say = lambda m="": print(m)

PAIRS = [
    (567, 604, "SAMBAL KOREK SURABAYA"),
    (566, 603, "SAMBAL IJO PADANG"),
    (568, 608, "SAMBAL RICA MANADO"),
    (584, 625, "MEVVAH"),
    (572, 630, "KULIT CRISPY"),
    (585, 618, "INDOMIE GEPREK SAMBAL LOKAL"),
]

say("=" * 122)
say("ASAL-USUL PRODUK KEMBAR — timestamp di database")
say("=" * 122)
say("")
say("%-5s %-52s %-22s %-22s %-10s %-10s" % (
    "tmpl", "nama", "create_date", "write_date", "create_uid", "write_uid"))
say("-" * 122)
for a, b, label in PAIRS:
    for t in (a, b):
        cr.execute("""SELECT name->>'en_US', create_date, write_date, create_uid, write_uid
                        FROM product_template WHERE id=%s""", (t,))
        nm, cd, wd, cu, wu = cr.fetchone()
        say("%-5s %-52s %-22s %-22s %-10s %-10s" % (
            t, (nm or "")[:52], str(cd)[:19], str(wd)[:19], cu, wu))
    say("")

say("─" * 122)
say("APA YANG MEMBUAT PERUBAHAN PADA 2026-08-25 08:55:25?")
say("")
cr.execute("""
    SELECT t.name->>'en_US', t.write_date, t.create_date,
           (SELECT COUNT(*) FROM mrp_bom b WHERE b.product_tmpl_id=t.id) nb,
           (SELECT COUNT(*) FROM pos_order_line l
              JOIN product_product p ON p.id=l.product_id WHERE p.product_tmpl_id=t.id) norder
      FROM product_template t
     WHERE t.write_date::date = '2026-08-25'
     ORDER BY t.write_date, t.name
""")
rows = cr.fetchall()
say("   %d product_template ditulis pada 2026-08-25" % len(rows))
say("")
say("   %-22s %-56s %5s %8s" % ("write_date", "nama", "BOM", "order"))
say("   " + "-" * 100)
for nm, wd, cd, nb, no in rows:
    say("   %-22s %-56s %5d %8d" % (str(wd)[:19], (nm or "")[:56], nb, no))

say("")
say("─" * 122)
say("BOM: kapan dibuat, dan berapa usernya?")
say("")
for a, b, label in PAIRS:
    for t in (a, b):
        cr.execute("""SELECT id, create_date, write_date, create_uid
                        FROM mrp_bom WHERE product_tmpl_id=%s""", (t,))
        for bid, cd, wd, cu in cr.fetchall():
            say("   tmpl %-5s bom %-6s dibuat %-22s ditulis %-22s uid=%s" % (
                t, bid, str(cd)[:19], str(wd)[:19], cu))
    say("")

say("─" * 122)
say("POS config mana yang memuat produk 'pendek' (kalau ada, berarti benar-benar dijual)?")
say("")
cr.execute("""
    SELECT p.product_tmpl_id, t.name->>'en_US', COUNT(DISTINCT s.config_id)
      FROM pos_order_line l
      JOIN pos_order o ON o.id=l.order_id
      JOIN pos_session s ON s.id=o.session_id
      JOIN product_product p ON p.id=l.product_id
      JOIN product_template t ON t.id=p.product_tmpl_id
     WHERE p.product_tmpl_id IN (604,603,608,625,630,618)
     GROUP BY 1,2 ORDER BY 1
""")
for t, nm, ncfg in cr.fetchall():
    say("   tmpl %-5s %-52s dipakai di %d POS config" % (t, (nm or "")[:52], ncfg))
say("")
say("=" * 122)
