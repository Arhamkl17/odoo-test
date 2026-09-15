# -*- coding: utf-8 -*-
"""F2 PoC — Cross-check Trial Balance (engine AFR) vs agregasi ORM independen
vs payload `finance.balance` dashboard (READ-ONLY).

Jalankan (odoo shell, pola resmi §2 PROGRESS_DASHBOARD.md):
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db \
    --db_port 5432 --db_user odoo --db_password odoo" \
    < scripts/test_f2_tb_crosscheck.py

Tiga sumber:
  A. TB via geprekyukss.dashboard.report.actions (jalur shell UI, engine AFR)
  B. Agregasi _read_group account.move.line (gaya dashboard_data.py)
  C. get_dashboard_data().finance.balance (Tab 2 existing)

Invarian yang diverifikasi (Agustus 2026 + kumulatif s.d. 31 Agu):
  1. Per-akun: TB ending_balance == ORM net (debit-credit kumulatif)
  2. Mutasi periode: TB debit/credit kolom == ORM debit/credit Agustus
  3. Totals: TB debit == TB credit (double-entry)
  4. Grup tipe akun: TB vs C — assets / liabilities / equity / net income YTD
  5. Neraca: total_assets == liab + equity + net_income_ytd (cek C dan TB)
"""
D = env["geprekyukss.dashboard.data"]
RA = env["geprekyukss.dashboard.report.actions"]
Aml = env["account.move.line"]
# active_test=False: akun arsip tetap bagian buku besar (dihitung AFR juga)
Account = env["account.account"].with_context(active_test=False)

P = {"date_from": "2026-08-01", "date_to": "2026-08-31", "outlet_ids": []}
D1, D2 = P["date_from"], P["date_to"]

fails = []


def check(name, cond, extra=""):
    if cond:
        print("  PASS %s %s" % (name, extra))
    else:
        print("  FAIL %s %s" % (name, extra))
    if not cond:
        fails.append(name)


# ------------------------------------------------------------------
# Sumber A — TB engine AFR via wrapper (jalur shell UI)
# ------------------------------------------------------------------
tb = RA.get_report_data("trial_balance", P)
tb_by_code = {r["code"]: r for r in tb["rows"]}

# ------------------------------------------------------------------
# Sumber B — agregasi ORM independen (posted only)
# ------------------------------------------------------------------
all_accs = Account.search([])

def _rg(dom):
    m = {}
    for acc, debit, credit in Aml._read_group(dom, ["account_id"], ["debit:sum", "credit:sum"]):
        m[acc.id] = ((debit or 0.0), (credit or 0.0))
    return m

cum = _rg([("account_id", "in", all_accs.ids), ("parent_state", "=", "posted"),
           ("date", "<=", D2)])
aug = _rg([("account_id", "in", all_accs.ids), ("parent_state", "=", "posted"),
           ("date", ">=", D1), ("date", "<=", D2)])

# ------------------------------------------------------------------
# 1) Per-akun: TB ending_balance vs ORM net kumulatif
# ------------------------------------------------------------------
print("=== 1) Per-akun: TB ending_balance == ORM net kumulatif s.d. %s ===" % D2)
mismatch, sign_flip, plug_row = [], [], []
tb_type = {}  # code -> account_type
for a in all_accs:
    tb_type[a.code] = a.account_type
for code, r in tb_by_code.items():
    aid = None
    net = 0.0
    # match by code -> account (termasuk akun arsip)
    acc = Account.search([("code", "=", code)], limit=1)
    if acc:
        d_, c_ = cum.get(acc.id, (0.0, 0.0))
        net = d_ - c_
    else:
        # akun plug earnings (tidak ada di account.account) — cek terpisah
        if code == "99999900":
            plug_row.append(r)
        continue
    diff = abs(r["balance"] - net)
    if diff <= 0.01:
        continue
    if abs(r["balance"] + net) <= 0.01:
        sign_flip.append(code)
    else:
        mismatch.append((code, r["balance"], round(net, 2)))

check("semua akun TB cocok dgn ORM (kumulatif)", not mismatch,
      str(mismatch[:5]))
check("tak ada inkonsistensi tanda (campuran)", len(sign_flip) in (0, len(tb_by_code) - 1),
      "sign_flip=%d dari %d akun" % (len(sign_flip), len(tb_by_code)))
if plug_row:
    pr = plug_row[0]
    inc_exp_signed = sum(
        (cum.get(a.id, (0.0, 0.0))[0] - cum.get(a.id, (0.0, 0.0))[1])
        for a in all_accs if a.account_type in ("income", "income_other",) or
        a.account_type.startswith("expense"))
    check("plug 99999900 ≈ -(income+expense signed) atau 0",
          abs(pr["balance"]) <= 0.01 or abs(pr["balance"] + inc_exp_signed) <= 1.0,
          "plug=%s, -(inc+exp)=%s" % (round(pr["balance"], 2), round(-inc_exp_signed, 2)))

# ------------------------------------------------------------------
# 2) Mutasi periode: kolom debit/credit TB == ORM Agustus
# ------------------------------------------------------------------
print("=== 2) Mutasi Agustus: TB debit/credit == ORM ===")
bad_aug = []
for code, r in tb_by_code.items():
    acc = Account.search([("code", "=", code)], limit=1)
    if not acc:
        continue
    d_, c_ = aug.get(acc.id, (0.0, 0.0))
    if abs(r["debit"] - d_) > 0.01 or abs(r["credit"] - c_) > 0.01:
        bad_aug.append((code, r["debit"], round(d_, 2), r["credit"], round(c_, 2)))
check("mutasi Agustus per-akun cocok (debit & kredit)", not bad_aug, str(bad_aug[:4]))

# ------------------------------------------------------------------
# 3) Totals: TB debit == TB credit
# ------------------------------------------------------------------
print("=== 3) Double-entry ===")
tbd = round(sum(r["debit"] for r in tb["rows"]), 2)
tbc = round(sum(r["credit"] for r in tb["rows"]), 2)
check("TB debit == TB credit", abs(tbd - tbc) <= 0.01, "(%s vs %s)" % (tbd, tbc))
orm_d = round(sum(d for d, _ in aug.values()), 2)
orm_c = round(sum(c for _, c in aug.values()), 2)
check("TB debit == ORM debit Agustus", abs(tbd - orm_d) <= 0.01, "(%s vs %s)" % (tbd, orm_d))
check("TB credit == ORM credit Agustus", abs(tbc - orm_c) <= 0.01, "(%s vs %s)" % (tbc, orm_c))

# ------------------------------------------------------------------
# 4) Grup tipe akun: TB vs payload dashboard (Tab 2)
# ------------------------------------------------------------------
print("=== 4) Grup tipe akun: TB vs finance.balance dashboard ===")
dash = D.get_dashboard_data(D1, D2, None)
bal = dash["finance"]["balance"]

def tb_sum(types):
    s = 0.0
    for code, r in tb_by_code.items():
        t = tb_type.get(code)
        if t in types:
            s += r["balance"]
    return s

tb_assets = tb_sum(["asset_cash", "asset_receivable", "asset_current",
                    "asset_prepayments", "asset_fixed"])
tb_liab = -tb_sum(["liability_payable", "liability_current"])
tb_equity = -tb_sum(["equity", "equity_unaffected"])
tb_inc = -tb_sum(["income", "income_other"])
tb_exp = tb_sum([t for t in set(tb_type.values()) if t.startswith("expense")])
tb_ni = tb_inc - tb_exp

check("total assets: TB == dashboard", abs(tb_assets - bal["total_assets"]) <= 0.01,
      "(%s vs %s)" % (round(tb_assets, 2), round(bal["total_assets"], 2)))
check("total liabilities: TB == dashboard", abs(tb_liab - bal["liabilities"]) <= 0.01,
      "(%s vs %s)" % (round(tb_liab, 2), round(bal["liabilities"], 2)))
check("total equity: TB == dashboard", abs(tb_equity - bal["equity"]) <= 0.01,
      "(%s vs %s)" % (round(tb_equity, 2), round(bal["equity"], 2)))
check("net income YTD: TB == dashboard", abs(tb_ni - bal["net_income_ytd"]) <= 0.05,
      "(%s vs %s)" % (round(tb_ni, 2), round(bal["net_income_ytd"], 2)))

# ------------------------------------------------------------------
# 5) Neraca seimbang di kedua sumber
# ------------------------------------------------------------------
print("=== 5) Neraca seimbang ===")
lhs_tb = tb_assets
rhs_tb = tb_liab + tb_equity + tb_ni
check("TB: assets == liab+equity+NI", abs(lhs_tb - rhs_tb) <= 0.05,
      "(%s vs %s)" % (round(lhs_tb, 2), round(rhs_tb, 2)))
check("dashboard: assets == liab+equity+NI",
      abs(bal["total_assets"] - bal["total_liab_equity"]) <= 0.05,
      "(%s vs %s)" % (round(bal["total_assets"], 2), round(bal["total_liab_equity"], 2)))

# ------------------------------------------------------------------
# Ringkasan sampel (untuk log)
# ------------------------------------------------------------------
print("")
print("Ringkasan (Agustus 2026):")
print("  TB accounts=%d, debit=%s, credit=%s" % (len(tb["rows"]), tbd, tbc))
print("  assets=%s | liab=%s | equity=%s | NI_ytd=%s" % (
    round(tb_assets, 2), round(tb_liab, 2), round(tb_equity, 2), round(tb_ni, 2)))

print("")
if fails:
    print("RESULT: %d FAIL -> %s" % (len(fails), fails))
else:
    print("RESULT: ALL PASS")
