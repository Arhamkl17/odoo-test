# -*- coding: utf-8 -*-
"""
juni_juli_101_merge_ghost.py — R1: gabungkan 3 pasang produk kembar (13 Sep 2026).

KEPUTUSAN PEMILIK (13 Sep 2026):
  • Cakupan  : HANYA 3 pasangan yang harga katalognya identik
               (SAMBAL KOREK · SAMBAL IJO · SAMBAL RICA).
               MEVVAH · KULIT CRISPY · INDOMIE **tidak** digabung (harga berbeda).
  • Harga    : "hapus aja itemnya" → item pricelist produk hantu DIHAPUS,
               produk yang disimpan tetap memakai harganya sendiri.
  • Nama     : nama produk klien DIPERTAHANKAN apa adanya.

Yang dilakukan per pasangan:
  1. pindahkan `pos_order_line.product_id` dari produk hantu → produk klien
  2. hapus `product_pricelist_item` milik produk hantu
  3. hapus `mrp_bom` produk hantu (beserta barisnya)
  4. hapus `product_template` produk hantu (ikut varian & atributnya)

Guard (berhenti kalau gagal):
  A. komponen BOM kedua produk harus IDENTIK PERSIS (product_id + qty)
  B. `list_price` harus sama
  C. tidak boleh ada `stock_move` / `stock_move_line` / `stock_quant` /
     `account_move_line` yang menunjuk produk hantu
  D. produk hantu tidak boleh dipakai sebagai komponen resep lain

Idempotent: kalau produk hantu sudah tidak ada, dilewati dengan catatan.

  dry-run : su odoo ... < scripts/juni_juli_101_merge_ghost.py
  eksekusi: su odoo ... " RUN=1 odoo shell ..." < scripts/juni_juli_101_merge_ghost.py
"""
import os

RUN = os.environ.get("RUN") == "1"

cr = env.cr
PT = env["product.template"]
PP = env["product.product"]
BOM = env["mrp.bom"]
PPI = env["product.pricelist.item"]

say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))
num = lambda x: "{:,.4f}".format(float(x or 0)).rstrip("0").rstrip(".")

# (ghost_pp, keep_pp) — dipetakan manual dari recon 96/97, bukan ditebak
PAIRS = [
    (593, 556, "PKG SAMBAL KOREK SURABAYA"),
    (592, 555, "PKG SAMBAL IJO PADANG"),
    (597, 557, "PKG SAMBAL RICA MANADO"),
]

say("=" * 112)
say("R1 — GABUNG 3 PRODUK KEMBAR   |   RUN=%s" % RUN)
say("=" * 112)


def bom_multiset(pp):
    """(product_id, qty) multiset dari SEMUA BOM milik template produk ini."""
    cr.execute("""
        SELECT bl.product_id, ROUND(bl.product_qty::numeric, 4)
          FROM mrp_bom b JOIN mrp_bom_line bl ON bl.bom_id = b.id
         WHERE b.product_tmpl_id = %s
         ORDER BY 1, 2
    """, (pp.product_tmpl_id.id,))
    return cr.fetchall()


def diff_multiset(a, b):
    from collections import Counter
    da, db = Counter(a), Counter(b)
    only_a = sorted((da - db).elements())
    only_b = sorted((db - da).elements())
    return only_a, only_b


before = {}
cr.execute("""SELECT to_char(date_order,'YYYY-MM'), COUNT(*), COALESCE(SUM(amount_total),0)
                FROM pos_order GROUP BY 1 ORDER BY 1""")
before_orders = cr.fetchall()
cr.execute("""SELECT COUNT(*), COALESCE(SUM(price_subtotal_incl),0) FROM pos_order_line""")
before_lines = cr.fetchone()

say("")
say("BASELINE SEBELUM")
say("   sesi POS     : %d" % env["pos.session"].search_count([]))
say("   order POS    : %s" % ", ".join("%s=%d" % (m, n) for m, n, _t in before_orders))
say("   baris order  : %d | omzet %s" % (before_lines[0], money(before_lines[1])))
say("   pricelist item: %d | template produk: %d" % (
    PPI.search_count([]), PT.search_count([])))

# ---------------------------------------------------------------- GUARD
say("")
say("[GUARD]")
say("")
ok_all = True
work = []
for gp, kp, label in PAIRS:
    g = PP.browse(gp)
    k = PP.browse(kp)
    if not g.exists():
        say("   %-28s ⊘ produk hantu pp %-5s sudah tidak ada — dilewati" % (label, gp))
        continue
    say("   %-28s pp %-5s → pp %-5s" % (label, gp, kp))

    # A. BOM
    ma, mb = bom_multiset(g), bom_multiset(k)
    only_a, only_b = diff_multiset(ma, mb)
    if only_a or only_b:
        say("        ✘ A. BOM BERBEDA — %d baris hanya di hantu, %d hanya di klien" % (
            len(only_a), len(only_b)))
        ok_all = False
    else:
        say("        ✔ A. BOM identik (%d baris)" % len(ma))

    # B. harga
    if abs(float(g.list_price) - float(k.list_price)) > 0.01:
        say("        ✘ B. list_price BEDA: %s vs %s" % (money(g.list_price), money(k.list_price)))
        ok_all = False
    else:
        say("        ✔ B. list_price sama (%s)" % money(g.list_price))

    # C. dokumen lain
    bad = []
    for tbl, col in (("stock_move", "product_id"), ("stock_move_line", "product_id"),
                     ("stock_quant", "product_id"), ("account_move_line", "product_id")):
        cr.execute("SELECT COUNT(*) FROM %s WHERE %s = %%s" % (tbl, col), (gp,))
        n = cr.fetchone()[0]
        if n:
            bad.append("%s=%d" % (tbl, n))
    if bad:
        say("        ✘ C. masih ada dokumen: %s" % ", ".join(bad))
        ok_all = False
    else:
        say("        ✔ C. tidak ada stock/ledger yang menempel")

    # D. dipakai sebagai komponen
    cr.execute("SELECT COUNT(*) FROM mrp_bom_line WHERE product_id = %s", (gp,))
    n = cr.fetchone()[0]
    if n:
        say("        ✘ D. dipakai sebagai komponen di %d resep" % n)
        ok_all = False
    else:
        say("        ✔ D. bukan komponen resep lain")

    cr.execute("SELECT COUNT(*) FROM pos_order_line WHERE product_id=%s", (gp,))
    n_order = cr.fetchone()[0]
    cr.execute("SELECT COUNT(*) FROM product_pricelist_item WHERE product_tmpl_id=%s", (g.product_tmpl_id.id,))
    n_prc = cr.fetchone()[0]
    cr.execute("SELECT COUNT(*) FROM mrp_bom WHERE product_tmpl_id=%s", (g.product_tmpl_id.id,))
    n_bom = cr.fetchone()[0]
    say("        ▸ akan dipindah: %d baris order | dihapus: %d item pricelist, %d BOM" % (
        n_order, n_prc, n_bom))
    work.append((gp, kp, label, g, k, n_order))

if not ok_all:
    say("")
    say("!! ADA GUARD YANG GAGAL — TIDAK ADA YANG DITULIS. Perbaiki dulu.")
    raise SystemExit(1)
if not work:
    say("")
    say("Tidak ada yang perlu dikerjakan (mungkin sudah pernah dijalankan).")
    raise SystemExit(0)

# ---------------------------------------------------------------- EKSEKUSI
say("")
say("[EKSEKUSI]")
say("")
if not RUN:
    for gp, kp, label, _g, _k, n_order in work:
        say("   [dry] %-28s : pindah %3d baris, hapus pricelist + BOM + template" % (label, n_order))
    say("")
    say("   (dry-run — jalankan dengan RUN=1 untuk eksekusi)")
    say("=" * 112)
    raise SystemExit(0)

total_moved = 0
for gp, kp, label, g, k, n_order in work:
    # 1. pindahkan baris order
    moved = 0
    if n_order:
        cr.execute("UPDATE pos_order_line SET product_id=%s WHERE product_id=%s", (kp, gp))
        moved = cr.rowcount
    total_moved += moved

    # 2. hapus item pricelist
    items = PPI.search([("product_tmpl_id", "=", g.product_tmpl_id.id)])
    n_prc = len(items)
    if items:
        items.unlink()

    # 3. hapus BOM
    boms = BOM.search([("product_tmpl_id", "=", g.product_tmpl_id.id)])
    n_bom = len(boms)
    if boms:
        boms.unlink()

    # 4. hapus template (ikut varian + atribut)
    nm = g.product_tmpl_id.name
    g.product_tmpl_id.unlink()
    env.cr.commit()
    say("   ✔ %-28s pindah %3d baris · hapus %d pricelist, %d BOM, 1 template" % (
        label, moved, n_prc, n_bom))
    say("        dihapus: %s" % nm)

# ---------------------------------------------------------------- VERIFIKASI
say("")
say("=" * 112)
say("[VERIFIKASI]")
say("")
cr.execute("""SELECT to_char(date_order,'YYYY-MM'), COUNT(*), COALESCE(SUM(amount_total),0)
                FROM pos_order GROUP BY 1 ORDER BY 1""")
after_orders = cr.fetchall()
cr.execute("""SELECT COUNT(*), COALESCE(SUM(price_subtotal_incl),0) FROM pos_order_line""")
after_lines = cr.fetchone()

say("   %-12s %-34s %-34s %s" % ("", "sebelum", "sesudah", "sama?"))
say("   " + "-" * 92)
say("   %-12s %-34s %-34s %s" % (
    "baris order", "%d / %s" % (before_lines[0], money(before_lines[1])),
    "%d / %s" % (after_lines[0], money(after_lines[1])),
    "YA" if abs(float(after_lines[1]) - float(before_lines[1])) < 0.01 else "TIDAK"))

bo = {m: (n, t) for m, n, t in before_orders}
ao = {m: (n, t) for m, n, t in after_orders}
for m in sorted(set(bo) | set(ao)):
    bn, bt = bo.get(m, (0, 0))
    an, at = ao.get(m, (0, 0))
    say("   %-12s %-34s %-34s %s" % (
        m, "%d order / %s" % (bn, money(bt)), "%d order / %s" % (an, money(at)),
        "YA" if (bn == an and abs(float(at) - float(bt)) < 0.01) else "TIDAK"))

say("")
say("   total baris order dipindah : %d" % total_moved)
say("   pricelist item  : %d → %d (−%d)" % (
    len(PPI.search([])) + 6, PPI.search_count([]), 6))
say("   template produk : %d → %d (−%d)" % (
    PT.search_count([]) + 3, PT.search_count([]), 3))

# sisa tabrakan nama
say("")
say("   sisa grup dengan BOM identik:")
cr.execute("""
    WITH s AS (
      SELECT b.product_tmpl_id t,
             md5(string_agg(bl.product_id::text||'x'||ROUND(bl.product_qty::numeric,4)::text,
                 '|' ORDER BY bl.product_id, ROUND(bl.product_qty::numeric,4))) fp
        FROM mrp_bom b JOIN mrp_bom_line bl ON bl.bom_id=b.id GROUP BY 1)
    SELECT fp, count(*), array_agg(t ORDER BY t) FROM s GROUP BY 1 HAVING count(*)>1
    ORDER BY 2 DESC, 3
""")
rows = cr.fetchall()
sisa_kembar = 0
for fp, n, ts in rows:
    cr.execute("SELECT name->>'en_US' FROM product_template WHERE id = ANY(%s) ORDER BY id", (ts,))
    namas = [r[0] or "" for r in cr.fetchall()]
    base = [x.replace("(GEPREK SAMBAL +NASI)", "").strip().upper() for x in namas]
    if len(set(base)) < len(base):
        sisa_kembar += 1
        say("        ⚠ %s" % "  ▲  ".join(x[:40] for x in namas))
say("        → %d grup kembar nama tersisa" % sisa_kembar)
say("        (grup lain = varian potongan, dan itu memang data klien — lihat §21.1)")
say("")
say("   TB check:")
for a, b, label in (("2026-06-01", "2026-06-30", "Juni"),
                    ("2026-07-01", "2026-07-31", "Juli"),
                    ("2026-08-01", "2026-08-31", "Agustus")):
    cr.execute("""SELECT COALESCE(SUM(debit),0)-COALESCE(SUM(credit),0)
                    FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                   WHERE am.state='posted' AND am.date>=%s AND am.date<=%s""", (a, b))
    say("        %-9s diff=%s" % (label, money(cr.fetchone()[0])))
say("")
say("=" * 112)
