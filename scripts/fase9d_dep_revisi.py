# -*- coding: utf-8 -*-
# CATATAN FASE 11 (12 Sep 2026): JE "(demo)" Fase 9 direklasifikasi resmi jadi DATA REAL —
#   marker "(demo)" sudah dihapus dari move.ref 5 JE (MISC/0058-0062); label tidak dipakai lagi.
#   PERINGATAN: JANGAN re-run script ini — guard anti-duplikat masih mencocokkan REF LAMA
#   "(demo)" yang sudah tidak ada di DB -> risiko JE GANDA. Log historis: PROGRESS_DASHBOARD.md 18.
# fase9d_dep_revisi.py — S3 step 4: revisi masa manfaat penyusutan (agresif, demo Agustus).
#   Resto 4->8 th | Renovasi 8->12 | Kantor 5->8 | IT&POS 3->5 | Gudang 5->8 | Kendaraan 5->8
#   (Bangunan Gudang 20 th tetap)
#   JE per aset: D akumulasi / K beban penyusutan = dep_lama - dep_baru (Agustus saja)
#   Bulan depan: JE bulanan manual memakai dep baru (total 11.743.055,56/bln)
# Pola: dry-run default; RUN=1 commit; anti-duplikat via ref; verifikasi per aset.
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

REF = "Revisi masa manfaat penyusutan (demo)"

# (nama, gross, akumulasi_code, beban_code, th_lama, th_baru)
ASSETS = [
    ("Peralatan Resto",    400_000_000, "1106.03", "6101.16", 4, 8),
    ("Aset Renovasi",      500_000_000, "1106.04", "6101.17", 8, 12),
    ("Peralatan Kantor",   120_000_000, "1106.02", "6101.15", 5, 8),
    ("Peralatan IT & POS",  60_000_000, "1200.13", "6200.07", 3, 5),
    ("Peralatan Gudang",    80_000_000, "1200.12", "6200.06", 5, 8),
    ("Kendaraan",           50_000_000, "1106.01", "6101.14", 5, 8),
]

# ---------- 1. Rencana + validasi dep lama vs DB ----------
acc_by_code = {}
for aid, code in rows("SELECT id, code_store->>'1' FROM account_account"):
    if code:
        acc_by_code[code] = aid
for c in ("6200.05",):
    assert c in acc_by_code

p("\nRencana revisi (Agustus saja):")
tot_delta = 0.0
plan = []
for nm, gross, acc_code, exp_code, y_old, y_new in ASSETS:
    dep_old = gross / (y_old * 12)
    dep_new = gross / (y_new * 12)
    delta = round(dep_old - dep_new, 2)
    # cek dep lama tercatat di DB (Agustus)
    db_dep = rows("""
        SELECT SUM(l.debit-l.credit) FROM account_move_line l
        JOIN account_account a ON a.id=l.account_id
        JOIN account_move m ON m.id=l.move_id
        WHERE m.state='posted' AND m.date BETWEEN '2026-08-01' AND '2026-08-31'
          AND a.code_store->>'1'=%s
    """, (exp_code,))[0][0]
    match = db_dep is not None and abs(float(db_dep) - dep_old) < 1.0
    p(f"   {nm:<20} {y_old}->{y_new} th | dep {dep_old:>12,.2f} -> {dep_new:>12,.2f} | Δ {delta:>12,.2f} | DB {float(db_dep):>12,.2f} {'OK' if match else 'BEDA!'}")
    assert match, f"dep lama {nm} tidak cocok dgn DB"
    tot_delta += delta
    plan.append((nm, acc_code, exp_code, delta))

dep_bangunan = rows("""
    SELECT SUM(l.debit-l.credit) FROM account_move_line l
    JOIN account_account a ON a.id=l.account_id
    JOIN account_move m ON m.id=l.move_id
    WHERE m.state='posted' AND m.date BETWEEN '2026-08-01' AND '2026-08-31'
      AND a.code_store->>'1'='6200.05'
""")[0][0]
tot_dep_new = 19_875_000 - round(tot_delta, 2)   # dep lama total - total koreksi
p(f"   TOTAL Δ Agustus : {tot_delta:,.2f}")
p(f"   dep baru/bln    : {tot_dep_new:,.2f} (harus 11.743.055,56)")
assert abs(tot_dep_new - 11_743_055.56) < 1.0

misc_jid = rows("SELECT id FROM account_journal WHERE code='MISC' AND company_id=1 LIMIT 1")[0][0]
dup = rows("SELECT COUNT(*) FROM account_move WHERE ref=%s AND state='posted'", (REF,))[0][0]

if not RUN:
    p("(dry-run — tidak ada JE dibuat)")
    p("DONE fase9d (dry-run).")
else:
    if dup:
        p(f"JE demo sudah ada ({dup}) — skip (rerun).")
    else:
        Move = env["account.move"]
        lines = []
        for nm, acc_code, exp_code, delta in plan:
            if delta > 0.005:
                lines.append((0, 0, {"account_id": acc_by_code[acc_code],
                                     "name": f"Koreksi penyusutan Agustus {nm} (demo)",
                                     "debit": delta, "credit": 0.0}))
                lines.append((0, 0, {"account_id": acc_by_code[exp_code],
                                     "name": f"Revisi masa manfaat {nm} (demo)",
                                     "debit": 0.0, "credit": delta}))
        je = Move.create({"journal_id": misc_jid, "date": date(2026, 8, 31),
                          "ref": REF, "move_type": "entry", "line_ids": lines})
        je.action_post()
        p(f"   JE: {je.name}")

    # ---------- 2. Verifikasi ----------
    env.cr.flush()
    r = rows("SELECT m.name, SUM(l.debit), SUM(l.credit) FROM account_move m "
             "JOIN account_move_line l ON l.move_id=m.id "
             "WHERE m.ref=%s AND m.state='posted' GROUP BY m.id, m.name", (REF,))[0]
    assert abs(r[1] - r[2]) < 0.01, "JE tidak balanced"
    p(f"   {r[0]} dr {r[1]:,.2f} cr {r[2]:,.2f} OK")

    dep_total = rows("""
        SELECT SUM(l.debit-l.credit) FROM account_move_line l
        JOIN account_account a ON a.id=l.account_id
        JOIN account_move m ON m.id=l.move_id
        WHERE m.state='posted' AND m.date BETWEEN '2026-08-01' AND '2026-08-31'
          AND a.name->>'en_US' ILIKE '%nyusut%' AND a.account_type LIKE 'expense%'
    """)[0][0]
    p(f"   total beban dep Agustus: {float(dep_total):,.2f} (harus 11.743.055,56)")
    assert abs(float(dep_total) - 11_743_055.56) < 1.0

    tb = rows("SELECT COALESCE(SUM(l.debit),0)-COALESCE(SUM(l.credit),0) FROM account_move_line l "
              "JOIN account_move m ON m.id=l.move_id WHERE m.state='posted'")[0][0]
    p(f"   TB diff: {tb:,.2f}")
    assert abs(tb) < 0.01
    env.cr.commit()
    p("\nCOMMITTED fase9d.")
