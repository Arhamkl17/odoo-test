# -*- coding: utf-8 -*-
"""Uji F4 — register aset tetap + jadwal penyusutan (baca-saja, tanpa menulis data).

Memverifikasi:
  1. 3 aset terdaftar (`AST-2026-001..003`) dengan nilai perolehan/akumulasi/
     nilai buku sesuai angka buku besar;
  2. Σ baris akumulasi historis + Σ baris jadwal = nilai perolehan tiap aset;
  3. Σ seluruh baris jadwal = Σ nilai buku register (tidak ada sisa menggantung);
  4. beban penyusutan bulanan register = angka yang disetujui pemilik;
  5. panel dashboard "Jadwal Penyusutan Mendatang" terisi dari register
     (agregat 12 bulan pertama setelah periode laporan).

Jalankan (pola resmi proyek):
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db \\
    --db_port 5432 --db_user odoo --db_password odoo --log-level=warn" \\
    < scripts/test_f4_asset_schedule.py
"""
from datetime import date

env = env  # noqa: F821
Asset = env["account.asset"].with_context(active_test=False)
Dash = env["geprekyukss.dashboard.data"]

ok_all = True


def check(label, got, want, tol=0.01):
    global ok_all
    good = abs(float(got) - float(want)) <= tol
    ok_all = ok_all and good
    print("  [%s] %-58s got=%s want=%s" % ("PASS" if good else "FAIL", label, got, want))


EXPECTED = {
    "AST-2026-001": ("Peralatan Resto", 500_000_000.00, 132_165_003.34, 3_027_466.20, 122),
    "AST-2026-002": ("Peralatan Kantor", 110_000_000.00, 31_243_360.38, 1_581_701.57, 50),
    "AST-2026-003": ("Kendaraan", 150_000_000.00, 37_500_000.00, 1_562_500.00, 72),
}

print("=== 1) Register aset ===")
assets = Asset.search([])
check("jumlah aset di register", len(assets), 3)
for code, (name, gross, accum, monthly, n_lines) in EXPECTED.items():
    a = assets.filtered(lambda r: r.code == code)
    check("%s ada" % code, 1 if a else 0, 1)
    if not a:
        continue
    a = a[0]
    check("%s nama" % code, 1 if a.name == name else 0, 1)
    check("%s state=open" % code, 1 if a.state == "open" else 0, 1)
    check("%s nilai perolehan" % code, a.purchase_value, gross)
    lines = a.depreciation_line_ids
    hist = lines.filtered(lambda l: l.type == "depreciate" and l.init_entry)
    plan = lines.filtered(lambda l: l.type == "depreciate" and not l.init_entry)
    check("%s akumulasi s.d. 31 Agu" % code, sum(hist.mapped("amount")), accum)
    check("%s jumlah baris jadwal" % code, len(plan), n_lines)
    check("%s Σ baris jadwal (= nilai buku)" % code, sum(plan.mapped("amount")), gross - accum)
    check("%s nilai buku register" % code, a.value_residual, gross - accum)
    check("%s beban bulan pertama" % code, plan[0].amount, monthly)
    check("%s baris pertama >= Sep 2026" % code, 1 if plan[0].line_date >= date(2026, 9, 1) else 0, 1)
    check("%s belum ada baris terposting" % code, len(plan.filtered(lambda l: l.move_check)), 0)
    end = {"AST-2026-001": "2036-10-31", "AST-2026-002": "2030-10-31",
           "AST-2026-003": "2032-08-31"}[code]
    check("%s jadwal berakhir %s" % (code, end),
          1 if plan[-1].line_date == date.fromisoformat(end) else 0, 1)

print("\n=== 2) Total register ===")
check("Σ nilai perolehan", sum(assets.mapped("purchase_value")), 760_000_000.00)
check("Σ akumulasi", sum(assets.mapped("value_depreciated")), 200_908_363.72)
check("Σ nilai buku", sum(assets.mapped("value_residual")), 559_091_636.28)
check("Σ beban penyusutan register / bulan", sum(
    a.depreciation_line_ids.filtered(lambda l: l.type == "depreciate" and not l.init_entry
                                     and l.line_date <= date(2026, 9, 30)).mapped("amount")),
    6_171_667.77)
check("Σ baris jadwal (belum diposting) di register",
      env["account.asset.line"].search_count([("type", "=", "depreciate"), ("init_entry", "=", False)]), 244)
check("baris terposting (harus 0 — F4 tidak memposting)",
      env["account.asset.line"].search_count([("move_check", "=", True)]), 0)

print("\n=== 3) Panel dashboard 'Jadwal Penyusutan Mendatang' ===")
data = Dash.get_dashboard_data("2026-06-01", "2026-08-31")
ops = data.get("ops", {}).get("assets", {})
sched = ops.get("schedule") or []
check("panel punya baris jadwal", 1 if sched else 0, 1)
check("baris pertama = Sep 2026", 1 if sched and sched[0]["month"] == "2026-09" else 0, 1)
check("max 12 bulan", 1 if len(sched) <= 12 else 0, 1)
plan_all = env["account.asset.line"].search([
    ("type", "=", "depreciate"), ("init_entry", "=", False),
    ("line_date", ">", "2026-08-31"), ("line_date", "<=", "2027-08-31")])
check("Σ bulan 1-12 = jadwal register (Sep 2026-Agu 2027)",
      ops.get("schedule_total"), sum(plan_all.mapped("amount")))
check("label bulan pertama terbaca", 1 if sched and sched[0]["label"].endswith("2026") else 0, 1)

print("\nRESULT: %s (F4 register aset)" % ("ALL PASS" if ok_all else "ADA YANG GAGAL"))
