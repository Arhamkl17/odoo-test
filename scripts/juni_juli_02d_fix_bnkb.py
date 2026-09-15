# -*- coding: utf-8 -*-
"""
P4 — Perbaiki journal `BNKB` (Mallengkeri Bank): default account diarahkan ke BSI.

Masalah (temuan §13.4 JUNI_JULI_DATA-spec.md):
  - `account.journal` code=BNKB (type=bank, aktif) `default_account_id` =
    `1112001 Bank Mallengkeri` yang berstatus **NONAKTIF** (dimatikan Fase 12 setelah
    seluruh mutasinya di-merge ke BSI).
  - `pos.payment.method` id 9 `Mallengkeri Kartu` memakai journal BNKB.
    => Setiap sesi POS Mallengkeri (termasuk Juni/Juli yang akan dibuat) akan
       memposting pembayaran kartu ke akun MATI, merusak struktur "BNI + BSI saja".

Perbaikan: `BNKB.default_account_id` -> **`1101.01 Bank BSI`** (menyambung konsolidasi
Fase 12). Tidak ada saldo/histori yang diubah — hanya konfigurasi journal.

Guard: saldo semua akun kas/bank + TB diff + jumlah move BNKB tidak boleh berubah.

Konvensi repo: DRY-RUN default, RUN=1 untuk eksekusi.
"""
import os
import sys

RUN = os.environ.get("RUN") == "1"
cr = env.cr
Aml = env["account.move.line"]
Acc = env["account.account"].with_context(active_test=False)
Journal = env["account.journal"].with_context(active_test=False)
PM = env["pos.payment.method"].with_context(active_test=False)

SEP = "=" * 78
TARGET_CODE = "BNKB"
BSI_CODE = "1101.01"


def sec(t):
    print("\n" + SEP + "\n" + t + "\n" + SEP)


def abort(msg):
    print("\nABORT: %s" % msg)
    env.cr.rollback()
    sys.exit(1)


def rp(v):
    return "{:,.2f}".format(v or 0.0)


def bal(acc_id):
    r = Aml._read_group([("account_id", "=", acc_id), ("parent_state", "=", "posted")],
                        [], ["balance:sum"])
    return sum(x or 0.0 for x in r[0]) if r else 0.0


# ===========================================================================
sec("1. KONDISI SEKARANG")
# ===========================================================================
bnkb = Journal.search([("code", "=", TARGET_CODE)], limit=1)
bsi = Acc.search([("code", "=", BSI_CODE)], limit=1)
if not bnkb:
    abort("journal %s tidak ditemukan" % TARGET_CODE)
if not bsi:
    abort("akun %s tidak ditemukan" % BSI_CODE)
if not bsi.active:
    abort("akun tujuan %s nonaktif — perbaiki dulu" % BSI_CODE)

cur = bnkb.default_account_id
print("journal      : [%d] code=%s name=%s type=%s active=%s" % (
    bnkb.id, bnkb.code, bnkb.name, bnkb.type, bnkb.active))
print("default acc  : %s" % ("[%d] %s (%s) active=%s" % (
    cur.id, cur.name, cur.code, cur.active) if cur else "(none)"))
print("tujuan       : [%d] %s (%s) active=%s" % (bsi.id, bsi.name, bsi.code, bsi.active))

if cur and cur.id == bsi.id:
    print("\nSUDAH BERES — default account BNKB memang sudah BSI. Tidak ada yang perlu dilakukan.")
    env.cr.rollback()
    sys.exit(0)
if cur and cur.active:
    print("\nCATATAN: akun default sekarang MASIH AKTIF (%s). Perbaikan ini tetap opsional." % cur.name)

print("\npos.payment.method yang memakai journal ini:")
pms = PM.search([("journal_id", "=", bnkb.id)])
for pm in pms:
    print("   [%d] %-24s active=%s | receivable=%s | config=%s" % (
        pm.id, pm.name, pm.active,
        pm.receivable_account_id.name if pm.receivable_account_id else "-",
        pm.config_ids.mapped("name")))

print("\nmove historis BNKB: %d" % env["account.move"].search_count([("journal_id", "=", bnkb.id)]))
# gotcha Odoo 19: `account_account.code` BUKAN kolom -> pakai code_store->>'1'
cr.execute("""SELECT a.code_store->>'1', a.name->>'en_US', a.active,
                     COUNT(*), COALESCE(SUM(l.debit),0), COALESCE(SUM(l.credit),0)
              FROM account_move_line l
              JOIN account_account a ON a.id = l.account_id
              JOIN account_move m ON m.id = l.move_id
              WHERE m.journal_id = %s AND a.account_type = 'asset_cash'
              GROUP BY a.code_store->>'1', a.name, a.active""", (bnkb.id,))
for code, name, active, cnt, d, c in cr.fetchall():
    print("   akun kas pada move BNKB: %-10s %-26s active=%-5s %d line D %s K %s" % (
        code, name[:26], active, cnt, rp(d), rp(c)))

sec("2. AUDIT: journal AKTIF lain yang default account-nya NONAKTIF")
risky = []
for j in Journal.search([("active", "=", True)]):
    d = j.default_account_id
    if d and not d.active:
        line = "   %-8s %-26s type=%-7s -> %s %s (NONAKTIF)" % (j.code, j.name[:26], j.type, d.code, d.name)
        print(line)
        risky.append(j)
if not risky:
    print("   (tidak ada — hanya BNKB)")

# ===========================================================================
sec("3. SNAPSHOT (tidak boleh berubah)")
# ===========================================================================
cash_ids = Acc.search([("account_type", "=", "asset_cash")]).ids
snap = {
    "kas_bank_total": sum(bal(i) for i in cash_ids),
    "bnkb_move_count": env["account.move"].search_count([("journal_id", "=", bnkb.id)]),
    "tb_diff": (lambda r: (r[0][0] or 0.0) - (r[0][1] or 0.0))(
        Aml._read_group([("parent_state", "=", "posted")], [], ["debit:sum", "credit:sum"])),
}
for k, v in snap.items():
    print("   %-18s %s" % (k, rp(v) if "count" not in k else v))

# ===========================================================================
sec("4. RENCANA")
# ===========================================================================
print("   set %s.default_account_id = %s (%s)" % (bnkb.code, bsi.code, bsi.name))
if cur:
    print("   (dari %s %s — tetap nonaktif, tidak dihapus)" % (cur.code, cur.name))

if not RUN:
    print("\nDRY-RUN — tidak ada perubahan. Jalankan RUN=1 untuk eksekusi.")
    env.cr.rollback()
    sys.exit(0)

# ===========================================================================
sec("5. EKSEKUSI (ORM)")
# ===========================================================================
cr.execute("SAVEPOINT p4")
bnkb.write({"default_account_id": bsi.id})
env.flush_all()
print("   default_account_id BNKB -> %s (%s)" % (bnkb.default_account_id.code, bnkb.default_account_id.name))

# ===========================================================================
sec("6. VERIFIKASI")
# ===========================================================================
ok = True
d = bnkb.default_account_id
print("   BNKB.default = %s %s active=%s" % (d.code, d.name, d.active))
if d.id != bsi.id or not d.active:
    ok = False

after = {
    "kas_bank_total": sum(bal(i) for i in cash_ids),
    "bnkb_move_count": env["account.move"].search_count([("journal_id", "=", bnkb.id)]),
    "tb_diff": (lambda r: (r[0][0] or 0.0) - (r[0][1] or 0.0))(
        Aml._read_group([("parent_state", "=", "posted")], [], ["debit:sum", "credit:sum"])),
}
for k in snap:
    same = abs(after[k] - snap[k]) < 0.005 if "count" not in k else after[k] == snap[k]
    print("   %-18s sebelum %18s | sesudah %18s %s" % (
        k, rp(snap[k]) if "count" not in k else snap[k],
        rp(after[k]) if "count" not in k else after[k], "" if same else "<<< BERUBAH!"))
    if not same:
        ok = False

print("\n   RISK CHECK ulang — journal aktif dgn default account nonaktif:")
still = []
for j in Journal.search([("active", "=", True)]):
    dd = j.default_account_id
    if dd and not dd.active:
        still.append("%s -> %s" % (j.code, dd.code))
        ok = False
print("      %s" % (still or "(bersih)"))

print("\n   PM yang terpengaruh:")
for pm in pms:
    print("      [%d] %-22s journal=%s -> akun %s (active=%s)" % (
        pm.id, pm.name, pm.journal_id.code, pm.journal_id.default_account_id.code,
        pm.journal_id.default_account_id.active))

print("\n   semua journal bank/kas & akun defaultnya:")
for j in Journal.search([("type", "in", ["bank", "cash"])], order="code"):
    if j.active:
        dd = j.default_account_id
        print("      %-7s %-24s -> %s %s active=%s" % (
            j.code, j.name[:24], dd.code if dd else "-", (dd.name or "-")[:24] if dd else "-",
            dd.active if dd else "-"))

if not ok:
    cr.execute("ROLLBACK TO SAVEPOINT p4")
    print("\nROLLBACK — tidak ada perubahan tersimpan.")
    sys.exit(1)

env.cr.commit()
print("\nCOMMITTED ✓ — BNKB kini memakai akun BSI (1101.01).")
