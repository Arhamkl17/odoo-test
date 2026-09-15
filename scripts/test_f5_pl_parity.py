# -*- coding: utf-8 -*-
"""F5(a) — Parity check: template MIS P&L vs _finance_detail vs ground truth.

Jalankan (odoo shell, pola resmi §2 PROGRESS_DASHBOARD.md):
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db \
    --db_port 5432 --db_user odoo --db_password odoo" \
    < scripts/test_f5_pl_parity.py

Prinsip (keputusan Q1 kanonik bertahap):
  MIS P&L harus menghasilkan angka yang IDENTIK dengan dashboard Tab 2
  (_finance_detail) dan ground truth (AML raw posted) — LANGSUNG, tanpa
  koreksi apa pun. (Fase 11, 12 Sep 2026: JE "(demo)" Fase 9 diklasifikasi
  ulang sebagai DATA REAL — marker "(demo)" dihapus dari move.ref; Q8
  demo-exclude dihapus dari template. Tidak ada lagi kebijakan exclude.)

Kelompok asersi:
  0. Invariant Fase 11: tidak ada JE ber-ref "(demo)" & tidak ada KPI MIS
     yang masih memuat domain demo-exclude.
  1. Struktur payload compute() — KPI, 2 kolom (Bulan + YTD), val_r, style.
  2. Bulan Agustus: income / expense / net / HPP / dep MIS == dashboard
     (_finance_detail) == ground truth AML raw (toleransi 0,01).
  3. YTD: income/expense/net MIS YTD == agregasi raw Jan–Aug.
  4. Margin % konsisten & net == income - expense.
  5. Jalur wrapper (get_report_data("profit_loss_mis")) — sinkronisasi
     periode manual via filter shell bekerja (kolom = filter).
"""
D = env["geprekyukss.dashboard.data"]
Aml = env["account.move.line"]
Account = env["account.account"].with_context(active_test=False)
RA = env["geprekyukss.dashboard.report.actions"]
fails = []


def check(name, cond, extra=""):
    if cond:
        print("  PASS %s %s" % (name, extra))
    else:
        print("  FAIL %s %s" % (name, extra))
    if not cond:
        fails.append(name)


D1, D2 = "2026-08-01", "2026-08-31"
Y1 = "2026-01-01"
INCOME_TYPES = ["income", "income_other"]
EXPENSE_TYPES = ["expense", "expense_direct_cost", "expense_depreciation", "expense_gnrl_admin"]


def _sum_grouped(dom, sign_credit):
    tot = 0.0
    for _acc, debit, credit in Aml._read_group(dom, ["account_id"], ["debit:sum", "credit:sum"]):
        tot += ((credit or 0.0) - (debit or 0.0)) if sign_credit else ((debit or 0.0) - (credit or 0.0))
    return tot


def raw_income(d1, d2):
    accs = Account.search([("account_type", "in", INCOME_TYPES)])
    return _sum_grouped([("date", ">=", d1), ("date", "<=", d2), ("parent_state", "=", "posted"),
                         ("account_id", "in", accs.ids)], True)


def raw_expense(d1, d2, types):
    accs = Account.search([("account_type", "in", types)])
    return _sum_grouped([("date", ">=", d1), ("date", "<=", d2), ("parent_state", "=", "posted"),
                         ("account_id", "in", accs.ids)], False)


def mis_get(kpi_desc, col_idx):
    """Nilai numerik KPI × kolom dari payload compute() resmi.

    Baris body di-key oleh label (= kpi.description) — as_dict() tidak
    membawa kpi.name (diverifikasi dari kpimatrix.py as_dict()).
    """
    for row in payload["body"]:
        if row["label"] == kpi_desc:
            cells = row["cells"]
            if col_idx >= len(cells):
                return None
            return cells[col_idx]["val"]
    return None


# ------------------------------------------------------------------
# 0) Invariant Fase 11 — JE "(demo)" = data real, filter sudah dihapus
# ------------------------------------------------------------------
print("=== 0) Invariant Fase 11 (demo = real) ===")
n_demo_ref = env["account.move"].search_count([("ref", "like", "(demo)")])
check("tidak ada JE dgn ref '(demo)'", n_demo_ref == 0, "(n=%d)" % n_demo_ref)
kpl = env.ref("geprekyukss_dashboard.mis_report_pl")
kbs = env.ref("geprekyukss_dashboard.mis_report_bs")
n_kpi_demo = sum(1 for k in env["mis.report.kpi"].search(
    [("report_id", "in", [kpl.id, kbs.id])]) if "(demo)" in (k.expression or ""))
check("tidak ada KPI MIS yg masih exclude demo", n_kpi_demo == 0, "(n=%d)" % n_kpi_demo)

# ------------------------------------------------------------------
# 1) Wrapper get_report_data + sinkron periode
# ------------------------------------------------------------------
print("=== 1) Wrapper get_report_data('profit_loss_mis') + sinkron periode ===")
payload = RA.get_report_data("profit_loss_mis", {"date_from": D1, "date_to": D2, "outlet_ids": []})
check("payload kind=matrix", payload.get("kind") == "matrix")
check("header 2 tingkat", len(payload.get("header") or []) == 2)
hdr2 = (payload.get("header") or [None, {}])[1]
cols2 = hdr2.get("cols") or []
check("2 kolom (Bulan + YTD)", len(cols2) == 2, str([c.get("label") for c in cols2]))
kpi_labels = [r["label"] for r in payload["body"]]
check("KPI income/expense/net ada", all(k in kpi_labels for k in ("PENDAPATAN", "BEBAN", "LABA BERSIH")),
      str(kpi_labels))
inst = env.ref("geprekyukss_dashboard.mis_instance_pl")
p1, p2 = inst.period_ids.sorted("sequence")[:2]
check("kolom 1 = filter shell (bulan)", str(p1.date_from) == D1 and str(p1.date_to) == D2,
      "(%s..%s)" % (p1.date_from, p1.date_to))
check("kolom 2 = YTD s.d. date_to", str(p2.date_from) == Y1 and str(p2.date_to) == D2,
      "(%s..%s)" % (p2.date_from, p2.date_to))

# ------------------------------------------------------------------
# 2) Bulan Agustus: MIS == dashboard == ground truth (langsung)
# ------------------------------------------------------------------
print("=== 2) Parity bulan Agustus (MIS == dashboard == ground truth) ===")
mis_income = mis_get("PENDAPATAN", 0)
mis_expense = mis_get("BEBAN", 0)
mis_net = mis_get("LABA BERSIH", 0)
mis_hpp = mis_get("HPP (Harga Pokok Penjualan)", 0)
mis_dep = mis_get("Beban Penyusutan", 0)

fin = D.get_dashboard_data(D1, D2, None)["finance"]
gt_income = raw_income(D1, D2)
gt_expense = raw_expense(D1, D2, EXPENSE_TYPES)

check("income parity (MIS == dashboard)", abs(mis_income - fin["income_total"]) <= 0.01,
      "(MIS %s vs dash %s)" % (round(mis_income, 2), round(fin["income_total"], 2)))
check("income parity (MIS == ground truth)", abs(mis_income - gt_income) <= 0.01,
      "(MIS %s vs GT %s)" % (round(mis_income, 2), round(gt_income, 2)))
check("expense parity (MIS == dashboard)", abs(mis_expense - fin["expense_total"]) <= 0.01,
      "(MIS %s vs dash %s)" % (round(mis_expense, 2), round(fin["expense_total"], 2)))
check("expense parity (MIS == ground truth)", abs(mis_expense - gt_expense) <= 0.01,
      "(MIS %s vs GT %s)" % (round(mis_expense, 2), round(gt_expense, 2)))
check("net parity", abs(mis_net - fin["net_profit"]) <= 0.01,
      "(MIS %s vs dash %s)" % (round(mis_net, 2), round(fin["net_profit"], 2)))
check("hpp parity", abs(mis_hpp - fin["hpp_total"]) <= 0.01,
      "(MIS %s vs dash %s)" % (round(mis_hpp, 2), round(fin["hpp_total"], 2)))
check("dep parity", abs(mis_dep - fin["depreciation_total"]) <= 0.01,
      "(MIS %s vs dash %s)" % (round(mis_dep, 2), round(fin["depreciation_total"], 2)))

# ------------------------------------------------------------------
# 3) YTD
# ------------------------------------------------------------------
print("=== 3) Parity YTD (Jan-Aug 2026) ===")
ytd_income_mis = mis_get("PENDAPATAN", 1)
ytd_income_base = raw_income(Y1, D2)
check("income YTD parity", abs(ytd_income_mis - ytd_income_base) <= 0.01,
      "(MIS %s vs base %s)" % (round(ytd_income_mis, 2), round(ytd_income_base, 2)))
ytd_exp_mis = mis_get("BEBAN", 1)
ytd_exp_base = raw_expense(Y1, D2, EXPENSE_TYPES)
check("expense YTD parity", abs(ytd_exp_mis - ytd_exp_base) <= 0.01,
      "(MIS %s vs base %s)" % (round(ytd_exp_mis, 2), round(ytd_exp_base, 2)))
ytd_net_mis = mis_get("LABA BERSIH", 1)
ytd_net_base = ytd_income_base - ytd_exp_base
check("net YTD parity", abs(ytd_net_mis - ytd_net_base) <= 0.01,
      "(MIS %s vs base %s)" % (round(ytd_net_mis, 2), round(ytd_net_base, 2)))

# ------------------------------------------------------------------
# 4) Konsistensi internal
# ------------------------------------------------------------------
print("=== 4) Konsistensi internal ===")
check("net == income - expense (bulan)", abs(mis_net - (mis_income - mis_expense)) <= 0.01)
check("margin == net/income*100 (bulan)",
      abs(mis_get("Margin Bersih (%)", 0) - (mis_net / mis_income * 100.0)) <= 0.01,
      "(%s)" % round(mis_get("Margin Bersih (%)", 0), 2))

print("")
print("Ringkasan (Agustus 2026):")
print("  MIS      : inc=%s exp=%s net=%s hpp=%s dep=%s" % (
    round(mis_income, 2), round(mis_expense, 2), round(mis_net, 2), round(mis_hpp, 2), round(mis_dep, 2)))
print("  dashboard: inc=%s exp=%s net=%s hpp=%s dep=%s" % (
    round(fin["income_total"], 2), round(fin["expense_total"], 2), round(fin["net_profit"], 2),
    round(fin["hpp_total"], 2), round(fin["depreciation_total"], 2)))
print("  YTD MIS  : inc=%s exp=%s net=%s" % (round(ytd_income_mis, 2), round(ytd_exp_mis, 2), round(ytd_net_mis, 2)))

print("")
if fails:
    print("RESULT: %d FAIL -> %s" % (len(fails), fails))
else:
    print("RESULT: ALL PASS")
