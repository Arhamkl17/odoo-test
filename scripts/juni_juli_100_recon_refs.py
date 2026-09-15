# -*- coding: utf-8 -*-
"""
juni_juli_100_recon_refs.py — sisir SEMUA referensi ke 3 produk hantu (READ-ONLY).

Target (keputusan pemilik: hanya 3 pasangan berharga identik):
    tmpl 604 / pp 593  PKG SAMBAL KOREK SURABAYA   → gabung ke tmpl 567 / pp 556
    tmpl 603 / pp 592  PKG SAMBAL IJO PADANG       → gabung ke tmpl 566 / pp 555
    tmpl 608 / pp 597  PKG SAMBAL RICA MANADO      → gabung ke tmpl 568 / pp 557

Menemukan tiap kolom di seluruh skema yang bernama product_id / product_tmpl_id /
variant_id, lalu menghitung berapa baris yang menunjuk ke produk hantu. Ini yang
menentukan aman/tidaknya menghapus.
"""
cr = env.cr

GHOST_PP = {593: "PKG SAMBAL KOREK SURABAYA", 592: "PKG SAMBAL IJO PADANG",
            597: "PKG SAMBAL RICA MANADO"}
GHOST_TMPL = {604: 593, 603: 592, 608: 597}
KEEP = {593: (556, 567), 592: (555, 566), 597: (557, 568)}

say = lambda m="": print(m)

say("=" * 116)
say("SISIR REFERENSI — 3 PRODUK HANTU   (read-only)")
say("=" * 116)

cr.execute("""
    SELECT c.table_name, c.column_name
      FROM information_schema.columns c
      JOIN information_schema.tables t
        ON t.table_name = c.table_name AND t.table_schema = c.table_schema
     WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE'
       AND c.column_name IN ('product_id', 'product_tmpl_id', 'variant_id')
     ORDER BY 1, 2
""")
cols = cr.fetchall()
say("")
say("kolom product_id/product_tmpl_id/variant_id ditemukan: %d" % len(cols))
say("")
say("%-42s %-16s %8s %8s %8s   %s" % ("tabel", "kolom", "KOREK", "IJO", "RICA", "keterangan"))
say("-" * 116)

total_rows = {}
for tbl, col in cols:
    try:
        cr.execute("SELECT %s FROM %s WHERE %s = ANY(%%s)" % (col, tbl, col),
                   (list(GHOST_PP),))
        n_pp = cr.rowcount if cr.rowcount >= 0 else len(cr.fetchall())
    except Exception:
        env.cr.rollback()
        n_pp = None
    try:
        cr.execute("SELECT %s FROM %s WHERE %s = ANY(%%s)" % (col, tbl, col),
                   (list(GHOST_TMPL),))
        n_tmpl = cr.rowcount if cr.rowcount >= 0 else len(cr.fetchall())
    except Exception:
        env.cr.rollback()
        n_tmpl = None
    n = max(n_pp or 0, n_tmpl or 0)
    if n:
        total_rows[tbl] = n
        ket = ""
        if tbl == "pos_order_line":
            ket = "→ PINDAH ke produk klien"
        elif tbl == "mrp_bom":
            ket = "→ HAPUS (BOM hantu)"
        elif tbl == "product_pricelist_item":
            ket = "→ HAPUS (keputusan pemilik)"
        elif tbl == "mrp_bom_line":
            ket = "⚠ dipakai sebagai KOMPONEN — periksa!"
        else:
            ket = "⚠ perlu ditangani"
        say("%-42s %-16s %8s %8s %8s   %s" % (
            tbl, col,
            "ya" if (n_pp or 0) else "-", "ya" if (n_tmpl or 0) else "-", "", ket))

say("")
say("TABEL TERDAMPAK: %s" % ", ".join(sorted(total_rows)) if total_rows else "tidak ada referensi")

# ---------------------------------------------------------------- rincian penting
say("")
say("─" * 116)
for tbl in ("pos_order_line", "product_pricelist_item", "mrp_bom", "mrp_bom_line",
            "stock_move", "stock_move_line", "stock_quant", "account_move_line"):
    for target, label in ((list(GHOST_PP), "pp"), (list(GHOST_TMPL), "tmpl")):
        col = "product_tmpl_id" if label == "tmpl" else "product_id"
        try:
            cr.execute("SELECT COUNT(*) FROM %s WHERE %s = ANY(%%s)" % (tbl, col), (target,))
            n = cr.fetchone()[0]
        except Exception:
            env.cr.rollback()
            continue
        if n:
            say("   %-28s %-14s %-6s : %d baris" % (tbl, col, label, n))

say("")
say("─" * 116)
say("RINCIAN pos_order_line per produk hantu (yang akan dipindah)")
say("")
cr.execute("""
    SELECT l.product_id, t.name->>'en_US', COUNT(*), COALESCE(SUM(l.qty),0),
           COALESCE(SUM(l.price_subtotal_incl),0)
      FROM pos_order_line l
      JOIN product_product p ON p.id = l.product_id
      JOIN product_template t ON t.id = p.product_tmpl_id
     WHERE l.product_id = ANY(%s)
     GROUP BY 1,2 ORDER BY 1
""", (list(GHOST_PP),))
for pid, nm, n, q, rev in cr.fetchall():
    keep_pp, keep_t = KEEP[pid]
    say("   pp %-5s %-42s %5d baris | qty %9.2f | %s" % (pid, (nm or "")[:42], n, q, "{:,.2f}".format(rev)))
    say("        → dipindah ke pp %-5s (tmpl %s)" % (keep_pp, keep_t))

say("")
say("─" * 116)
say("APAKAH produk hantu dipakai sebagai KOMPONEN resep lain? (kalau ya, jangan dihapus)")
say("")
cr.execute("SELECT COUNT(*) FROM mrp_bom_line WHERE product_id = ANY(%s)", (list(GHOST_PP),))
say("   mrp_bom_line.product_id = produk hantu : %d" % cr.fetchone()[0])

say("")
say("─" * 116)
say("BANDINGKAN mutu data: apakah ketiga pasangan benar-benar identik?")
say("")
for gp, (kp, kt) in sorted(KEEP.items()):
    gt = [t for t, p in GHOST_TMPL.items() if p == gp][0]
    cr.execute("""SELECT name->>'en_US', list_price, available_in_pos, active
                    FROM product_template WHERE id IN (%s, %s)""", (gt, kt))
    rows = cr.fetchall()
    say("   pp %-5s vs %-5s" % (gp, kp))
    for nm, lp, aip, act in rows:
        say("        %-58s list_price=%-12s POS=%-5s aktif=%s" % ((nm or "")[:58], lp, aip, act))
    cr.execute("""SELECT COUNT(*), md5(string_agg(product_id::text||'x'||
                    ROUND(product_qty::numeric,4)::text, '|' ORDER BY product_id,
                    ROUND(product_qty::numeric,4)::text))
                    FROM mrp_bom_line WHERE bom_id IN
                    (SELECT id FROM mrp_bom WHERE product_tmpl_id IN (%s,%s))""", (gt, kt))
    n, md = cr.fetchone()
    say("        sidik jari komponen gabungan: %d baris, md5=%s" % (n, (md or "")[:16]))
    say("")

say("=" * 116)
