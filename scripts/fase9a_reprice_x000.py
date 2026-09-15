# -*- coding: utf-8 -*-
# CATATAN FASE 11 (12 Sep 2026): JE "(demo)" Fase 9 direklasifikasi resmi jadi DATA REAL —
#   marker "(demo)" sudah dihapus dari move.ref 5 JE (MISC/0058-0062); label tidak dipakai lagi.
#   PERINGATAN: JANGAN re-run script ini — guard anti-duplikat masih mencocokkan REF LAMA
#   "(demo)" yang sudah tidak ada di DB -> risiko JE GANDA. Log historis: PROGRESS_DASHBOARD.md 18.
# fase9a_reprice_x000.py — S3 step 1: repricing x777 -> x000+1000 (15 menu x777).
#   list_price baru = (floor(cur/1000)+1)*1000 + 1000  (mis. 11.777 -> 13.000)
#   + JE demo Agustus: D 11210011 / K 4101.02 (food) & 4101.01 (bev) = qty Agustus x delta
# Yang TIDAK disentuh: cost, BoM, pos_order, pos_payment, jurnal POS asli.
# Backup json SEBELUM update. Pola: dry-run default; RUN=1 utk eksekusi+commit.
import os, json
from datetime import date

def p(*a):
    print(*a)

RUN = os.environ.get("RUN") == "1"
p(f"MODE: {'EXECUTE (RUN=1)' if RUN else 'DRY-RUN (set RUN=1 utk eksekusi)'}")

# 15 menu x777 (id dari update_harga_x777.py). Kategori: 11=Menu Food, 10=Menu Beverage
CAT = {628: 11, 622: 11, 626: 11, 627: 11, 623: 11, 576: 11, 616: 11, 620: 11,
       614: 11, 588: 11, 601: 11, 615: 11, 548: 11, 547: 11, 630: 10}

Prod = env["product.product"]
prods = Prod.browse(sorted(CAT))

# ---------- 1. Validasi nama & harga sekarang masih x777 ----------
EXPECT = {628: 4777, 622: 11777, 626: 5777, 627: 5777, 623: 2777, 576: 6777,
          616: 18777, 620: 40777, 614: 38777, 588: 38777, 601: 100777,
          615: 36777, 548: 14777, 547: 14777, 630: 1777}
errors = []
for pr in prods:
    if pr.product_tmpl_id.list_price != EXPECT[pr.id]:
        errors.append(f"id {pr.id}: harga {pr.product_tmpl_id.list_price} != {EXPECT[pr.id]}")
if errors:
    p("GAGAL validasi — harga tidak sesuai dugaan, TIDAK ADA yang diubah:")
    for e in errors:
        p("  -", e)
    env.cr.rollback()
else:
    # ---------- 2. Qty Agustus per menu (basis JE demo) ----------
    D1, D2 = '2026-08-01', '2026-09-01'
    def rows(sql, params=None):
        if params:
            env.cr.execute(sql, params)
        else:
            env.cr.execute(sql)
        return env.cr.fetchall()
    qty = dict((r[0], float(r[1])) for r in rows("""
        SELECT l.product_id, SUM(l.qty) FROM pos_order_line l
        JOIN pos_order o ON o.id=l.order_id
        WHERE o.state IN ('done','invoiced') AND o.date_order >= %s AND o.date_order < %s
          AND l.product_id = ANY(%s) GROUP BY 1
    """, (D1, D2, sorted(CAT))))
    env.cr.rollback()

    # ---------- 3. Rencana ----------
    plan = []   # (id, name, old, new, delta, qty_aug)
    for pr in prods:
        cur = pr.product_tmpl_id.list_price
        new = (int(cur // 1000) + 1) * 1000 + 1000
        plan.append((pr.id, pr.display_name, cur, new, new - cur, qty.get(pr.id, 0.0)))
    tot_delta = sum(x[4] * x[5] for x in plan)   # x = (id, nama, old, new, DELTA, qty)
    d_food = sum(x[4] * x[5] for x in plan if CAT[x[0]] == 11)
    d_bev = sum(x[4] * x[5] for x in plan if CAT[x[0]] == 10)
    p(f"\nRENCANA repricing (x000+1000): {len(plan)} menu, Δ revenue (qty Agu) = {tot_delta:,.2f}")
    p(f"   food 4101.02: {d_food:,.2f} | bev 4101.01: {d_bev:,.2f}")
    for pid, nm, old, new, dlt, q in plan:
        p(f"   id={pid:<5} {nm[:36]:<36} {old:>9,.0f} -> {new:>9,.0f}  qty {q:>6,.0f}  Δ {q*dlt:>+11,.0f}")

    if not RUN:
        env.cr.rollback()
        p("\nDONE fase9a (dry-run) — tidak ada perubahan.")
    else:
        # ---------- 4. Backup + update harga ----------
        backup = {}
        for pr in prods:
            backup[str(pr.id)] = {"name": pr.display_name,
                                  "old_list_price": pr.product_tmpl_id.list_price}
        with open("backup_harga_sebelum_x000_S3.json", "w", encoding="utf-8") as f:
            json.dump(backup, f, indent=2, ensure_ascii=False)
        p(f"\nBackup {len(backup)} harga -> backup_harga_sebelum_x000_S3.json")

        for pr in prods:
            cur = pr.product_tmpl_id.list_price
            new = (int(cur // 1000) + 1) * 1000 + 1000
            pr.product_tmpl_id.list_price = new
        env.cr.flush()

        # verifikasi harga
        bad = 0
        for pr in Prod.browse(sorted(CAT)):
            exp = (int(EXPECT[pr.id] // 1000) + 1) * 1000 + 1000
            if pr.product_tmpl_id.list_price != exp:
                bad += 1
                p(f"   HARGA MISMATCH id={pr.id}: {pr.product_tmpl_id.list_price} != {exp}")
        p(f"   harga mismatch: {bad}/{len(plan)}")

        # ---------- 5. JE demo Agustus ----------
        if tot_delta > 0.005 and bad == 0:
            # resolve account id by code (deterministik via SQL jsonb)
            # PENTING: JANGAN rollback di sini — transaction memuat flush harga!
            acc_by_code = {}
            for aid, code in rows("SELECT id, code_store->>'1' FROM account_account"):
                if code:
                    acc_by_code[code] = aid
            for c in ("11210011", "4101.02", "4101.01"):
                assert c in acc_by_code, f"akun {c} tidak ditemukan"
            misc_jid = rows("""
                SELECT id FROM account_journal WHERE code='MISC' AND company_id=1 LIMIT 1
            """)[0][0]

            # guard: JE demo sudah ada? (anti duplikat saat rerun)
            je_exists = rows("""
                SELECT COUNT(*) FROM account_move
                WHERE ref = 'Markup repricing x000+1000 (demo)' AND state = 'posted'
            """)[0][0]

            if je_exists:
                p("   JE demo sudah ada (rerun) — skip JE, hanya memastikan harga")
            else:
                Move = env["account.move"]
                lines = []
                for cat_id, amt in ((11, d_food), (10, d_bev)):
                    if amt > 0.005:
                        lines.append((0, 0, {
                            "account_id": acc_by_code["11210011"],
                            "name": f"Markup repricing x000 (demo) - categ {cat_id}",
                            "debit": amt, "credit": 0.0,
                        }))
                        lines.append((0, 0, {
                            "account_id": acc_by_code["4101.02" if cat_id == 11 else "4101.01"],
                            "name": f"Gross-up omzet markup x000 (demo) - categ {cat_id}",
                            "debit": 0.0, "credit": amt,
                        }))
                je = Move.create({
                    "journal_id": misc_jid,
                    "date": date(2026, 8, 31),
                    "ref": "Markup repricing x000+1000 (demo)",
                    "move_type": "entry",
                    "line_ids": lines,
                })
                je.action_post()
                p(f"   JE demo: {je.name} = {tot_delta:,.2f}")

        # ---------- 6. Verifikasi ulang harga DARI DB (bukan cache) lalu commit ----------
        env.cr.flush()
        env.cr.execute("""
            SELECT COUNT(*) FROM product_template pt
            JOIN product_product pp ON pp.product_tmpl_id = pt.id
            WHERE pp.id = ANY(%s) AND pt.list_price NOT IN %s
        """, (sorted(CAT), tuple(sorted(set(x[3] for x in plan)))))
        bad_db = env.cr.fetchone()[0]
        p(f"   harga mismatch (raw DB): {bad_db}/{len(plan)}")
        if bad == 0 and bad_db == 0:
            env.cr.commit()
            p(f"\nCOMMITTED fase9a: {len(plan)} harga x000+1000 (JE demo {'skip-rerun' if je_exists else 'posted'})")
        else:
            env.cr.rollback()
            p("\nGAGAL — rollback.")
