# -*- coding: utf-8 -*-
"""F4 — daftarkan aset tetap ke register OCA `account_asset_management`.

Temuan (inspeksi 15 Sep 2026): 3 aset tetap (Rp 760 jt bruto) ada di buku besar
tetapi **tidak** ada satu pun baris di register `account.asset`; penyusutan
dibukukan manual lewat JE `MISC` tiap bulan.

Keputusan pemilik (15 Sep 2026):
  1. **Renovasi TIDAK didaftarkan** — aset renovasi punya akumulasi
     Rp 4.073.234,41 tetapi nilai perolehan (1105.04) = 0 dan tidak pernah masuk
     akun lain; gap ini dibiarkan sebagai temuan terbuka (lihat ringkasan F4).
  2. **Kendaraan mulai disusutkan** dengan masa manfaat 8 tahun: nilai perolehan
     150 jt, akumulasi s.d. 31 Agu 2026 Rp 37,5 jt (= 2 tahun × 18,75 jt/th),
     sisa buku Rp 112,5 jt disusutkan 72 bulan → **Rp 1.562.500,00/bulan**.
  3. **Belum diposting**: register + jadwal dibuat, JE penyusutan September 2026
     TIDAK dibuat supaya invarian dataset (berakhir 31 Agu 2026, 0 jurnal ≥ 1 Sep)
     tetap terjaga. Posting bulanan dilakukan lewat modul (tombol Post / cron
     `ir_cron_assets_generator`) kapan pun pemilik ingin mulai berjalan.

Cara kerja (mengikuti konvensi modul — lihat `_compute_depreciation_line`):
  * 1 baris `type='create'` = dasar penyusutan (dibuat otomatis oleh modul).
  * 1 baris historis `init_entry=True` per aset = akumulasi penyusutan yang
    SUDAH dibukukan manual s.d. 31 Agu 2026 → modul tidak membuat JE untuk baris
    ini (`_compute_depreciation` menghitungnya sebagai nilai tersusut).
  * baris bulanan mulai 30 Sep 2026 dengan `amount` PERSIS sama dengan beban
    penyusutan yang berlaku sekarang (angka dari dataset/klien); baris terakhir
    menyerap pembulatan sehingga Σ seluruh baris = nilai perolehan.
  * baris pertama tidak punya `previous_id` (konvensi modul saat belum ada baris
    terposting), sisanya dirantai lewat `previous_id` supaya kolom
    "Nilai Tersusut"/"Sisa" pada register benar.

Jalankan (odoo shell, pola resmi proyek) — DRY-RUN default:
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db \
    --db_port 5432 --db_user odoo --db_password odoo --log-level=warn" \
    < scripts/perbaikan_14_register_aset.py

Eksekusi: tambahkan RUN=1 (commit di akhir).
Uji dulu di database salinan: DB_NAME=<db lab> + `scripts/restore_full_system.sh`.

Env:
  RUN=1          eksekusi (default: hanya laporan)
  RESET=1        hapus register aset buatan skrip ini (butuh RUN=1; menolak bila ada
                 baris penyusutan terposting — aman karena F4 tidak memposting apa pun)

Skrip idempotent: aset yang sudah punya jadwal penyusutan dilewati, jadi aman
dijalankan ulang.
  MAX_LINES=600  pengaman jumlah baris jadwal per aset
"""
import os
from calendar import monthrange
from datetime import date

RUN = os.environ.get("RUN", "") == "1"
RESET = os.environ.get("RESET", "") == "1"
MAX_LINES = int(os.environ.get("MAX_LINES", "600"))

env = env  # noqa: F821  (disediakan odoo shell)
Account = env["account.account"].with_context(active_test=False)
Profile = env["account.asset.profile"]
Asset = env["account.asset"].with_context(active_test=False)
Line = env["account.asset.line"]
AML = env["account.move.line"].with_context(active_test=False)

CUTOFF = "2026-08-31"          # akhir jendela dataset 72 hari
FIRST_DEP = (2026, 9)          # penyusutan berikutnya: September 2026
OPEN_DATE = "2026-06-19"       # tanggal saldo awal portofolio
JOURNAL_CODE = "MISC"

# (nama, kode, akun bruto, akun akumulasi, akun beban, bruto, bulanan, catatan)
ASSETS = [
    ("Peralatan Resto", "AST-2026-001", "1105.03", "1106.03", "6101.16",
     500_000_000.00, 3_027_466.20, "beban/bulan = angka dataset (JE MISC Jun-Agu)"),
    ("Peralatan Kantor", "AST-2026-002", "1105.02", "1106.02", "6101.15",
     110_000_000.00, 1_581_701.57, "beban/bulan = angka dataset (JE MISC Jun-Agu)"),
    ("Kendaraan", "AST-2026-003", "1105.01", "1106.01", "6101.14",
     150_000_000.00, 1_562_500.00, "keputusan pemilik: masa manfaat 8 th, "
     "akumulasi 37,5 jt = 2 th → sisa 112,5 jt / 72 bln"),
]

fails = []


def head(t):
    print("\n=== %s ===" % t)


def money(x):
    return "{:,.2f}".format(float(x or 0))


def acc(code):
    a = Account.search([("code", "=", code)], limit=1)
    if not a:
        fails.append("akun %s tidak ditemukan" % code)
    return a


def months(start, n):
    """Tanggal akhir bulan ke-i mulai bulan `start` (year, month)."""
    y, m = start
    for _i in range(n):
        last = monthrange(y, m)[1]
        yield date(y, m, last)
        m += 1
        if m > 12:
            m = 1
            y += 1


def gl_accumulated(acc_id):
    """Akumulasi penyusutan sudah terposting s.d. CUTOFF (sisi kredit)."""
    mls = AML.search([("account_id", "=", acc_id), ("parent_state", "=", "posted"),
                      ("date", "<=", CUTOFF)])
    return abs(sum(mls.mapped("debit")) - sum(mls.mapped("credit")))


def gl_monthly(acc_id, d1="2026-08-01", d2="2026-08-31"):
    mls = AML.search([("account_id", "=", acc_id), ("parent_state", "=", "posted"),
                      ("date", ">=", d1), ("date", "<=", d2)])
    return sum(mls.mapped("debit")) - sum(mls.mapped("credit"))


def plan_lines(gross, accumulated, monthly):
    """Daftar (tanggal, jumlah) baris bulanan sampai nilai perolehan lunas."""
    remaining = round(gross - accumulated, 2)
    out = []
    for dt in months(FIRST_DEP, MAX_LINES):
        if remaining <= 0.005:
            break
        amt = monthly if remaining - monthly > 0.005 else remaining
        out.append((dt, round(amt, 2)))
        remaining = round(remaining - amt, 2)
    return out, remaining


# ---------------------------------------------------------------------------
# 0) inventaris & validasi terhadap buku besar
# ---------------------------------------------------------------------------
head("0) Register aset saat ini")
existing = Asset.search([])
print("  asset di register : %s" % ([(a.code or '-', a.name, a.state) for a in existing] or "kosong"))
print("  profile aset      : %s" % Profile.search_count([]))
for a in existing:
    print("    id=%s %s %s state=%s buku=%s" % (a.id, a.code, a.name, a.state, money(a.value_residual)))

if RESET and RUN:
    head("0b) RESET — hapus register aset buatan skrip ini")
    codes = [c for _n, c, *_r in ASSETS]
    target = existing.filtered(lambda a: a.code in codes)
    print("  aset yang dihapus: %s" % [(a.code, a.name, a.state) for a in target])
    posted = target.filtered(
        lambda a: a.depreciation_line_ids.filtered(
            lambda l: l.type == "depreciate" and l.move_check))
    if posted:
        print("  DIBATALKAN: ada baris penyusutan terposting → %s" % [(a.code, a.name) for a in posted])
    else:
        # aset 'open' tanpa baris terposting boleh dibalik ke draft lalu dihapus
        target.filtered(lambda a: a.state != "draft").set_to_draft()
        target.unlink()
        prof = Profile.search([("name", "like", "Penyusutan %")])
        print("  profile dihapus : %s" % prof.mapped("name"))
        prof.unlink()
        env.cr.commit()
        print("  RESET SELESAI (commit)")
    raise SystemExit(0)

head("1) Validasi angka terhadap buku besar")
misc = env["account.journal"].search([("code", "=", JOURNAL_CODE)], limit=1)
if not misc:
    fails.append("jurnal %s tidak ditemukan" % JOURNAL_CODE)
plan = []
for name, code, acc_gross, acc_dep, acc_exp, gross, monthly, note in ASSETS:
    a_gross, a_dep, a_exp = acc(acc_gross), acc(acc_dep), acc(acc_exp)
    gl_gross = sum(AML.search([("account_id", "=", a_gross.id), ("parent_state", "=", "posted")]).mapped("debit")) \
        - sum(AML.search([("account_id", "=", a_gross.id), ("parent_state", "=", "posted")]).mapped("credit"))
    accu = gl_accumulated(a_dep.id)
    aug = gl_monthly(a_exp.id)
    rows, sisa = plan_lines(gross, accu, monthly)
    print("  %-18s bruto GL %18s | akumulasi %18s | beban Agu %14s | %3d baris s/d %s" % (
        name, money(gl_gross), money(accu), money(aug), len(rows), rows[-1][0]))
    if abs(gl_gross - gross) > 0.01:
        fails.append("bruto %s: GL %s != rencana %s" % (name, gl_gross, gross))
    if abs(aug - monthly) > 0.01 and aug:
        fails.append("beban %s: JE Agustus %s != rencana %s" % (name, aug, monthly))
    if sisa > 0.005:
        fails.append("%s: jadwal belum lunas, sisa %s" % (name, sisa))
    print("      %s" % note)
    plan.append(dict(name=name, code=code, gross=gross, accu=accu, monthly=monthly,
                     acc_gross=a_gross, acc_dep=a_dep, acc_exp=a_exp, rows=rows))

head("2) Ringkasan jadwal penyusutan yang akan dibuat")
sep = sum(p["monthly"] for p in plan)
print("  %-18s %18s %18s %14s %10s %s" % ("ASET", "NILAI PEROLEHAN", "AKUMULASI", "SISA BUKU", "BULANAN", "SELESAI"))
for p in plan:
    print("  %-18s %18s %18s %18s %14s %s" % (
        p["name"], money(p["gross"]), money(p["accu"]), money(p["gross"] - p["accu"]),
        money(p["monthly"]), p["rows"][-1][0]))
print("  total beban penyusutan per bulan (Sep 2026 dst) = %s" % money(sep))
print("  (Renovasi tidak didaftarkan sesuai keputusan pemilik: akumulasi 4.073.234,41 tetap manual)")

if not RUN:
    print("\nDRY-RUN — tidak ada data ditulis. Jalankan dengan RUN=1 untuk mengeksekusi.")
    print("\nRESULT: %s" % ("SIAP (dry-run)" if not fails else "ADA MASALAH -> %s" % fails))
    raise SystemExit(0 if not fails else 1)

if fails:
    print("\nDIBATALKAN — perbaiki dulu: %s" % fails)
    raise SystemExit(1)

# ---------------------------------------------------------------------------
# 3) eksekusi
# ---------------------------------------------------------------------------
head("3) Registrasi aset + jadwal penyusutan")
created = []
for p in plan:
    prof = Profile.search([("name", "=", "Penyusutan %s (garis lurus bulanan)" % p["name"])], limit=1)
    if not prof:
        prof = Profile.create({
            "name": "Penyusutan %s (garis lurus bulanan)" % p["name"],
            "method": "linear",
            "method_time": "number",
            "method_period": "month",
            "method_number": len(p["rows"]),
            "account_asset_id": p["acc_gross"].id,
            "account_depreciation_id": p["acc_dep"].id,
            "account_expense_depreciation_id": p["acc_exp"].id,
            "journal_id": misc.id,
            "company_id": env.company.id,
            "note": "Dibuat oleh scripts/perbaikan_14_register_aset.py (F4, 15 Sep 2026)",
        })
    a = Asset.search([("code", "=", p["code"])], limit=1)
    if a and a.depreciation_line_ids.filtered(
            lambda l: l.type == "depreciate" and not l.init_entry):
        print("  %-18s sudah terdaftar %s state=%s buku=%s jadwal=%s baris — DILEWATI" % (
            p["name"], a.code, a.state, money(a.value_residual),
            len(a.depreciation_line_ids.filtered(lambda l: l.type == "depreciate" and not l.init_entry))))
        created.append(a)
        continue
    if not a:
        a = Asset.create({
            "name": p["name"], "code": p["code"], "profile_id": prof.id,
            "purchase_value": p["gross"], "salvage_value": 0.0,
            "date_start": OPEN_DATE, "company_id": env.company.id,
            "note": "Register aset F4 (15 Sep 2026). Akumulasi s.d. 31 Agu 2026 dan "
                    "jadwal bulanan dibangun manual mengikuti konvensi modul "
                    "(`init_entry` untuk periode yang sudah dibukukan).",
        })
    # baris historis (akumulasi s.d. 31 Agu) + baris bulanan (rantai previous_id)
    prev = Line
    hist = Line.create({
        "asset_id": a.id, "name": "Akumulasi s.d. 31 Agu 2026 (manual)",
        "amount": p["accu"], "line_date": CUTOFF, "type": "depreciate",
        "init_entry": True, "previous_id": False,
    })
    prev = hist
    for i, (dt, amt) in enumerate(p["rows"], start=1):
        prev = Line.create({
            "asset_id": a.id, "name": "Penyusutan %s" % dt.strftime("%m/%Y"),
            "amount": amt, "line_date": dt, "type": "depreciate",
            "previous_id": prev.id,
        })
    a.validate()          # state: draft -> open (jadwal sudah ada, modul tidak menghitung ulang)
    env.cr.commit()
    a.invalidate_recordset()
    created.append(a)
    n_plan = len(a.depreciation_line_ids.filtered(lambda l: l.type == "depreciate" and not l.init_entry))
    print("  %-18s dibuat: %s state=%s buku=%s jadwal=%s baris" % (
        p["name"], a.code, a.state, money(a.value_residual), n_plan))

# ---------------------------------------------------------------------------
# 4) verifikasi
# ---------------------------------------------------------------------------
head("4) Verifikasi register")
ok = True
# catatan: baris `type='create'` bawaan modul JUGA ber-`init_entry=True`
# (lihat `_create_first_asset_line`) — jadi akumulasi harus disaring per tipe.
for a in created:
    lines = a.depreciation_line_ids
    create = lines.filtered(lambda l: l.type == "create")
    hist = lines.filtered(lambda l: l.type == "depreciate" and l.init_entry)
    planned = lines.filtered(lambda l: l.type == "depreciate" and not l.init_entry)
    total_planned = sum(planned.mapped("amount"))
    sisa = a.purchase_value - sum(hist.mapped("amount"))
    sep_amt = sum(planned.filtered(lambda l: date(2026, 9, 1) <= l.line_date <= date(2026, 9, 30)).mapped("amount"))
    print("  %-18s bruto %18s | akumulasi %16s | buku %18s | jadwal %3d baris = %18s | Sep %14s" % (
        a.name, money(a.purchase_value), money(sum(hist.mapped("amount"))), money(a.value_residual),
        len(planned), money(total_planned), money(sep_amt)))
    if len(create) != 1 or abs(sum(create.mapped("amount")) - a.depreciation_base) > 0.01:
        fails.append("%s: baris dasar penyusutan (type=create) tidak sesuai" % a.name)
        ok = False
    if len(hist) != 1:
        fails.append("%s: baris akumulasi historis harus 1, ada %s" % (a.name, len(hist)))
        ok = False
    if abs(a.value_residual - sisa) > 0.01:
        fails.append("%s: nilai buku register (%s) != bruto-akumulasi (%s)" % (a.name, a.value_residual, sisa))
        ok = False
    if abs(sum(hist.mapped("amount")) + total_planned - a.purchase_value) > 0.01:
        fails.append("%s: akumulasi + jadwal != nilai perolehan" % a.name)
        ok = False
    if planned.filtered(lambda l: l.move_id):
        fails.append("%s: ada baris jadwal yang sudah terposting" % a.name)
        ok = False
    if planned and planned[-1].line_date < date(2026, 9, 1):
        fails.append("%s: baris jadwal terakhir sebelum Sep 2026" % a.name)
        ok = False

n_moves = env["account.move"].search_count([])
print("  jumlah jurnal di sistem : %s (tidak berubah — F4 tidak membuat JE)" % n_moves)
print("  lock period             : %s" % (env.company.fiscalyear_lock_date or "(kosong)"))

print("\n--- RINGKASAN ---")
print("  aset terdaftar : %s" % [(a.code, a.name, a.state) for a in created])
print("  fails          : %s" % (fails or "tidak ada"))
print("RESULT: %s" % ("SELESAI" if not fails else "ADA MASALAH -> %s" % fails))
