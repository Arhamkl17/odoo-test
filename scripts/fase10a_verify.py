# -*- coding: utf-8 -*-
# fase10a_verify.py — READ-ONLY. Verifikasi Fase 10a vs backup pre-run.
import json

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

backup = json.load(open("backup_bom_uom_pre_fase10a.json"))

# 1) sisa cross-root
bls = env['mrp.bom.line'].with_context(active_test=False).search([])
left = bls.filtered(lambda l: l.product_uom_id and l.product_id.uom_id
                    and uom_root(l.product_uom_id) != uom_root(l.product_id.uom_id))
p(f"1) Sisa BOM line cross-root : {len(left)}  (harus 0)  {'OK' if not left else 'BEDA!'}")

# 2) tiap group: line pertama (min id) dari backup masih ada, qty = jumlah group, uom = uom produk
groups = {}
for b in backup:
    groups.setdefault((b["bom_id"], b["product_id"]), []).append(b)
bad = 0
for (bom_id, prod_id), items in sorted(groups.items()):
    first_id = min(i["bom_line_id"] for i in items)
    want = sum(i["old_qty"] for i in items)
    r = rows("""
        SELECT bl.product_qty, (ul.id=up.id) AS uom_ok
        FROM mrp_bom_line bl
        JOIN uom_uom ul ON ul.id=bl.product_uom_id
        JOIN product_product pp ON pp.id=bl.product_id
        JOIN product_template pt ON pt.id=pp.product_tmpl_id
        JOIN uom_uom up ON up.id=pt.uom_id
        WHERE bl.id=%s
    """, (first_id,))
    if not r or abs(float(r[0][0]) - want) > 1e-6 or not r[0][1]:
        bad += 1
        p(f"   BEDA! bom={bom_id} prod={items[0]['product_name'][:24]} line={first_id} "
          f"cur={float(r[0][0]) if r else 'HILANG'} want={want} uom_ok={bool(r[0][1]) if r else '-'}")
p(f"2) Line utama group (qty merged + uom produk): {len(groups)-bad}/{len(groups)}  {'OK' if bad == 0 else 'BEDA!'}")

# 3) uom line sekarang = uom produk utk semua group
uom_bad = 0
for (bom_id, prod_id), items in sorted(groups.items()):
    uom_bad += rows("""
        SELECT count(*) FROM mrp_bom_line bl
        JOIN product_product pp ON pp.id=bl.product_id
        JOIN product_template pt ON pt.id=pp.product_tmpl_id
        JOIN uom_uom ul ON ul.id=bl.product_uom_id
        JOIN uom_uom up ON up.id=pt.uom_id
        WHERE bl.bom_id=%s AND bl.product_id=%s AND ul.id<>up.id
    """, (bom_id, prod_id))[0][0]
p(f"3) Line dgn uom != uom produk di group: {uom_bad}  (harus 0)  {'OK' if uom_bad == 0 else 'BEDA!'}")

# 4) TB & jumlah line total
tb = float(rows("SELECT COALESCE(SUM(l.debit),0)-COALESCE(SUM(l.credit),0) FROM account_move_line l JOIN account_move m ON m.id=l.move_id WHERE m.state='posted'")[0][0])
n_lines = rows("SELECT count(*) FROM mrp_bom_line")[0][0]
p(f"4) TB diff: {tb:,.2f}  {'OK' if abs(tb) < 0.01 else 'BEDA!'} | total BOM line: {n_lines} (722 - 2 duplikat dihapus = 720)")

ok = not left and bad == 0 and uom_bad == 0 and abs(tb) < 0.01
p(f"\nVERDICT Fase 10a: {'LULUS ✓' if ok else 'CEK DI ATAS'}")
p("DONE fase10a_verify — read only.")
