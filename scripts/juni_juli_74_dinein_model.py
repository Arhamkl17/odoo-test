# -*- coding: utf-8 -*-
"""
juni_juli_74_dinein_model.py — MODEL HARGA DINE IN DARI KOMPONEN (READ-ONLY, odoo shell).

Idenya:
  1. Anchor = 53 item daftar Dine In klien yang berhasil dipetakan ke produk sistem.
     uplift(anchor) = harga_dinein - harga_dasar
  2. Untuk tiap menu lain, cari kombinasi anchor (<=4, boleh berulang) yang resepnya
     merupakan HIMPUNAN BAGIAN (multiset subset) dari resep menu itu, maksimalkan
     nilai dasar yang tercakup.
  3. harga_dinein(menu) = harga_dasar + jumlah uplift anchor terpilih.
  4. Uji: apakah model ini mereproduksi anchor paket yang kita punya (PAKET SEGEPOK)?

  su odoo ... < scripts/juni_juli_74_dinein_model.py
"""
import difflib
import re
from collections import Counter

import openpyxl

PATH = "product_photos/data sheet master/TEMPLATE IMPORT HARGA DINE IN.xlsx"
cr = env.cr
Prod = env["product.product"]
Bom = env["mrp.bom"]
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

# ---------------------------------------------------------------- 1. daftar Dine In klien
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

# ---------------------------------------------------------------- 2. produk POS + penjualan
cr.execute("""
    SELECT pol.product_id, SUM(pol.qty), SUM(pol.price_subtotal)
      FROM pos_order_line pol JOIN pos_order po ON po.id=pol.order_id
     WHERE po.state IN ('paid','done','invoiced')
       AND po.date_order >= '2026-06-01' AND po.date_order < '2026-09-01'
     GROUP BY 1""")
sales = {int(p): (float(q or 0), float(r or 0)) for p, q, r in cr.fetchall() if p}

sysprod = []
for p in Prod.search([("sale_ok", "=", True), ("available_in_pos", "=", True)]):
    t = p.product_tmpl_id
    nm = (t.display_name or "").strip()
    q, rev = sales.get(p.id, (0.0, 0.0))
    sysprod.append({"pid": p.id, "tid": t.id, "nm": nm, "up": nm.upper(),
                    "price": float(t.list_price or 0), "qty": q, "rev": rev})
by_up = {s["up"]: s for s in sysprod}
norm = lambda s: re.sub(r"[^A-Z0-9]", "", (s or "").upper())
by_norm = {}
for s in sysprod:
    by_norm.setdefault(norm(s["up"]), s)

ALIAS = {
    "KRISPI DADA/PAHA ATAS": "AYAM CRISPY DADA/PAHA ATAS",
    "KRISPI PAHA BAWAH": "AYAM CRISPY PAHA BAWAH",
    "KRISPI SAYAP": "AYAM CRISPY SAYAP",
    "AYAM KRISPI PAHA ATAS/DADA": "AYAM CRISPY DADA/PAHA ATAS",
    "AYAM KRISPI PAHA BAWAH": "AYAM CRISPY PAHA BAWAH",
    "AYAM KRISPI SAYAP": "AYAM CRISPY SAYAP",
    "GEPREK SAMBAL IJO": "GEPREK SAMBAL IJO PADANG",
    "GEPREK SAMBAL KOREK": "GEPREK SAMBAL KOREK SURABAYA",
    "GEPREK SAMBAL RICA": "GEPREK SAMBAL RICA MANADO",
    "GEPREK BARBEQUE": "GEPREK SMOKEY BBQ",
    "GEPREK KEJU LUMER": "GEPREK SAOS KEJU LUMER",
    "GEPREK KEJU MOZZA": "GEPREK MOZAA",
    "GEPREK KEJU TABUR": "GEPREK KEJU",
    "PAKET SEGEPOK": "SEGEPOK BERLIMA",
    "MIE GORENG": "INDOMIE",
    "ES LEMON TEA": "LEMON TEA",
    "ES COKELAT": "ICE CHOCOLATE",
    "ES COLA": "ICE COLA",
    "KULIT": "KULIT CRISPY",
    "ES TEH": "ES TEH",
    "NASI": "NASI",
}

# ---------------------------------------------------------------- 3. resep tiap produk POS
def recipe_of(tid):
    bom = Bom.search([("product_tmpl_id", "=", tid), ("type", "in", ("phantom", "normal"))], limit=1)
    if not bom:
        return None
    sig = Counter()
    for l in bom.bom_line_ids:
        sig[l.product_id.id] += round(l.product_qty or 0, 4)
    return sig


recipes = {}
for s in sysprod:
    r = recipe_of(s["tid"])
    if r:
        r = Counter({k: v for k, v in r.items()})
        recipes[s["tid"]] = +r

# ---------------------------------------------------------------- 4. anchor
anchors, unmatched = [], []
for nm, pr in sorted(dinein.items()):
    hit, cara = None, ""
    if nm in ALIAS and ALIAS[nm] in by_up:
        hit, cara = by_up[ALIAS[nm]], "alias"
    elif nm in by_up:
        hit, cara = by_up[nm], "persis"
    elif norm(nm) in by_norm:
        hit, cara = by_norm[norm(nm)], "normal"
    else:
        cand = difflib.get_close_matches(nm, [s["up"] for s in sysprod], n=1, cutoff=0.72)
        if cand:
            hit, cara = by_up[cand[0]], "mirip"
    if not hit:
        unmatched.append((nm, pr))
        continue
    if hit["price"] <= 0:
        unmatched.append((nm, pr))
        continue
    a = dict(hit)
    a.update({"dn_nm": nm, "dn_price": pr, "cara": cara,
              "uplift": pr - hit["price"], "ratio": pr / hit["price"],
              "sig": recipes.get(hit["tid"])})
    anchors.append(a)

# dedupe anchor dengan resep identik (resep sama -> tidak boleh dihitung dua kali)
sig_key = lambda s: tuple(sorted(s.items())) if s else None
seen = {}
for a in sorted(anchors, key=lambda x: x["uplift"]):
    k = sig_key(a["sig"]) or ("NORECIPE", a["tid"])
    if k in seen:
        a["dup_of"] = seen[k]["up"]
        seen[k]["dups"] = seen[k].get("dups", []) + [a["up"]]
    else:
        a["dup_of"] = None
        seen[k] = a

say("=" * 128)
say("ANCHOR — %d item daftar Dine In terpetakan, %d tak terpetakan" % (len(anchors), len(unmatched)))
say("=" * 128)
say("%-38s %9s %-40s %9s %8s %7s %7s  %s" % (
    "nama di daftar Dine In", "Dine In", "produk sistem", "dasar", "uplift", "rasio", "qty", "cara"))
say("-" * 128)
for a in sorted(anchors, key=lambda x: -x["uplift"]):
    say("%-38s %9s %-40s %9s %8s %6.2fx %7.0f  %s%s" % (
        a["dn_nm"][:38], money(a["dn_price"]), a["nm"][:40], money(a["price"]),
        money(a["uplift"]), a["ratio"], a["qty"], a["cara"],
        ("  [dup resep: %s]" % a["dup_of"][:28]) if a["dup_of"] else ""))
if unmatched:
    say("")
    say("TAK TERPETAKAN / tanpa harga (%d):" % len(unmatched))
    for nm, pr in unmatched:
        say("    %-46s %s" % (nm[:46], money(pr)))

# ---------------------------------------------------------------- 5. pool anchor utk dekomposisi
pool = [(a["tid"], a["sig"], a["uplift"], a["price"], a["nm"])
        for a in anchors if a["sig"] and not a["dup_of"]]
say("")
say("pool dekomposisi: %d anchor beresep unik" % len(pool))

# ---------------------------------------------------------------- 6. dekomposisi
MAXN = 4


def decompose(target):
    """cari kombinasi anchor (<=MAXN) yg resepnya subset dari target, maksimalkan nilai dasar."""
    cands = [(tid, sig, up, bp, nm) for (tid, sig, up, bp, nm) in pool
             if all(target.get(k, 0) >= v for k, v in sig.items())]
    if not cands:
        return None
    # urutan: uplift terbesar dulu supaya DFS menemukan solusi bagus lebih awal
    cands.sort(key=lambda c: -c[3])
    best = {"val": -1.0, "n": 99, "combo": None}

    def dfs(i, used, val, combo):
        if combo and val > best["val"] + 1e-6 or (abs(val - best["val"]) < 1e-6 and len(combo) < best["n"]):
            best.update({"val": val, "n": len(combo), "combo": list(combo)})
        if len(combo) >= MAXN or i >= len(cands):
            return
        for j in range(i, len(cands)):
            tid, sig, up, bp, nm = cands[j]
            if all(used.get(k, 0) + v <= target.get(k, 0) for k, v in sig.items()):
                for k, v in sig.items():
                    used[k] = used.get(k, 0) + v
                combo.append(cands[j])
                dfs(j, used, val + bp, combo)
                combo.pop()
                for k, v in sig.items():
                    used[k] -= v
                    if not used[k]:
                        del used[k]

    dfs(0, {}, 0.0, [])
    return best["combo"]


say("")
say("=" * 128)
say("MODEL: harga_dinein = harga_dasar + jumlah uplift anchor yg resepnya terkandung")
say("=" * 128)
say("%-46s %9s %9s %7s  %s" % ("menu", "dasar", "Dine In", "naik", "komponen anchor terdeteksi"))
say("-" * 128)
got = same = 0
rows_out = []
for s in sorted(sysprod, key=lambda x: -x["rev"]):
    a = next((x for x in anchors if x["pid"] == s["pid"]), None)
    if a:
        pred, src = a["dn_price"], "daftar klien (langsung)"
    else:
        combo = decompose(recipes.get(s["tid"], Counter()))
        if combo:
            pred = s["price"] + sum(c[2] for c in combo)
            src = " + ".join("%s" % c[4].split(" (")[0] for c in combo)
            got += 1
        else:
            pred, src = s["price"], "— tidak terdeteksi"
            same += 1
    rows_out.append((s, pred, src))
    say("%-46s %9s %9s %6.0f%%  %s" % (
        s["nm"][:46], money(s["price"]), money(pred),
        100.0 * (pred - s["price"]) / s["price"] if s["price"] else 0, src[:58]))

say("-" * 128)
rev = sum(s["rev"] for s, _, _ in rows_out)
rev_up = sum(s["rev"] * (p - s["price"]) / s["price"] for s, p, _ in rows_out if s["price"])
say("menu dapat uplift : %d dari %d | tanpa uplift: %d" % (got, len(rows_out), same))
say("omzet 3 bulan     : %s" % money(rev))
say("kenaikan omzet bila semua 100%% Dine In: %s (%.1f%%)" % (
    money(rev_up), 100.0 * rev_up / rev if rev else 0))

# ---------------------------------------------------------------- 7. validasi pada anchor paket
say("")
say("=" * 128)
say("VALIDASI pada anchor PAKET (resepnya bisa dibongkar -> bandingkan model vs harga klien)")
say("=" * 128)
for a in anchors:
    if not a["sig"] or not a["nm"].upper().startswith(("PAKET", "PKG", "PKC", "BIG HEMAT", "SEGEPOK")):
        continue
    combo = decompose(a["sig"])
    if not combo:
        say("%-46s tidak bisa dibongkar" % a["nm"][:46])
        continue
    idx = next(i for i, (tid, _, _, _, _) in enumerate(pool) if True)  # noqa
    pred = a["price"] + sum(c[2] for c in combo)
    err = pred - a["dn_price"]
    say("%-46s klien %9s | model %9s | selisih %+8s (%+.1f%%)" % (
        a["nm"][:46], money(a["dn_price"]), money(pred), money(err),
        100.0 * err / a["dn_price"] if a["dn_price"] else 0))
    for c in combo:
        say("        + %-40s uplift %8s" % (c[4][:40], money(c[2])))

env.cr.rollback()
