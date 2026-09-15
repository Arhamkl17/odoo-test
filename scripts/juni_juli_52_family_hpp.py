# -*- coding: utf-8 -*-
"""
juni_juli_52_family_hpp.py — KELOMPOKKAN menu HPP>ambang jadi KELUARGA (READ-ONLY).

Keluaran:
  A. daftar keluarga (agg omzet, rasio terburuk, jumlah anggota)
  B. bedah BOM lengkap untuk keluarga terburuk
  C. pemeriksaan data: menu kembar (nama identik) & omzet yang mustahil sama

  su odoo ... " THRESHOLD=45 TARGET=45 TOP=18 odoo shell ..." < scripts/juni_juli_52_family_hpp.py
"""
import os
import re
from collections import defaultdict

THRESHOLD = float(os.environ.get("THRESHOLD", "45"))
TARGET = float(os.environ.get("TARGET", "45"))
TOP = int(os.environ.get("TOP", "18"))
cr = env.cr
Bom = env["mrp.bom"]
Prod = env["product.product"]
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

PROT = ("SAYAP/PAHA BAWAH", "DADA/PAHA ATAS", "PAHA BAWAH", "SAYAP", "DADA")


def sp(p):
    v = p.standard_price
    return float((v.get("1") if isinstance(v, dict) else v) or 0.0)


def core_name(nm):
    s = (nm or "").upper()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^A-Z0-9/ ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    for pref in ("PAKET ", "PKG ", "PKC "):
        if s.startswith(pref):
            s = s[len(pref):]
    for prot in PROT:
        s = s.replace(prot, "AYAM")
    s = re.sub(r"\b(BIG HEMAT) [0-9]+\b", r"\1", s)
    s = re.sub(r"\b(AYAM AYAM|AYAM AYAM AYAM)\b", "AYAM", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or (nm or "?").upper()


def explode(tmpl):
    bom = Bom.search([("product_tmpl_id", "=", tmpl.id),
                      ("type", "in", ("phantom", "normal"))], limit=1)
    if not bom:
        return None, None
    _b, lines = bom.explode(bom.product_tmpl_id, 1.0)
    comps = []
    for bl, vals in lines:
        c = bl.product_id
        if not c:
            continue
        if Bom.search_count([("product_tmpl_id", "=", c.product_tmpl_id.id)]):
            continue
        q = vals.get("qty") or 0.0
        comps.append((q * sp(c), c.display_name, q, c.uom_id.name, sp(c)))
    comps.sort(reverse=True)
    return comps, bom


cr.execute("""
    SELECT pol.product_id, SUM(pol.qty), SUM(pol.price_subtotal)
      FROM pos_order_line pol JOIN pos_order po ON po.id = pol.order_id
     WHERE po.state IN ('paid','done','invoiced')
       AND po.date_order >= '2026-06-01' AND po.date_order < '2026-09-01'
     GROUP BY 1""")
sales = {int(p): (float(q or 0), float(r or 0)) for p, q, r in cr.fetchall() if p}

over, under = [], []
for p in Prod.search([("sale_ok", "=", True), ("available_in_pos", "=", True)]):
    tmpl = p.product_tmpl_id
    price = tmpl.list_price or 0.0
    comps, bom = explode(tmpl)
    if not comps or not price:
        continue
    cost = sum(c[0] for c in comps)
    ratio = cost / price * 100
    qty, rev = sales.get(p.id, (0.0, 0.0))
    rec = {"pid": p.id, "tmpl": tmpl, "nm": tmpl.display_name or "", "price": price,
           "cost": cost, "ratio": ratio, "qty": qty, "rev": rev,
           "comps": comps, "bom": bom}
    (over if ratio > THRESHOLD else under).append(rec)

# ---- keluarga -------------------------------------------------------------
fam = defaultdict(list)
for r in over:
    fam[core_name(r["nm"])].append(r)

fams = []
for k, members in fam.items():
    worst = max(members, key=lambda r: r["ratio"])
    fams.append({
        "key": k, "members": members,
        "rev": sum(m["rev"] for m in members),
        "qty": sum(m["qty"] for m in members),
        "worst": worst,
        "maxr": worst["ratio"],
    })
fams.sort(key=lambda f: -f["maxr"])

say("=" * 120)
say("KELUARGA MENU HPP > %.0f%%   — %d menu -> %d keluarga   (target %.0f%%, basis HPP/harga jual)"
    % (THRESHOLD, len(over), len(fams), TARGET))
say("=" * 120)
say("%-4s %-46s %5s %9s %9s %8s %6s %13s" % (
    "no", "keluarga", "angg", "harga", "HPP", "rasio", "qty", "omzet 3bln"))
say("-" * 120)
for i, f in enumerate(fams, 1):
    w = f["worst"]
    say("%-4d %-46s %5d %9s %9s %7.1f%% %6.0f %13s" % (
        i, f["key"][:46], len(f["members"]), money(w["price"]), money(w["cost"]),
        f["maxr"], f["qty"], money(f["rev"])))

say("")
say("=" * 120)
say("BEDAH BOM — %d keluarga terburuk" % TOP)
say("=" * 120)
for i, f in enumerate(fams[:TOP], 1):
    say("")
    say("### %2d. %s   (%d menu, omzet 3bln %s)" % (i, f["key"], len(f["members"]), money(f["rev"])))
    seen_sig = set()
    for m in sorted(f["members"], key=lambda x: -x["ratio"]):
        sig = (round(m["cost"], 2), round(m["price"], 2))
        dup = "  [KEMBAR]" if sig in seen_sig else ""
        seen_sig.add(sig)
        ideal = m["cost"] / (TARGET / 100.0)
        say("    %-50s harga %8s  HPP %8s  %6.1f%%  qty %5.0f%s" % (
            m["nm"][:50], money(m["price"]), money(m["cost"]), m["ratio"], m["qty"], dup))
        say("       -> harga ideal %s (naik %+.0f%%)  |  atau pangkas biaya %s (-%.0f%%)" % (
            money(ideal), (ideal / m["price"] - 1) * 100,
            money(m["cost"] - m["price"] * TARGET / 100.0),
            (1 - (m["price"] * TARGET / 100.0) / m["cost"]) * 100 if m["cost"] else 0))
    m = f["worst"]
    say("    RINCIAN BIAYA (menu terburuk: %s):" % m["nm"][:60])
    for c, nm, q, uom, spv in m["comps"][:8]:
        say("       - %-42s %10s = %7.2f %-5s x %s" % (
            (nm or "")[:42], money(c), q, (uom or "")[:5], money(spv)))
    if len(m["comps"]) > 8:
        say("       - (+%d komponen lain) %s" % (
            len(m["comps"]) - 8, money(sum(c[0] for c in m["comps"][8:]))))

# ---- C. pemeriksaan data -------------------------------------------------
say("")
say("=" * 120)
say("C. PEMERIKSAAN DATA")
say("=" * 120)
byname = defaultdict(list)
for r in over + under:
    byname[r["nm"]].append(r)
dupn = {k: v for k, v in byname.items() if len(v) > 1}
say("Nama menu muncul >1x: %d" % len(dupn))
for k, v in list(dupn.items())[:20]:
    say("   %-58s -> id %s" % (k[:58], [x["pid"] for x in v]))

bymoney = defaultdict(list)
for r in over:
    bymoney[(round(r["qty"], 4), round(r["rev"], 2), round(r["cost"], 2), round(r["price"], 2))].append(r)
say("")
say("Menu dengan qty+omzet+harga+HPP PERSIS sama (indikasi data ganda):")
n = 0
for k, v in bymoney.items():
    if len(v) > 1:
        n += 1
        say("   qty %6.0f omzet %12s -> %s" % (k[0], money(k[1]), [x["nm"][:44] for x in v]))
if not n:
    say("   (tidak ada)")
say("=" * 120)
env.cr.rollback()
