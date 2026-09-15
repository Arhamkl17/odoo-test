"""install_dashboard_module.py — install/upgrade geprekyukss_dashboard + smoke test data layer.

Jalankan (READ-ONLY terhadap data bisnis; hanya update registry modul):
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 --db_user odoo --db_password odoo" < scripts/install_dashboard_module.py
"""
env  # noqa: F821

# Rescan addons_path agar modul baru terdeteksi di registry yang sudah jalan
n_added = env["ir.module.module"].update_list()
print("update_list: added =", n_added)

mod = env["ir.module.module"].search([("name", "=", "geprekyukss_dashboard")])
print("module found:", bool(mod), "| state:", mod.state if mod else "-")
if mod:
    mod.button_immediate_install()
    env.cr.commit()
    print("installed. state:", mod.state)

    # pastikan menu & action terdaftar
    act = env["ir.actions.client"].search([("tag", "=", "geprekyukss_dashboard.main")])
    print("client action:", act.name if act else "TIDAK ADA")
    menu = env["ir.ui.menu"].search([("name", "=", "Dashboard Keuangan")])
    print("menu:", menu.mapped("name"), "| parent:", menu.mapped("parent_id.name"))

    # smoke test data layer
    Data = env["geprekyukss.dashboard.data"]
    aug = Data.get_dashboard_data("2026-08-01", "2026-08-31")
    print("Agustus:", aug)
    jul = Data.get_dashboard_data("2026-07-01", "2026-07-31")
    print("Juli:", jul)
    env.cr.rollback()
    print("SMOKE TEST SELESAI.")
else:
    print("MODUL TIDAK TERDETEKSI — cek addons_path & permission file")
