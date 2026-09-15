# -*- coding: utf-8 -*-
"""
juni_juli_93_recon_ghost.py — RECON R1: produk kembar/hantu (READ-ONLY, tidak menulis apa pun).

Tujuan: sebelum menggabungkan, pastikan
  [1] pasangan mana saja yang benar-benar kembar identik (qty, omzet, HPP, HPP/unit, harga)
  [2] berapa baris pos_order_line / BOM / item pricelist yang menempel di masing-masing
  [3] apa yang akan hilang kalau produk hantu dihapus (harus nol supaya aman)

Jalankan (read-only):
  su odoo -s /bin/bash -c "cd /workspaces/odoo-test && odoo shell -d Test1 \
      --db_host=db --db_user=odoo --db_password=odoo --no-http --logfile=/dev/null \
      < scripts/juni_juli_93_recon_ghost.py"
"""
cr = env.cr
PT = env["product.template"]
PP = env["product.product"]
POL = env["pos.order.line"]
BOM = env["mrp.bom"]
PPI = env["product.pricelist.item"]

say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))
qty = lambda x: "{:,.4f}".format(float(x or 0)).rstrip("0").rstrip(".")


def aid(code):
    cr.execute("SELECT id FROM account_account WHERE code_store->>'1'=%s LIMIT 1", (code,))
    r = cr.fetchone()
    return r[0] if r else None


say("=" * 112)
say("RECON R1 — PRODUK KEMBAR / HANTU   (read-only, tidak ada yang ditulis)")
say("=" * 112)

# ------------------------------------------------------------------ [1] kandidat kembar
say("")
say("[1] PASANGAN KEMBAR (qty, omzet, HPP, HPP/unit identik)")
say("")
cr.execute("""
    SELECT pp.id, pp.default_code, pt.name->>'en_US',
           COALESCE(SUM(pol.qty), 0),
           COALESCE(SUM(pol.price_subtotal_incl), 0),
           COUNT(pol.id)
      FROM product_product pp
      JOIN product_template pt ON pt.id = pp.product_tmpl_id
      LEFT JOIN pos_order_line pol ON pol.product_id = pp.id
     WHERE pt.active IS NOT FALSE
     GROUP BY 1, 2, 3
     HAVING COALESCE(SUM(pol.qty), 0) > 0
     ORDER BY 4 DESC, 1
""")
rows = cr.fetchall()
# kelompokkan yang identik
groups = {}
for pid, code, nama, q, rev, n in rows:
    key = (round(float(q), 4), round(float(rev), 2))
    groups.setdefault(key, []).append((pid, code, nama, int(n)))

say("%-6s %-9s %-52s %10s %16s %7s" % ("id", "kode", "produk", "qty", "omzet", "baris"))
say("-" * 112)
kembar = []
for key, items in sorted(groups.items(), key=lambda kv: -kv[0][1]):
    if len(items) < 2:
        continue
    kembar.append(items)
    for pid, code, nama, n in items:
        say("%-6s %-9s %-52s %10s %16s %7s" % (
            pid, code or "-", (nama or "")[:52], qty(key[0]), money(key[1]), n))
    say(" " * 6 + "└─ " + "  ▲  ".join(str(i[0]) for i in items) + "   ← KEMBAR")
    say("")

say("   jumlah grup kembar: %d grup (%d produk)" % (len(kembar), sum(len(g) for g in kembar)))

# ------------------------------------------------------------------ [2] detail tiap kandidat
ids = [pid for g in kembar for pid, _c, _n, _x in g]
say("")
say("[2] DETAIL TIAP PRODUK KEMBAR — order / BOM / pricelist / template")
say("")
say("%-6s %-5s %-8s %9s %8s %11s %11s %7s %7s" % (
    "id", "tmpl", "kode", "order", "BOM", "jmhBOM", "hPP/unit", "prc", "aktif"))
say("-" * 112)
for pid in sorted(ids):
    pp = PP.browse(pid)
    pt = pp.product_tmpl_id
    norder = POL.search_count([("product_id", "=", pid)])
    boms = BOM.search([("product_tmpl_id", "=", pt.id)])
    nline = sum(len(b.bom_line_ids) for b in boms)
    cr.execute("""
        SELECT COALESCE(SUM(CASE WHEN aa.account_type='expense_direct_cost'
                                 THEN aml.balance END), 0)
          FROM account_move_line aml
          JOIN account_move am ON am.id = aml.move_id
          JOIN account_account aa ON aa.id = aml.account_id
         WHERE am.state='posted' AND aml.product_id = %s
    """, (pid,))
    hpp = float(cr.fetchone()[0] or 0)
    cr.execute("""SELECT COUNT(*) FROM product_pricelist_item WHERE product_id=%s
                   OR (product_tmpl_id=%s AND applied_on='1_product')""", (pid, pt.id))
    nprc = cr.fetchone()[0]
    say("%-6s %-5s %-8s %9d %8d %11d %11s %7d %7s" % (
        pid, pt.id, pp.default_code or "-", norder, len(boms), nline,
        money(hpp), nprc, "ya" if pt.active else "TIDAK"))

# ------------------------------------------------------------------ [3] apa yang akan hilang
say("")
say("[3] DAMPAK PENGGABUNGAN — apa yang harus dipindah / dihapus")
say("")
cr.execute("""
    SELECT pol.product_id, COUNT(*), COALESCE(SUM(pol.qty),0),
           COALESCE(SUM(pol.price_subtotal_incl),0)
      FROM pos_order_line pol
     WHERE pol.product_id = ANY(%s)
     GROUP BY 1 ORDER BY 1
""", (ids,))
tot = 0
for pid, n, q, rev in cr.fetchall():
    say("   pindah  pos_order_line  produk %-6s : %5d baris | qty %10s | %s" % (
        pid, n, qty(q), money(rev)))
    tot += n
say("   TOTAL baris pos_order_line yang dipindah: %d" % tot)

say("")
for pid in sorted(ids):
    pp = PP.browse(pid)
    boms = BOM.search([("product_tmpl_id", "=", pp.product_tmpl_id.id)])
    if boms:
        say("   hapus   BOM              produk %-6s : %d BOM, %d baris  (biaya %s)" % (
            pid, len(boms), sum(len(b.bom_line_ids) for b in boms),
            money(sum(boms.mapped("bom_line_ids.price_subtotal")))))

say("")
cr.execute("""
    SELECT COUNT(*) FROM stock_move WHERE product_id = ANY(%s)
""", (ids,))
say("   stock.move     menempel pada produk kembar : %d" % cr.fetchone()[0])
cr.execute("SELECT COUNT(*) FROM stock_move_line WHERE product_id = ANY(%s)", (ids,))
say("   stock.move.line menempel pada produk kembar : %d" % cr.fetchone()[0])
cr.execute("SELECT COUNT(*) FROM mrp_bom_line WHERE product_id = ANY(%s)", (ids,))
say("   dipakai sebagai komponen di BOM lain      : %d" % cr.fetchone()[0])

# ------------------------------------------------------------------ [4] sumber klien
say("")
say("[4] JEJAK SUMBER — mana yang ada di daftar produk klien?")
say("")
import csv, os
path = "import_data/csv/05_products_with_id.csv"
if os.path.exists(path):
    with open(path, encoding="utf-8-sig") as f:
        names = set()
        for row in csv.DictReader(f):
            for k in ("name", "Name", "nama", "display_name"):
                if k in row and row[k]:
                    names.add(row[k].strip())
                    break
    for pid in sorted(ids):
        nm = PP.browse(pid).product_tmpl_id.name or ""
        hit = [x for x in names if x == nm.strip()]
        say("   %-6s %-52s %s" % (pid, nm[:52], "ADA di daftar produk klien" if hit else "TIDAK ADA (hantu)"))
else:
    say("   %s tidak ditemukan" % path)

say("")
say("=" * 112)
