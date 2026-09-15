# -*- coding: utf-8 -*-
# CATATAN FASE 11 (12 Sep 2026): JE "(demo)" Fase 9 direklasifikasi resmi jadi DATA REAL —
#   marker "(demo)" sudah dihapus dari move.ref 5 JE (MISC/0058-0062); label tidak dipakai lagi.
#   PERINGATAN: JANGAN re-run script ini — guard anti-duplikat masih mencocokkan REF LAMA
#   "(demo)" yang sudah tidak ada di DB -> risiko JE GANDA. Log historis: PROGRESS_DASHBOARD.md 18.
# fase9c_gaji_efisiensi.py — S3 step 3: efisiensi 3 karyawan office (demo Agustus).
#   74jt / 29 org = 2.551.724,14/org -> 3 org = 7.655.172,41
#   JE: D <akun kredit JE gaji asli MISC/2026/08/0046> / K 6101.03
# Pola: dry-run default; RUN=1 commit; anti-duplikat via ref; JANGAN rollback di tengah.
from datetime import date

def p(*a):
    print(*a)

import os
RUN = os.environ.get("RUN") == "1"
p(f"MODE: {'EXECUTE (RUN=1)' if RUN else 'DRY-RUN'}")

def rows(sql, params=None):
    if params:
        env.cr.execute(sql, params)
    else:
        env.cr.execute(sql)
    return env.cr.fetchall()

REF = "Efisiensi 3 karyawan office (demo)"
N_ORG, N_TOTAL = 3, 29
AMT = round(74_000_000 / N_TOTAL * N_ORG, 2)

# ---------- 1. Cari akun kredit JE gaji asli ----------
p(f"\nJE gaji asli (MISC/2026/08/0046):")
for r in rows("""
    SELECT a.code_store->>'1', a.name->>'en_US', l.debit, l.credit
    FROM account_move_line l
    JOIN account_account a ON a.id=l.account_id
    JOIN account_move m ON m.id=l.move_id
    WHERE m.name='MISC/2026/08/0046'
"""):
    p(f"   {str(r[0]):<10} {str(r[1])[:36]:<36} dr {r[2]:>13,.2f} cr {r[3]:>13,.2f}")
env.cr.execute("""
    SELECT a.code_store->>'1' FROM account_move_line l
    JOIN account_account a ON a.id=l.account_id
    JOIN account_move m ON m.id=l.move_id
    WHERE m.name='MISC/2026/08/0046' AND l.credit > 0 LIMIT 1
""")
counter_code = env.cr.fetchone()[0]
p(f"   counter account = {counter_code}")

# ---------- 2. Rencana ----------
acc_by_code = {}
for aid, code in rows("SELECT id, code_store->>'1' FROM account_account"):
    if code:
        acc_by_code[code] = aid
for c in (counter_code, "6101.03"):
    assert c in acc_by_code, f"akun {c} tidak ditemukan"
misc_jid = rows("SELECT id FROM account_journal WHERE code='MISC' AND company_id=1 LIMIT 1")[0][0]
dup = rows("SELECT COUNT(*) FROM account_move WHERE ref=%s AND state='posted'", (REF,))[0][0]

p(f"\nRENCANA: {N_ORG} org x {74_000_000/N_TOTAL:,.2f} = {AMT:,.2f}")
p(f"   D {counter_code} / K 6101.03 (Beban Gaji)")

if not RUN:
    p("(dry-run — tidak ada JE dibuat)")
    p("DONE fase9c (dry-run).")
else:
    if dup:
        p(f"JE demo sudah ada ({dup}) — skip (rerun).")
    else:
        je = env["account.move"].create({
            "journal_id": misc_jid, "date": date(2026, 8, 31),
            "ref": REF, "move_type": "entry",
            "line_ids": [
                (0, 0, {"account_id": acc_by_code[counter_code],
                        "name": f"Refund gaji {N_ORG} karyawan office (demo)",
                        "debit": AMT, "credit": 0.0}),
                (0, 0, {"account_id": acc_by_code["6101.03"],
                        "name": f"Beban gaji berkurang {N_ORG} org (demo)",
                        "debit": 0.0, "credit": AMT}),
            ],
        })
        je.action_post()
        p(f"   JE: {je.name}")

    # ---------- 3. Verifikasi ----------
    env.cr.flush()
    for r in rows("SELECT m.name, SUM(l.debit), SUM(l.credit) FROM account_move m "
                  "JOIN account_move_line l ON l.move_id=m.id "
                  "WHERE m.ref=%s AND m.state='posted' GROUP BY m.id, m.name", (REF,)):
        ok = abs(r[1] - r[2]) < 0.01
        p(f"   {r[0]} dr {r[1]:,.2f} cr {r[2]:,.2f} {'OK' if ok else 'TIDAK BALANCE!'}")
        assert ok
    gaji = rows("""
        SELECT SUM(l.debit-l.credit) FROM account_move_line l
        JOIN account_account a ON a.id=l.account_id
        JOIN account_move m ON m.id=l.move_id
        WHERE m.state='posted' AND m.date BETWEEN '2026-08-01' AND '2026-08-31'
          AND a.code_store->>'1'='6101.03'
    """)[0][0]
    p(f"   6101.03 setelah JE: {gaji:,.2f} (harus {74_000_000-AMT:,.2f})")
    assert abs(gaji - (74_000_000 - AMT)) < 0.01
    tb = rows("SELECT COALESCE(SUM(l.debit),0)-COALESCE(SUM(l.credit),0) FROM account_move_line l "
              "JOIN account_move m ON m.id=l.move_id WHERE m.state='posted'")[0][0]
    p(f"   TB diff: {tb:,.2f}")
    assert abs(tb) < 0.01
    env.cr.commit()
    p("\nCOMMITTED fase9c.")
