# -*- coding: utf-8 -*-
"""READ-ONLY: susun tabel mapping BOM utk direview + ukur dampak hapus TERONG CRISPY."""
from collections import Counter

AUG_FROM, AUG_TO = "2026-08-01", "2026-09-01"
Prod = env["product.product"]
Bom = env["mrp.bom"]
BomLine = env["mrp.bom.line"]
POSm = env["pos.order"]

# ---------------------------------------------------------------------------
# 1. DAMPAK HAPUS TERONG CRISPY
# ---------------------------------------------------------------------------
print("=" * 78)
print("1. DAMPAK HAPUS 'TERONG CRISPY'")
terong = Prod.search([("name", "=", "TERONG CRISPY")], limit=1)
if terong:
    lines = env["pos.order.line"].search([("product_id", "=", terong.id)])
    rev = sum(l.price_subtotal_incl for l in lines)
    aug_lines = [l for l in lines if AUG_FROM <= str(l.order_id.date_order)[:10] < AUG_TO]
    aug_rev = sum(l.price_subtotal_incl for l in aug_lines)
    orders = len(set(l.order_id.id for l in lines))
    sm = env["stock.move"].search([("product_id", "=", terong.id)])
    bom = Bom.search([("product_tmpl_id", "=", terong.product_tmpl_id.id)])
    print("   id=%s category=%s harga=%s active=%s" % (
        terong.id, terong.categ_id.name, terong.list_price, terong.active))
    print("   pos.order.line : %d baris (Agustus %d) di %d order" % (
        len(lines), len(aug_lines), orders))
    print("   omzet total    : %s  (Agustus %s = %.3f%% dari 232.683.763)" % (
        "{:,.2f}".format(rev), "{:,.2f}".format(aug_rev), 100 * aug_rev / 232683763))
    print("   stock.move     : %d" % len(sm))
    print("   BOM            : %d" % len(bom))
    print("   dipakai di BOM lain: %d baris" % BomLine.search_count([("product_id", "=", terong.id)]))
    print("   >> menghapus produk = harus ikut menghapus %d baris order (omzet Agustus turun %s)" % (
        len(lines), "{:,.2f}".format(aug_rev)))
else:
    print("   tidak ditemukan")

# ---------------------------------------------------------------------------
# 2. MAPPING
# ---------------------------------------------------------------------------
MAP = [
    (567, "PAKET AYAM CRISPY DADA/PAHA ATAS", None),
    (568, "PAKET AYAM CRISPY SAYAP", None),
    (569, "PAKET AYAM CRISPY PAHA BAWAH", None),
    (571, "PAKET INDOMIE CRISPY DADA/PAHA ATAS", None),
    (572, "PKG INDOMIE CRISPY SAYAP", None),
    (574, "PKG INDOMIE GEPREK SAMBAL LOKAL", None),
    (555, "PKG SAMBAL IJO PADANG", None),
    (556, "PKG SAMBAL KOREK SURABAYA", None),
    (557, "PKG SAMBAL RICA MANADO", None),
    (558, "PKG SAMBAL RICA MANADO", ("SAMBAL RICA MANADO", "SAMBAL TOMAT MALINO", None)),
    (559, "GEPREK SAOS KEJU LUMER", None),
    (545, "GEPREK SAOS KEJU LUMER", None),
    (549, "GEPREK SAOS KEJU LUMER", None),
    (552, "PAKET GEPREK LUMER", None),
    (553, "PAKET GEPREK LUMER", None),
    (543, "GEPREK SMOKEY BBQ", None),
    (544, "GEPREK SMOKEY BBQ", None),
    (550, "PKG SMOKEY BBQ", None),
    (551, "PKG SMOKEY BBQ", None),
    (554, "PKG GEPREK BAKAR ANDALAN", None),
    (561, "PAKET KULIT CRISPY", None),
    (563, "GEPREK SAMBAL RICA MANADO", ("SAMBAL RICA MANADO", "SAMBAL TOMAT MALINO", None)),
    (570, "PAKET AYAM CRISPY PAHA BAWAH", None),
    (573, "PAKET MEVVAH BERDUA", None),
    (580, "LEMON TEA", ("BUBUK LEMON TEA", "BUBUK BLACKCURRENT", None)),
    (560, "GEPREK SAOS KEJU LUMER", ("[BUBUK KEJU, AIR GALON]", "KEJU MOZARELLA", 50)),
]

aug = POSm.search([("date_order", ">=", AUG_FROM), ("date_order", "<", AUG_TO)])
sold = Counter()
for o in aug:
    for l in o.lines:
        sold[l.product_id.id] += l.qty

say = []
say.append("# Tabel Mapping Resep BOM — 26 Menu Tanpa BOM")
say.append("")
say.append("> Sumber: clone BOM phantom yang sudah ada (70 BOM existing TIDAK diubah).")
say.append("> Menu 539 TERONG CRISPY DIHAPUS (keputusan Anda), jadi tidak masuk tabel.")
say.append("")
say.append("| # | Menu (id) | qty Agu | Sumber clone | Penggantian bahan |")
say.append("|---|---|---|---|---|")

detail = []
for pid, src_name, repl in MAP:
    p = Prod.browse(pid)
    src = Prod.search([("name", "=", src_name)], limit=1)
    sb = Bom.search([("product_tmpl_id", "=", src.product_tmpl_id.id)], limit=1)
    if not src or not sb:
        say.append("| %d | %s | %g | **SUMBER TIDAK DITEMUKAN: %s** | %s |" % (
            len(detail) + 1, p.display_name, sold.get(pid, 0), src_name, repl or "-"))
        continue
    if repl:
        rtxt = "%s \u2192 %s" % (repl[0], repl[1]) + (" \u00d7%g" % repl[2] if repl[2] else " (qty sama)")
    else:
        rtxt = "\u2014"
    say.append("| %d | %s (id %s) | %g | %s (id %s) | %s |" % (
        len(detail) + 1, p.display_name[:44], pid, sold.get(pid, 0),
        src_name[:40], src.id, rtxt))
    detail.append((p, src, sb, repl))

say.append("")
say.append("## Rincian baris resep per menu")
say.append("")
for p, src, sb, repl in detail:
    say.append("### %s  (id %s, Rp %s)" % (
        p.display_name, p.id, "{:,.0f}".format(p.list_price or 0)))
    say.append("*clone dari* **%s** (id %s)" % (src.display_name, src.id))
    say.append("")
    say.append("| Bahan | Qty | UoM |")
    say.append("|---|---|---|")
    dropped = set()
    for l in sb.bom_line_ids:
        nm = l.product_id.display_name
        qty, uom = l.product_qty, l.product_uom_id.name
        if repl:
            old, new, newqty = repl
            if old.startswith("["):
                drop = {x.strip() for x in old.strip("[]").split(",")}
                if nm in drop:
                    dropped.add(nm)
                    continue
            elif nm == old:
                nm = new
                if newqty:
                    qty = newqty
                # uom ikut produk baru
                uom = Prod.search([("name", "=", new)], limit=1).uom_id.name or uom
        say.append("| %s | %g | %s |" % (nm, qty, uom))
    if repl and repl[2] and repl[1] not in [x for x in []]:
        say.append("| **+ %s (baru)** | %g | %s |" % (
            repl[1], repl[2],
            Prod.search([("name", "=", repl[1])], limit=1).uom_id.name or "-"))
    if dropped:
        say.append("| ~~%s~~ (dihapus) | \u2014 | \u2014 |" % ", ".join(sorted(dropped)))
    say.append("")

txt = "\n".join(say)
with open("BOM_MAPPING_REVIEW.md", "w") as f:
    f.write(txt + "\n")
print("=" * 78)
print("2. FILE DITULIS: BOM_MAPPING_REVIEW.md  (%d baris)" % (len(say) + 1))
print(txt[:2600])
env.cr.rollback()
