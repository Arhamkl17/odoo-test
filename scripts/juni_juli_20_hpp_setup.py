# -*- coding: utf-8 -*-
"""
juni_juli_20_hpp_setup.py — siapkan LOKASI ber-akun valuasi (Odoo 19).

Di Odoo 19 JE valuasi stok dibuat dari `stock.location.valuation_account_id`
(bukan lagi dari kategori produk). Jadi:

  * keluar  (internal -> lokasi konsumsi)  : Dr akun lokasi tujuan / Cr 1103.xx
  * masuk   (lokasi pembelian -> internal) : Dr 1103.xx / Cr akun lokasi asal

Yang dibuat (idempotent, cari dulu berdasarkan nama):

  BTL/Beverage    usage=production  akun 5101.01 HPP Beverage
  BTL/Food        usage=production  akun 5101.02 HPP Food
  BTL/Pendukung   usage=production  akun 5101.04 HPP Bahan Pendukung Menu
  BTL/Vendor      usage=supplier    akun 1101.01 Bank BSI   <-- PEMBELIAN TUNAI

Catatan: akun lokasi pembelian semula 2101.01 Utang Usaha; diganti ke 1101.01 Bank BSI
supaya pembelian bahan dibayar tunai dan tidak meninggalkan utang tanpa vendor.
Akibatnya lokasi ini berfungsi sebagai "laci pembayaran", bukan supplier berhutang.

  RUN=1  eksekusi (default dry-run)
"""
import os

RUN = os.environ.get("RUN") == "1"
cr = env.cr
Loc = env["stock.location"]
AA = env["account.account"]
say = lambda m="": print(m)

SPEC = [
    ("BTL/Beverage", "production", "5101.01"),
    ("BTL/Food", "production", "5101.02"),
    ("BTL/Pendukung", "production", "5101.04"),
    ("BTL/Vendor", "supplier", "1101.01"),   # pembelian TUNAI dari Bank BSI
]
NAMA_LEGACY = {   # nama lama (dibuat sebelum perbaikan) -> nama sekarang
    "Konsumsi/Beverage": "BTL/Beverage",
    "Konsumsi/Food": "BTL/Food",
    "Konsumsi/Pendukung": "BTL/Pendukung",
    "Pembelian/Vendor": "BTL/Vendor",
}


def acc(code):
    cr.execute("SELECT id FROM account_account WHERE code_store->>'1'=%s LIMIT 1", (code,))
    r = cr.fetchone()
    if not r:
        raise SystemExit("akun %s tidak ditemukan" % code)
    return AA.browse(r[0])


say("=" * 84)
say("SETUP LOKASI VALUASI STOK   |   RUN=%s" % RUN)
say("=" * 84)
for name, usage, code in SPEC:
    a = acc(code)
    # cari nama sekarang ATAU nama legacy supaya tidak membuat lokasi duplikat
    found = Loc.search([("complete_name", "=", name)], limit=1)
    if not found:
        for old, new in NAMA_LEGACY.items():
            if new == name:
                found = Loc.search([("complete_name", "=", old)], limit=1)
                break
    say("  %-22s usage=%-11s akun=%-8s %s  -> %s" % (
        name, usage, code, a.display_name,
        ("sudah ada id=%s (akun=%s)" % (found.id, found.valuation_account_id.display_name)
         if found else "AKAN DIBUAT")))
    if not found and RUN:
        loc = Loc.create({
            "name": name.split("/")[-1],
            "location_id": Loc.search([("usage", "=", "view")], limit=1).id or False,
            "usage": usage,
            "company_id": env.company.id,
            "valuation_account_id": a.id,
        })
        env.flush_all()
        say("        dibuat id=%s (%s)" % (loc.id, loc.complete_name))
        found = loc
    if found and RUN and found.valuation_account_id.id != a.id:
        found.valuation_account_id = a.id
        say("        akun diperbarui -> %s" % a.display_name)

if RUN:
    env.cr.commit()

say("")
say("Hasil akhir:")
for name, usage, code in SPEC:
    l = Loc.search([("complete_name", "=", name)], limit=1)
    if not l:
        for old, new in NAMA_LEGACY.items():
            if new == name:
                l = Loc.search([("complete_name", "=", old)], limit=1)
                break
    say("  %-22s id=%-6s akun=%s" % (
        name, l.id or "-", l.valuation_account_id.display_name if l else "BELUM ADA"))
say("=" * 84)
