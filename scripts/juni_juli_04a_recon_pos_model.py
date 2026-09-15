# -*- coding: utf-8 -*-
"""
RECON READ-ONLY — model POS & struktur data Agustus, bahan generator Juni/Juli.

Fokus:
  A. Sesi: field, contoh sesi closed, JE POSS yang terbentuk, statement line
  B. Order: contoh lengkap (field + line + payment), pola nama & relasi
  C. Jejak: apakah order Agustus punya stock.picking / stock.move sendiri?
  D. Pajak & harga: subtotal vs subtotal_incl, tax pada line
  E. Cara order/sesi dibuat (create_uid/create_date) -> ORM flow atau backfill?
  F. Distribusi harian & jam (untuk pola generator)
"""
from collections import defaultdict

SEP = "=" * 78
def sec(t): print("\n" + SEP + "\n" + t + "\n" + SEP)
def rp(v): return "{:,.2f}".format(v or 0.0)

POS = env["pos.order"]
POL = env["pos.order.line"]
Pay = env["pos.payment"]
Sess = env["pos.session"]
AUG1, AUG2 = "2026-08-01", "2026-09-01"

# ===========================================================================
sec("A. SESI")
# ===========================================================================
print("field penting pos.session:")
for f in ("name", "state", "start_at", "stop_at", "config_id", "user_id", "move_id",
          "cash_register_balance_start", "cash_register_balance_end_real",
          "update_stock_at_closing", "sequence_number", "opening_notes", "closing_notes"):
    if f in Sess._fields:
        print("   %-32s %-10s readonly=%s" % (f, Sess._fields[f].type, Sess._fields[f].readonly))
    else:
        print("   %-32s (tidak ada)" % f)

s = Sess.search([("start_at", ">=", AUG1), ("start_at", "<", AUG2)], order="start_at", limit=1)
print("\ncontoh sesi: id=%s name=%r state=%s" % (s.id, s.name, s.state))
print("   start=%s stop=%s config=%s user=%s" % (s.start_at, s.stop_at, s.config_id.name, s.user_id.name))
print("   move_id=%s (%s) | cash_start=%s cash_end=%s" % (
    s.move_id.name if s.move_id else "-", s.move_id.date if s.move_id else "-",
    s.cash_register_balance_start, s.cash_register_balance_end_real))
print("   create_uid=%s create_date=%s" % (s.create_uid.name, s.create_date))
print("   jumlah order di sesi ini:", POS.search_count([("session_id", "=", s.id)]))
print("   jumlah payment di sesi ini:", Pay.search_count([("session_id", "=", s.id)]))

if s.move_id:
    print("\n   === JE POSS sesi ini: %s (%s) ===" % (s.move_id.name, s.move_id.date))
    for l in s.move_id.line_ids:
        print("      %-12s %-40s D %16s K %16s" % (
            l.account_id.code, l.account_id.name[:40], rp(l.debit), rp(l.credit)))

ssl = env["account.bank.statement.line"].search([("pos_session_id", "=", s.id)])
print("\n   statement line sesi ini: %d" % len(ssl))
for l in ssl[:6]:
    print("      %-28s amount=%14s journal=%s partner=%s" % (
        l.payment_ref or "-", rp(l.amount), l.journal_id.code, l.partner_id.name or "-"))

# ===========================================================================
sec("B. ORDER — contoh lengkap")
# ===========================================================================
o = POS.search([("date_order", ">=", AUG1), ("date_order", "<", AUG2)], order="id", limit=1)
print("contoh order id=%s" % o.id)
skip = {"create_date", "write_date", "write_uid", "create_uid", "__last_update"}
for fname, fld in sorted(POS._fields.items()):
    if fname in skip:
        continue
    try:
        val = o[fname]
    except Exception:
        continue
    if hasattr(val, "ids"):
        val = val.display_name if len(val.ids) <= 1 else "%s (+%d)" % (val[:1].display_name, len(val) - 1)
    if fname in ("name", "pos_reference", "date_order", "session_id", "config_id", "state",
                 "amount_total", "amount_paid", "amount_tax", "amount_return", "user_id",
                 "partner_id", "sequence_number", "account_move", "picking_ids", "nb_print",
                 "company_id", "currency_id", "pricelist_id", "note", "source", "last_order_preparation_change"):
        print("   %-28s %-10s = %r" % (fname, fld.type, val))

print("\n   line order ini: %d" % len(o.lines))
for l in o.lines[:3]:
    print("      product=%-34s qty=%-8s price_unit=%-12s subtotal=%-12s incl=%-12s disc=%s tax=%s" % (
        l.product_id.display_name[:34], l.qty, l.price_unit, l.price_subtotal,
        l.price_subtotal_incl, l.discount, l.tax_ids.mapped("name")))
    print("         full_product_name=%r | price_type=%s" % (getattr(l, "full_product_name", None), getattr(l, "price_type", None)))
    print("         field line:", sorted([k for k in POL._fields if k not in skip])[:30])

print("\n   payment order ini: %d" % len(o.payment_ids))
for p in o.payment_ids:
    print("      method=%-24s amount=%-14s date=%s | journal=%s" % (
        p.payment_method_id.name, rp(p.amount), p.payment_date, p.payment_method_id.journal_id.code))

print("\n   picking terkait order: %s" % (o.picking_ids.mapped("name") or "(tidak ada)"))
print("   account_move terkait: %s" % (o.account_move.name if o.account_move else "(tidak ada)"))

# ===========================================================================
sec("C. JEJAK STOK — apakah order Agustus punya stock.move sendiri?")
# ===========================================================================
print("   order Agustus dengan picking        : %d / %d" % (
    POS.search_count([("date_order", ">=", AUG1), ("date_order", "<", AUG2), ("picking_ids", "!=", False)]),
    POS.search_count([("date_order", ">=", AUG1), ("date_order", "<", AUG2)])))
print("   order Agustus dengan account_move   : %d" % POS.search_count(
    [("date_order", ">=", AUG1), ("date_order", "<", AUG2), ("account_move", "!=", False)]))
cr = env.cr
cr.execute("""SELECT origin, COUNT(*) FROM stock_move
              WHERE date >= '2026-08-01' AND date < '2026-09-01' AND state='done'
              GROUP BY origin ORDER BY COUNT(*) DESC LIMIT 8""")
print("   origin stock_move Agustus (top 8):")
for org, cnt in cr.fetchall():
    print("      %-34s %d" % ((org or "(kosong)")[:34], cnt))
cr.execute("""SELECT create_uid, COUNT(*) FROM stock_move
              WHERE date >= '2026-08-01' AND date < '2026-09-01' AND state='done'
              GROUP BY create_uid""")
print("   stock_move Agustus dibuat oleh uid:", cr.fetchall())
cr.execute("""SELECT COUNT(*) FROM stock_move WHERE date >= '2026-08-01' AND date < '2026-09-01'
              AND state='done' AND value = 0""")
print("   stock_move Agustus nilai 0:", cr.fetchone()[0])
print("   picking type terkait POS:", env["stock.picking.type"].search([("code", "=", "outgoing")]).mapped("name"))

# ===========================================================================
sec("D. PAJAK & HARGA")
# ===========================================================================
cr.execute("""SELECT COUNT(*) FROM pos_order_line WHERE order_id IN
              (SELECT id FROM pos_order WHERE date_order >= '2026-08-01' AND date_order < '2026-09-01')""")
print("   total pos.order.line Agustus:", cr.fetchone()[0])
cr.execute("""SELECT COUNT(*) FROM pos_order_line l JOIN pos_order o ON o.id = l.order_id
              WHERE o.date_order >= '2026-08-01' AND o.date_order < '2026-09-01'
              AND EXISTS (SELECT 1 FROM account_tax_pos_order_line_rel r WHERE r.pos_order_line_id = l.id)""")
print("   line dengan pajak:", cr.fetchone()[0])
cr.execute("""SELECT COUNT(DISTINCT t.id), t.name->>'en_US', t.amount FROM account_tax t
              JOIN account_tax_pos_order_line_rel r ON r.account_tax_id = t.id
              JOIN pos_order_line l ON l.id = r.pos_order_line_id
              JOIN pos_order o ON o.id = l.order_id
              WHERE o.date_order >= '2026-08-01' AND o.date_order < '2026-09-01'
              GROUP BY t.id, t.name, t.amount""")
print("   pajak yang dipakai:", cr.fetchall())
cr.execute("""SELECT COUNT(*) FROM account_move_line WHERE 1=0""")
print("   contoh harga produk (3 menu):")
for p in env["product.product"].search([("sale_ok", "=", True)], limit=3):
    print("      %-36s lst_price=%-12s taxes=%s" % (p.display_name[:36], p.lst_price, p.taxes_id.mapped("name")))

# ===========================================================================
sec("E. CARA ORDER AGUSTUS DIBUAT")
# ===========================================================================
cr.execute("""SELECT create_uid, COUNT(*), MIN(create_date), MAX(create_date) FROM pos_order
              WHERE date_order >= '2026-08-01' AND date_order < '2026-09-01'
              GROUP BY create_uid""")
print("   pos_order Agustus per uid:", cr.fetchall())
cr.execute("""SELECT u.id, u.login, p.name FROM res_users u
              JOIN res_partner p ON p.id = u.partner_id
              WHERE u.id IN (SELECT DISTINCT create_uid FROM pos_order WHERE date_order >= '2026-08-01')""")
print("   uid tersebut:", cr.fetchall())
cr.execute("""SELECT COUNT(*) FROM pos_order WHERE date_order >= '2026-08-01' AND date_order < '2026-09-01'
              AND pos_reference IS NULL""")
print("   order tanpa pos_reference:", cr.fetchone()[0])
cr.execute("""SELECT pos_reference, name FROM pos_order WHERE date_order >= '2026-08-01'
              ORDER BY id LIMIT 5""")
print("   contoh pos_reference/name:", cr.fetchall())
cr.execute("""SELECT source, COUNT(*) FROM pos_order WHERE date_order >= '2026-08-01'
              GROUP BY source""")
print("   distribusi 'source':", cr.fetchall())

# ===========================================================================
sec("F. DISTRIBUSI HARIAN & JAM (pola generator) — tetap READ-ONLY")
# ===========================================================================
cr.execute("""SELECT EXTRACT(DOW FROM date_order)::int AS dow, COUNT(*), SUM(amount_total)
              FROM pos_order WHERE date_order >= '2026-08-01' AND date_order < '2026-09-01'
              GROUP BY dow ORDER BY dow""")
print("   per hari (0=Minggu):")
for dow, cnt, amt in cr.fetchall():
    print("      DOW %d : %5d order | Rp %s" % (dow, cnt, rp(amt)))
cr.execute("""SELECT EXTRACT(HOUR FROM date_order)::int AS h, COUNT(*)
              FROM pos_order WHERE date_order >= '2026-08-01' AND date_order < '2026-09-01'
              GROUP BY h ORDER BY h""")
print("   per jam:", cr.fetchall())
cr.execute("""SELECT DATE(date_order), COUNT(*), SUM(amount_total)
              FROM pos_order WHERE date_order >= '2026-08-01' AND date_order < '2026-09-01'
              GROUP BY DATE(date_order) ORDER BY DATE(date_order) LIMIT 8""")
print("   per tanggal (8 pertama):")
for d, cnt, amt in cr.fetchall():
    print("      %s : %4d order | Rp %s" % (d, cnt, rp(amt)))

print("\n[RECON POS SELESAI — read-only]")
env.cr.rollback()
