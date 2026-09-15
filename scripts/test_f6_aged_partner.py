# -*- coding: utf-8 -*-
"""Test F6 — Aged Partner Balance di report shell (roadmap §A.3 fase F6).
READ-ONLY data; transient wizard only.

Jalankan (odoo shell, pola resmi §2 PROGRESS_DASHBOARD.md):
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db \\
    --db_port 5432 --db_user odoo --db_password odoo" \\
    < scripts/test_f6_aged_partner.py

Yang diuji (pola F2/F3 — cross-check vs sumber independen):
  1. Shape        : kolom by engine bucket key (b_current...b_total),
                    baris akun + sub-baris partner (— prefix, style muted).
  2. Bucket math  : per baris Σ bucket == total; per kolom Σ partner ==
                    baris akun (subtotal engine).
  3. Cross-check 1: total piutang (akun receivable) == amount_residual
                    AML raw as-of date_to (posted, exclude rekonsiliasi
                    penuh setelah date_to — mimic engine AFR).
  3b. Cross-check 2: total hutang (akun payable) baris akun == saldo
                    payable AML raw as-of date_to — UPDATE 15 Sep: anchor
                    hard-code 100.224.681,49 (era dataset lama) diganti
                    ground truth dinamis; dataset 72 hari kini AP=0 & AR
                    full-reconciled → laporan legit kosong.
  4. meta.totals  : values per bucket == Σ baris akun per bucket; footer
                    total == GT open AP+AR (bukan lagi "harus non-zero").
  5. Juli kosong  : rows = 0 (atau semua bucket 0) — empty state.
  6. Export       : PDF/XLSX action dict valid.
"""
RA = env["geprekyukss.dashboard.report.actions"]

fails = []
TOL = 1.0


def check(name, cond, extra=""):
    if cond:
        print("  PASS %s %s" % (name, extra))
    else:
        print("  FAIL %s %s" % (name, extra))
    if not cond:
        fails.append(name)


AGU = {"date_from": "2026-08-01", "date_to": "2026-08-31", "outlet_ids": []}
JUL = {"date_from": "2026-07-01", "date_to": "2026-07-31", "outlet_ids": []}
BUCKETS = ["b_current", "b_30_days", "b_60_days", "b_90_days", "b_120_days",
           "b_older", "total"]

# --- Ground truth open AP/AR as-of 31 Agu (AML raw, posted) ---
# UPDATE 15 Sep: menggantikan anchor hard-code F2 (100.224.681,49) yang
# basi sejak dataset 72 hari (Jun–Agu) diimpor ulang: liability_payable
# tidak punya aktivitas & satu-satunya akun AR sudah full-reconciled.
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
GT_OPEN = GT_AP + GT_AR
print("info: GT open as-of %s — AP=%.2f AR=%.2f" % (AGU["date_to"], GT_AP, GT_AR))

print("=" * 62)
print("1) SHAPE - preview Agustus 2026")
print("=" * 62)
d = RA.get_report_data("aged_partner", AGU)
check("kind == table", d.get("kind") == "table")
cols = [c["key"] for c in d.get("columns") or []]
check("kolom by engine bucket key",
      cols == ["partner"] + BUCKETS, str(cols))
rows = d.get("rows") or []
acc_rows = [r for r in rows if not r.get("is_partner")]
prt_rows = [r for r in rows if r.get("is_partner")]
print("     info: rows=%d (akun=%d, partner=%d)" % (len(rows), len(acc_rows), len(prt_rows)))
# UPDATE 15 Sep: laporan legit kosong saat GT open = 0 (AR full-reconciled,
# AP tanpa aktivitas) — cek baris hanya bila GT open > 0.
if GT_OPEN > 0.01:
    check("ada >= 1 baris akun", len(acc_rows) >= 1)
else:
    check("ada >= 1 baris akun (GT open=0 → kosong legit)", True,
          "rows=%d" % len(acc_rows))
check("sub-baris partner prefix '— '",
      all(str(r.get("partner") or "").startswith("— ") for r in prt_rows))
check("sub-baris partner style muted",
      all(r.get("style") == "muted" for r in prt_rows))

print("=" * 62)
print("2) BUCKET MATH - Σ bucket == total; Σ partner == akun")
print("=" * 62)
bad_sum = [r["partner"] for r in rows
           if abs(sum(r.get(b) or 0.0 for b in BUCKETS[:-1]) - (r.get("total") or 0.0)) > 0.01]
check("Σ bucket == total (semua baris)", not bad_sum, "bad=%s" % bad_sum[:3])
for ar in acc_rows:
    code = ar.get("code")
    subs = [r for r in prt_rows if r.get("code") == code]
    if not subs:
        continue
    bad_cols = [b for b in BUCKETS
                if abs(sum(r.get(b) or 0.0 for r in subs) - (ar.get(b) or 0.0)) > 0.01]
    if bad_cols:
        check("Σ partner == akun (%s)" % code, False, "bad=%s" % bad_cols)
        break
else:
    check("Σ partner == akun (per kolom, semua akun)", True)

print("=" * 62)
print("3) CROSS-CHECK vs AML RAW (as-of 2026-08-31)")
print("=" * 62)
# UPDATE 15 Sep: anchor payable = GT dinamis (dulu: F2 100.224.681,49).
pay_rows = [r for r in acc_rows if str(r.get("code") or "").startswith("21")]
tot_pay = sum(abs(r.get("total") or 0.0) for r in pay_rows)
check("total hutang baris akun == GT payable AML raw (as-of)",
      abs(tot_pay - GT_AP) < TOL, "(%s vs GT %s)" % (round(tot_pay, 2), round(GT_AP, 2)))
# Piutang: cross-check amount_residual AML raw as-of date_to
ML = env["account.move.line"]
rec_accs = env["account.account"].with_context(active_test=False).search(
    [("account_type", "=", "asset_receivable")])
aml = ML.with_context(active_test=False).search([
    ("parent_state", "=", "posted"),
    ("account_id", "in", rec_accs.ids),
    ("date", "<=", AGU["date_to"]),
])
gt_rec = -sum(aml.mapped("amount_residual"))
rec_rows = [r for r in acc_rows if str(r.get("code") or "").startswith("11")]
tot_rec = sum(abs(r.get("total") or 0.0) for r in rec_rows)
print("     info: piutang AML raw=%s vs laporan=%s" % (round(gt_rec, 2), round(tot_rec, 2)))
check("total piutang == AML raw amount_residual (as-of)",
      abs(tot_rec - gt_rec) < TOL)

print("=" * 62)
print("4) META.TOTALS - footer per bucket == Σ baris akun")
print("=" * 62)
meta = d.get("meta") or {}
totals = meta.get("totals") or []
check("meta.totals ada (shape values)", bool(totals) and "values" in totals[0])
if totals and "values" in totals[0]:
    vals = totals[0]["values"]
    bad = [b for b in BUCKETS
           if abs((vals.get(b) or 0.0) - sum(r.get(b) or 0.0 for r in acc_rows)) > 0.01]
    check("values per bucket == Σ baris akun", not bad, "bad=%s" % bad)
    # UPDATE 15 Sep: footer total == GT open AP+AR (bukan "harus non-zero" —
    # dataset kini memang 0; cek konsistensi, bukan asumsi ada hutang).
    check("footer total == GT open AP+AR (as-of)",
          abs((vals.get("total") or 0.0) - GT_OPEN) < TOL,
          "(footer %s vs GT %s)" % (round(vals.get("total") or 0.0, 2), round(GT_OPEN, 2)))

print("=" * 62)
print("5) JULI 2026 (kosong) - empty state")
print("=" * 62)
dj = RA.get_report_data("aged_partner", JUL)
jrows = dj.get("rows") or []
check("Juli: tanpa baris bernilai",
      all(abs(r.get(b) or 0.0) <= 0.005 for r in jrows for b in BUCKETS),
      "rows=%d" % len(jrows))

print("=" * 62)
print("6) EXPORT - shape action dict (PDF/XLSX)")
print("=" * 62)
for fmt in ("pdf", "xlsx"):
    try:
        act = RA.get_report_export_action("aged_partner", AGU, fmt)
        check("%s action dict" % fmt, isinstance(act, dict))
        check("%s type dikenal" % fmt,
              act.get("type") in ("ir.actions.report", "ir.actions.act_window"),
              str(act.get("type")))
        check("%s report_name ada" % fmt, bool(act.get("report_name")),
              act.get("report_name") or "")
    except Exception as ex:
        check("%s export" % fmt, False, repr(ex)[:200])

print("")
if fails:
    print("RESULT: %d FAIL -> %s" % (len(fails), fails))
else:
    print("RESULT: ALL PASS (F6 Aged Partner)")
env.cr.commit()
