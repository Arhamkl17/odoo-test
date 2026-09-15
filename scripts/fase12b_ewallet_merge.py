# -*- coding: utf-8 -*-
"""FASE 12b — Merge e-wallet (OVO/GOPAY/SHOPEE PAY) ke BSI, net-zero.

Keputusan: kartu kas & bank tidak boleh menampilkan minus. 3 e-wallet sudah
inactive (Fase 3) dan konsolidasi ke BSI, tapi artefak backdate (sweep
MISC/0053 31 Agu vs setoran 1 Sep) membuat saldo per-31-Agu minus. Karena
kode dashboard termasuk akun arsip (active_test=False), minus ini masih
tampil di kartu.

Metode: SEMUA move line (debit DAN kredit) 3 e-wallet -> BSI. Selisih net
= 0, jadi BSI tetap 157.302.634,81 dan BNI tetap 23.022.406,00 (split
keputusan user tidak berubah). E-wallet jadi 0 line -> minus hilang.

Konvensi repo: dry-run default; RUN=1 utk eksekusi. Backup penuh sudah
ada: backup_pre_fase12_2026-09-12.dump (pre-Fase 12, valid utk rollback
total). Hash chain MISC/0053 akan flagged inconsistent (rewrite history,
disetujui user).
"""

import os
import sys

RUN = os.environ.get("RUN") == "1"
cr = env.cr
Aml = env["account.move.line"]
Account = env["account.account"].with_context(active_test=False)


def abort(msg):
    print("ABORT: %s" % msg)
    sys.exit(1)


def bal(acc):
    res = Aml._read_group(
        [("account_id", "=", acc.id), ("parent_state", "=", "posted")],
        ["account_id"], ["debit:sum", "credit:sum"])
    if not res:
        return 0.0, 0.0, 0.0
    deb, cred = res[0][1] or 0.0, res[0][2] or 0.0
    return deb, cred, deb - cred


def find(name):
    recs = Account.search([("name", "=ilike", name), ("account_type", "=", "asset_cash")])
    if len(recs) != 1:
        abort("akun '%s' tidak unik: %s" % (name, recs.mapped("name")))
    return recs


bsi = find("Bank BSI")
bni = find("Bank BNI")
srcs = [find("OVO"), find("GOPAY"), find("SHOPEE PAY")]

snap_bsi = bal(bsi)[2]
snap_bni = bal(bni)[2]
print("=== SNAPSHOT ===")
for a in srcs:
    d, c, b = bal(a)
    print("  %-24s D %14.2f K %14.2f = %14.2f (active=%s)" % (a.name, d, c, b, a.active))
print("  Bank BSI = %.2f | Bank BNI = %.2f" % (snap_bsi, snap_bni))
for a in srcs:
    d, c, b = bal(a)
    if abs(b) > 0.005:
        abort("e-wallet %s tidak net-zero (%.2f) — investigasi manual" % (a.name, b))

plan = []
for a in srcs:
    for l in Aml.search([("account_id", "=", a.id), ("parent_state", "=", "posted")], order="date, id"):
        plan.append((l.id, a.name, l.date, l.debit or 0.0, l.credit or 0.0, l.move_id.name))
print("\n=== PLAN: %d lines -> BSI (net zero) ===" % len(plan))

if not RUN:
    print("\nDRY-RUN — tidak ada perubahan. RUN=1 utk eksekusi.")
    sys.exit(0)

print("\n=== EKSEKUSI (SQL) ===")
cr.execute("SAVEPOINT fase12b")
for lid, src, *_ in plan:
    cr.execute("UPDATE account_move_line SET account_id = %s WHERE id = %s", (bsi.id, lid))
for a in srcs:
    cr.execute("UPDATE account_account SET active = FALSE WHERE id = %s", (a.id,))
print("  %d line di-update; 3 akun dinonaktifkan" % len(plan))

# Verifikasi
bsi_after = bal(bsi)[2]
bni_after = bal(bni)[2]
print("\n=== VERIFIKASI ===")
print("  Bank BSI = %.2f (before %.2f, delta %.2f)" % (bsi_after, snap_bsi, bsi_after - snap_bsi))
print("  Bank BNI = %.2f (before %.2f)" % (bni_after, snap_bni))
for a in srcs:
    print("  %-24s (inactive) saldo %.2f" % (a.name, bal(a)[2]))
ok = True
if abs(bsi_after - snap_bsi) > 0.005:
    print("  !!! BSI berubah — GAGAL")
    ok = False
if abs(bni_after - snap_bni) > 0.005:
    print("  !!! BNI berubah — GAGAL")
    ok = False
if not ok:
    cr.execute("ROLLBACK TO SAVEPOINT fase12b")
    sys.exit(1)

env.cr.commit()
print("\nCOMMITTED ✓ — BSI/BNI tidak berubah; minus e-wallet hilang.")