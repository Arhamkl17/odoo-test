# -*- coding: utf-8 -*-
"""
juni_juli_61_agent_products.py — menu yang ADA DI SISTEM tapi TIDAK ADA DI EKSPOR KLIEN.

Basis: import_data/csv/05_products_with_id.csv (ekspor product.template klien).
Ini mendeteksi produk buatan agent (bukan data klien).

  su odoo ... < scripts/juni_juli_61_agent_products.py
"""
import csv
import io

CSV_PATH = "import_data/csv/05_products_with_id.csv"
Prod = env["product.product"]
cr = env.cr
say = lambda m="": print(m)

client = {}          # nama upper -> baris
with io.open(CSV_PATH, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        nm = (r.get("Nama") or "").strip()
        if nm:
            client[nm.upper()] = r

say("=" * 116)
say("A. PRODUK MENU POS DI SISTEM vs EKSPOR PRODUK KLIEN")
say("=" * 116)
say("baris di ekspor klien : %d" % len(client))

recs = []
for p in Prod.search([("sale_ok", "=", True), ("available_in_pos", "=", True)]):
    tmpl = p.product_tmpl_id
    nm = (tmpl.display_name or "").upper().strip()
    recs.append((p.id, tmpl.id, tmpl.display_name or "", nm))

miss = [x for x in recs if x[3] not in client]
say("menu POS di sistem   : %d" % len(recs))
say("menu POS yang TIDAK ada di ekspor klien: %d" % len(miss))
say("")
say("%-5s %-6s %s" % ("pid", "tmpl", "nama di sistem"))
say("-" * 116)
for pid, tid, nm, _ in sorted(miss, key=lambda x: x[2]):
    say("%-5d %-6d %s" % (pid, tid, nm))

say("")
say("=" * 116)
say("B. PRODUK NON-POS / BAHAN: apa mereka ada di ekspor klien?")
say("=" * 116)
allp = Prod.search([])
n_no = 0
contoh = []
for p in allp:
    nm = (p.product_tmpl_id.display_name or "").upper().strip()
    if nm and nm not in client:
        n_no += 1
        if len(contoh) < 30:
            contoh.append((p.id, p.product_tmpl_id.display_name or "", p.type,
                           p.product_tmpl_id.categ_id.complete_name))
say("total produk di sistem: %d | tidak ada di ekspor klien: %d" % (len(allp), n_no))
say("")
say("%-5s %-52s %-12s %s" % ("pid", "nama", "tipe", "kategori"))
say("-" * 116)
for pid, nm, tp, cat in contoh:
    say("%-5s %-52s %-12s %s" % (pid, nm[:52], tp, (cat or "")[:40]))

say("")
say("=" * 116)
say("C. EKSPOR KLIEN YANG TIDAK ADA DI SISTEM (kebalikannya)")
say("=" * 116)
sys_names = set((p.product_tmpl_id.display_name or "").upper().strip() for p in allp)
n = 0
for nm in sorted(client):
    if nm not in sys_names:
        n += 1
        if n <= 40:
            r = client[nm]
            say("   %-62s harga jual %-6s satuan %s" % (
                nm[:62], (r.get("Harga Jual") or "").strip(), (r.get("Unit Pembelian") or "").strip()))
say("   ... total %d nama klien tidak ada di sistem" % n)
env.cr.rollback()
