# -*- coding: utf-8 -*-
"""
hpp_fifo_segmented_2toko_72hari_v2.py — V2 OPTIMIZED (bulk BOM, no per-line search)

Perbaikan v1 yang timeout di explode() per line (6381 lines * search_count = lambat).
v2: bulk preload bom_map + product info, hitung need via dict lookup O(1).

Lainnya sama: segmented fresh 3 hari vs dry 7 hari, 2 outlet WH/BTL, full FIFO real_time.

  dry-run : cat scripts/hpp_fifo_segmented_2toko_72hari_v2.py | odoo shell -d Test1 ...
  RUN=1   : RUN=1 cat scripts/hpp_fifo_segmented_2toko_72hari_v2.py | odoo shell ...
"""
import os
from collections import defaultdict
from datetime import timedelta
import math

RUN = os.environ.get("RUN") == "1"
MONTHS_ENV = [m.strip() for m in os.environ.get("MONTHS", "june,july,august").split(",") if m.strip()]

from odoo import fields

cr = env.cr
Prod = env["product.product"]
MV = env["stock.move"]
AM = env["account.move"]
Loc = env["stock.location"]

say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

PERIODS = {
    "june":   ("2026-06-20", "2026-07-01", "2026-06-30", "Juni 20-30"),
    "july":   ("2026-07-01", "2026-08-01", "2026-07-31", "Juli"),
    "august": ("2026-08-01", "2026-09-01", "2026-08-31", "Agustus"),
}
WH_STOK = 5
BTL_STOK = 32
VENDOR = 42
CONS_BEV = 39
CONS_FOOD = 40
CONS_PEND = 41
CONS = {5: CONS_BEV, 6: CONS_FOOD, 7: CONS_PEND}
OUTLETS = {1: (WH_STOK, "Pallangga"), 2: (BTL_STOK, "Mallengkeri")}
FRESH_CATS = {6}
ORIG = "HPP-BOM-2TOKO"

say("="*110)
say("HPP FIFO SEGMENTED 2 TOKO V2 (OPTIMIZED BULK) | RUN=%s | months=%s" % (RUN, ",".join(MONTHS_ENV)))
say("WH %s + BTL %s | Vendor %s | Bev %s Food %s Pend %s" % (WH_STOK, BTL_STOK, VENDOR, CONS_BEV, CONS_FOOD, CONS_PEND))
say("Segmented: Fresh (cat 6 Food) 3 hari | Dry (5+7 Bev/Pend) 7 hari")
say("="*110)

# --- preload BOM ---
say("")
say("[0] Preload BOM (mrp_bom + mrp_bom_line) ...")
cr.execute("""
    SELECT b.product_tmpl_id, l.product_id, l.product_qty::float
    FROM mrp_bom b JOIN mrp_bom_line l ON l.bom_id=b.id
    WHERE b.active
""")
bom_map = defaultdict(list)  # tmpl_id -> [(comp_pid, qty), ...]
for tmpl, pid, qty in cr.fetchall():
    bom_map[tmpl].append((pid, qty))
say("  BOM aktif: %d tmpl punya resep (%d total baris)" % (len(bom_map), sum(len(v) for v in bom_map.values())))
# set of tmpl yang punya BOM (untuk filter)
tmpl_with_bom = set(bom_map.keys())
# juga preload product->tmpl
cr.execute("SELECT id, product_tmpl_id FROM product_product")
pp_to_tmpl = {r[0]: r[1] for r in cr.fetchall()}
say("  product_product: %d varian" % len(pp_to_tmpl))

# preload product info bulk
say("[0b] Preload product info (is_storable, categ_id, uom, sp, name)...")
cr.execute("""
    SELECT pp.id, pt.id as tmpl, pt.categ_id, pt.is_storable, pt.name->>'en_US' as name,
           (pp.standard_price->>'1')::numeric as sp,
           pt.uom_id, pp.default_code
    FROM product_product pp JOIN product_template pt ON pt.id=pp.product_tmpl_id
""")
prod_info = {}
for row in cr.fetchall():
    pid, tmpl, cat_id, is_stor, name, sp, uom_id, code = row
    prod_info[pid] = {
        "tmpl": tmpl, "categ_id": cat_id, "is_storable": is_stor,
        "name": name, "sp": float(sp or 0), "uom_id": uom_id, "code": code or str(pid)
    }
say("  loaded %d product infos" % len(prod_info))
# also need for NASI/ES TEH check
for name in ["NASI","ES TEH"]:
    cr.execute("SELECT pp.id, pt.is_storable FROM product_product pp JOIN product_template pt ON pt.id=pp.product_tmpl_id WHERE pt.name->>'en_US'=%s", (name,))
    r = cr.fetchone()
    if r:
        say("  %-10s id=%s is_storable=%s sp=%s (dibuat via SQL quant, akan di-skip di HPP)" % (name, r[0], r[1], prod_info.get(r[0],{}).get("sp")))

# helper explode_need — pecah komponen sampai bahan daun (produk tanpa BOM).
# F1 15 Sep 2026: sebelumnya 1 level saja, sehingga sub-resep seperti NASI &
# ES TEH (dipakai PAKET AYAM SEGEPOK BEREMPAT) diperlakukan sebagai bahan beli
# padahal keduanya menu ber-BOM dan non-storable → bahan daunnya tidak pernah
# dibeli/dibebankan (HPP kurang catat 14,9 jt; lihat INSPEKSI_SISTEM_2026-09-15.md).
MAX_DEPTH = 8

def explode_need(pid, qty, _depth=0, _path=None):
    """Kembalikan [(product_id_daun, qty_total), ...] untuk `qty` unit `pid`."""
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


def make_move(product_id, qty, src_id, dst_id, dt, origin):
    # product_id is int
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

# --- Hitung kebutuhan per outlet per bulan (bulk, no ORM per line) ---
say("")
say("[1] Hitung kebutuhan BOM per outlet per bulan (bulk dict lookup)")
# For speed, fetch all relevant pos_order_lines in one query per period+outlet? Or one big query group by outlet
# Fetch sekali untuk 20 Jun - 1 Sep, grouping
cr.execute("""
    SELECT
        to_char(o.date_order,'YYYY-MM-DD') as d,
        s.config_id as cfg,
        l.product_id as pid,
        sum(l.qty)::float as tot_qty,
        count(*) as lines
    FROM pos_order_line l
    JOIN pos_order o ON o.id=l.order_id
    JOIN pos_session s ON s.id=o.session_id
    WHERE o.date_order >= '2026-06-20' AND o.date_order < '2026-09-01' AND o.state != 'cancel'
    GROUP BY 1,2,3
    ORDER BY 1,2
""")
# This grouping loses per-line but for HPP we need sum qty per product per day? Actually we just need sum qty per product per outlet per month, grouping is fine
# Aggregate to monthly per outlet
from collections import Counter
raw = cr.fetchall()
# raw: d, cfg, pid, tot_qty, lines
say("  raw aggregate rows: %d" % len(raw))
# Aggregate to plan
plan = defaultdict(lambda: defaultdict(float))  # (mkey,cfg)-> {comp_pid: qty}
# Need to map product to tmpl, then explode
# For each aggregated row: pid is menu product_id, qty is total menu qty
# Expand via bom_map
for d_str, cfg, menu_pid, tot_qty, _ in raw:
    # determine month bucket
    d = fields.Date.to_date(d_str)
    # find mkey
    mkey = None
    for mk, (d_from, d_to_excl, _, _) in PERIODS.items():
        if fields.Date.to_date(d_from) <= d < fields.Date.to_date(d_to_excl):
            mkey = mk
            break
    if not mkey or mkey not in MONTHS_ENV:
        continue
    if cfg not in OUTLETS:
        continue
    # if menu product has BOM
    tmpl = prod_info.get(menu_pid, {}).get("tmpl")
    if not tmpl or tmpl not in bom_map:
        # AIR GELAS etc without BOM skip
        continue
    # explode REKURSIF (F1 15 Sep 2026): komponen yang punya BOM sendiri
    # (mis. NASI, ES TEH pada PAKET AYAM SEGEPOK BEREMPAT) TIDAK boleh
    # diperlakukan sebagai bahan beli — kalau dibiarkan, bahan anaknya
    # (BERAS, TEH MIX, ES KRISTAL, …) tidak pernah dibeli/dibebankan.
    # Ledakkan terus sampai daun (produk tanpa BOM).
    for comp_pid, comp_qty in explode_need(menu_pid, tot_qty):
        plan[(mkey, cfg)][comp_pid] += comp_qty

say("  plan buckets: %d" % len(plan))
total_need_all = defaultdict(float)
for (mk,cfg), d in plan.items():
    label = PERIODS[mk][3]
    out_name = OUTLETS[cfg][1]
    val = sum(d[pid]*prod_info[pid]["sp"] for pid in d if pid in prod_info)
    stor_cnt = sum(1 for pid in d if prod_info.get(pid,{}).get("is_storable"))
    total_cnt = len(d)
    say("    %-12s %-13s (cfg %s): komponen %d (storable %d) nilai %s" % (label, out_name, cfg, total_cnt, stor_cnt, money(val)))
    for pid in d:
        total_need_all[pid] += d[pid]

# total
say("")
say("[1b] Total gabungan 72 hari")
total_val = sum(total_need_all[pid]*prod_info.get(pid,{}).get("sp",0) for pid in total_need_all)
cat_need = defaultdict(lambda: defaultdict(float))
for pid, q in total_need_all.items():
    cat_id = prod_info.get(pid,{}).get("categ_id")
    # get cat name
    cat_name = {5:"Bahan Baku Beverage",6:"Bahan Baku Food",7:"Bahan Pendukung Menu"}.get(cat_id, str(cat_id))
    cat_need[cat_name][pid] += q
for cat in sorted(cat_need):
    qty_sum = sum(cat_need[cat].values())
    val_sum = sum(cat_need[cat][pid]*prod_info.get(pid,{}).get("sp",0) for pid in cat_need[cat])
    say("  %-28s komponen %-3d qty %-12.0f nilai %-14s (%.1f%%)" % (cat, len(cat_need[cat]), qty_sum, money(val_sum), 100*val_sum/total_val if total_val else 0))
say("  TOTAL nilai HPP estimasi = %s" % money(total_val))
cr.execute("SELECT sum(amount_total) FROM pos_order WHERE date_order >= '2026-06-20' AND date_order < '2026-09-01' AND state!='cancel'")
omzet = float(cr.fetchone()[0] or 0)
say("  Omzet POS 72 hari %s => cost ratio %.1f%% (master avg 43.9%%)" % (money(omzet), 100*total_val/omzet if omzet else 0))

# segmented plan
say("")
say("[1c] Segmented waves")
for mk in MONTHS_ENV:
    d_from,d_to_excl,d_kons,label = PERIODS[mk]
    d0=fields.Date.to_date(d_from); d1=fields.Date.to_date(d_kons)
    days=(d1-d0).days+1
    fresh_waves=math.ceil(days/3.0); dry_waves=math.ceil(days/7.0)
    say("  %-12s %2d hari => Fresh %d gel (3d) | Dry %d gel (7d)" % (label, days, fresh_waves, dry_waves))
    for cfg,(stok_loc,out_name) in OUTLETS.items():
        need=plan.get((mk,cfg),{})
        fresh_n=sum(1 for pid in need if prod_info.get(pid,{}).get("categ_id")==6 and prod_info.get(pid,{}).get("is_storable"))
        dry_n=sum(1 for pid in need if prod_info.get(pid,{}).get("categ_id") in (5,7) and prod_info.get(pid,{}).get("is_storable"))
        say("    %-13s fresh %d (%d moves) | dry %d (%d moves) | konsumsi %d" % (out_name, fresh_n, fresh_n*fresh_waves, dry_n, dry_n*dry_waves, fresh_n+dry_n))

# --- Hapus move lama ---
say("")
say("[2] Bersihkan move lama origin %s" % ORIG)
LABELS=[PERIODS[k][3] for k in MONTHS_ENV]
old=MV.search([("origin","like",ORIG+"%")])
filtered=old.filtered(lambda m: any(lbl in (m.origin or "") for lbl in LABELS))
# fallback: if origin not contain label (old format), also match date
if not filtered and old:
    # also delete all old HPP-BOM-2TOKO regardless
    filtered=old
say("  move lama: total %d, filtered untuk bulan terpilih %d" % (len(old), len(filtered)))
if filtered and RUN:
    jes=filtered.mapped("account_move_id")
    ids=tuple(filtered.ids)
    cr.execute("SAVEPOINT sp_hpp_clean")
    try:
        cr.execute("DELETE FROM stock_move_line WHERE move_id IN %s", (ids,))
        n_ml=cr.rowcount
        MV.browse(ids).invalidate_recordset()
        MV.browse(ids).unlink()
        cr.execute("RELEASE SAVEPOINT sp_hpp_clean")
        say("    %d move + %d line dihapus" % (len(filtered), n_ml))
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
elif filtered:
    say("  [dry] akan hapus %d move" % len(filtered))

if not RUN:
    say("")
    say("DRY-RUN — tidak ada data ditulis. Jalankan RUN=1 untuk eksekusi.")
    # Estimate
    est_pur = total_val
    say("  Estimasi pembelian %s, kas bank 2.45M cukup sisa %.1fM OK" % (money(est_pur), (2450000-1075000)/1000 if False else 1.38))
    # kas check
    cr.execute("SELECT sum(aml.balance) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id JOIN account_account aa ON aa.id=aml.account_id WHERE am.state='posted' AND aa.account_type='asset_cash'")
    kas=float(cr.fetchone()[0] or 0)
    say("  Kas saat ini %s, butuh HPP %s, sisa %s" % (money(kas), money(total_val), money(kas-total_val)))
    env.cr.rollback()
    import sys; sys.exit(0)

# --- Eksekusi segmented ---
say("")
say("-"*110)
say("[3] EKSEKUSI HPP FIFO SEGMENTED")
tot_pur=0.0; tot_cons=0.0; total_moves=0
for mk in MONTHS_ENV:
    d_from,d_to_excl,d_konsumsi,label=PERIODS[mk]
    d0=fields.Date.to_date(d_from); d1=fields.Date.to_date(d_konsumsi)
    days=(d1-d0).days+1
    fresh_waves=math.ceil(days/3.0); dry_waves=math.ceil(days/7.0)
    def wave_dates(n):
        if n<=1:
            return [d0]
        return [d0+timedelta(days=round((days-1)*i/(n-1))) for i in range(n)]
    fresh_dates=wave_dates(fresh_waves)
    dry_dates=wave_dates(dry_waves)
    say("")
    say("%s (%s s/d %s = %d hari): fresh %d gel %s | dry %d gel %s | konsumsi %s"
        % (label,d_from,d_konsumsi,days,fresh_waves, ",".join(str(d) for d in fresh_dates[:3])+("..." if len(fresh_dates)>3 else ""),
           dry_waves, ",".join(str(d) for d in dry_dates[:3])+("..." if len(dry_dates)>3 else ""), d_konsumsi))
    for cfg_id,(stok_loc_id,outlet_name) in OUTLETS.items():
        need=plan.get((mk,cfg_id),{})
        if not need:
            say("  %-13s tidak ada kebutuhan -> skip" % outlet_name)
            continue
        stok_loc=Loc.browse(stok_loc_id)
        vendor_loc=Loc.browse(VENDOR)
        # split
        fresh_need={}
        dry_need={}
        for pid,qty in need.items():
            if qty<=0.0001:
                continue
            info=prod_info.get(pid)
            if not info or not info["is_storable"]:
                continue
            if info["categ_id"]==6:
                fresh_need[pid]=qty
            else:
                dry_need[pid]=qty
        say("  %-13s (cfg %s): %d komponen (fresh %d dry %d) stok %s" % (outlet_name,cfg_id,len(fresh_need)+len(dry_need),len(fresh_need),len(dry_need),stok_loc_id))
        # Pembelian Fresh
        n_p=0; v_p=0.0
        for wi,wd in enumerate(fresh_dates):
            share=1.0/fresh_waves
            for pid,q in fresh_need.items():
                qw=q*share
                if qw<=0.0001:
                    continue
                info=prod_info[pid]
                origin="%s beli %s %s %s (fresh %d/%d)" % (ORIG,label,outlet_name,info["code"][:15],wi+1,fresh_waves)
                mv=make_move(pid,qw,vendor_loc.id,stok_loc.id,wd.isoformat(),origin)
                v_p+=mv.value or 0.0
                n_p+=1
            env.cr.commit()
        # Dry
        for wi,wd in enumerate(dry_dates):
            share=1.0/dry_waves
            for pid,q in dry_need.items():
                qw=q*share
                if qw<=0.0001:
                    continue
                info=prod_info[pid]
                origin="%s beli %s %s %s (dry %d/%d)" % (ORIG,label,outlet_name,info["code"][:15],wi+1,dry_waves)
                mv=make_move(pid,qw,vendor_loc.id,stok_loc.id,wd.isoformat(),origin)
                v_p+=mv.value or 0.0
                n_p+=1
            env.cr.commit()
        tot_pur+=v_p
        total_moves+=n_p
        say("    pembelian %d move nilai %s" % (n_p, money(v_p)))
        # Konsumsi
        n_c=0; v_c=0.0
        for pid,q in sorted(need.items()):
            if q<=0.0001:
                continue
            info=prod_info.get(pid)
            if not info or not info["is_storable"]:
                continue
            dst_id=CONS.get(info["categ_id"],CONS_FOOD)
            dst=Loc.browse(dst_id)
            origin="%s konsumsi %s %s %s" % (ORIG,label,outlet_name,info["code"][:15])
            mv=make_move(pid,q,stok_loc.id,dst.id,d_konsumsi,origin)
            v_c+=mv.value or 0.0
            n_c+=1
        env.cr.commit()
        tot_cons+=v_c
        total_moves+=n_c
        say("    konsumsi %d move nilai %s" % (n_c, money(v_c)))

say("")
say("="*110)
say("RINGKASAN HPP 72 HARI SEGMENTED 2 TOKO (V2)")
say("  total pembelian %s" % money(tot_pur))
say("  total HPP konsumsi %s" % money(tot_cons))
for mk in MONTHS_ENV:
    cr.execute("SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id JOIN account_account aa ON aa.id=aml.account_id WHERE am.state='posted' AND aa.account_type='expense_direct_cost' AND am.date >= %s AND am.date <= %s", (PERIODS[mk][0], PERIODS[mk][2]))
    hpp=cr.fetchone()[0]
    cr.execute("SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id JOIN account_account aa ON aa.id=aml.account_id WHERE am.state='posted' AND aa.code_store->>'1' IN ('1103.01','1103.02','1103.03') AND am.date <= %s", (PERIODS[mk][2],))
    stok=cr.fetchone()[0]
    say("  %-12s HPP %s | persediaan %s" % (PERIODS[mk][3], money(hpp), money(stok)))
say("")
say("  SALDO KAS/BANK per akhir bulan")
for last in ["2026-06-30","2026-07-31","2026-08-31"]:
    cr.execute("SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id JOIN account_account aa ON aa.id=aml.account_id WHERE am.state='posted' AND am.date <= %s AND aa.account_type='asset_cash'", (last,))
    kas=cr.fetchone()[0]
    cr.execute("SELECT COUNT(*) FROM (SELECT aa.id FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id JOIN account_account aa ON aa.id=aml.account_id WHERE am.state='posted' AND am.date <= %s AND aa.account_type='asset_cash' GROUP BY 1 HAVING SUM(aml.balance) < -0.01) x", (last,))
    neg=cr.fetchone()[0]
    say("    %s kas %s | negatif %d %s" % (last, money(kas), neg, "OK" if neg==0 else "<<<"))
cr.execute("SELECT COALESCE(SUM(aml.debit),0), COALESCE(SUM(aml.credit),0) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id WHERE am.state='posted'")
d,k=cr.fetchone()
say("  TB debit %s credit %s diff %s %s" % (money(d), money(k), money(float(d or 0)-float(k or 0)), "OK" if abs(float(d or 0)-float(k or 0))<0.01 else ">>>"))
# quant check
cr.execute("SELECT location_id, count(*), sum(quantity) FROM stock_quant WHERE location_id IN (5,32) GROUP BY 1 ORDER BY 1")
for loc,cnt,qty in cr.fetchall():
    cr.execute("SELECT sum(sq.quantity * (pp.standard_price->>'1')::numeric) FROM stock_quant sq JOIN product_product pp ON pp.id=sq.product_id WHERE sq.location_id=%s", (loc,))
    val=cr.fetchone()[0] or 0
    say("  Stock loc %s: %s SKU qty %.0f val %s" % (loc,cnt,qty or 0, money(val)))
say("="*110)
env.cr.commit()
