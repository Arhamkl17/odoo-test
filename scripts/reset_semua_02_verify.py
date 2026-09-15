# -*- coding: utf-8 -*-
"""
reset_semua_02_verify.py — VERIFIKASI pasca `reset_semua_01_wipe.py` (READ-ONLY).

Cek:
  1. seluruh model transaksi benar-benar 0
  2. master data (produk/BOM/pricelist/partner/COA) utuh
  3. buku besar nol & seimbang
  4. tidak ada sisa rekonsiliasi / saldo akun
  5. ORM sehat (search, read_group) — tidak ada error setelah SQL delete

  su odoo ... < scripts/reset_semua_02_verify.py
"""
cr = env.cr
say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))
SEP = "=" * 96


def count(model):
    try:
        return env[model].search_count([])
    except Exception as e:
        return "ERR: %s" % repr(e)[:60]


say(SEP)
say("VERIFIKASI PASCA-RESET — DB Test1")
say(SEP)

say("")
say("1. MODEL TRANSAKSI (harus 0)")
for m in ("pos.order", "pos.session", "pos.payment", "stock.picking", "stock.move",
          "stock.move.line", "stock.quant", "stock.scrap", "account.move",
          "account.move.line", "account.payment", "account.bank.statement.line",
          "purchase.order", "account.asset", "stock.lot", "stock.package"):
    say("   %-30s : %s" % (m, count(m)))

say("")
say("2. MASTER DATA (harus tetap)")
for m, label in (("product.template", "produk"), ("product.product", "varian"),
                 ("mrp.bom", "BOM"), ("mrp.bom.line", "baris BOM"),
                 ("product.pricelist", "pricelist"), ("product.pricelist.item", "item pricelist"),
                 ("res.partner", "partner"), ("account.account", "akun"),
                 ("account.journal", "jurnal"), ("uom.uom", "UoM"),
                 ("pos.config", "pos.config"), ("product.supplierinfo", "harga supplier")):
    say("   %-30s : %s" % ("%s (%s)" % (label, m), count(m)))

say("")
say("3. BUKU BESAR")
cr.execute("""SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) FROM account_move_line""")
d, k = cr.fetchone()
say("   debit=%s  credit=%s  diff=%s" % (money(d), money(k), money(float(d) - float(k))))
cr.execute("""SELECT count(*) FROM account_move_line WHERE balance <> 0""")
say("   baris dengan saldo <> 0 : %s" % cr.fetchone()[0])
cr.execute("""SELECT count(*) FROM account_partial_reconcile""")
say("   sisa rekonsiliasi parsial : %s" % cr.fetchone()[0])
cr.execute("""SELECT count(*) FROM account_full_reconcile""")
say("   sisa rekonsiliasi penuh   : %s" % cr.fetchone()[0])

say("")
say("4. CONFIG PENTING")
cr.execute("""SELECT j.code, j.name->>'en_US', j.restrict_mode_hash_table, j.active
                FROM account_journal j ORDER BY j.code""")
say("   jurnal (code | hash | active):")
for code, nm, h, a in cr.fetchall():
    say("      %-8s %-28s hash=%-5s active=%s" % (code, (nm or "")[:28], h, a))
cr.execute("SELECT count(*) FROM res_company WHERE account_opening_move_id IS NOT NULL")
say("   company punya opening move : %s (harus 0)" % cr.fetchone()[0])

say("")
say("5. HARGA (master data yang harus selamat)")
cr.execute("SELECT count(*) FROM product_product")
nprod = cr.fetchone()[0]
cr.execute("""SELECT count(*) FROM product_template
               WHERE list_price > 0 AND type <> 'service'""")
say("   produk total                        : %s" % nprod)
say("   template dengan harga jual > 0      : %s" % cr.fetchone()[0])
cr.execute("""SELECT count(*) FROM product_pricelist_item WHERE fixed_price IS NOT NULL
               AND fixed_price > 0""")
say("   item pricelist dengan harga tetap>0 : %s" % cr.fetchone()[0])

say("")
say("6. ORM SEHAT (uji baca)")
try:
    n = env["product.template"].search_count([])
    b = env["mrp.bom"].search_count([])
    say("   env search OK — produk=%d, BOM=%d" % (n, b))
except Exception as e:
    say("   !! ORM error: %s" % repr(e))
try:
    grp = env["account.move.line"]._read_group([], ["account_id"], ["balance:sum"])
    say("   _read_group account.move.line OK — %d grup (harus 0)" % len(grp))
except Exception as e:
    say("   !! _read_group error: %s" % repr(e))

say("")
say("CATATAN untuk langkah berikutnya:")
say("   * Semua transaksi & jurnal pembukaan sudah nol — termasuk modal, aset tetap,")
say("     dan saldo awal persediaan (keputusan pemilik 13 Sep 2026).")
say("   * Harga beli bahan (standard_price), resep (BOM), dan pricelist tetap utuh")
say("     untuk dirapikan.")
say("   * Backup pra-reset: backup_pre_reset_semua_transaksi_2026-09-13.dump")
say(SEP)
cr.rollback()
