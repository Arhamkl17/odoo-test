# -*- coding: utf-8 -*-
"""
perbaikan_master_02_harga_platform.py — PERBAIKI HARGA PLATFORM YANG MENYIMPANG (13 Sep 2026).

LATAR BELAKANG
  Hasil audit `AUDIT_MASTER_DATA_2026-09-13.md` §1 menemukan **2 produk** yang harga
  item pricelist "Harga Platform Online" (id 5) tidak sesuai rumus yang ditetapkan di
  `scripts/juni_juli_112_harga_tunggal_preset.py`:

      harga platform = ceil500(harga normal × 1,10)

  | Produk                | tmpl | Normal | Platform sekarang | Seharusnya |
  |-----------------------|------|-------:|------------------:|-----------:|
  | GEPREK MOZAA          |  571 | 25.000 |            28.000 |     27.500 |
  | PAKET GEPREK BAKAR    |  599 | 50.000 |            55.500 |     55.000 |

  Keduanya **terlalu mahal** (di atas +10%), jadi bukan kasus markup hilang — hanya
  pembulatan yang salah. Produk lain + kategori Services tidak disentuh.

YANG DILAKUKAN
  A. Periksa ULANG seluruh 103 produk POS: harga normal (pricelist 3) vs platform (pricelist 5).
     Hanya item yang menyimpang > Rp 0,50 dari ceil500(normal × 1,10) yang ditulis.
     Kategori 'Services' → platform WAJIB = normal (tanpa markup).
  B. Tulis `fixed_price` item platform yang salah saja. Tidak menyentuh `list_price`,
     pricelist "Harga Normal", "Harga Dine In", preset, pos.config, order, atau stok.
  C. Verifikasi ulang setelah commit.

  Idempotent — aman dijalankan ulang (setelah benar, 0 item diubah).
  Read-only penuh saat dry-run (`env.cr.rollback()`).

  dry-run : su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/perbaikan_master_02_harga_platform.py
  eksekusi: su odoo -s /bin/bash -c "RUN=1 odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/perbaikan_master_02_harga_platform.py
"""
import os
from decimal import Decimal, ROUND_CEILING

RUN = os.environ.get("RUN") == "1"

MARKUP = 1.10          # +10% komisi platform (sama dengan skrip 112)
ROUND_TO = 500         # dibulatkan KE ATAS ke Rp 500 (juni_juli_112)
TOL = 0.5              # toleransi pembulatan (sama dengan recon_kesiapan_harga_bom.py)
PL_NORMAL = 3
PL_PLATFORM = 5
KATEGORI_TANPA_MARKUP = ("Services",)

cr = env.cr
PP = env["product.product"]
PL = env["product.pricelist"]
PLI = env["product.pricelist.item"]

say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))


def bulat(x):
    """Bulatkan KE ATAS ke Rp 500 terdekat.

    AKAR MASALAH yang diperbaiki skrip ini: implementasi `juni_juli_112` memakai
    `math.ceil(float(x) / 500) * 500`. Untuk harga yang hasil kalinya jatuh PERSIS di
    kelipatan Rp 500, floating point membuatnya sedikit DI ATAS, lalu `ceil` menaikkan
    satu langkah penuh:

        25000 * 1.10  ->  27500.000000000004  ->  ceil(55.000000001) = 56  ->  28.000  (salah)
        50000 * 1.10  ->  55000.000000000010  ->  ceil(110.0000001)  = 111 ->  55.500  (salah)

    Inilah sebabnya GEPREK MOZAA (25.000) dan PAKET GEPREK BAKAR (50.000) — dua produk
    dengan harga normal kelipatan Rp 5.000 — menjadi satu langkah Rp 500 terlalu mahal.
    Decimal menghitung eksak sehingga +10% tepat tetap dibulatkan ke dirinya sendiri.
    """
    d = Decimal(str(x)) * Decimal(str(MARKUP))
    langkah = (d / Decimal(ROUND_TO)).to_integral_value(rounding=ROUND_CEILING)
    return int(langkah) * ROUND_TO


def item_map(pricelist):
    """{product_tmpl_id: (item, fixed_price)} — item level template saja."""
    out = {}
    for it in PLI.search([("pricelist_id", "=", pricelist.id)]):
        tid = it.product_tmpl_id.id or (it.product_id.product_tmpl_id.id if it.product_id else None)
        if tid:
            out[tid] = it
    return out


# ================================================================ GUARD
say("=" * 112)
say("PERBAIKI HARGA PLATFORM YANG MENYIMPANG   |   RUN=%s   |   %s" % (RUN, "TULIS" if RUN else "DRY-RUN"))
say("=" * 112)

pl3 = PL.with_context(active_test=False).search([("id", "=", PL_NORMAL)], limit=1)
plp = PL.with_context(active_test=False).search([("id", "=", PL_PLATFORM)], limit=1)

say("")
say("[GUARD]")
if not pl3.exists():
    raise SystemExit("!! pricelist id %s tidak ada — hentikan." % PL_NORMAL)
if not plp.exists():
    raise SystemExit("!! pricelist id %s ('Harga Platform Online') tidak ada — hentikan." % PL_PLATFORM)
if plp.name != "Harga Platform Online":
    raise SystemExit("!! pricelist id %s bernama %r, bukan 'Harga Platform Online' — hentikan."
                     % (PL_PLATFORM, plp.name))
say("   pricelist %s '%s'  item=%d   (sumber harga normal)" % (
    pl3.id, pl3.name, PLI.search_count([("pricelist_id", "=", pl3.id)])))
say("   pricelist %s '%s'  item=%d   (yang diperbaiki)" % (
    plp.id, plp.name, PLI.search_count([("pricelist_id", "=", plp.id)])))
say("   rumus: platform = ceil500(normal x %.2f)   |  toleransi Rp %.2f" % (MARKUP, TOL))

# ================================================================ RENCANA
m_normal = item_map(pl3)
m_plat = item_map(plp)

prods = PP.search([("available_in_pos", "=", True), ("sale_ok", "=", True), ("active", "=", True)])
say("")
say("   produk POS diperiksa : %d" % len(prods))

salah, tanpa_item, ok = [], [], 0
for p in prods:
    t = p.product_tmpl_id
    it_n = m_normal.get(t.id)
    it_p = m_plat.get(t.id)
    if not it_n or not it_p:
        tanpa_item.append((t, "normal" if not it_n else "platform"))
        continue
    harga_normal = float(it_n.fixed_price or 0)
    harga_kini = float(it_p.fixed_price or 0)
    kat = t.categ_id.name if t.categ_id else ""
    tanpa_markup = kat in KATEGORI_TANPA_MARKUP
    target = int(round(harga_normal)) if tanpa_markup else bulat(harga_normal)
    if abs(harga_kini - target) > TOL:
        salah.append((t, kat, harga_normal, harga_kini, target, tanpa_markup, it_p))
    else:
        ok += 1

say("   sudah sesuai rumus   : %d" % ok)
say("   MENYIMPANG           : %d" % len(salah))
if tanpa_item:
    say("   !! tanpa item pricelist: %d" % len(tanpa_item))
    for t, mana in tanpa_item:
        say("        - tmpl %-5s %-46s (tidak punya item %s)" % (t.id, t.display_name[:46], mana))

if not salah:
    say("")
    say("   TIDAK ADA YANG PERLU DIPERBAIKI — semua harga platform sudah sesuai rumus.")
    say("=" * 112)
    cr.rollback()
    raise SystemExit(0)

say("")
say("   %-6s %-46s %-9s %12s %12s %12s %9s" % (
    "tmpl", "produk", "kategori", "normal", "platform", "seharusnya", "selisih"))
say("   " + "-" * 104)
for t, kat, hn, hk, target, _tm, _it in sorted(salah, key=lambda r: -abs(r[3] - r[4])):
    say("   %-6s %-46s %-9s %12s %12s %12s %+9s" % (
        t.id, t.display_name[:46], kat[:9], money(hn), money(hk), money(target), money(target - hk)))
say("   " + "-" * 104)
say("   total item akan diubah: %d" % len(salah))
naik = [r for r in salah if r[4] > r[3]]
turun = [r for r in salah if r[4] < r[3]]
say("     turun harga : %d  (total %s)" % (len(turun), money(sum(r[4] - r[3] for r in turun))))
say("     naik harga  : %d  (total +%s)" % (len(naik), money(sum(r[4] - r[3] for r in naik))))

# ================================================================ DRY-RUN
if not RUN:
    say("")
    say("DRY-RUN — tidak ada perubahan ditulis. Jalankan RUN=1 untuk eksekusi.")
    say("=" * 112)
    cr.rollback()
    raise SystemExit(0)

# ================================================================ EKSEKUSI
say("")
say("[EKSEKUSI] menulis fixed_price item pricelist '%s'" % plp.name)
for t, kat, hn, hk, target, _tm, it in salah:
    it.write({"fixed_price": target})
    say("   %-46s %12s → %12s" % (t.display_name[:46], money(hk), money(target)))
cr.flush()
cr.commit()
say("   [COMMITTED] %d item" % len(salah))

# ================================================================ VERIFIKASI
say("")
say("=" * 112)
say("[VERIFIKASI]")
sisa, cek_ok = [], 0
for p in prods:
    t = p.product_tmpl_id
    it_n = m_normal.get(t.id)
    it_p = m_plat.get(t.id)
    if not it_n or not it_p:
        continue
    it_p.invalidate_recordset()
    hn = float(it_n.fixed_price or 0)
    hk = float(it_p.fixed_price or 0)
    kat = t.categ_id.name if t.categ_id else ""
    target = int(round(hn)) if kat in KATEGORI_TANPA_MARKUP else bulat(hn)
    if abs(hk - target) > TOL:
        sisa.append((t, hn, hk, target))
    else:
        cek_ok += 1
say("   sesuai rumus : %d / %d" % (cek_ok, cek_ok + len(sisa)))
for t, hn, hk, target in sisa:
    say("   !! MASIH SALAH: %-44s normal=%s platform=%s harusnya=%s" % (
        t.display_name[:44], money(hn), money(hk), money(target)))

say("")
say("   harga jual & yang lain tidak disentuh:")
say("     list_price         : tidak diubah skrip ini")
say("     pricelist 3 Normal : %d item" % PLI.search_count([("pricelist_id", "=", pl3.id)]))
say("     pricelist 4 Dine In: %d item (arsip, tidak disentuh)" % PLI.search_count(
    [("pricelist_id", "=", 4)]))
say("     produk POS         : %d" % len(prods))
say("")
say("   POS historis tidak disentuh (bukti):")
cr.execute("SELECT to_char(date_order,'YYYY-MM'), count(*), COALESCE(SUM(amount_total),0) "
           "FROM pos_order GROUP BY 1 ORDER BY 1")
for m, n, tot in cr.fetchall():
    say("     %s : %d order / %s" % (m, n, money(tot)))
say("")
say("   CATATAN: harga di POS yang sudah berjalan di-cache; setelah perubahan ini,"
    " hard-reload/restart sesi POS. Item pricelist dievaluasi ulang saat keranjang dibuat.")
say("=" * 112)
