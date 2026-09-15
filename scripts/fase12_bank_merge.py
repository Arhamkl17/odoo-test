# -*- coding: utf-8 -*-
"""FASE 12 — Merge akun bank ke BNI & BSI (rewrite history, keputusan user 12 Sep 2026).

Keputusan user (portofolio/testing, bebas ubah DB):
- Hapus (deactivate) semua akun "Bank X" KECUALI Bank BNI & Bank BSI.
- QRIS + Kas Operasional + Kas Mallengkeri TIDAK disentuh.
- Pemetaan transaksi:
    * Bank Mallengkeri  -> SEMUA line   -> BSI
    * Bank BCA/BRI/Mandiri: line DEBIT (setoran) -> BNI
                            line KREDIT (sweep MISC/0054) -> BSI
- Target akhir: BNI 23.022.406,00 | BSI 157.302.634,81 (total konservasi
  180.325.040,81 = total bank kumulatif s.d. hari ini).
- Metode: UPDATE SQL (jurnal MISC hash-secured — ORM memblokir write move
  posted; hash chain MISC akan flagged inconsistent di integrity check,
  didokumentasikan di PROGRESS_DASHBOARD.md).

Konvensi repo: dry-run default; eksekusi nyata = env RUN=1.
WAJIB sebelum RUN=1: pg_dump backup penuh (lihat perintah di PROGRESS).
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
        return 0.0, 0.0, 0.0          # akun tanpa move line sama sekali
    deb, cred = res[0][1] or 0.0, res[0][2] or 0.0
    return deb, cred, deb - cred


def find(name):
    recs = Account.search([("name", "=ilike", name), ("account_type", "=", "asset_cash")])
    if len(recs) != 1:
        abort("akun '%s' tidak unik: %s" % (name, recs.mapped("name")))
    return recs


bni, bsi = find("Bank BNI"), find("Bank BSI")
mall, bca, bri, mandiri = find("Bank Mallengkeri"), find("Bank BCA"), find("Bank BRI"), find("Bank Mandiri")
SOURCE = [mall, bca, bri, mandiri]
TARGETS = [bni, bsi]

# ---------- 1. Snapshot & guard ekspektasi (kumulatif s.d. hari ini) ----------
snap = {a.id: bal(a) for a in SOURCE + TARGETS}
total_before = sum(v[2] for v in snap.values())

print("=== SNAPSHOT (posted, kumulatif) ===")
for a in SOURCE + TARGETS:
    d, c, b = snap[a.id]
    print("  %-24s D %14.2f K %14.2f = %14.2f" % (a.name, d, c, b))
print("  TOTAL bank        : %.2f" % total_before)

EXPECT = {
    "Bank BNI": 0.00,
    "Bank BSI": 162462802.81,
    "Bank Mallengkeri": 17862238.00,
    "Bank BCA": 0.00,
    "Bank BRI": 0.00,
    "Bank Mandiri": 0.00,
}
acc_by_name = {"Bank BNI": bni, "Bank BSI": bsi, "Bank Mallengkeri": mall,
               "Bank BCA": bca, "Bank BRI": bri, "Bank Mandiri": mandiri}
for name, exp in EXPECT.items():
    b = snap[acc_by_name[name].id][2]
    if abs(b - exp) > 0.05:
        abort("guard ekspektasi %s: %.2f != %.2f — DB berubah sejak audit 12 Sep?" % (name, b, exp))

# ---------- 2. Plan ----------
plan = []
for a in SOURCE:
    lines = Aml.search([("account_id", "=", a.id), ("parent_state", "=", "posted")], order="date, id")
    for l in lines:
        is_debit = (l.debit or 0.0) > 0 and not (l.credit or 0.0)
        is_credit = (l.credit or 0.0) > 0 and not (l.debit or 0.0)
        if a.id == mall.id:
            tgt = bsi                      # semua mutasi Mallengkeri -> BSI
        elif is_debit:
            tgt = bni                      # setoran -> BNI
        elif is_credit:
            tgt = bsi                      # sweep MISC/0054 -> BSI
        else:
            abort("line %s id=%s debit & kredit sekaligus — investigasi manual" % (l.move_id.name, l.id))
        plan.append((l.id, a.name, tgt, l.date, l.debit or 0.0, l.credit or 0.0, l.move_id.name))

n_bni = sum(1 for p in plan if p[2].id == bni.id)
n_bsi = len(plan) - n_bni
print("\n=== PLAN: %d lines dipindah (BNI %d, BSI %d) ===" % (len(plan), n_bni, n_bsi))

sim = {a.id: snap[a.id][2] for a in SOURCE + TARGETS}
for _, src, tgt, _, d, c, _ in plan:
    sim[[x.id for x in SOURCE if x.name == src][0]] -= d - c
    sim[tgt.id] += d - c
print("  Simulasi akhir : BNI %.2f | BSI %.2f" % (sim[bni.id], sim[bsi.id]))
if abs(sim[bni.id] - 23022406.00) > 0.05 or abs(sim[bsi.id] - 157302634.81) > 0.05:
    abort("simulasi target tidak sesuai rencana (BNI 23.022.406 / BSI 157.302.634,81)")
if abs(sum(sim.values()) - total_before) > 0.005:
    abort("konservasi gagal di simulasi")
print("  Konservasi     : OK (total tetap %.2f)" % total_before)

if not RUN:
    print("\nDRY-RUN — tidak ada perubahan. Jalankan ulang dengan RUN=1 utk eksekusi.")
    sys.exit(0)

# ---------- 3. Eksekusi (SQL; ORM memblokir write move posted) ----------
print("\n=== EKSEKUSI (SQL) ===")
cr.execute("SAVEPOINT fase12")
for lid, src, tgt, *_ in plan:
    cr.execute("UPDATE account_move_line SET account_id = %s WHERE id = %s", (tgt.id, lid))
print("  %d line account_move_line di-update" % len(plan))
for a in SOURCE:
    cr.execute("UPDATE account_account SET active = FALSE WHERE id = %s", (a.id,))
print("  4 akun sumber dinonaktifkan (Bank Mallengkeri, BCA, BRI, Mandiri)")

# ---------- 4. Verifikasi ----------
after = {a.id: bal(a) for a in TARGETS}
total_after = sum(after[t][2] for t in after)
print("\n=== VERIFIKASI ===")
for a in TARGETS:
    d, c, b = after[a.id]
    print("  %-24s D %14.2f K %14.2f = %14.2f" % (a.name, d, c, b))
for a in SOURCE:
    print("  %-24s (inactive) saldo %14.2f" % (a.name, bal(a)[2]))
print("  TOTAL bank        : %.2f (before %.2f)" % (total_after, total_before))
ok = True
if abs(total_after - total_before) > 0.005:
    print("  !!! konservasi GAGAL")
    ok = False
minus = [a.name for a in TARGETS if after[a.id][2] < -0.005]
if minus:
    print("  !!! target minus: %s" % minus)
    ok = False
# posisi per akhir bulan (yang dilihat kartu dashboard) tidak boleh minus
tgt_ids = [a.id for a in TARGETS]
for ym, d_last in (("2026-07", "2026-07-31"), ("2026-08", "2026-08-31"), ("2026-09", "2026-09-30")):
    rows = Aml._read_group(
        [("account_id", "in", tgt_ids), ("parent_state", "=", "posted"), ("date", "<=", d_last)],
        ["account_id"], ["debit:sum", "credit:sum"])
    pos = {acc.name: (deb or 0.0) - (cred or 0.0) for acc, deb, cred in rows}
    neg = [k for k, v in pos.items() if v < -0.005]
    print("  posisi %s: %s%s" % (d_last, pos, "  <<< MINUS!" if neg else ""))
    if neg:
        ok = False
if not ok:
    cr.execute("ROLLBACK TO SAVEPOINT fase12")
    print("\nROLLBACK — tidak ada perubahan tersimpan.")
    sys.exit(1)

env.cr.commit()
print("\nCOMMITTED ✓ — catat: hash chain jurnal MISC kini flagged inconsistent (rewrite history, disetujui user).")
print("Sisa: restart server PID 1 (pending utk perubahan Python F-UI.4) + hard-reload browser.")
