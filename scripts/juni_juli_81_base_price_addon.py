# -*- coding: utf-8 -*-
"""
juni_juli_81_base_price_addon.py — R7 + R8 langkah 1.

A. Kembalikan harga dasar 6 PAKET ke nilai PRA-R3 (keputusan user 13 Sep 2026).
   Sumber: import_data/pre_r3_master_prices.csv (dibaca dari dump backup R3).
   Alasan: R3 menurunkan harga paket ini ke harga keluaran generator, sehingga
   paket 5 porsi jadi lebih murah dari menu 1 porsi (lihat spec §21.7).

B. Buat 9 produk ADD-ON dari daftar harga Dine In klien (keputusan user):
   5.000 -> BARBEQUE, IJO, KOREK, RICA, KEJU LUMER
   2.000 -> NUGGET, TAHU/BIJI, TEMPE/BIJI, TELUR KRISPI
   Produk dilewati bila nama ternormalisasi sudah ada.

  dry-run : su odoo ... < scripts/juni_juli_81_base_price_addon.py
  eksekusi: su odoo ... " RUN=1 odoo shell ..." < scripts/juni_juli_81_base_price_addon.py
"""
import csv
import io
import os
import re

RUN = os.environ.get("RUN") == "1"
PRE = "import_data/pre_r3_master_prices.csv"

Prod = env["product.product"]
TM = env["product.template"]
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

# ------------------------------------------------------------------ A
PAKET = ["SEGEPOK BERLIMA", "PKG LOKAL DUO", "PAKET GEPREK BAKAR",
         "PAKET MEVVAH BERDUA", "PAKET YUKSSS MABAR", "YUKSSS RAMA 1"]

# keputusan user 13 Sep 2026: angka bulat, bukan hasil hitungan (menimpa nilai pra-R3)
OVERRIDE = {"SEGEPOK BERLIMA": 100_000.0}

pre = {}
with io.open(PRE, encoding="utf-8") as f:
    for ln in f:
        p = ln.strip().split("|")
        if len(p) >= 3:
            try:
                pre[int(p[0])] = float(p[2])
            except ValueError:
                pass

say("=" * 112)
say("A. KEMBALIKAN HARGA DASAR 6 PAKET KE NILAI PRA-R3   |   RUN=%s" % RUN)
say("=" * 112)
say("%-6s %-46s %9s %9s %9s" % ("tid", "paket", "kini", "pra-R3", "akan jadi"))
say("-" * 112)
fixes = []
for nm in PAKET:
    t = TM.search([("name", "=", nm), ("sale_ok", "=", True)], limit=1)
    if not t:
        say("%-6s %-46s  TIDAK DITEMUKAN" % ("-", nm))
        continue
    old = float(t.list_price or 0)
    new = OVERRIDE.get(nm, pre.get(t.id))
    if new is None:
        say("%-6s %-46s %9s   (tidak ada di arsip pra-R3)" % (t.id, nm[:46], money(old)))
        continue
    say("%-6s %-46s %9s %9s %9s" % (t.id, nm[:46], money(old), money(new), money(new)))
    if abs(old - new) > 0.005:
        fixes.append((t, nm, old, new))

# ------------------------------------------------------------------ B
ADDON = [("BARBEQUE", 5000), ("IJO", 5000), ("KOREK", 5000), ("RICA", 5000),
         ("KEJU LUMER", 5000), ("NUGGET", 2000), ("TAHU/BIJI", 2000),
         ("TEMPE/BIJI", 2000), ("TELUR KRISPI", 2000)]

norm = lambda s: re.sub(r"[^A-Z0-9]", "", (s or "").upper())
ada = {}
for p in Prod.search([("sale_ok", "=", True)]):
    ada.setdefault(norm(p.product_tmpl_id.display_name), p.product_tmpl_id.display_name)

say("")
say("=" * 112)
say("B. BUAT 9 PRODUK ADD-ON")
say("=" * 112)
buat = []
for nm, price in ADDON:
    if norm(nm) in ada:
        say("%-16s %8s   DILEWATI — sudah ada: %s" % (nm, money(price), ada[norm(nm)]))
    else:
        buat.append((nm, price))
        say("%-16s %8s   akan dibuat" % (nm, money(price)))

say("")
say("RINGKASAN: %d harga paket diperbaiki, %d produk add-on dibuat" % (len(fixes), len(buat)))

if not RUN:
    say("")
    say("DRY-RUN — tidak ada perubahan.")
    env.cr.rollback()
else:
    say("")
    say("EKSEKUSI")
    for t, nm, old, new in fixes:
        t.write({"list_price": new})
    say("   %d harga paket ditulis" % len(fixes))
    for nm, price in buat:
        p = Prod.create({
            "name": nm,
            "list_price": price,
            "sale_ok": True,
            "available_in_pos": True,
            "type": "consu",
        })
        say("   add-on dibuat: %-16s id=%-5s harga %s" % (nm, p.id, money(price)))
    env.cr.flush()

    bad = [nm for t, nm, old, new in fixes if abs(float(t.list_price) - new) > 0.005]
    if bad:
        env.cr.rollback()
        say("   MISMATCH -> ROLLBACK: %s" % bad)
    else:
        env.cr.commit()
        say("   COMMITTED.")
say("=" * 112)
