# -*- coding: utf-8 -*-
"""Verifikasi pasca-Fase 12 lewat jalur dashboard asli + integritas buku."""
D = env["geprekyukss.dashboard.data"]

pay = D.get_dashboard_data("2026-08-01", "2026-08-31")
f = pay["finance"]
print("=== Kartu kas & bank (payload dashboard, Agustus) ===")
for p in f["cash_positions"]:
    flag = "  <<< MINUS!" if p["balance"] < 0 else ""
    print("  %-30s %-8s %14.2f%s" % (p["name"], p["kind"], p["balance"], flag))

print("\n=== Invariant buku ===")
print("  neraca balance (assets vs liab+eq) :", f["balance"]["total_assets"],
      "vs", f["balance"]["total_liab_equity"])
print("  selisih                            : %.2f" % (f["balance"]["total_assets"] - f["balance"]["total_liab_equity"]))

Account = env["account.account"].with_context(active_test=False)
Aml = env["account.move.line"]
res = Aml._read_group([("parent_state", "=", "posted")], [], ["debit:sum", "credit:sum"])
tb = (res[0][0] or 0.0) - (res[0][1] or 0.0) if res else 0.0
print("  trial balance seluruh buku (D-K)   : %.2f" % tb)
print("  akun kas/bank aktif tersisa        :",
      [a.name for a in Account.search([("account_type", "=", "asset_cash")])])
