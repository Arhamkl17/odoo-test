# -*- coding: utf-8 -*-
"""
juni_juli_104_dua_sheet_dinein.py — bandingkan DUA daftar harga Dine In dari klien.

`TEMPLATE IMPORT HARGA DINE IN.xlsx` ternyata memuat DUA sheet, keduanya bernama
"Harga Menu Baru Dine In", tapi berasal dari pricelist berbeda di Odoo klien:
  • `__export__.product_pricelist_149_181fe140`
  • `__export__.product_pricelist_154_7540f593`
"""
import openpyxl

say = lambda m="": print(m)
F = "product_photos/data sheet master/TEMPLATE IMPORT HARGA DINE IN.xlsx"

wb = openpyxl.load_workbook(F, data_only=True)

data = {}
for ws in wb.worksheets:
    rows = [r for r in ws.iter_rows(values_only=True) if any(c not in (None, "") for c in r)]
    header = [str(h or "").strip() for h in rows[0]]
    idx = {h: i for i, h in enumerate(header)}
    nama_pl = set()
    items = {}
    for r in rows[1:]:
        pl = str(r[idx["Pricelist Name"]] or "").strip()
        nama_pl.add(pl)
        prod = str(r[idx["Pricelist Items/Product"]] or "").strip()
        harga = r[idx["Pricelist Items/Fixed Price"]]
        if prod:
            items[prod] = float(harga or 0)
    data[ws.title] = {"pl": nama_pl, "items": items, "n": len(items)}

say("=" * 104)
say("DUA DAFTAR HARGA DINE IN DI BERKAS KLIEN")
say("=" * 104)
say("")
for sheet, d in data.items():
    say("   sheet %-14s pricelist=%s   %d item" % (sheet, "/".join(sorted(d["pl"])), d["n"]))

sheets = list(data.keys())
a, b = sheets[0], sheets[1]
ia, ib = data[a]["items"], data[b]["items"]

say("")
say("   item hanya di %s : %d" % (a, len(set(ia) - set(ib))))
say("   item hanya di %s : %d" % (b, len(set(ib) - set(ia))))
beda = [(k, ia[k], ib[k]) for k in sorted(set(ia) & set(ib)) if abs(ia[k] - ib[k]) > 0.01]
say("   item sama tapi harga BEDA: %d" % len(beda))
say("")
if beda:
    say("   %-44s %12s %12s" % ("menu", a, b))
    say("   " + "-" * 72)
    for k, va, vb in beda:
        say("   %-44s %12s %12s" % (k[:44], "{:,.0f}".format(va), "{:,.0f}".format(vb)))

say("")
say("   CONTOH 10 ITEM:")
say("   %-44s %12s %12s" % ("menu", a, b))
say("   " + "-" * 72)
for k in sorted(set(ia) | set(ib))[:10]:
    say("   %-44s %12s %12s" % (
        k[:44],
        "{:,.0f}".format(ia[k]) if k in ia else "—",
        "{:,.0f}".format(ib[k]) if k in ib else "—"))

say("")
say("=" * 104)
say("KESIMPULAN")
say("=" * 104)
say("")
say("   Dua sheet itu adalah SATU daftar harga yang sama ('Harga Menu Baru Dine In'),")
say("   hanya tersimpan dua kali di Odoo klien dengan id berbeda (149 = lama, 154 = baru).")
say("   Sistem kita memakai yang BARU (154).")
say("")
say("=" * 104)
