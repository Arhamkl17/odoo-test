# -*- coding: utf-8 -*-
"""
juni_juli_112_harga_tunggal_preset.py — SATU HARGA JUAL + HARGA PLATFORM + PRESET (13 Sep 2026).

KEPUTUSAN PEMILIK (13 Sep 2026):
  • Harga tunggal   : harga Dine In klien (pricelist id 4) menjadi SATU harga untuk
                      dine-in & take-away.
  • Markup platform : +10% (komisi platform) untuk GoFood/GrabFood/ShopeeFood,
                      DIBULATKAN KE ATAS ke Rp 500 (tidak boleh di bawah +10%).
                      Produk kategori 'Services' (Gift Card / Top-up) TIDAK di-markup.
  • Implementasi POS: lewat PRESET (Dine In / Takeout / Delivery) — TIDAK menambah
                      pos.config baru (tetap 2 outlet).
  • UOM             : TIDAK diubah (keputusan pemilik); anomali dilaporkan di skrip 111.

Yang dilakukan:
  A. pricelist id 3 di-rename "Harga Normal"; `fixed_price` item-nya DAN `list_price`
     disetel = harga Dine In (pricelist id 4).
  B. pricelist baru "Harga Platform Online" = harga normal +10%, dibulatkan Rp 500.
  C. preset 1/2/3 diberi pricelist (Dine In & Takeout -> Normal, Delivery -> Platform),
     lalu dipasang di pos.config 1 & 2 (use_presets + use_pricelist, default = Dine In).
  D. TERONG CRISPY (tmpl 550) diarsipkan — variannya (pp 539) sudah non-aktif sejak lama,
     tinggal templatenya. Riwayat stok (127 move) & jurnal (10 baris) TIDAK disentuh.

TIDAK menyentuh order/sesi historis. Idempotent — aman dijalankan ulang.

  dry-run : su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/juni_juli_112_harga_tunggal_preset.py
  eksekusi: su odoo -s /bin/bash -c "RUN=1 odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/juni_juli_112_harga_tunggal_preset.py
"""
import math
import os

RUN = os.environ.get("RUN") == "1"

MARKUP = 1.10           # +10% untuk channel platform
ROUND_TO = 500          # pembulatan Rp 500 terdekat
NAMA_NORMAL = "Harga Normal"
NAMA_PLATFORM = "Harga Platform Online"
TERONG_TMPL = 550       # template yang diarsipkan
CONFIG_IDS = [1, 2]
PRESET_DINEIN, PRESET_TAKEOUT, PRESET_DELIVERY = 1, 2, 3

cr = env.cr
PT = env["product.template"]
PP = env["product.product"]
PL = env["product.pricelist"]
PLI = env["product.pricelist.item"]
CFG = env["pos.config"]
PRE = env["pos.preset"]

say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))


def bulat(x):
    """Bulatkan KE ATAS ke Rp 500 terdekat.

    Ke atas (ceil), bukan terdekat: pembulatan terdekat pernah membuat harga
    platform TURUN ke harga normal pada item murah (2.000 × 1,10 = 2.200 → 2.000)
    dan Rp 0 pada item Rp 50. Dengan ceil dijamin ≥ +10%.

    CATATAN (13 Sep 2026): `round(float(x), 6)` WAJIB ada. Tanpa itu, floating point
    membuat hasil yang jatuh persis di kelipatan Rp 500 menjadi sedikit DI ATAS lalu
    `ceil` menaikkan satu langkah penuh (25.000 × 1,10 → 27.500,000000000004 →
    dianggap 55,000000001 langkah → 28.000). Dua produk pernah salah karena ini
    (GEPREK MOZAA 28.000, PAKET GEPREK BAKAR 55.500) dan sudah diperbaiki oleh
    `scripts/perbaikan_master_02_harga_platform.py`.
    """
    return int(math.ceil(round(float(x), 6) / ROUND_TO) * ROUND_TO)


def kategori(t):
    return t.categ_id.name if t.categ_id else None


# ================================================================ GUARD
say("=" * 116)
say("HARGA TUNGGAL + HARGA PLATFORM + PRESET   |   RUN=%s" % RUN)
say("=" * 116)

pl3 = PL.search([("id", "=", 3)], limit=1)
pl4 = PL.with_context(active_test=False).search([("name", "=", "Harga Dine In")], limit=1)

say("")
say("[GUARD]")
if not pl3.exists():
    raise SystemExit("!! pricelist id 3 tidak ada — hentikan.")
if not pl4.exists():
    raise SystemExit("!! pricelist 'Harga Dine In' tidak ada — hentikan.")

dn = {it.product_tmpl_id.id: float(it.fixed_price or 0)
      for it in PLI.search([("pricelist_id", "=", pl4.id)]) if it.product_tmpl_id}
say("   pricelist 3 '%s'  item=%d" % (pl3.name, PLI.search_count([("pricelist_id", "=", pl3.id)]))
    )
say("   pricelist 4 '%s'  item=%d  (arsip, sumber harga tunggal)" % (pl4.name, len(dn)))

prods = PP.search([("available_in_pos", "=", True), ("sale_ok", "=", True)])
tanpa_harga = [p for p in prods if p.product_tmpl_id.id not in dn]
say("   produk POS = %d  |  tanpa harga Dine In = %d %s" % (
    len(prods), len(tanpa_harga),
    ", ".join(p.display_name for p in tanpa_harga) if tanpa_harga else ""))

cfgs = CFG.browse(CONFIG_IDS).exists()
presets = PRE.browse([PRESET_DINEIN, PRESET_TAKEOUT, PRESET_DELIVERY]).exists()
say("   pos.config yang disetel : %s" % ", ".join("%s %r" % (c.id, c.name) for c in cfgs))
say("   preset                  : %s" % ", ".join("%s %r" % (p.id, p.name) for p in presets))
if len(cfgs) != len(CONFIG_IDS) or len(presets) != 3:
    raise SystemExit("!! config/preset tidak lengkap — hentikan.")

# rencana harga  (tuple: p, t, harga normal, harga platform, di-markup?)
rencana = []
for p in prods:
    t = p.product_tmpl_id
    normal = dn[t.id]
    mark = kategori(t) != "Services"
    rencana.append((p, t, normal, bulat(normal * MARKUP) if mark else int(normal), mark))
rencana.sort(key=lambda r: -r[2])
non_markup = [r for r in rencana if not r[4]]

say("")
say("   harga (normal → platform +10%% → dibulatkan KE ATAS Rp 500):")
say("   %-48s %12s %12s" % ("menu", "normal", "platform"))
say("   " + "-" * 76)
for p, t, normal, plat, _m in rencana[:10]:
    say("   %-48s %12s %12s" % (t.display_name[:48], money(normal), money(plat)))
say("   … total %d produk" % len(rencana))
say("")
say("   item TERMURAH (efek pembulatan paling terasa):")
for p, t, normal, plat, _m in sorted(rencana, key=lambda r: r[2])[:8]:
    say("   %-48s %12s %12s" % (t.display_name[:48], money(normal), money(plat)))
if non_markup:
    say("   tanpa markup (kategori Services): %s" % ", ".join(
        r[1].display_name for r in non_markup))

naik = sum(1 for _p, _t, n, pl, _m in rencana if pl > n)
say("")
say("   rencana:")
say("     A. rename pricelist 3 '%s' → '%s'" % (pl3.name, NAMA_NORMAL))
say("        setel list_price + item pricelist 3 = harga Dine In (%d produk)" % len(rencana))
say("     B. pricelist '%s' = harga normal +%.0f%% (bulat ke atas Rp %d) — %d item" % (
    NAMA_PLATFORM, (MARKUP - 1) * 100, ROUND_TO, len(rencana)))
say("     C. preset: Dine In & Takeout → '%s' | Delivery → '%s'" % (
    NAMA_NORMAL, NAMA_PLATFORM))
say("        pos.config 1 & 2: use_presets=True, use_pricelist=True, "
    "available_pricelist=[Normal, Platform], default preset = Dine In")
say("     D. arsipkan template %s 'TERONG CRISPY' (stok & jurnal tidak disentuh)" % TERONG_TMPL)
say("     (harga platform > normal untuk %d dari %d produk)" % (naik, len(rencana)))

# ================================================================ DRY-RUN
if not RUN:
    say("")
    say("DRY-RUN — tidak ada perubahan ditulis. Jalankan RUN=1 untuk eksekusi.")
    say("=" * 116)
    env.cr.rollback()
    raise SystemExit(0)

# ================================================================ A. harga tunggal
say("")
say("[A] SATU HARGA JUAL")
pl3.write({"name": NAMA_NORMAL})
pl3_items = {it.product_tmpl_id.id: it for it in PLI.search([("pricelist_id", "=", pl3.id)])}
n_list = n_item = n_new = 0
for p, t, normal, _plat, _m in rencana:
    if abs(float(t.list_price or 0) - normal) > 0.01:
        t.write({"list_price": normal})
        n_list += 1
    it = pl3_items.get(t.id)
    if it:
        if abs(float(it.fixed_price or 0) - normal) > 0.01:
            it.write({"fixed_price": normal})
            n_item += 1
    else:
        PLI.create({"pricelist_id": pl3.id, "applied_on": "1_product",
                    "product_tmpl_id": t.id, "min_quantity": 0,
                    "compute_price": "fixed", "fixed_price": normal,
                    "base": "list_price"})
        n_new += 1
say("   list_price diubah    : %d" % n_list)
say("   item pricelist diubah: %d" % n_item)
say("   item pricelist baru  : %d" % n_new)
env.cr.flush()

# ================================================================ B. harga platform
say("")
say("[B] HARGA PLATFORM ONLINE (+%.0f%%)" % ((MARKUP - 1) * 100))
plp = PL.with_context(active_test=False).search([("name", "=", NAMA_PLATFORM)], limit=1)
if not plp:
    plp = PL.create({
        "name": NAMA_PLATFORM,
        "currency_id": env.company.currency_id.id,
        "company_id": env.company.id,
        "active": True,
    })
    say("   pricelist dibuat: id=%s" % plp.id)
else:
    say("   pricelist sudah ada: id=%s" % plp.id)
plp.write({"active": True})

wanted = {t.id for _p, t, _n, _pl, _m in rencana}
plp_items = {it.product_tmpl_id.id: it for it in PLI.search([("pricelist_id", "=", plp.id)])}
n_upd = n_new = n_del = 0
for p, t, normal, plat, _m in rencana:
    it = plp_items.get(t.id)
    if it:
        if abs(float(it.fixed_price or 0) - plat) > 0.01:
            it.write({"fixed_price": plat})
            n_upd += 1
    else:
        PLI.create({"pricelist_id": plp.id, "applied_on": "1_product",
                    "product_tmpl_id": t.id, "min_quantity": 0,
                    "compute_price": "fixed", "fixed_price": plat,
                    "base": "list_price"})
        n_new += 1
for tid, it in plp_items.items():
    if tid not in wanted:
        it.unlink()
        n_del += 1
say("   item platform: diubah=%d | baru=%d | dihapus=%d | total=%d" % (
    n_upd, n_new, n_del, len(rencana)))
env.cr.flush()

# ================================================================ C. preset
say("")
say("[C] PRESET & POS CONFIG")
pset = {PRESET_DINEIN: pl3, PRESET_TAKEOUT: pl3, PRESET_DELIVERY: plp}
for pid, pl in pset.items():
    pr = PRE.browse(pid)
    pr.write({"pricelist_id": pl.id})
    say("   preset %-4s %-16s → %s" % (pid, pr.name, pl.name))

for c in cfgs:
    c.write({
        "use_presets": True,
        "use_pricelist": True,
        "pricelist_id": pl3.id,
        "available_pricelist_ids": [(6, 0, [pl3.id, plp.id])],
        "default_preset_id": PRESET_DINEIN,
        "available_preset_ids": [(6, 0, [PRESET_DINEIN, PRESET_TAKEOUT, PRESET_DELIVERY])],
    })
    say("   config %-3s %-22s pricelist=%s | preset default=%s | n preset=%d" % (
        c.id, c.name, c.pricelist_id.name, c.default_preset_id.name,
        len(c.available_preset_ids)))
env.cr.flush()

# ================================================================ D. TERONG CRISPY
say("")
say("[D] ARSIP TERONG CRISPY")
terong = PT.browse(TERONG_TMPL)
if terong.exists() and terong.active:
    terong.write({"active": False, "available_in_pos": False, "sale_ok": False})
    say("   template %s '%s' → active=%s available_in_pos=%s sale_ok=%s" % (
        TERONG_TMPL, terong.name, terong.active,
        terong.available_in_pos, terong.sale_ok))
    say("   (stok 127 move & 10 baris jurnal tetap utuh)")
else:
    say("   sudah tidak aktif / tidak ada — dilewati")

env.cr.commit()
say("")
say("[COMMITTED]")

# ================================================================ VERIFIKASI
say("")
say("=" * 116)
say("[VERIFIKASI]")
say("")
for pl in PL.with_context(active_test=False).search([]):
    say("   pricelist id=%-3s %-26s aktif=%-5s item=%d" % (
        pl.id, pl.name, pl.active, PLI.search_count([("pricelist_id", "=", pl.id)])))
say("")
for c in CFG.with_context(active_test=False).search([]):
    say("   config id=%-3s %-22s aktif=%-5s pricelist=%-18s preset(default=%-14s n=%d)" % (
        c.id, c.name, c.active, c.pricelist_id.name or "-",
        c.default_preset_id.name or "-", len(c.available_preset_ids)))
say("")
for pr in PRE.search([]):
    say("   preset id=%-3s %-16s pricelist=%s" % (
        pr.id, pr.name, pr.pricelist_id.name or "(KOSONG)"))
say("")
say("   produk POS           : %d" % PP.search_count(
    [("available_in_pos", "=", True), ("sale_ok", "=", True)]))
say("   produk tanpa kategori: %d (dilaporkan, tidak diubah)" % PT.search_count(
    [("available_in_pos", "=", True), ("sale_ok", "=", True), ("categ_id", "=", False)]))
say("")
say("   contoh harga akhir (list_price | Normal | Platform):")
for p, t, normal, plat, _m in rencana[:8]:
    t.invalidate_recordset()
    say("     %-48s %10s | %10s | %10s" % (
        t.display_name[:48], money(t.list_price), money(normal), money(plat)))

say("")
say("   POS historis tidak disentuh:")
cr.execute("SELECT to_char(date_order,'YYYY-MM'), count(*), COALESCE(SUM(amount_total),0) "
           "FROM pos_order GROUP BY 1 ORDER BY 1")
for m, n, t in cr.fetchall():
    say("     %s : %d order / %s" % (m, n, money(t)))
say("=" * 116)
