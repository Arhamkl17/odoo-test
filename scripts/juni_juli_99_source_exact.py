# -*- coding: utf-8 -*-
"""
juni_juli_99_source_exact.py — pencarian nama dengan cocok PERSIS (bukan substring).

Penting: `PKG SAMBAL KOREK SURABAYA` adalah substring dari
`PKG SAMBAL KOREK SURABAYA (GEPREK SAMBAL +NASI)`, jadi pencarian `in` memberi
positif palsu. Skrip ini membandingkan sel/field secara persis.

Pertanyaan yang dijawab: apakah nama "pendek" (kandidat hantu) BENAR-BENAR ada sebagai
entri tersendiri di berkas klien, atau hanya muncul sebagai bagian dari nama panjang?
"""
import csv, glob, json, os

SHORT = [
    "PKG SAMBAL KOREK SURABAYA",
    "PKG SAMBAL IJO PADANG",
    "PKG SAMBAL RICA MANADO",
    "PAKET MEVVAH BERDUA",
    "PAKET KULIT CRISPY",
    "PKG INDOMIE GEPREK SAMBAL LOKAL",
]
LONG = [
    "PKG SAMBAL KOREK SURABAYA (GEPREK SAMBAL +NASI)",
    "PKG SAMBAL IJO PADANG (GEPREK SAMBAL +NASI)",
    "PKG SAMBAL RICA MANADO (GEPREK SAMBAL +NASI)",
    "PKG MEVVAH (AYAM GEPREK+TELUR ORAK ARIK+INDOMIE MEVVAH)",
    "PAKET KULIT CRISPY + NASI + MINUM",
    "PKG MIE (AYAM GEPREK+SAMBAL LOKAL+INDOMIE)",
]
ALL = set(SHORT + LONG)
say = lambda m="": print(m)

say("=" * 116)
say("PENCARIAN COCOK PERSIS")
say("=" * 116)


def cells_csv(path):
    out = []
    with open(path, encoding="utf-8-sig", errors="ignore") as f:
        for row in csv.reader(f):
            for c in row:
                s = (c or "").strip()
                if s in ALL:
                    out.append(s)
    return out


say("")
say("[1] CSV — nilai sel yang cocok PERSIS")
say("")
for path in sorted(glob.glob("import_data/csv/*.csv")):
    hits = cells_csv(path)
    if hits:
        say("   %s" % os.path.basename(path))
        for h in sorted(set(hits)):
            say("        %-62s (%d sel)" % (h, hits.count(h)))

say("")
say("[2] JSON — field bernilai persis salah satu nama")
say("")


def walk_json(o, sink):
    if isinstance(o, dict):
        for v in o.values():
            walk_json(v, sink)
    elif isinstance(o, list):
        for v in o:
            walk_json(v, sink)
    elif isinstance(o, str):
        s = o.strip()
        if s in ALL:
            sink[s] = sink.get(s, 0) + 1


for path in sorted(glob.glob("import_data/*.json")):
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        say("   %-40s GAGAL: %s" % (os.path.basename(path), e))
        continue
    sink = {}
    walk_json(data, sink)
    say("   %s" % os.path.basename(path))
    if sink:
        for k, n in sorted(sink.items()):
            say("        %-62s (%d kali)" % (k, n))
    else:
        say("        —")

say("")
say("[3] XLSX master — nilai sel yang cocok PERSIS")
say("")
try:
    import openpyxl
except ImportError:
    openpyxl = None
    say("   openpyxl tidak tersedia")

MASTER = sorted(glob.glob("product_photos/data sheet master/*.xlsx"))
for path in MASTER:
    if not openpyxl:
        break
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as e:
        say("   %-60s GAGAL: %s" % (os.path.basename(path), e))
        continue
    found = {}
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            for cell in row:
                if isinstance(cell, str) and cell.strip() in ALL:
                    s = cell.strip()
                    found.setdefault(s, {}).setdefault(ws.title, 0)
                    found[s][ws.title] += 1
    say("   %s" % os.path.basename(path))
    if found:
        for nama, sheets in sorted(found.items()):
            say("        %-62s %s" % (nama[:62], ", ".join("%s×%d" % (s, n) for s, n in sorted(sheets.items()))))
    else:
        say("        —")
    wb.close()

say("")
say("=" * 116)
say("KESIMPULAN")
say("=" * 116)
say("")
say("   Nama PENDEK (kandidat 'hantu') hanya sah dihapus bila TIDAK muncul sebagai")
say("   entri tersendiri di daftar produk klien. Kalau muncul di dua tempat pada")
say("   berkas yang sama, berarti duplikat itu memang ada di data klien.")
say("")
