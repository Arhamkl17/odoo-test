# -*- coding: utf-8 -*-
"""
P1 — PERBAIKAN: reaktivasi akun `Bank BNI` (1101.07) + journal bank BNI.

Latar (JUNI_JULI_DATA-spec.md §12.5):
  - `fase3_execute.py`:134-142 menonaktifkan semua akun kas/bank bersaldo < 0,01
    (saat itu BNI sudah di-sweep ke BSI -> saldo 0) => Bank BNI dimatikan.
  - `fase3_execute.py`:171-173 menonaktifkan journal id 18-24 (.../BCA/BNI/BRI/BMR).
  - `fase12_bank_merge.py` memakai Bank BNI sebagai TARGET merge, tapi tidak pernah
    mengaktifkan ulang akun maupun journal-nya.
  => Akun bersaldo tapi mati & tak bisa menerima transaksi baru.

Yang dilakukan skrip ini (HANYA ini):
  1. `account.account` 1101.07 -> active = True (via ORM; bukan rewrite posted move,
     hash chain tidak tersentuh).
  2. Journal bank untuk BNI: aktifkan journal nonaktif yang `default_account_id`
     = akun BNI; bila tidak ada, buat journal baru (code BNI, type bank).
  3. Tidak menyentuh akun/jurnal lain; tidak mengubah saldo/histori.

Guard: saldo BNI & total trial balance TIDAK boleh berubah. Kalau berubah -> rollback.

Konvensi repo: default DRY-RUN. Eksekusi nyata = env RUN=1.
  su odoo -s /bin/bash -c "cd /workspaces/odoo-test && odoo shell -d Test1 --no-http \
    --db_host db --db_port 5432 --db_user odoo --db_password odoo" < scripts/juni_juli_02a_fix_bni.py
  # eksekusi:
  su odoo -s /bin/bash -c "cd /workspaces/odoo-test && RUN=1 odoo shell -d Test1 --no-http \
    --db_host db --db_port 5432 --db_user odoo --db_password odoo" < scripts/juni_juli_02a_fix_bni.py
"""
import os
import sys

RUN = os.environ.get("RUN") == "1"
cr = env.cr
Aml = env["account.move.line"]
Account = env["account.account"].with_context(active_test=False)
Journal = env["account.journal"].with_context(active_test=False)

BNI_CODE = "1101.07"
SEP = "=" * 78


def sec(t):
    print("\n" + SEP + "\n" + t + "\n" + SEP)


def abort(msg):
    print("\nABORT: %s" % msg)
    env.cr.rollback()
    sys.exit(1)


def bal(acc):
    """Saldo posted kumulatif akun."""
    res = Aml._read_group(
        [("account_id", "=", acc.id), ("parent_state", "=", "posted")],
        ["account_id"], ["debit:sum", "credit:sum"])
    if not res:
        return 0.0
    return (res[0][1] or 0.0) - (res[0][2] or 0.0)


def tb_diff():
    res = Aml._read_group([("parent_state", "=", "posted")], [], ["debit:sum", "credit:sum"])
    return (res[0][0] or 0.0) - (res[0][1] or 0.0)


# ===========================================================================
sec("1. SNAPSHOT SEBELUM")
# ===========================================================================
bni = Account.search([("code", "=", BNI_CODE)])
if len(bni) != 1:
    abort("akun code %s tidak unik (%d record): %s" % (BNI_CODE, len(bni), bni.mapped("name")))
bni_before_active = bni.active
bni_before_bal = bal(bni)
tb_before = tb_diff()

print("akun      : [%d] %s (%s) | active=%s" % (bni.id, bni.name, bni.code, bni.active))
print("saldo     : Rp %s" % "{:,.2f}".format(bni_before_bal))
print("TB diff   : Rp %s" % "{:,.2f}".format(tb_before))

sec("2. JOURNAL YANG MEMAKAI AKUN BNI")
cands = Journal.search([("default_account_id", "=", bni.id)], order="id")
print("kandidat (semua, termasuk nonaktif): %d" % len(cands))
for j in cands:
    print("   [%d] code=%-8s name=%-28s type=%-7s active=%s" % (
        j.id, j.code or "-", (j.name or "-")[:28], j.type, j.active))

active_j = cands.filtered(lambda j: j.active)
inactive_j = cands - active_j
print("   aktif   : %s" % (active_j.mapped("code") or "-"))
print("   nonaktif: %s" % (inactive_j.mapped("code") or "-"))

sec("3. KONTEKS: journal nonaktif lain (id 18-24 dari Fase 3)")
for j in env["account.journal"].with_context(active_test=False).browse([18, 19, 20, 21, 22, 23, 24]).exists():
    d = j.default_account_id
    print("   [%d] code=%-8s name=%-26s type=%-7s active=%-5s default=%s" % (
        j.id, j.code or "-", (j.name or "-")[:26], j.type, j.active,
        ("%s %s" % (d.code, d.name)) if d else "-"))

# ===========================================================================
sec("4. RENCANA")
# ===========================================================================
plan = []
if not bni_before_active:
    plan.append("aktifkan akun 1101.07 '%s'" % bni.name)
else:
    print("   akun BNI SUDAH aktif — tidak ada aksi untuk akun")

journal_to_activate = None
journal_to_create = False
if active_j:
    print("   journal aktif sudah ada: %s — tidak ada aksi untuk journal" % active_j.mapped("code"))
elif inactive_j:
    journal_to_activate = inactive_j[0]
    plan.append("aktifkan journal [%d] code=%s name=%s" % (
        journal_to_activate.id, journal_to_activate.code, journal_to_activate.name))
else:
    journal_to_create = True
    plan.append("buat journal baru code=BNI type=bank default=1101.07")

for p in plan:
    print("   - " + p)
if not plan:
    print("   (tidak ada yang perlu dilakukan — sudah beres)")

if not RUN:
    print("\nDRY-RUN — tidak ada perubahan. Jalankan dengan RUN=1 untuk eksekusi.")
    env.cr.rollback()
    sys.exit(0)

# ===========================================================================
sec("5. EKSEKUSI")
# ===========================================================================
cr.execute("SAVEPOINT p1")
if not bni_before_active:
    bni.active = True
    print("   akun 1101.07 -> active=True")

if journal_to_activate is not None:
    journal_to_activate.active = True
    # pastikan metadata journal konsisten utk dipakai transaksi bank
    vals = {}
    if journal_to_activate.type != "bank":
        vals["type"] = "bank"
    if not journal_to_activate.default_account_id:
        vals["default_account_id"] = bni.id
    if vals:
        journal_to_activate.write(vals)
        print("   journal [%d] metadata diperbaiki: %s" % (journal_to_activate.id, vals))
    print("   journal [%d] %s -> active=True" % (journal_to_activate.id, journal_to_activate.code))
elif journal_to_create:
    newj = Journal.create({
        "name": "Bank BNI",
        "code": "BNI",
        "type": "bank",
        "default_account_id": bni.id,
        "company_id": env.company.id,
    })
    print("   journal baru dibuat: [%d] code=%s" % (newj.id, newj.code))

env.flush_all()

# ===========================================================================
sec("6. VERIFIKASI (guard)")
# ===========================================================================
ok = True
cr.execute("SELECT active FROM account_account WHERE id = %s", (bni.id,))
db_active = cr.fetchone()[0]
print("   akun active (dari DB)  :", db_active)
if not db_active:
    print("   !!! akun masih nonaktif")
    ok = False

bni_after_bal = bal(bni)
tb_after = tb_diff()
print("   saldo BNI sesudah      : Rp %s (sebelum Rp %s)" % (
    "{:,.2f}".format(bni_after_bal), "{:,.2f}".format(bni_before_bal)))
if abs(bni_after_bal - bni_before_bal) > 0.005:
    print("   !!! SALDO BNI BERUBAH")
    ok = False

print("   TB diff sesudah        : Rp %s (sebelum Rp %s)" % (
    "{:,.2f}".format(tb_after), "{:,.2f}".format(tb_before)))
if abs(tb_after - tb_before) > 0.005:
    print("   !!! TRIAL BALANCE BERUBAH")
    ok = False

j_now = Journal.search([("default_account_id", "=", bni.id), ("active", "=", True)])
print("   journal aktif utk BNI  : %s" % (j_now.mapped("code") or "*** TIDAK ADA ***"))
if not j_now:
    ok = False

# hanya 1 akun yang boleh berubah status
changed = env["account.account"].with_context(active_test=False).search_count([])
n_inactive_cash = Account.search_count([("account_type", "=", "asset_cash"), ("active", "=", False)])
print("   akun kas/bank nonaktif tersisa: %d (BCA/BRI/Mandiri/OVO/GOPAY/SPPAY/Mallengkeri)" % n_inactive_cash)

# journal lain tidak ikut berubah
other_active = env["account.journal"].search([("type", "in", ["bank", "cash"])]).mapped("code")
print("   journal bank/kas aktif :", other_active)

if not ok:
    cr.execute("ROLLBACK TO SAVEPOINT p1")
    print("\nROLLBACK — tidak ada perubahan tersimpan.")
    sys.exit(1)

env.cr.commit()
print("\nCOMMITTED ✓ — Bank BNI aktif kembali & punya journal bank.")
print("Sisa: (opsional) restart server + hard-reload browser untuk cek kartu kas & bank.")
