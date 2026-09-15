# -*- coding: utf-8 -*-
# fase10a_normalize_bom_uom.py — Fase 10a: Normalisasi 63 BOM line cross-root.
#
# Masalah (hasil audit cek_cost_uom*.py, 11 Sep 2026):
#   61x CUKA & MINYAK GORENG : uom line GRM vs uom produk MIL (root beda, tak konvertibel)
#    2x TAHU & TEMPE         : uom line PTG vs uom produk GRM
#   Konsumsi aktual (stock.move done) selalu ter-book di UOM PRODUK — core Odoo 19
#   mengabaikan uom line saat kit dijual (pass-through 1:1, terbukti: 100 GRM -> MIL = 100).
#   Jadi nilai qty TIDAK diubah — hanya uom line disamakan dgn uom produk (re-label).
#
# Keputusan (A): qty value dipertahankan persis; label uom line = uom produk.
#   - CUKA   0.07 GRM -> 0.07 MIL  (sesuai konsumsi riil MIL 143.61 utk ~2000 kit)
#   - MINYAK 0.52 GRM -> 0.52 MIL  (sesuai konsumsi riil MIL 951.38)
#   - TAHU   3.0 PTG  -> 3.0 GRM & TEMPE 4.0 PTG -> 4.0 GRM
#     (catatan: basis costing TAHU/TEMPE per-gram vs per-piece tetap ambigu —
#      dampak ~Rp 40rb / 0.04% HPP; tidak diubah di fase ini, hanya label.)
#
# Grouping: per (bom_id, product_id) — kalau satu BOM punya multi-line komponen yg sama,
# qty di-JUMLAH lalu ditulis ke line pertama & line sisanya dihapus (hindari duplikasi).
# Pola: dry-run default, RUN=1 (env var) utk commit. Idempotent. Tanpa env.cr.rollback() mid-run.
# Backup: backup_bom_uom_pre_fase10a.json
import json, os

RUN = os.environ.get('RUN') == '1'
BACKUP = "backup_bom_uom_pre_fase10a.json"

def p(*a):
    print(*a)

def rows(sql, params=None):
    env.cr.execute(sql, params or ())
    return env.cr.fetchall()

def uom_root(u):
    seen = set()
    while u and u.relative_uom_id and u.id not in seen:
        seen.add(u.id)
        u = u.relative_uom_id
    return u

p(f"=== Fase 10a — Normalisasi BOM line cross-root ({'RUN=1 COMMIT' if RUN else 'DRY-RUN'}) ===")

bls = env['mrp.bom.line'].with_context(active_test=False).search([])
cross = bls.filtered(lambda l: l.product_uom_id and l.product_id.uom_id
                     and uom_root(l.product_uom_id) != uom_root(l.product_id.uom_id))
p(f"BOM line cross-root ditemukan: {len(cross)} (harus 63)")

if not cross:
    p("\nTidak ada yang perlu dinormalisasi — idempotent, selesai.")
else:
    # ---------- backup ----------
    backup = [{
        "bom_line_id": l.id, "bom_id": l.bom_id.id, "bom_name": l.bom_id.display_name,
        "product_id": l.product_id.id, "product_name": l.product_id.display_name,
        "old_uom_id": l.product_uom_id.id, "old_uom": l.product_uom_id.name,
        "old_qty": l.product_qty,
    } for l in cross]
    with open(BACKUP, "w") as f:
        json.dump(backup, f, indent=1, ensure_ascii=False)
    p(f"Backup {len(backup)} line -> {BACKUP}")

    # ---------- grouping per (bom, produk) ----------
    groups = {}
    for l in cross:
        groups.setdefault((l.bom_id.id, l.product_id.id), []).append(l)

    p(f"\n{'bom':<28} {'komponen':<18} {'qty_lama':>22} -> {'qty_baru':<10} {'uom_baru'}")
    plan = []
    for (bom_id, prod_id), lines in sorted(groups.items()):
        lines = sorted(lines, key=lambda x: x.id)
        total = sum(l.product_qty for l in lines)
        target_uom = lines[0].product_id.uom_id
        old_lbl = " + ".join(f"{l.product_qty} {l.product_uom_id.name}" for l in lines)
        plan.append((lines, total, target_uom, old_lbl))
        p(f"{lines[0].bom_id.display_name[:27]:<28} {lines[0].product_id.display_name[:17]:<18} "
          f"{old_lbl:>22} -> {total:<10.4f} {target_uom.name}")

    # guard: semua target uom satu root dgn produk (trivially true) & qty>0
    assert all(total > 0 for _, total, _, _ in plan), "ada qty total <= 0!"

    if not RUN:
        p(f"\nDRY-RUN — {len(plan)} group akan diubah. Jalankan: RUN=1 fase10a_normalize_bom_uom.py")
    else:
        for lines, total, target_uom, _ in plan:
            lines[0].write({"product_uom_id": target_uom.id, "product_qty": total})
            for extra in lines[1:]:
                extra.unlink()
        env.cr.commit()
        p(f"\nCOMMIT: {len(plan)} group dinormalisasi.")

        # ---------- verifikasi pasca ----------
        left = bls.exists().filtered(lambda l: l.product_uom_id and l.product_id.uom_id
                                     and uom_root(l.product_uom_id) != uom_root(l.product_id.uom_id))
        p(f"Sisa cross-root setelah commit: {len(left)} (harus 0)")
        # sanity: total qty per (bom, produk) bertahan
        for (bom_id, prod_id), lines in sorted(groups.items()):
            cur = rows("""
                SELECT COALESCE(SUM(bl.product_qty),0) FROM mrp_bom_line bl
                WHERE bl.bom_id=%s AND bl.product_id=%s
            """, (bom_id, prod_id))[0][0]
            want = sum(l.product_qty for l in lines)
            p(f"   bom={bom_id} prod={lines[0].product_id.display_name[:20]:<20} "
              f"qty_total={float(cur):.4f} (harus {want:.4f}) {'OK' if abs(float(cur)-want) < 1e-6 else 'BEDA!'}")

# ---------- invariant: TB & cost tak tersentuh ----------
tb = float(rows("""
    SELECT COALESCE(SUM(l.debit),0)-COALESCE(SUM(l.credit),0)
    FROM account_move_line l JOIN account_move m ON m.id=l.move_id
    WHERE m.state='posted'
""")[0][0])
n_cost = rows("SELECT count(*) FROM product_product WHERE standard_price::text <> '0' AND standard_price IS NOT NULL")[0][0]
p(f"\nTB diff: {tb:,.2f} {'OK' if abs(tb) < 0.01 else 'BEDA!'}")
p(f"Produk dgn cost tercatat (raw table): {n_cost}")
p("DONE fase10a_normalize_bom_uom.")
