# -*- coding: utf-8 -*-
"""juni_juli_17_recon_inventory.py — setup valuasi persediaan & jejak Agustus (READ-ONLY)."""
cr = env.cr
say = lambda m="": print(m)

say("=" * 100)
say("A. KATEGORI PRODUK — cost method & valuation")
cr.execute("""
    SELECT pc.id, pc.complete_name, pc.property_cost_method, pc.property_valuation,
           COUNT(pt.id) AS n_produk
      FROM product_category pc LEFT JOIN product_template pt ON pt.categ_id = pc.id
     GROUP BY 1,2,3,4 ORDER BY 1""")
say("%-5s %-42s %-14s %-16s %8s" % ("id", "kategori", "cost_method", "valuation", "produk"))
for r in cr.fetchall():
    say("%-5s %-42s %-14s %-16s %8s" % (r[0], (r[1] or "")[:42], r[2], r[3], r[4]))

say("")
say("B. STOCK MOVE Agustus — dari mana & status")
cr.execute("""
    SELECT sm.state, COALESCE(sm.reference, '-'), COUNT(*), SUM(sm.quantity),
           COUNT(sm.picking_id), COUNT(sm.stock_valuation_layer_ids)
      FROM stock_move sm
      LEFT JOIN stock_picking sp ON sp.id = sm.picking_id
     WHERE sm.date >= '2026-08-01' AND sm.date < '2026-09-01'
     GROUP BY 1,2 ORDER BY 3 DESC LIMIT 12""")
say("%-9s %-28s %8s %14s %10s %10s" % ("state", "reference", "n", "qty", "picking", "SVL"))
for r in cr.fetchall():
    say("%-9s %-28s %8s %14s %10s %10s" % (r[0], (r[1] or "")[:28], r[2],
                                            "{:,.2f}".format(r[3] or 0), r[4], r[5]))

say("")
say("C. STOCK VALUATION LAYER (Agustus)")
cr.execute("""
    SELECT aj.code, COUNT(*), SUM(svl.value), SUM(svl.quantity)
      FROM stock_valuation_layer svl
      LEFT JOIN account_journal aj ON aj.id = svl.account_journal_id
      LEFT JOIN stock_move sm ON sm.id = svl.stock_move_id
     WHERE sm.date >= '2026-08-01' AND sm.date < '2026-09-01'
     GROUP BY 1 ORDER BY 2 DESC LIMIT 10""")
rows_ = cr.fetchall()
if not rows_:
    say("   (tidak ada stock_valuation_layer untuk Agustus)")
for r in rows_:
    say("   jurnal=%-6s n=%-6d value=%18s qty=%14s" % (
        r[0] or "-", r[1], "{:,.2f}".format(r[2] or 0), "{:,.2f}".format(r[3] or 0)))

say("")
say("D. JE HPP Agustus — akun & nilai per jurnal (yang akan diganti)")
cr.execute("""
    SELECT aj.code, aa.code_store->>'1', COUNT(*), SUM(aml.balance)
      FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
      JOIN account_journal aj ON aj.id = am.journal_id
      JOIN account_account aa ON aa.id = aml.account_id
     WHERE am.state='posted' AND aa.account_type='expense_direct_cost'
       AND am.date >= '2026-08-01' AND am.date < '2026-09-01'
     GROUP BY 1,2 ORDER BY 4 DESC""")
for r in cr.fetchall():
    say("   %-6s %-10s n=%-5d %18s" % (r[0], r[1], r[2], "{:,.2f}".format(r[3] or 0)))

say("")
say("E. HUTANG USAHA Agustus (sisi kredit bill TAGIH)")
cr.execute("""
    SELECT aa.code_store->>'1', COALESCE(aa.name->>'en_US', aa.name->>'1'), SUM(aml.balance)
      FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
      JOIN account_account aa ON aa.id = aml.account_id
     WHERE am.state='posted' AND aa.account_type='liability_payable'
     GROUP BY 1,2 ORDER BY 3""")
for r in cr.fetchall():
    say("   %-12s %-44s %18s" % (r[0], (r[1] or "")[:44], "{:,.2f}".format(r[2] or 0)))

say("")
say("F. QUANT vs GL persediaan (31 Agu)")
cr.execute("""
    SELECT aa.code_store->>'1', COALESCE(aa.name->>'en_US', aa.name->>'1'), SUM(aml.balance)
      FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
      JOIN account_account aa ON aa.id = aml.account_id
     WHERE am.state='posted' AND am.date <= '2026-08-31'
       AND aa.account_type='asset_current'
     GROUP BY 1,2 HAVING SUM(aml.balance) <> 0 ORDER BY 1""")
for r in cr.fetchall():
    say("   %-12s %-44s %18s" % (r[0], (r[1] or "")[:44], "{:,.2f}".format(r[2] or 0)))
cr.execute("""
    SELECT COUNT(*), SUM(sq.quantity * pp.standard_price)
      FROM stock_quant sq JOIN product_product pp ON pp.id = sq.product_id
     WHERE sq.location_id IN (SELECT id FROM stock_location WHERE usage='internal')""")
r = cr.fetchone()
say("   quant internal: %s baris | nilai @standard_price = %s" % (r[0], "{:,.2f}".format(r[1] or 0)))

say("")
say("G. BIAYA KOMPONEN (5 teratas menurut pemakaian Agustus)")
cr.execute("""
    SELECT pt.default_code, COALESCE(pt.name->>'en_US', pt.name->>'1'),
           pp.standard_price, SUM(bol.product_qty) AS bom_qty
      FROM mrp_bom_line bol JOIN mrp_bom bo ON bo.id = bol.bom_id
      JOIN product_product pp ON pp.id = bol.product_id
      JOIN product_template pt ON pt.id = pp.product_tmpl_id
     GROUP BY 1,2,3 ORDER BY 2 LIMIT 8""")
say("%-14s %-40s %14s" % ("kode", "komponen", "standard_price"))
for r in cr.fetchall():
    say("%-14s %-40s %14s" % (r[0] or "-", (r[1] or "")[:40], "{:,.2f}".format(r[2] or 0)))
say("=" * 100)
env.cr.rollback()
