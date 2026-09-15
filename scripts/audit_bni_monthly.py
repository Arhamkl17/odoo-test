# -*- coding: utf-8 -*-
"""Rekon BNI: move line per bulan + simulasi posisi kas/bank dgn date_to Juli.

Pertanyaan yang dijawab:
1. Kapan pertama kali ada move di akun kas/bank? (kalau semua mulai Agustus,
   maka pilihan bulan apapun di picker tidak mungkin menghasilkan minus)
2. Apa isi JE BNI per bulan (posted), biar ketahuan jejak konsolidasi Fase 3?
3. Simulasi payload dashboard untuk date_to = 31 Juli (placeholder) —
   apakah ada jalur yang menghasilkan saldo minus?
"""

Aml = env["account.move.line"]
Account = env["account.account"].with_context(active_test=False)

bni = Account.search([("name", "=ilike", "%BNI%"), ("account_type", "=", "asset_cash")])
print("BNI accounts:", [(a.id, a.name, a.code, a.active) for a in bni])

print("\n=== 1. Move line BNI per bulan (posted) ===")
for acc in bni:
    groups = Aml._read_group(
        [("account_id", "=", acc.id), ("parent_state", "=", "posted")],
        ["date:month"], ["debit:sum", "credit:sum"])
    print("\n%s (active=%s):" % (acc.name, acc.active))
    for month, deb, cred in groups:
        print("   %s  D %14.2f  K %14.2f  net %14.2f" % (month, deb or 0.0, cred or 0.0, (deb or 0.0) - (cred or 0.0)))

print("\n=== 2. Detail JE yang menyentuh BNI ===")
for acc in bni:
    lines = Aml.search([("account_id", "=", acc.id), ("parent_state", "=", "posted")], order="date, id")
    for l in lines:
        print("  %s | %-14s | %-24s | %-30s | D %12.2f K %12.2f" % (
            l.date, l.journal_id.code or "-", (l.move_id.name or "")[:24],
            (l.name or "")[:30], l.debit or 0.0, l.credit or 0.0))

print("\n=== 3. JE terakhir di seluruh buku (cek kronologi) ===")
last = Aml.search([("parent_state", "=", "posted"), ("account_id.account_type", "=", "asset_cash")],
                  order="date DESC, id DESC", limit=5)
for l in last:
    print("  %s | %s | %s" % (l.date, l.move_id.name, l.account_id.name))

print("\n=== 4. Simulasi posisi kas/bank dgn date_to = 31 Juli 2026 ===")
cash = Account.search([("account_type", "=", "asset_cash")])
dom = [("account_id", "in", cash.ids), ("parent_state", "=", "posted"), ("date", "<=", "2026-07-31")]
rows = Aml._read_group(dom, ["account_id"], ["debit:sum", "credit:sum"])
found = False
for acc, deb, cred in rows:
    bal = (deb or 0.0) - (cred or 0.0)
    if abs(bal) >= 0.01:
        found = True
        print("   %-38s %14.2f%s" % (acc.name, bal, "  <<< MINUS" if bal < 0 else ""))
if not found:
    print("   (kosong — tidak ada move kas/bank s.d. 31 Juli; dashboard harusnya placeholder)")

print("\n=== 5. Simulasi dgn date_to = 31 Agustus 2026 (kondisi sekarang) ===")
dom2 = [("account_id", "in", cash.ids), ("parent_state", "=", "posted"), ("date", "<=", "2026-08-31")]
rows2 = Aml._read_group(dom2, ["account_id"], ["debit:sum", "credit:sum"])
minus = 0
for acc, deb, cred in rows2:
    bal = (deb or 0.0) - (cred or 0.0)
    if abs(bal) >= 0.01:
        tag = "  <<< MINUS" if bal < 0 else ""
        minus += 1 if bal < 0 else 0
        print("   %-38s %14.2f%s" % (acc.name, bal, tag))
print("   total akun minus: %d" % minus)
