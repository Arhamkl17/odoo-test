# -*- coding: utf-8 -*-
"""
juni_juli_60_client_recipe_groups.py — uji duplikasi resep DI FILE KLIEN (read-only, tanpa Odoo).

Membandingkan tanda tangan resep (komponen + qty) antar menu pada
`import_data/bom_parsed_v2.json` untuk kelompok yang di sistem identik.
"""
import json
from collections import defaultdict

SRC = "import_data/bom_parsed_v2.json"
data = json.load(open(SRC, encoding="utf-8"))
by = {}
for x in data:
    nm = x["produk"].strip().upper()
    sig = tuple(sorted((l["komponen"].strip().upper(), round(float(l["qty"]), 3)) for l in x["lines"]))
    by.setdefault(nm, []).append((sig, len(x["lines"]), x.get("source")))

print("=" * 112)
print("A. NAMA YANG MUNCUL >1x DI FILE KLIEN")
print("=" * 112)
for nm, v in by.items():
    if len(v) > 1:
        sigs = set(s for s, _, _ in v)
        print("  %-52s %d kemunculan, resep %s" % (nm, len(v), "SAMA" if len(sigs) == 1 else "BERBEDA"))
        for sig, n, src in v:
            print("      %2d komponen [%s]" % (n, src))

GROUPS = [
    ("PAKET AYAM CRISPY (3 varian potongan)",
     ["PAKET AYAM CRISPY DADA/PAHA ATAS", "PAKET AYAM CRISPY PAHA BAWAH", "PAKET AYAM CRISPY SAYAP"]),
    ("GEPREK ORIGINAL (3 varian potongan)",
     ["GEPREK ORIGINAL DADA/PAHA ATAS", "GEPREK ORIGINAL SAYAP", "GEPREK ORIGINAL PAHA BAWAH"]),
    ("AYAM CRISPY (3 varian potongan)",
     ["AYAM CRISPY DADA/PAHA ATAS", "AYAM CRISPY PAHA BAWAH", "AYAM CRISPY SAYAP"]),
    ("BIG HEMAT (4 paket)",
     ["BIG HEMAT 1", "BIG HEMAT 2", "BIG HEMAT 3", "BIG HEMAT 4"]),
    ("PAKET INDOMIE CRISPY (2 varian)",
     ["PAKET INDOMIE CRISPY DADA/PAHA ATAS", "PAKET INDOMIE CRISPY PAHA BAWAH"]),
    ("MEVVAH (berdua vs satu porsi)",
     ["PAKET MEVVAH BERDUA", "PKG GEPREK MEVVAH"]),
    ("SAMBAAL (korek/ijo/rica/ori)",
     ["PKG SAMBAL KOREK SURABAYA", "PKG SAMBAL IJO PADANG", "PKG SAMBAL RICA MANADO", "PKG SAMBAL ORI SAYAP"]),
]

print("")
print("=" * 112)
print("B. APAKAH RESEP VARIAN IDENTIK DI FILE KLIEN?")
print("=" * 112)
for label, names in GROUPS:
    sigs = {}
    for nm in names:
        if nm not in by:
            sigs[nm] = None
            continue
        sigs[nm] = by[nm][0][0]
    uniq = set(s for s in sigs.values() if s)
    print("")
    print("-- %s -> %d resep unik dari %d menu" % (label, len(uniq), len([s for s in sigs.values() if s])))
    for nm in names:
        s = sigs[nm]
        print("   %-46s %s" % (nm, ("%d komponen" % len(s)) if s else "TIDAK ADA DI FILE KLIEN"))
    if len(uniq) > 1:
        items = [sorted(s) for s in uniq]
        base = items[0]
        print("   PERBEDAAN (terhadap resep pertama):")
        for s in items[1:]:
            only_a = [x for x in base if x not in s]
            only_b = [x for x in s if x not in base]
            print("      + hanya di A: %s" % (only_a or "-"))
            print("      + hanya di B: %s" % (only_b or "-"))
    else:
        print("   >> IDENTIK di file klien juga")

print("")
print("=" * 112)
print("C. CONTOH RINCI: PKG SAMBAL KOREK SURABAYA (2 kemunculan) vs BIG HEMAT 4 vs PKG GEPREK MEVVAH")
print("=" * 112)
for nm in ("PKG SAMBAL KOREK SURABAYA", "BIG HEMAT 4", "PKG GEPREK MEVVAH"):
    for sig, n, src in by.get(nm, []):
        print("")
        print("-- %s  (%d komponen, sumber: %s)" % (nm, n, src))
        for comp, q in sig:
            print("      %-40s %s" % (comp, q))
