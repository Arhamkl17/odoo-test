# -*- coding: utf-8 -*-
"""
juni_juli_34_pembelian_tunai.py — P8: pembelian bahan jadi TUNAI, utang tanpa vendor hilang.

MASALAH
  P7 membuat 141 JE pembelian (`HPP-BOM beli ...`) yang mengkredit 2101.01 Utang Usaha
  tanpa vendor/nomor/jatuh tempo -> Rp 347.479.045,46 utang fiktif di neraca.
  Odoo menolak cancel stock.move berstatus Done, jadi stok tidak disentuh sama sekali;
  yang diubah hanya sisi akuntansi (kredit).

TAPI pembelian tunai butuh kas. Dua temuan yang harus diberesi lebih dulu:

  A. 1 Juni modal Rp 1.330.000.000 habis PERSIS untuk aset tetap (MISC/2026/06/0002),
     sehingga Bank BSI = Rp 0 padahal pembelian bahan Rp 52.381.235,50 juga di 1 Juni.
     -> tambah MODAL KERJA AWAL Rp 60.000.000 (cushion Rp 7,6 jt setelah belanja).

  B. Rp 258.085.726 tertahan di akun 1101.02 QRIS (kredit hanya Rp 4,1 jt sepanjang
     3 bulan). QRIS di dunia nyata disetor ke rekening bank dalam 1-2 hari.
     -> setoran QRIS -> Bank BSI akhir tiap bulan (reklas kas, TIDAK menyentuh laba).

FASE
  0. Resync sequence MISC  : date-range Jun/Jul belum ada -> numpang 0001 (collision)
  1. Modal kerja awal      : Dr 1101.01 / Cr 3101.02   Rp  60.000.000 (1 Jun)
  2. Setoran QRIS          : Dr 1101.01 / Cr 1101.02   per bulan
  3. Reklas 141 JE beli    : kredit 2101.01 -> 1101.01

  RUN=1  eksekusi (default dry-run)
"""
import os

RUN = os.environ.get("RUN") == "1"
ORIG = "HPP-BOM beli"
MODAL_KERJA = 60000000.00
cr = env.cr
AM = env["account.move"]
say = lambda m="": print(m)


def aid(code):
    cr.execute("SELECT id FROM account_account WHERE code_store->>'1'=%s LIMIT 1", (code,))
    r = cr.fetchone()
    return r[0] if r else None


def jid_of(move_name):
    cr.execute("SELECT journal_id FROM account_move WHERE name=%s", (move_name,))
    r = cr.fetchone()
    return r[0] if r else None


def je_exists(ref):
    cr.execute("SELECT id FROM account_move WHERE ref=%s AND state='posted' LIMIT 1", (ref,))
    return cr.fetchone() is not None


BANK = aid("1101.01")
QRIS = aid("1101.02")
MODAL = aid("3101.02")
AP = aid("2101.01")
MISC_J = jid_of("MISC/2026/06/0002")
J = env["account.journal"].browse(MISC_J)
say("=" * 100)
say("P8 PEMBELIAN TUNAI  |  RUN=%s" % RUN)
say("   bank=1101.01 id=%s | qris=1101.02 id=%s | modal=3101.02 id=%s | AP=2101.01 id=%s | jurnal MISC id=%s"
    % (BANK, QRIS, MODAL, AP, MISC_J))
say("=" * 100)


def post_entry(date, ref, lines):
    """lines = [(account_id, debit, credit, label)]"""
    vals = [{"account_id": a, "debit": d, "credit": k, "name": lb} for a, d, k, lb in lines]
    m = AM.create({"move_type": "entry", "journal_id": MISC_J, "date": date,
                   "ref": ref, "line_ids": [(0, 0, v) for v in vals]})
    m.action_post()
    return m


# ---------------------------------------------------------------- FASE 0
# Jurnal MISC memakai sequence `no_gap` berbasis date-range per bulan
# (addons/account_move_name_sequence). Date-range Juni & Juli belum pernah dibuat,
# jadi JE bertanggal Juni memakai counter bawaan (1) dan bentrok dengan
# MISC/2026/06/0001. Dibuatkan range dari nomor tertinggi yang sudah terpakai —
# persis nilai yang dihasilkan `journal._prepare_sequence_current_moves()`.
say("")
say("FASE 0 — RESYNC SEQUENCE MISC (dari nomor tertinggi yang sudah terpakai)")
SEQ = J.sequence_id
RANGE = env["ir.sequence.date_range"]

# PERBAIKAN 13 Sep 2026 — backfill prefix & nomor yang kosong.
# Temuan: `Setoran Modal Kerja Awal (stok awal Juni)` punya nama `MISC/2026/06/0003`
# tetapi `sequence_prefix` KOSONG dan `sequence_number` NULL. Akibatnya query
# MAX(sequence_number) mengembalikan 2, number_next disetel 3, lalu posting berikutnya
# menabrak `account_move_unique_name` (duplicate MISC/2026/06/0003).
# Move seperti ini lahir dari jalur penomoran fallback (range belum ada saat dibuat),
# jadi prefix & nomornya diselaraskan dari NAMA-nya sebelum MAX dihitung.
for mth, d_from, d_to in (("2026-06", "2026-06-01", "2026-06-30"),
                          ("2026-07", "2026-07-01", "2026-07-31")):
    pref = "MISC/%s/" % mth.replace("-", "/")
    cr.execute("""UPDATE account_move
                      SET sequence_prefix = %s,
                          sequence_number = NULLIF(split_part(name,'/',4),'')::int
                    WHERE journal_id = %s AND sequence_number IS NULL
                      AND name LIKE %s AND name <> '/'
                      AND split_part(name,'/',4) ~ '^[0-9]+$'""",
               (pref, MISC_J, pref + "%"))
    if cr.rowcount:
        say("   %s backfill prefix/nomor: %d move" % (mth, cr.rowcount))
    env.invalidate_all()

for mth, d_from, d_to in (("2026-06", "2026-06-01", "2026-06-30"),
                          ("2026-07", "2026-07-01", "2026-07-31")):
    cr.execute("""SELECT COALESCE(MAX(sequence_number),0) FROM account_move
                   WHERE journal_id=%s AND sequence_prefix LIKE %s AND name<>'/'""",
               (MISC_J, "MISC/%s/%%" % mth.replace("-", "/")))
    mx = cr.fetchone()[0]
    want = mx + 1
    found = RANGE.search([("sequence_id", "=", SEQ.id), ("date_from", "=", d_from)], limit=1)
    if found:
        if found.number_next != want:
            say("   %s range ada, number_next=%s -> %s" % (mth, found.number_next, want))
            if RUN:
                found.write({"number_next": want})
        else:
            say("   %s range OK (number_next=%s)" % (mth, want))
    elif RUN:
        RANGE.create({"sequence_id": SEQ.id, "date_from": d_from, "date_to": d_to,
                      "number_next": want})
        say("   %s range dibuat, number_next=%s (max terpakai=%s)" % (mth, want, mx))
    else:
        say("   %s [dry] buat range number_next=%s (max terpakai=%s)" % (mth, want, mx))
if RUN:
    env.cr.commit()

# ---------------------------------------------------------------- FASE 1
say("")
say("FASE 1 — MODAL KERJA AWAL (1 Jun) Rp %s" % "{:,.2f}".format(MODAL_KERJA))
REF1 = "Setoran Modal Kerja Awal (stok awal Juni)"
if je_exists(REF1):
    say("   dilewati (sudah ada)")
elif RUN:
    m = post_entry("2026-06-01", REF1, [
        (BANK, MODAL_KERJA, 0.0, "Setoran modal kerja awal"),
        (MODAL, 0.0, MODAL_KERJA, "Modal disetor — modal kerja"),
    ])
    say("   -> dibuat %s" % m.name)
else:
    say("   [dry] akan membuat JE Dr Bank BSI / Cr Modal Disetor Rp %s" % "{:,.2f}".format(MODAL_KERJA))

# ---------------------------------------------------------------- FASE 2
say("")
say("FASE 2 — SETORAN QRIS -> BANK BSI (akhir bulan)")
cr.execute("""
    SELECT to_char(am.date,'YYYY-MM') m, SUM(aml.debit)-SUM(aml.credit) net
      FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE am.state='posted' AND aa.code_store->>'1'='1101.02'
     GROUP BY 1 ORDER BY 1""")
qris_rows = cr.fetchall()
LAST_DAY = {"2026-06": "2026-06-30", "2026-07": "2026-07-31", "2026-08": "2026-08-31"}
for mth, net in qris_rows:
    if net == 0:
        say("   %s saldo QRIS 0 — dilewati" % mth)
        continue
    ref = "Setoran QRIS %s ke Bank BSI" % mth
    if je_exists(ref):
        say("   %s dilewati (sudah ada)" % mth)
    elif RUN:
        m = post_entry(LAST_DAY[mth], ref, [
            (BANK, net, 0.0, "Setoran QRIS %s" % mth),
            (QRIS, 0.0, net, "Setoran QRIS %s" % mth),
        ])
        say("   %s -> %s  Rp %s" % (mth, m.name, "{:,.2f}".format(net)))
    else:
        say("   %s [dry] Dr Bank BSI / Cr QRIS Rp %s" % (mth, "{:,.2f}".format(net)))

# ---------------------------------------------------------------- FASE 3
say("")
say("FASE 3 — REKLAS 141 JE PEMBELIAN: kredit Utang Usaha -> Bank BSI")
cr.execute("""
    SELECT DISTINCT am.id, am.name, am.date, am.state
      FROM stock_move sm JOIN account_move am ON am.id = sm.account_move_id
     WHERE sm.origin LIKE %s ORDER BY am.id""", (ORIG + "%",))
jes = cr.fetchall()
say("   JE ditemukan: %d" % len(jes))
tot = 0.0
n_ok = n_skip = 0
for mid, nm, dt, st in jes:
    m = AM.browse(mid)
    lines = m.line_ids.filtered(lambda l: l.account_id.id == AP)
    if not lines:
        n_skip += 1
        continue
    tot += sum(lines.mapped("credit"))
    if not RUN:
        continue
    try:
        if m.state == "posted":
            m.button_draft()
        for l in lines:
            l.write({"account_id": BANK, "name": "Pembelian bahan tunai via Bank BSI"})
        m.action_post()
        n_ok += 1
    except Exception as e:
        say("   GAGAL %s -> %s" % (nm, repr(e)[:110]))
    if n_ok and n_ok % 40 == 0:
        env.cr.commit()
        say("      ... %d JE diproses" % n_ok)
if RUN:
    env.cr.commit()
say("   total kredit dipindah: %s | berhasil=%d | dilewati=%d"
    % ("{:,.2f}".format(tot), n_ok, n_skip))

# ---------------------------------------------------------------- VERIFIKASI
say("")
say("=" * 100)
say("VERIFIKASI")
for code in ("2101.01", "1101.01", "1101.02", "3101.02"):
    cr.execute("""SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml
                    JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND aa.code_store->>'1'=%s""", (code,))
    say("   %-10s saldo = %18s" % (code, "{:,.2f}".format(cr.fetchone()[0])))
cr.execute("""SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml
                JOIN account_move am ON am.id=aml.move_id
                JOIN account_account aa ON aa.id=aml.account_id
               WHERE am.state='posted' AND aa.account_type='liability_payable'""")
say("   TOTAL hutang usaha           = %s" % "{:,.2f}".format(cr.fetchone()[0]))
cr.execute("""SELECT COALESCE(SUM(aml.debit),0), COALESCE(SUM(aml.credit),0)
                FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
               WHERE am.state='posted'""")
d, k = cr.fetchone()
say("   TB debit=%s credit=%s diff=%s" % ("{:,.2f}".format(d), "{:,.2f}".format(k),
                                          "{:,.2f}".format(d - k)))
say("")
say("   SALDO BANK BSI — titip terendah & akhir per bulan")
cr.execute("""
    SELECT am.date, SUM(aml.balance)
      FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE am.state='posted' AND aa.code_store->>'1'='1101.01'
     GROUP BY 1 ORDER BY 1""")
run = 0.0
mins = {}
ends = {}
for dt, bal in cr.fetchall():
    run += bal
    mk = dt.strftime("%Y-%m")
    mins[mk] = min(mins.get(mk, run), run)
    ends[mk] = run
for mk in sorted(ends):
    flag = "  <-- NEGATIF!" if mins[mk] < 0 else ""
    say("   %s  terendah=%16s  akhir=%16s%s" % (mk, "{:,.0f}".format(mins[mk]),
                                                "{:,.0f}".format(ends[mk]), flag))
say("=" * 100)
