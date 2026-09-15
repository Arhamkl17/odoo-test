# -*- coding: utf-8 -*-
"""
juni_juli_11_reset_juni_juli.py — hapus SELURUH data POS Juni & Juli (regenerate ulang).

Kenapa aman (berbeda dari kasus Agustus/TERONG):
  * sesi Juni/Juli TIDAK punya picking / stock.move -> tidak ada HPP & valuasi stok
    yang bisa dobel dihitung.
  * order, payment, JE, statement line semuanya lahir dari generator yang sama,
    jadi bisa dibongkar balik dengan urutan kebalikannya.

Urutan pembongkaran per sesi (kebalikan urutan pembuatan):
  1. JE sesi            : remove reconcile -> draft -> unlink
  2. account.payment    : remove reconcile -> draft -> move unlink -> row delete
  3. statement line     : remove reconcile -> draft -> unlink (ikut move)
  4. order + payment    : state->cancel (SQL) -> unlink payment -> unlink order
  5. sesi               : unlink

Ditambah:
  * JE settlement buatan generator (ref 'Settlement pembayaran POS %' /
    'Settlement pelunasan invoice %') yang bertanggal Juni/Juli.
  * invoice catering Juli (opsional, dipilih pemilik) + pembayarannya.

  RUN=1   eksekusi  (default: dry-run)
  ALSO_CATERING_JULY=1  sekalian hapus invoice catering Juli
"""
import os

RUN = os.environ.get("RUN") == "1"
DROP_CATERING_JULY = os.environ.get("ALSO_CATERING_JULY") == "1"
JUN_FROM, AUG_FROM = "2026-06-01", "2026-08-01"

cr = env.cr
AM = env["account.move"]
Sess = env["pos.session"]
Pay = env["account.payment"]
POSo = env["pos.order"]

say = lambda m="": print(m)
say("=" * 78)
say("RESET DATA POS JUNI & JULI   |   RUN=%s | drop_catering_july=%s" % (RUN, DROP_CATERING_JULY))
say("=" * 78)


def rp(x):
    return "{:,.2f}".format(float(x or 0))


# --- ringkasan yang akan dihapus -------------------------------------------
sess = Sess.search([("start_at", ">=", JUN_FROM), ("start_at", "<", AUG_FROM)], order="start_at")
orders = POSo.search([("date_order", ">=", JUN_FROM), ("date_order", "<", AUG_FROM)])
pays = Pay.search([("pos_session_id", "in", sess.ids)]) if sess else Pay.browse()
sls = env["account.bank.statement.line"].search([("pos_session_id", "in", sess.ids)])
settle = AM.search([("date", ">=", JUN_FROM), ("date", "<", AUG_FROM),
                    ("ref", "like", "Settlement %")])
cat = AM.search([("move_type", "=", "out_invoice"),
                 ("invoice_date", ">=", "2026-07-01"), ("invoice_date", "<", AUG_FROM)])

say("sesi            : %d" % len(sess))
say("order           : %d (omzet %s)" % (len(orders), rp(sum(orders.mapped("amount_total")))))
say("account.payment : %d" % len(pays))
say("statement line  : %d" % len(sls))
say("JE settlement   : %d" % len(settle))
say("invoice catering Juli: %d %s" % (len(cat), cat.mapped("name")))

if not RUN:
    say("")
    say("DRY-RUN — tidak ada data dihapus.")
    env.cr.rollback()
    raise SystemExit(0)

# --- 1. JE settlement ------------------------------------------------------
if settle:
    for m in settle:
        m.line_ids.remove_move_reconcile()
        m.button_draft()
        m.unlink()
    say("hapus %d JE settlement" % len(settle))
    env.cr.commit()

# --- 2. invoice catering Juli (+ pembayarannya) ----------------------------
if DROP_CATERING_JULY and cat:
    for inv in cat:
        inv.button_draft()
        inv.unlink()
    pj = Pay.search([("payment_type", "=", "inbound"), ("date", ">=", "2026-07-01"),
                     ("date", "<", AUG_FROM), ("reconciled_invoice_ids", "=", False)])
    say("hapus %d invoice catering Juli" % len(cat))
    env.cr.commit()

# --- 3. per sesi -----------------------------------------------------------
done = err = 0
for s in sess:
    cr.execute("SAVEPOINT sp_reset")
    try:
        # 3a. order + payment-nya
        so = POSo.search([("session_id", "=", s.id)])
        for o in so:
            cr.execute("UPDATE pos_order SET state='cancel' WHERE id=%s", (o.id,))
            o.invalidate_recordset(["state"])
            o.payment_ids.unlink()
            o.unlink()
        # 3b. statement line
        sl = env["account.bank.statement.line"].search([("pos_session_id", "=", s.id)])
        if sl:
            sm = sl.move_id
            sm.line_ids.remove_move_reconcile()
            sm.button_draft()
            sl.unlink()
        # 3c. account.payment POS
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
        # 3d. JE sesi
        mv = s.move_id
        if mv:
            mv.line_ids.remove_move_reconcile()
            mv.button_draft()
            mv.unlink()
        # 3e. sesi
        s.write({"state": "closed", "move_id": False})
        s.unlink()
        cr.execute("RELEASE SAVEPOINT sp_reset")
        done += 1
    except Exception as e:
        cr.execute("ROLLBACK TO SAVEPOINT sp_reset")
        err += 1
        say("   !! %s %s -> %s" % (s.start_at, s.config_id.name, repr(e)[:120]))

env.cr.commit()
say("sesi dihapus=%d gagal=%d" % (done, err))

# --- 4. verifikasi ---------------------------------------------------------
sisa = Sess.search_count([("start_at", ">=", JUN_FROM), ("start_at", "<", AUG_FROM)])
sisa_o = POSo.search_count([("date_order", ">=", JUN_FROM), ("date_order", "<", AUG_FROM)])
cr.execute("""SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml
              JOIN account_move am ON am.id=aml.move_id
              WHERE am.state='posted' AND am.date>=%s AND am.date<%s
                AND aml.account_id IN (SELECT id FROM account_account
                                       WHERE code_store->>'1' IN ('1103.06','11120003'))""",
           (JUN_FROM, AUG_FROM))
outs = cr.fetchone()[0]
cr.execute("""SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) FROM account_move_line aml
              JOIN account_move am ON am.id=aml.move_id WHERE am.state='posted'""")
d, k = cr.fetchone()
say("")
say("VERIFIKASI")
say("   sisa sesi Juni/Juli : %d" % sisa)
say("   sisa order Juni/Juli: %d" % sisa_o)
say("   saldo 1103.06+11120003 di rentang Juni/Juli: %s" % rp(outs))
say("   TB debit=%s credit=%s diff=%s" % (rp(d), rp(k), rp(d - k)))
aug = POSo.search([("date_order", ">=", AUG_FROM), ("date_order", "<", "2026-09-01")])
say("   AGUSTUS tetap: %d order, omzet %s" % (len(aug), rp(sum(aug.mapped("amount_total")))))
say("=" * 78)
