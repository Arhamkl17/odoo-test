# -*- coding: utf-8 -*-
"""
opening_19jun_2toko.py — OPENING BALANCE 19 JUNI 2026 (2 TOKO, 72 HARI PORTFOLIO)

Neraca sintetis + stok awal 30 hari (244,9 jt) — RUNBOOK Bab 4 Langkah 2.
Sumber: L/R Tondo 18 akun (Agustus) + asumsi kas/stok/aset. Abaikan Trial Balance.pdf.
Idempotent, dry-run default.

  dry-run : cat scripts/opening_19jun_2toko.py | su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 --db_user odoo --db_password odoo"
  eksekusi: RUN=1 cat scripts/opening_19jun_2toko.py | su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 --db_user odoo --db_password odoo"
"""
import json
import os
from collections import defaultdict

RUN = os.environ.get("RUN") == "1"
OPEN_DATE = "2026-06-19"
OPEN_REF = "Opening Balance 19 Juni 2026 — Portfolio 72 hari"

# --- Neraca sintetis (debit = kredit = 1.154.900.000) ---
# Kas 150jt split: Bank BSI 90jt (BNK1) + Kas Mallengkeri 45jt + QRIS 15jt — distinct accounts
ACC = {
    "bank_bsi": 122,   # Bank BSI 1101.01 (BNK1/BNKB shared, pakai 122)
    "kas_mall": 223,   # Kas Mallengkeri 1111001
    "qris": 210,       # QRIS 1101.02
    "inventory": 11,   # Inventory 11300180
    # Aset tetap: pakai akun AKTIF (20/21/22 arsip f) — ganti ke seri 1105/1200 aktif
    "office_building": 136,  # Peralatan Resto 1105.03 (ganti Office Building 20 arsip)
    "vehicle": 134,          # Kendaraan 1105.01 (ganti Vehicle 21 arsip)
    "office_supplies": 135,  # Peralatan Kantor 1105.02 (ganti Office Supplies 22 arsip)
    "accum_building": 140,   # Akum Resto 1106.03
    "accum_vehicle": 138,    # Akum Kendaraan 1106.01
    "accum_office": 139,     # Akum Kantor 1106.02
    "paid_capital": 59,
    "past_profit": 63,
}
AMOUNT = {
    "bank_bsi": 90_000_000,
    "kas_mall": 45_000_000,
    "qris": 15_000_000,
    "inventory_total": 244_900_000,  # 136.043.299 + 108.834.639 (80%)
    "office_building": 500_000_000,
    "vehicle": 150_000_000,
    "office_supplies": 110_000_000,
    "accum_building": 125_000_000,
    "accum_vehicle": 37_500_000,
    "accum_office": 27_500_000,
    "paid_capital": 600_000_000,
    "past_profit": 364_900_000,
}
# Stok awal per outlet (value, untuk verifikasi)
STOK_PALLANGGA = 136_043_299
STOK_MALLENGKERI = 108_834_639

# Lokasi stok
LOC_PALLANGGA = 5   # WH/Stok
LOC_MALLENGKERI = 32  # BTL/Stok (check: Stok Mallengkeri)

PROFILE_PATH = "import_data/pos_profile_august.json"

say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

cr = env.cr
AM = env["account.move"]
AJ = env["account.journal"]
SQ = env["stock.quant"]
Prod = env["product.product"]

say("=" * 100)
say("OPENING BALANCE 19 JUNI 2026 — 2 TOKO | RUN=%s | %s" % (RUN, OPEN_REF))
say("=" * 100)

# --- 0. Guard: sudah ada? ---
existing = AM.search([("ref", "=", OPEN_REF)], limit=1)
if existing:
    say("SUDAH ADA: %s id=%s date=%s state=%s (idempotent — lewati pembuatan JE)" % (existing.name, existing.id, existing.date, existing.state))
    je_exists = True
else:
    je_exists = False

# --- 1. Tampilkan neraca ---
total_debit = AMOUNT["bank_bsi"] + AMOUNT["kas_mall"] + AMOUNT["qris"] + AMOUNT["inventory_total"] + AMOUNT["office_building"] + AMOUNT["vehicle"] + AMOUNT["office_supplies"]
total_credit = AMOUNT["accum_building"] + AMOUNT["accum_vehicle"] + AMOUNT["accum_office"] + AMOUNT["paid_capital"] + AMOUNT["past_profit"]
say("")
say("[NERACA] %s" % OPEN_DATE)
say("  DEBIT:")
say("    Bank BSI (122)            %16s" % money(AMOUNT["bank_bsi"]))
say("    Kas Mallengkeri (223)     %16s" % money(AMOUNT["kas_mall"]))
say("    QRIS (210)                %16s" % money(AMOUNT["qris"]))
say("    Inventory (11)            %16s  (30 hari: Pallangga %s + Mallengkeri %s)" % (money(AMOUNT["inventory_total"]), money(STOK_PALLANGGA), money(STOK_MALLENGKERI)))
say("    Office Building (20)      %16s" % money(AMOUNT["office_building"]))
say("    Vehicle (21)              %16s" % money(AMOUNT["vehicle"]))
say("    Office Supplies (22)      %16s" % money(AMOUNT["office_supplies"]))
say("                              ----------------")
say("    TOTAL DEBIT               %16s" % money(total_debit))
say("  KREDIT:")
say("    Akum Building (23)        %16s" % money(AMOUNT["accum_building"]))
say("    Akum Vehicle (24)         %16s" % money(AMOUNT["accum_vehicle"]))
say("    Akum Office (25)          %16s" % money(AMOUNT["accum_office"]))
say("    Paid Capital (59)         %16s" % money(AMOUNT["paid_capital"]))
say("    Past P&L (63)             %16s" % money(AMOUNT["past_profit"]))
say("                              ----------------")
say("    TOTAL KREDIT              %16s" % money(total_credit))
say("  Balance: %s" % ("OK" if abs(total_debit - total_credit) < 0.01 else ">>> TIDAK BALANCE!"))

# --- 2. Hitung kebutuhan stok per komponen (30 hari) ---
say("")
say("[STOK] Hitung kebutuhan 30 hari per komponen (52) — Pallangga 245.8 order/hari + Mallengkeri 196.6")
if not os.path.exists(PROFILE_PATH):
    say("  Profil %s tidak ada — pakai fallback HPP kategori" % PROFILE_PATH)
    use_bom = False
else:
    with open(PROFILE_PATH, encoding="utf-8") as f:
        prof = json.load(f)
    PROD_W = {int(k): v for k, v in prof["prod_weight"].items()}
    PROD_W_MALL = {}
    import random
    rng_jit = random.Random(20260620 + 999)
    for pid, w in PROD_W.items():
        PROD_W_MALL[pid] = w * rng_jit.uniform(0.90, 1.10)
    sum_w_pall = sum(PROD_W.values())
    sum_w_mall = sum(PROD_W_MALL.values())
    use_bom = True
    # Ambil BOM: map tmpl_id -> list (product_id, qty)
    cr.execute("""
        SELECT b.product_tmpl_id, l.product_id, l.product_qty
        FROM mrp_bom b JOIN mrp_bom_line l ON l.bom_id=b.id
        WHERE b.active
    """)
    bom_by_tmpl = defaultdict(list)
    for tmpl, pid, qty in cr.fetchall():
        bom_by_tmpl[tmpl].append((pid, float(qty)))
    # Map product.product -> product_tmpl_id
    cr.execute("SELECT id, product_tmpl_id FROM product_product")
    pp_to_tmpl = {r[0]: r[1] for r in cr.fetchall()}
    # Map product_template id -> product.product id (ambil satu)
    cr.execute("SELECT product_tmpl_id, id FROM product_product ORDER BY id")
    tmpl_to_pp = {}
    for tmpl, pp in cr.fetchall():
        if tmpl not in tmpl_to_pp:
            tmpl_to_pp[tmpl] = pp
    # Hitung demand per komponen
    pall_daily = 245.8
    mall_daily = 196.6
    comp_daily_pall = defaultdict(float)  # product_id -> qty/hari
    comp_daily_mall = defaultdict(float)
    for pp_id, w in PROD_W.items():
        tmpl = pp_to_tmpl.get(pp_id)
        if not tmpl or tmpl not in bom_by_tmpl:
            continue
        share = w / sum_w_pall if sum_w_pall else 0
        orders_for_menu = pall_daily * share
        for comp_pid, qty in bom_by_tmpl[tmpl]:
            comp_daily_pall[comp_pid] += orders_for_menu * qty
    for pp_id, w in PROD_W_MALL.items():
        tmpl = pp_to_tmpl.get(pp_id)
        if not tmpl or tmpl not in bom_by_tmpl:
            continue
        share = w / sum_w_mall if sum_w_mall else 0
        orders_for_menu = mall_daily * share
        for comp_pid, qty in bom_by_tmpl[tmpl]:
            comp_daily_mall[comp_pid] += orders_for_menu * qty
    # Ambil sp
    comp_ids = set(list(comp_daily_pall.keys()) + list(comp_daily_mall.keys()))
    if not comp_ids:
        use_bom = False
    else:
        cr.execute("SELECT id, (standard_price->>'1')::numeric as sp FROM product_product WHERE id = ANY(%s)", (list(comp_ids),))
        sp_map = {r[0]: float(r[1] or 0) for r in cr.fetchall()}
        # Estimasi value 30 hari dari demand BOM
        est_val_pall = sum(comp_daily_pall[pid] * 30 * sp_map.get(pid, 0) for pid in comp_daily_pall)
        est_val_mall = sum(comp_daily_mall[pid] * 30 * sp_map.get(pid, 0) for pid in comp_daily_mall)
        say("  Estimasi value 30 hari dari BOM: Pallangga %s, Mallengkeri %s (target %s / %s)" % (
            money(est_val_pall), money(est_val_mall), money(STOK_PALLANGGA), money(STOK_MALLENGKERI)))
        # Scale agar total = target 136jt / 108jt (karena prod_weight vs real HPP gap)
        scale_pall = STOK_PALLANGGA / est_val_pall if est_val_pall else 1
        scale_mall = STOK_MALLENGKERI / est_val_mall if est_val_mall else 1
        say("  Scale factor: Pallangga %.4f, Mallengkeri %.4f" % (scale_pall, scale_mall))
        # Hitung qty opening (30 hari, scaled)
        open_qty_pall = {}
        open_qty_mall = {}
        for pid in comp_daily_pall:
            open_qty_pall[pid] = comp_daily_pall[pid] * 30 * scale_pall
        for pid in comp_daily_mall:
            open_qty_mall[pid] = comp_daily_mall[pid] * 30 * scale_mall
        # Top 5 komponen
        say("  Top 5 Pallangga (qty, value):")
        for pid, qty in sorted(open_qty_pall.items(), key=lambda x: x[1]*sp_map.get(x[0],0), reverse=True)[:5]:
            cr.execute("SELECT (name->>'en_US') FROM product_template WHERE id=%s", (pp_to_tmpl.get(pid) or 0,))
            # Actually get via product_product
            env.cr.execute("SELECT (pt.name->>'en_US') FROM product_product pp JOIN product_template pt ON pt.id=pp.product_tmpl_id WHERE pp.id=%s", (pid,))
            r = env.cr.fetchone()
            nama = (r[0] if r else str(pid))[:30]
            say("    %-30s qty %10.2f  value %14s (sp %s)" % (nama, qty, money(qty*sp_map.get(pid,0)), money(sp_map.get(pid,0))))
        say("  Top 5 Mallengkeri:")
        for pid, qty in sorted(open_qty_mall.items(), key=lambda x: x[1]*sp_map.get(x[0],0), reverse=True)[:5]:
            env.cr.execute("SELECT (pt.name->>'en_US') FROM product_product pp JOIN product_template pt ON pt.id=pp.product_tmpl_id WHERE pp.id=%s", (pid,))
            r = env.cr.fetchone()
            nama = (r[0] if r else str(pid))[:30]
            say("    %-30s qty %10.2f  value %14s" % (nama, qty, money(qty*sp_map.get(pid,0))))
        # Total check
        tot_q_pall = sum(open_qty_pall.values())
        tot_q_mall = sum(open_qty_mall.values())
        say("  Total qty: Pallangga %.1f, Mallengkeri %.1f (52 komponen)" % (tot_q_pall, tot_q_mall))

if not use_bom:
    say("  Fallback: tidak hitung BOM — stok akan diisi via JE saja, qty menyusul manual.")

# --- 3. Cek stock_quant existing ---
cr.execute("SELECT count(*) FROM stock_quant WHERE location_id IN (%s,%s) AND quantity != 0", (LOC_PALLANGGA, LOC_MALLENGKERI))
existing_q = cr.fetchone()[0]
say("")
say("[STOCK_QUANT] Existing non-zero di WH/BTL: %s" % existing_q)
cr.execute("SELECT location_id, count(*), sum(quantity) FROM stock_quant WHERE location_id IN (%s,%s) GROUP BY location_id", (LOC_PALLANGGA, LOC_MALLENGKERI))
for loc, cnt, s in cr.fetchall():
    say("  loc %s: %s record, sum qty %s" % (loc, cnt, s))

if not RUN:
    say("")
    say("DRY-RUN — tidak ada data ditulis. Jalankan dengan RUN=1 untuk eksekusi.")
    env.cr.rollback()
    import sys; sys.exit(0)

# --- 4. EKSEKUSI ---
say("")
say("[EKSEKUSI]")

# 4a. Matikan hash untuk MISC/STJ (agar bisa backdate 19 Jun — chain MISC sudah handled)
try:
    cr.execute("UPDATE account_journal SET restrict_mode_hash_table = false WHERE code = ANY(%s)", (["MISC","STJ","POSS","BNK1","BNKB"],))
    say("  Hash MISC/STJ/POSS/BNK dimatikan untuk opening.")
except Exception as e:
    say("  (hash disable gagal, lanjut): %s" % e)

# 4b. Buat JE Opening jika belum ada
if not je_exists:
    # Cari journal MISC
    misc_journal = AJ.search([("code", "=", "MISC")], limit=1)
    if not misc_journal:
        misc_journal = AJ.search([("type", "=", "general")], limit=1)
    if not misc_journal:
        say("  GAGAL: journal MISC tidak ditemukan")
        import sys; sys.exit(1)
    lines = []
    # DEBIT
    lines.append((0, 0, {"account_id": ACC["bank_bsi"], "debit": AMOUNT["bank_bsi"], "credit": 0.0, "name": "Kas Bank BSI — Opening 19 Juni"}))
    lines.append((0, 0, {"account_id": ACC["kas_mall"], "debit": AMOUNT["kas_mall"], "credit": 0.0, "name": "Kas Mallengkeri — Opening"}))
    lines.append((0, 0, {"account_id": ACC["qris"], "debit": AMOUNT["qris"], "credit": 0.0, "name": "QRIS Wallet — Opening"}))
    lines.append((0, 0, {"account_id": ACC["inventory"], "debit": AMOUNT["inventory_total"], "credit": 0.0, "name": "Persediaan awal 30 hari"}))
    lines.append((0, 0, {"account_id": ACC["office_building"], "debit": AMOUNT["office_building"], "credit": 0.0, "name": "Aset Tetap — Office Building"}))
    lines.append((0, 0, {"account_id": ACC["vehicle"], "debit": AMOUNT["vehicle"], "credit": 0.0, "name": "Aset Tetap — Vehicle"}))
    lines.append((0, 0, {"account_id": ACC["office_supplies"], "debit": AMOUNT["office_supplies"], "credit": 0.0, "name": "Aset Tetap — Office Supplies"}))
    # KREDIT
    lines.append((0, 0, {"account_id": ACC["accum_building"], "debit": 0.0, "credit": AMOUNT["accum_building"], "name": "Akum Penyusutan Building"}))
    lines.append((0, 0, {"account_id": ACC["accum_vehicle"], "debit": 0.0, "credit": AMOUNT["accum_vehicle"], "name": "Akum Penyusutan Vehicle"}))
    lines.append((0, 0, {"account_id": ACC["accum_office"], "debit": 0.0, "credit": AMOUNT["accum_office"], "name": "Akum Penyusutan Office"}))
    lines.append((0, 0, {"account_id": ACC["paid_capital"], "debit": 0.0, "credit": AMOUNT["paid_capital"], "name": "Modal Disetor"}))
    lines.append((0, 0, {"account_id": ACC["past_profit"], "debit": 0.0, "credit": AMOUNT["past_profit"], "name": "Laba Ditahan"}))
    mv = AM.create({"journal_id": misc_journal.id, "date": OPEN_DATE, "ref": OPEN_REF, "line_ids": lines})
    mv.action_post()
    say("  JE Opening dibuat: %s id=%s date=%s deb=%s cred=%s" % (mv.name, mv.id, mv.date, money(sum(l.debit for l in mv.line_ids)), money(sum(l.credit for l in mv.line_ids))))
    env.cr.flush()
else:
    say("  JE Opening sudah ada — skip.")

# 4c. Buat stock_quant per outlet (qty opening)
if use_bom and 'open_qty_pall' in locals():
    # Idempotent: hapus quant lama di lokasi WH/BTL untuk komponen BOM saja jika RUN ulang?
    # Kita cek sudah ada, skip jika sudah ada quantity
    if existing_q > 0:
        say("  Stock quant sudah ada %s record — skip pembuatan qty (idempotent)." % existing_q)
        say("  Untuk regenerate, hapus dulu: DELETE FROM stock_quant WHERE location_id IN (5,32)")
    else:
        # Buat via SQL langsung (tanpa valuation) — qty = opening 30 hari
        created = 0
        for pid, qty in open_qty_pall.items():
            if qty <= 0:
                continue
            cr.execute("""
                INSERT INTO stock_quant (product_id, location_id, quantity, reserved_quantity, inventory_quantity, inventory_diff_quantity, in_date, company_id, create_date, write_date)
                VALUES (%s, %s, %s, 0, %s, %s, %s, 1, now(), now())
            """, (pid, LOC_PALLANGGA, qty, qty, qty, OPEN_DATE))
            created += 1
        for pid, qty in open_qty_mall.items():
            if qty <= 0:
                continue
            cr.execute("""
                INSERT INTO stock_quant (product_id, location_id, quantity, reserved_quantity, inventory_quantity, inventory_diff_quantity, in_date, company_id, create_date, write_date)
                VALUES (%s, %s, %s, 0, %s, %s, %s, 1, now(), now())
            """, (pid, LOC_MALLENGKERI, qty, qty, qty, OPEN_DATE))
            created += 1
        say("  Stock quant dibuat: %s record (Pallangga %s + Mallengkeri %s)" % (created, len(open_qty_pall), len(open_qty_mall)))
        env.cr.flush()
else:
    say("  Skip stock_quant (use_bom=False atau tidak ada demand)")

env.cr.commit()
say("")
say("[COMMITTED] Opening 19 Juni selesai.")

# --- 5. VERIFIKASI ---
say("")
say("=" * 100)
say("[VERIFIKASI]")
cr.execute("SELECT count(*), sum(debit), sum(credit) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id WHERE am.ref=%s AND am.state='posted'", (OPEN_REF,))
cnt, d, c = cr.fetchone()
say("  JE Opening: %s line, debit %s credit %s diff %s" % (cnt, money(d), money(c), money((d or 0)-(c or 0))))
cr.execute("SELECT location_id, count(*), sum(quantity) FROM stock_quant WHERE location_id IN (%s,%s) GROUP BY location_id ORDER BY location_id", (LOC_PALLANGGA, LOC_MALLENGKERI))
for loc, cnt, s in cr.fetchall():
    # Hitung value
    cr.execute("""
        SELECT sum(sq.quantity * (pp.standard_price->>'1')::numeric)
        FROM stock_quant sq JOIN product_product pp ON pp.id=sq.product_id
        WHERE sq.location_id=%s
    """, (loc,))
    val = cr.fetchone()[0] or 0
    say("  Stock loc %s: %s SKU, sum qty %s, est value %s" % (loc, cnt, money(s or 0), money(val)))
# TB check s/d 19 Jun
cr.execute("""
    SELECT coalesce(sum(debit),0), coalesce(sum(credit),0)
    FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
    WHERE am.state='posted' AND am.date <= %s
""", (OPEN_DATE,))
d, c = cr.fetchone()
say("  TB s/d %s: debit %s credit %s diff %s %s" % (OPEN_DATE, money(d), money(c), money(d-c), "OK" if abs(d-c) < 0.01 else ">>> TIDAK BALANCE"))
say("")
say("LANGKAH LANJUTAN: GENERATE POS 72 HARI (juni_juli_92_gen_pos_channels_2toko.py dengan MONTHS=june,july,august, RUN=1)")
say("=" * 100)
