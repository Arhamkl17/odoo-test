# -*- coding: utf-8 -*-
"""
settlement_outstanding_1103.py — Settlement Outstanding Receipts 1103.06 -> Bank wallets

POS 20 Jun - 31 Aug creates outstanding 1103.06 per bank journal (QRIW, OVOW, GPYW, SPPW, BNK1, BNKB)
that must be settled to the journal's default cash account (1101.01/02/03/04/05) so that
cash is available for tunai purchases and TB is clean (no 1103.06).

This script mimics the settlement part of juni_juli_92 but run standalone idempotently.

  dry-run : cat scripts/settlement_outstanding_1103.py | odoo shell -d Test1 ...
  RUN=1   : RUN=1 cat scripts/settlement_outstanding_1103.py | odoo shell -d Test1 ...

Periods: 2026-06-20..30 (June), July, August — matches POS periods.
But alsohandles generic if outside.
"""
import os
from datetime import date, timedelta

RUN = os.environ.get("RUN") == "1"

cr = env.cr
AM = env["account.move"]
AJ = env["account.journal"]
AA = env["account.account"]
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

PERIODS = {
    "june":   ("2026-06-20", "2026-07-01", "2026-06-30", "Juni 2026"),
    "july":   ("2026-07-01", "2026-08-01", "2026-07-31", "Juli 2026"),
    "august": ("2026-08-01", "2026-09-01", "2026-08-31", "Agustus 2026"),
}

def acc_id(code):
    cr.execute("SELECT id FROM account_account WHERE code_store->>'1'=%s LIMIT 1", (code,))
    r = cr.fetchone()
    return r[0] if r else None

OUT_ACC = acc_id("1103.06")
if not OUT_ACC:
    raise SystemExit("Akun 1103.06 tidak ditemukan")

say("="*100)
say("SETTLEMENT OUTSTANDING 1103.06 -> Bank | RUN=%s | out_acc=%s" % (RUN, OUT_ACC))
say("="*100)

# Ensure hash disabled for relevant journals (already false, but ensure)
cr.execute("UPDATE account_journal SET restrict_mode_hash_table=false WHERE code IN ('BNK1','BNKB','QRIW','OVOW','GPYW','SPPW')")
say("Hash disabled for bank journals")

# Check current outstanding per journal per period
say("")
say("[CEK SAAT INI] Outstanding 1103.06 (harus 2.25M sebelum settlement)")
for name, (d_from, d_to, d_last, label) in PERIODS.items():
    cr.execute("""
        SELECT aj.code, aj.id, aj.default_account_id, sum(aml.balance)
        FROM account_move_line aml
        JOIN account_move am ON am.id=aml.move_id
        JOIN account_journal aj ON aj.id=am.journal_id
        WHERE aml.account_id=%s AND am.state='posted' AND am.date >= %s AND am.date < %s
        GROUP BY 1,2,3 HAVING sum(aml.balance) <> 0 ORDER BY 1
    """, (OUT_ACC, d_from, d_to))
    rows = cr.fetchall()
    if rows:
        for code, jid, def_acc, bal in rows:
            def_code = None
            if def_acc:
                cr.execute("SELECT code_store->>'1' FROM account_account WHERE id=%s", (def_acc,))
                r = cr.fetchone()
                def_code = r[0] if r else str(def_acc)
            say("  %-7s %-6s %12s -> def %s (%s) saldo %s" % (name, code, jid, def_acc, def_code, money(bal)))
    else:
        say("  %-7s tidak ada outstanding (sudah settle?)" % name)

# Check if settlement already exists (ref Settlement)
cr.execute("SELECT ref, count(*) FROM account_move WHERE ref LIKE 'Settlement outstanding 1103.06%%' GROUP BY 1")
existing = cr.fetchall()
if existing:
    say("")
    say("[EXISTING SETTLEMENT] ditemukan %d ref:" % len(existing))
    for ref, cnt in existing:
        say("  %s x%d" % (ref, cnt))
    # we will delete and recreate to ensure correctness if RUN
    if RUN:
        say("  Akan hapus dan buat ulang (idempotent)")

if not RUN:
    say("")
    say("DRY-RUN — tidak ada data ditulis. Jalankan RUN=1 untuk eksekusi.")
    # Estimate total settlement
    cr.execute("SELECT sum(balance) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id WHERE aml.account_id=%s AND am.state='posted'", (OUT_ACC,))
    tot = cr.fetchone()[0] or 0
    say("  Total outstanding 1103.06 saat ini: %s" % money(tot))
    say("  Akan dibuat ~18 JE (6 journal x 3 bulan) -> outstanding jadi 0, kas bank jadi +2.25M")
    env.cr.rollback()
    import sys; sys.exit(0)

# --- EKSEKUSI ---
say("")
say("[EKSEKUSI] Buat JE settlement per journal per bulan")

# Hapus settlement lama jika ada (idempotent)
old = AM.search([("ref", "like", "Settlement outstanding 1103.06%")])
if old:
    say("  Hapus %d JE lama" % len(old))
    # need to unlink via SQL? Use button_draft then unlink
    for m in old:
        try:
            if m.state == "posted":
                m.button_draft()
            m.unlink()
        except Exception as e:
            say("    gagal hapus %s: %s" % (m.name, e))
    env.cr.commit()
    say("  Dihapus")

created = 0
for name, (d_from, d_to, d_last, label) in PERIODS.items():
    cr.execute("""
        SELECT aj.id, aj.code, aj.default_account_id, sum(aml.balance) as bal
        FROM account_move_line aml
        JOIN account_move am ON am.id=aml.move_id
        JOIN account_journal aj ON aj.id=am.journal_id
        WHERE aml.account_id=%s AND am.state='posted' AND am.date >= %s AND am.date < %s
        GROUP BY 1,2,3 HAVING sum(aml.balance) <> 0
    """, (OUT_ACC, d_from, d_to))
    for jid, code, def_acc, bal in cr.fetchall():
        if abs(bal) < 0.01:
            continue
        if not def_acc:
            say("  %-7s %-6s SKIP — tidak ada default_account" % (name, code))
            continue
        j = AJ.browse(jid)
        ref = "Settlement outstanding 1103.06 %s %s" % (code, label)
        # bal is debit (positive) in outstanding, so to settle: credit outstanding, debit bank
        # outstanding is asset_current with debit 2.25M, need to credit it to 0
        lines = [
            (0, 0, {"account_id": def_acc, "debit": bal, "credit": 0.0, "name": "Pencairan %s %s dari POS" % (code, label)}),
            (0, 0, {"account_id": OUT_ACC, "debit": 0.0, "credit": bal, "name": "Pencairan %s %s dari POS" % (code, label)}),
        ]
        mv = AM.create({"journal_id": jid, "date": d_last, "ref": ref, "line_ids": lines})
        mv.action_post()
        say("  %-7s %-6s %12s -> %s (%s) JE %s" % (name, code, money(bal), mv.name, j.code, ref))
        created += 1
        env.cr.commit()

say("")
say("[SELESAI] %d JE settlement dibuat" % created)

# Verifikasi
say("")
say("[VERIFIKASI]")
cr.execute("SELECT sum(balance) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id WHERE aml.account_id=%s AND am.state='posted'", (OUT_ACC,))
tot = cr.fetchone()[0] or 0
say("  Outstanding 1103.06 sekarang: %s %s" % (money(tot), "OK (0)" if abs(tot) < 0.01 else ">>> BELUM 0"))
for code_target in ("1101.01","1101.02","1101.03","1101.04","1101.05"):
    aid = acc_id(code_target)
    cr.execute("SELECT sum(aml.balance) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id WHERE aml.account_id=%s AND am.state='posted'", (aid,))
    bal = cr.fetchone()[0] or 0
    cr.execute("SELECT name->>'en_US' FROM account_account WHERE id=%s", (aid,))
    nm = cr.fetchone()[0]
    say("  %-8s %-20s %14s" % (code_target, nm[:20], money(bal)))
# Receivable check
cr.execute("SELECT sum(aml.balance) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id JOIN account_account aa ON aa.id=aml.account_id WHERE aa.account_type='asset_receivable' AND am.state='posted'")
piut = cr.fetchone()[0] or 0
say("  Piutang Receivable total: %s %s" % (money(piut), "OK" if abs(piut) < 0.01 else ">>> CEK"))

# TB
cr.execute("SELECT sum(debit), sum(credit) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id WHERE am.state='posted'")
d,c = cr.fetchone()
say("  TB debit %s credit %s diff %s %s" % (money(d), money(c), money((d or 0)-(c or 0)), "OK" if abs((d or 0)-(c or 0))<0.01 else ">>> TIDAK BALANCE"))
say("="*100)
env.cr.commit()
