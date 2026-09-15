# -*- coding: utf-8 -*-
"""
P2b — rapikan NAMA 3 JE opening setelah re-date (P2).

P2 memindahkan tanggal 3 JE ke Juni/Juli via ORM, tapi `button_draft()` +
`action_post()` TIDAK meregenerasi `name` (Odoo mempertahankan nama lama).
Akibatnya: JE bernama `MISC/2026/08/0001` bertanggal 1 Juni — benar secara angka,
tapi menyesatkan saat dibaca di Buku Besar / Journal Ledger.

Skrip ini menyeragamkan nama + metadata sequence, sekaligus membersihkan kolom
hash pada 3 move tersebut (hash chain MISC memang sudah di-waiver, §7.3):

  MISC/2026/08/0001 (1 Jun) -> MISC/2026/06/0001  prefix MISC/2026/06/ #1
  MISC/2026/08/0011 (1 Jun) -> MISC/2026/06/0002  prefix MISC/2026/06/ #2
  MISC/2026/08/0003 (1 Jul) -> MISC/2026/07/0001  prefix MISC/2026/07/ #1

Kolom `name`/`sequence_prefix`/`sequence_number` adalah kolom ledger, jadi update
via SQL — sesuai keputusan user "tidak masalah pake SQL" (preseden Fase 12).

Guard: saldo & tanggal TIDAK berubah; hanya nama/prefix/number/hash.
Konvensi: DRY-RUN default, RUN=1 untuk eksekusi.
"""
import os
import sys

RUN = os.environ.get("RUN") == "1"
cr = env.cr
Aml = env["account.move.line"]
Move = env["account.move"]
Acc = env["account.account"].with_context(active_test=False)

SEP = "=" * 78


def sec(t):
    print("\n" + SEP + "\n" + t + "\n" + SEP)


def rp(v):
    return "{:,.2f}".format(v or 0.0)


# nama lama -> (nama baru, prefix baru, nomor baru, tanggal yang diharapkan)
PLAN = {
    "MISC/2026/08/0001": ("MISC/2026/06/0001", "MISC/2026/06/", 1, "2026-06-01"),
    "MISC/2026/08/0011": ("MISC/2026/06/0002", "MISC/2026/06/", 2, "2026-06-01"),
    "MISC/2026/08/0003": ("MISC/2026/07/0001", "MISC/2026/07/", 1, "2026-07-01"),
}

sec("1. CEK KEADAAN SEKARANG")
found = {}
for old in PLAN:
    m = Move.search([("name", "=", old)], limit=1)
    if not m:
        print("   ABORT: %s tidak ditemukan" % old)
        env.cr.rollback()
        sys.exit(1)
    found[old] = m
    exp_date = PLAN[old][3]
    print("   %-20s date=%s prefix=%-12s #%-3s state=%-8s hash=%s | target: %s %s #%s" % (
        m.name, m.date, m.sequence_prefix, m.sequence_number, m.state,
        (m.inalterable_hash or "-")[:10], PLAN[old][0], PLAN[old][1], PLAN[old][2]))
    if str(m.date) != exp_date:
        print("   ABORT: tanggal %s != %s (P2 belum berjalan?)" % (m.date, exp_date))
        env.cr.rollback()
        sys.exit(1)

# cek tabrakan nama baru
for old, (new, *_rest) in PLAN.items():
    clash = Move.search_count([("name", "=", new)])
    print("   nama baru %-20s sudah dipakai? %s" % (new, "YA" if clash else "tidak"))

# snapshot angka (tidak boleh berubah)
mids = [m.id for m in found.values()]
snap_lines = {}
cr.execute("SELECT move_id, COUNT(*), COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) "
           "FROM account_move_line WHERE move_id = ANY(%s) GROUP BY move_id", (mids,))
for row in cr.fetchall():
    snap_lines[row[0]] = row[1:]
print("\n   snapshot baris per move (id: jumlah, debit, kredit):")
for k, v in sorted(snap_lines.items()):
    print("      %s: %s" % (k, v))

if not RUN:
    print("\nDRY-RUN — tidak ada perubahan. Jalankan RUN=1 untuk eksekusi.")
    env.cr.rollback()
    sys.exit(0)

sec("2. EKSEKUSI (SQL: name + sequence_prefix + sequence_number + bersihkan hash)")
cr.execute("SAVEPOINT p2b")
for old, (new, prefix, num, _d) in PLAN.items():
    mv = found[old]
    # catatan: `secured` adalah field computed (bukan kolom) -> tidak ikut di-update
    cr.execute("""
        UPDATE account_move
           SET name = %s, sequence_prefix = %s, sequence_number = %s,
               inalterable_hash = NULL, secure_sequence_number = 0
         WHERE id = %s
    """, (new, prefix, num, mv.id))
    print("   %-20s -> %s (prefix %s #%s) | hash dibersihkan" % (old, new, prefix, num))
env.invalidate_all()

sec("3. VERIFIKASI")
ok = True
print("   state 3 move:")
for old, (new, *_r) in PLAN.items():
    m = Move.search([("name", "=", new)], limit=1)
    if not m:
        print("      !!! %s tidak ditemukan" % new)
        ok = False
        continue
    print("      %-20s date=%s state=%s prefix=%s #%s secured=%s" % (
        m.name, m.date, m.state, m.sequence_prefix, m.sequence_number, m.secured))
    if m.state != "posted" or m.inalterable_hash:
        ok = False

print("\n   baris per move (harus sama dgn snapshot):")
cr.execute("SELECT move_id, COUNT(*), COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) "
           "FROM account_move_line WHERE move_id = ANY(%s) GROUP BY move_id", (mids,))
after = {r[0]: r[1:] for r in cr.fetchall()}
for k in snap_lines:
    same = tuple(after.get(k, ())) == tuple(snap_lines[k])
    print("      %s: %s %s" % (k, after.get(k), "" if same else "<<< BERUBAH!"))
    if not same:
        ok = False

print("\n   tanggal baris move line (harus seragam dgn move):")
cr.execute("""SELECT m.name, l.date, COUNT(*) FROM account_move_line l
              JOIN account_move m ON m.id = l.move_id
              WHERE l.move_id = ANY(%s) GROUP BY m.name, l.date ORDER BY m.name""", (mids,))
for row in cr.fetchall():
    print("      %-20s %s x%s" % row)

print("\n   TB diff total: Rp %s" % rp(
    (lambda r: (r[0][0] or 0.0) - (r[0][1] or 0.0))(
        Aml._read_group([("parent_state", "=", "posted")], [], ["debit:sum", "credit:sum"]))))

print("\n   nama MISC yang tersisa di prefix Agustus (harus tanpa 0001/0003/0011):")
cr.execute("SELECT name FROM account_move WHERE journal_id = 3 AND sequence_prefix = 'MISC/2026/08/' "
           "ORDER BY sequence_number LIMIT 5")
print("      ", [r[0] for r in cr.fetchall()])

if not ok:
    cr.execute("ROLLBACK TO SAVEPOINT p2b")
    print("\nROLLBACK — tidak ada perubahan tersimpan.")
    sys.exit(1)

env.cr.commit()
print("\nCOMMITTED ✓ — nama 3 JE opening kini konsisten dgn tanggalnya.")
