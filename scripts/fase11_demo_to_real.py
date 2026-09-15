# -*- coding: utf-8 -*-
"""Fase 11 — Reklasifikasi JE "(demo)" Fase 9 menjadi DATA REAL (write, user-approved).

Latar (keputusan user 12 Sep 2026):
  5 JE MISC/2026/08/0058–0062 (ref mengandung "(demo)") sebenarnya ADJUSTMENT
  REAL untuk perbaikan profit — JE gaji book-lah yang dummy. Karena itu:
  1. Data  : hapus marker "(demo)" dari move.ref (bukti Fase 9 pada jurnal,
             nama line, & chatter TIDAK disentuh — entri sudah ter-hash oleh
             integritas journal "Operasi Lain-lain"; ref bukan field hash,
             jadi legal & tidak memicu re-hash/re-queue). Idempotent.
  2. Template: kebijakan Q8 "exclude demo" DIBATALKAN — 9 ekspresi KPI MIS
             (4 P&L + 5 Neraca) di-sync di DB menjadi versi TANPA domain
             demo-exclude (noupdate="True" → -u tidak meng-update; temuan F5a).
  3. Verifikasi: P&L MIS harus == ground truth AML raw (delta 0,01) dan
             == _finance_detail; Neraca tetap self-balancing.

Hasil angka yang diharapkan (Agustus 2026):
  PENDAPATAN 240.293.763,00 | BEBAN 229.261.878,29 | NET +11.031.884,71

Jalankan (odoo shell, pola §2 PROGRESS_DASHBOARD.md):
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db \
    --db_port 5432 --db_user odoo --db_password odoo" \
    < scripts/fase11_demo_to_real.py
"""
D = env["geprekyukss.dashboard.data"]
Aml = env["account.move.line"]
Account = env["account.account"].with_context(active_test=False)

D1, D2 = "2026-08-01", "2026-08-31"
INCOME_TYPES = ("income", "income_other")
EXPENSE_TYPES = ("expense", "expense_direct_cost", "expense_depreciation", "expense_gnrl_admin")
TOL = 0.01


def rp(v):
    return "{:,.2f}".format(float(v or 0.0)).replace(",", "X").replace(".", ",").replace("X", ".")


fails = []


def check(name, cond, extra=""):
    print(("  PASS %s %s" if cond else "  FAIL %s %s") % (name, extra))
    if not cond:
        fails.append(name)


def gt_totals():
    """Ground truth: agregasi AML posted Aug per kategori (tanpa filter apa pun)."""
    inc = exp = 0.0
    for types, sign in ((INCOME_TYPES, "cr"), (EXPENSE_TYPES, "dr")):
        accs = Account.search([("account_type", "in", list(types))])
        for _acc, debit, credit in Aml._read_group(
                [("date", ">=", D1), ("date", "<=", D2), ("parent_state", "=", "posted"),
                 ("account_id", "in", accs.ids)],
                ["account_id"], ["debit:sum", "credit:sum"]):
            if sign == "cr":
                inc += (credit or 0.0) - (debit or 0.0)
            else:
                exp += (debit or 0.0) - (credit or 0.0)
    return inc, exp


def mis_get(payload, label, col=0):
    for row in payload["body"]:
        if row["label"] == label:
            cells = row["cells"]
            return cells[col]["val"] if col < len(cells) else None
    return None


# ------------------------------------------------------------------
# 0) State sebelum
# ------------------------------------------------------------------
print("=== 0) State sebelum ===")
demo_moves = env["account.move"].search([("ref", "like", "(demo)")])
print("  JE dgn ref '(demo)' (semua state): %d" % len(demo_moves))
for m in demo_moves:
    print("    %s | %s | %s | %s" % (m.name, m.date, m.state, m.ref))
demo_lines = env["account.move.line"].search([("move_id", "in", demo_moves.ids)])
n_demo_names = sum(1 for l in demo_lines if "(demo)" in (l.name or ""))
print("  line dgn nama '(demo)': %d dari %d" % (n_demo_names, len(demo_lines)))

RA = env["geprekyukss.dashboard.report.actions"]
for kpi in env["mis.report.kpi"].search([("report_id", "in", [
        env.ref("geprekyukss_dashboard.mis_report_pl").id,
        env.ref("geprekyukss_dashboard.mis_report_bs").id])]):
    if "(demo)" in (kpi.expression or ""):
        print("  KPI %-10s (masih exclude demo): %s" % (kpi.name, (kpi.expression or "")[-60:]))

# ------------------------------------------------------------------
# 1) DATA FIX — strip "(demo)" dari ref & nama line (idempotent)
# ------------------------------------------------------------------
print("")
print("=== 1) DATA FIX: hapus marker '(demo)' dari move.ref ===")
if not demo_moves:
    print("  Tidak ada JE '(demo)' — sudah pernah dibersihkan (idempotent), skip.")
else:
    for m in demo_moves:
        old_ref = m.ref
        new_ref = old_ref.replace("(demo)", "").strip()
        m.write({"ref": new_ref})
        print("    %s: ref '%s' -> '%s' (nama line ter-hash tidak disentuh)" % (
            m.name, old_ref, new_ref))
    n_left = env["account.move"].search_count([("ref", "like", "(demo)")])
    check("tidak ada sisa ref '(demo)'", n_left == 0, "(sisa=%d)" % n_left)

# ------------------------------------------------------------------
# 2) TEMPLATE SYNC — 9 KPI MIS jadi versi demo-include (tanpa domain demo)
# ------------------------------------------------------------------
print("")
print("=== 2) Sync ekspresi KPI MIS (noupdate=True → sinkron manual) ===")
NEW_EXPR = {
    "geprekyukss_dashboard.mis_kpi_pl_income":
        "-balp[][('account_type', 'in', ('income', 'income_other'))]",
    "geprekyukss_dashboard.mis_kpi_pl_expense":
        "balp[][('account_type', 'in', ('expense', 'expense_direct_cost', 'expense_depreciation', 'expense_gnrl_admin'))]",
    "geprekyukss_dashboard.mis_kpi_pl_hpp":
        "balp[][('account_type', '=', 'expense_direct_cost')]",
    "geprekyukss_dashboard.mis_kpi_pl_dep":
        "balp[][('account_type', 'in', ('expense', 'expense_direct_cost', 'expense_depreciation', 'expense_gnrl_admin')), ('account_id.name', 'ilike', 'penyusutan')]",
    "geprekyukss_dashboard.mis_kpi_bs_assets":
        "bale[][('account_type', 'in', ('asset_cash', 'asset_receivable', 'asset_current', 'asset_prepayments', 'asset_fixed'))]",
    "geprekyukss_dashboard.mis_kpi_bs_liabilities":
        "-bale[][('account_type', 'in', ('liability_payable', 'liability_current'))]",
    "geprekyukss_dashboard.mis_kpi_bs_equity":
        "-bale[][('account_type', 'in', ('equity', 'equity_unaffected'))]",
    "geprekyukss_dashboard.mis_kpi_bs_retained":
        "-balu[]",
    "geprekyukss_dashboard.mis_kpi_bs_ni_ytd":
        "-balp[][('account_type', 'in', ('income', 'income_other', 'expense', 'expense_direct_cost', 'expense_depreciation', 'expense_gnrl_admin'))]",
}
for xmlid, expr in NEW_EXPR.items():
    kpi = env.ref(xmlid)
    if (kpi.expression or "") == expr:
        print("    %-42s sudah sinkron" % xmlid.split(".")[-1])
        continue
    kpi.write({"expression": expr})
    print("    %-42s DI-UPDATE" % xmlid.split(".")[-1])

kpi_ids_pl_bs = env["mis.report.kpi"].search(
    [("report_id", "in", [env.ref("geprekyukss_dashboard.mis_report_pl").id,
                          env.ref("geprekyukss_dashboard.mis_report_bs").id])])
n_kpi_demo = sum(1 for k in kpi_ids_pl_bs if "(demo)" in (k.expression or ""))
check("tidak ada KPI MIS yg masih exclude demo", n_kpi_demo == 0, "(sisa=%d)" % n_kpi_demo)

# ------------------------------------------------------------------
# 3) VERIFIKASI — P&L MIS vs ground truth vs dashboard; Neraca balance
# ------------------------------------------------------------------
print("")
print("=== 3) Verifikasi: 3 sumber harus identik (JE demo = real) ===")
gt_inc, gt_exp = gt_totals()
print("  Ground truth : Pendapatan=%s | Beban=%s | Net=%s" % (
    rp(gt_inc), rp(gt_exp), rp(gt_inc - gt_exp)))

pl = RA.get_report_data("profit_loss_mis", {"date_from": D1, "date_to": D2, "outlet_ids": []})
mis_inc = mis_get(pl, "PENDAPATAN")
mis_exp = mis_get(pl, "BEBAN")
mis_hpp = mis_get(pl, "HPP (Harga Pokok Penjualan)")
mis_dep = mis_get(pl, "Beban Penyusutan")
mis_net = mis_get(pl, "LABA BERSIH")
print("  MIS P&L      : Pendapatan=%s | Beban=%s | HPP=%s | Dep=%s | Net=%s" % (
    rp(mis_inc), rp(mis_exp), rp(mis_hpp), rp(mis_dep), rp(mis_net)))
check("MIS income == GT", abs(mis_inc - gt_inc) <= TOL, "(delta %s)" % rp(mis_inc - gt_inc))
check("MIS expense == GT", abs(mis_exp - gt_exp) <= TOL, "(delta %s)" % rp(mis_exp - gt_exp))

fin = D.get_dashboard_data(D1, D2, None)["finance"]
print("  Dashboard    : income=%s | expense=%s | hpp=%s | dep=%s | net=%s" % (
    rp(fin["income_total"]), rp(fin["expense_total"]), rp(fin["hpp_total"]),
    rp(fin["depreciation_total"]), rp(fin["net_profit"])))
check("dashboard income == GT", abs(fin["income_total"] - gt_inc) <= TOL)
check("dashboard expense == GT", abs(fin["expense_total"] - gt_exp) <= TOL)
check("MIS net == dashboard net == GT net",
      abs(mis_net - fin["net_profit"]) <= TOL and abs(fin["net_profit"] - (gt_inc - gt_exp)) <= TOL)

bs = RA.get_report_data("balance_sheet_mis", {"date_from": D1, "date_to": D2, "outlet_ids": []})
diff1 = mis_get(bs, "Selisih (harus 0)", 0) or 0.0
ni_bs = mis_get(bs, "Laba (Rugi) Tahun Berjalan", 0) or 0.0
check("Neraca self-balancing kolom 1", abs(diff1) <= TOL, "(selisih %s)" % rp(diff1))
check("NI Neraca == Laba Bersih P&L YTD",
      abs(ni_bs - (mis_get(pl, "LABA BERSIH", 1) or 0.0)) <= TOL,
      "(BS %s vs P&L %s)" % (rp(ni_bs), rp(mis_get(pl, "LABA BERSIH", 1))))

# ------------------------------------------------------------------
# 4) COMMIT
# ------------------------------------------------------------------
print("")
if fails:
    print("RESULT: %d FAIL -> TIDAK commit (transaksi di-rollback). Perbaiki dulu." % len(fails))
    env.cr.rollback()
    for f in fails:
        print("  - %s" % f)
else:
    env.cr.commit()
    print("COMMITTED Fase 11: marker '(demo)' dihapus dari ref 5 JE + 9 KPI MIS jadi demo-include.")
    print("  P&L Agustus final: Pendapatan %s | Beban %s | Laba %s" % (
        rp(mis_inc), rp(mis_exp), rp(mis_net)))
