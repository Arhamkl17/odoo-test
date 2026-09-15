# -*- coding: utf-8 -*-
"""perbaikan_10_hpp_subresep.py — F1: koreksi HPP sub-resep yang terlewat

Masalah (temuan F1 INSPEKSI_SISTEM_2026-09-15.md):
  `PAKET AYAM SEGEPOK BEREMPAT` (150 Jun / 427 Jul / 377 Agu = 954 pcs) memakai
  komponen MENU `NASI ×5` + `ES TEH ×5` (4.770 unit masing-masing). Kedua menu itu
  `consu` + `is_storable = false`, sementara `hpp_fifo_segmented_2toko_72hari_v2.py`
  dulu meledakkan BOM 1 level lalu menyaring `is_storable` → bahan daun NASI/ES TEH
  (BERAS, TEH MIX, ES KRISTAL, AIR GALON, GELAS, PIPET, ALAS NASI, CUKA, GARAM,
  MINYAK GORENG) TIDAK PERNAH dibeli & TIDAK PERNAH dibebankan.
  Akibat: HPP terposting 1.060.108.209,75 vs resep 1.075.021.852,90 → kurang 14.913.643,15.

Yang dilakukan skrip ini (mengikuti pola JE `STJ` yang sudah ada):
  1. hitung SELISIH kebutuhan bahan daun: `explode rekursif` − `1 level (storable)`
     per outlet × per bulan (persis bagian yang dulu dilewati);
  2. buat stock move PEMBELIAN segmented (fresh 3 hari / dry 7 hari) Vendor → Stok
     outlet — supaya bahan yang dipakai benar-benar dibeli (kas bank berkurang);
  3. buat stock move KONSUMSI Stok → lokasi produksi per kategori, tanggal akhir bulan
     → JE otomatis Dr `5101.0x HPP` / Cr `1103.0x Persediaan` (mesin Odoo, bukan JE manual).

Setelah skrip ini: HPP = 1.075.021.852,90 (± pembulatan < Rp 1) dan laba turun 14,91 jt.

Jalankan (default = DRY-RUN, tidak menulis apa pun):
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 \
    --db_user odoo --db_password odoo --log-level=warn" < scripts/perbaikan_10_hpp_subresep.py

Eksekusi:
  RUN=1 su odoo -s /bin/bash -c "odoo shell -d Test1 ..." < scripts/perbaikan_10_hpp_subresep.py

Env opsional: MONTHS=june,july,august (default ketiganya).
"""
import os
from collections import defaultdict
from datetime import timedelta
import math

from odoo import fields

RUN = os.environ.get("RUN") == "1"
MONTHS_ENV = [m.strip() for m in os.environ.get("MONTHS", "june,july,august").split(",") if m.strip()]

cr = env.cr
Prod = env["product.product"]
MV = env["stock.move"]
Loc = env["stock.location"]

say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))

PERIODS = {
    "june":   ("2026-06-20", "2026-07-01", "2026-06-30", "Juni 20-30"),
    "july":   ("2026-07-01", "2026-08-01", "2026-07-31", "Juli"),
    "august": ("2026-08-01", "2026-09-01", "2026-08-31", "Agustus"),
}
WH_STOK, BTL_STOK, VENDOR = 5, 32, 42
CONS = {5: 39, 6: 40, 7: 41}          # kategori bahan → lokasi produksi (konsisten data lama)
OUTLETS = {1: (WH_STOK, "Pallangga"), 2: (BTL_STOK, "Mallengkeri")}
ORIG = "KOREKSI-HPP-SUBRESEP"
MAX_DEPTH = 8

say("=" * 110)
say("F1 — KOREKSI HPP SUB-RESEP | RUN=%s | months=%s" % (RUN, ",".join(MONTHS_ENV)))
say("=" * 110)

# ---------------------------------------------------------------- preload
cr.execute("""
    SELECT b.product_tmpl_id, l.product_id, l.product_qty::float
    FROM mrp_bom b JOIN mrp_bom_line l ON l.bom_id = b.id
    WHERE b.active
""")
bom_map = defaultdict(list)
for tmpl, pid, qty in cr.fetchall():
    bom_map[tmpl].append((pid, qty))
cr.execute("SELECT id, product_tmpl_id FROM product_product")
pp_to_tmpl = {r[0]: r[1] for r in cr.fetchall()}
cr.execute("""
    SELECT pp.id, pt.id, pt.categ_id, pt.is_storable, pt.name->>'en_US',
           (pp.standard_price->>'1')::numeric, pt.uom_id, pp.default_code
    FROM product_product pp JOIN product_template pt ON pt.id = pp.product_tmpl_id
""")
prod_info = {}
for pid, tmpl, cat, is_stor, name, sp, uom, code in cr.fetchall():
    prod_info[pid] = {"tmpl": tmpl, "categ_id": cat, "is_storable": is_stor, "name": name,
                      "sp": float(sp or 0), "uom_id": uom, "code": code or str(pid)}
say("BOM: %d tmpl (%d baris) | produk: %d" % (len(bom_map), sum(len(v) for v in bom_map.values()), len(prod_info)))


def explode_need(pid, qty, _depth=0, _path=None):
    """Ledakkan sampai bahan daun (produk tanpa BOM). Cegah siklus via _path."""
    _path = _path or set()
    tmpl = pp_to_tmpl.get(pid)
    lines = bom_map.get(tmpl) if tmpl else None
    if not lines or _depth >= MAX_DEPTH or pid in _path:
        return [(pid, qty)]
    _path = _path | {pid}
    out = []
    for comp_pid, comp_qty in lines:
        out.extend(explode_need(comp_pid, qty * comp_qty, _depth + 1, _path))
    return out


# ---------------------------------------------------------------- 1) hitung selisih
say("")
say("[1] Hitung kebutuhan: resep penuh (rekursif) vs yang sudah dibebankan (1 level, storable)")
cr.execute("""
    SELECT to_char(o.date_order, 'YYYY-MM') AS bln, s.config_id AS cfg,
           l.product_id AS pid, sum(l.qty)::float AS qty
    FROM pos_order_line l
    JOIN pos_order o ON o.id = l.order_id
    JOIN pos_session s ON s.id = o.session_id
    WHERE o.date_order >= '2026-06-20' AND o.date_order < '2026-09-01'
      AND o.state != 'cancel'
    GROUP BY 1, 2, 3
""")
MKEY = {"2026-06": "june", "2026-07": "july", "2026-08": "august"}
full = defaultdict(lambda: defaultdict(float))   # (mkey,cfg) -> {leaf_pid: qty}
l1 = defaultdict(lambda: defaultdict(float))     # (mkey,cfg) -> {comp_pid: qty  (storable saja)}
skipped_menu = defaultdict(float)                # komponen menu tanpa BOM yang dilewati (info)
for bln, cfg, pid, qty in cr.fetchall():
    mkey = MKEY.get(bln)
    if not mkey or mkey not in MONTHS_ENV or cfg not in OUTLETS:
        continue
    info = prod_info.get(pid)
    if not info or info["tmpl"] not in bom_map:
        continue
    for leaf_pid, leaf_qty in explode_need(pid, qty):
        full[(mkey, cfg)][leaf_pid] += leaf_qty
    for comp_pid, comp_qty in bom_map[info["tmpl"]]:
        ci = prod_info.get(comp_pid)
        if ci and ci["is_storable"]:
            l1[(mkey, cfg)][comp_pid] += qty * comp_qty
        elif ci and ci["tmpl"] in bom_map:
            skipped_menu[ci["name"]] = skipped_menu.get(ci["name"], 0.0) + qty * comp_qty

delta = defaultdict(lambda: defaultdict(float))
for key in sorted(full, key=lambda k: (MONTHS_ENV.index(k[0]), k[1])):
    for leaf_pid, q in full[key].items():
        d = q - l1[key].get(leaf_pid, 0.0)
        if abs(d) > 1e-6:
            delta[key][leaf_pid] = d

say("")
say("  Komponen MENU ber-BOM yang dulu dilewati (inilah akar masalah):")
for name, q in sorted(skipped_menu.items(), key=lambda x: -x[1]):
    say("    %-12s %12.2f unit" % (name, q))

say("")
say("  Ringkasan selisih (yang akan dibeli + dibebankan):")
tot_qty = tot_val = 0.0
for mkey in MONTHS_ENV:
    label = PERIODS[mkey][3]
    for cfg, (stok, out_name) in OUTLETS.items():
        need = delta.get((mkey, cfg), {})
        val = sum(prod_info[p]["sp"] * q for p, q in need.items())
        tot_qty += sum(need.values())
        tot_val += val
        say("    %-12s %-13s komponen %-3d qty %14.2f nilai %18s" % (label, out_name, len(need), sum(need.values()), money(val)))

full_val = sum(prod_info[p]["sp"] * q for key in full for p, q in full[key].items())
l1_val = sum(prod_info[p]["sp"] * q for key in l1 for p, q in l1[key].items())
cr.execute("""SELECT COALESCE(SUM(status_amt),0) FROM (
                SELECT SUM(aml.balance) status_amt
                FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
                JOIN account_account aa ON aa.id = aml.account_id
                WHERE am.state='posted' AND aa.account_type='expense_direct_cost'
                GROUP BY aa.id) x""")
hpp_now = float(cr.fetchone()[0] or 0)
say("")
say("  HPP terposting sekarang            : %18s" % money(hpp_now))
say("  Nilai kebutuhan resep penuh        : %18s" % money(full_val))
say("  Nilai yang sudah dibebankan (1 lvl): %18s" % money(l1_val))
say("  SELISIH (target koreksi)           : %18s   (qty %s)" % (money(tot_val), "{:,.2f}".format(tot_qty)))
say("  Prediksi HPP setelah koreksi       : %18s" % money(hpp_now + tot_val))
say("  Target dokumen inspeksi            :           1,075,021,852.90")
if abs((hpp_now + tot_val) - 1075021852.90) > 5:
    say("  >>> PERHATIAN: prediksi menyimpang > Rp 5 dari target dokumen — periksa!")

# ---------------------------------------------------------------- 2) eksekusi
if not RUN:
    say("")
    say("DRY-RUN — tidak ada data ditulis. Jalankan RUN=1 untuk eksekusi.")
    env.cr.rollback()
    import sys
    sys.exit(0)


def make_move(product_id, qty, src_id, dst_id, dt, origin):
    info = prod_info[product_id]
    mv = MV.with_context(force_period_date=dt).create({
        "product_id": product_id,
        "product_uom_qty": qty,
        "product_uom": info["uom_id"],
        "location_id": src_id,
        "location_dest_id": dst_id,
        "origin": origin,
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


say("")
say("-" * 110)
say("[2] EKSEKUSI (pembelian segmented + konsumsi)")
tot_pur = tot_cons = 0.0
n_moves = 0
for mkey in MONTHS_ENV:
    d_from, d_to_excl, d_kons, label = PERIODS[mkey]
    d0 = fields.Date.to_date(d_from)
    d1 = fields.Date.to_date(d_kons)
    days = (d1 - d0).days + 1
    n_fresh = math.ceil(days / 3.0)
    n_dry = math.ceil(days / 7.0)

    def wave_dates(n):
        if n <= 1:
            return [d0]
        return [d0 + timedelta(days=round((days - 1) * i / (n - 1))) for i in range(n)]

    fresh_dates, dry_dates = wave_dates(n_fresh), wave_dates(n_dry)
    for cfg, (stok_id, out_name) in OUTLETS.items():
        need = delta.get((mkey, cfg), {})
        if not need:
            say("  %-12s %-13s tidak ada kebutuhan -> skip" % (label, out_name))
            continue
        fresh = {p: q for p, q in need.items() if prod_info[p]["categ_id"] == 6}
        dry = {p: q for p, q in need.items() if prod_info[p]["categ_id"] != 6}

        v_p = 0.0
        n_p = 0
        for wi, wd in enumerate(fresh_dates):
            share = 1.0 / n_fresh
            for pid, q in fresh.items():
                qw = q * share
                if qw <= 0.0001:
                    continue
                origin = "%s beli %s %s %s (fresh %d/%d)" % (ORIG, label, out_name, prod_info[pid]["code"][:15], wi + 1, n_fresh)
                mv = make_move(pid, qw, VENDOR, stok_id, wd.isoformat(), origin)
                v_p += mv.value or 0.0
                n_p += 1
            env.cr.commit()
        for wi, wd in enumerate(dry_dates):
            share = 1.0 / n_dry
            for pid, q in dry.items():
                qw = q * share
                if qw <= 0.0001:
                    continue
                origin = "%s beli %s %s %s (dry %d/%d)" % (ORIG, label, out_name, prod_info[pid]["code"][:15], wi + 1, n_dry)
                mv = make_move(pid, qw, VENDOR, stok_id, wd.isoformat(), origin)
                v_p += mv.value or 0.0
                n_p += 1
            env.cr.commit()

        v_c = 0.0
        n_c = 0
        for pid, q in sorted(need.items()):
            dst_id = CONS.get(prod_info[pid]["categ_id"], CONS[6])
            origin = "%s konsumsi %s %s %s" % (ORIG, label, out_name, prod_info[pid]["code"][:15])
            mv = make_move(pid, q, stok_id, dst_id, d_kons, origin)
            v_c += mv.value or 0.0
            n_c += 1
        env.cr.commit()
        tot_pur += v_p
        tot_cons += v_c
        n_moves += n_p + n_c
        say("  %-12s %-13s beli %2d move %18s | konsumsi %2d move %18s" % (label, out_name, n_p, money(v_p), n_c, money(v_c)))

env.cr.commit()
say("")
say("  total pembelian %s | total konsumsi (HPP) %s | move baru %d" % (money(tot_pur), money(tot_cons), n_moves))

# ---------------------------------------------------------------- 3) verifikasi
say("")
say("[3] Verifikasi HPP per bulan (dari buku besar)")
for mkey in MONTHS_ENV:
    d_from, d_to_excl, d_kons, label = PERIODS[mkey]
    cr.execute("""SELECT COALESCE(SUM(aml.balance),0)
                  FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
                  JOIN account_account aa ON aa.id = aml.account_id
                  WHERE am.state='posted' AND aa.account_type='expense_direct_cost'
                    AND am.date >= %s AND am.date <= %s""", (d_from, d_kons))
    hpp = float(cr.fetchone()[0] or 0)
    cr.execute("""SELECT COALESCE(SUM(aml.balance),0)
                  FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
                  JOIN account_account aa ON aa.id = aml.account_id
                  WHERE am.state='posted' AND aa.code_store->>'1' IN ('1103.01','1103.02','1103.03')
                    AND am.date <= %s""", (d_kons,))
    stok = float(cr.fetchone()[0] or 0)
    say("  %-12s HPP %18s | saldo akun persediaan alur %s" % (label, money(hpp), money(stok)))
cr.execute("""SELECT COALESCE(SUM(aml.debit),0), COALESCE(SUM(aml.credit),0)
              FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
              WHERE am.state='posted'""")
d, k = cr.fetchone()
say("  TB debit %s credit %s diff %s %s" % (money(d), money(k), money(float(d or 0) - float(k or 0)),
                                           "OK" if abs(float(d or 0) - float(k or 0)) < 0.01 else ">>>"))
say("=" * 110)
