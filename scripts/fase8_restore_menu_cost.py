# -*- coding: utf-8 -*-
# fase8_restore_menu_cost.py — Restore standard_price menu non-storable dari snapshot
# pre-Fase-1 (cost_snapshot_pre_fase1_2026-09-11.json, diekstrak dari
# backup_pre_guide_data1_2026-09-11_fase0.dump).
#
# LATAR BELAKANG
#   Fase 1 (11 Sep) mengubah kategori menu → fifo + real_time. Efek samping Odoo:
#   standard_price (company-dependent jsonb) KOSONG utk semua 106 produk non-storable
#   (99 storable tetap ada). Laporan margin menu (cek_margin_profit.py /
#   laporan_margin_profit.md) jadi tidak bisa hitung cost lagi.
#
# YANG DILAKUKAN
#   - Fill standard_price utk produk NON-STORABLE yang (a) ada di snapshot dengan
#     cost > 0, dan (b) live cost-nya kosong/0. 69 produk.
#   - TIDAK menyentuh: storable (cost sudah ada), produk tanpa cost di snapshot,
#     list_price (harga jual), BoM, stok, jurnal.
#   - Verifikasi: nol storable berubah; 69/69 match snapshot; urutan write menaik.
#
# POLA EKSEKUSI (sama dgn fase1_execute_final.py / fase7_bev_reclass.py):
#   DRY-RUN (default):  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http \
#                         --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
#                         < scripts/fase8_restore_menu_cost.py
#   EKSEKUSI:           RUN=1 su odoo -s /bin/bash -c "odoo shell ..." < scripts/...
#
# NOTE: produk duplikat (nama sama, id beda — mis. KEMASAN VARIAN AYAM 623 vs 634)
# punya cost snapshot berbeda utk tiap id; fill mengikuti snapshot per-id apa adanya
# (quirk pre-existing, bukan dibuat di script ini).
import os
import json

def p(*a):
    print(*a)

RUN = os.environ.get("RUN") == "1"
p(f"MODE: {'EXECUTE (RUN=1)' if RUN else 'DRY-RUN (set RUN=1 utk eksekusi)'}")

SNAP_FILE = "cost_snapshot_pre_fase1_2026-09-11.json"
snap = {r["id"]: r for r in json.load(open(SNAP_FILE))}

Prod = env["product.product"]

def cost_of(pp):
    sp = pp.standard_price  # jsonb dict saat raw; via ORM dict utk company-dependent
    return sp

# ---------- 1. Bangun rencana fill ----------
plan = []          # (pp, new_cost)
skipped_storable = skipped_has_cost = skipped_no_snap = skipped_zero = 0
for pp in Prod.search([("active", "=", True)]):
    rec = snap.get(pp.id)
    new_cost = None
    if rec and rec.get("standard_price"):
        new_cost = rec["standard_price"].get("1")
    if new_cost is None or float(new_cost) <= 0:
        skipped_zero += 1
        continue
    if pp.product_tmpl_id.is_storable:
        skipped_storable += 1
        continue
    live = pp.standard_price
    live_cost = live.get("1") if isinstance(live, dict) else live
    if live_cost not in (None, 0, 0.0):
        skipped_has_cost += 1
        continue
    plan.append((pp, float(new_cost)))

p(f"\nRENCANA: fill {len(plan)} produk; skip: storable {skipped_storable}, "
  f"sudah ada cost {skipped_has_cost}, tanpa/0 di snapshot {skipped_zero}")

# ---------- 2. Dry-run listing ----------
p("\n--- DRY-RUN LIST ---")
for pp, c in sorted(plan, key=lambda x: x[0].id):
    p(f"   id={pp.id:<5} {pp.display_name[:44]:<44} cost -> {c:>12,.2f}")

if not RUN:
    env.cr.rollback()
    p("\nDONE fase8 (dry-run) — tidak ada perubahan, rollback OK.")
else:
    # ---------- 3. Eksekusi: write naik (mapping .write utk hindari cache quirk) ----------
    # Capture pre-run cost storable (baseline utk guard "tidak ada storable berubah")
    storable_before = {}
    for pp in Prod.search([("active", "=", True)]):
        if pp.product_tmpl_id.is_storable:
            v = pp.standard_price
            storable_before[pp.id] = v.get("1") if isinstance(v, dict) else v

    Prod_c = Prod.with_context(company_id=1)
    n = 0
    for pp, c in sorted(plan, key=lambda x: x[0].id):
        Prod_c.browse(pp.id).write({"standard_price": c})
        n += 1
    env.cr.flush()

    # ---------- 4. Verifikasi re-read ----------
    p("\n--- VERIFIKASI (re-read dari DB) ---")
    n_bad = 0
    for pp, c in sorted(plan, key=lambda x: x[0].id):
        got = Prod_c.browse(pp.id).standard_price
        got = got.get("1") if isinstance(got, dict) else got
        match = got is not None and abs(float(got) - c) < 0.005
        if not match:
            n_bad += 1
            p(f"   id={pp.id:<5} {pp.display_name[:40]:<40} EXPECT {c:,.2f} GOT {got}  MISMATCH")
    ok = (n_bad == 0)
    p(f"   mismatch: {n_bad} / {len(plan)} -> {'semua OK' if ok else 'ADA MASALAH'}")

    # ---------- 5. Verifikasi: storable tidak berubah DIBANDING PRE-RUN ----------
    # (2 storable memang beda dgn snapshot — efek FIFO recompute Fase 1, bukan script ini)
    stor_bad = 0
    for pid, want in storable_before.items():
        got = Prod_c.browse(pid).standard_price
        got = got.get("1") if isinstance(got, dict) else got
        if want is not None and (got is None or abs(float(got or 0) - float(want)) > 0.005):
            stor_bad += 1
            p(f"   STORABLE BERUBAH OLEH SCRIPT! id={pid}: want {want} got {got}")
    p(f"   storable berubah oleh script: {stor_bad} (harus 0)")
    p("   (catatan: AIR GALON & AYAM CUT 9 memang sudah beda vs snapshot sejak Fase 1")
    p("    — FIFO recompute side effect, dibiarkan apa adanya, bukan diubah script ini.)")

    # ---------- 5. Commit ----------
    if ok and stor_bad == 0:
        env.cr.commit()
        p(f"\nCOMMITTED: {n} standard_price non-storable di-restore dari snapshot pre-Fase-1.")
    else:
        env.cr.rollback()
        p("\nGAGAL verifikasi — ROLLBACK, tidak ada yang di-commit. Cek output di atas.")
