# -*- coding: utf-8 -*-
"""
juni_juli_63_align_master_price.py — R3: SELARASKAN HARGA MASTER (Jun/Juli/Agu 2026).

DASAR KEPUTUSAN (lihat JUNI_JULI_DATA-spec.md §21.3)
  Dibandingkan tiga sumber: harga KLIEN (06_price_update.csv), harga MASTER, harga POS nyata.
  Hasil pada 35 produk yang ada di daftar harga klien:
      master == harga klien : 28 produk
      master  > harga klien :  7 produk   (dinaikkan agent 11 Sep, +60% s/d +133%)
      master  < harga klien :  0 produk
      harga POS == klien    : 26 produk   (sisanya tidak dijual eceran)
  => daftar harga KLIEN dan harga POS sepakat; yang menyimpang adalah MASTER.

ATURAN YANG DIPAKAI
  1. Produk yang PUNYA penjualan Jun-Agu  -> master disetel = harga efektif POS.
     (harga itu sendiri sudah terverifikasi sama dengan harga klien)
  2. Produk TANPA penjualan tapi ada di daftar harga klien -> master = harga klien.
  3. Produk tanpa penjualan & tanpa harga klien -> TIDAK disentuh.
  4. Bila harga POS BERBEDA dari harga klien -> DILAPORKAN & DILEWATI (butuh keputusan).

DAMPAK LEDGER: NOL. Skrip ini hanya mengubah `list_price` (daftar harga), tidak menyentuh
`pos_order_line`, `account_move`, maupun stok. Omzet & laba 3 bulan tidak berubah.

  dry-run : su odoo ... < scripts/juni_juli_63_align_master_price.py
  eksekusi: su odoo ... " RUN=1 odoo shell ..." < scripts/juni_juli_63_align_master_price.py
"""
import csv
import io
import os

RUN = os.environ.get("RUN") == "1"
CSV_PATH = "import_data/csv/06_price_update.csv"
cr = env.cr
Prod = env["product.product"]
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))


def klien_prices():
    d = {}
    with io.open(CSV_PATH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            nm = (r.get("Nama") or "").strip().upper()
            if not nm:
                continue
            try:
                d[nm] = float((r.get("Harga Jual") or "0").strip() or 0)
            except ValueError:
                d[nm] = 0.0
    return d


KL = klien_prices()

# harga efektif POS per produk
cr.execute("""
    SELECT pol.product_id, MIN(pol.price_unit), MAX(pol.price_unit), SUM(pol.qty)
      FROM pos_order_line pol JOIN pos_order po ON po.id=pol.order_id
     WHERE po.state IN ('paid','done','invoiced')
       AND po.date_order >= '2026-06-01' AND po.date_order < '2026-09-01'
     GROUP BY 1""")
pos = {}
for pid, mn, mx, q in cr.fetchall():
    if pid:
        pos[int(pid)] = (float(mn or 0), float(mx or 0), float(q or 0))

say("=" * 118)
say("R3 — SELARASKAN HARGA MASTER  |  RUN=%s" % RUN)
say("=" * 118)

plans = []          # (template, pid, nama, lama, baru, alasan, qty)
skip = []
for p in Prod.search([("sale_ok", "=", True), ("available_in_pos", "=", True)]):
    tmpl = p.product_tmpl_id
    nm = (tmpl.display_name or "").upper().strip()
    old = float(tmpl.list_price or 0)
    mn, mx, qty = pos.get(p.id, (0.0, 0.0, 0.0))
    kp = KL.get(nm)

    if qty > 0 and mn > 0:
        if abs(mx - mn) > 0.005:
            skip.append((p.id, tmpl.display_name, old, None,
                         "harga POS beragam (%.0f s/d %.0f) — perlu keputusan" % (mn, mx)))
            continue
        if kp and abs(kp - mn) > 0.005:
            skip.append((p.id, tmpl.display_name, old, kp,
                         "harga POS (%.0f) != harga klien (%.0f)" % (mn, kp)))
            continue
        if abs(old - mn) > 0.005:
            why = "harga POS nyata"
            if kp:
                why += " (= harga klien)"
            plans.append((tmpl, p.id, tmpl.display_name, old, mn, why, qty))
        continue

    if kp and abs(old - kp) > 0.005:
        plans.append((tmpl, p.id, tmpl.display_name, old, kp, "daftar harga klien", 0.0))

plans.sort(key=lambda x: -abs(x[3] - x[4]))
say("")
say("A. AKAN DIUBAH — %d produk" % len(plans))
say("%-6s %-48s %9s %9s %9s %8s  %s" % (
    "pid", "menu", "lama", "baru", "selisih", "qty", "alasan"))
say("-" * 118)
for tmpl, pid, nama, old, new, why, qty in plans:
    say("%-6d %-48s %9s %9s %8.1f%% %8.0f  %s" % (
        pid, nama[:48], money(old), money(new),
        ((new - old) / old * 100) if old else 0, qty, why))

say("")
say("B. DILEWATI — %d produk (butuh keputusan / tidak bisa ditentukan)" % len(skip))
for pid, nama, old, kp, why in skip[:30]:
    say("   pid=%-5d %-46s master %-8s %s" % (pid, nama[:46], money(old), why))
if len(skip) > 30:
    say("   ... dan %d lainnya" % (len(skip) - 30))

naik = len([x for x in plans if x[4] > x[3]])
turun = len([x for x in plans if x[4] < x[3]])
say("")
say("RINGKASAN: %d naik, %d turun, %d dilewati" % (naik, turun, len(skip)))
say("Dampak ledger: NOL (hanya list_price; pos_order_line & account_move tidak disentuh).")

if RUN:
    say("")
    say("C. TULIS")
    n = 0
    for tmpl, pid, nama, old, new, why, qty in plans:
        tmpl.write({"list_price": new})
        n += 1
    env.cr.flush()
    bad = 0
    for tmpl, pid, nama, old, new, why, qty in plans:
        got = float(tmpl.list_price or 0)
        if abs(got - new) > 0.005:
            bad += 1
            say("   MISMATCH pid=%s %s: harap %s dapat %s" % (pid, nama[:40], money(new), money(got)))
    if bad:
        env.cr.rollback()
        say("   %d mismatch -> ROLLBACK" % bad)
    else:
        env.cr.commit()
        say("   %d harga master diperbarui. COMMITTED." % n)
else:
    env.cr.rollback()
    say("")
    say("DRY-RUN — tidak ada perubahan. Jalankan dengan RUN=1 untuk menulis.")
say("=" * 118)
