# -*- coding: utf-8 -*-
"""recon_pl_discrepancy.py — Investigasi selisih P&L Agustus 2026 (READ-ONLY).

Latar: 2 laporan beda angka utk periode & outlet sama (Agustus 2026, semua outlet):
  - MIS Builder "Laba Rugi (Dashboard)"  : PENDAPATAN 226.117.212 / BEBAN 243.820.049
  - Dashboard Tab 1+2 (dashboard_data.py): Pendapatan ±229,6 jt / Beban 229.261.878

Skrip ini membandingkan 3 sumber dgn ground truth = account.move.line posted
(raw, tanpa custom logic) + cross-check Trial Balance engine AFR (jalur resmi
Accounting → Reporting → Trial Balance): RA.get_report_data("trial_balance").

Definisi masing-masing sumber (diekstrak, bukan diubah):
  1. Ground truth : AML posted Aug, dikelompokkan per account_type
                    (income/income_other = pendapatan; expense* = beban).
  2. MIS Builder  : instance geprekyukss_dashboard.mis_instance_pl via wrapper
                    get_report_data("profit_loss_mis") — ekspresi balp[] dengan
                    domain move line: account_type + EXCLUDE JE demo
                    ('|', ('move_id.ref','=',False), ('move_id.ref','not like','(demo)')).
  3. Dashboard    : D.get_dashboard_data("2026-08-01","2026-08-31",None)["finance"]
                    — account_type sama TANPA exclude JE demo.

Output akhir mengikuti format laporan investigasi (step 5 brief user).

Jalankan (odoo shell, pola §2 PROGRESS_DASHBOARD.md):
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db \
    --db_port 5432 --db_user odoo --db_password odoo" \
    < scripts/recon_pl_discrepancy.py
"""
from collections import defaultdict

D = env["geprekyukss.dashboard.data"]
RA = env["geprekyukss.dashboard.report.actions"]
Aml = env["account.move.line"]
# active_test=False: akun arsip tetap punya mutasi (temuan F2, kanonik Q1)
Account = env["account.account"].with_context(active_test=False)

D1, D2 = "2026-08-01", "2026-08-31"
INCOME_TYPES = ("income", "income_other")
EXPENSE_TYPES = ("expense", "expense_direct_cost", "expense_depreciation", "expense_gnrl_admin")
DEMO_DOM = ["|", ("move_id.ref", "=", False), ("move_id.ref", "not like", "(demo)")]
TOL = 0.01


def rp(v):
    return "{:,.2f}".format(float(v or 0.0)).replace(",", "X").replace(".", ",").replace("X", ".")


def aml_by_account(types, excl_demo):
    """Net per akun (debit-kredit) dari AML posted Aug; excl_demo=domain MIS."""
    accs = Account.search([("account_type", "in", list(types))])
    dom = [("date", ">=", D1), ("date", "<=", D2),
           ("parent_state", "=", "posted"), ("account_id", "in", accs.ids)]
    if excl_demo:
        dom = dom + DEMO_DOM
    m = {}
    for acc, debit, credit in Aml._read_group(dom, ["account_id"], ["debit:sum", "credit:sum"]):
        m[acc.id] = {"code": acc.code, "name": acc.name, "type": acc.account_type,
                     "net": (debit or 0.0) - (credit or 0.0)}
    return m


# ==================================================================
# 1) GROUND TRUTH — AML raw (posted) + cross-check TB AFR
# ==================================================================
print("=== 1) GROUND TRUTH: AML posted %s..%s (raw, tanpa custom logic) ===" % (D1, D2))
print("  db=%s | companies=%s | akun arsip=%d" % (
    env.cr.dbname, ", ".join(env.companies.mapped("name")),
    env["account.account"].search_count([("active", "=", False)])))

gt_inc = aml_by_account(INCOME_TYPES, excl_demo=False)
gt_exp = aml_by_account(EXPENSE_TYPES, excl_demo=False)
gt_income = -sum(r["net"] for r in gt_inc.values())
gt_expense = sum(r["net"] for r in gt_exp.values())
gt_hpp = sum(r["net"] for r in gt_exp.values() if r["type"] == "expense_direct_cost")
gt_dep = sum(r["net"] for r in gt_exp.values() if "penyusutan" in r["name"].lower())
print("  Pendapatan (income+other, kredit-debit) = %s" % rp(gt_income))
print("  Beban     (expense*, debit-kredit)       = %s" % rp(gt_expense))
print("  HPP       (expense_direct_cost)          = %s" % rp(gt_hpp))
print("  Penyusutan (nama ~ 'penyusutan')         = %s" % rp(gt_dep))
print("  breakdown pendapatan:")
for r in sorted(gt_inc.values(), key=lambda x: -x["net"]):
    print("    %s | %s | %s" % (r["code"], r["name"], rp(-r["net"])))
print("  breakdown beban:")
for r in sorted(gt_exp.values(), key=lambda x: -x["net"]):
    print("    %s | %-14s | %s | %s" % (r["code"], r["type"], r["name"], rp(r["net"])))

print("")
print("=== 1b) Cross-check Trial Balance (engine AFR, jalur native) ===")
tb = RA.get_report_data("trial_balance", {"date_from": D1, "date_to": D2, "outlet_ids": []})
tb_type = {a.code: a.account_type for a in Account.search([])}
tb_inc = tb_exp = 0.0
for r in tb["rows"]:
    t = tb_type.get(r["code"])
    if t in INCOME_TYPES:
        tb_inc += (r["credit"] - r["debit"])
    elif t and t.startswith("expense"):
        tb_exp += (r["debit"] - r["credit"])
print("  TB: akun=%d | Pendapatan=%s | Beban=%s" % (len(tb["rows"]), rp(tb_inc), rp(tb_exp)))
print("  TB vs AML raw: income delta=%s | expense delta=%s" % (
    rp(abs(tb_inc - gt_income)), rp(abs(tb_exp - gt_expense))))

# ==================================================================
# 2) MIS BUILDER — ekspresi KPI + angka via wrapper (jalur shell UI)
# ==================================================================
print("")
print("=== 2) MIS BUILDER: mis_instance_pl (Laba Rugi (Dashboard)) ===")
rep = env.ref("geprekyukss_dashboard.mis_report_pl")
for k in rep.kpi_ids.sorted("sequence"):
    print("  KPI %-12s | %-30s | %s" % (k.name, k.description, k.expression))
inst = env.ref("geprekyukss_dashboard.mis_instance_pl")
print("  target_move=%s | kolom:" % inst.target_move)
for p in inst.period_ids.sorted("sequence"):
    print("    %s: %s .. %s" % (p.name, p.date_from, p.date_to))

payload = RA.get_report_data("profit_loss_mis", {"date_from": D1, "date_to": D2, "outlet_ids": []})


def mis_get(label, col=0):
    for row in payload["body"]:
        if row["label"] == label:
            cells = row["cells"]
            return cells[col]["val"] if col < len(cells) else None
    return None


mis_income = mis_get("PENDAPATAN")
mis_expense = mis_get("BEBAN")
mis_hpp = mis_get("HPP (Harga Pokok Penjualan)")
mis_dep = mis_get("Beban Penyusutan")
mis_net = mis_get("LABA BERSIH")
print("  MIS (kolom Bulan): PENDAPATAN=%s | BEBAN=%s | HPP=%s | Dep=%s | NET=%s" % (
    rp(mis_income), rp(mis_expense), rp(mis_hpp), rp(mis_dep), rp(mis_net)))

# ==================================================================
# 3) DASHBOARD CUSTOM — _finance_detail via get_dashboard_data
# ==================================================================
print("")
print("=== 3) DASHBOARD CUSTOM: get_dashboard_data(%s, %s, None) ===" % (D1, D2))
dash = D.get_dashboard_data(D1, D2, None)
fin = dash["finance"]
dash_income = fin["income_total"]
dash_expense = fin["expense_total"]
dash_hpp = fin["hpp_total"]
dash_dep = fin["depreciation_total"]
print("  income_total    = %s" % rp(dash_income))
print("  expense_total   = %s" % rp(dash_expense))
print("  hpp_total       = %s" % rp(dash_hpp))
print("  depreciation    = %s" % rp(dash_dep))
print("  net_profit      = %s" % rp(fin["net_profit"]))
print("  Tab 1 'Total omzet' (pos.order amount_total, BUKAN akunting) = %s" % rp(dash["summary"]["amount_total"]))
print("  Draft include? TIDAK — semua query parent_state=posted (diverifikasi domain di kode).")

# ==================================================================
# 4) DRILL-DOWN — akun spesifik penyebab selisih
# ==================================================================
print("")
print("=== 4a) MIS vs Ground truth: per akun (efek exclude JE demo) ===")
mis_inc_map = aml_by_account(INCOME_TYPES, excl_demo=True)
mis_exp_map = aml_by_account(EXPENSE_TYPES, excl_demo=True)
demo_inc_rows, demo_exp_rows = [], []
for aid, g in gt_inc.items():
    m = mis_inc_map.get(aid, {}).get("net", 0.0)
    if abs((g["net"] - m)) > TOL:  # kontribusi pendapatan = -(net); delta = -(g-m) — pakai kontribusi agar positif
        demo_inc_rows.append((g["code"], g["name"], -(g["net"] - m)))
for aid, g in gt_exp.items():
    m = mis_exp_map.get(aid, {}).get("net", 0.0)
    if abs((g["net"] - m)) > TOL:  # kontribusi beban = net; delta = g-m
        demo_exp_rows.append((g["code"], g["name"], g["net"] - m))
print("  akun pendapatan terkena exclude demo (%d):" % len(demo_inc_rows))
for code, name, d in sorted(demo_inc_rows, key=lambda x: -abs(x[2])):
    print("    %s | %s | delta pendapatan = %s" % (code, name, rp(d)))
print("  akun beban terkena exclude demo (%d):" % len(demo_exp_rows))
for code, name, d in sorted(demo_exp_rows, key=lambda x: -abs(x[2])):
    print("    %s | %s | delta beban = %s" % (code, name, rp(d)))
inc_demo_total = sum(d for _, _, d in demo_inc_rows)
exp_demo_total = sum(d for _, _, d in demo_exp_rows)
print("  total efek demo: pendapatan %+s | beban %+s | net laba %+s" % (
    rp(inc_demo_total), rp(exp_demo_total), rp(inc_demo_total - exp_demo_total)))

print("")
print("=== 4b) JE demo Agustus (posted, ref ~ '(demo)') ===")
demo_moves = env["account.move"].search(
    [("ref", "like", "(demo)"), ("state", "=", "posted"),
     ("date", ">=", D1), ("date", "<=", D2)])
print("  jumlah JE: %d" % len(demo_moves))
for m in demo_moves:
    lines = m.line_ids.filtered(lambda l: l.account_id.account_type in INCOME_TYPES + EXPENSE_TYPES)
    inc_net = -sum((l.credit - l.debit) for l in lines if l.account_id.account_type in INCOME_TYPES)
    exp_net = sum((l.debit - l.credit) for l in lines if l.account_id.account_type.startswith("expense"))
    print("    %s | %s | %s | jurnal=%s | inc=%s exp=%s" % (
        m.name, m.date, (m.ref or "")[:40], m.journal_id.name, rp(inc_net), rp(exp_net)))

print("")
print("=== 4c) Dashboard vs Ground truth (harus 0 by construction — verifikasi) ===")
exp_list_codes = {e["code"] for e in fin["expenses"]}
raw_codes = {r["code"] for r in gt_exp.values()}
print("  akun beban di dashboard tapi tidak di raw: %s" % sorted(exp_list_codes - raw_codes))
print("  akun beban di raw tapi tidak di dashboard (|amt|<0.01 di-skip UI saja): %s" % sorted(raw_codes - exp_list_codes))
for cat, dash_v, gt_v in (("income", dash_income, gt_income), ("expense", dash_expense, gt_expense),
                          ("hpp", dash_hpp, gt_hpp), ("dep", dash_dep, gt_dep)):
    print("  %-8s dashboard=%s vs GT=%s | delta=%s" % (cat, rp(dash_v), rp(gt_v), rp(dash_v - gt_v)))

# ==================================================================
# 5) REKAP — format laporan investigasi
# ==================================================================
print("")
print("=== 5) REKAP (format laporan) ===")
print("  Ground truth (TB/AML raw, posted): Pendapatan=%s | Beban=%s | HPP=%s | Dep=%s" % (
    rp(gt_income), rp(gt_expense), rp(gt_hpp), rp(gt_dep)))
print("  TB AFR cross-check : Pendapatan=%s | Beban=%s (delta vs AML: %s / %s)" % (
    rp(tb_inc), rp(tb_exp), rp(abs(tb_inc - gt_income)), rp(abs(tb_exp - gt_expense))))
print("  MIS Builder        : Pendapatan=%s | Beban=%s | HPP=%s | Dep=%s | Net=%s" % (
    rp(mis_income), rp(mis_expense), rp(mis_hpp), rp(mis_dep), rp(mis_net)))
print("  Dashboard custom   : Pendapatan=%s | Beban=%s | HPP=%s | Dep=%s | Net=%s" % (
    rp(dash_income), rp(dash_expense), rp(dash_hpp), rp(dash_dep), rp(fin["net_profit"])))
print("")
print("  Selisih MIS    vs GT: income=%s | expense=%s (harus == total efek demo)" % (
    rp(mis_income - gt_income), rp(mis_expense - gt_expense)))
print("  Selisih Dash   vs GT: income=%s | expense=%s" % (
    rp(dash_income - gt_income), rp(dash_expense - gt_expense)))
print("  Efek exclude JE demo (dari drill-down): income=%s | expense=%s" % (
    rp(inc_demo_total), rp(exp_demo_total)))
print("")
print("RESULT: recon selesai (read-only)")
