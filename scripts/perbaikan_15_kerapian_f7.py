# -*- coding: utf-8 -*-
"""F7 (kerapian) — hapus pricelist arsip & rapikan seluruh rujukannya.

Latar: `Harga Dine In` (id 4) adalah pricelist sisa skenario "dine in" yang tidak
jadi dipakai — sudah `active = False`, tidak dipakai satu order pun, tetapi masih
menyimpan 103 baris harga dan dirujuk oleh 2 `pos.config` arsip (id 6 & 7).
F7 memutuskan pricelist ini dibuang supaya tidak ada harga "hantu".

Bagian database sisa (`tmp_cost_snap`) TIDAK ditangani di sini karena berada di
luar database ini — lakukan via psql (lihat
`RINGKASAN_PERBAIKAN_F7_KERAPIAN_2026-09-15.md`):

  pg_dump -Fc -h db -U odoo tmp_cost_snap > backup_snapshot_tmp_cost_snap.dump   # arsipkan dulu
  psql -h db -U odoo -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='tmp_cost_snap';"
  psql -h db -U odoo -d postgres -c 'DROP DATABASE "tmp_cost_snap";'

Cara pakai (odoo shell, pola resmi proyek):
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db \
    --db_port 5432 --db_user odoo --db_password odoo --log-level=warn" \
    < scripts/perbaikan_15_kerapian_f7.py            # DRY-RUN (default)

  RUN=1 ... < scripts/perbaikan_15_kerapian_f7.py    # EKSEKUSI

Env:
  RUN=1              eksekusi (tanpa ini hanya laporan / dry-run)
  TARGET_PRICELIST=3 pricelist pengganti untuk rujukan yang dirapikan (Harga Normal)
  KEEP_IDS=          daftar id pricelist arsip yang DIPERTAHANKAN (mis. "4,9")
"""
import os

RUN = os.environ.get("RUN", "") == "1"
TARGET_ID = int(os.environ.get("TARGET_PRICELIST", "3"))
KEEP = {int(x) for x in os.environ.get("KEEP_IDS", "").replace(" ", "").split(",") if x}

env = env  # noqa: F821  (disediakan odoo shell)
PL = env["product.pricelist"].with_context(active_test=False)
Item = env["product.pricelist.item"].with_context(active_test=False)
PC = env["pos.config"].with_context(active_test=False)
PO = env["pos.order"]
PS = env["pos.session"]

fails = []


def head(txt):
    print("\n=== %s ===" % txt)


def act(txt):
    """Tindakan yang HANYA dijalankan dengan RUN=1."""
    print("    %s %s" % ("[EKSEKUSI]" if RUN else "[dry-run, tidak dijalankan]", txt))


# ---------------------------------------------------------------------------
# 1) Inventaris
# ---------------------------------------------------------------------------
head("1) Inventaris pricelist")
all_pl = PL.search([])
print("  %-4s %-24s %-6s %-6s %s" % ("id", "nama", "aktif", "item", "dipakai order"))
for pl in all_pl:
    n_item = Item.search_count([("pricelist_id", "=", pl.id)])
    n_order = PO.search_count([("pricelist_id", "=", pl.id)])
    print("  %-4s %-24s %-6s %-6s %s" % (pl.id, pl.name, pl.active, n_item, n_order))

target = PL.browse(TARGET_ID)
archived = all_pl.filtered(lambda p: not p.active and p.id not in KEEP)
print("\n  pricelist arsip kandidat hapus: %s" % ([(p.id, p.name) for p in archived] or "tidak ada"))
print("  pricelist pengganti (TARGET_PRICELIST): id=%s %s" % (target.id, target.name))
if not target.exists():
    fails.append("TARGET_PRICELIST id=%s tidak ada" % TARGET_ID)
if not archived:
    print("  (tidak ada yang perlu dihapus — selesai)")

# ---------------------------------------------------------------------------
# 2) Pemindaian rujukan — semua model, semua field many2one ke product.pricelist
# ---------------------------------------------------------------------------
head("2) Pemindaian rujukan ke pricelist arsip")
ids = archived.ids
refs = []      # (model, field, jumlah, wajib?)
scan_fail = []
if ids:
    for mname in sorted(env.registry.models.keys()):
        if mname in ("product.pricelist", "product.pricelist.item"):
            continue  # anak pricelist ikut terhapus saat unlink
        try:
            Model = env[mname]
            mfields = Model._fields
        except Exception:      # noqa: BLE001 — model abstrak/aneh, lewati
            continue
        for fname, fld in mfields.items():
            if fld.type != "many2one" or fld.comodel_name != "product.pricelist":
                continue
            try:
                n = Model.with_context(active_test=False).search_count([(fname, "in", ids)])
            except Exception as exc:   # noqa: BLE001 — model yang tak bisa dibaca
                scan_fail.append("%s.%s (%s)" % (mname, fname, exc))
                continue
            if n:
                refs.append((mname, fname, n, bool(fld.required), Model))
if not refs:
    print("  tidak ada rujukan yang menghalangi penghapusan")
for mname, fname, n, req, _Model in refs:
    print("  %-28s %-24s %s baris %s" % (mname, fname, n, "(WAJIB — tidak boleh dikosongkan)" if req else ""))
    if req:
        fails.append("%s.%s wajib diisi — perlu keputusan manual" % (mname, fname))
if scan_fail:
    print("  model yang tidak bisa dipindai: %s" % ", ".join(scan_fail[:5]))

# ---------------------------------------------------------------------------
# 3) pos.config — status & rencana perapian
# ---------------------------------------------------------------------------
head("3) pos.config (outlet) — pemakai pricelist")
for c in PC.search([]):
    n_ord = PO.search_count([("config_id", "=", c.id)])
    n_ses = PS.with_context(active_test=False).search_count([("config_id", "=", c.id)])
    print("  id=%-3s %-24s aktif=%-5s pricelist=%-4s order=%-6s sesi=%s" % (
        c.id, c.name, c.active, c.pricelist_id.id or "-", n_ord, n_ses))
    if not c.active and n_ord == 0 and n_ses == 0 and c.pricelist_id.id in ids:
        act("pos.config id=%s (%s): pricelist %s -> %s" % (
            c.id, c.name, c.pricelist_id.id, TARGET_ID))

# ---------------------------------------------------------------------------
# 4) Eksekusi
# ---------------------------------------------------------------------------
head("4) Perapian rujukan + penghapusan pricelist arsip")
if not ids:
    print("  tidak ada pricelist arsip untuk dihapus")
elif fails:
    print("  DIBATALKAN: ada rujukan wajib / prasyarat gagal -> %s" % fails)
else:
    for mname, fname, n, _req, Model in refs:
        recs = Model.with_context(active_test=False).search([(fname, "in", ids)])
        act("%s.%s: %s baris -> id %s" % (mname, fname, len(recs), TARGET_ID))
        if RUN:
            recs.write({fname: TARGET_ID})
    act("hapus %s pricelist arsip + baris harganya" % len(ids))
    if RUN:
        archived.unlink()

# `odoo shell` TIDAK commit otomatis — tanpa baris di bawah seluruh perubahan
# di atas akan di-rollback saat shell selesai (pola yang sama dipakai
# scripts/perbaikan_10..13).
if RUN and not fails:
    env.cr.commit()
    print("    transaksi di-COMMIT (env.cr.commit())")
elif not RUN:
    print("    (dry-run: tidak menulis apa pun, tidak ada commit)")

# ---------------------------------------------------------------------------
# 5) Verifikasi
# ---------------------------------------------------------------------------
head("5) Verifikasi setelah perapian")
sisa = PL.search([])
sisa_arsip = sisa.filtered(lambda p: not p.active)
print("  pricelist aktif  : %s" % [(p.id, p.name) for p in sisa.filtered(lambda p: p.active)])
print("  pricelist arsip  : %s" % ([(p.id, p.name) for p in sisa_arsip] or "tidak ada"))
print("  total baris harga: %s" % Item.search_count([]))
print("  order POS        : %s (omzet %s)" % (
    PO.search_count([]), sum(PO.search([]).mapped("amount_total"))))

sisa_rujukan = []
if ids:
    for mname, fname, _n, _req, Model in refs:
        left = Model.with_context(active_test=False).search_count([(fname, "in", ids)])
        if left:
            sisa_rujukan.append("%s.%s masih %s" % (mname, fname, left))
if RUN and sisa_rujukan:
    print("  RUJUKAN TERTINGGAL: %s" % sisa_rujukan)
    fails.append("rujukan ke pricelist arsip belum bersih")
elif not RUN:
    print("  (dry-run: %s rujukan akan dirapikan ke id %s)" % (len(refs), TARGET_ID))

untargeted = PC.search([("pricelist_id", "in", ids)]) if ids else PC.browse()
if untargeted and RUN:
    print("  pos.config masih menunjuk pricelist arsip: %s" % [(c.id, c.name) for c in untargeted])
    fails.append("pos.config masih menunjuk pricelist arsip")

print("\n--- RINGKASAN ---")
print("mode     : %s" % ("EKSEKUSI (RUN=1)" if RUN else "DRY-RUN (tambahkan RUN=1 untuk eksekusi)"))
print("fails    : %s" % (fails or "tidak ada"))
print("RESULT: %s" % ("SELESAI" if not fails else "ADA MASALAH -> %s" % fails))
