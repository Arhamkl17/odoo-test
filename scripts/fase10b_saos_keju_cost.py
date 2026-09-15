# -*- coding: utf-8 -*-
# fase10b_saos_keju_cost.py — Fase 10b: isi cost SAOS KEJU (id 578) dari BOM kit-nya.
#
# Dasar (audit cek_cost_uom_detail2, 11 Sep 2026): SAOS KEJU satu-satunya produk
# ber-BOM yang tidak pernah punya cost sejak awal (snapshot pre-Fase-1 = None),
# jadi laporan margin menu membacanya Rp 0. Kit BOM id 11:
#   AIR GALON 15 MIL (cost 1.19003/MIL) + BUBUK KEJU 8 GRM (cost 150/GRM)
#   => X = 15*1.19 + 8*150 = 19.05 per PORSI (dihitung fresh, bukan hardcoded).
# Non-storable: write standard_price (jsonb company-dependent) — pola sama dgn Fase 8.
# Dry-run default; RUN=1 (env) commit. Idempotent. Tanpa env.cr.rollback() mid-run.
import json, os

RUN = os.environ.get('RUN') == '1'
BACKUP = "backup_cost_saos_keju_pre_fase10b.json"
TARGET = 578  # product.product SAOS KEJU
BOM = 11

def p(*a):
    print(*a)

def rows(sql, params=None):
    env.cr.execute(sql, params or ())
    return env.cr.fetchall()

p(f"=== Fase 10b — Cost SAOS KEJU dari kit BOM ({'RUN=1 COMMIT' if RUN else 'DRY-RUN'}) ===")

prod = env['product.product'].browse(TARGET)
p(f"Target : {prod.display_name} | uom={prod.uom_id.name} | storable={prod.is_storable} | cost skrg={prod.standard_price!r}")

# hitung X fresh dari BOM + cost komponen live
bom = env['mrp.bom'].browse(BOM)
p(f"BOM    : {bom.display_name}")
X = 0.0
for l in bom.bom_line_ids:
    c = l.product_id.standard_price or 0.0
    sub = l.product_qty * c
    X += sub
    p(f"   {l.product_id.display_name[:24]:<24} {l.product_qty} {l.product_uom_id.name} x {c:,.4f} = {sub:,.4f}")
p(f"X (cost/kit) = {X:,.6f}  per {prod.uom_id.name} | harga jual {prod.list_price:,.0f} -> margin {(1 - X/prod.list_price)*100:.1f}%")

cur = prod.standard_price or 0.0
if abs(cur - X) < 1e-6:
    p("\nCost sudah sama dgn X — idempotent, tidak ada yang diubah.")
elif not RUN:
    p(f"\nDRY-RUN — akan set standard_price {cur!r} -> {X:.6f}. Jalankan: RUN=1 fase10b_saos_keju_cost.py")
else:
    with open(BACKUP, "w") as f:
        json.dump([{"product_id": TARGET, "name": prod.display_name,
                    "old_standard_price": prod.standard_price, "new": X,
                    "basis": f"kit BOM {BOM} (AIR GALON 15 MIL + BUBUK KEJU 8 GRM)"}],
                  f, indent=1, ensure_ascii=False)
    p(f"Backup -> {BACKUP}")
    prod.write({"standard_price": X})
    env.cr.commit()
    # verifikasi
    v = env['product.product'].browse(TARGET).standard_price
    p(f"COMMIT: standard_price = {v!r}  {'OK' if abs(v - X) < 1e-6 else 'BEDA!'}")

# invariant: TB
tb = float(rows("SELECT COALESCE(SUM(l.debit),0)-COALESCE(SUM(l.credit),0) FROM account_move_line l JOIN account_move m ON m.id=l.move_id WHERE m.state='posted'")[0][0])
p(f"TB diff: {tb:,.2f}  {'OK' if abs(tb) < 0.01 else 'BEDA!'}")
p("DONE fase10b_saos_keju_cost.")
