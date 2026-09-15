"""test_assets_bundle.py — kompilasi web.assets_backend untuk menangkap error JS/SCSS. READ-ONLY terhadap data."""
env  # noqa: F821

import re

# pastikan modul ter-upgrade (JS/XML/SCSS terbaru)
env["ir.module.module"].search([("name", "=", "geprekyukss_dashboard")]).button_immediate_upgrade()
env.cr.commit()

IrQweb = env["ir.qweb"]
try:
    nodes = IrQweb._get_asset_nodes("web.assets_backend")
    print("ASSET NODES OK —", len(nodes), "elemen")
except Exception as e:
    print("_get_asset_nodes ERR:", type(e).__name__, e)
    # fallback API alternatif
    try:
        files = env["ir.asset"]._get_asset_paths("web.assets_backend")
        hit = [f for f in files if "geprekyukss_dashboard" in str(f)]
        print("files modul di bundle:", len(hit))
        for f in hit:
            print("  ", f)
    except Exception as e2:
        print("fallback ERR:", type(e2).__name__, e2)

# cek hasil kompilasi scss: cari attachment asset
att = env["ir.attachment"].search([("name", "ilike", "assets_backend"), ("mimetype", "in", ["text/css", "text/javascript", "application/javascript"])], limit=5)
print("sample compiled attachments:", [(a.name[:60], a.mimetype) for a in att])

env.cr.rollback()
print("ASSET TEST SELESAI.")
