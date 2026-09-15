# -*- coding: utf-8 -*-
"""
reset_semua_01_wipe.py — BERSIHKAN SELURUH TRANSAKSI DB `Test1` (sisakan MASTER DATA).

Latar belakang (13 Sep 2026):
  Pemilik ingin memakai ulang DB demo ini untuk merapikan setup **pricelist & BOM**
  dulu, dan baru membuat lagi data transaksi dummy setelah sistem benar. Jadi seluruh
  transaksi lama dihapus sampai **nol**, termasuk jurnal pembukaan (modal disetor,
  akuisisi aset tetap, saldo awal persediaan) — keputusan pemilik 13 Sep 2026.

YANG DIHAPUS (semua jadi 0)
  * POS          : pos.order + line, pos.payment, pos.session, statement line POS
  * Stok         : stock.picking, stock.move, stock.move.line, product_value (valuasi),
                   stock.quant (persediaan dikosongkan), stock.scrap
  * Akuntansi    : account.move + line, account.partial/full.reconcile,
                   account.payment, account.bank.statement.line
  * Pembelian    : purchase.order + line, tagihan supplier (account.move)
  * B2B/katering : invoice penjualan (3 invoice)
  * Sequence     : nomor dokumen direset supaya dokumen baru mulai dari 1

YANG **TIDAK** DISENTUH (master data)
  * product.template / product.product (+ standard_price / harga beli bahan)
  * mrp.bom + mrp.bom.line (resep)
  * product.pricelist + product.pricelist.item (semua daftar harga)
  * res.partner (pelanggan, supplier, platform)
  * account.account, account.journal, tax, uom, kategori produk
  * pos.config, payment method, user/employee

CARA PAKAI
  dry-run  : su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db \\
               --db_port 5432 --db_user odoo --db_password odoo" < scripts/reset_semua_01_wipe.py
  eksekusi : tambahkan RUN=1 di depan perintah odoo shell

  RUN=1   eksekusi (default: dry-run, tidak ada data dihapus)

CATATAN TEKNIS
  * Penghapusan lewat SQL murni karena Odoo menolak unlink stock.move `done` dan
    move yang tersegel hash chain. Urutan tabel disusun mengikuti FK (anak dulu).
  * Semua penghapusan dilakukan dalam SATU transaksi; bila ada yang gagal -> rollback
    total, tidak ada perubahan setengah jalan.
  * Odoo 19: `stock_valuation_layer` tidak ada; valuasi hidup di `product_value` +
    `stock_move.value`.
  * Setelah eksekusi: restart/registry-signal server + hard-reload browser.
"""
import os

RUN = os.environ.get("RUN") == "1"

cr = env.cr
say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))
SEP = "=" * 104


# --------------------------------------------------------------------------- inv
MASTER = [
    ("produk (template)", "product_template"),
    ("BOM (resep)", "mrp_bom"),
    ("baris BOM", "mrp_bom_line"),
    ("item pricelist", "product_pricelist_item"),
    ("partner", "res_partner"),
    ("akun (COA)", "account_account"),
    ("jurnal", "account_journal"),
    ("pos.config", "pos_config"),
]

TRX = [
    ("order POS", "pos_order"),
    ("baris order POS", "pos_order_line"),
    ("pembayaran POS", "pos_payment"),
    ("sesi POS", "pos_session"),
    ("transfer stok (picking)", "stock_picking"),
    ("pergerakan stok", "stock_move"),
    ("baris pergerakan stok", "stock_move_line"),
    ("valuasi produk", "product_value"),
    ("quant persediaan", "stock_quant"),
    ("jurnal + tagihan + B2B", "account_move"),
    ("baris jurnal", "account_move_line"),
    ("rekonsiliasi parsial", "account_partial_reconcile"),
    ("rekonsiliasi penuh", "account_full_reconcile"),
    ("pembayaran (payment)", "account_payment"),
    ("mutasi bank (stmt line)", "account_bank_statement_line"),
    ("purchase order", "purchase_order"),
    ("baris purchase order", "purchase_order_line"),
    ("scrap", "stock_scrap"),
]


def count(table):
    cr.execute('SELECT count(*) FROM "%s"' % table)
    return cr.fetchone()[0]


def tb():
    cr.execute("""SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0)
                    FROM account_move_line aml
                    JOIN account_move am ON am.id = aml.move_id""")
    d, k = cr.fetchone()
    return float(d or 0), float(k or 0)


def money_sum(sql):
    cr.execute(sql)
    return float(cr.fetchone()[0] or 0)


say(SEP)
say("RESET TOTAL — BERSIHKAN SELURUH TRANSAKSI DB Test1   |   RUN=%s" % RUN)
say(SEP)

# --------------------------------------------------------------- pre-flight
say("")
say("A. MASTER DATA YANG DIPERTAHANKAN")
for label, table in MASTER:
    say("   %-28s : %s" % (label, count(table)))

d0, k0 = tb()
omzet = money_sum("SELECT COALESCE(SUM(amount_total),0) FROM pos_order")
say("")
say("B. RINGKASAN YANG AKAN DIHAPUS")
for label, table in TRX:
    say("   %-28s : %d" % (label, count(table)))
say("   %-28s : %s" % ("omzet POS", money(omzet)))
say("   %-28s : debit=%s credit=%s diff=%s" % ("total buku besar", money(d0), money(k0), money(d0 - k0)))
say("   %-28s : %d baris quant" % ("persediaan (quant)", count("stock_quant")))

# guard: tidak boleh ada sesi POS terbuka
open_sess = count("pos_session") and env["pos.session"].search_count([("state", "!=", "closed")])
if open_sess:
    say("")
    say("!! ADA %d SESI POS BELUM CLOSED -> dibatalkan." % open_sess)
    cr.rollback()
    raise SystemExit(1)

# master data tidak boleh kosong (sanity: kita menghapus transaksi, bukan master)
if count("product_template") == 0 or count("mrp_bom") == 0:
    say("")
    say("!! MASTER DATA KOSONG -> dibatalkan (mungkin salah DB?).")
    cr.rollback()
    raise SystemExit(1)

if not RUN:
    say("")
    say("DRY-RUN — tidak ada data dihapus. Jalankan dengan RUN=1 untuk eksekusi.")
    cr.rollback()
    raise SystemExit(0)

# --------------------------------------------------------------- eksekusi
PHASES = [
    ("FASE 1 — valuasi & pergerakan stok", [
        "DELETE FROM product_value",
        "DELETE FROM stock_move_line_consume_rel",
        "DELETE FROM stock_move_line_stock_put_in_pack_rel",
        "DELETE FROM lot_label_layout_stock_move_line_rel",
        'DELETE FROM "Products"',
        "DELETE FROM stock_move_line",
        "DELETE FROM stock_move_move_rel",
        "DELETE FROM stock_reference_move_rel",
        "DELETE FROM stock_move_created_purchase_line_rel",
        "DELETE FROM product_label_layout_stock_move_rel",
        "DELETE FROM account_analytic_line_stock_move_rel",
        "DELETE FROM template_attribute_value_stock_move_rel",
        "DELETE FROM stock_route_move",
        "DELETE FROM stock_move",
    ]),
    ("FASE 2 — transfer / picking", [
        "DELETE FROM stock_scrap",
        "DELETE FROM stock_return_picking",
        "DELETE FROM stock_return_picking_line",
        "DELETE FROM stock_backorder_confirmation_line",
        "DELETE FROM stock_picking_backorder_rel",
        "DELETE FROM stock_picking_sms_rel",
        "DELETE FROM picking_label_type_stock_picking_rel",
        "DELETE FROM purchase_order_stock_picking_rel",
        "DELETE FROM stock_package_history_stock_picking_rel",
        "DELETE FROM stock_picking",
    ]),
    ("FASE 3 — persediaan (quant)", [
        "DELETE FROM stock_conflict_quant_rel",
        "DELETE FROM stock_inventory_adjustment_name_stock_quant_rel",
        "DELETE FROM stock_inventory_conflict_stock_quant_rel",
        "DELETE FROM stock_inventory_warning_stock_quant_rel",
        "DELETE FROM stock_quant_stock_quant_relocate_rel",
        "DELETE FROM stock_quant_stock_request_count_rel",
        "DELETE FROM stock_quant",
    ]),
    ("FASE 4 — order & pembayaran POS", [
        "DELETE FROM restaurant_order_course",
        "DELETE FROM stock_reference_pos_order_rel",
        "DELETE FROM l10n_id_qris_transaction_pos_order_rel",
        "DELETE FROM pos_order_line",
        "DELETE FROM pos_payment",
        "DELETE FROM pos_order",
    ]),
    ("FASE 5 — statement line & sesi POS", [
        "DELETE FROM account_payment_account_bank_statement_line_rel",
        "DELETE FROM account_bank_statement_line",
        "DELETE FROM pos_daily_sales_reports_wizard",
        "DELETE FROM pos_session",
    ]),
    ("FASE 6 — pembayaran (account.payment)", [
        "DELETE FROM account_move__account_payment",
        "DELETE FROM payment_refund_wizard",
        "DELETE FROM payment_transaction",
        "DELETE FROM account_payment",
    ]),
    ("FASE 7 — jurnal & rekonsiliasi", [
        "DELETE FROM account_move_reversal_move",
        "DELETE FROM account_move_reversal_new_move",
        "DELETE FROM account_move_account_move_send_batch_wizard_rel",
        "DELETE FROM account_move_account_resequence_wizard_rel",
        "DELETE FROM account_move_renumber_wizard_ir_sequence_rel",
        "DELETE FROM account_move_l10n_id_qris_transaction_rel",
        "DELETE FROM account_move_validate_account_move_rel",
        "DELETE FROM account_move_send_wizard",
        "DELETE FROM account_move_purchase_order_rel",
        "DELETE FROM adjusting_entries__account_move",
        "DELETE FROM account_account_tag_account_move_line_rel",
        "DELETE FROM account_analytic_account_account_move_line_rel",
        "DELETE FROM account_move_line_account_move_make_netting_rel",
        "DELETE FROM account_move_line_account_tax_rel",
        "DELETE FROM account_payment_register_move_line_rel",
        "DELETE FROM sale_order_line_invoice_rel",
        "DELETE FROM mrp_workcenter_productivity",
        "UPDATE account_move_line SET full_reconcile_id = NULL",
        "DELETE FROM account_partial_reconcile",
        "DELETE FROM account_full_reconcile",
        "DELETE FROM account_move_line",
        "DELETE FROM account_move",
    ]),
    ("FASE 8 — purchase order", [
        "DELETE FROM purchase_order_line",
        "DELETE FROM stock_reference_purchase_rel",
        "DELETE FROM bill_to_po_wizard",
        "DELETE FROM purchase_order",
    ]),
]

say("")
say("C. EKSEKUSI (satu transaksi — gagal = rollback total)")
try:
    for ph, stmts in PHASES:
        say("")
        say("   %s" % ph)
        for sql in stmts:
            cr.execute(sql)
            n = cr.rowcount
            if n:
                say("      %-72s %6d baris" % (sql.replace("DELETE FROM ", "").replace("UPDATE ", "update "), n))

    say("")
    say("D. RESET SEQUENCE (dokumen baru mulai dari 1)")
    cr.execute("UPDATE ir_sequence SET number_next = 1")
    say("      ir_sequence            %6d baris" % cr.rowcount)
    cr.execute("UPDATE ir_sequence_date_range SET number_next = 1")
    say("      ir_sequence_date_range %6d baris" % cr.rowcount)

    env.cr.commit()
except Exception as e:
    env.cr.rollback()
    say("")
    say("!! GAGAL — seluruh perubahan di-ROLLBACK. Error: %s" % repr(e))
    raise
say("")
say("COMMIT selesai.")
say(SEP)


# --------------------------------------------------------------- verifikasi
def n(table):
    cr.execute('SELECT count(*) FROM "%s"' % table)
    return cr.fetchone()[0]


say("")
say("E. VERIFIKASI PASCA-RESET")
trx_tables = [
    "pos_order", "pos_order_line", "pos_payment", "pos_session",
    "stock_picking", "stock_move", "stock_move_line", "product_value", "stock_quant",
    "account_move", "account_move_line", "account_partial_reconcile",
    "account_full_reconcile", "account_payment", "account_bank_statement_line",
    "purchase_order", "purchase_order_line", "stock_scrap",
]
sisa = {t: n(t) for t in trx_tables}
bad = {t: c for t, c in sisa.items() if c}
for t in trx_tables:
    say("   %-30s : %s" % (t, sisa[t]))
say("")
d, k = tb()
say("   total buku besar : debit=%s credit=%s diff=%s" % (money(d), money(k), money(d - k)))

# keseimbangan akhir harus 0
cr.execute("""SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml
               JOIN account_move am ON am.id = aml.move_id WHERE am.state='posted'""")
say("   saldo posted     : %s" % money(cr.fetchone()[0]))
say("")
say("   MASTER DATA (harus tetap):")
for label, table in MASTER:
    say("      %-28s : %s" % (label, count(table)))

say("")
if bad:
    say("!! MASIH ADA SISA: %s" % bad)
else:
    say("BERSIH — seluruh transaksi 0, master data utuh.")
say("")
say("LANGKAH SELANJUTNYA: registry-signal/restart server + hard-reload browser,")
say("lalu rapikan setup pricelist & BOM. Data transaksi dummy dibuat belakangan.")
say(SEP)
