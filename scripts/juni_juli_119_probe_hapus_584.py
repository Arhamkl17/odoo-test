# -*- coding: utf-8 -*-
"""
juni_juli_119_probe_hapus_584.py — UJI KELAYAKAN HAPUS TRANSAKSI `PKG MEVVAH` (READ-ONLY).

Tujuan: membuktikan apakah Odoo MENGIZINKAN penghapusan order POS, stock move, dan jurnal
yang menempel pada `PKG MEVVAH (AYAM GEPREK+TELUR ORAK ARIK+INDOMIE MEVVAH)` (tmpl 584).

PENTING: skrip ini TIDAK commit apa pun. Semua percobaan penghapusan dilakukan di dalam
transaksi yang di-rollback di akhir. Tidak ada satu baris pun yang berubah di DB.

  jalankan: su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/juni_juli_119_probe_hapus_584.py
"""
TM = 584
cr = env.cr
say = lambda m="": print(m)

say("=" * 112)
say("UJI KELAYAKAN HAPUS TRANSAKSI  tmpl=%s  (TIDAK COMMIT)" % TM)
say("=" * 112)

PT = env["product.template"].browse(TM)
pp = PT.product_variant_id
say("produk : %s  (product.product id=%s)" % (PT.name, pp.id))
say("")

# ---------- 1. status dokumen yang menempel ----------
say("[1] STATUS DOKUMEN YANG MENEMPEL")
for label, sql in (
    ("pos_order_line", "SELECT COUNT(*) FROM pos_order_line WHERE product_id=%s"),
    ("pos_order (lewat line)", "SELECT COUNT(DISTINCT o.id) FROM pos_order_line l JOIN pos_order o ON o.id=l.order_id WHERE l.product_id=%s"),
    ("stock_move", "SELECT COUNT(*) FROM stock_move WHERE product_id=%s"),
    ("stock_move state", "SELECT state, COUNT(*) FROM stock_move WHERE product_id=%s GROUP BY 1"),
    ("account_move_line", "SELECT COUNT(*) FROM account_move_line WHERE product_id=%s"),
    ("account_move (lewat line)", "SELECT COUNT(DISTINCT m.id) FROM account_move_line l JOIN account_move m ON m.id=l.move_id WHERE l.product_id=%s"),
    ("account_move state", "SELECT m.state, COUNT(*) FROM account_move_line l JOIN account_move m ON m.id=l.move_id WHERE l.product_id=%s GROUP BY 1"),
):
    cr.execute(sql, (pp.id,))
    rows = cr.fetchall()
    if len(rows) == 1:
        say("   %-24s : %s" % (label, rows[0][0]))
    else:
        say("   %-24s : %s" % (label, ", ".join("%s=%s" % r for r in rows)))

# ---------- 2. pembukuan yang terlibat ----------
cr.execute("""
    SELECT m.name, m.state, m.date::date, COUNT(*) AS baris,
           COALESCE(SUM(CASE WHEN aml.debit<>0 THEN aml.debit ELSE -aml.credit END),0)::numeric(14,2)
      FROM account_move_line aml JOIN account_move m ON m.id = aml.move_id
     WHERE aml.product_id = %s GROUP BY 1,2,3 ORDER BY 3
""", (pp.id,))
say("")
say("[2] JURNAL YANG TERLIBAT")
for n, st, d, b, v in cr.fetchall():
    say("   %-22s %-9s %s  %2d baris  nilai %14s" % (n or "-", st, d, b, "{:,.2f}".format(float(v))))

# ---------- 3. percobaan hapus: POS order ----------
say("")
say("[3] PERCOBAAN HAPUS — semuanya di-ROLLBACK")
cr.execute("SELECT DISTINCT l.order_id FROM pos_order_line l WHERE l.product_id=%s", (pp.id,))
oid = [r[0] for r in cr.fetchall()]
for model, ids, label in (
    ("pos.order", oid, "pos.order (%d)" % len(oid)),
):
    if not ids:
        say("   %-22s : tidak ada" % label)
        continue
    try:
        with env.cr.savepoint():
            env[model].browse(ids[:1]).unlink()
        say("   %-22s : BISA dihapus (Odoo tidak menolak)" % label)
    except Exception as e:
        say("   %-22s : DITOLAK → %s" % (label, str(e).strip().splitlines()[0][:150]))

# ---------- 4. percobaan hapus: stock move ----------
for state in ("done", "cancel", "draft"):
    cr.execute("SELECT array_agg(id) FROM stock_move WHERE product_id=%s AND state=%s", (pp.id, state))
    ids = cr.fetchone()[0] or []
    if not ids:
        continue
    try:
        with env.cr.savepoint():
            env["stock.move"].browse(ids[:1]).unlink()
        say("   stock.move %-9s : BISA dihapus" % state)
    except Exception as e:
        say("   stock.move %-9s : DITOLAK → %s" % (state, str(e).strip().splitlines()[0][:150]))

# ---------- 5. percobaan hapus: jurnal ----------
cr.execute("""
    SELECT array_agg(DISTINCT m.id), string_agg(DISTINCT m.state, ',')
      FROM account_move_line l JOIN account_move m ON m.id = l.move_id
     WHERE l.product_id = %s
""", (pp.id,))
mids, states = cr.fetchone()
say("   account_move status    : %s (%d move)" % (states, len(mids or [])))
try:
    with env.cr.savepoint():
        env["account.move"].browse((mids or [])[:1]).unlink()
    say("   account.move           : BISA dihapus")
except Exception as e:
    say("   account.move           : DITOLAK → %s" % str(e).strip().splitlines()[0][:150])

# ---------- 6. yang BISA dilakukan tanpa merusak buku ----------
say("")
say("[4] YANG BISA DILAKUKAN TANPA MERUSAK BUKU")
say("   a. arsipkan produk (active=False, available_in_pos=False) → hilang dari kasir")
say("   b. batalkan dokumen yang masih draft (bila ada) → boleh dihapus")
say("   c. reversal / credit note untuk jurnal ter-post → buku tetap seimbang & tertelusur")
say("")
say("   status sekarang: produk 584 active=%s, available_in_pos=%s" % (PT.active, PT.available_in_pos))
say("=" * 112)
env.cr.rollback()
say("ROLLBACK — tidak ada perubahan.")
