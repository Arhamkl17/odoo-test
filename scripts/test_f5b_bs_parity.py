# -*- coding: utf-8 -*-
"""F5(b) — Parity check: template MIS Neraca vs Tab 2 finance.balance.

Jalankan (odoo shell, pola resmi §2 PROGRESS_DASHBOARD.md):
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db \
    --db_port 5432 --db_user odoo --db_password odoo" \
    < scripts/test_f5b_bs_parity.py

Metodologi (Fase 11, 12 Sep 2026): JE "(demo)" Fase 9 diklasifikasi ulang
sebagai DATA REAL — marker "(demo)" dihapus dari move.ref, Q8 demo-exclude
dihapus dari template. Baseline Tab 2 dan MIS kini mengukur hal yang sama:
parity LANGSUNG tanpa koreksi net-demo (koreksi versi lama tidak berlaku).

Window kolom MIS = tahun fiskal (1 Jan → akhir bulan) sehingga balp kolom
= NI YTD (selaras _net_income(ytd_from, date_to) Tab 2). Kolom 1 = akhir
bulan filter; kolom 2 = akhir bulan lalu (neraca = posisi per tanggal).
"""
D = env["geprekyukss.dashboard.data"]
Aml = env["account.move.line"]
Account = env["account.account"].with_context(active_test=False)
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
PREV_D2 = "2026-07-31"
ASSET_TYPES = ["asset_cash", "asset_receivable", "asset_current", "asset_prepayments", "asset_fixed"]
LIAB_TYPES = ["liability_payable", "liability_current"]
EQUITY_TYPES = ["equity", "equity_unaffected"]
PL_TYPES = ["income", "income_other", "expense", "expense_direct_cost",
            "expense_depreciation", "expense_gnrl_admin"]


def _sum_grouped(dom):
    """Σ(dr − cr) atas domain."""
    tot = 0.0
    for _acc, debit, credit in Aml._read_group(dom, ["account_id"], ["debit:sum", "credit:sum"]):
        tot += (debit or 0.0) - (credit or 0.0)
    return tot


def base_ending(d2, types):
    """Σ(dr−cr) kumulatif s.d. d2 (ending, gaya bale)."""
    accs = Account.search([("account_type", "in", types)])
    dom = [("date", "<=", d2), ("parent_state", "=", "posted"),
           ("account_id", "in", accs.ids)]
    return _sum_grouped(dom)


def base_pl(d1, d2):
    """Σ(dr−cr) P&L accounts dalam window (gaya balp)."""
    accs = Account.search([("account_type", "in", PL_TYPES)])
    dom = [("date", ">=", d1), ("date", "<=", d2), ("parent_state", "=", "posted"),
           ("account_id", "in", accs.ids)]
    return _sum_grouped(dom)


def mis_get(kpi_desc, col_idx):
    for row in payload["body"]:
        if row["label"] == kpi_desc:
            cells = row["cells"]
            if col_idx >= len(cells):
                return None
            return cells[col_idx]["val"]
    return None


def mis_get0(kpi_desc, col_idx):
    """mis_get dgn default 0.0 — sel AccountingNone (window tanpa mutasi)
    bernilai 0 dalam identitas neraca, sama dgn konvensi Tab 2 (Σ kosong=0)."""
    v = mis_get(kpi_desc, col_idx)
    return 0.0 if v is None else v


# ------------------------------------------------------------------
# 0) Invariant Fase 11 — JE "(demo)" = data real, filter sudah dihapus
# ------------------------------------------------------------------
print("=== 0) Invariant Fase 11 (demo = real) ===")
RA = env["geprekyukss.dashboard.report.actions"]
n_demo_ref = env["account.move"].search_count([("ref", "like", "(demo)")])
check("tidak ada JE dgn ref '(demo)'", n_demo_ref == 0, "(n=%d)" % n_demo_ref)
kpl = env.ref("geprekyukss_dashboard.mis_report_pl")
kbs = env.ref("geprekyukss_dashboard.mis_report_bs")
n_kpi_demo = sum(1 for k in env["mis.report.kpi"].search(
    [("report_id", "in", [kpl.id, kbs.id])]) if "(demo)" in (k.expression or ""))
check("tidak ada KPI MIS yg masih exclude demo", n_kpi_demo == 0, "(n=%d)" % n_kpi_demo)

# ------------------------------------------------------------------
# 1) Wrapper get_report_data('balance_sheet_mis') + sinkron periode
# ------------------------------------------------------------------
print("=== 1) Wrapper get_report_data('balance_sheet_mis') + sinkron periode ===")
payload = RA.get_report_data("balance_sheet_mis", {"date_from": D1, "date_to": D2, "outlet_ids": []})
check("payload kind=matrix", payload.get("kind") == "matrix")
hdr2 = (payload.get("header") or [None, {}])[1]
cols2 = hdr2.get("cols") or []
check("2 kolom pembanding", len(cols2) == 2, str([c.get("label") for c in cols2]))
labels = [r["label"] for r in payload["body"]]
check("7 baris KPI ada", all(k in labels for k in (
    "TOTAL ASET", "Total Kewajiban", "Total Ekuitas",
    "Laba Ditahan (sblm thn berjalan)", "Laba (Rugi) Tahun Berjalan",
    "KEWAJIBAN + EKUITAS", "Selisih (harus 0)")), str(labels))
inst = env.ref("geprekyukss_dashboard.mis_instance_bs")
p1, p2 = inst.period_ids.sorted("sequence")[:2]
check("kolom 1 window FY s.d. date_to", str(p1.date_from) == Y1 and str(p1.date_to) == D2,
      "(%s..%s)" % (p1.date_from, p1.date_to))
check("kolom 2 window FY s.d. akhir bulan lalu", str(p2.date_from) == Y1 and str(p2.date_to) == PREV_D2,
      "(%s..%s)" % (p2.date_from, p2.date_to))

# ------------------------------------------------------------------
# 2) Parity kolom 1 — akhir Agustus (MIS vs Tab 2, langsung)
# ------------------------------------------------------------------
print("=== 2) Parity kolom 1 (per 2026-08-31) ===")
bal = D.get_dashboard_data(D1, D2, None)["finance"]["balance"]
exp_assets = bal["total_assets"]
exp_liab = bal["liabilities"]
exp_equity = bal["equity"]
exp_ni = bal["net_income_ytd"]
mis_assets = mis_get("TOTAL ASET", 0)
mis_liab = mis_get("Total Kewajiban", 0)
mis_equity = mis_get("Total Ekuitas", 0)
mis_ni = mis_get("Laba (Rugi) Tahun Berjalan", 0)
mis_retained = mis_get("Laba Ditahan (sblm thn berjalan)", 0)
# UPDATE 15 Sep: NULL-coerce semua sel — dgn dataset 72 hari kewajiban = 0,
# akun ber-saldo float_is_zero di-skip do_queries (MODE_UNALLOCATED) →
# AccountingNone → val None. Semantik neraca: sel kosong = 0 (konvensi
# yang sama dgn mis_get0 di kolom 2 & mis_retained di bawah).
mis_assets = 0.0 if mis_assets is None else mis_assets
mis_liab = 0.0 if mis_liab is None else mis_liab
mis_equity = 0.0 if mis_equity is None else mis_equity
mis_ni = 0.0 if mis_ni is None else mis_ni
if mis_retained is None:
    # balu dgn saldo 0: do_queries skip akun float_is_zero di MODE_UNALLOCATED
    # → AccountingNone → val None. Semantik: retained = 0 (belum ada tutup buku).
    mis_retained = 0.0
check("assets parity", abs(mis_assets - exp_assets) <= 0.01,
      "(MIS %s vs Tab2 %s)" % (round(mis_assets, 2), round(exp_assets, 2)))
check("liabilities parity", abs(mis_liab - exp_liab) <= 0.01,
      "(MIS %s vs Tab2 %s)" % (round(mis_liab, 2), round(exp_liab, 2)))
check("equity parity", abs(mis_equity - exp_equity) <= 0.01,
      "(MIS %s vs Tab2 %s)" % (round(mis_equity, 2), round(exp_equity, 2)))
check("NI YTD parity", abs(mis_ni - exp_ni) <= 0.01,
      "(MIS %s vs Tab2 %s)" % (round(mis_ni, 2), round(exp_ni, 2)))
check("retained ≈ 0 (data mulai 2026, belum ada tutup buku)",
      abs(mis_retained) <= 0.01, "(%s)" % round(mis_retained, 2))
mis_liab_eq = mis_get("KEWAJIBAN + EKUITAS", 0)
mis_liab_eq = 0.0 if mis_liab_eq is None else mis_liab_eq
_selisih = mis_get0("Selisih (harus 0)", 0)
check("kolom 1 self-balancing (selisih ≈ 0)",
      abs(_selisih) <= 0.01
      and abs(mis_liab_eq - (mis_liab + mis_equity + mis_retained + mis_ni)) <= 0.01,
      "(selisih %s)" % round(_selisih, 2))

# ------------------------------------------------------------------
# 3) Parity kolom 2 — akhir Juli (Tab 2 parametrik dgn tanggal Juli)
# ------------------------------------------------------------------
print("=== 3) Parity kolom 2 (per 2026-07-31; UPDATE 15 Sep: Juli ADA data) ===")
bal_j = D.get_dashboard_data("2026-07-01", PREV_D2, None)["finance"]["balance"]
check("assets parity Jul", abs(mis_get0("TOTAL ASET", 1) - bal_j["total_assets"]) <= 0.01,
      "(MIS %s vs Tab2-Jul %s)" % (round(mis_get0("TOTAL ASET", 1), 2),
                                   round(bal_j["total_assets"], 2)))
check("liabilities parity Jul",
      abs(mis_get0("Total Kewajiban", 1) - bal_j["liabilities"]) <= 0.01,
      "(MIS %s vs Tab2-Jul %s)" % (round(mis_get0("Total Kewajiban", 1), 2),
                                   round(bal_j["liabilities"], 2)))
check("NI YTD parity Jul",
      abs(mis_get0("Laba (Rugi) Tahun Berjalan", 1) - bal_j["net_income_ytd"]) <= 0.01,
      "(MIS %s vs Tab2-Jul %s)" % (round(mis_get0("Laba (Rugi) Tahun Berjalan", 1), 2),
                                   round(bal_j["net_income_ytd"], 2)))
check("kolom 2 self-balancing (selisih ≈ 0)",
      abs(mis_get0("Selisih (harus 0)", 1)) <= 0.01,
      "(selisih %s)" % round(mis_get0("Selisih (harus 0)", 1), 2))

# ------------------------------------------------------------------
# 4) Konsistensi lintas-laporan: NI BS (F5b) == net P&L (F5a), window sama
# ------------------------------------------------------------------
print("=== 4) Konsistensi F5a <-> F5b ===")
pl_pay = RA.get_report_data("profit_loss_mis", {"date_from": D1, "date_to": D2, "outlet_ids": []})
net_pl = None
for row in pl_pay["body"]:
    if row["label"] == "LABA BERSIH":
        net_pl = row["cells"][1]["val"]  # kolom YTD P&L = window sama dgn BS kolom 1
        break
check("NI Neraca == Laba Bersih P&L (YTD)",
      net_pl is not None and abs(mis_ni - net_pl) <= 0.01,
      "(BS %s vs P&L %s)" % (round(mis_ni, 2), round(net_pl or 0, 2)))

print("")
print("Ringkasan (per 2026-08-31):")
print("  MIS  : assets=%s liab=%s equity=%s retained=%s ni_ytd=%s" % (
    round(mis_assets, 2), round(mis_liab, 2), round(mis_equity, 2),
    round(mis_retained, 2), round(mis_ni, 2)))
print("  Tab2 : assets=%s liab=%s equity=%s ni_ytd=%s" % (
    round(bal["total_assets"], 2), round(bal["liabilities"], 2),
    round(bal["equity"], 2), round(bal["net_income_ytd"], 2)))

print("")
if fails:
    print("RESULT: %d FAIL -> %s" % (len(fails), fails))
else:
    print("RESULT: ALL PASS")
