"""get_asset_urls.py — cetak URL bundle web.assets_backend. READ-ONLY."""
env  # noqa: F821

nodes = env["ir.qweb"]._get_asset_nodes("web.assets_backend")
for n in nodes:
    print(str(n))

env.cr.rollback()
