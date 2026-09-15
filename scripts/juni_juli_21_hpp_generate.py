# -*- coding: utf-8 -*-
"""
juni_juli_21_hpp_generate.py — HPP berbasis KONSUMSI BOM + pembelian stok.

Untuk setiap bulan (Jun, Jul, Agu):
  1. ledakkan BOM setiap menu terjual -> kebutuhan tiap komponen
  2. PEMBELIAN : move masuk  BTL/Vendor(42) -> BTL/Stok(32), qty = kebutuhan,
                 tgl awal bulan  -> JE: Dr 1103.xx Persediaan / Cr 2101.01 Utang Usaha
  3. KONSUMSI  : move keluar BTL/Stok(32) -> konsumsi (39/40/41 sesuai kategori),
                 tgl akhir bulan -> JE: Dr 5101.xx HPP / Cr 1103.xx Persediaan
  4. AGUSTUS   : batalkan vendor bill lama yang mendebit 5101.* (metode lama)
                 supaya tidak dobel hitung.

Idempotent: semua move yang dibuat ber-`origin` "HPP-BOM <bulan> ..." dihapus dulu.

  RUN=1        eksekusi (default dry-run)
  MONTHS=june  batasi bulan (default june,july,august)
"""
import os
from collections import defaultdict
from datetime import timedelta

from odoo import fields

RUN = os.environ.get("RUN") == "1"
MONTHS = [m.strip() for m in os.environ.get("MONTHS", "june,july,august").split(",") if m.strip()]

cr = env.cr
Bom = env["mrp.bom"]
Prod = env["product.product"]
MV = env["stock.move"]
AM = env["account.move"]
Loc = env["stock.location"]
say = lambda m="": print(m)

PERIODS = {
    "june": ("2026-06-01", "2026-06-30", "Juni"),
    "july": ("2026-07-01", "2026-07-31", "Juli"),
    "august": ("2026-08-01", "2026-08-31", "Agustus"),
}
# kategori komponen -> lokasi konsumsi (akun HPP)
CONS = {5: 39, 6: 40, 7: 41}
STOK = 32          # BTL/Stok (internal)
VENDOR = 42        # BTL/Vendor (supplier, akun 2101.01)
ORIG = "HPP-BOM"

say("=" * 92)
say("GENERATE HPP (KONSUMSI BOM) + PEMBELIAN   |   RUN=%s | months=%s" % (RUN, ",".join(MONTHS)))
say("=" * 92)

if not Loc.browse(CONS[5]).exists() or not Loc.browse(VENDOR).exists():
    raise SystemExit("Lokasi valuasi belum dibuat — jalankan juni_juli_20_hpp_setup.py dulu.")


# --- explode BOM -----------------------------------------------------------
# Memakai API NATIVE Odoo: mrp.bom.explode(product, qty) -> (boms_done, lines_done).
# Jadi konversi UoM, ledakan multi-level, atribut varian, dan pembulatan semuanya
# dikerjakan engine Odoo (sama seperti saat menjual kit/phantom di POS).
def explode(tmpl, qty):
    """{component_product_id: qty} memakai mrp.bom.explode() milik Odoo."""
    bom = Bom.search([("product_tmpl_id", "=", tmpl.id),
                      ("type", "in", ("phantom", "normal"))], limit=1)
    if not bom or qty <= 0:
        return {tmpl.product_variant_id.id: qty}
    _boms_done, lines_done = bom.explode(bom.product_tmpl_id, qty)
    out = defaultdict(float)
    for bom_line, vals in lines_done:
        # CATATAN: vals['product'] = produk INDUN, bukan komponen.
        # Komponen yang benar = bom_line.product_id; vals['qty'] = qty hasil ledak.
        comp = bom_line.product_id
        comp_qty = vals.get("qty") or 0.0
        if not comp or not comp_qty:
            continue
        # `lines_done` memuat SEMUA level pohon BOM (termasuk node perantara).
        # Ambil hanya DAUN (komponen tanpa BOM sendiri) supaya tidak dobel hitung.
        if Bom.search_count([("product_tmpl_id", "=", comp.product_tmpl_id.id)]):
            continue
        out[comp.id] += comp_qty
    return out


def make_move(product, qty, src, dst, dt, origin):
    """Buat 1 stock.move selesai + JE valuasi otomatis (tanggal JE = force_period_date)."""
    mv = MV.with_context(force_period_date=dt).create({
        "product_id": product.id,
        "product_uom_qty": qty,
        "product_uom": product.uom_id.id,
        "location_id": src.id,
        "location_dest_id": dst.id,
        "origin": origin,
        # tanpa picking, `reference` kosong -> _get_account_move_line_vals gagal
        # (False + str). is_inventory + inventory_name mengisinya, sama seperti
        # move hasil penyesuaian stok di Agustus.
        "is_inventory": True,
        "inventory_name": origin,
    })
    mv._action_confirm()
    mv._action_assign()
    mv.quantity = qty
    mv.picked = True
    mv._action_done()
    try:
        mv.write({"date": "%s 12:00:00" % dt})
    except Exception:
        pass
    return mv


# --- bersihkan move lama (idempotent) -------------------------------------
# CATATAN (perbaikan 13 Sep 2026):
#   1. Sebelumnya pembersihan mengambil SEMUA move ber-origin `HPP-BOM%` tanpa melihat
#      bulan, lalu memanggil `_action_cancel()`. Dua masalah:
#        - menjalankan MONTHS=june,july ikut mencoba menghapus move Agustus;
#        - Odoo 19 MENOLAK `_action_cancel()` untuk move berstatus `done`
#          (`stock/models/stock_move.py::_action_cancel`).
#      `stock.move.unlink()` sendiri tidak memblokir move `done`
#      (`stock/models/stock_move.py::unlink` baris 2340), jadi unlink langsung dipakai.
LABELS = [PERIODS[k][2] for k in MONTHS]
old = MV.search([("origin", "like", ORIG + "%")]).filtered(
    lambda m: any((" %s " % lb) in (m.origin or "") for lb in LABELS))
say("Move lama ber-origin %s untuk %s: %d" % (ORIG, ",".join(LABELS), len(old)))
if old and RUN:
    jes = old.mapped("account_move_id")
    ids = tuple(old.ids)
    # `stock.move.line.unlink` menolak baris berstatus done/cancel
    # (`stock/models/stock_move_line.py::_unlink_except_done_or_cancel`). Karena move ini
    # murni buatan skrip ini (tidak ada picking, tidak ada operasi turunan), barisnya
    # dihapus lewat SQL lebih dulu, baru move-nya lewat ORM.
    cr.execute("SAVEPOINT sp_hpp_clean")
    try:
        cr.execute("DELETE FROM stock_move_line WHERE move_id IN %s", (ids,))
        n_ml = cr.rowcount
        MV.browse(ids).invalidate_recordset()
        MV.browse(ids).unlink()
        cr.execute("RELEASE SAVEPOINT sp_hpp_clean")
        say("   %d move + %d move line dihapus" % (len(old), n_ml))
    except Exception as e:
        cr.execute("ROLLBACK TO SAVEPOINT sp_hpp_clean")
        say("   !! gagal hapus move: %s" % repr(e)[:140])
        raise
    for j in jes.filtered(lambda x: x.exists()):
        try:
            j.line_ids.remove_move_reconcile()
            j.button_draft()
            j.unlink()
        except Exception as e:
            say("   (JE %s tidak terhapus: %s)" % (j.name, repr(e)[:80]))
    env.cr.commit()
    say("   JE valuasi ikut dibatalkan")

# --- hitung kebutuhan per bulan -------------------------------------------
POSL = env["pos.order.line"]
plan = {}
for key in MONTHS:
    d_from, d_to, label = PERIODS[key]
    lines = POSL.search([("order_id.date_order", ">=", d_from + " 00:00:00"),
                         ("order_id.date_order", "<=", d_to + " 23:59:59"),
                         ("order_id.state", "!=", "cancel")])
    need = defaultdict(float)
    for l in lines:
        tmpl = l.product_id.product_tmpl_id
        if Bom.search_count([("product_tmpl_id", "=", tmpl.id)]):
            for k, v in explode(tmpl, l.qty or 0.0).items():
                need[k] += v
    plan[key] = need
    val = sum(q * (Prod.browse(p).standard_price or 0.0) for p, q in need.items())
    say("%-7s %-8s order line=%-6d komponen=%-4d nilai=%s" % (
        label, d_from + ".." + d_to, len(lines), len(need), "{:,.2f}".format(val)))

if not RUN:
    say("")
    say("DRY-RUN — tidak ada data ditulis.")
    env.cr.rollback()
    raise SystemExit(0)

# --- eksekusi -------------------------------------------------------------
say("")
say("-" * 92)
tot_pur = tot_cons = 0.0
for key in MONTHS:
    d_from, d_to, label = PERIODS[key]
    need = plan[key]
    say("%s: pembelian tgl %s, konsumsi tgl %s" % (label, d_from, d_to))

    # 1. pembelian — TUNAI (lokasi BTL/Vendor ber-akun 1101.01 Bank BSI)
    #    Dipecah beberapa gelombang dalam bulan; kalau seluruh kebutuhan sebulan
    #    dibeli di tanggal 1, arus kas jadi negatif di awal bulan.
    d0 = fields.Date.to_date(d_from)
    d1 = fields.Date.to_date(d_to)
    span = (d1 - d0).days
    waves = 3 if span <= 12 else 5
    wave_dates = [d0 + timedelta(days=round(span * i / (waves - 1))) for i in range(waves)]
    n_p = 0
    v_p = 0.0
    for wi, wd in enumerate(wave_dates):
        share = 1.0 / waves if wi < waves - 1 else 1.0 - (waves - 1) / float(waves)
        for pid, q in sorted(need.items()):
            qw = q * share
            if qw <= 0:
                continue
            p = Prod.browse(pid)
            mv = make_move(p, qw, Loc.browse(VENDOR), Loc.browse(STOK), wd.isoformat(),
                           "%s beli %s %s" % (ORIG, label, p.default_code or p.id))
            v_p += mv.value or 0.0
            n_p += 1
        env.cr.commit()
    tot_pur += v_p
    say("   pembelian : %d move dalam %d gelombang (%s) nilai %s" % (
        n_p, waves, ", ".join(str(d) for d in wave_dates), "{:,.2f}".format(v_p)))

    # 2. konsumsi
    n_c = 0
    v_c = 0.0
    for pid, q in sorted(need.items()):
        if q <= 0:
            continue
        p = Prod.browse(pid)
        dst = Loc.browse(CONS.get(p.categ_id.id, CONS[6]))
        mv = make_move(p, q, Loc.browse(STOK), dst, d_to,
                       "%s konsumsi %s %s" % (ORIG, label, p.default_code or p.id))
        v_c += mv.value or 0.0
        n_c += 1
    env.cr.commit()
    tot_cons += v_c
    say("   konsumsi  : %d move  nilai %s" % (n_c, "{:,.2f}".format(v_c)))

# --- Agustus: batalkan vendor bill lama yang mendebit 5101.* --------------
say("")
say("-" * 92)
say("AGUSTUS: batalkan vendor bill lama (metode HPP berbasis bill)")
cr.execute("""
    SELECT DISTINCT am.id, am.name, am.state
      FROM account_move am JOIN account_move_line aml ON aml.move_id = am.id
      JOIN account_account aa ON aa.id = aml.account_id
     WHERE am.move_type = 'in_invoice' AND am.state = 'posted'
       AND am.date >= '2026-08-01' AND am.date < '2026-09-01'
       AND aa.code_store->>'1' LIKE '5101%%' AND aml.debit > 0
""")
bills = cr.fetchall()
say("   vendor bill HPP Agustus ditemukan: %d" % len(bills))
for bid, nm, st in bills:
    b = AM.browse(bid)
    try:
        b.button_cancel()
        say("      dibatalkan %s (%s)" % (nm, "{:,.2f}".format(sum(b.line_ids.mapped("debit")) / 2)))
    except Exception as e:
        say("      GAGAL %s -> %s" % (nm, repr(e)[:120]))
env.cr.commit()

# --- ringkasan ------------------------------------------------------------
say("")
say("=" * 92)
say("RINGKASAN")
say("   total pembelian stok : %s" % "{:,.2f}".format(tot_pur))
say("   total HPP konsumsi   : %s" % "{:,.2f}".format(tot_cons))
for key in MONTHS:
    d_from, d_to, label = PERIODS[key]
    cr.execute("""SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml
                    JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND aa.account_type='expense_direct_cost'
                     AND am.date >= %s AND am.date <= %s""", (d_from, d_to))
    hpp = cr.fetchone()[0]
    cr.execute("""SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml
                    JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND aa.code_store->>'1' LIKE '1103.0%%'
                     AND am.date <= %s""", (d_to,))
    stok = cr.fetchone()[0]
    say("   %-8s HPP=%18s | persediaan s/d %s = %18s" % (
        label, "{:,.2f}".format(hpp), d_to, "{:,.2f}".format(stok)))
say("")
say("   SALDO KAS/BANK per akhir bulan (harus >= 0)")
for _last in ("2026-06-30", "2026-07-31", "2026-08-31"):
    cr.execute("""SELECT COALESCE(SUM(aml.balance),0)
                    FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND am.date <= %s AND aa.account_type='asset_cash'""",
               (_last,))
    kas = cr.fetchone()[0]
    cr.execute("""SELECT COUNT(*) FROM (
                  SELECT aa.id, SUM(aml.balance) s FROM account_move_line aml
                    JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND am.date <= %s AND aa.account_type='asset_cash'
                   GROUP BY 1 HAVING SUM(aml.balance) < -0.01) x""", (_last,))
    neg = cr.fetchone()[0]
    say("      %s total kas/bank=%18s | akun negatif=%d %s" % (
        _last, "{:,.2f}".format(kas), neg, "OK" if neg == 0 else "<<< PERIKSA"))
cr.execute("""SELECT COALESCE(SUM(aml.debit),0), COALESCE(SUM(aml.credit),0)
                FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
               WHERE am.state='posted'""")
d, k = cr.fetchone()
say("   TB debit=%s credit=%s diff=%s" % (
    "{:,.2f}".format(d), "{:,.2f}".format(k), "{:,.2f}".format(d - k)))
say("=" * 92)
