# -*- coding: utf-8 -*-
"""
juni_juli_97_ghost_final.py — RECON DEFINITIF R1 (READ-ONLY).

PERINGATAN: `mrp_bom.product_tmpl_id` = **template** id, sedangkan §21.1 spec memakai
**product** id. Keduanya berbeda (mis. pp 593 → tmpl 604). Skrip ini selalu menampilkan
keduanya supaya tidak tertukar.

6 pasangan (dari sidik jari BOM stabil md5):
  {566,603} {567,604} {568,608} {584,625} {572,630} {585,618}
"""
import csv, os

cr = env.cr
PP = env["product.product"]
PT = env["product.template"]
BOM = env["mrp.bom"]
PL = env["product.pricelist"]
PPI = env["product.pricelist.item"]

say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))
num = lambda x: "{:,.4f}".format(float(x or 0)).rstrip("0").rstrip(".")

PAIRS = [
    (567, 604, "SAMBAL KOREK SURABAYA"),
    (566, 603, "SAMBAL IJO PADANG"),
    (568, 608, "SAMBAL RICA MANADO"),
    (584, 625, "MEVVAH"),
    (572, 630, "KULIT CRISPY"),
    (585, 618, "INDOMIE GEPREK SAMBAL LOKAL"),
]


def read_csv(path):
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            nm = (row.get("Nama") or "").strip()
            if nm:
                out[nm] = row
    return out


KLIEN = read_csv("import_data/csv/05_products_with_id.csv")
HARGA = read_csv("import_data/csv/06_price_update.csv")

say("=" * 126)
say("RECON DEFINITIF R1 — 6 pasangan produk kembar   (read-only)")
say("=" * 126)

tmpl_ids = [t for p in PAIRS for t in p[:2]]

# ------------------------------------------------ jejak HPP per produk
cr.execute("""
    SELECT aml.product_id, COUNT(*), COALESCE(SUM(aml.balance),0)
      FROM account_move_line aml
      JOIN account_move am ON am.id = aml.move_id
      JOIN account_account aa ON aa.id = aml.account_id
     WHERE am.state='posted' AND aa.account_type='expense_direct_cost'
       AND aml.product_id IS NOT NULL
     GROUP BY 1
""")
hpp = {r[0]: (r[1], float(r[2])) for r in cr.fetchall()}

say("")
for a, b, label in PAIRS:
    say("━" * 126)
    say("PASANGAN: %s" % label)
    say("")
    say("%-5s %-5s %-62s %-7s %-7s %10s %11s %11s %6s" % (
        "tmpl", "pp", "nama di sistem", "klien", "harga", "lst_price", "TakeAway", "DineIn", "order"))
    say("-" * 126)
    for t in (a, b):
        pt = PT.browse(t)
        pp = PP.search([("product_tmpl_id", "=", t)], limit=1)
        nama = pt.name or ""
        cr.execute("SELECT COUNT(*), COALESCE(SUM(qty),0), COALESCE(SUM(price_subtotal_incl),0) "
                   "FROM pos_order_line WHERE product_id=%s", (pp.id,))
        n, q, rev = cr.fetchone()
        h = hpp.get(pp.id, (0, 0.0))
        d = {}
        for pl in PL.search([]):
            it = PPI.search([("pricelist_id", "=", pl.id), "|",
                             ("product_id", "=", pp.id),
                             "&", ("product_tmpl_id", "=", t), ("applied_on", "=", "1_product")], limit=1)
            if it:
                d[pl.name] = it.fixed_price
        say("%-5s %-5s %-62s %-7s %-7s %10s %11s %11s %6d" % (
            t, pp.id, nama[:62],
            "ADA" if nama.strip() in KLIEN else "—",
            "ADA" if nama.strip() in HARGA else "—",
            money(pt.list_price),
            money(d.get("Harga Dasar (Take Away)")) if d.get("Harga Dasar (Take Away)") is not None else "—",
            money(d.get("Harga Dine In")) if d.get("Harga Dine In") is not None else "—",
            n))
        say("      └─ qty=%-9s omzet=%-16s | baris JE HPP=%-5d nilai HPP=%s | BOM=%d | POS=%s" % (
            num(q), money(rev), h[0], money(h[1]),
            BOM.search_count([("product_tmpl_id", "=", t)]),
            "ya" if pt.available_in_pos else "TIDAK"))
        # harga dari daftar harga klien
        if nama.strip() in HARGA:
            say("      └─ daftar harga klien: %s / %s %s" % (
                HARGA[nama.strip()].get("Harga Jual"), HARGA[nama.strip()].get("Unit"),
                "(nama ini ADA di 06_price_update.csv)"))
    say("")

say("=" * 126)
say("[REKAP] mana yang ada di daftar produk klien (05_products_with_id.csv)")
say("")
for a, b, label in PAIRS:
    ada = []
    for t in (a, b):
        nm = (PT.browse(t).name or "")
        ada.append((t, nm, nm.strip() in KLIEN))
    n_ada = sum(1 for _x in ada if _x[2])
    tag = "JELAS" if n_ada == 1 else ("AMBIGU" if n_ada == 2 else "DUA-DUANYA HANTU")
    say("   [%-6s] %s" % (tag, label))
    for t, nm, ok in ada:
        say("        tmpl=%-5s %-64s %s" % (t, nm[:64], "ADA" if ok else "—"))
    say("")
say("=" * 126)
