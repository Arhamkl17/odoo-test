# -*- coding: utf-8 -*-
"""
juni_juli_84_dinein_config.py — R8 langkah 2b (TIDAK menyentuh ledger lama).

Odoo menolak satu metode bayar TUNAI dipakai di dua POS config
(`pos_config.py::_check_payment_method_ids_journal`). Karena itu tiap config
Dine In dibuatkan sendiri:
  * 1 akun kas baru  (1100.03 / 1100.04)
  * 1 jurnal kas baru (CSHD1 / CSHD2)
  * 1 metode bayar tunai baru
Metode NON-tunai (Kartu, QRIS, ShopeeFood) dipakai ulang — tidak ada batasan.

  dry-run : su odoo ... < scripts/juni_juli_84_dinein_config.py
  eksekusi: su odoo ... " RUN=1 odoo shell ..." < scripts/juni_juli_84_dinein_config.py
"""
import os

RUN = os.environ.get("RUN") == "1"
AA = env["account.account"]
AJ = env["account.journal"]
PM = env["pos.payment.method"]
Config = env["pos.config"]
PL = env["product.pricelist"]
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

pl_dn = PL.search([("name", "=", "Harga Dine In")], limit=1)
if not pl_dn:
    raise SystemExit("pricelist 'Harga Dine In' belum ada — jalankan 82 dulu.")

COMPANY = env.company
PLAN = [
    # (config sumber, nama baru, kode jurnal, kode akun, nama akun)
    ("Restoran Pallangga",   "Dine In Pallangga",   "CSHD1", "1100.03", "Kas Dine In Pallangga"),
    ("Restoran Mallengkeri", "Dine In Mallengkeri", "CSHD2", "1100.04", "Kas Dine In Mallengkeri"),
]

say("=" * 112)
say("BUAT 2 POS CONFIG DINE IN   |   RUN=%s" % RUN)
say("=" * 112)

made = []
for src_name, new_name, jcode, acode, aname in PLAN:
    src = Config.search([("name", "=", src_name)], limit=1)
    if not src:
        say("%-26s sumber TIDAK ADA" % new_name)
        continue
    if Config.search_count([("name", "=", new_name)]):
        say("%-26s SUDAH ADA — dilewati" % new_name)
        continue

    acc = AA.search([("code", "=", acode)], limit=1)
    if not acc:
        acc = AA.create({"name": aname, "code": acode, "account_type": "asset_cash",
                         "company_ids": [(6, 0, [COMPANY.id])]})
        say("   akun kas dibuat    : %s %s (id=%s)" % (acode, aname, acc.id))
    else:
        say("   akun kas dipakai   : %s %s (id=%s)" % (acode, aname, acc.id))

    jr = AJ.search([("code", "=", jcode)], limit=1)
    if not jr:
        jr = AJ.create({"name": aname, "code": jcode, "type": "cash",
                        "company_id": COMPANY.id, "default_account_id": acc.id})
        say("   jurnal kas dibuat  : %s (id=%s)" % (jcode, jr.id))
    else:
        say("   jurnal kas dipakai : %s (id=%s)" % (jcode, jr.id))

    # tunai baru + non-tunai dari config sumber
    cash_new = PM.create({"name": "%s Tunai" % new_name, "journal_id": jr.id,
                          "company_id": COMPANY.id})
    noncash = src.payment_method_ids.filtered(
        lambda m: m.journal_id and m.journal_id.type != "cash")
    pm_ids = [cash_new.id] + noncash.ids
    say("   metode bayar       : %s" % ", ".join(PM.browse(pm_ids).mapped("name")))

    vals = {
        "name": new_name,
        "journal_id": src.journal_id.id,
        "invoice_journal_id": src.invoice_journal_id.id,
        "picking_type_id": src.picking_type_id.id,
        "payment_method_ids": [(6, 0, pm_ids)],
        "pricelist_id": pl_dn.id,
        "company_id": COMPANY.id,
        "limit_categories": False,
        "iface_tax_included": src.iface_tax_included,
    }
    if "warehouse_id" in src._fields and src.warehouse_id:
        vals["warehouse_id"] = src.warehouse_id.id
    c = Config.create(vals)
    say("   CONFIG dibuat      : id=%s '%s' | pricelist=%s" % (c.id, c.name, c.pricelist_id.name))
    say("")
    made.append(c)

say("=" * 112)
say("RINGKASAN: %d config Dine In dibuat" % len(made))
say("")
say("SEMUA POS CONFIG SEKARANG:")
for c in Config.search([], order="id"):
    say("   id=%-3s %-26s pricelist=%-26s metode=%d" % (
        c.id, c.name, c.pricelist_id.name or "(kosong)", len(c.payment_method_ids)))

if not RUN:
    say("")
    say("DRY-RUN — semua perubahan DIBATALKAN.")
    env.cr.rollback()
else:
    env.cr.flush()
    env.cr.commit()
    say("")
    say("COMMITTED.")
say("=" * 112)
