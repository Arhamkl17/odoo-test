# -*- coding: utf-8 -*-
"""Audit akun kas/bank ber saldo minus (read-only, tidak ada write/commit).

Cari: semua account asset_cash (termasuk inactive), saldo kumulatif posted,
breakdown per jurnal (siapa biang keladinya), lalu detail move line untuk
akun yang minus + running balance.
"""

accs = env["account.account"].with_context(active_test=False).search(
    [("account_type", "=", "asset_cash")])
Aml = env["account.move.line"]

print("=" * 78)
print("AUDIT KAS & BANK — saldo kumulatif posted (debit - kredit)")
print("=" * 78)

groups = Aml._read_group(
    [("account_id", "in", accs.ids), ("parent_state", "=", "posted")],
    ["account_id", "journal_id"], ["debit:sum", "credit:sum"])

per_acc = {}
for acc, journal, debit, credit in groups:
    per_acc.setdefault(acc.id, {"acc": acc, "rows": [], "d": 0.0, "c": 0.0})
    per_acc[acc.id]["rows"].append((journal, debit or 0.0, credit or 0.0))
    per_acc[acc.id]["d"] += debit or 0.0
    per_acc[acc.id]["c"] += credit or 0.0

negatives = []
for aid in sorted(per_acc, key=lambda i: per_acc[i]["acc"].name):
    p = per_acc[aid]
    bal = p["d"] - p["c"]
    state = "INACTIVE" if not p["acc"].active else "active"
    flag = "  <<< MINUS" if bal < -0.005 else ""
    print("%-38s [%s] D %15.2f  K %15.2f  = %15.2f%s" % (
        p["acc"].name, state, p["d"], p["c"], bal, flag))
    if bal < -0.005:
        negatives.append((p["acc"], bal))

print("-" * 78)
print("Breakdown per jurnal — hanya akun MINUS:")
for acc, bal in negatives:
    print("\n### %s (saldo %.2f)" % (acc.name, bal))
    for journal, d, c in sorted(per_acc[acc.id]["rows"], key=lambda r: -(r[2])):
        net = d - c
        print("   %-30s D %14.2f  K %14.2f  net %14.2f" % (journal.name, d, c, net))

# Detail move line + running balance utk akun minus pertama (BNI?)
if negatives:
    acc, bal = negatives[0]
    print("-" * 78)
    print("DETAIL move line: %s  (urut tanggal, running balance)" % acc.name)
    lines = Aml.search(
        [("account_id", "=", acc.id), ("parent_state", "=", "posted")],
        order="date, id")
    run = 0.0
    flips = []
    for l in lines:
        run += (l.debit or 0.0) - (l.credit or 0.0)
        mark = ""
        if run < 0 and not flips:
            mark = "   <<< PERTAMA KALI MINUS DI SINI"
            flips.append(l)
        print("  %s | %-14s | ref %-22s | %-38s | D %12.2f K %12.2f | run %13.2f%s" % (
            l.date, l.journal_id.code or "-", (l.move_id.ref or "")[:22],
            (l.name or "")[:38], l.debit or 0.0, l.credit or 0.0, run, mark))
    if flips:
        f = flips[0]
        print("\nJE penyebab pertama minus:")
        print("  move : %s (%s)" % (f.move_id.name, f.move_id.journal_id.name))
        print("  date : %s   ref : %s" % (f.date, f.move_id.ref))
        print("  semua baris JE ini:")
        for ml in f.move_id.line_ids.sorted(key=lambda x: -abs((x.debit or 0) - (x.credit or 0))):
            print("    %-38s D %14.2f K %14.2f" % (
                ml.account_id.name[:38], ml.debit or 0.0, ml.credit or 0.0))
print("=" * 78)
print("AUDIT SELESAI — read-only, tidak ada perubahan data.")
