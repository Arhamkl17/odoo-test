# -*- coding: utf-8 -*-
"""
juni_juli_77_r3_audit.py — AUDIT R3: apakah harga master ikut TURUN tanpa dasar klien? (READ-ONLY)

Sumber pembanding `list_price` SEBELUM R3: /tmp/pre_r3.csv (dari dump
backup_pre_R3_harga_2026-09-13.dump, tabel product_template, di DB sementara).

Klasifikasi tiap produk POS yang punya penjualan Jun-Agu:
  A. harga klien ada  -> perubahan R3 terverifikasi (AMAN)
  B. harga klien TIDAK ada -> R3 memakai harga POS generator (PERLU DITINJAU)
     di sini juga dicek: apakah harga hasil R3 lebih rendah dari SEBELUM R3

  su odoo ... < scripts/juni_juli_77_r3_audit.py
"""
import csv
import io

PRE = {}
with io.open("/tmp/pre_r3.csv", encoding="utf-8") as f:
    for ln in f:
        p = ln.rstrip("\n").split("|")
        if len(p) >= 3:
            try:
                PRE[int(p[0])] = float(p[2])
            except ValueError:
                pass

KL = {}
with io.open("import_data/csv/06_price_update.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        nm = (r.get("Nama") or "").strip().upper()
        if nm:
            try:
                KL[nm] = float((r.get("Harga Jual") or "0").strip() or 0)
            except ValueError:
                KL[nm] = 0.0

cr = env.cr
Prod = env["product.product"]
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

cr.execute("""
    SELECT pol.product_id, SUM(pol.qty), SUM(pol.price_subtotal)
      FROM pos_order_line pol JOIN pos_order po ON po.id=pol.order_id
     WHERE po.state IN ('paid','done','invoiced')
       AND po.date_order >= '2026-06-01' AND po.date_order < '2026-09-01'
     GROUP BY 1""")
sales = {int(p): (float(q or 0), float(r or 0)) for p, q, r in cr.fetchall() if p}

rows = []
for p in Prod.search([("sale_ok", "=", True), ("available_in_pos", "=", True)]):
    t = p.product_tmpl_id
    nm = (t.display_name or "").strip()
    nmu = nm.upper()
    if p.id not in sales:
        continue
    now = float(t.list_price or 0)
    pre = PRE.get(t.id)
    kp = KL.get(nmu)
    if pre is None:
        continue
    if abs(pre - now) < 0.005:
        continue                      # tidak diubah R3
    gap = now - pre
    ratio = (pre / now) if now else 0
    stok = "PERLU DITINJAU"
    if kp and abs(kp - now) < 0.005:
        stok = "AMAN (klien)"
    elif kp and abs(kp - pre) < 0.005:
        stok = "R3 SALAH? (pre==klien)"
    rows.append((stok, nm, p.id, pre, now, kp, gap, ratio, sales[p.id]))

rows.sort(key=lambda r: (r[0] != "AMAN (klien)", r[6]))
say("=" * 126)
say("AUDIT R3 — %d produk berubah | AMAN %d | PERLU DITINJAU %d" % (
    len(rows), len([r for r in rows if r[0].startswith("AMAN")]),
    len([r for r in rows if not r[0].startswith("AMAN")])))
say("=" * 126)
say("%-22s %-46s %9s %9s %9s %8s %7s %10s" % (
    "status", "menu", "pra-R3", "kini", "harga klien", "selisih", "rasio", "omzet 3bln"))
say("-" * 126)
for stok, nm, pid, pre, now, kp, gap, ratio, (q, rev) in rows:
    say("%-22s %-46s %9s %9s %9s %8s %6.2fx %10s" % (
        stok, nm[:46], money(pre), money(now), money(kp) if kp else "—",
        money(gap), ratio, money(rev)))

belum = [r for r in rows if not r[0].startswith("AMAN")]
say("")
say("=" * 126)
say("RINGKASAN BARIS 'PERLU DITINJAU' — master diturunkan tanpa dasar harga klien")
say("=" * 126)
tot_rev = sum(r[8][1] for r in belum)
pot = sum(r[8][0] * (r[3] - r[4]) for r in belum)   # pakai harga PRA-R3
say("produk      : %d" % len(belum))
say("omzet 3 bln : %s" % money(tot_rev))
say("bila harga pra-R3 dipakai, omzet naik %s" % money(pot))
say("")
say("%-46s %9s %9s %8s %10s" % ("menu", "pra-R3", "kini", "selisih", "omzet 3bln"))
for stok, nm, pid, pre, now, kp, gap, ratio, (q, rev) in belum[:40]:
    say("%-46s %9s %9s %8s %10s" % (nm[:46], money(pre), money(now), money(gap), money(rev)))

env.cr.rollback()
