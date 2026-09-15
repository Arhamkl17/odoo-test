# -*- coding: utf-8 -*-
# margin_report_bulanan.py — Laporan margin menu bulanan (READ-ONLY) -> MD + JSON.
# Pembaruan dari cek_margin_profit.py (10 Sep):
#   - komisi platform 10% (rate final pasca-Fase 3; dulu 15%)
#   - cost non-storable sudah di-restore Fase 8 (69 menu); fallback BoM utk sisanya
#   - harga sudah x000+1000 utk 15 menu repriced (Fase 9a / S3)
# Metode sama dgn laporan 10 Sep: net = harga x (1-komisi); margin = (net-cost)/net;
# target net 25%; flag: RUGI / NAIK HARGA (<15%) / PANTAU (<25%) / OK / COST 0.
# Jalankan:
#   su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 \
#     --db_user odoo --db_password odoo" < scripts/margin_report_bulanan.py
import json
from collections import defaultdict

def p(*a):
    print(*a)

KOM = 0.10          # komisi platform (konservatif: diasumsikan semua penjualan lewat platform)
TARGET = 0.25       # target net margin
TGL = "2026-09-11"

def rows(sql, params=None):
    if params:
        env.cr.execute(sql, params)
    else:
        env.cr.execute(sql)
    return env.cr.fetchall()

Prod = env["product.product"].with_context(company_id=1)

# ---------- 1. Produk sale_ok ----------
prods = Prod.search([("sale_ok", "=", True), ("active", "=", True)])
data = {}
for pr in prods:
    data[pr.id] = {
        "name": pr.display_name, "price": pr.list_price or 0.0,
        "cost": pr.standard_price or 0.0, "src": "standard_price",
        "storable": bool(pr.product_tmpl_id.is_storable),
    }

# ---------- 2. Fallback BoM (komponen semua ber-cost) ----------
boms = rows("""
    SELECT b.id, COALESCE(b.product_id, 0), b.product_tmpl_id
    FROM mrp_bom b
""")
bom_of = {}
for bid, pid, tid in boms:
    bom_of[pid or tid] = bid          # product-specific menang atas template
env.cr.rollback()
bom_lines = defaultdict(list)
for bid, comp_id, qty in rows("SELECT bom_id, product_id, product_qty FROM mrp_bom_line"):
    bom_lines[bid].append((comp_id, qty))
env.cr.rollback()

def bom_cost(pid, tid):
    bid = bom_of.get(pid) or bom_of.get(tid)
    if not bid:
        return None
    total = 0.0
    for comp_id, qty in bom_lines.get(bid, []):
        c = comp_cost_cache.get(comp_id)
        if c is None:
            c = Prod.browse(comp_id).standard_price or 0.0
            comp_cost_cache[comp_id] = c
        if c <= 0:
            return None
        total += qty * c
    return total if total > 0 else None

comp_cost_cache = {}

for pid, d in data.items():
    if d["cost"] <= 0 and pid in bom_of:
        bc = bom_cost(pid, pid)
        if bc:
            d["cost"], d["src"] = bc, "bom"

# ---------- 3. Qty & revenue Agustus ----------
for pid, qty, rev in rows("""
    SELECT l.product_id, SUM(l.qty), SUM(l.price_subtotal)
    FROM pos_order_line l JOIN pos_order o ON o.id=l.order_id
    WHERE o.state IN ('done','invoiced')
      AND o.date_order >= '2026-08-01' AND o.date_order < '2026-09-01'
    GROUP BY 1
"""):
    if pid in data:
        data[pid]["qty_aug"] = float(qty)
        data[pid]["rev_aug"] = float(rev)
env.cr.rollback()

# ---------- 4. Hitung margin ----------
def margin(price, cost):
    if price <= 0 or cost <= 0:
        return None
    net = price * (1 - KOM)
    return (net - cost) / net

for pid, d in data.items():
    d["margin"] = margin(d["price"], d["cost"])
    if d["cost"] <= 0:
        d["flag"] = "COST 0"
    elif d["margin"] < 0:
        d["flag"] = "RUGI"
    elif d["margin"] < 0.15:
        d["flag"] = "NAIK HARGA"
    elif d["margin"] < TARGET:
        d["flag"] = "PANTAU"
    else:
        d["flag"] = "OK"
    # harga minimum utk net 25%
    d["min_price_25"] = round(d["cost"] / (1 - KOM - TARGET) / 1000 + 0.999) * 1000 \
        if d["cost"] > 0 else None

# ---------- 5. Tabel 15 menu repriced (before x777 -> after x000) ----------
REPRICED = json.load(open("backup_harga_sebelum_x000_S3.json"))
snap_cost = {r["id"]: r for r in json.load(open("cost_snapshot_pre_fase1_2026-09-11.json"))}

p("=" * 100)
p(f"A. 15 MENU REPRICED (x777 -> x000+1000, Fase 9a) — margin @ komisi {int(KOM*100)}%")
p("=" * 100)
p(f"{'MENU':<34}{'HARGA LAMA':>11}{'M LAMA':>8}{'HARGA BARU':>11}{'M BARU':>8}{'Δpp':>7}{'QTY AGU':>9}")
sec_a = []
for pid_s, rec in sorted(REPRICED.items(), key=lambda x: x[1]["name"]):
    pid = int(pid_s)
    old_price = rec["old_list_price"]
    d = data.get(pid)
    if not d:
        continue
    cost = d["cost"] or (snap_cost.get(pid, {}).get("standard_price") or {}).get("1") or 0
    m_old = margin(old_price, cost)
    m_new = d["margin"]
    dpp = (m_new - m_old) * 100 if (m_new is not None and m_old is not None) else None
    sec_a.append((d["name"], old_price, m_old, d["price"], m_new, dpp, d.get("qty_aug", 0)))
    mo_s = f"{m_old*100:>6.1f}%" if m_old is not None else "     -"
    mn_s = f"{m_new*100:>6.1f}%" if m_new is not None else "     -"
    dpp_s = f"{dpp:>+6.1f}" if dpp is not None else "      -"
    p(f"{d['name'][:34]:<34}{old_price:>11,.0f}{mo_s:>8}{d['price']:>11,.0f}{mn_s:>8}{dpp_s:>7}{d.get('qty_aug',0):>9,.0f}")

# ---------- 6. Ringkasan flag (MENU vs BAHAN BAKU dipisah) ----------
p()
p("=" * 100)
p("B. RINGKASAN — MENU (non-storable) vs BAHAN BAKU (storable, masih sale_ok)")
p("=" * 100)
counts_menu = defaultdict(int)
counts_bb = defaultdict(int)
n_bb = 0
for d in data.values():
    if d["storable"]:
        counts_bb[d["flag"]] += 1
        n_bb += 1
    else:
        counts_menu[d["flag"]] += 1
prev = {"RUGI": 9, "NAIK HARGA": 11, "PANTAU": 5, "OK": 105, "COST 0": 35}
p(f"   MENU (non-storable)      {'10 SEP':>8}{'SEKARANG':>10}")
for f in ("RUGI", "NAIK HARGA", "PANTAU", "OK", "COST 0"):
    p(f"   {f:<12}{prev.get(f,'-'):>8}{counts_menu.get(f,0):>10}")
n_menu = sum(counts_menu.values())
p(f"   TOTAL MENU               {sum(prev.values()):>8}{n_menu:>10}")
p(f"\n   BAHAN BAKU storable sale_ok: {n_bb} produk (flag RUGI di sini = artefak")
p(f"   harga satuan bahan (mis. BERAS Rp1), BUKAN menu rugi — guide step 2: matikan sale_ok)")
p(f"   flag bahan baku: {dict(counts_bb)}")

# ---------- 7. Tabel lengkap (sort margin asc) ----------
sold = [(d, pid) for pid, d in data.items() if d.get("qty_aug")]
unsold = [(d, pid) for pid, d in data.items() if not d.get("qty_aug")]
sold.sort(key=lambda x: (x[0]["margin"] is None, x[0]["margin"] if x[0]["margin"] is not None else 9))
unsold.sort(key=lambda x: x[0]["name"])

p()
p("C. DETAIL — produk TERJUAL Agustus (margin terendah dulu):")
p(f"   {'FLAG':<11}{'MENU':<34}{'HARGA':>9}{'COST':>9}{'SRC':<5}{'MARGIN':>8}{'QTY':>7}{'REV AGU':>12}")
md_b = []
for d, pid in sold:
    m = f"{d['margin']*100:>7.1f}%" if d["margin"] is not None else "      -"
    p(f"   {d['flag']:<11}{d['name'][:34]:<34}{d['price']:>9,.0f}{d['cost']:>9,.0f}{d['src'][:5]:<5}{m:>8}{d.get('qty_aug',0):>7,.0f}{d.get('rev_aug',0):>12,.0f}")
    md_b.append((d, pid))

# ---------- 8. Tulis MD ----------
def fmt_m(m):
    return f"{m*100:.1f}%" if m is not None else "-"

lines = []
lines.append(f"# LAPORAN MARGIN MENU — {TGL} (DB `Test1`, demo)\n")
lines.append(f"> Basis: harga master saat ini (15 menu sudah x000+1000 pasca Fase 9a), cost hasil restore Fase 8 + fallback BoM.")
lines.append(f"> Asumsi komisi platform **{int(KOM*100)}%** seragam (konservatif — penjualan walk-in sebenarnya 0% komisi). Target net margin {int(TARGET*100)}%.")
lines.append("> Read-only via odoo shell (`scripts/margin_report_bulanan.py`). Omzet POS Agustus tidak diubah Fase 9.\n")
lines.append("## Ringkasan\n")
lines.append("### Menu (non-storable)\n")
lines.append("| Flag | 10 Sep | Sekarang |")
lines.append("|---|---:|---:|")
for f in ("RUGI", "NAIK HARGA", "PANTAU", "OK", "COST 0"):
    lines.append(f"| {f} | {prev.get(f,'-')} | {counts_menu.get(f,0)} |")
lines.append(f"| TOTAL | {sum(prev.values())} | {n_menu} |")
lines.append("")
lines.append(f"### Bahan baku storable yang masih `sale_ok`: {n_bb} produk")
lines.append("")
lines.append(f"Flag bahan baku: {dict(counts_bb)}. Nilai \"RUGI\" di kelompok ini adalah artefak harga satuan bahan (mis. BERAS Rp 1, cost 15,30) — bukan menu rugi. Guide step #2 (matikan `sale_ok` bahan baku) belum dieksekusi.")
lines.append("")
lines.append("## A. 15 menu repriced (Fase 9a) — before → after\n")
lines.append("| Menu | Harga lama | M lama | Harga baru | M baru | Δpp | Qty Agu |")
lines.append("|---|---:|---:|---:|---:|---:|---:|")
for nm, op, mo, np_, mn, dpp, q in sec_a:
    lines.append(f"| {nm} | {op:,.0f} | {fmt_m(mo)} | {np_:,.0f} | {fmt_m(mn)} | {f'{dpp:+.1f}' if dpp is not None else '-'} | {q:,.0f} |")
lines.append("")
lines.append("## B. Produk terjual Agustus (margin terendah dulu)\n")
lines.append("| Flag | Menu | Harga | Cost | Sumber | Margin@10% | Qty | Rev Agustus |")
lines.append("|---|---|---:|---:|---|---:|---:|---:|")
for d, pid in md_b:
    lines.append(f"| {d['flag']} | {d['name']} | {d['price']:,.0f} | {d['cost']:,.0f} | {d['src']} | {fmt_m(d['margin'])} | {d.get('qty_aug',0):,.0f} | {d.get('rev_aug',0):,.0f} |")
lines.append("")
lines.append("## C. Produk COST 0 (blind spot — guide step 4–5 belum dilakukan)\n")
cost0 = sorted([d for d in data.values() if d["flag"] == "COST 0"], key=lambda x: x["name"])
lines.append(", ".join(d["name"] for d in cost0))
lines.append("")
lines.append("## Catatan metode\n")
lines.append("- Net = harga × 0,90; margin = (net − cost)/net — metodologi sama dgn laporan 10 Sep (`scripts/laporan_margin_profit.md`), komisi di-update 15% → 10%.")
lines.append("- Sumber cost: `standard_price` (Fase 8 restore utk 69 menu non-storable); fallback = jumlah komponen BoM; sisanya COST 0 (37 menu tanpa BoM/cost).")
lines.append("- Komisi seragam 10% = skenario terburuk; margin riil per menu lebih tinggi karena ±65% omzet datang dari walk-in (0% komisi).")
lines.append("- Markup platform +15% (Fase 9b) belum direfleksikan per-menu di sini — omzet POS Agustus asli dipertahankan utk basis perbandingan.")
with open("laporan_margin_menu_2026-09-11.md", "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

json_rows = [{"id": pid, **{k: v for k, v in d.items()}} for pid, d in sorted(data.items())]
with open("margin_report_2026-09-11.json", "w", encoding="utf-8") as f:
    json.dump(json_rows, f, indent=2, ensure_ascii=False)

p()
p("Artifacts: laporan_margin_menu_2026-09-11.md + margin_report_2026-09-11.json")
p("DONE margin_report_bulanan — read only.")
