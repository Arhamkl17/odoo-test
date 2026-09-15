# -*- coding: utf-8 -*-
"""
juni_juli_59_dup_bom_direct.py — uji apakah BOM benar-benar DISALIN (READ-ONLY).

Dua tanda tangan:
  D = baris BOM langsung (anak), (product_id, qty, bom_type)  -> "BOM disalin?"
  L = daun hasil explode (semua level), (component_id, qty)   -> "efek resep sama"

Kasus D sama        -> BOM identik apa adanya (copy-paste).
Kasus D beda, L sama -> kit berbeda tapi komposisi daunnya sama (masih wajar).
"""
from collections import defaultdict
import os

ROUND = int(os.environ.get("ROUND", "3"))
cr = env.cr
Bom = env["mrp.bom"]
BomLine = env["mrp.bom.line"]
Prod = env["product.product"]
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))


def sp(p):
    v = p.standard_price
    return float((v.get("1") if isinstance(v, dict) else v) or 0.0)


sigD = defaultdict(list)
sigL = defaultdict(list)
meta = {}
for bom in Bom.search([("type", "in", ("phantom", "normal"))]):
    tmpl = bom.product_tmpl_id
    if not tmpl:
        continue
    d = tuple(sorted((l.product_id.id, round(l.product_qty or 0, ROUND)) for l in bom.bom_line_ids))
    _b, lines = bom.explode(tmpl, 1.0)
    lv, cost = [], 0.0
    for bl, vals in lines:
        c = bl.product_id
        if not c or Bom.search_count([("product_tmpl_id", "=", c.product_tmpl_id.id)]):
            continue
        q = round(vals.get("qty") or 0.0, ROUND)
        lv.append((c.id, q))
        cost += sp(c) * q
    if not d or not lv:
        continue
    key = tmpl.id
    sigD[d].append(key)
    sigL[tuple(sorted(lv))].append(key)
    meta[key] = {"tmpl": tmpl, "bom": bom, "cost": cost, "nd": len(d), "nl": len(lv)}

onlyL = {k: v for k, v in sigL.items() if len(v) > 1}
onlyD = {k: v for k, v in sigD.items() if len(v) > 1}
print_D = set()
for v in onlyD.values():
    print_D.update(v)
print_L = set()
for v in onlyL.values():
    print_L.update(v)

say("=" * 118)
say("A. BOM IDENTIK APA ADANYA (baris langsung sama) — %d kelompok, %d template" % (len(onlyD), len(print_D)))
say("=" * 118)
for k, v in sorted(onlyD.items(), key=lambda kv: -len(kv[1])):
    m = meta[v[0]]
    say("")
    say("-- %d template | %d baris BOM langsung | biaya %s | jenis BOM: %s" % (
        len(v), m["nd"], money(m["cost"]), sorted(set(meta[x]["bom"].type for x in v))))
    for x in v:
        say("   tmpl=%-5d %-52s harga %8s" % (
            x, (meta[x]["tmpl"].display_name or "")[:52], money(meta[x]["tmpl"].list_price)))
    say("   baris: %s" % ", ".join(
        "%s x%s" % (Prod.browse(c).display_name[:26], q) for c, q in k[:6]))
    if len(k) > 6:
        say("          (+%d baris lain)" % (len(k) - 6))

say("")
say("=" * 118)
say("B. HANYA DAUNNYA YANG SAMA (baris langsung BERBEDA) — %d kelompok tambahan" % (
    len([k for k in onlyL if k not in sigD or len(sigD.get(k, [])) < 2])))
say("=" * 118)
for k, v in sorted(onlyL.items(), key=lambda kv: -len(kv[1])):
    if len(v) < 2:
        continue
    dkeys = set()
    for x in v:
        for dk, dv in sigD.items():
            if x in dv:
                dkeys.add(dk)
    if len(dkeys) == 1:
        continue          # sudah dilaporkan di bagian A
    say("")
    say("-- %d template, komposisi daun sama (%d daun), biaya %s" % (len(v), meta[v[0]]["nl"], money(meta[v[0]]["cost"])))
    for x in v:
        m = meta[x]
        ndirect = m["nd"]
        say("   tmpl=%-5d %-50s harga %8s | %2d baris langsung | %s" % (
            x, (m["tmpl"].display_name or "")[:50], money(m["tmpl"].list_price),
            ndirect, m["bom"].type))
env.cr.rollback()
