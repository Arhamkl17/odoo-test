# -*- coding: utf-8 -*-
"""
juni_juli_91_reset_pos_channels.py — hapus data POS Jun–Agu supaya bisa di-regenerate
dengan campuran 60% Dine In / 40% take-away.

SCOPE YANG DIHAPUS
  1. `Settlement %` bertanggal Jun–Agu  (pass 1 & 2 generator akan membuatnya ulang)
  2. JE buatan generator : ref 'Setoran kas %' dan 'Penarikan kas untuk modal laci'
  3. JE setoran QRIS     : ref 'Setoran QRIS % ke Bank BSI'  (skrip 34 dijalankan ulang)
  4. per sesi            : order + payment, statement line, account.payment,
                           JE sesi, lalu sesinya sendiri

YANG **TIDAK** DISENTUH
  * `stock.move` origin `HPP-BOM%` — lapisan HPP terpisah; dibangun ulang oleh skrip 21
  * invoice B2B / catering (INV/2026/00001, 00002, 00004) beserta pembayarannya
  * 'Modal kerja awal', beban operasional (skrip 25), pembelian bahan

⚠️ AGUSTUS TIDAK IKUT SECARA DEFAULT (`ONLY=june,july`). Alasannya tiga
  (lihat `91b_probe_pickings.py`):

  1. **4.515 `stock.picking` + 82.881 `stock_move_line` menempel pada sesi Agustus**
     (Juni & Juli: NOL picking). Menghapus sesi Agustus wajib ikut menghapus picking,
     move, dan move line-nya — kalau tidak, stok & HPP Agustus jadi yatim.
     Kabar baiknya: picking itu **tidak** menghasilkan jurnal (0 `account_move`),
     jadi tidak ada dampak akuntansi langsung.
  2. **Agustus satu-satunya bulan berisi data klien asli.** Jalur reset ini sudah
     TERBUKTI aman untuk Juni–Juli (`juni_juli_11_*`), belum pernah diuji untuk Agustus.
  3. Regenerate Agustus berarti juga membuang picking-nya yang belum punya pengganti
     di generator (generator POS tidak membuat picking).

  → Untuk Agustus, regenerate lewat jalur ini **belum layak dieksekusi**. Perlu desain
    terpisah (hapus picking dulu, atau reprice tanpa regenerate).

ALASAN 91 ADA: skrip 11 lama hanya mencakup Juni–Juli dan tidak menyentuh JE settlement,
setoran QRIS, maupun Agustus.

  dry-run : su odoo ... < scripts/juni_juli_91_reset_pos_channels.py
  eksekusi: su odoo ... " RUN=1 odoo shell ..." < scripts/juni_juli_91_reset_pos_channels.py

Env:
  RUN=1                 eksekusi (default dry-run)
  ONLY=june,july        batasi bulan (DEFAULT — Agustus sengaja tidak ikut)
  ONLY=june,july,august untuk menyertakan Agustus (perlu keputusan sadar)
"""
import os

from odoo import fields

RUN = os.environ.get("RUN") == "1"
PERIODS = {
    "june":    ("2026-06-01", "2026-07-01"),
    "july":    ("2026-07-01", "2026-08-01"),
    "august":  ("2026-08-01", "2026-09-01"),
}
MONTHS = [m.strip() for m in os.environ.get("ONLY", "june,july").split(",") if m.strip()]
RANGES = [PERIODS[m] for m in MONTHS if m in PERIODS]
FROM = min(a for a, _ in RANGES)
TO = max(b for _, b in RANGES)

cr = env.cr
AM = env["account.move"]
Sess = env["pos.session"]
Pay = env["account.payment"]
POSo = env["pos.order"]
SL = env["account.bank.statement.line"]
say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))


def in_range(ref_like):
    return AM.search([("ref", "like", ref_like), ("date", ">=", FROM), ("date", "<", TO)])


say("=" * 108)
say("RESET DATA POS %s   |   RUN=%s" % (" + ".join(MONTHS).upper(), RUN))
say("rentang: %s s/d %s" % (FROM, TO))
say("=" * 108)

# ------------------------------------------------------------------ inventaris
sess = Sess.search([("start_at", ">=", FROM), ("start_at", "<", TO)], order="start_at")
orders = POSo.search([("date_order", ">=", FROM), ("date_order", "<", TO)])
pays = Pay.search([("pos_session_id", "in", sess.ids)]) if sess else Pay.browse()
sls = SL.search([("pos_session_id", "in", sess.ids)]) if sess else SL.browse()
settle = in_range("Settlement %")
setor_kas = in_range("Setoran kas %")
float_je = in_range("Penarikan kas untuk modal laci")
qris = in_range("Setoran QRIS %")

open_sess = sess.filtered(lambda s: s.state != "closed")
b2b = AM.search([("move_type", "=", "out_invoice"), ("date", ">=", FROM), ("date", "<", TO)])

say("")
say("A. YANG AKAN DIHAPUS")
say("   sesi POS                      : %d  (belum closed: %d)" % (len(sess), len(open_sess)))
say("   order POS                     : %d  omzet %s" % (len(orders), money(sum(orders.mapped("amount_total")))))
say("   account.payment (POS)         : %d" % len(pays))
say("   statement line (POS)          : %d" % len(sls))
say("   JE 'Settlement %%'            : %d" % len(settle))
say("   JE 'Setoran kas %%'           : %d" % len(setor_kas))
say("   JE float laci                 : %d" % len(float_je))
say("   JE 'Setoran QRIS %%'          : %d" % len(qris))

per_month = {}
for bln, (a, b) in PERIODS.items():
    if bln not in MONTHS:
        continue
    per_month[bln] = (
        Sess.search_count([("start_at", ">=", a), ("start_at", "<", b)]),
        POSo.search_count([("date_order", ">=", a), ("date_order", "<", b)]),
        sum(POSo.search([("date_order", ">=", a), ("date_order", "<", b)]).mapped("amount_total")),
    )
say("")
say("   rincian per bulan:")
for bln, (ns, no, rev) in per_month.items():
    say("      %-8s sesi=%-4d order=%-5d omzet=%16s" % (bln, ns, no, money(rev)))

say("")
say("B. YANG **TIDAK** DISENTUH")
say("   invoice B2B : %d" % len(b2b))
for m in b2b:
    say("      %-18s %-12s %-26s %12s state=%s" % (
        m.name, str(m.invoice_date), (m.partner_id.name or "")[:26], money(m.amount_total), m.state))
cr.execute("SELECT count(*) FROM stock_move WHERE origin LIKE 'HPP-BOM%%'")
say("   stock.move HPP-BOM : %s (dibangun ulang skrip 21)" % cr.fetchone()[0])
cr.execute("SELECT count(*) FROM stock_picking WHERE pos_session_id IS NOT NULL")
say("   stock.picking dari POS : %s" % cr.fetchone()[0])
say("   'Modal kerja awal' : %d JE" % len(AM.search([("ref", "like", "Modal kerja%"),
                                                      ("date", ">=", FROM), ("date", "<", TO)])))

say("")
say("C. JE 'Settlement %%' yang akan dihapus (maks 20 contoh)")
for m in settle[:20]:
    say("      %-14s %-10s %-56s %14s" % (
        m.name, str(m.date), (m.ref or "")[:56], money(m.amount_total)))
if len(settle) > 20:
    say("      ... dan %d lainnya" % (len(settle) - 20))

if open_sess:
    say("")
    say("!!! ADA %d SESI BELUM CLOSED -> reset dibatalkan: %s" % (
        len(open_sess), open_sess.mapped("name")))
    env.cr.rollback()
    raise SystemExit(1)

# --- guard Agustus ------------------------------------------------------------
if "august" in MONTHS:
    cr.execute("""SELECT count(*), count(DISTINCT sm.id), count(DISTINCT sml.id)
                    FROM stock_picking p
                    JOIN pos_session s ON s.id = p.pos_session_id
                    LEFT JOIN stock_move sm ON sm.picking_id = p.id
                    LEFT JOIN stock_move_line sml ON sml.move_id = sm.id
                   WHERE s.start_at >= '2026-08-01' AND s.start_at < '2026-09-01'""")
    np_, nm_, nl_ = cr.fetchone()
    say("")
    say("⚠️  AGUSTUS DISERTAKAN — resiko tinggi")
    say("    picking yang ikut menggantung : %d" % np_)
    say("    stock.move                    : %d" % nm_)
    say("    stock.move.line               : %d" % nl_)
    say("    Generator POS TIDAK membuat picking, jadi setelah reset tidak ada pengganti.")
    say("    Agustus juga satu-satunya bulan berisi data klien asli.")
    if os.environ.get("KONFIRMASI_AGUSTUS") != "YA":
        say("")
        say("    DIBATALKAN. Set KONFIRMASI_AGUSTUS=YA kalau memang mau lanjut.")
        env.cr.rollback()
        raise SystemExit(1)

if not RUN:
    say("")
    say("DRY-RUN — tidak ada data dihapus. Jalankan dengan RUN=1 untuk eksekusi.")
    env.cr.rollback()
    raise SystemExit(0)

# ------------------------------------------------------------------ 1. JE non-sesi
say("")
say("EKSEKUSI")
for label, moves in (("Settlement", settle), ("Setoran kas", setor_kas),
                     ("Float laci", float_je), ("Setoran QRIS", qris)):
    n = 0
    for m in moves:
        try:
            m.line_ids.remove_move_reconcile()
            m.button_draft()
            m.unlink()
            n += 1
        except Exception as e:
            say("   !! %s %s -> %s" % (label, m.name, repr(e)[:100]))
    say("   hapus %-14s %d JE" % (label, n))
    env.cr.commit()

# ------------------------------------------------------------------ 2. per sesi
done = err = 0
for s in sess:
    cr.execute("SAVEPOINT sp_reset")
    try:
        so = POSo.search([("session_id", "=", s.id)])
        for o in so:
            cr.execute("UPDATE pos_order SET state='cancel' WHERE id=%s", (o.id,))
            o.invalidate_recordset(["state"])
            o.payment_ids.unlink()
            o.unlink()
        sl = SL.search([("pos_session_id", "=", s.id)])
        if sl:
            sm = sl.move_id
            sm.line_ids.remove_move_reconcile()
            sm.button_draft()
            sl.unlink()
        p = Pay.search([("pos_session_id", "=", s.id)])
        if p:
            pmv = p.mapped("move_id")
            pmv.line_ids.remove_move_reconcile()
            pmv.button_draft()
            ids = tuple(p.ids)
            cr.execute("UPDATE account_payment SET move_id=NULL, state='draft' WHERE id IN %s", (ids,))
            p.invalidate_recordset()
            pmv.filtered(lambda m: m.state == "draft").unlink()
            cr.execute("DELETE FROM account_payment WHERE id IN %s", (ids,))
        mv = s.move_id
        if mv:
            mv.line_ids.remove_move_reconcile()
            mv.button_draft()
            mv.unlink()
        s.write({"state": "closed", "move_id": False})
        s.unlink()
        cr.execute("RELEASE SAVEPOINT sp_reset")
        done += 1
    except Exception as e:
        cr.execute("ROLLBACK TO SAVEPOINT sp_reset")
        err += 1
        say("   !! %s %s -> %s" % (s.start_at, s.config_id.name, repr(e)[:120]))
env.cr.commit()
say("   sesi dihapus=%d gagal=%d" % (done, err))

# ------------------------------------------------------------------ 3. verifikasi
say("")
say("VERIFIKASI PASCA-RESET")
say("   sisa sesi POS          : %d" % Sess.search_count([("start_at", ">=", FROM), ("start_at", "<", TO)]))
say("   sisa order POS         : %d" % POSo.search_count([("date_order", ">=", FROM), ("date_order", "<", TO)]))
say("   sisa JE 'Settlement %%' : %d" % len(in_range("Settlement %")))
say("   sisa JE 'Setoran kas %%': %d" % len(in_range("Setoran kas %")))
say("   invoice B2B masih ada  : %d" % AM.search_count([("move_type", "=", "out_invoice"),
                                                          ("date", ">=", FROM), ("date", "<", TO)]))
cr.execute("SELECT count(*) FROM stock_move WHERE origin LIKE 'HPP-BOM%%'")
say("   stock.move HPP-BOM     : %s (tidak disentuh)" % cr.fetchone()[0])
for bln, (a, b) in PERIODS.items():
    if bln not in MONTHS:
        continue
    cr.execute("""SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0)
                    FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                   WHERE am.state='posted' AND am.date >= %s AND am.date < %s""", (a, b))
    d, k = cr.fetchone()
    say("   TB %-8s debit=%16s credit=%16s diff=%s" % (bln, money(d), money(k), money(float(d or 0) - float(k or 0))))
say("")
say("LANGKAH LANJUTAN: jalankan 92 (regenerate) -> 21 (HPP) -> 34 (QRIS & pembelian tunai).")
say("=" * 108)
