# -*- coding: utf-8 -*-
"""
juni_juli_82_pricelist_config.py — R8 langkah 2 (TIDAK menyentuh ledger).

Membuat:
  A. pricelist `Harga Dasar (Take Away)`  -> item fixed_price = list_price tiap produk POS
  B. pricelist `Harga Dine In`            -> item fixed_price = import_data/pricelist_dinein_plan.csv
  C. tempelkan pricelist A ke 2 POS config yang sudah ada (channel take-away)
  D. buat 2 POS config Dine In baru (Pallangga & Mallengkeri) memakai pricelist B

Idempotent: pricelist dicocokkan lewat nama; config dicocokkan lewat nama.

  dry-run : su odoo ... < scripts/juni_juli_82_pricelist_config.py
  eksekusi: su odoo ... " RUN=1 odoo shell ..." < scripts/juni_juli_82_pricelist_config.py
"""
import csv
import io
import os

RUN = os.environ.get("RUN") == "1"
CSV_PLAN = "import_data/pricelist_dinein_plan.csv"
NAMES = ["Gift Card", "Top-up eWallet", "[TIPS] Tips"]

PL = env["product.pricelist"]
PLI = env["product.pricelist.item"]
Config = env["pos.config"]
Prod = env["product.product"]
TM = env["product.template"]
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

# Produk hantu R1 (§21.1). R1 SUDAH DIJALANKAN 13 Sep 2026 lewat `101_merge_ghost.py`:
# 3 pasangan berharga identik (KOREK · IJO · RICA) digabung — produk hantunya beserta
# item pricelist-nya DIHAPUS. Karena itu daftar ini tetap kosong: tidak ada lagi produk
# hantu yang perlu dikecualikan.
# 3 pasangan sisanya (MEVVAH · KULIT CRISPY · INDOMIE) sengaja TIDAK digabung karena
# harga katalognya berbeda — lihat §21.1 dan §26.
GHOST = []

prods = [p for p in Prod.search([("sale_ok", "=", True), ("available_in_pos", "=", True)])
         if p.product_tmpl_id.list_price > 0]

# harga Dine In dari CSV (kunci = product.product id)
dn = {}
with io.open(CSV_PLAN, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        try:
            dn[int(r["product_id"])] = float(r["harga_dine_in"])
        except (ValueError, KeyError):
            pass
say("CSV rencana Dine In : %d produk" % len(dn))

# ------------------------------------------------------------------ A & B
def ensure_pricelist(name):
    pl = PL.search([("name", "=", name)], limit=1)
    if pl:
        return pl, True
    return PL.create({
        "name": name,
        "currency_id": env.company.currency_id.id,
        "company_id": env.company.id,
        "active": True,
    }), False


def sync_items(pl, price_of, label):
    """item fixed_price per produk; ganti item lama supaya idempotent."""
    olds = PLI.search([("pricelist_id", "=", pl.id)])
    if olds:
        olds.unlink()
    n = 0
    for p in prods:
        if p.product_tmpl_id.id in GHOST or p.id in GHOST:
            continue
        pr = price_of(p)
        if pr is None:
            continue
        PLI.create({
            "pricelist_id": pl.id,
            "applied_on": "1_product",
            "product_tmpl_id": p.product_tmpl_id.id,
            "min_quantity": 0,
            "compute_price": "fixed",
            "fixed_price": pr,
            "base": "list_price",
        })
        n += 1
    say("   %s: %d item (lama dihapus: %d)" % (label, n, len(olds)))
    return n


say("")
say("A/B. PRICELIST")
pl_base, ada_a = ensure_pricelist("Harga Dasar (Take Away)")
pl_dn, ada_b = ensure_pricelist("Harga Dine In")
say("   '%s' -> id=%s %s" % (pl_base.name, pl_base.id, "(sudah ada)" if ada_a else "(BARU)"))
say("   '%s' -> id=%s %s" % (pl_dn.name, pl_dn.id, "(sudah ada)" if ada_b else "(BARU)"))

n_a = sync_items(pl_base, lambda p: float(p.product_tmpl_id.list_price), "Harga Dasar")
n_b = sync_items(pl_dn, lambda p: dn.get(p.id), "Harga Dine In")

# ------------------------------------------------------------------ C
say("")
say("C. TEMPEL PRICELIST DASAR KE CONFIG TAKE-AWAY")
for c in Config.search([("name", "not like", "Dine In")]):
    say("   %-28s pricelist: %s -> %s" % (
        c.name, c.pricelist_id.name or "(kosong)", pl_base.name))
    c.write({"pricelist_id": pl_base.id})

# ------------------------------------------------------------------ D  -> dipindah ke 84 (butuh jurnal kas sendiri)
buat = []
say("")
say("D. CONFIG DINE IN  ->  lihat scripts/juni_juli_84_dinein_config.py")

say("")
say("RINGKASAN: item dasar=%d, item dine-in=%d" % (n_a, n_b))
if not RUN:
    say("")
    say("DRY-RUN — semua perubahan DIBATALKAN.")
    env.cr.rollback()
else:
    env.cr.flush()
    env.cr.commit()
    say("")
    say("COMMITTED.")
say("=" * 112)
