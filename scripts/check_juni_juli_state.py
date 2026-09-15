# -*- coding: utf-8 -*-
"""
READ-ONLY — verifikasi cepat keadaan DB setelah P1 (BNI) & P2 (JE opening).

Dipakai sebagai regression check tiap kali langkah Juni/Juli selesai.
"""
SEP = "=" * 78
def sec(t): print("\n" + SEP + "\n" + t + "\n" + SEP)
def rp(v): return "{:,.2f}".format(v or 0.0)

Aml = env["account.move.line"]
Acc = env["account.account"].with_context(active_test=False)
J = env["account.journal"].with_context(active_test=False)

sec("1. INVARIANT GLOBAL")
r = Aml._read_group([("parent_state", "=", "posted")], [], ["debit:sum", "credit:sum"])
deb, cred = r[0][0] or 0.0, r[0][1] or 0.0
print("   TB total debit  : Rp %s" % rp(deb))
print("   TB total credit : Rp %s" % rp(cred))
print("   diff            : Rp %s  -> %s" % (rp(deb - cred), "BALANCE" if abs(deb - cred) < 0.01 else "*** TIDAK BALANCE ***"))

D = env["geprekyukss.dashboard.data"]
bal = None
for label, d1, d2 in (("Juni 2026", "2026-06-01", "2026-06-30"),
                      ("Juli 2026", "2026-07-01", "2026-07-31"),
                      ("Agustus 2026", "2026-08-01", "2026-08-31"),
                      ("Mei 2026", "2026-05-01", "2026-05-31")):
    d = D.get_dashboard_data(d1, d2, None)
    f = d.get("finance") or {}
    b = f.get("balance") or {}
    s = d.get("summary") or {}
    if label == "Agustus 2026":
        bal = b
    print("   %-14s has_data=%-5s omzet=%14s | net_profit=%14s | assets=%14s" % (
        label, d.get("has_data"), rp(s.get("amount_total")).strip(),
        rp(f.get("net_profit")).strip(), rp(b.get("total_assets")).strip()))

sec("2. NERACA 31 AGUSTUS (identitas)")
if bal:
    print("   total_assets      : Rp %s" % rp(bal.get("total_assets")))
    print("   total_liab_equity : Rp %s" % rp(bal.get("total_liab_equity")))
    print("   selisih           : Rp %s  -> %s" % (
        rp((bal.get("total_assets") or 0) - (bal.get("total_liab_equity") or 0)),
        "BALANCE" if abs((bal.get("total_assets") or 0) - (bal.get("total_liab_equity") or 0)) < 0.01 else "*** TIDAK BALANCE ***"))
    print("   liabilities=%s | equity=%s | NI YTD=%s" % (
        rp(bal.get("liabilities")), rp(bal.get("equity")), rp(bal.get("net_income_ytd"))))

sec("3. JE OPENING & POSISI BULANAN")
for nm in ("MISC/2026/06/0001", "MISC/2026/06/0002", "MISC/2026/07/0001"):
    m = env["account.move"].search([("name", "=", nm)], limit=1)
    print("   %-20s %s | %s | %s baris" % (nm, m.date if m else "-", m.state if m else "-", len(m.line_ids) if m else 0))
modal = Acc.search([("code", "=", "3101.02")], limit=1)
for d in ("2026-05-31", "2026-06-30", "2026-07-31", "2026-08-31"):
    x = Aml._read_group([("account_id", "=", modal.id), ("parent_state", "=", "posted"), ("date", "<=", d)],
                        [], ["balance:sum"])
    print("   Modal Disetor per %s = Rp %s" % (d, rp(-(sum(y or 0.0 for y in x[0]) if x else 0.0))))

sec("4. BANK & KAS")
for a in Acc.search([("account_type", "=", "asset_cash")]):
    x = Aml._read_group([("account_id", "=", a.id), ("parent_state", "=", "posted")], [], ["balance:sum"])
    v = sum(y or 0.0 for y in x[0]) if x else 0.0
    if abs(v) >= 0.005 or a.active:
        print("   %-10s %-30s Rp %16s active=%s%s" % (
            a.code, a.name[:30], rp(v), a.active, "   <<< BERSALDO TAPI NONAKTIF" if (not a.active and abs(v) >= 0.005) else ""))

sec("5. FLAG HASH JOURNAL")
cr = env.cr
cr.execute("SELECT code, restrict_mode_hash_table FROM account_journal WHERE type IN ('sale','purchase','general') ORDER BY code")
for c, h in cr.fetchall():
    print("   %-8s hash=%s" % (c, h))
print("   journal bank/kas hash:", {j.code: j.restrict_mode_hash_table
                                    for j in J.search([("type", "in", ["bank", "cash"])])})

sec("6. AKTIVITAS JUNI/JULI (harus masih kosong kecuali JE opening)")
for label, d1, d2 in (("Juni", "2026-06-01", "2026-07-01"), ("Juli", "2026-07-01", "2026-08-01")):
    mv = env["account.move"].search_count([("date", ">=", d1), ("date", "<", d2), ("state", "=", "posted")])
    po = env["pos.order"].search_count([("date_order", ">=", d1), ("date_order", "<", d2)])
    print("   %-5s posted move=%d | pos.order=%d" % (label, mv, po))

print("\n[SELESAI — read-only]")
env.cr.rollback()
