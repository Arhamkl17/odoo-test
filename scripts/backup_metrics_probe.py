# -*- coding: utf-8 -*-
"""Probe metrik baseline — dijalankan lewat `odoo shell` (baca-saja, tanpa menulis).

Dipakai oleh `scripts/backup_full_system.sh` (merekam baseline) dan
`scripts/restore_full_system.sh` (membandingkan hasil restore dengan baseline).

Output: satu baris per metrik, format `METRIC|<kunci>|<nilai>` supaya mudah
di-diff. Kunci & nilai dipilih agar **stabil** (tidak berubah oleh restore):
tidak ada id, tanggal buat, atau data volatil lain.

Cara jalankan (pola resmi proyek):
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db \
    --db_port 5432 --db_user odoo --db_password odoo --log-level=warn" \
    < scripts/backup_metrics_probe.py
"""
from decimal import Decimal

env = env  # noqa: F821  (disediakan odoo shell)
D = env["geprekyukss.dashboard.data"]
Aml = env["account.move.line"]
Move = env["account.move"]
Account = env["account.account"].with_context(active_test=False)


def out(key, value):
    print("METRIC|%s|%s" % (key, value))


def n(value):
    """Angka 2 desimal, gaya stabil untuk diff."""
    return "%.2f" % float(value or 0.0)


def pl_accounts():
    accs = Account.search([("code", "=like", "5101%")])
    return accs


def sum_aml(dom):
    tot = 0.0
    for _acc, debit, credit in Aml._read_group(dom, ["account_id"], ["debit:sum", "credit:sum"]):
        tot += (debit or 0.0) - (credit or 0.0)
    return tot


def inv_accounts():
    accs = Account.search(["|", ("code", "=like", "1103%"), ("code", "=", "11300180")])
    return accs


base_mod = env["ir.module.module"].sudo().search([("name", "=", "base")], limit=1)
out("odoo_version", base_mod.latest_version or "")
out("company", env.company.name)
out("db_name", env.cr.dbname)

# --- POS / transaksi -------------------------------------------------
out("pos_orders", env["pos.order"].search_count([]))
out("pos_orders_done", env["pos.order"].search_count([("state", "=", "done")]))
out("pos_revenue", n(sum(env["pos.order"].search([("state", "=", "done")]).mapped("amount_total"))))
out("pos_order_lines", env["pos.order.line"].search_count([]))
out("pos_sessions", env["pos.session"].search_count([]))
out("pos_sessions_closed", env["pos.session"].search_count([("state", "=", "closed")]))
out("pos_payment_methods", env["pos.payment.method"].search_count([]))

# --- Akuntansi -------------------------------------------------------
posted = [("parent_state", "=", "posted")]
out("account_moves_posted", Move.search_count([("state", "=", "posted")]))
out("account_move_lines", Aml.search_count(posted))
out("entry_number_filled", Aml.search_count(posted + [("entry_number", "!=", False)]))
out("tb_debit", n(sum(Aml.search(posted).mapped("debit"))))
out("tb_credit", n(sum(Aml.search(posted).mapped("credit"))))
out("fiscalyear_lock_date", str(env.company.fiscalyear_lock_date or ""))
JN = env["account.journal"].with_context(active_test=False)
out("journals", JN.search_count([]))
out("journals_active", JN.search_count([("active", "=", True)]))
out("accounts_total", Account.search_count([]))
out("accounts_used", len(set(Aml.search(posted).mapped("account_id").ids)))

# HPP (5101.xx) per bulan + total
hpp_accs = pl_accounts()
hpp = lambda d1, d2: sum_aml(posted + [("account_id", "in", hpp_accs.ids),
                                       ("date", ">=", d1), ("date", "<=", d2)])
out("hpp_jun_2026", n(hpp("2026-06-01", "2026-06-30")))
out("hpp_jul_2026", n(hpp("2026-07-01", "2026-07-31")))
out("hpp_aug_2026", n(hpp("2026-08-01", "2026-08-31")))
out("hpp_total", n(sum_aml(posted + [("account_id", "in", hpp_accs.ids)])))

# Persediaan: GL (1103.xx + 11300180) vs sub-ledger stok
inv_accs = inv_accounts()
out("inventory_gl", n(sum_aml(posted + [("account_id", "in", inv_accs.ids)])))
quants = env["stock.quant"].search([])
out("inventory_quant_value", n(sum(quants.mapped("value"))))
out("stock_quant_rows", len(quants))

# --- Laporan (sumber sama dgn dashboard/tab Neraca) -------------------
bal = D.get_dashboard_data("2026-08-01", "2026-08-31", None)["finance"]["balance"]
out("total_assets", n(bal["total_assets"]))
out("liabilities", n(bal["liabilities"]))
out("equity", n(bal["equity"]))
out("net_income_ytd", n(bal["net_income_ytd"]))

# --- Master data ------------------------------------------------------
PT = env["product.template"].with_context(active_test=False)
PP = env["product.product"].with_context(active_test=False)
out("product_templates", PT.search_count([]))
out("product_templates_active", PT.search_count([("active", "=", True)]))
out("products_available_in_pos", PT.search_count([("available_in_pos", "=", True)]))
out("product_variants", PP.search_count([]))
out("uom_uoms", env["uom.uom"].search_count([]))
out("uom_uoms_all", env["uom.uom"].with_context(active_test=False).search_count([]))
out("product_categories", env["product.category"].search_count([]))
out("boms", env["mrp.bom"].search_count([]))
out("bom_lines", env["mrp.bom.line"].search_count([]))
out("pricelists", env["product.pricelist"].search_count([]))
out("pricelist_items", env["product.pricelist.item"].search_count([]))
out("supplierinfo_lines", env["product.supplierinfo"].search_count([]))
out("supplierinfo_vendors", len(set(env["product.supplierinfo"].search([]).mapped("partner_id").ids)))
RP = env["res.partner"].with_context(active_test=False)
out("partners", RP.search_count([]))
out("partners_active", RP.search_count([("active", "=", True)]))
out("stock_moves", env["stock.move"].search_count([]))
out("stock_moves_done", env["stock.move"].search_count([("state", "=", "done")]))
out("stock_pickings", env["stock.picking"].search_count([]))
out("purchase_orders", env["purchase.order"].search_count([]))
out("stock_locations", env["stock.location"].search_count([]))
out("warehouses", env["stock.warehouse"].search_count([]))
PC = env["pos.config"].with_context(active_test=False)
out("pos_configs", PC.search_count([]))
out("pos_configs_active", PC.search_count([("active", "=", True)]))
out("taxes", env["account.tax"].search_count([]))

# --- Aset tetap (register OCA account_asset_management, F4 15 Sep 2026) ---
# Metrik ini menjaga register + jadwal penyusutan ikut terbukti utuh saat restore.
try:
    assets = env["account.asset"].with_context(active_test=False).search([])
    out("assets_registered", len(assets))
    out("assets_purchase_value", n(sum(assets.mapped("purchase_value"))))
    out("assets_depreciated_value", n(sum(assets.mapped("value_depreciated"))))
    out("assets_residual_value", n(sum(assets.mapped("value_residual"))))
    out("assets_depreciation_lines", env["account.asset.line"].search_count([]))
    out("assets_depreciation_profiles", env["account.asset.profile"].search_count([]))
except KeyError:
    out("assets_registered", "n/a (modul account_asset_management tidak terpasang)")

# --- Modul terpasang --------------------------------------------------
IM = env["ir.module.module"].sudo()
out("modules_installed", IM.search_count([("state", "=", "installed")]))
out("modules_to_upgrade", IM.search_count([("state", "=", "to upgrade")]))
out("modules_non_odoo_author", IM.search_count([
    ("state", "=", "installed"), ("author", "not ilike", "Odoo")]))

# Modul kustom proyek — wajib "installed" agar dashboard & POS kustom hidup
custom = IM.search([("name", "in", ["geprekyukss_dashboard", "geprekyukss_pos"])])
out("custom_modules_state", ",".join(sorted("%s=%s" % (m.name, m.state) for m in custom)))

print("PROBE_DONE")
