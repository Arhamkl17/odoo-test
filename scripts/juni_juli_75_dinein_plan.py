# -*- coding: utf-8 -*-
"""
juni_juli_75_dinein_plan.py — RENCANA harga Dine In utk SELURUH menu (READ-ONLY, odoo shell).

Temuan: dekomposisi lewat resep TIDAK bisa dipakai (resep datar; varian potongan
beresep identik sehingga tidak bisa dibedakan). Karena itu aturan disusun dari
NAMA produk + daftar harga Dine In klien:

  A. harga klien langsung (alias terkurasi)                      -> sumber "klien"
  B. harga dasar + jumlah uplift komponen yang dikenali di NAMA  -> sumber "komponen"
  C. harga dasar x 1,25 (lantai minimum)                         -> sumber "lantai"

Keputusan user yang sudah dikunci:
  - AYAM CRISPY DADA/PAHA ATAS=14.000, PAHA BAWAH=11.000, SAYAP=12.000 (set "AYAM KRISPI")
  - item 5.000 (BARBEQUE/IJO/KOREK/RICA/KEJU LUMER) & 2.000 (NUGGET/TAHU/TEMPE/TELUR KRISPI)
    dipakai apa adanya sebagai harga produk TAMBAHAN

  su odoo ... < scripts/juni_juli_75_dinein_plan.py
"""
import openpyxl

PATH = "product_photos/data sheet master/TEMPLATE IMPORT HARGA DINE IN.xlsx"
cr = env.cr
Prod = env["product.product"]
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

# ---------------------------------------------------------------- daftar Dine In klien
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
    if c[i_prod] and c[i_pr]:
        try:
            dinein[str(c[i_prod]).strip().upper()] = float(c[i_pr])
        except (TypeError, ValueError):
            pass

# ---------------------------------------------------------------- produk POS + penjualan
cr.execute("""
    SELECT pol.product_id, SUM(pol.qty), SUM(pol.price_subtotal)
      FROM pos_order_line pol JOIN pos_order po ON po.id=pol.order_id
     WHERE po.state IN ('paid','done','invoiced')
       AND po.date_order >= '2026-06-01' AND po.date_order < '2026-09-01'
     GROUP BY 1""")
sales = {int(p): (float(q or 0), float(r or 0)) for p, q, r in cr.fetchall() if p}
prods = []
for p in Prod.search([("sale_ok", "=", True), ("available_in_pos", "=", True)]):
    t = p.product_tmpl_id
    nm = (t.display_name or "").strip()
    q, rev = sales.get(p.id, (0.0, 0.0))
    prods.append({"pid": p.id, "nm": nm, "up": nm.upper(),
                  "price": float(t.list_price or 0), "qty": q, "rev": rev})
by_up = {s["up"]: s for s in prods}

# ---------------------------------------------------------------- A. peta langsung (terkurasi)
DIRECT = {
    "PAKET SEGEPOK": "SEGEPOK BERLIMA",
    "AYAM SEGEPOK SINGLE": "AYAM SEGEPOK SINGLE",
    "MIE MEVVAH": "INDOMIE MEVVAH",
    "GEPREK KEJU MOZZA": "GEPREK MOZAA",
    "MIE AYAM KRISPI (SAYAP)": "AYAM CRISPY SAYAP",
    "MIE AYAM KRISPI (PAHA BAWAH)": "AYAM CRISPY PAHA BAWAH",
    "MIE AYAM KRISPI (PAHA ATAS/DADA)": "AYAM CRISPY DADA/PAHA ATAS",
    "GEPREK KEJU TABUR": "GEPREK KEJU",
    "GEPREK ORIGINAL": "GEPREK ORIGINAL DADA/PAHA ATAS",
    "GEPREK ORIGINAL PAHA ATAS/DADA": "GEPREK ORIGINAL DADA/PAHA ATAS",
    "GEPREK ORIGINAL PAHA BAWAH": "GEPREK ORIGINAL PAHA BAWAH",
    "GEPREK ORIGINAL SAYAP": "GEPREK ORIGINAL SAYAP",
    "GEPREK BARBEQUE": "GEPREK SMOKEY BBQ",
    "GEPREK KEJU LUMER": "GEPREK SAOS KEJU LUMER",
    "GEPREK SAMBAL IJO": "GEPREK SAMBAL IJO PADANG",
    "GEPREK SAMBAL KOREK": "GEPREK SAMBAL KOREK SURABAYA",
    "GEPREK SAMBAL RICA": "GEPREK SAMBAL RICA MANADO",
    "MIE GEPREK SAMBAL LOKAL": "PKG INDOMIE GEPREK SAMBAL LOKAL",
    "ES COKELAT": "ICE CHOCOLATE",
    "ES COLA": "ICE COLA",
    "ES LEMON TEA": "LEMON TEA",
    "ES TEH": "ES TEH",
    "ES JERUK": "ES JERUK",
    "AIR MINERAL": "AIR GELAS",
    "NASI": "NASI",
    "KULIT": "KULIT CRISPY",
    "TELUR DADAR/CEPLOK": "TELUR DADAR/CEPLOK",
    "GEPREK ANDALAN TANPA KECAP": "GEPREK ANDALAN",
    "GEPREK ANDALAN DENGAN KECAP": "GEPREK ANDALAN",
    # 9 produk add-on yang dibuat 13 Sep 2026 (§23.7 butir 1) — nama produk = nama di daftar Dine In
    "BARBEQUE": "BARBEQUE", "IJO": "IJO", "KOREK": "KOREK", "RICA": "RICA",
    "KEJU LUMER": "KEJU LUMER", "NUGGET": "NUGGET", "TAHU/BIJI": "TAHU/BIJI",
    "TEMPE/BIJI": "TEMPE/BIJI", "TELUR KRISPI": "TELUR KRISPI",
}
# keputusan user: set "AYAM KRISPI" utk 3 produk AYAM CRISPY
USER_FIX = {
    "AYAM CRISPY DADA/PAHA ATAS": 14_000.0,
    "AYAM CRISPY PAHA BAWAH": 11_000.0,
    "AYAM CRISPY SAYAP": 12_000.0,
}
# add-on diperlakukan sebagai harga produk TAMBAHAN (keputusan user)
ADDON = {"BARBEQUE": 5_000, "IJO": 5_000, "KOREK": 5_000, "RICA": 5_000, "KEJU LUMER": 5_000,
         "NUGGET": 2_000, "TAHU/BIJI": 2_000, "TEMPE/BIJI": 2_000, "TELUR KRISPI": 2_000}

direct_price = {}
for dn, sysnm in DIRECT.items():
    if dn in dinein and sysnm in by_up:
        direct_price[sysnm] = dinein[dn]
for k, v in USER_FIX.items():
    direct_price[k] = v

# ---------------------------------------------------------------- uplift komponen (dari anchor)
UPLIFT = {
    "NASI": 1_000,
    "MINUM": 2_000,          # ES TEH +2.000
    "INDOMIE": 1_000,
    "AYAM DADA": 2_500,      # set AYAM KRISPI
    "AYAM BAWAH": 2_000,
    "AYAM SAYAP": 3_000,
    "GEPREK DADA": 3_000,    # set GEPREK ORIGINAL
    "GEPREK BAWAH": 2_000,
    "GEPREK SAYAP": 3_000,
    "SAMBAL": 2_500,
    "MEVVAH": 11_000,
    "KULIT": 2_000,
    "TELUR": 0,
}


# produk non-menu: harga TIDAK diubah (bukan makanan)
NON_MENU = ("GIFT CARD", "TOP-UP EWALLET", "TOP UP EWALLET", "TIPS")

# penanda ada hidangan utama walau potongan tidak disebut
MAIN_DISH = ("GEPREK", "AYAM", "CRISPY", "KRISPI", "ANDALAN", "SAMBAL", "MOZZA",
             "BBQ", "BARBEQUE", "KEJU", "RICA", "IJO", "KOREK", "MEVVAH",
             "INDOMIE", "MIE", "KULIT", "SEGEPOK")
AYAM_UMUM = 2_500          # uplift median set AYAM KRISPI


def komponen(nm):
    u = nm.upper()
    out = []
    if "NASI" in u:
        out.append(("NASI", UPLIFT["NASI"]))
    if "MINUM" in u or "ES TEH" in u:
        out.append(("MINUM", UPLIFT["MINUM"]))
    if "INDOMIE" in u or "MIE" in u:
        out.append(("INDOMIE", UPLIFT["INDOMIE"]))
    if "MEVVAH" in u:
        out.append(("MEVVAH", UPLIFT["MEVVAH"]))
    if "KULIT" in u:
        out.append(("KULIT", UPLIFT["KULIT"]))
    ayam = None
    if "SAYAP" in u:
        ayam = "AYAM SAYAP"
    elif "PAHA BAWAH" in u:
        ayam = "AYAM BAWAH"
    elif "DADA" in u or "PAHA ATAS" in u:
        ayam = "AYAM DADA"
    elif any(k in u for k in MAIN_DISH):
        ayam = "AYAM (potongan tidak disebut)"
        UPLIFT.setdefault(ayam, AYAM_UMUM)
    if ayam:
        out.append((ayam, UPLIFT[ayam]))
    return out


# ---------------------------------------------------------------- hitung harga
plan = []
for s in sorted(prods, key=lambda x: -x["rev"]):
    nm, base = s["nm"], s["price"]
    if nm.upper().strip() in NON_MENU or nm.upper().strip().endswith("] TIPS"):
        plan.append({"nm": nm, "base": base, "dn": base, "src": "non-menu", "komp": [],
                     "qty": s["qty"], "rev": s["rev"], "pid": s["pid"]})
        continue
    if nm in direct_price:
        dn, src, komp = direct_price[nm], "klien", []
    else:
        komp = komponen(nm)
        raw = base + sum(k[1] for k in komp) if komp else base * 1.25
        src = "komponen" if komp else "lantai"
        # PAKET selalu pakai lantai 1,25× — supaya paket tidak pernah lebih murah
        # per porsi daripada menu tunggal (rasio paket klien: 1,26× s/d 1,34×)
        if nm.upper().startswith(("PAKET ", "PKG ", "PKC ", "BIG HEMAT", "YUKSSS RAMA", "SEGEPOK")):
            import math
            if raw < base * 1.25:
                raw = base * 1.25
                src = "komponen+lantai"
                komp = list(komp) + [("lantai paket 1,25x", 0)]
        dn = round(raw / 500.0) * 500          # harga akhir dibulatkan ke 500 -> angka rapi
    plan.append({"nm": nm, "base": base, "dn": dn, "src": src, "komp": komp,
                 "qty": s["qty"], "rev": s["rev"], "pid": s["pid"]})

say("=" * 120)
say("RENCANA PRICELIST DINE IN — %d produk POS" % len(plan))
say("=" * 120)
say("%-48s %9s %9s %7s %6s %-9s %s" % ("menu", "dasar", "Dine In", "naik", "ratio", "sumber", "komponen"))
say("-" * 120)
for r in plan:
    if r["base"] <= 0:
        continue
    say("%-48s %9s %9s %6.0f%% %5.2fx %-9s %s" % (
        r["nm"][:48], money(r["base"]), money(r["dn"]),
        100.0 * (r["dn"] - r["base"]) / r["base"], r["dn"] / r["base"], r["src"],
        " + ".join(k[0] for k in r["komp"])))

# ---------------------------------------------------------------- dampak omzet
rev_base = sum(r["rev"] for r in plan)
rev_dn = sum(r["rev"] * (r["dn"] / r["base"]) for r in plan if r["base"] > 0)
say("")
say("=" * 120)
say("DAMPAK OMZET 3 BULAN")
say("=" * 120)
say("omzet sekarang (semua harga dasar)        : %s" % money(rev_base))
say("omzet bila 100%% Dine In                   : %s  (+%s)" % (money(rev_dn), money(rev_dn - rev_base)))
mix = 0.6
rev_mix = mix * rev_dn + (1 - mix) * rev_base
say("omzet bila campuran 60%% Dine In / 40%% dasar : %s  (+%s, +%.1f%%)" % (
    money(rev_mix), money(rev_mix - rev_base), 100.0 * (rev_mix - rev_base) / rev_base))

# ---------------------------------------------------------------- tulis CSV untuk review
import csv
with open("import_data/pricelist_dinein_plan.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["product_id", "menu", "harga_dasar", "harga_dine_in", "rasio", "sumber", "komponen", "omzet_3bln"])
    for r in plan:
        w.writerow([r["pid"], r["nm"], "%.2f" % r["base"], "%.2f" % r["dn"],
                    "%.3f" % (r["dn"] / r["base"]) if r["base"] else "", r["src"],
                    " + ".join(k[0] for k in r["komp"]), "%.0f" % r["rev"]])
say("")
say("CSV ditulis: import_data/pricelist_dinein_plan.csv")

cr.execute("""
    SELECT to_char(po.date_order,'YYYY-MM'), SUM(pol.price_subtotal)
      FROM pos_order_line pol JOIN pos_order po ON po.id=pol.order_id
     WHERE po.state IN ('paid','done','invoiced')
       AND po.date_order >= '2026-06-01' AND po.date_order < '2026-09-01'
     GROUP BY 1 ORDER BY 1""")
say("")
say("%-10s %14s %14s   %s" % ("bulan", "omzet kini", "omzet 60/40", "selisih"))
for m, rv in cr.fetchall():
    rv = float(rv or 0)
    say("%-10s %14s %14s   +%s" % (m, money(rv), money(rv * rev_mix / rev_base), money(rv * (rev_mix / rev_base) - rv)))

say("")
say("=" * 120)
say("ADD-ON (harga produk tambahan, keputusan user)")
say("=" * 120)
for k, v in sorted(ADDON.items()):
    ada = "ADA di sistem" if k in by_up else "belum ada -> perlu dibuat"
    say("   %-16s %8s   %s" % (k, money(v), ada))

env.cr.rollback()
