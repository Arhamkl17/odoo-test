# -*- coding: utf-8 -*-
"""juni_juli_80_recon_pricelist.py — recon model pricelist & pos.config (READ-ONLY)."""
Config = env["pos.config"]
PL = env["product.pricelist"]
say = lambda m="": print(m)

say("=" * 110)
say("MODEL product.pricelist — field yang bisa diisi")
say("=" * 110)
f = PL.fields_get()
for k in ["name", "currency_id", "company_id", "active", "sequence", "item_ids", "country_group_ids"]:
    if k in f:
        say("   %-18s %-14s required=%s" % (k, f[k].get("type"), f[k].get("required")))

say("")
say("MODEL product.pricelist.item")
it = env["product.pricelist.item"].fields_get()
for k in ["pricelist_id", "applied_on", "product_tmpl_id", "product_id", "categ_id",
          "min_quantity", "compute_price", "fixed_price", "percent_price", "base", "date_start"]:
    if k in it:
        say("   %-18s %-14s required=%s  selection=%s" % (
            k, it[k].get("type"), it[k].get("required"),
            (it[k].get("selection") or "")[:80] if it[k].get("selection") else ""))

say("")
say("=" * 110)
say("POS CONFIG yang ada")
say("=" * 110)
for c in Config.search([]):
    say("")
    say("id=%-4s %s" % (c.id, c.name))
    for k in ["journal_id", "invoice_journal_id", "picking_type_id", "sequence_id",
              "payment_method_ids", "pricelist_id", "company_id", "limit_categories",
              "iface_tax_included", "module_pos_restaurant", "is_restaurant", "warehouse_id"]:
        if k in c._fields:
            v = getattr(c, k)
            try:
                val = ", ".join(v.mapped("display_name")) if hasattr(v, "ids") else v
            except Exception:
                val = v
            say("      %-24s = %s" % (k, val))

say("")
say("=" * 110)
say("payment method yang dipakai sesi Juni-Agustus")
say("=" * 110)
cr = env.cr
cr.execute("""
    SELECT pm.id, pm.name, pm.type, pm.journal_id, count(*)
      FROM pos_payment pp
      JOIN pos_payment_method pm ON pm.id = pp.payment_method_id
      JOIN pos_order po ON po.id = pp.pos_order_id
     WHERE po.date_order >= '2026-06-01' AND po.date_order < '2026-09-01'
     GROUP BY 1,2,3,4 ORDER BY 5 DESC""")
for pid, nm, ty, jr, n in cr.fetchall():
    say("   id=%-4s %-28s type=%-12s journal=%s  dipakai %d x" % (pid, nm, ty, jr, n))

env.cr.rollback()
