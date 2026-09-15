# -*- coding: utf-8 -*-
"""Verifikasi hipotesis: minus per 31 Agu = setoran 1 Sep yang tersedot sweep
backdate. Untuk tiap akun kas/bank yang minus per 31 Agu, bandingkan dengan
mutasi setelah 31 Agu."""

Aml = env["account.move.line"]
Account = env["account.account"].with_context(active_test=False)
cash = Account.search([("account_type", "=", "asset_cash")])

print("%-24s %14s %14s %10s" % ("Akun", "Minus 31 Agu", "Mutasi >31 Agu", "Cocok?"))
for acc, deb, cred in Aml._read_group(
        [("account_id", "in", cash.ids), ("parent_state", "=", "posted"), ("date", "<=", "2026-08-31")],
        ["account_id"], ["debit:sum", "credit:sum"]):
    bal_aug = (deb or 0.0) - (cred or 0.0)
    if bal_aug >= -0.005:
        continue
    after = Aml.search([("account_id", "=", acc.id), ("parent_state", "=", "posted"),
                        ("date", ">", "2026-08-31")])
    net_after = sum((l.debit or 0.0) - (l.credit or 0.0) for l in after)
    ok = "OK" if abs(net_after + bal_aug) < 0.005 else "BEDA"
    print("%-24s %14.2f %14.2f %10s" % (acc.name, bal_aug, net_after, ok))
    for l in after:
        print("    %s | %-14s | %-24s | %-34s | D %12.2f K %12.2f" % (
            l.date, l.journal_id.code or "-", (l.move_id.name or "")[:24],
            (l.name or "")[:34], l.debit or 0.0, l.credit or 0.0))

print("\nJE sweep konsolidasi (kredit besar ke BSI, tanggal 31 Agu):")
misc = Aml.search([("parent_state", "=", "posted"), ("date", "=", "2026-08-31"),
                   ("journal_id.code", "=", "MISC"), ("credit", ">", 1000000)],
                  order="credit DESC")
for l in misc:
    print("  %-24s %-34s K %14.2f" % (l.move_id.name, l.account_id.name[:34], l.credit or 0.0))
