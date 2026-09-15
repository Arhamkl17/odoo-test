# -*- coding: utf-8 -*-
"""juni_juli_70_dinein_full.py — isi lengkap & perbandingan 2 sheet harga Dine In."""
import os

import openpyxl

PATH = "product_photos/data sheet master/TEMPLATE IMPORT HARGA DINE IN.xlsx"
wb = openpyxl.load_workbook(PATH, data_only=True, read_only=True)

sheets = {}
for ws in wb.worksheets:
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        continue
    hdr = [("" if c is None else str(c).strip()) for c in rows[0]]
    i_ext = next((j for j, h in enumerate(hdr) if h.lower().startswith("external")), None)
    i_pl = next((j for j, h in enumerate(hdr) if "Pricelist Name" in h), None)
    i_prod = next((j for j, h in enumerate(hdr) if h.endswith("/Product")), None)
    i_pr = next((j for j, h in enumerate(hdr) if h.endswith("Fixed Price")), None)
    items = {}
    ext_first = None
    pl_name = None
    for r in rows[1:]:
        cells = list(r) + [None] * 6
        nm = cells[i_prod] if i_prod is not None else None
        pr = cells[i_pr] if i_pr is not None else None
        if nm and pr:
            try:
                items[str(nm).strip().upper()] = float(pr)
            except (TypeError, ValueError):
                pass
        if ext_first is None and i_ext is not None and cells[i_ext]:
            ext_first = str(cells[i_ext]).strip()
        if pl_name is None and i_pl is not None and cells[i_pl]:
            pl_name = str(cells[i_pl]).strip()
    sheets[ws.title] = {"items": items, "ext": ext_first, "pl": pl_name, "nrow": len(rows)}
wb.close()

print("=" * 112)
print("BERKAS HARGA DINE IN — %d sheet" % len(sheets))
print("=" * 112)
for nm, d in sheets.items():
    print("")
    print("--- sheet '%s' : %d baris | pricelist='%s' | ext=%s | %d item" % (
        nm, d["nrow"], d["pl"], (d["ext"] or "-")[-34:], len(d["items"])))
    for k, v in sorted(d["items"].items()):
        print("      %-46s %10s" % (k[:46], "{:,.0f}".format(v)))

if len(sheets) >= 2:
    ks = list(sheets)
    a, b = sheets[ks[0]]["items"], sheets[ks[1]]["items"]
    print("")
    print("=" * 112)
    print("PERBANDINGAN '%s' vs '%s'" % (ks[0], ks[1]))
    print("=" * 112)
    same = diff = onlyA = onlyB = 0
    for k in sorted(set(a) | set(b)):
        va, vb = a.get(k), b.get(k)
        if va is not None and vb is not None:
            if abs(va - vb) < 0.5:
                same += 1
            else:
                diff += 1
                print("   BEDA  %-44s A=%10s  B=%10s" % (k[:44], "{:,.0f}".format(va), "{:,.0f}".format(vb)))
        elif va is not None:
            onlyA += 1
            print("   hanya A: %-44s %10s" % (k[:44], "{:,.0f}".format(va)))
        else:
            onlyB += 1
            print("   hanya B: %-44s %10s" % (k[:44], "{:,.0f}".format(vb)))
    print("")
    print("   sama: %d | beda harga: %d | hanya sheet A: %d | hanya sheet B: %d" % (same, diff, onlyA, onlyB))
