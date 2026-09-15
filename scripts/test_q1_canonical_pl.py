# -*- coding: utf-8 -*-
"""test_q1_canonical_pl.py — Refactor kanonik Q1 opsi (a) READ-ONLY.

Verifikasi: headline P&L Tab 2 (dashboard_data.py::_finance_detail) kini
didelegasikan ke compute MIS Builder (via get_report_data wrapper — jalur
shell UI). Semua sumber harus identik dgn ground truth AML raw posted:

  A. finance headline == MIS payload (jalur wrapper)        — kanonik by design
  B. finance headline == ground truth AML raw + TB AFR      — benar scr akuntansi
  C. breakdown expenses (raw per akun) == headline expense  — konsistensi internal
  D. balance identity: assets == liab + equity + NI YTD     — neraca seimbang
  E. sparkline harian: Σ(daily) == net_profit (residual ke date_to)
  F. prev period (Juli): net_profit_prev == Juli net — UPDATE 15 Sep:
     premise lama "Juli kosong" basi, dataset 72 hari (Jun-Aug) diimpor
  G. Juli payload: has_data True + YTD konsisten — UPDATE 15 Sep (idem)

Jalankan (odoo shell, pola §2 PROGRESS_DASHBOARD.md):
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db \
    --db_port 5432 --db_user odoo --db_password odoo" \
    < scripts/test_q1_canonical_pl.py
"""
from collections import defaultdict

D = env["geprekyukss.dashboard.data"]
RA = env["geprekyukss.dashboard.report.actions"]
Aml = env["account.move.line"]
Account = env["account.account"].with_context(active_test=False)

D1, D2 = "2026-08-01", "2026-08-31"
INCOME_TYPES = ("income", "income_other")
EXPENSE_TYPES = ("expense", "expense_direct_cost", "expense_depreciation", "expense_gnrl_admin")
TOL = 0.01
fails = []


def check(name, cond, extra=""):
    print(("  PASS %s %s" if cond else "  FAIL %s %s") % (name, extra))
    if not cond:
        fails.append(name)


def gt_totals(d1, d2):
    inc = exp = hpp = 0.0
    accs_inc = Account.search([("account_type", "in", list(INCOME_TYPES))])
    for _a, debit, credit in Aml._read_group(
            [("date", ">=", d1), ("date", "<=", d2), ("parent_state", "=", "posted"),
             ("account_id", "in", accs_inc.ids)], ["account_id"], ["debit:sum", "credit:sum"]):
        inc += (credit or 0.0) - (debit or 0.0)
    accs_exp = Account.search([("account_type", "in", list(EXPENSE_TYPES))])
    for acc, debit, credit in Aml._read_group(
            [("date", ">=", d1), ("date", "<=", d2), ("parent_state", "=", "posted"),
             ("account_id", "in", accs_exp.ids)], ["account_id"], ["debit:sum", "credit:sum"]):
        net = (debit or 0.0) - (credit or 0.0)
        exp += net
        if acc.account_type == "expense_direct_cost":
            hpp += net
    return inc, exp, hpp


# ------------------------------------------------------------------
print("=== A) finance == MIS payload (jalur wrapper) ===")
fin = D.get_dashboard_data(D1, D2, None)["finance"]
pl = RA.get_report_data("profit_loss_mis", {"date_from": D1, "date_to": D2, "outlet_ids": []})


def mis_val(label, col=0):
    for row in pl["body"]:
        if row["label"] == label:
            return (row["cells"][col]["val"] or 0.0) if col < len(row["cells"]) else 0.0
    return 0.0


pairs = [
    ("income_total", mis_val("PENDAPATAN")),
    ("expense_total", mis_val("BEBAN")),
    ("hpp_total", mis_val("HPP (Harga Pokok Penjualan)")),
    ("depreciation_total", mis_val("Beban Penyusutan")),
    ("net_profit", mis_val("LABA BERSIH")),
    ("net_profit_ytd", mis_val("LABA BERSIH", 1)),
]
for key, misv in pairs:
    check("finance.%s == MIS" % key, abs(fin[key] - misv) <= TOL,
          "(%s vs %s)" % (round(fin[key], 2), round(misv, 2)))

# ------------------------------------------------------------------
print("=== B) finance == ground truth (AML raw + TB AFR) ===")
gt_inc, gt_exp, gt_hpp = gt_totals(D1, D2)
gt_dep = 0.0
accs_exp = Account.search([("account_type", "in", list(EXPENSE_TYPES))])
for acc, debit, credit in Aml._read_group(
        [("date", ">=", D1), ("date", "<=", D2), ("parent_state", "=", "posted"),
         ("account_id", "in", accs_exp.ids)], ["account_id"], ["debit:sum", "credit:sum"]):
    if "penyusutan" in acc.name.lower():
        gt_dep += (debit or 0.0) - (credit or 0.0)
check("income == GT", abs(fin["income_total"] - gt_inc) <= TOL, "(%s vs %s)" % (round(fin["income_total"], 2), round(gt_inc, 2)))
check("expense == GT", abs(fin["expense_total"] - gt_exp) <= TOL, "(%s vs %s)" % (round(fin["expense_total"], 2), round(gt_exp, 2)))
check("hpp == GT", abs(fin["hpp_total"] - gt_hpp) <= TOL)
check("dep == GT", abs(fin["depreciation_total"] - gt_dep) <= TOL)
check("net == GT net", abs(fin["net_profit"] - (gt_inc - gt_exp)) <= TOL)
# UPDATE 15 Sep: YTD = FY 2026 s.d. date_to (Jan-Agu), bukan window bulan —
# premise lama "Jan-Jul kosong" basi sejak dataset 72 hari diimpor.
gt_inc_ytd, gt_exp_ytd, _gt_hpp_ytd = gt_totals("2026-01-01", D2)
check("NI ytd == GT ytd (FY s.d. Agu)", abs(fin["balance"]["net_income_ytd"] - (gt_inc_ytd - gt_exp_ytd)) <= TOL,
      "(%s vs %s)" % (round(fin["balance"]["net_income_ytd"], 2), round(gt_inc_ytd - gt_exp_ytd, 2)))

tb = RA.get_report_data("trial_balance", {"date_from": D1, "date_to": D2, "outlet_ids": []})
tb_type = {a.code: a.account_type for a in Account.search([])}
tb_inc = tb_exp = 0.0
for r in tb["rows"]:
    t = tb_type.get(r["code"])
    if t in INCOME_TYPES:
        tb_inc += r["credit"] - r["debit"]
    elif t and t.startswith("expense"):
        tb_exp += r["debit"] - r["credit"]
check("income == TB AFR", abs(fin["income_total"] - tb_inc) <= TOL)
check("expense == TB AFR", abs(fin["expense_total"] - tb_exp) <= TOL)

# ------------------------------------------------------------------
print("=== C) breakdown raw per akun == headline ===")
sum_exp_rows = sum(e["amount"] for e in fin["expenses"])
sum_hpp_rows = sum(e["amount"] for e in fin["expenses"] if e["category"] == "hpp")
check("Σ(expenses) == expense_total", abs(sum_exp_rows - fin["expense_total"]) <= TOL,
      "(%s vs %s)" % (round(sum_exp_rows, 2), round(fin["expense_total"], 2)))
check("Σ(hpp rows) == hpp_total", abs(sum_hpp_rows - fin["hpp_total"]) <= TOL)

# ------------------------------------------------------------------
print("=== D) Neraca seimbang ===")
bal = fin["balance"]
check("assets == liab+equity+NI", abs(bal["total_assets"] - bal["total_liab_equity"]) <= 0.05,
      "(%s vs %s)" % (round(bal["total_assets"], 2), round(bal["total_liab_equity"], 2)))

# ------------------------------------------------------------------
print("=== E) Sparkline harian konsisten dgn headline ===")
daily_sum = sum(r["value"] for r in fin["daily_net_profit"])
check("Σ(daily_net_profit) == net_profit", abs(daily_sum - fin["net_profit"]) <= TOL,
      "(%s vs %s)" % (round(daily_sum, 2), round(fin["net_profit"], 2)))

# ------------------------------------------------------------------
print("=== F) Prev (Juli 2026 — ADA DATA; premise 'Juli kosong' basi) ===")
jul_prev_f = D.get_dashboard_data("2026-07-01", "2026-07-31", None)["finance"]
check("net_profit_prev == Juli net", abs(fin["net_profit_prev"] - jul_prev_f["net_profit"]) <= TOL,
      "(%s vs %s)" % (round(fin["net_profit_prev"], 2), round(jul_prev_f["net_profit"], 2)))
check("hpp_prev == Juli hpp", abs(fin["hpp_prev"] - jul_prev_f["hpp_total"]) <= TOL,
      "(%s vs %s)" % (round(fin["hpp_prev"], 2), round(jul_prev_f["hpp_total"], 2)))

# ------------------------------------------------------------------
print("=== G) Payload Juli: ada data (UPDATE 15 Sep — dataset 72 hari) ===")
jul = D.get_dashboard_data("2026-07-01", "2026-07-31", None)
check("Juli has_data True", jul["has_data"] is True)
check("Juli income_total > 0", jul["finance"]["income_total"] > TOL, "(%s)" % round(jul["finance"]["income_total"], 2))
check("Juli net_profit > 0", jul["finance"]["net_profit"] > TOL, "(%s)" % round(jul["finance"]["net_profit"], 2))
gt_inc_jytd, gt_exp_jytd, _ = gt_totals("2026-01-01", "2026-07-31")
check("Juli NI ytd == GT FY s.d. Juli", abs(jul["finance"]["balance"]["net_income_ytd"] - (gt_inc_jytd - gt_exp_jytd)) <= TOL,
      "(%s vs %s)" % (round(jul["finance"]["balance"]["net_income_ytd"], 2), round(gt_inc_jytd - gt_exp_jytd, 2)))

print("")
print("Ringkasan (Agustus 2026):")
print("  income=%s expense=%s net=%s | ytd net=%s | prev net=%s" % (
    round(fin["income_total"], 2), round(fin["expense_total"], 2), round(fin["net_profit"], 2),
    round(fin["net_profit_ytd"], 2), round(fin["net_profit_prev"], 2)))
print("")
if fails:
    print("RESULT: %d FAIL -> %s" % (len(fails), fails))
else:
    print("RESULT: ALL PASS")
