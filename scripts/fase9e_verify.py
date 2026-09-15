# -*- coding: utf-8 -*-
# CATATAN FASE 11 (12 Sep 2026): JE "(demo)" Fase 9 direklasifikasi resmi jadi DATA REAL —
#   marker "(demo)" sudah dihapus dari move.ref 5 JE (MISC/0058-0062); label tidak dipakai lagi.
#   PERINGATAN: JANGAN re-run script ini — guard anti-duplikat masih mencocokkan REF LAMA
#   "(demo)" yang sudah tidak ada di DB -> risiko JE GANDA. Log historis: PROGRESS_DASHBOARD.md 18.
# fase9e_verify.py — READ-ONLY. Verifikasi akhir skenario S3:
# recompute P&L Agustus (net per akun), TB, margin, daftar JE demo Fase 9.
def p(*a):
    print(*a)

def rows(sql, params=None):
    if params:
        env.cr.execute(sql, params)
    else:
        env.cr.execute(sql)
    return env.cr.fetchall()

# ---------- P&L recompute (agregat net per akun) ----------
rev = rows("""
    SELECT COALESCE(SUM(l.credit-l.debit),0) FROM account_move_line l
    JOIN account_account a ON a.id=l.account_id
    JOIN account_move m ON m.id=l.move_id
    WHERE m.state='posted' AND m.date BETWEEN '2026-08-01' AND '2026-08-31'
      AND a.account_type LIKE 'income%'
""")[0][0]
exp = rows("""
    SELECT COALESCE(SUM(l.debit-l.credit),0) FROM account_move_line l
    JOIN account_account a ON a.id=l.account_id
    JOIN account_move m ON m.id=l.move_id
    WHERE m.state='posted' AND m.date BETWEEN '2026-08-01' AND '2026-08-31'
      AND a.account_type LIKE 'expense%'
""")[0][0]
net = float(rev) - float(exp)
margin = net / float(rev) * 100 if rev else 0

p("=== P&L AGUSTUS 2026 — pasca Fase 9 (S3) ===")
p(f"   Pendapatan : {float(rev):>15,.2f}   (target 254.470.313,90)")
p(f"   Beban      : {float(exp):>15,.2f}   (target 230.490.824,48)")
p(f"   NET PROFIT : {net:>15,.2f}   (target  +23.979.489,42)")
p(f"   MARGIN     : {margin:>14.2f}%   (target >= 9,4%)")

ok_rev = abs(float(rev) - 254_470_313.90) < 1.0
ok_exp = abs(float(exp) - 230_490_824.48) < 1.0
ok_net = abs(net - 23_979_489.42) < 1.0
ok_margin = margin >= 9.4
p(f"   check: rev {'OK' if ok_rev else 'BEDA!'} | exp {'OK' if ok_exp else 'BEDA!'} | "
  f"net {'OK' if ok_net else 'BEDA!'} | margin {'OK' if ok_margin else 'BEDA!'}")

# ---------- Komponen kunci ----------
p("\n=== Komponen kunci ===")
for code, label, want in [
    ("6101.03", "Gaji", 66_344_827.59),
    ("6300.01", "Komisi platform", 9_421_920.79),
    ("5101.01", "HPP Bev", 1_039_178.47),
    ("5101.02", "HPP Food", 103_596_333.43),
]:
    v = float(rows("""
        SELECT COALESCE(SUM(l.debit-l.credit),0) FROM account_move_line l
        JOIN account_account a ON a.id=l.account_id
        JOIN account_move m ON m.id=l.move_id
        WHERE m.state='posted' AND m.date BETWEEN '2026-08-01' AND '2026-08-31'
          AND a.code_store->>'1'=%s
    """, (code,))[0][0])
    p(f"   {label:<18} {v:>15,.2f}  (harus {want:,.2f})  {'OK' if abs(v-want)<1 else 'BEDA!'}")

dep = float(rows("""
    SELECT COALESCE(SUM(l.debit-l.credit),0) FROM account_move_line l
    JOIN account_account a ON a.id=l.account_id
    JOIN account_move m ON m.id=l.move_id
    WHERE m.state='posted' AND m.date BETWEEN '2026-08-01' AND '2026-08-31'
      AND a.name->>'en_US' ILIKE '%nyusut%' AND a.account_type LIKE 'expense%'
""")[0][0])
p(f"   {'Penyusutan':<18} {dep:>15,.2f}  (harus 11.743.055,56)  {'OK' if abs(dep-11_743_055.56)<1 else 'BEDA!'}")

# ---------- TB + JE demo ----------
tb = float(rows("""
    SELECT COALESCE(SUM(l.debit),0)-COALESCE(SUM(l.credit),0)
    FROM account_move_line l JOIN account_move m ON m.id=l.move_id
    WHERE m.state='posted'
""")[0][0])
p(f"\n   TB diff      : {tb:,.2f}  {'OK' if abs(tb)<0.01 else 'BEDA!'}")

p("\n=== JE demo Fase 9 (semua harus posted & balanced) ===")
for r in rows("""
    SELECT m.name, m.ref, SUM(l.debit), SUM(l.credit)
    FROM account_move m JOIN account_move_line l ON l.move_id=m.id
    WHERE m.ref ILIKE '%(demo)%' AND m.state='posted'
    GROUP BY m.id, m.name, m.ref ORDER BY m.name
"""):
    ok = abs(r[2] - r[3]) < 0.01
    p(f"   {r[0]:<20} {str(r[1])[:44]:<44} {r[2]:>13,.2f}  {'OK' if ok else 'BEDA!'}")

# ---------- Integritas data asli ----------
pos_tot = float(rows("""
    SELECT COALESCE(SUM(o.amount_total),0) FROM pos_order o
    WHERE o.state IN ('done','invoiced')
      AND o.date_order >= '2026-08-01' AND o.date_order < '2026-09-01'
""")[0][0])
p(f"\n   POS omzet asli  : {pos_tot:,.2f}  {'OK (tak berubah)' if abs(pos_tot-232_683_763.00)<1 else 'BERUBAH!'}")

verdict = ok_rev and ok_exp and ok_net and ok_margin and abs(tb) < 0.01
p(f"\nVERDICT S3: {'LULUS — margin ' + f'{margin:.2f}%' if verdict else 'GAGAL — cek di atas'}")
p("DONE fase9e_verify — read only.")
