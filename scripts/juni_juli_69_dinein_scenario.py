# -*- coding: utf-8 -*-
"""
juni_juli_69_dinein_scenario.py — SKENARIO HARGA DINE IN (READ-ONLY, odoo shell).

Klien punya DUA daftar harga:
  - 'dasar' (06_price_update.csv)  -> harga yang dipakai POS kita Juni-Agustus
  - 'Dine In' (TEMPLATE IMPORT HARGA DINE IN.xlsx, pricelist 149 & 154) -> 17-78% lebih tinggi

Skrip ini menghitung rasio harga Dine In / dasar per menu, lalu mensimulasikan
labanya bila penjualan memakai harga Dine In (HPP & beban operasional TIDAK diubah).

  su odoo ... < scripts/juni_juli_69_dinein_scenario.py
"""
import os

import openpyxl

DINEIN = "product_photos/data sheet master/TEMPLATE IMPORT HARGA DINE IN.xlsx"
cr = env.cr
Prod = env["product.product"]
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

# --- baca harga dine in
wb = openpyxl.load_workbook(DINEIN, data_only=True, read_only=True)
ws = wb.worksheets[0]
rows = list(ws.iter_rows(values_only=True))
wb.close()
hdr = [("" if c is None else str(c).strip()) for c in rows[0]]
i_prod = next(j for j, h in enumerate(hdr) if h.endswith("/Product"))
i_pr = next(j for j, h in enumerate(hdr) if h.endswith("Fixed Price"))
dinein = {}
for r in rows[1:]:
    cells = list(r) + [None] * 6
    nm, pr = cells[i_prod], cells[i_pr]
    if nm and pr:
        try:
            dinein[str(nm).strip().upper()] = float(pr)
        except (TypeError, ValueError):
            pass

say("=" * 118)
say("HARGA DINE IN KLIEN — %d item" % len(dinein))
say("=" * 118)

# --- penjualan POS per produk (harga dasar)
cr.execute("""
    SELECT pol.product_id, SUM(pol.qty), SUM(pol.price_subtotal)
      FROM pos_order_line pol JOIN pos_order po ON po.id=pol.order_id
     WHERE po.state IN ('paid','done','invoiced')
       AND po.date_order >= '2026-06-01' AND po.date_order < '2026-09-01'
     GROUP BY 1""")
sales = {int(p): (float(q or 0), float(r or 0)) for p, q, r in cr.fetchall() if p}

# --- peta nama dine in -> nama produk sistem (manual, transparan)
MAP = {
    "KRISPI DADA/PAHA ATAS": "AYAM CRISPY DADA/PAHA ATAS",
    "KRISPI PAHA BAWAH": "AYAM CRISPY PAHA BAWAH",
    "KRISPI SAYAP": "AYAM CRISPY SAYAP",
    "AYAM KRISPI PAHA ATAS/DADA": "AYAM CRISPY DADA/PAHA ATAS",
    "AYAM KRISPI PAHA BAWAH": "AYAM CRISPY PAHA BAWAH",
    "AYAM KRISPI SAYAP": "AYAM CRISPY SAYAP",
    "GEPREK SAMBAL IJO": "GEPREK SAMBAL IJO PADANG",
    "GEPREK SAMBAL KOREK": "GEPREK SAMBAL KOREK SURABAYA",
    "GEPREK SAMBAL RICA": "GEPREK SAMBAL RICA MANADO",
    "GEPREK KEU LUMER": "GEPREK SAOS KEJU LUMER",
    "GEPREK KEJU LUMER": "GEPREK SAOS KEJU LUMER",
    "GEPREK KEJU MOZZA": "GEPREK MOZAA",
    "GEPREK KEJU TABUR": "GEPREK KEJU",
    "GEPREK BARBEQUE": "GEPREK SMOKEY BBQ",
    "AYAM SEGEPOK SINGLE": "AYAM SEGEPOK SINGLE",
    "PAKET SEGEPOK": "SEGEPOK BERLIMA",
    "NASI": "NASI",
    "MIE GORENG": "INDOMIE",
    "ES TEH": "ES TEH",
    "ES COKELAT": "ICE CHOCOLATE",
    "ES COLA": "ICE COLA",
    "ES LEMON TEA": "LEMON TEA",
    "KULIT": "KULIT CRISPY",
    "TELUR DADAR/CEPLOK": "TELUR DADAR/CEPLOK",
}

say("")
say("%-46s %10s %10s %8s %14s" % ("menu", "dasar POS", "dine in", "rasio", "omzet 3bln"))
say("-" * 118)
ratios = []
tot_rev_affected = 0.0
for k, v in sorted(dinein.items()):
    sysname = MAP.get(k)
    if not sysname:
        continue
    p = Prod.search([("display_name", "=", sysname)], limit=1)
    if not p:
        continue
    qty, rev = sales.get(p.id, (0.0, 0.0))
    base = (rev / qty) if qty else (p.product_tmpl_id.list_price or 0)
    if not base:
        continue
    ratio = v / base
    ratios.append((sysname, base, v, ratio, rev))
    tot_rev_affected += rev
    say("%-46s %10s %10s %7.2fx %14s" % (sysname[:46], money(base), money(v), ratio, money(rev)))

if ratios:
    rs = sorted(r[3] for r in ratios)
    med = rs[len(rs) // 2]
    say("-" * 118)
    say("menu terpetakan: %d | rasio min %.2fx  median %.2fx  maks %.2fx" % (
        len(ratios), rs[0], med, rs[-1]))
    say("omzet 3 bulan yang terdampak langsung: %s" % money(tot_rev_affected))
    say("")
    say("=" * 118)
    say("SKENARIO: seluruh omzet memakai harga Dine In (HPP & beban TIDAK diubah)")
    say("=" * 118)
    cr.execute("""SELECT to_char(am.date,'YYYY-MM'), COALESCE(SUM(aml.balance),0)
                    FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND aa.account_type IN ('income','income_other')
                     AND am.date >= '2026-06-01' AND am.date < '2026-09-01'
                   GROUP BY 1 ORDER BY 1""")
    rev_m = {str(m): -float(v) for m, v in cr.fetchall()}
    cr.execute("""SELECT to_char(am.date,'YYYY-MM'), COALESCE(SUM(aml.balance),0)
                    FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND aa.account_type IN ('expense','expense_depreciation')
                     AND am.date >= '2026-06-01' AND am.date < '2026-09-01'
                   GROUP BY 1 ORDER BY 1""")
    opex_m = {str(m): float(v) for m, v in cr.fetchall()}
    cr.execute("""SELECT to_char(am.date,'YYYY-MM'), COALESCE(SUM(aml.balance),0)
                    FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND aa.account_type='expense_direct_cost'
                     AND am.date >= '2026-06-01' AND am.date < '2026-09-01'
                   GROUP BY 1 ORDER BY 1""")
    hpp_m = {str(m): float(v) for m, v in cr.fetchall()}
    say("%-8s %16s %16s %16s %16s" % ("bulan", "Pendapatan", "+dine in(x%.2f)" % med, "HPP", "Laba skrg -> dine in"))
    for m in sorted(hpp_m):
        r = rev_m.get(m, 0.0)
        hpp = hpp_m.get(m, 0.0)
        e = opex_m.get(m, 0.0)
        rd = r * med
        say("%-8s %16s %16s %16s %16s -> %s" % (
            m, money(r), money(rd), money(hpp),
            money(r - hpp - e), money(rd - hpp - e)))
    say("")
    say("CATATAN: rasio median %.2fx dipakai sebagai pendekatan seragam. Angka ini BUKAN" % med)
    say("proyeksi final — daftar Dine In hanya 52 item dan belum dipetakan seluruhnya.")
say("=" * 118)
env.cr.rollback()
