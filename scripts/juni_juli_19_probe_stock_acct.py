# -*- coding: utf-8 -*-
"""
juni_juli_19_probe_stock_acct.py — cek ke akun mana konsumsi stok akan jatuh.

READ-ONLY (semua dibatalkan). Membuat 1 stock.move konsumsi di savepoint, lalu
mencetak JE yang lahir dari valuasi otomatis Odoo 19.
"""
cr = env.cr
Prod = env["product.product"]
Loc = env["stock.location"]
MV = env["stock.move"]
say = lambda m="": print(m)

say("=" * 100)
say("A. AKUN STOK per kategori (via ORM)")
say("%-26s %-9s %-10s | %-18s %-18s %-18s %-7s" % (
    "kategori", "cost", "valuation", "valuasi", "variasi", "prod_cost", "jurnal"))
for pc in env["product.category"].browse([5, 6, 7, 8, 10, 11]).exists():
    def _c(f):
        v = pc[f]
        return (v.display_name or "-")[:18] if v else "-"
    say("%-26s %-9s %-10s | %-18s %-18s %-18s %-7s" % (
        (pc.complete_name or "")[:26], (pc.property_cost_method or "-"),
        (pc.property_valuation or "-"), _c("property_stock_valuation_account_id"),
        _c("account_stock_variation_id"),
        _c("property_stock_account_production_cost_id"),
        (pc.property_stock_journal.code if pc.property_stock_journal else "-")))

say("")
say("B. LOKASI (internal & virtual) 10 pertama")
for l in Loc.search([], limit=25):
    say("   %-6s %-42s usage=%-12s scrap=%s" % (
        l.id, (l.complete_name or "")[:42], l.usage, getattr(l, "scrap_location", "-")))

say("")
say("C. PROBE: 1 stock move konsumsi (savepoint, dibatalkan)")
stok = Loc.search([("usage", "=", "internal")], limit=1)
virt = Loc.search([("usage", "=", "inventory")], limit=1) or \
    Loc.search([("usage", "=", "production")], limit=1) or Loc.search([("usage", "=", "customer")], limit=1)
say("   lokasi asal=%s (%s) | tujuan=%s (%s)" % (
    stok.id, stok.complete_name, virt.id, virt.complete_name))

comp = Prod.search([("default_code", "=", "ES KRISTAL")], limit=1) or \
    Prod.search([("categ_id", "in", (5, 6, 7)), ("type", "=", "consu")], limit=1)
say("   komponen uji: %s (id=%s) std=%s categ=%s valuasi=%s" % (
    comp.display_name, comp.id, comp.standard_price, comp.categ_id.complete_name,
    comp.categ_id.property_valuation))
say("   qty on hand (quant): %s" % getattr(comp, "qty_available", "n/a"))

before = env["account.move"].search_count([])
say("   account.move sebelum: %d" % before)
try:
    mv = MV.create({
        "product_id": comp.id,
        "product_uom_qty": 1000,
        "product_uom": comp.uom_id.id,
        "location_id": stok.id,
        "location_dest_id": virt.id,
        "origin": "PROBE",
    })
    mv._action_confirm()
    mv._action_assign()
    mv.quantity = 1000
    mv.picked = True
    mv._action_done()
    env.flush_all()
    say("   move state=%s | value=%s | remaining_value=%s" % (
        mv.state, getattr(mv, "value", "n/a"), getattr(mv, "remaining_value", "n/a")))
    for m in env["account.move"].search([("id", ">", 0)], order="id desc", limit=3):
        say("   JE %s | %s | %s | ref=%s" % (m.name, m.journal_id.code, m.date, m.ref))
        for l in m.line_ids:
            say("        %-12s %-44s D%16s K%16s" % (
                l.account_id.code, (l.name or "")[:44],
                "{:,.2f}".format(l.debit), "{:,.2f}".format(l.credit)))
except Exception as e:
    say("   !! PROBE GAGAL: %s" % repr(e)[:300])

env.cr.rollback()
say("")
say("D. stok.move Agustus: picking/lokasi apa yang dipakai backfill?")
cr.execute("""
    SELECT COALESCE(sm.reference,'-') ref, ls.usage, ld.usage, COUNT(*),
           SUM(sm.quantity), COUNT(sm.picking_id)
      FROM stock_move sm
      LEFT JOIN stock_location ls ON ls.id = sm.location_id
      LEFT JOIN stock_location ld ON ld.id = sm.location_dest_id
     WHERE sm.date >= '2026-08-01' AND sm.date < '2026-09-01'
     GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 10""")
for r in cr.fetchall():
    say("   ref=%-24s %-12s -> %-12s n=%-6s qty=%-14s picking=%s" % (
        (r[0] or "")[:24], r[1], r[2], r[3], "{:,.1f}".format(r[4] or 0), r[5]))
say("=" * 100)
