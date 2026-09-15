# -*- coding: utf-8 -*-
"""Test F1 Report Shell — geprekyukss.dashboard.report.actions (READ-ONLY data; transient wizards only).

Jalankan (odoo shell, pola resmi §2 PROGRESS_DASHBOARD.md):
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db \
    --db_port 5432 --db_user odoo --db_password odoo" \
    < scripts/test_report_actions.py

Yang diuji:
  1. Trial Balance (AFR)  -> get_report_data preview (adapter -> columns/rows)
  2. General Ledger (AFR) -> preview + batas jumlah baris (GL panjang)
  3. Cash Flow (MIS)      -> compute() resmi: header/body/notes, kolom valid
  4. Export actions       -> PDF & XLSX untuk TB + Cash Flow (shape action dict)
  5. Juli 2026 (kosong)   -> TB rows kosong (empty state, bukan error)
"""
RA = env["geprekyukss.dashboard.report.actions"]

fails = []


def check(name, cond, extra=""):
    if cond:
        print("  PASS %s %s" % (name, extra))
    else:
        print("  FAIL %s %s" % (name, extra))
    if not cond:
        fails.append(name)


AGU = {"date_from": "2026-08-01", "date_to": "2026-08-31", "outlet_ids": []}
JUL = {"date_from": "2026-07-01", "date_to": "2026-07-31", "outlet_ids": []}

print("=" * 62)
print("1) TRIAL BALANCE (AFR) - preview Agustus 2026")
print("=" * 62)
tb = RA.get_report_data("trial_balance", AGU)
check("kind == table", tb.get("kind") == "table")
check("columns ada (5)", len(tb.get("columns") or []) == 5, str(len(tb.get("columns") or [])))
cols = {c["key"] for c in tb["columns"]}
check("column keys benar", cols == {"code", "name", "debit", "credit", "balance"}, str(sorted(cols)))
check("rows list", isinstance(tb.get("rows"), list))
print("     info: rows=%d" % len(tb.get("rows") or []))
if tb.get("rows"):
    r0 = tb["rows"][0]
    check("row keys sesuai columns", set(r0.keys()) == cols, str(sorted(r0.keys())))
    nums = [r for r in tb["rows"] if isinstance(r.get("debit"), (int, float))]
    check("debit numerik di >=1 baris", len(nums) > 0)

print("=" * 62)
print("2) SEMUA LAPORAN AFR - preview Agustus (shape + invariant angka)")
print("=" * 62)
summaries = {}
for key in ("trial_balance", "general_ledger", "journal_ledger",
            "aged_partner", "open_items", "vat"):
    try:
        d = RA.get_report_data(key, AGU)
        check("%s kind table" % key, d.get("kind") == "table")
        check("%s columns non-empty" % key, bool(d.get("columns")))
        rows = d.get("rows") or []
        summaries[key] = rows
        print("     info: %s rows=%d" % (key, len(rows)))
    except Exception as ex:
        check("%s preview tanpa crash" % key, False, repr(ex)[:200])

# Invariant: total debit/credit TB == GL == Journal Ledger (sumber sama)
def _dc(rows):
    return (round(sum(r.get("debit") or 0 for r in rows), 2),
            round(sum(r.get("credit") or 0 for r in rows), 2))
if all(k in summaries for k in ("trial_balance", "general_ledger")):
    tbd, tbc = _dc(summaries["trial_balance"])
    gld, glc = _dc(summaries["general_ledger"])
    check("TB debit == GL debit", abs(tbd - gld) < 1.0, "(%s vs %s)" % (tbd, gld))
    check("TB credit == GL credit", abs(tbc - glc) < 1.0, "(%s vs %s)" % (tbc, glc))
if all(k in summaries for k in ("trial_balance", "journal_ledger")):
    tbd, tbc = _dc(summaries["trial_balance"])
    jld, jlc = _dc(summaries["journal_ledger"])
    check("TB debit == JL debit", abs(tbd - jld) < 1.0, "(%s vs %s)" % (tbd, jld))
    check("TB credit == JL credit", abs(tbc - jlc) < 1.0, "(%s vs %s)" % (tbc, jlc))
# Aged partner: total = sum bucket (semantik engine)
if summaries.get("aged_partner"):
    bad = [r for r in summaries["aged_partner"]
           if abs(sum(v for kk, v in r.items() if kk.startswith("b_")) - (r.get("total") or 0)) > 0.5]
    check("aged bucket sum == total (semua baris)", not bad, "bad=%d" % len(bad))
# Open items: sisa <= nilai
if summaries.get("open_items"):
    bad = [r for r in summaries["open_items"]
           if abs((r.get("open") or 0) - (r.get("original") or 0)) > 0.005
           and abs((r.get("open") or 0)) > abs((r.get("original") or 0))]
    check("open_items sisa <= nilai", not bad, "bad=%d" % len(bad))

print("=" * 62)
print("3) CASH FLOW (MIS) - compute() resmi Agustus 2026")
print("=" * 62)
try:
    cf = RA.get_report_data("cash_flow_mis", AGU)
    check("kind == matrix", cf.get("kind") == "matrix")
    check("header 2 baris", isinstance(cf.get("header"), list) and len(cf["header"]) == 2)
    check("body list", isinstance(cf.get("body"), list))
    print("     info: KPI rows=%d, kolom header[0]=%d" % (
        len(cf.get("body") or []),
        len((cf.get("header") or [{}, {}])[0].get("cols") or [])))
    nb = len(cf.get("body") or [])
    check("body > 0", nb > 0)
    if nb:
        row0 = cf["body"][0]
        check("row punya label+cells", "label" in row0 and "cells" in row0)
        cells = row0["cells"]
        check("cells == jumlah subcol header[1]", len(cells) == len(cf["header"][1]["cols"]),
              "(%d vs %d)" % (len(cells), len(cf["header"][1]["cols"])))
        all_vals = [c.get("val") for row in cf["body"] for c in row["cells"]]
        numeric = [v for v in all_vals if isinstance(v, (int, float))]
        check("ada nilai numerik (Agustus ada data)", len(numeric) > 0)
        check("val_r (rendered) tersedia", any(
            c.get("val_r") not in (None, "") for row in cf["body"] for c in row["cells"]))
        check("style row berupa string", all(isinstance(r.get("style"), (str, type(None))) for r in cf["body"]))
except Exception as ex:
    check("cash_flow preview tanpa crash", False, repr(ex)[:300])

print("=" * 62)
print("4) EXPORT ACTIONS - shape action dict (TB & Cash Flow, PDF/XLSX)")
print("=" * 62)
for key, fmt in [
    ("trial_balance", "pdf"),
    ("trial_balance", "xlsx"),
    ("cash_flow_mis", "pdf"),
    ("cash_flow_mis", "xlsx"),
]:
    try:
        act = RA.get_report_export_action(key, AGU, fmt)
        check("%s %s action dict" % (key, fmt), isinstance(act, dict))
        check("%s %s type dikenal" % (key, fmt),
              act.get("type") in ("ir.actions.report", "ir.actions.act_window"),
              str(act.get("type")))
        check("%s %s report_name ada" % (key, fmt), bool(act.get("report_name")),
              act.get("report_name") or "")
    except Exception as ex:
        check("%s %s export" % (key, fmt), False, repr(ex)[:200])

print("=" * 62)
print("5) JULI 2026 - TB konsisten (UPDATE 15 Sep: Juli ADA data)")
print("=" * 62)
try:
    tbj = RA.get_report_data("trial_balance", JUL)
    check("kind table", tbj.get("kind") == "table")
    # UPDATE 15 Sep: premise lama "Juli kosong" basi sejak dataset 72 hari
    # (Jun-Agu) diimpor. TB Juli kini punya baris bermutasi — invarian yang
    # benar: Σ(debit) == Σ(credit) (TB seimbang per periode).
    rows_j = tbj.get("rows") or []
    tot_dr = sum(r.get("debit") or 0 for r in rows_j)
    tot_cr = sum(r.get("credit") or 0 for r in rows_j)
    check("Juli TB: Σ debit == Σ credit (seimbang)",
          abs(tot_dr - tot_cr) <= 1.0,
          "rows=%d dr=%s cr=%s" % (len(rows_j), round(tot_dr, 2), round(tot_cr, 2)))
except Exception as ex:
    check("Juli TB preview tanpa crash", False, repr(ex)[:200])

print("")
if fails:
    print("RESULT: %d FAIL -> %s" % (len(fails), fails))
else:
    print("RESULT: ALL PASS")
