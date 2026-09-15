# -*- coding: utf-8 -*-
# CATATAN FASE 11 (12 Sep 2026): JE "(demo)" Fase 9 direklasifikasi resmi jadi DATA REAL —
#   marker "(demo)" sudah dihapus dari move.ref 5 JE (MISC/0058-0062); label tidak dipakai lagi.
#   PERINGATAN: JANGAN re-run script ini — guard anti-duplikat masih mencocokkan REF LAMA
#   "(demo)" yang sudah tidak ada di DB -> risiko JE GANDA. Log historis: PROGRESS_DASHBOARD.md 18.
# fase9b_markup_platform.py — S3 step 2: markup harga platform +15% (demo Agustus).
#   Markup gross = 15% x omzet platform Agustus (D 11210011 / K 4101.02 per platform)
#   Komisi naik  = 10% x markup              (D 6300.01  / K 11210011)
# Pola: dry-run default; RUN=1 commit. Anti-duplikat via ref. JANGAN rollback di tengah.
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

REF_MK = "Markup harga platform +15% (demo)"
REF_KOM = "Komisi platform atas markup (demo)"

# ---------- 1. Basis omzet platform Agustus (fresh dari DB) ----------
plat = rows("""
    SELECT rp.name, SUM(po.amount_total)
    FROM pos_order po JOIN res_partner rp ON rp.id=po.partner_id
    WHERE po.state IN ('done','invoiced')
      AND po.date_order >= '2026-08-01' AND po.date_order < '2026-09-01'
      AND rp.name ILIKE '%Platform%'
    GROUP BY 1 ORDER BY 1
""")
base = {r[0]: float(r[1]) for r in plat}
tot_base = sum(base.values())
p("\nBasis platform Agustus:")
for k, v in base.items():
    p(f"   {k:<28} {v:>13,.2f}  -> markup 15% = {v*0.15:>12,.2f}")
p(f"   TOTAL basis {tot_base:,.2f}")
assert abs(tot_base - 81929746.00) < 1.0, f"basis platform berubah! {tot_base}"

# ---------- 2. Rencana JE ----------
mk_lines_amt = [(k, round(v * 0.15, 2)) for k, v in sorted(base.items())]
tot_mk = round(sum(a for _, a in mk_lines_amt), 2)
tot_kom = round(tot_mk * 0.10, 2)
p(f"\nRENCANA: markup {tot_mk:,.2f} | komisi naik {tot_kom:,.2f} | net {tot_mk-tot_kom:,.2f}")

# akun & jurnal
acc_by_code = {}
for aid, code in rows("SELECT id, code_store->>'1' FROM account_account"):
    if code:
        acc_by_code[code] = aid
for c in ("11210011", "4101.02", "6300.01"):
    assert c in acc_by_code, f"akun {c} tidak ditemukan"
misc_jid = rows("SELECT id FROM account_journal WHERE code='MISC' AND company_id=1 LIMIT 1")[0][0]

# anti-duplikat
dup = rows("SELECT COUNT(*) FROM account_move WHERE ref IN (%s,%s) AND state='posted'", (REF_MK, REF_KOM))[0][0]

if not RUN:
    p("(dry-run — tidak ada JE dibuat)")
    p("DONE fase9b (dry-run).")
else:
    if dup:
        p(f"JE demo sudah ada ({dup}) — skip (rerun).")
    else:
        Move = env["account.move"]
        lines = [(0, 0, {"account_id": acc_by_code["11210011"],
                         "name": "Markup harga platform +15% (demo)",
                         "debit": tot_mk, "credit": 0.0})]
        for pname, amt in mk_lines_amt:
            lines.append((0, 0, {"account_id": acc_by_code["4101.02"],
                                 "name": f"Gross-up markup 15% {pname} (demo)",
                                 "debit": 0.0, "credit": amt}))
        je1 = Move.create({"journal_id": misc_jid, "date": date(2026, 8, 31),
                           "ref": REF_MK, "move_type": "entry", "line_ids": lines})
        je1.action_post()
        je2 = Move.create({"journal_id": misc_jid, "date": date(2026, 8, 31),
                           "ref": REF_KOM, "move_type": "entry",
                           "line_ids": [
                               (0, 0, {"account_id": acc_by_code["6300.01"],
                                       "name": "Komisi 10% atas markup platform (demo)",
                                       "debit": tot_kom, "credit": 0.0}),
                               (0, 0, {"account_id": acc_by_code["11210011"],
                                       "name": "Potongan markup utk komisi (demo)",
                                       "debit": 0.0, "credit": tot_kom}),
                           ]})
        je2.action_post()
        p(f"   JE markup: {je1.name} | JE komisi: {je2.name}")

    # ---------- 3. Verifikasi balanced + TB ----------
    env.cr.flush()
    for r in rows("SELECT m.name, SUM(l.debit), SUM(l.credit) FROM account_move m "
                  "JOIN account_move_line l ON l.move_id=m.id "
                  "WHERE m.ref IN (%s,%s) AND m.state='posted' GROUP BY m.id, m.name", (REF_MK, REF_KOM)):
        ok = abs(r[1] - r[2]) < 0.01
        p(f"   {r[0]} dr {r[1]:,.2f} cr {r[2]:,.2f} {'OK' if ok else 'TIDAK BALANCE!'}")
        assert ok
    tb = rows("SELECT COALESCE(SUM(l.debit),0)-COALESCE(SUM(l.credit),0) FROM account_move_line l "
              "JOIN account_move m ON m.id=l.move_id WHERE m.state='posted'")[0][0]
    p(f"   TB diff: {tb:,.2f}")
    assert abs(tb) < 0.01
    env.cr.commit()
    p("\nCOMMITTED fase9b.")
