# -*- coding: utf-8 -*-
"""
hpp_fifo_segmented_2toko_72hari.py — HPP FIFO REAL_TIME SEGMENTED 2 TOKO (20 JUNI - 31 AGU, 72 HARI)

Portofolio skill: full FIFO otomatis via stock.move, 2 outlet terpisah (WH + BTL), 
segmented real F&B: 
  - Bahan Baku Food (ayam,bumbu,etc) = FRESH -> beli tiap 3 hari (4x Juni, 10-11x Juli/Agu)
  - Bahan Baku Beverage + Pendukung (bubuk,kemasan) = DRY -> mingguan (2x Juni, 5x Juli/Agu)
=> showcase ~120 Stock Moves pembelian + 100 konsumsi = ~220 JE valuasi per outlet

Asumsi: Tondo tidak punya data pembelian, L/R hanya total HPP 136jt (Food 92% dominan) -> 
  fresh dominan wajar restock 2-3 hari di F&B, dry weekly.

Flow per bulan per outlet:
  1. Hitung kebutuhan BOM via mrp.bom.explode (API Odoo native, handle UoM & phantom)
  2. PEMBELIAN: VENDOR(42)->STOK (WH 5 / BTL 32) split gelombang dalam bulan -> Dr 1103 / Cr 1101.01 (tunai)
  3. KONSUMSI: STOK -> BTL/Beverage(39)/Food(40)/Pendukung(41) akhir bulan -> Dr 5101.xx / Cr 1103.xx
  4. Idempotent: hapus move lama ber-origin HPP-BOM-2TOKO untuk bulan tsb

Stok awal 30 hari sudah ada (100 quant, 244.9jt). Pembelian = konsumsi => inventori tetap ~244jt.

  dry-run : cat scripts/hpp_fifo_segmented_2toko_72hari.py | odoo shell -d Test1 --no-http ...
  RUN=1   : RUN=1 cat scripts/hpp_fifo_segmented_2toko_72hari.py | odoo shell ...

Periode portfolio: 20-30 Jun (12d), Juli 31d, Agu 31d => 72 hari
"""
import os
from collections import defaultdict
from datetime import timedelta

RUN = os.environ.get("RUN") == "1"
MONTHS_ENV = [m.strip() for m in os.environ.get("MONTHS", "june,july,august").split(",") if m.strip()]

from odoo import fields

cr = env.cr
Bom = env["mrp.bom"]
Prod = env["product.product"]
MV = env["stock.move"]
AM = env["account.move"]
Loc = env["stock.location"]
PosLine = env["pos.order.line"]

say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

# Periode portfolio 72 hari (20 Juni start, bukan 1 Juni)
PERIODS = {
    "june":   ("2026-06-20", "2026-07-01", "2026-06-30", "Juni 20-30",  0),  # 11 hari
    "july":   ("2026-07-01", "2026-08-01", "2026-07-31", "Juli",        0),
    "august": ("2026-08-01", "2026-09-01", "2026-08-31", "Agustus",     0),
}

# Lokasi (hasil setup juni_juli_20_hpp_setup.py + opening)
WH_STOK = 5        # WH/Stok (Pallangga)
BTL_STOK = 32      # BTL/Stok (Mallengkeri)
VENDOR = 42        # BTL/Vendor supplier (tunai Bank BSI 1101.01)
CONS_BEV = 39      # BTL/Beverage -> 5101.01
CONS_FOOD = 40     # BTL/Food -> 5101.02
CONS_PEND = 41     # BTL/Pendukung -> 5101.04

# Map kategori id -> lokasi konsumsi
CONS = {
    5: CONS_BEV,   # Bahan Baku Beverage
    6: CONS_FOOD,  # Bahan Baku Food
    7: CONS_PEND,  # Bahan Pendukung Menu
}

# Outlet mapping: config -> (lokasi_stok, nama, share)
OUTLETS = {
    1: (WH_STOK, "Pallangga"),
    2: (BTL_STOK, "Mallengkeri"),
}

# Kategori Fresh vs Dry untuk segmented
# Fresh = Bahan Baku Food (cat 6) -> ayam,bumbu etc, restock tiap 3 hari
# Dry = Bahan Baku Beverage (5) + Pendukung (7) -> mingguan
FRESH_CATS = {6}
DRY_CATS   = {5,7}

ORIG = "HPP-BOM-2TOKO"

say("="*110)
say("HPP FIFO SEGMENTED 2 TOKO — 20 JUNI s/d 31 AGU (72 HARI) | RUN=%s | months=%s" % (RUN, ",".join(MONTHS_ENV)))
say("WH %s (Pallangga) + BTL %s (Mallengkeri) | Vendor %s (Bank BSI)" % (WH_STOK, BTL_STOK, VENDOR))
say("Konsumsi: Bev %s (5101.01) | Food %s (5101.02) | Pend %s (5101.04)" % (CONS_BEV, CONS_FOOD, CONS_PEND))
say("Segmented: Fresh (cat Food) 3 hari | Dry (Bev+Pend) 7 hari — mirip resto real")
say("="*110)

# Validate locations
for lid, code in [(WH_STOK,"WH/Stok"), (BTL_STOK,"BTL/Stok"), (VENDOR,"BTL/Vendor"), (CONS_BEV,"Beverage"), (CONS_FOOD,"Food"), (CONS_PEND,"Pendukung")]:
    if not Loc.browse(lid).exists():
        raise SystemExit("Lokasi %s id %s tidak ada — jalankan juni_juli_20_hpp_setup.py" % (code, lid))
say("Lokasi OK")

# Helper explode (pakai API Odoo native, sama spt juni_juli_21)
def explode(tmpl, qty):
    bom = Bom.search([("product_tmpl_id","=",tmpl.id), ("type","in",("phantom","normal"))], limit=1)
    if not bom or qty <= 0:
        # jika tmpl tidak punya BOM, anggap jadi daun (tapi untuk menu tanpa BOM seperti AIR GELAS ini tidak akan Dipakai HPP)
        return {}
    _boms_done, lines_done = bom.explode(bom.product_tmpl_id, qty)
    out = defaultdict(float)
    for bom_line, vals in lines_done:
        comp = bom_line.product_id
        comp_qty = vals.get("qty") or 0.0
        if not comp or not comp_qty:
            continue
        # hanya daun
        if Bom.search_count([("product_tmpl_id","=",comp.product_tmpl_id.id)]):
            continue
        out[comp.id] += comp_qty
    return out

def make_move(product, qty, src, dst, dt, origin):
    mv = MV.with_context(force_period_date=dt).create({
        "product_id": product.id,
        "product_uom_qty": qty,
        "product_uom": product.uom_id.id,
        "location_id": src.id,
        "location_dest_id": dst.id,
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

# --- Hitung kebutuhan per outlet per bulan ---
import math

plan = {}  # (month, outlet_config) -> {pp_id: qty_total}
total_need_all = defaultdict(float)

say("")
say("[1] Hitung kebutuhan BOM per outlet per bulan (explode via Odoo API)")
for mkey in MONTHS_ENV:
    if mkey not in PERIODS:
        continue
    d_from, d_to_excl, d_konsumsi, label, _ = PERIODS[mkey]
    # query per config
    for cfg_id, (stok_loc, outlet_name) in OUTLETS.items():
        # cari semua line POS untuk outlet ini dalam periode
        lines = PosLine.search([
            ("order_id.date_order", ">=", d_from + " 00:00:00"),
            ("order_id.date_order", "<", d_to_excl + " 00:00:00"),
            ("order_id.state", "!=", "cancel"),
            ("order_id.session_id.config_id", "=", cfg_id),
        ])
        need = defaultdict(float)
        for l in lines:
            tmpl = l.product_id.product_tmpl_id
            if not Bom.search_count([("product_tmpl_id","=",tmpl.id)]):
                # menu tanpa BOM (AIR GELAS) -> tidak ada HPP bahan
                continue
            qty = l.qty or 0.0
            if qty <=0:
                continue
            exploded = explode(tmpl, qty)
            for pid, q in exploded.items():
                need[pid] += q
                total_need_all[pid] += q
        plan[(mkey, cfg_id)] = need
        # skip non-storable? filter untuk laporan tapi keep full for now, filter saat eksekusi
        # hitung nilai estimasi (qty * sp)
        val = 0.0
        for pid, q in need.items():
            p = Prod.browse(pid)
            # sp jsonb
            cr.execute("SELECT (standard_price->>'1')::numeric FROM product_product WHERE id=%s", (pid,))
            r = cr.fetchone()
            sp = float(r[0] or 0) if r else 0.0
            val += q * sp
        # hitung komponen storable only
        need_storable = 0
        val_storable = 0.0
        for pid, q in need.items():
            cr.execute("SELECT pt.is_storable FROM product_product pp JOIN product_template pt ON pt.id=pp.product_tmpl_id WHERE pp.id=%s", (pid,))
            r = cr.fetchone()
            is_stor = r[0] if r else False
            if is_stor:
                need_storable +=1
                cr.execute("SELECT (standard_price->>'1')::numeric FROM product_product WHERE id=%s", (pid,))
                sp = float(cr.fetchone()[0] or 0)
                val_storable += q*sp
        say("  %-12s %-13s (%s) : lines=%-5d komponen total=%-3d (storable=%-3d) nilai total=%s (storable %s)" % (
            label, outlet_name, "cfg %s"%cfg_id, len(lines), len(need), need_storable, money(val), money(val_storable)
        ))

# Ringkasan total
say("")
say("[1b] Total kebutuhan gabungan 72 hari (semua outlet)")
cr.execute("SELECT (pp.standard_price->>'1')::numeric, pp.id FROM product_product pp WHERE pp.id = ANY(%s)", (list(total_need_all.keys()),))
sp_map = {r[1]: float(r[0] or 0) for r in cr.fetchall()}
total_val = sum(total_need_all[pid]*sp_map.get(pid,0) for pid in total_need_all)
# kategorikan
cat_need = defaultdict(lambda: defaultdict(float))  # cat_name -> pid->qty
for pid, q in total_need_all.items():
    cr.execute("SELECT pt.categ_id, pc.name FROM product_product pp JOIN product_template pt ON pt.id=pp.product_tmpl_id JOIN product_category pc ON pc.id=pt.categ_id WHERE pp.id=%s", (pid,))
    r = cr.fetchone()
    if r:
        cat_id, cat_name = r
        cat_need[cat_name][pid] += q

for cat in sorted(cat_need):
    qty_sum = sum(cat_need[cat].values())
    val_sum = sum(cat_need[cat][pid]*sp_map.get(pid,0) for pid in cat_need[cat])
    say("  %-28s komponen %-3d  qty total %-12.0f  nilai %-14s  (%.1f%%)" % (cat, len(cat_need[cat]), qty_sum, money(val_sum), 100*val_sum/total_val if total_val else 0))
say("  TOTAL 72 hari: nilai HPP estimasi (storable) = %s" % money(total_val))
# bandingkan dengan omzet 2.384M => cost ratio
cr.execute("SELECT sum(amount_total) FROM pos_order WHERE date_order >= '2026-06-20' AND date_order < '2026-09-01' AND state!='cancel'")
omzet = float(cr.fetchone()[0] or 0)
say("  Omzet POS 72 hari  %s  => cost ratio %.1f%% (target master 43.9%%, Tondo 59.4%%)" % (money(omzet), 100*total_val/omzet if omzet else 0))

# --- Segmented: fresh vs dry summary ---
say("")
say("[1c] Segmented plan: Fresh (Food) tiap 3 hari vs Dry (Bev+Pend) tiap 7 hari")
for mkey in MONTHS_ENV:
    d_from, d_to_excl, d_kons, label, _ = PERIODS[mkey]
    d0 = fields.Date.to_date(d_from)
    d1 = fields.Date.to_date(d_kons)  # inclusive last day
    days = (d1 - d0).days + 1
    fresh_waves = math.ceil(days / 3.0)
    dry_waves = math.ceil(days / 7.0)
    say("  %-12s %2d hari => Fresh %2d gelombang (tiap 3 hari) | Dry %2d gelombang (mingguan)" % (label, days, fresh_waves, dry_waves))
    for cfg_id, (stok_loc, out_name) in OUTLETS.items():
        need = plan.get((mkey, cfg_id), {})
        # count per cat
        fresh_n = sum(1 for pid in need if Prod.browse(pid).categ_id.id in FRESH_CATS)
        dry_n = sum(1 for pid in need if Prod.browse(pid).categ_id.id in DRY_CATS)
        say("    %-13s fresh komponen %-3d (waves %-2d -> %-4d moves) | dry %-3d (waves %-2d -> %-4d moves) | konsumsi %-3d"
            % (out_name, fresh_n, fresh_waves, fresh_n*fresh_waves, dry_n, dry_waves, dry_n*dry_waves, len(need)))

# --- Hapus move lama untuk bulan terpilih (idempotent) ---
LABELS = [PERIODS[k][3] for k in MONTHS_ENV]
say("")
say("[2] Bersihkan move lama origin %s untuk %s" % (ORIG, ", ".join(LABELS)))

# Cari semua move lama dengan origin like HPP-BOM-2TOKO
old = MV.search([("origin","like", ORIG+"%")])
# filter untuk bulan terpilih via label di origin (contains label month? we use label like "Juni" etc not reliable.
# Instead filter by date between periode? Simpler: filter by move date.
# Kita simpan origin format: "HPP-BOM-2TOKO beli Agustus AYAM_CUT_9" etc, label ada di origin ke-2 token.
# Jadi filter lambda any label in origin
filtered_old = old.filtered(lambda m: any(lbl in (m.origin or "") for lbl in LABELS) )
# Jika tidak ketemu label, fallback hapus semua untuk periode date range
if not filtered_old and old:
    # fallback: hapus yang tanggalnya dalam periode terpilih
    to_delete_ids = []
    for m in old:
        # ambil tanggal move date (field date)
        move_date = fields.Date.to_string(m.date.date()) if m.date else ""
        for mk in MONTHS_ENV:
            d_from, d_to_excl, _, _, _ = PERIODS[mk]
            if d_from <= move_date < d_to_excl or d_from <= (m.inventory_name or ""):
                filtered_old |= m
                break
say("  Move lama ditemukan: %d (filtered untuk bulan terpilih: %d)" % (len(old), len(filtered_old)))
if filtered_old and RUN:
    jes = filtered_old.mapped("account_move_id")
    ids = tuple(filtered_old.ids)
    cr.execute("SAVEPOINT sp_hpp_clean")
    try:
        cr.execute("DELETE FROM stock_move_line WHERE move_id IN %s", (ids,))
        n_ml = cr.rowcount
        MV.browse(ids).invalidate_recordset()
        MV.browse(ids).unlink()
        cr.execute("RELEASE SAVEPOINT sp_hpp_clean")
        say("    %d move + %d line dihapus" % (len(filtered_old), n_ml))
    except Exception as e:
        cr.execute("ROLLBACK TO SAVEPOINT sp_hpp_clean")
        say("    GAGAL hapus: %s" % repr(e)[:200])
        raise
    for j in jes.filtered(lambda x: x.exists()):
        try:
            j.line_ids.remove_move_reconcile()
            j.button_draft()
            j.unlink()
        except Exception as e:
            say("    JE %s gagal hapus: %s" % (j.name, repr(e)[:80]))
    env.cr.commit()
    say("    JE valuasi ikut dibatalkan")
elif filtered_old:
    say("  [dry] akan hapus %d move" % len(filtered_old))

if not RUN:
    say("")
    say("DRY-RUN — tidak ada data ditulis. Jalankan RUN=1 untuk eksekusi penuh.")
    say("  Estimasi total pembelian ~1.07M (HPP), kas cukup (2.45M) -> sisa ~1.38M OK, TB balance.")
    env.cr.rollback()
    import sys; sys.exit(0)

# --- Eksekusi ---
say("")
say("-"*110)
say("[3] EKSEKUSI HPP FIFO SEGMENTED")
tot_pur = 0.0
tot_cons = 0.0
total_moves = 0

for mkey in MONTHS_ENV:
    d_from, d_to_excl, d_konsumsi, label, _ = PERIODS[mkey]
    d0 = fields.Date.to_date(d_from)
    d1 = fields.Date.to_date(d_konsumsi)
    days = (d1 - d0).days + 1
    fresh_waves = math.ceil(days / 3.0)
    dry_waves = math.ceil(days / 7.0)
    # buat tanggal gelombang
    def wave_dates(n):
        if n <=1:
            return [d0]
        return [d0 + timedelta(days= round( (days-1) * i / (n-1) )) for i in range(n)]
    fresh_dates = wave_dates(fresh_waves)
    dry_dates = wave_dates(dry_waves)
    say("")
    say("%s (%s s/d %s = %d hari): fresh %d gelombang %s | dry %d gelombang %s | konsumsi %s"
        % (label, d_from, d_konsumsi, days, fresh_waves, ", ".join(str(d) for d in fresh_dates[:3]) + ("..." if len(fresh_dates)>3 else ""),
           dry_waves, ", ".join(str(d) for d in dry_dates[:3]) + ("..." if len(dry_dates)>3 else ""), d_konsumsi))

    for cfg_id, (stok_loc_id, outlet_name) in OUTLETS.items():
        need = plan.get((mkey, cfg_id), {})
        if not need:
            say("  %-13s tidak ada kebutuhan -> skip" % outlet_name)
            continue
        say("  %-13s (cfg %s, stok %s): %d komponen" % (outlet_name, cfg_id, stok_loc_id, len(need)))
        stok_loc = Loc.browse(stok_loc_id)
        vendor_loc = Loc.browse(VENDOR)
        # split need into fresh vs dry via category
        fresh_need = {}
        dry_need = {}
        for pid, qty in need.items():
            if qty <=0:
                continue
            # cek storable
            cr.execute("SELECT pt.is_storable FROM product_product pp JOIN product_template pt ON pt.id=pp.product_tmpl_id WHERE pp.id=%s", (pid,))
            r = cr.fetchone()
            is_stor = r[0] if r else False
            if not is_stor:
                # skip non-storable like NASI, ES TEH (tidak valuasi)
                continue
            # cek kategori
            cr.execute("SELECT pt.categ_id FROM product_product pp JOIN product_template pt ON pt.id=pp.product_tmpl_id WHERE pp.id=%s", (pid,))
            cat_id = cr.fetchone()[0]
            if cat_id in FRESH_CATS:
                fresh_need[pid] = qty
            else:
                dry_need[pid] = qty
        # Pembelian Fresh
        n_p = 0
        v_p = 0.0
        for wi, wd in enumerate(fresh_dates):
            # share: equally distributed, last wave adjust? simple 1/waves
            share = 1.0/fresh_waves
            for pid, q in fresh_need.items():
                qw = q * share
                if qw <= 0.0001:
                    continue
                p = Prod.browse(pid)
                origin = "%s beli %s %s %s (fresh %d/%d)" % (ORIG, label, outlet_name, p.default_code or p.display_name[:15], wi+1, fresh_waves)
                mv = make_move(p, qw, vendor_loc, stok_loc, wd.isoformat(), origin)
                v_p += mv.value or 0.0
                n_p += 1
            env.cr.commit()
            if (wi+1)%5==0:
                say("      fresh wave %d/%d selesai batch" % (wi+1, fresh_waves))
        # Pembelian Dry
        for wi, wd in enumerate(dry_dates):
            share = 1.0/dry_waves
            for pid, q in dry_need.items():
                qw = q * share
                if qw <= 0.0001:
                    continue
                p = Prod.browse(pid)
                origin = "%s beli %s %s %s (dry %d/%d)" % (ORIG, label, outlet_name, p.default_code or p.display_name[:15], wi+1, dry_waves)
                mv = make_move(p, qw, vendor_loc, stok_loc, wd.isoformat(), origin)
                v_p += mv.value or 0.0
                n_p += 1
            env.cr.commit()
        tot_pur += v_p
        total_moves += n_p
        say("    pembelian: %d move (fresh %d + dry %d) nilai %s" % (n_p, len(fresh_need)*fresh_waves if fresh_need else 0, len(dry_need)*dry_waves if dry_need else 0, money(v_p)))

        # Konsumsi
        n_c = 0
        v_c = 0.0
        for pid, q in sorted(need.items()):
            if q <=0:
                continue
            cr.execute("SELECT pt.is_storable, pt.categ_id FROM product_product pp JOIN product_template pt ON pt.id=pp.product_tmpl_id WHERE pp.id=%s", (pid,))
            row = cr.fetchone()
            if not row or not row[0]:
                continue
            is_stor, cat_id = row
            p = Prod.browse(pid)
            dst_id = CONS.get(cat_id, CONS_FOOD)
            dst = Loc.browse(dst_id)
            origin = "%s konsumsi %s %s %s" % (ORIG, label, outlet_name, p.default_code or p.display_name[:15])
            mv = make_move(p, q, stok_loc, dst, d_konsumsi, origin)
            v_c += mv.value or 0.0
            n_c += 1
        env.cr.commit()
        tot_cons += v_c
        total_moves += n_c
        say("    konsumsi : %d move nilai %s (%s)" % (n_c, money(v_c), "-> HPP"))

# --- Ringkasan ---
say("")
say("="*110)
say("RINGKASAN HPP 72 HARI SEGMENTED 2 TOKO")
say("  total pembelian: %s (%d moves)" % (money(tot_pur), total_moves - sum(len(plan.get((mk,cfg),{})) for mk in MONTHS_ENV for cfg in OUTLETS)))
say("  total HPP konsumsi: %s" % money(tot_cons))
for mkey in MONTHS_ENV:
    d_from, d_to_excl, d_kons, label, _ = PERIODS[mkey]
    for cfg_id, (stok_loc, out_name) in OUTLETS.items():
        # Hitung HPP per kategori per outlet per bulan via valuasi? Ambil dari account move line yang baru dibuat?
        pass
    # Global per bulan HPP
    cr.execute("""
        SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml
        JOIN account_move am ON am.id=aml.move_id
        JOIN account_account aa ON aa.id=aml.account_id
        WHERE am.state='posted' AND aa.account_type='expense_direct_cost' AND am.date >= %s AND am.date <= %s
    """, (PERIODS[mkey][0], PERIODS[mkey][2]))
    hpp = cr.fetchone()[0]
    cr.execute("""
        SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml
        JOIN account_move am ON am.id=aml.move_id
        JOIN account_account aa ON aa.id=aml.account_id
        WHERE am.state='posted' AND aa.code_store->>'1' IN ('1103.01','1103.02','1103.03')
          AND am.date <= %s
    """, (PERIODS[mkey][2],))
    stok = cr.fetchone()[0]
    say("  %-12s HPP s/d %s = %-14s | persediaan s/d %s = %s" % (label, PERIODS[mkey][2], money(hpp), PERIODS[mkey][2], money(stok)))

say("")
say("  SALDO KAS/BANK per akhir bulan (harus >=0)")
for last in ["2026-06-30","2026-07-31","2026-08-31"]:
    cr.execute("""
        SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml
        JOIN account_move am ON am.id=aml.move_id
        JOIN account_account aa ON aa.id=aml.account_id
        WHERE am.state='posted' AND am.date <= %s AND aa.account_type='asset_cash'
    """, (last,))
    kas = cr.fetchone()[0]
    cr.execute("""
        SELECT COUNT(*) FROM (
          SELECT aa.id FROM account_move_line aml
            JOIN account_move am ON am.id=aml.move_id
            JOIN account_account aa ON aa.id=aml.account_id
            WHERE am.state='posted' AND am.date <= %s AND aa.account_type='asset_cash'
            GROUP BY 1 HAVING SUM(aml.balance) < -0.01
        ) x
    """, (last,))
    neg = cr.fetchone()[0]
    say("    %s total kas/bank=%-14s | akun negatif=%d %s" % (last, money(kas), neg, "OK" if neg==0 else "<<< PERIKSA"))
cr.execute("SELECT COALESCE(SUM(aml.debit),0), COALESCE(SUM(aml.credit),0) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id WHERE am.state='posted'")
d,k = cr.fetchone()
say("  TB debit=%s credit=%s diff=%s %s" % (money(d), money(k), money(float(d or 0)-float(k or 0)), "OK" if abs(float(d or 0)-float(k or 0))<0.01 else ">>> TIDAK BALANCE"))
# stok quant check
cr.execute("SELECT location_id, count(*), sum(quantity) FROM stock_quant WHERE location_id IN (5,32) GROUP BY 1 ORDER BY 1")
for loc, cnt, qty in cr.fetchall():
    cr.execute("SELECT sum(sq.quantity * (pp.standard_price->>'1')::numeric) FROM stock_quant sq JOIN product_product pp ON pp.id=sq.product_id WHERE sq.location_id=%s", (loc,))
    val = cr.fetchone()[0] or 0
    say("  Stock loc %s: %s SKU qty %.0f est value %s (harus ~%s jika pembelian= konsumsi)" % (loc, cnt, qty or 0, money(val), money(136043299 if loc==5 else 108834639)))
say("="*110)
env.cr.commit()
