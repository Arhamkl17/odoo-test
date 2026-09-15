# -*- coding: utf-8 -*-
"""Cek cepat: apakah Fase 12 ter-commit atau ter-rollback?"""
Aml = env["account.move.line"]
Account = env["account.account"].with_context(active_test=False)
for name in ("Bank BNI", "Bank BSI"):
    acc = Account.search([("name", "=", name)], limit=1)
    res = Aml._read_group([("account_id", "=", acc.id), ("parent_state", "=", "posted")],
                          ["account_id"], ["debit:sum", "credit:sum"])
    b = (res[0][1] or 0.0) - (res[0][2] or 0.0) if res else 0.0
    print("%s: %.2f" % (name, b))
mall = Account.search([("name", "=", "Bank Mallengkeri")], limit=1)
print("Bank Mallengkeri active =", mall.active)
