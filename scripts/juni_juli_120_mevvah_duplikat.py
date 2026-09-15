# -*- coding: utf-8 -*-
"""
juni_juli_120_mevvah_duplikat.py — SELESAIKAN DUPLIKAT MEVVAH (13 Sep 2026).

KEPUTUSAN PEMILIK (13 Sep 2026): "yang duplikat hapus salah satu, jika sudah ada transaksi
di history hapus aja yang berkaitan."

DUPLIKAT YANG DIMAKSUD
  `PKG MEVVAH (AYAM GEPREK+TELUR ORAK ARIK+INDOMIE MEVVAH)` (tmpl 584) vs
  `PAKET MEVVAH BERDUA` (tmpl 625)  — resep IDENTIK 100% (28 baris, komponen & qty sama),
  tapi harga 36.500 vs 53.500 (selisih 46,6%). Yang dibuang: **584** (margin 16,2%).

HASIL UJI `juni_juli_119_probe_hapus_584.py` — Odoo MENOLAK hapus transaksinya:
  • pos.order  (177 order)     → DITOLAK ("penjualan harus baru atau dibatalkan")
  • stock.move (112, semua done) → DITOLAK ("menghapus pergerakan setelah transfer selesai?")
  • account.move (10)          → BOLEH, dan semuanya state='cancel' nilai 0,00
Jadi skrip ini:
  1. mengarsipkan produk 584 + menonaktifkan resepnya  → hilang dari kasir
  2. menghapus 10 jurnal cancel bernilai 0 miliknya     → satu-satunya yang bisa & aman
  3. TIDAK menyentuh pos_order dan stock_move (ditolak Odoo; dipaksa = buku & stok rusak)

Idempotent. Backup: `backup_pre_harga_bahan_klien_2026-09-13.dump` (dibuat sebelum ini).

  dry-run : su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/juni_juli_120_mevvah_duplikat.py
  eksekusi: RUN=1 ... (perintah sama)
"""
import os

RUN = os.environ.get("RUN") == "1"
BUANG = 584          # PKG MEVVAH (...) — yang diarsipkan
SIMPAN = 625         # PAKET MEVVAH BERDUA — yang dipertahankan

cr = env.cr
PT = env["product.template"]
BOM = env["mrp.bom"]
AM = env["account.move"]
say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))


def pp_id_of(tmpl_id):
    """product.product id — lewat SQL, karena `product_variant_id` kosong untuk produk terarsip."""
    cr.execute("SELECT id FROM product_product WHERE product_tmpl_id=%s ORDER BY id LIMIT 1", (tmpl_id,))
    r = cr.fetchone()
    return r[0] if r else None


def hpp_of(tmpl_id):
    cr.execute("""
        SELECT COALESCE(SUM(bl.product_qty * COALESCE((cp.standard_price->>'1')::numeric, 0)), 0)
          FROM mrp_bom b JOIN mrp_bom_line bl ON bl.bom_id = b.id
          LEFT JOIN product_product cp ON cp.id = bl.product_id
         WHERE b.product_tmpl_id = %s AND b.active
    """, (tmpl_id,))
    return float(cr.fetchone()[0] or 0)


say("=" * 116)
say("SELESAIKAN DUPLIKAT MEVVAH   |   RUN=%s" % RUN)
say("=" * 116)

a = PT.browse(BUANG)
b = PT.browse(SIMPAN)
PP_A = pp_id_of(BUANG)
for t, label in ((a, "BUANG"), (b, "SIMPAN")):
    if not t.exists():
        raise SystemExit("!! tmpl %s tidak ada" % t.id)
    harga = float(t.list_price or 0)
    hpp = hpp_of(t.id)
    say("   %-7s tmpl %-4s %-58s jual %s  HPP %s  margin %.1f%%" % (
        label, t.id, t.name[:57], money(harga), money(hpp),
        ((harga - hpp) / harga * 100) if harga else 0))

# ---------- dokumen yang menempel ----------
cr.execute("SELECT COUNT(*) FROM pos_order_line WHERE product_id=%s", (PP_A,))
n_posline = cr.fetchone()[0]
cr.execute("SELECT COUNT(*) FROM stock_move WHERE product_id=%s", (PP_A,))
n_move = cr.fetchone()[0]
cr.execute("""
    SELECT array_agg(DISTINCT m.id) FROM account_move_line l
      JOIN account_move m ON m.id = l.move_id
     WHERE l.product_id = %s AND m.state = 'cancel'
""", (PP_A,))
hapus_moves = cr.fetchone()[0] or []
cr.execute("""
    SELECT array_agg(DISTINCT m.id) FROM account_move_line l
      JOIN account_move m ON m.id = l.move_id
     WHERE l.product_id = %s AND m.state <> 'cancel'
""", (PP_A,))
sisa_moves = cr.fetchone()[0] or []

say("")
say("[DOKUMEN MENEMPEL pada tmpl %s]" % BUANG)
say("   pos_order_line            : %d   → TIDAK disentuh (ditolak Odoo)" % n_posline)
say("   stock_move                : %d   → TIDAK disentuh (ditolak Odoo)" % n_move)
say("   account_move state=cancel : %d   → akan dihapus (nilai 0)" % len(hapus_moves))
if sisa_moves:
    say("   account_move state lain   : %d   → TIDAK disentuh" % len(sisa_moves))

# ---------- rencana ----------
say("")
say("[RENCANA]")
say("   1. tmpl %s : active=False, available_in_pos=False  → hilang dari kasir" % BUANG)
say("   2. resep tmpl %s (%d BOM) : active=False" % (BUANG, BOM.search_count([("product_tmpl_id", "=", BUANG)])))
say("   3. hapus %d account_move (cancel, nilai 0) milik tmpl %s" % (len(hapus_moves), BUANG))
say("   4. tmpl %s tetap aktif di harga %s (margin %.1f%%)" % (
    SIMPAN, money(b.list_price), ((float(b.list_price) - hpp_of(SIMPAN)) / float(b.list_price) * 100)))

if not RUN:
    say("")
    say("DRY-RUN — tidak ada perubahan. Jalankan RUN=1 untuk eksekusi.")
    say("=" * 116)
    env.cr.rollback()
    raise SystemExit(0)

# ---------- eksekusi ----------
say("")
say("[EKSEKUSI]")
a.with_context(disable_auto_revaluation=True).write({"active": False, "available_in_pos": False})
say("   produk %s diarsipkan" % BUANG)
boms = BOM.search([("product_tmpl_id", "=", BUANG)])
if boms:
    boms.write({"active": False})
    say("   %d resep dinonaktifkan" % len(boms))
if hapus_moves:
    for m in AM.browse(hapus_moves):
        say("   hapus %-22s %-8s %s  nilai %s" % (m.name, m.state, m.date, money(m.amount_total)))
    AM.browse(hapus_moves).unlink()
    say("   %d account_move dihapus" % len(hapus_moves))
env.cr.flush()
env.cr.commit()
say("   [COMMITTED]")

# ---------- verifikasi ----------
say("")
say("=" * 116)
say("[VERIFIKASI]")
a = PT.browse(BUANG)
b = PT.browse(SIMPAN)
say("   tmpl %s : active=%s  available_in_pos=%s  BOM aktif=%d" % (
    BUANG, a.active, a.available_in_pos, BOM.search_count([("product_tmpl_id", "=", BUANG), ("active", "=", True)])))
say("   tmpl %s : active=%s  available_in_pos=%s  harga %s" % (
    SIMPAN, b.active, b.available_in_pos, money(b.list_price)))
cr.execute("SELECT COUNT(*) FROM pos_order_line WHERE product_id=%s", (PP_A,))
say("   pos_order_line tmpl %s  : %d  (utuh — sengaja)" % (BUANG, cr.fetchone()[0]))
cr.execute("SELECT COUNT(*) FROM stock_move WHERE product_id=%s", (PP_A,))
say("   stock_move tmpl %s      : %d  (utuh — sengaja)" % (BUANG, cr.fetchone()[0]))
cr.execute("""
    SELECT COUNT(*) FROM account_move_line l JOIN account_move m ON m.id=l.move_id
     WHERE l.product_id=%s
""", (PP_A,))
say("   account_move_line tmpl %s: %d  (target 0)" % (BUANG, cr.fetchone()[0]))
cr.execute("SELECT COUNT(*) FROM product_template WHERE available_in_pos AND active AND sale_ok")
say("")
say("   produk POS aktif        : %d" % cr.fetchone()[0])
cr.execute("SELECT COUNT(*) FROM product_template WHERE name->>'en_US' ILIKE '%%MEVVAH%%' AND available_in_pos AND active")
say("   menu MEVVAH di kasir    : %d  (target 3: INDOMIE / PKG GEPREK / PAKET BERDUA)" % cr.fetchone()[0])
cr.execute("SELECT pt.name->>'en_US' FROM product_template pt WHERE pt.name->>'en_US' ILIKE '%%MEVVAH%%' AND pt.available_in_pos AND pt.active ORDER BY 1")
for (n,) in cr.fetchall():
    say("      - %s" % n)
cr.execute("SELECT ROUND(SUM(amount_total)::numeric,2) FROM pos_order WHERE state IN ('paid','done','invoiced')")
say("")
say("   omzet POS total (tidak berubah): %s" % money(cr.fetchone()[0]))
say("=" * 116)
