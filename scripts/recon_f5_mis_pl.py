# -*- coding: utf-8 -*-
"""F5(a) recon — read-only untuk desain template MIS P&L.

Cek:
  1. Kode akun existing (struktur CoA) + tipe akun per prefix.
  2. JE demo Fase 9: ada berapa, ref-nya apa.
  3. Dukungan domain di AEP (mis_builder_account) — balita pad `balp[60%]`.
  4. Struktur template Cash Flow existing (contoh: mode kolom, kpi, style).
  5. Angka baseline Agustus dari _finance_detail (target parity).

Jalankan (odoo shell, pola §2 PROGRESS_DASHBOARD.md):
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db \
    --db_port 5432 --db_user odoo --db_password odoo" \
    < scripts/recon_f5_mis_pl.py
"""
D = env["geprekyukss.dashboard.data"]
Account = env["account.account"].with_context(active_test=False)

# ------------------------------------------------------------------
# 1) Struktur CoA: kode + tipe
# ------------------------------------------------------------------
print("=== 1) CoA: kode -> tipe (grouped by prefix) ===")
accs = Account.search([])
by_type = {}
for a in accs:
    by_type.setdefault(a.account_type, []).append(a.code)
for t in sorted(by_type):
    codes = sorted(by_type[t])
    print("  %-22s n=%-3d %s ... %s" % (t, len(codes), codes[:6], codes[-2:]))

# ------------------------------------------------------------------
# 2) JE demo Fase 9 (ref '(demo)') — untuk keputusan Q8 (exclude)
# ------------------------------------------------------------------
print("")
print("=== 2) JE demo (Fase 9) ===")
Moves = env["account.move"]
demo_moves = Moves.search([("ref", "like", "(demo)"), ("state", "=", "posted")])
print("  posted JE dgn ref '(demo)': %d" % len(demo_moves))
demo_lines = env["account.move.line"].search(
    [("move_id", "in", demo_moves.ids), ("parent_state", "=", "posted")])
print("  lines: %d, debit sum=%s" % (
    len(demo_lines), round(sum(demo_lines.mapped("debit")), 2)))
for m in demo_moves[:8]:
    print("  - %s | %s | %s" % (m.name, m.ref, m.date))
# domain kandidat untuk exclude di AEP:
print("  kandidat domain AEP: [('move_id.ref','not like','(demo)')]")
print("  move_id di AEP padded: 'move_id.ref' valid karena AEP menambahkan account_id pad")

# ------------------------------------------------------------------
# 3) Angka baseline Agustus (target parity F5a)
# ------------------------------------------------------------------
print("")
print("=== 3) Baseline _finance_detail Agustus 2026 ===")
fin = D.get_dashboard_data("2026-08-01", "2026-08-31", None)["finance"]
print("  income_total  = %s" % round(fin["income_total"], 2))
print("  expense_total = %s" % round(fin["expense_total"], 2))
print("  net_profit    = %s" % round(fin["net_profit"], 2))
print("  hpp_total     = %s" % round(fin["hpp_total"], 2))
print("  depreciation_total = %s" % round(fin["depreciation_total"], 2))
print("  income breakdown:")
for r in (fin.get("incomes") or [])[:12]:
    print("    %s | %s | %s" % (r.get("code"), r.get("name"), round(r.get("amount", 0), 2)))
print("  expense breakdown (top 12):")
for r in (fin.get("expenses") or [])[:12]:
    print("    %s | %s | %s | cat=%s" % (
        r.get("code"), r.get("name"), round(r.get("amount", 0), 2), r.get("category")))
print("  income breakdown count: %d | expense count: %d" % (
    len(fin.get("incomes") or []), len(fin.get("expenses") or [])))

# ------------------------------------------------------------------
# 4) Struktur template Cash Flow existing (contoh pola resmi)
# ------------------------------------------------------------------
print("")
print("=== 4) Template Cash Flow existing (pola referensi) ===")
t_cf = env.ref("mis_builder_cash_flow.mis_report_cash_flow", raise_if_not_found=False)
if t_cf:
    print("  name=%s | basis=%s" % (t_cf.name, getattr(t_cf, "account_model", "")))
    k = t_cf.kpi_ids[:5]
    for kpi in k:
        print("  KPI: %-30s expr=%s" % (kpi.name, (kpi.expression or "")[:70]))
    print("  styles: %s" % [s.name for s in env["mis.report.style"].search([], limit=8)])
else:
    print("  mis_builder_cash_flow template tidak ditemukan")

inst_cf = env.ref("mis_builder_cash_flow.mis_instance_cash_flow", raise_if_not_found=False)
if inst_cf:
    print("  instance=%s | kolom:" % inst_cf.name)
    for p in inst_cf.period_ids[:12]:
        print("    %-28s mode=%s expr=%s" % (p.name, p.mode, (p.expr or "")[:30]))

# ------------------------------------------------------------------
# 5) Template MIS lain yang sudah ada (mungkin ada template P&L bawaan)
# ------------------------------------------------------------------
print("")
print("=== 5) Semua mis.report existing ===")
for t in env["mis.report"].search([]):
    print("  %-40s kpi=%d | %s" % (t.name, len(t.kpi_ids), t.kpi_ids[:1].expression or ""))
for i in env["mis.report.instance"].search([]):
    print("  instance: %-40s template=%s" % (i.name, i.report_id.name))

print("")
print("RESULT: recon selesai (read-only)")
