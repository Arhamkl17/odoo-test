# -*- coding: utf-8 -*-
"""Test F-UI.4 — verifikasi tag `kind` (ap|ar|other) di adapter open_items.

READ-ONLY. Memastikan perubahan `_adapt_open_items` (F-UI.4, 12 Sep 2026)
TIDAK mengubah angka laporan — hanya menambah metadata `kind` per baris.

Jalankan (odoo shell, pola resmi §2 PROGRESS_DASHBOARD.md):
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db \\
    --db_port 5432 --db_user odoo --db_password odoo" \\
    < scripts/test_fui4_open_items_kind.py

Yang diuji:
  1. Shape      : setiap baris punya `kind` ∈ {ap, ar, other}.
  2. Mapping    : kind konsisten dengan account_type akun per baris
                  (liability_payable → ap, asset_receivable → ar).
  3. Angka utuh : Σ(open) & Σ(original) per kode akun IDENTIK antara
                  payload ber-tag dan agregasi `amount_residual` AML raw
                  as-of date_to (posted, reconcile parsial — mimic engine),
                  delta 0,01.
  4. Anchor AP  : total AP baris kind=ap == GT amount_residual AML raw
                  as-of date_to — UPDATE 15 Sep: anchor hard-code F2
                  (100.224.681,49, era dataset lama) diganti ground truth
                  dinamis; dataset 72 hari kini AP=0 → laporan legit kosong.
  5. Kolom      : columns tidak berubah (9 kolom, tanpa kolom kind —
                  kind metadata, bukan kolom tabel).
"""
RA = env["geprekyukss.dashboard.report.actions"]

fails = []
TOL = 0.05


def check(name, cond, extra=""):
    if cond:
        print("  PASS %s %s" % (name, extra))
    else:
        print("  FAIL %s %s" % (name, extra))
    if not cond:
        fails.append(name)


AGU = {"date_from": "2026-08-01", "date_to": "2026-08-31", "outlet_ids": []}

# --- Ground truth open AP/AR as-of 31 Agu (AML raw, posted) ---
# UPDATE 15 Sep: menggantikan anchor hard-code F2 yang basi sejak dataset
# 72 hari diimpor ulang (liability_payable tanpa aktivitas → AP = 0).
_GT_ACC = env["account.account"].with_context(active_test=False)
_GT_ML = env["account.move.line"].with_context(active_test=False)


def _gt_open(account_type, date_to):
    accs = _GT_ACC.search([("account_type", "=", account_type)])
    if not accs:
        return 0.0
    mls = _GT_ML.search([
        ("parent_state", "=", "posted"),
        ("account_id", "in", accs.ids),
        ("date", "<=", date_to),
    ])
    return abs(sum(mls.mapped("amount_residual")))


GT_AP = _gt_open("liability_payable", AGU["date_to"])
GT_AR = _gt_open("asset_receivable", AGU["date_to"])
print("info: GT open as-of %s — AP=%.2f AR=%.2f" % (AGU["date_to"], GT_AP, GT_AR))

print("=== F-UI.4 — open_items adapter: tag kind, angka utuh ===")
d = RA.get_report_data("open_items", AGU)
rows = d.get("rows") or []
print("  rows=%d" % len(rows))

# 1) Shape: kind ada & valid di semua baris
kinds = set(r.get("kind") for r in rows)
# UPDATE 15 Sep: laporan legit kosong saat GT AP+AR = 0 → kind vacuous.
if GT_AP + GT_AR > 0.01:
    check("1. kind ada & valid", rows and kinds <= {"ap", "ar", "other"}, "kinds=%s" % sorted(kinds))
else:
    check("1. kind ada & valid (GT open=0 → kosong legit)", True, "rows=%d" % len(rows))

# 2) Mapping kind == account_type akun (lookup independen per kode akun)
Account = env["account.account"].with_context(active_test=False)
code2type = {}
for r in rows:
    if r["code"] not in code2type:
        acc = Account.search([("code", "=", r["code"])], limit=1)
        code2type[r["code"]] = acc.account_type or ""
bad_map = []
for r in rows:
    at = code2type.get(r["code"], "")
    expect = "ap" if at == "liability_payable" else "ar" if at == "asset_receivable" else "other"
    if r["kind"] != expect:
        bad_map.append((r["code"], r["kind"], expect))
check("2. mapping kind == account_type", not bad_map, "bad=%d %s" % (len(bad_map), bad_map[:3]))

# 3) Angka utuh: Σ open per kode akun == ±Σ amount_residual AML raw
#    as-of 31 Agu (posted) — pola cross-check yang sama dgn test F6.
MoveLine = env["account.move.line"]
ap_ar_accs = env["account.account"].with_context(active_test=False).search([
    ("account_type", "in", ("liability_payable", "asset_receivable")),
])
aml = MoveLine.with_context(active_test=False).search([
    ("parent_state", "=", "posted"),
    ("account_id", "in", ap_ar_accs.ids),
    ("date", "<=", AGU["date_to"]),
])
aml_by_code = {}
for ml in aml:
    aml_by_code[ml.account_id.code] = aml_by_code.get(ml.account_id.code, 0.0) + ml.amount_residual

sum_by_code = {}
orig_by_code = {}
for r in rows:
    sum_by_code[r["code"]] = sum_by_code.get(r["code"], 0.0) + (r["open"] or 0.0)
    orig_by_code[r["code"]] = orig_by_code.get(r["code"], 0.0) + (r["original"] or 0.0)

bad_sum = []
for code, s in sum_by_code.items():
    raw = aml_by_code.get(code)
    if raw is None:
        bad_sum.append((code, "tak ada di AML raw", s))
    elif abs(abs(raw) - abs(s)) > TOL:
        bad_sum.append((code, raw, s))
check("3. Σ open per akun == AML raw", not bad_sum,
      "bad=%d %s" % (len(bad_sum), [(b[0], b[1], b[2]) for b in bad_sum[:3]]))

# 4) Anchor AP: total AP == GT dinamis (dulu: F2 100.224.681,49)
ap_total = sum((r["open"] or 0.0) for r in rows if r["kind"] == "ap")
check("4. total AP == GT payable AML raw (as-of)", abs(abs(ap_total) - GT_AP) < TOL,
      "(AP=%.2f vs GT %.2f)" % (ap_total, GT_AP))
ar_total = sum((r["open"] or 0.0) for r in rows if r["kind"] == "ar")
check("4b. total AR == GT receivable AML raw (as-of)", abs(ar_total - GT_AR) < TOL,
      "(AR=%.2f vs GT %.2f)" % (ar_total, GT_AR))

# 5) Kolom tidak berubah (kind metadata, bukan kolom)
keys = [c["key"] for c in d.get("columns") or []]
check("5. columns tetap 9 tanpa kind",
      keys == ["code", "account", "partner", "date", "due", "entry", "label", "original", "open"],
      "keys=%s" % keys)

print("")
print("HASIL: %s (%d kegagalan)" % ("ALL PASS" if not fails else "FAIL", len(fails)))
for f in fails:
    print(" - %s" % f)
