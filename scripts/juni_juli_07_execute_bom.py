# -*- coding: utf-8 -*-
"""
juni_juli_07_execute_bom.py — P5.7: buat 26 BOM phantom utk menu yang belum punya resep.

Sumber mapping: BOM_MAPPING_REVIEW.md (sudah disetujui).
Cara kerja: clone BOM phantom yang sudah ada, lalu terapkan penggantian bahan
seperlunya. 70 BOM existing TIDAK disentuh.

  RUN=1   eksekusi  (default: dry-run)

  su odoo -s /bin/bash -c "cd /workspaces/odoo-test && RUN=1 odoo shell -d Test1 \\
      --no-http --db_host db --db_port 5432 --db_user odoo --db_password odoo" \\
      < scripts/juni_juli_07_execute_bom.py
"""
import os

RUN = os.environ.get("RUN") == "1"
Prod = env["product.product"]
Bom = env["mrp.bom"]
BomLine = env["mrp.bom.line"]

# (menu_id, nama menu, nama sumber BOM, penggantian)
# penggantian = (old_name, new_name, new_qty|None)  |  ("[drop1, drop2]", add_name, add_qty)
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


def say(m=""):
    print(m)


say("=" * 78)
say("P5.7 — BUAT 26 BOM   |   RUN=%s" % RUN)
say("=" * 78)
say("BOM sebelum: %d header, %d baris" % (len(Bom.search([])), BomLine.search_count([])))

created, skipped, errors = [], [], []
for pid, src_name, repl in MAP:
    p = Prod.browse(pid)
    if Bom.search_count([("product_tmpl_id", "=", p.product_tmpl_id.id)]):
        skipped.append(p.display_name)
        continue
    src = Prod.search([("name", "=", src_name)], limit=1)
    if not src:
        errors.append("sumber tak ada: %s (utk %s)" % (src_name, p.display_name))
        continue
    sb = Bom.search([("product_tmpl_id", "=", src.product_tmpl_id.id)], limit=1)
    if not sb:
        errors.append("BOM sumber tak ada: %s (utk %s)" % (src_name, p.display_name))
        continue

    vals, dropped = [], []
    for l in sb.bom_line_ids:
        nm = l.product_id.display_name
        prod, qty = l.product_id, l.product_qty
        if repl:
            old, new, newqty = repl
            if old.startswith("["):
                drop = {x.strip() for x in old.strip("[]").split(",")}
                if nm in drop:
                    dropped.append(nm)
                    continue
            elif nm == old:
                prod = Prod.search([("name", "=", new)], limit=1)
                if not prod:
                    errors.append("bahan pengganti tak ada: %s" % new)
                    continue
                if newqty:
                    qty = newqty
        line_uom = prod.uom_id
        vals.append((0, 0, {
            "product_id": prod.id,
            "product_qty": qty,
            "product_uom_id": (line_uom or l.product_uom_id).id,
        }))
    if repl and repl[2]:
        add = Prod.search([("name", "=", repl[1])], limit=1)
        if add:
            vals.append((0, 0, {"product_id": add.id, "product_qty": repl[2],
                                "product_uom_id": add.uom_id.id}))

    say("   [%s] %-46s <- %-34s %d baris%s" % (
        "EXEC" if RUN else "DRY ", p.display_name[:46], src_name[:34], len(vals),
        ("  (drop: %s)" % ", ".join(dropped)) if dropped else ""))
    if RUN:
        newb = Bom.create({
            "product_tmpl_id": p.product_tmpl_id.id,
            "product_qty": sb.product_qty or 1.0,
            "product_uom_id": sb.product_uom_id.id,
            "type": sb.type,
            "bom_line_ids": vals,
        })
        created.append((p.display_name, newb.id, len(newb.bom_line_ids)))

say("")
if RUN:
    env.cr.commit()
    env.invalidate_all()
    say("DIBUAT: %d BOM" % len(created))
say("DILEWATI (sudah punya BOM): %d %s" % (len(skipped), skipped[:5]))
say("ERROR: %d" % len(errors))
for e in errors:
    say("   !! " + e)

say("")
say("VERIFIKASI")
say("   BOM sesudah   : %d header, %d baris" % (
    len(Bom.search([])), BomLine.search_count([])))
# cek tidak ada lagi menu terjual tanpa BOM
aug = env["pos.order"].search([("date_order", ">=", "2026-08-01"), ("date_order", "<", "2026-09-01")])
sold = set()
for o in aug:
    for l in o.lines:
        sold.add(l.product_id.id)
nobom = [Prod.browse(i).display_name for i in sold
         if not Bom.search_count([("product_tmpl_id", "=", Prod.browse(i).product_tmpl_id.id)])]
say("   menu terjual tanpa BOM: %d %s" % (len(nobom), nobom))
# spot check
for pid in (560, 580, 563):
    p = Prod.browse(pid)
    b = Bom.search([("product_tmpl_id", "=", p.product_tmpl_id.id)], limit=1)
    say("   %-22s -> %s" % (p.display_name[:22],
        " + ".join("%s x%g" % (l.product_id.name[:24], l.product_qty) for l in b.bom_line_ids)))
say("=" * 78)
