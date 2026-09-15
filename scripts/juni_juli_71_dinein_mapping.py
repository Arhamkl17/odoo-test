# -*- coding: utf-8 -*-
"""
juni_juli_71_dinein_mapping.py — USULAN PEMETAAN harga Dine In -> produk POS (READ-ONLY).

Memakai pencocokan: (1) alias manual, (2) nama ternormalisasi, (3) kemiripan difflib.
Item yang tidak yakin ditandai PERLU KEPUTUSAN.

  su odoo ... < scripts/juni_juli_71_dinein_mapping.py
"""
import difflib
import re

import openpyxl

PATH = "product_photos/data sheet master/TEMPLATE IMPORT HARGA DINE IN.xlsx"
cr = env.cr
Prod = env["product.product"]
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

# ---------- baca harga dine in (sheet versi BARU = 154) ----------
wb = openpyxl.load_workbook(PATH, data_only=True, read_only=True)
ws = wb.worksheets[0]
rows = list(ws.iter_rows(values_only=True))
wb.close()
hdr = [("" if c is None else str(c).strip()) for c in rows[0]]
i_prod = next(j for j, h in enumerate(hdr) if h.endswith("/Product"))
i_pr = next(j for j, h in enumerate(hdr) if h.endswith("Fixed Price"))
dinein = {}
for r in rows[1:]:
    c = list(r) + [None] * 6
    nm, pr = c[i_prod], c[i_pr]
    if nm and pr:
        try:
            dinein[str(nm).strip().upper()] = float(pr)
        except (TypeError, ValueError):
            pass

# ---------- produk POS sistem ----------
cr.execute("""
    SELECT pol.product_id, SUM(pol.qty), SUM(pol.price_subtotal)
      FROM pos_order_line pol JOIN pos_order po ON po.id=pol.order_id
     WHERE po.state IN ('paid','done','invoiced')
       AND po.date_order >= '2026-06-01' AND po.date_order < '2026-09-01'
     GROUP BY 1""")
sales = {int(p): (float(q or 0), float(r or 0)) for p, q, r in cr.fetchall() if p}

sysprod = []
for p in Prod.search([("sale_ok", "=", True), ("available_in_pos", "=", True)]):
    tmpl = p.product_tmpl_id
    nm = (tmpl.display_name or "").strip()
    qty, rev = sales.get(p.id, (0.0, 0.0))
    sysprod.append({"pid": p.id, "nm": nm, "up": nm.upper(), "price": float(tmpl.list_price or 0),
                    "qty": qty, "rev": rev})
by_up = {s["up"]: s for s in sysprod}


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


by_norm = {}
for s in sysprod:
    by_norm.setdefault(norm(s["up"]), s)

# alias manual: nama dine in -> nama produk sistem
ALIAS = {
    "KRISPI DADA/PAHA ATAS": "AYAM CRISPY DADA/PAHA ATAS",
    "KRISPI PAHA BAWAH": "AYAM CRISPY PAHA BAWAH",
    "KRISPI SAYAP": "AYAM CRISPY SAYAP",
    "AYAM KRISPI PAHA ATAS/DADA": "AYAM CRISPY DADA/PAHA ATAS",
    "AYAM KRISPI PAHA BAWAH": "AYAM CRISPY PAHA BAWAH",
    "AYAM KRISPI SAYAP": "AYAM CRISPY SAYAP",
    "GEPREK SAMBAL IJO": "GEPREK SAMBAL IJO PADANG",
    "GEPREK SAMBAL KOREK": "GEPREK SAMBAL KOREK SURABAYA",
    "GEPREK SAMBAL RICA": "GEPREK SAMBAL RICA MANADO",
    "GEPREK BARBEQUE": "GEPREK SMOKEY BBQ",
    "GEPREK KEJU LUMER": "GEPREK SAOS KEJU LUMER",
    "GEPREK KEJU MOZZA": "GEPREK MOZAA",
    "GEPREK KEJU TABUR": "GEPREK KEJU",
    "PAKET SEGEPOK": "SEGEPOK BERLIMA",
    "MIE GORENG": "INDOMIE",
    "ES LEMON TEA": "LEMON TEA",
    "ES COKELAT": "ICE CHOCOLATE",
    "ES COLA": "ICE COLA",
    "KULIT": "KULIT CRISPY",
    "TELUR DADAR/CEPLOK": "TELUR DADAR/CEPLOK",
    "ES TEH": "ES TEH",
    "NASI": "NASI",
    "AYAM SEGEPOK SINGLE": "AYAM SEGEPOK SINGLE",
}

say("=" * 124)
say("USULAN PEMETAAN HARGA DINE IN -> PRODUK POS SISTEM")
say("=" * 124)
say("%-40s %9s %-40s %9s %7s %8s  %s" % (
    "nama di daftar Dine In", "Dine In", "produk sistem", "harga kini", "rasio", "qty 3bln", "cara"))
say("-" * 124)
mapped, unmapped = [], []
for nm, pr in sorted(dinein.items()):
    hit, cara = None, ""
    if nm in ALIAS and ALIAS[nm] in by_up:
        hit, cara = by_up[ALIAS[nm]], "alias"
    elif nm in by_up:
        hit, cara = by_up[nm], "persis"
    elif norm(nm) in by_norm:
        hit, cara = by_norm[norm(nm)], "normal"
    else:
        cand = difflib.get_close_matches(nm, [s["up"] for s in sysprod], n=1, cutoff=0.72)
        if cand:
            hit, cara = by_up[cand[0]], "mirip"
    if hit:
        ratio = pr / hit["price"] if hit["price"] else 0
        mapped.append((nm, pr, hit, ratio, cara))
        say("%-40s %9s %-40s %9s %6.2fx %8.0f  %s" % (
            nm[:40], money(pr), hit["nm"][:40], money(hit["price"]), ratio, hit["qty"], cara))
    else:
        unmapped.append((nm, pr))
        say("%-40s %9s %-40s %9s %7s %8s  %s" % (nm[:40], money(pr), "—", "—", "—", "—", "PERLU KEPUTUSAN"))

say("-" * 124)
say("terpetakan: %d item | perlu keputusan: %d item" % (len(mapped), len(unmapped)))
if mapped:
    rs = sorted(m[3] for m in mapped)
    say("rasio Dine In / harga kini: min %.2fx | median %.2fx | maks %.2fx" % (
        rs[0], rs[len(rs) // 2], rs[-1]))
    say("")
    say("Pengaruh ke omzet bila item ini naik ke harga Dine In:")
    for nm, pr, hit, ratio, cara in sorted(mapped, key=lambda x: -x[2]["rev"]):
        if hit["rev"] > 0:
            say("   %-44s omzet %12s -> %12s  (+%s)" % (
                hit["nm"][:44], money(hit["rev"]), money(hit["rev"] * ratio),
                money(hit["rev"] * (ratio - 1))))
if unmapped:
    say("")
    say("BELUM TERPETAKAN (perlu keputusan):")
    for nm, pr in unmapped:
        say("   %-46s %s" % (nm[:46], money(pr)))
say("=" * 124)
env.cr.rollback()
