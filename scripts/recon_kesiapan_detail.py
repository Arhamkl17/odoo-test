# -*- coding: utf-8 -*-
"""
recon_kesiapan_detail.py — DETAIL ANOMALI (READ-ONLY), lanjutan recon_kesiapan_harga_bom.py.

Menggali:
  P1. duplikat nama (Gift Card · SAMBAL * · MEVVAH)
  P2. 3 pasang produk kembar sisa (MEVVAH · KULIT CRISPY · INDOMIE)
  P3. BOM yatim 94 + item pricelist yatim MEVVAH
  P4. margin < 45% dipisah: HPP terverifikasi vs belum
  P5. kesiapan prasyarat regenerate (fiscal year, date_range, asset, lock date, opening move)

  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http \
    --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
    < scripts/recon_kesiapan_detail.py
"""
import collections
import datetime

cr = env.cr
say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))
SEP = "=" * 116

PT = env["product.template"]
PP = env["product.product"]
PLI = env["product.pricelist.item"]
BOM = env["mrp.bom"]

say(SEP)
say("DETAIL ANOMALI HARGA & BOM — %s — READ-ONLY" % datetime.date.today())
say(SEP)

# ---------------------------------------------------------------- P1
say("")
say("[P1] DUPLIKAT NAMA — rincian")
say("")
cr.execute("""
    SELECT (pt.name->>'en_US'), pp.id, pt.id, pt.active, pt.available_in_pos, pt.sale_ok,
           pt.list_price, COALESCE(pc.name,''), COALESCE((uu.name->>'en_US'),''),
           COALESCE(pt.default_code,''), COALESCE((pp.standard_price->>'1')::numeric,0)
      FROM product_product pp JOIN product_template pt ON pt.id=pp.product_tmpl_id
      LEFT JOIN product_category pc ON pc.id=pt.categ_id
      LEFT JOIN uom_uom uu ON uu.id=pt.uom_id
     WHERE pt.name->>'en_US' IN (
        SELECT pt2.name->>'en_US' FROM product_product pp2
          JOIN product_template pt2 ON pt2.id=pp2.product_tmpl_id
         WHERE pt2.active GROUP BY 1 HAVING count(*)>1)
     ORDER BY 1, 2
""")
for nama, ppid, tid, act, ipos, sok, lpx, cat, uom, dc, sp in cr.fetchall():
    say("   %-46s pp=%-4s tmpl=%-4s aktif=%-5s POS=%-5s sale=%-5s harga=%-10s sp=%-10s [%s/%s]" % (
        (nama or "")[:46], ppid, tid, act, ipos, sok, money(lpx), money(sp), cat, uom))

# ---------------------------------------------------------------- P2
say("")
say("[P2] PASANGAN KEMBAR SISA — produk · harga · BOM · penjualan")
PASANGAN = [
    ("PKG MEVVAH (AYAM GEPREK+TELUR ORAK ARIK+INDOMIE MEVVAH)", "PAKET MEVVAH BERDUA"),
    ("PAKET KULIT CRISPY + NASI + MINUM", "PAKET KULIT CRISPY"),
    ("PKG MIE (AYAM GEPREK+SAMBAL LOKAL+INDOMIE)", "PKG INDOMIE GEPREK SAMBAL LOKAL"),
]
for a, b in PASANGAN:
    say("")
    for nm in (a, b):
        cr.execute("""SELECT pp.id, pt.id, pt.active, pt.available_in_pos, pt.list_price,
                             (pt.name->>'en_US')
                        FROM product_product pp JOIN product_template pt ON pt.id=pp.product_tmpl_id
                       WHERE pt.name->>'en_US' = %s""", (nm,))
        for ppid, tid, act, ipos, lpx, fullname in cr.fetchall():
            cr.execute("""SELECT count(*), COALESCE(SUM(l.product_qty),0)
                            FROM mrp_bom_line l JOIN mrp_bom b ON b.id=l.bom_id
                           WHERE b.product_tmpl_id=%s AND b.active""", (tid,))
            nb, nq = cr.fetchone()
            say("   %-62s pp=%-4s tmpl=%-4s aktif=%-5s POS=%-5s harga=%-10s bom=%s baris/qty=%s" % (
                fullname[:62], ppid, tid, act, ipos, money(lpx), nb, nq))

# ---------------------------------------------------------------- P3
say("")
say("[P3] BOM & ITEM PRICELIST YATIM")
say("")
b94 = BOM.with_context(active_test=False).browse(94)
if b94.exists():
    say("   BOM 94 : aktif=%s tmpl=%s (%s) baris=%s" % (
        b94.active, b94.product_tmpl_id.id, b94.product_tmpl_id.display_name,
        len(b94.bom_line_ids)))
cr.execute("""
    SELECT pi.id, pl.name->>'en_US', (pt.name->>'en_US'), pt.active, pi.fixed_price
      FROM product_pricelist_item pi
      JOIN product_template pt ON pt.id=pi.product_tmpl_id
      JOIN product_pricelist pl ON pl.id=pi.pricelist_id
     WHERE NOT (pt.active AND pt.available_in_pos AND pt.sale_ok) ORDER BY 2
""")
for iid, pl, pn, act, px in cr.fetchall():
    say("   item %-4s [%-22s] %-52s aktif=%-5s harga=%s" % (iid, pl, (pn or "")[:52], act, money(px)))
cr.execute("""
    SELECT b.id, b.active, (bt.name->>'en_US'), bt.active
      FROM mrp_bom b JOIN product_template bt ON bt.id=b.product_tmpl_id
     WHERE NOT (bt.active AND bt.available_in_pos AND bt.sale_ok) ORDER BY 1
""")
for bid, bact, pn, act in cr.fetchall():
    say("   BOM  %-4s aktif=%-5s → %-52s produk_aktif=%s" % (bid, bact, (pn or "")[:52], act))

# ---------------------------------------------------------------- P4
say("")
say("[P4] MARGIN < 45% — dipisah: HPP terverifikasi vs belum")
say("")
cr.execute("""
    SELECT pp.id, pt.id, (pt.name->>'en_US'), pt.list_price
      FROM product_template pt JOIN product_product pp ON pp.product_tmpl_id=pt.id
     WHERE pt.available_in_pos AND pt.active AND pt.sale_ok ORDER BY 3
""")
rows = cr.fetchall()

# klien sourced set
import os, re, openpyxl
XLSX = next((p for p in ("product_photos/data sheet master/HARGA BAHAN BAKU GUDANG.xlsx",
                         "/root/odoo/product_photos/data sheet master/HARGA BAHAN BAKU GUDANG.xlsx")
             if os.path.exists(p)), None)
klien = set()
if XLSX:
    wb = openpyxl.load_workbook(XLSX, data_only=True, read_only=True)
    ws = wb.worksheets[0]; rws = list(ws.iter_rows(values_only=True)); wb.close()
    hi = next(i for i, r in enumerate(rws[:8]) if any((c or "") == "Nama Barang" for c in r))
    hdr = [("" if c is None else str(c).strip()) for c in rws[hi]]
    i_nm = hdr.index("Nama Barang")
    i_kc = next(j for j, h in enumerate(hdr) if h.upper().startswith("HRG/SAT"))
    for r in rws[hi+1:]:
        c = list(r) + [None]*8
        if not c[i_nm]:
            continue
        try:
            float(c[i_kc])
        except (TypeError, ValueError):
            continue
        klien.add(re.sub(r"[^A-Z0-9]", "", str(c[i_nm]).upper()))
ALIAS = {"BUBUK LEMON TEA": "LEMON TEA", "AIR GELAS": "AIR MINERAL GELAS",
         "KEMASAN SEGEPOK": "KEMASAN SEGEPOK (BIASA)", "PLASTIK KLIP 8X5": "PLASTIK KLIP 5X8",
         "MIKA BUNDAR": "MIKA BURGER"}


def bersumber(n):
    return re.sub(r"[^A-Z0-9]", "", str(n or "").upper()) in klien or \
        re.sub(r"[^A-Z0-9]", "", str(ALIAS.get(str(n).upper(), "")).upper()) in klien


terverif, belum = [], []
for ppid, tid, nm, lpx in rows:
    cr.execute("""
        SELECT bl.product_qty, (ct.name->>'en_US'), COALESCE((cp.standard_price->>'1')::numeric,0)
          FROM mrp_bom b JOIN mrp_bom_line bl ON bl.bom_id=b.id
          JOIN product_product cp ON cp.id=bl.product_id
          JOIN product_template ct ON ct.id=cp.product_tmpl_id
         WHERE b.product_tmpl_id=%s AND b.active
    """, (tid,))
    baris = cr.fetchall()
    if baris:
        hpp = sum(float(q)*float(h) for q, _, h in baris)
        ver = sum(float(q)*float(h) for q, n, h in baris if bersumber(n))
    else:
        cr.execute("SELECT COALESCE((standard_price->>'1')::numeric,0) FROM product_product WHERE id=%s", (ppid,))
        hpp = float(cr.fetchone()[0] or 0)
        ver = hpp if bersumber(nm) else 0.0
    px = float(lpx or 0)
    if px <= 0:
        continue
    m = (1 - hpp/px) * 100
    if m >= 45:
        continue
    pct = (ver/hpp*100) if hpp else 0
    (terverif if pct >= 80 else belum).append((nm, px, hpp, m, pct))

say("   A. HPP cukup terverifikasi (>=80%%) — kandidat koreksi HARGA/BOM  : %d" % len(terverif))
for nm, px, hpp, m, pct in sorted(terverif, key=lambda x: x[3]):
    say("      %-46s jual=%-10s HPP=%-11s margin=%5.1f%%  verif=%.0f%%" % (
        nm[:46], money(px), money(hpp), m, pct))
say("")
say("   B. HPP BELUM terverifikasi (<80%%) — JANGAN diutak-atik dulu    : %d" % len(belum))
for nm, px, hpp, m, pct in sorted(belum, key=lambda x: x[3]):
    say("      %-46s jual=%-10s HPP=%-11s margin=%5.1f%%  verif=%.0f%%" % (
        nm[:46], money(px), money(hpp), m, pct))

# ---------------------------------------------------------------- P5
say("")
say("[P5] KESIAPAN PRASYARAT REGENERATE")
say("")
for label, model, dom in (
        ("fiscal year", "account.fiscal.year", []),
        ("date.range", "date.range", []),
        ("date.range.type", "date.range.type", []),
        ("account.asset", "account.asset", []),
        ("product.supplierinfo", "product.supplierinfo", []),
        ("res.partner (supplier)", "res.partner", [("supplier_rank", ">", 0)]),
        ("res.partner (customer)", "res.partner", [("customer_rank", ">", 0)]),
):
    try:
        n = env[model].search_count(dom)
    except Exception as e:
        n = "ERR %s" % repr(e)[:40]
    say("   %-26s : %s" % (label, n))
c = env["res.company"].search([], limit=1)
say("   fiscalyear_lock_date        : %s" % c.fiscalyear_lock_date)
say("   account_opening_move_id     : %s" % (c.account_opening_move_id.id or "(kosong)"))
say("   pos_update_stock_quantities : %s" % getattr(c, "point_of_sale_update_stock_quantities", "(n/a)"))
say("")
say("   pos.config aktif:")
for cfg in env["pos.config"].search([]):
    say("      id=%-3s %-22s pricelist=%-24s metode=%d preset(default=%s)" % (
        cfg.id, cfg.name, cfg.pricelist_id.name or "-",
        len(cfg.payment_method_ids), cfg.default_preset_id.name or "-"))
say("")
say("   produk POS tanpa kategori : %d" % len(env["product.template"].search(
    [("available_in_pos", "=", True), ("active", "=", True), ("sale_ok", "=", True)]).filtered(
    lambda t: not t.categ_id)))
say("   produk POS tanpa UOM      : %d" % len(env["product.template"].search(
    [("available_in_pos", "=", True), ("active", "=", True), ("sale_ok", "=", True)]).filtered(
    lambda t: not t.uom_id)))
say(SEP)
cr.rollback()
