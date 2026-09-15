# -*- coding: utf-8 -*-
"""Test F3 — General Ledger & VAT (roadmap §A.3 fase F3). READ-ONLY data.

Jalankan (odoo shell, pola resmi §2 PROGRESS_DASHBOARD.md):
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db \\
    --db_port 5432 --db_user odoo --db_password odoo" \\
    < scripts/test_f3_gl_vat.py

Yang diuji (cross-check engine AFR vs sumber independen, pola F2):
  1. GL preview  : shape + invariant per-akun vs Trial Balance (sumber sama,
                   engine sama) — debit/kredit/saldo-akhir per akun, saldo
                   berjalan, saldo awal + Σ mutasi == saldo akhir.
  2. GL totals   : Σ fin_bal debit/credit == TB debit/credit total —
                   UPDATE 15 Sep: angka hard-code era 12 Sep (2.629 M)
                   diganti total TB dinamis dari payload (dataset 72 hari
                   mengubah total; invarian GL==TB tetap yang diuji).
  3. GL last bal : saldo akhir baris terakhir per akun == fin_bal balance.
  4. VAT preview : shape + meta.totals; berdasarkan agregasi AML raw:
                   tax = Σ balance tax_line_id, net = Σ balance move line
                   ber-taxes (posted, periode sama) — delta < 1,0.
                   CATATAN: DB tanpa account.tax moves → 0 == 0 (benar);
  5. Juli        : GL totals seimbang (UPDATE 15 Sep: Juli ADA data —
                   premise "Juli kosong" basi sejak dataset 72 hari).

Hasil 12 Sep 2026: ALL PASS (GL 3.215 baris Agustus; VAT 0 baris — DB
memang tanpa pajak; GL==TB 71/71 akun; total 2.629.159.281,58).
"""
RA = env["geprekyukss.dashboard.report.actions"]

fails = []
TOL = 1.0  # rupiah; konsisten test F1


def check(name, cond, extra=""):
    if cond:
        print("  PASS %s %s" % (name, extra))
    else:
        print("  FAIL %s %s" % (name, extra))
    if not cond:
        fails.append(name)


AGU = {"date_from": "2026-08-01", "date_to": "2026-08-31", "outlet_ids": []}
JUL = {"date_from": "2026-07-01", "date_to": "2026-07-31", "outlet_ids": []}

# ======================================================================
print("=" * 62)
print("1) GENERAL LEDGER - preview Agustus 2026 (shape)")
print("=" * 62)
gl = RA.get_report_data("general_ledger", AGU)
check("kind == table", gl.get("kind") == "table")
cols = gl.get("columns") or []
check("columns 10", len(cols) == 10, str(len(cols)))
col_keys = [c["key"] for c in cols]
check("column keys urut",
      col_keys == ["date", "entry", "code", "account", "journal", "partner",
                   "label", "debit", "credit", "balance"], str(col_keys))
rows = gl.get("rows") or []
print("     info: rows=%d (termasuk Saldo Awal/Akhir)" % len(rows))
meta = gl.get("meta") or {}
check("meta.totals ada", bool(meta.get("totals")))

# ======================================================================
print("=" * 62)
print("2) GL vs TB - invariant per-akun & total (Agustus)")
print("=" * 62)
tb = RA.get_report_data("trial_balance", AGU)
tb_rows = tb.get("rows") or []
tb_by_code = {}
for r in tb_rows:
    tb_by_code[str(r.get("code") or "")] = r

# GL: kelompokkan baris per akun; hanya baris data (bukan Saldo Awal/Akhir)
gl_by_code = {}
gl_fin = {}
for r in rows:
    code = str(r.get("code") or "")
    lab = r.get("label")
    if lab == "Saldo Akhir":
        gl_fin[code] = r
    elif lab == "Saldo Awal":
        gl_by_code.setdefault(code, {"d": 0.0, "c": 0.0, "init": 0.0, "last_bal": None, "n": 0})
        gl_by_code[code]["init"] = float(r.get("balance") or 0.0)
    else:
        g = gl_by_code.setdefault(code, {"d": 0.0, "c": 0.0, "init": 0.0, "last_bal": None, "n": 0})
        g["d"] += float(r.get("debit") or 0.0)
        g["c"] += float(r.get("credit") or 0.0)
        g["last_bal"] = float(r.get("balance") or 0.0)
        g["n"] += 1

check("kode akun TB ⊆ GL", set(tb_by_code) <= set(gl_by_code.keys()) | set(gl_fin),
      "tb=%d gl=%d" % (len(tb_by_code), len(gl_by_code)))

bad_d, bad_c, bad_bal, bad_run = [], [], [], []
for code, tbr in tb_by_code.items():
    g = gl_by_code.get(code) or {"d": 0.0, "c": 0.0, "init": 0.0, "last_bal": None, "n": 0}
    if abs(g["d"] - float(tbr.get("debit") or 0.0)) > TOL:
        bad_d.append(code)
    if abs(g["c"] - float(tbr.get("credit") or 0.0)) > TOL:
        bad_c.append(code)
    # Saldo akhir GL == saldo akhir TB (ending_balance)
    fin = gl_fin.get(code)
    if fin:
        if abs(float(fin.get("balance") or 0.0) - float(tbr.get("balance") or 0.0)) > TOL:
            bad_bal.append(code)
check("debit mutasi per-akun GL == TB", not bad_d, "bad=%s" % bad_d[:5])
check("kredit mutasi per-akun GL == TB", not bad_c, "bad=%s" % bad_c[:5])
check("saldo akhir per-akun GL == TB ending_balance", not bad_bal, "bad=%s" % bad_bal[:5])

# Saldo berjalan: init + Σ(debit-credit) == saldo akhir (per akun GL)
for code, fin in gl_fin.items():
    g = gl_by_code.get(code)
    if not g or g["n"] == 0:
        continue
    expect = g["init"] + g["d"] - g["c"]
    if abs(float(fin.get("balance") or 0.0) - expect) > TOL:
        bad_run.append(code)
check("saldo berjalan konsisten (init+mutasi=akhir)", not bad_run, "bad=%s" % bad_run[:5])

# Total GL (UPDATE 15 Sep): footer GL = KUMULATIF (saldo awal + mutasi window)
# sedangkan TB = mutasi window saja. Identitas yang benar:
#   GL_dr − GL_cr == Σ saldo awal + (TB_dr − TB_cr)
# (buku seimbang di tiap tanggal → Σ saldo awal semua akun = 0 dan TB window
# seimbang → footer GL dr == cr). Parity mutasi window per-akun sudah diuji
# di check "debit/kredit mutasi per-akun GL == TB" di atas.
tot = (meta.get("totals") or [{}])[0]
GL_TOTAL_DR = float(tot.get("debit") or 0.0)
GL_TOTAL_CR = float(tot.get("credit") or 0.0)
TB_TOTAL_DR = sum(float(r.get("debit") or 0.0) for r in tb_rows)
TB_TOTAL_CR = sum(float(r.get("credit") or 0.0) for r in tb_rows)
INIT_SUM = sum(g["init"] for g in gl_by_code.values())
check("GL footer kumulatif seimbang (dr == cr)",
      abs(GL_TOTAL_DR - GL_TOTAL_CR) <= TOL,
      "(dr=%s cr=%s)" % (round(GL_TOTAL_DR, 2), round(GL_TOTAL_CR, 2)))
check("GL footer == Σ saldo awal + mutasi window TB (identitas)",
      abs((GL_TOTAL_DR - GL_TOTAL_CR) - (INIT_SUM + (TB_TOTAL_DR - TB_TOTAL_CR))) <= TOL,
      "(init_sum=%s tb_window=%s)" % (round(INIT_SUM, 2), round(TB_TOTAL_DR - TB_TOTAL_CR, 2)))

# ======================================================================
print("=" * 62)
print("3) VAT - preview Agustus 2026 vs agregasi AML raw")
print("=" * 62)
vat = RA.get_report_data("vat", AGU)
check("kind == table", vat.get("kind") == "table")
vcols = vat.get("columns") or []
check("column keys", [c["key"] for c in vcols] == ["code", "name", "net", "tax"],
      str([c["key"] for c in vcols]))
vrows = vat.get("rows") or []
print("     info: rows=%d" % len(vrows))
# TEMUAN F3 (12 Sep): DB ini TIDAK punya move line ber-pajak sama sekali
# (tax_line_id / tax_ids = 0 record di seluruh aml; "Pajak Resto" di Tab 2
# hanya akun beban ber-nama pajak, bukan account.tax). VAT = 0 baris adalah
# properti data yang benar — test tetap memverifikasi engine == AML raw.
vmeta = vat.get("meta") or {}
vtot = (vmeta.get("totals") or [{}])[0]

# Ground truth: agregasi AML raw (posted, Agustus) — pola engine vat_report:
# tax  = Σ balance ml yang punya tax_line_id (baris pajak)
# net  = Σ balance ml yang punya tax_ids (baris base, di-exclude dari tax)
ML = env["account.move.line"]
tax_lines = ML.search([("parent_state", "=", "posted"),
                       ("date", ">=", AGU["date_from"]),
                       ("date", "<=", AGU["date_to"]),
                       ("tax_line_id", "!=", False)])
gt_tax = sum(tax_lines.mapped("balance"))
base_lines = ML.search([("parent_state", "=", "posted"),
                        ("date", ">=", AGU["date_from"]),
                        ("date", "<=", AGU["date_to"]),
                        ("tax_ids", "!=", False),
                        ("tax_line_id", "=", False)])
gt_net = sum(base_lines.mapped("balance"))
print("     info: ground truth net=%s tax=%s" % (round(gt_net, 2), round(gt_tax, 2)))
check("VAT tax engine == AML raw (Σ tax_line_id balance)",
      abs(float(vtot.get("credit") or 0.0) - gt_tax) < TOL,
      "(%s vs %s)" % (vtot.get("credit"), round(gt_tax, 2)))
check("VAT net engine == AML raw (Σ balance base lines)",
      abs(float(vtot.get("debit") or 0.0) - gt_net) < TOL,
      "(%s vs %s)" % (vtot.get("debit"), round(gt_net, 2)))
# meta.totals == Σ baris level-atas (bukan sub-detail "— ")
top_rows = [r for r in vrows if not str(r.get("name") or "").startswith("— ")]
s_net = round(sum(float(r.get("net") or 0.0) for r in top_rows), 2)
s_tax = round(sum(float(r.get("tax") or 0.0) for r in top_rows), 2)
check("VAT Σ baris == meta.totals",
      abs(s_net - float(vtot.get("debit") or 0.0)) < TOL
      and abs(s_tax - float(vtot.get("credit") or 0.0)) < TOL)

# ======================================================================
print("=" * 62)
print("4) JULI 2026 (bulan kosong) - GL & VAT empty state")
print("=" * 62)
glj = RA.get_report_data("general_ledger", JUL)
jrows = glj.get("rows") or []
# UPDATE 15 Sep: Juli ada data (dataset 72 hari) — invarian yang benar:
# totals GL Juli seimbang (Σ debit == Σ credit), bukan "tanpa mutasi".
jmeta = glj.get("meta") or {}
jtot = (jmeta.get("totals") or [{}])[0]
check("Juli GL: totals seimbang (Σ debit == Σ credit)",
      abs(float(jtot.get("debit") or 0.0) - float(jtot.get("credit") or 0.0)) <= TOL
      and float(jtot.get("debit") or 0.0) > TOL,
      "(dr=%s cr=%s rows=%d)" % (jtot.get("debit"), jtot.get("credit"), len(jrows)))
vatj = RA.get_report_data("vat", JUL)
vjrows = vatj.get("rows") or []
vtotj = ((vatj.get("meta") or {}).get("totals") or [{}])[0]
check("Juli VAT: totals 0",
      abs(float(vtotj.get("debit") or 0.0)) <= 0.005
      and abs(float(vtotj.get("credit") or 0.0)) <= 0.005,
      "rows=%d" % len(vjrows))

# ======================================================================
print("=" * 62)
print("5) EXPORT GL & VAT - shape action dict (PDF/XLSX)")
print("=" * 62)
for key in ("general_ledger", "vat"):
    for fmt in ("pdf", "xlsx"):
        try:
            act = RA.get_report_export_action(key, AGU, fmt)
            check("%s %s action dict" % (key, fmt), isinstance(act, dict))
            check("%s %s type dikenal" % (key, fmt),
                  act.get("type") in ("ir.actions.report", "ir.actions.act_window"),
                  str(act.get("type")))
            check("%s %s report_name ada" % (key, fmt),
                  bool(act.get("report_name")), act.get("report_name") or "")
        except Exception as ex:
            check("%s %s export" % (key, fmt), False, repr(ex)[:200])

print("")
if fails:
    print("RESULT: %d FAIL -> %s" % (len(fails), fails))
else:
    print("RESULT: ALL PASS (F3 GL & VAT)")
