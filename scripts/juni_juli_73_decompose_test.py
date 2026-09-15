# -*- coding: utf-8 -*-
"""
juni_juli_73_decompose_test.py — UJI BONGKAR RESEP (READ-ONLY).

Untuk setiap PAKET/PKG/PKC/BIG HEMAT/RAMA/SEGEPOK/SETIA/LOKAL DUO:
cari kombinasi resep menu DASAR (tanpa awalan PAKET/PKG/PKC) yang jumlah komponennya
PERSIS sama (multiset) dengan resep paket. Bila ketemu -> paket bisa dihargai
dari jumlah harga komponennya.
"""
from collections import Counter
import itertools
import re

Bom = env["mrp.bom"]
Prod = env["product.product"]
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

PREFIX = ("PAKET ", "PKG ", "PKC ", "BIG HEMAT")


def recipe(tmpl):
    bom = Bom.search([("product_tmpl_id", "=", tmpl.id), ("type", "in", ("phantom", "normal"))], limit=1)
    if not bom:
        return None
    sig = Counter()
    for l in bom.bom_line_ids:
        t = l.product_id.product_tmpl_id.id
        if Bom.search_count([("product_tmpl_id", "=", t)]):
            return None          # ada sub-menu, tidak dipakai di uji ini
        sig[(l.product_id.id, round(l.product_qty or 0, 4))] += 1
    return sig


menus = {}
for p in Prod.search([("sale_ok", "=", True), ("available_in_pos", "=", True)]):
    t = p.product_tmpl_id
    r = recipe(t)
    if r:
        menus[t.id] = {"tmpl": t, "nm": (t.display_name or "").strip(),
                       "sig": r, "price": float(t.list_price or 0)}

base = {k: v for k, v in menus.items() if not v["nm"].upper().startswith(PREFIX)}
pkg = {k: v for k, v in menus.items() if v["nm"].upper().startswith(PREFIX)}

say("=" * 118)
say("UJI BONGKAR RESEP: %d menu paket vs %d menu dasar" % (len(pkg), len(base)))
say("=" * 118)
ok = 0
for k, v in sorted(pkg.items(), key=lambda kv: kv[1]["nm"]):
    target = v["sig"]
    found = None
    # coba kombinasi 1..4 menu dasar (dengan pengulangan), maksimal 4000 percobaan
    cands = list(base.values())
    tries = 0
    for n in range(1, 5):
        for combo in itertools.combinations_with_replacement(range(len(cands)), n):
            tries += 1
            if tries > 4000:
                break
            tot = Counter()
            for i in combo:
                tot += cands[i]["sig"]
            if tot == target:
                found = [cands[i] for i in combo]
                break
        if found or tries > 4000:
            break
    if found:
        ok += 1
        say("")
        say("✔ %-46s harga %9s" % (v["nm"][:46], money(v["price"])))
        for f in found:
            say("     = %-42s harga %9s" % (f["nm"][:42], money(f["price"])))
        say("     resep cocok persis (%d baris)" % sum(target.values()))
    else:
        say("")
        say("✘ %-46s harga %9s  -> TIDAK bisa dibongkar (maks 4 menu dasar)" % (
            v["nm"][:46], money(v["price"])))
say("")
say("-" * 118)
say("berhasil dibongkar: %d dari %d paket (%.0f%%)" % (ok, len(pkg), (100.0 * ok / len(pkg)) if pkg else 0))
say("=" * 118)
env.cr.rollback()
