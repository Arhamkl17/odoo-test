# -*- coding: utf-8 -*-
"""
juni_juli_72_bom_submenu.py — apakah resep PAKET memuat sub-menu? (READ-ONLY)

Ini menentukan apakah harga Dine In paket bisa "dibangun dari komponennya":
  - bila baris BOM memuat produk MENU lain (NASI, ES TEH, AYAM GEPREK, INDOMIE, SAMBAL)
    -> uplift bisa dihitung dari uplift tiap sub-menu
  - bila hanya bahan mentah -> harus jalur lain
"""
import os

Bom = env["mrp.bom"]
Prod = env["product.product"]
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

POS = {}
for p in Prod.search([("sale_ok", "=", True), ("available_in_pos", "=", True)]):
    POS[p.product_tmpl_id.id] = p.id

say("=" * 120)
say("BARIS BOM LANGSUNG setiap menu — mana yang berupa PRODUK MENU (sub-menu)")
say("=" * 120)
n_sub = n_flat = 0
for bom in Bom.search([("type", "in", ("phantom", "normal"))]):
    tmpl = bom.product_tmpl_id
    if not tmpl or tmpl.id not in POS:
        continue
    subs, raws = [], []
    for l in bom.bom_line_ids:
        t = l.product_id.product_tmpl_id.id
        # sub-menu = barisnya produk yang punya BOM sendiri ATAU ada di daftar POS
        if Bom.search_count([("product_tmpl_id", "=", t)]):
            subs.append("%s x%s" % (l.product_id.display_name, l.product_qty))
        else:
            raws.append(l.product_id.display_name)
    if subs:
        n_sub += 1
        say("")
        say("SUB-MENU  %-48s harga %9s | %d baris" % (
            (tmpl.display_name or "")[:48], money(tmpl.list_price), len(bom.bom_line_ids)))
        for s in subs:
            say("      + %s" % s)
    else:
        n_flat += 1
say("")
say("-" * 120)
say("menu dengan sub-menu : %d" % n_sub)
say("menu bahan mentah saja: %d" % n_flat)
say("")
say("=" * 120)
say("PRODUK MENU yang dipakai sebagai komponen oleh menu lain")
say("=" * 120)
used = {}
for bom in Bom.search([("type", "in", ("phantom", "normal"))]):
    tmpl = bom.product_tmpl_id
    if not tmpl or tmpl.id not in POS:
        continue
    for l in bom.bom_line_ids:
        c = l.product_id
        if c.product_tmpl_id.id in POS and Bom.search_count([("product_tmpl_id", "=", c.product_tmpl_id.id)]):
            used.setdefault(c.product_tmpl_id.display_name, set()).add(tmpl.display_name)
for nm, users in sorted(used.items(), key=lambda kv: -len(kv[1])):
    say("   %-46s dipakai oleh %d menu" % (nm[:46], len(users)))
say("=" * 120)
env.cr.rollback()
