# -*- coding: utf-8 -*-
"""F7 (butir 3) — isi partner pada 1.898 baris AR POS (akun 11210011).

Masalah (temuan inspeksi 15 Sep 2026): seluruh 1.898 baris akun
`11210011 Account Receivable (PoS)` tidak punya `partner_id`. Akun ini adalah
akun transit POS: tiap sesi kasir mendebit AR per metode bayar (jurnal POSS),
lalu jurnal settlement (QRIS, e-wallet, bank, kas) mengkreditnya kembali.
Tanpa partner, laporan per pelanggan (`aged partner`, `partner statement`)
tidak bisa diatribusi.

Aturan atribusi (keputusan pemilik, 15 Sep 2026): **per kanal pembayaran**
(6 partner) — platform memakai partner yang sudah ada, kanal lain dibuatkan
partner "acquirer/kas" baru:

    GoFood (OVO)           -> GoFood Platform        (sudah ada, id 19)
    GrabFood (GO-PAY)      -> GrabFood Platform      (sudah ada, id 20)
    ShopeeFood (ShopeePay) -> ShopeeFood Platform    (sudah ada, id 21)
    QRIS                   -> QRIS Acquirer          (dibuat bila belum ada)
    Kartu / Mallengkeri Kartu        -> Kartu Acquirer   (dibuat)
    Tunai / Mallengkeri Tunai        -> Kasir Tunai      (dibuat)

Sisi kredit (baris settlement) diberi partner yang SAMA supaya saldo per
partner tetap 0 (sesuai kenyataan: tiap sesi dilunasi) dan kartu pernyataan
partner menampilkan pasangan tagih–pelunasan secara utuh.

Keamanan:
  * Dry-run default (tanpa RUN=1 tidak ada yang ditulis).
  * Pemetaan kanal diverifikasi silang lewat pasangan rekonsiliasi
    (`account.partial.reconcile`) — debit dan kredit yang terhubung harus
    satu kanal; bila ada yang tidak terpetakan / tidak konsisten → berhenti.
  * Period lock (`fiscalyear_lock_date = 2026-08-31`) memblokir perubahan
    baris Jun–Agu, jadi skrip ini **membuka lock sementara lalu menutupnya
    kembali** (kecuali RELOCK=0) — sama dengan prosedur di
    `PLANNING_PERBAIKAN_HASIL_INSPEKSI_2026-09-15.md` §13.5.

Jalankan (odoo shell, pola resmi proyek):
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db \
    --db_port 5432 --db_user odoo --db_password odoo --log-level=warn" \
    < scripts/perbaikan_16_partner_ar_pos.py              # DRY-RUN

  RUN=1 su odoo -s /bin/bash -c "RUN=1 odoo shell -d Test1 ..." \
    < scripts/perbaikan_16_partner_ar_pos.py              # EKSEKUSI

Env:
  RUN=1        eksekusi (default: laporan saja)
  RESET=1      KEMBALIKAN: kosongkan lagi partner pada baris AR POS (butuh RUN=1)
  RELOCK=0     biarkan lock terbuka setelah eksekusi (default: lock dipasang lagi)
  ACCOUNT=11210011  kode akun AR POS yang diproses
  CREATE_PARTNERS=0  jangan buat partner baru (hanya pakai yang sudah ada)
"""
import os
import re

RUN = os.environ.get("RUN", "") == "1"
RESET = os.environ.get("RESET", "") == "1"
RELOCK = os.environ.get("RELOCK", "1") != "0"
CREATE = os.environ.get("CREATE_PARTNERS", "1") != "0"
ACCOUNT_CODE = os.environ.get("ACCOUNT", "11210011")

env = env  # noqa: F821  (disediakan odoo shell)
AML = env["account.move.line"]
Partner = env["res.partner"].with_context(active_test=False)
Account = env["account.account"].with_context(active_test=False)
Partial = env["account.partial.reconcile"]

# (kunci, nama partner, label metode di sisi debit, kode jurnal di sisi kredit)
CHANNELS = [
    ("gofood",     "GoFood Platform",     ["GoFood (OVO)"],                       ["OVOW"]),
    ("grabfood",   "GrabFood Platform",   ["GrabFood (GO-PAY)"],                  ["GPYW"]),
    ("shopeefood", "ShopeeFood Platform", ["ShopeeFood (ShopeePay)"],             ["SPPW"]),
    ("qris",       "QRIS Acquirer",       ["QRIS"],                               ["QRIW"]),
    ("kartu",      "Kartu Acquirer",      ["Kartu", "Mallengkeri Kartu"],         ["BNK1", "BNKB"]),
    ("tunai",      "Kasir Tunai",         ["Tunai", "Mallengkeri Tunai"],         ["CSH2", "CSHB"]),
]
BY_METHOD = {m: key for key, _n, methods, _j in CHANNELS for m in methods}
BY_JOURNAL = {c: key for key, _n, _m, codes in CHANNELS for c in codes}
PARTNER_NAME = {key: name for key, name, _m, _j in CHANNELS}

fails = []


def head(txt):
    print("\n=== %s ===" % txt)


def money(x):
    return "{:,.2f}".format(float(x or 0))


def act(txt):
    print("    %s %s" % ("[EKSEKUSI]" if RUN else "[dry-run, tidak dijalankan]", txt))


# ---------------------------------------------------------------------------
# 1) ambil baris AR POS
# ---------------------------------------------------------------------------
head("1) Baris akun AR POS")
accs = Account.search([("code", "=", ACCOUNT_CODE)])
if not accs:
    fails.append("akun %s tidak ditemukan" % ACCOUNT_CODE)
acc = accs[:1]
lines = AML.search([("account_id", "in", accs.ids)], order="date, id")
print("  akun %s — %s : %s baris" % (ACCOUNT_CODE, acc.name, len(lines)))
print("  sudah punya partner : %s" % len(lines.filtered("partner_id")))
print("  tanpa partner       : %s" % len(lines.filtered(lambda l: not l.partner_id)))
if not lines:
    print("  (tidak ada baris — selesai)")
    raise SystemExit(0)

# ---------------------------------------------------------------------------
# 2) klasifikasi kanal setiap baris
# ---------------------------------------------------------------------------
head("2) Klasifikasi kanal (debit: label metode · kredit: kode jurnal)")
channel_of = {}     # line id -> key
unmapped = []
debit_re = re.compile(r"^/\s*-\s*(?P<method>.+?)\s*$")
credit_re = re.compile(r"Gabungkan\s+(?P<method>.+?)\s+pembayaran POS")
for line in lines:
    jcode = line.journal_id.code
    label = (line.name or "").strip()
    if line.debit > 0:
        m = debit_re.match(label)
        key = BY_METHOD.get(m.group("method")) if m else None
        if not key:
            unmapped.append((line.id, "debit", jcode, label))
            continue
    else:
        key = BY_JOURNAL.get(jcode)
        if not key:
            m = credit_re.search(label)
            key = BY_METHOD.get(m.group("method")) if m else None
        if not key:
            unmapped.append((line.id, "kredit", jcode, label))
            continue
    channel_of[line.id] = key

if unmapped:
    print("  TIDAK TERPETAKAN: %d baris" % len(unmapped))
    for row in unmapped[:10]:
        print("    id=%s arah=%s jurnal=%s label=%r" % row)
    fails.append("%d baris tidak bisa dipetakan ke kanal" % len(unmapped))

print("  %-12s %6s %18s %18s" % ("KANAL", "BARIS", "DEBIT", "KREDIT"))
for key, _name, _m, _j in CHANNELS:
    ids = [i for i, k in channel_of.items() if k == key]
    recs = AML.browse(ids)
    print("  %-12s %6d %18s %18s" % (
        key, len(ids),
        money(sum(recs.filtered(lambda l: l.debit > 0).mapped("debit"))),
        money(sum(recs.filtered(lambda l: l.credit > 0).mapped("credit")))))

# ---------------------------------------------------------------------------
# 3) verifikasi silang lewat pasangan rekonsiliasi
# ---------------------------------------------------------------------------
head("3) Verifikasi silang (pasangan rekonsiliasi harus satu kanal)")
pairs = Partial.search([("debit_move_id", "in", lines.ids),
                        ("credit_move_id", "in", lines.ids)])
beda = []
for p in pairs:
    kd = channel_of.get(p.debit_move_id.id)
    kc = channel_of.get(p.credit_move_id.id)
    if kd != kc:
        beda.append((p.debit_move_id.id, kd, p.credit_move_id.id, kc))
print("  pasangan ditemukan : %d dari %d baris kredit" % (
    len(pairs), len(lines.filtered(lambda l: l.credit > 0))))
print("  pasangan beda kanal: %d %s" % (len(beda), beda[:3] if beda else ""))
if beda:
    fails.append("%d pasangan rekonsiliasi beda kanal" % len(beda))

# ---------------------------------------------------------------------------
# 4) siapkan partner per kanal
# ---------------------------------------------------------------------------
head("4) Partner per kanal")
partner_of = {}
for key, name, _m, _j in CHANNELS:
    found = Partner.search([("name", "=", name)], limit=1)
    if found:
        partner_of[key] = found
        print("  %-12s -> %-24s (sudah ada, id %s)" % (key, name, found.id))
    elif CREATE:
        act("buat partner baru: %s" % name)
        if RUN:
            partner_of[key] = Partner.create({
                "name": name,
                "company_type": "company",
                "is_company": True,
                "customer_rank": 0,
                "comment": "Dibuat oleh scripts/perbaikan_16_partner_ar_pos.py "
                           "(atribusi piutang kanal POS per 15 Sep 2026)",
            })
            print("  %-12s -> %-24s (dibuat, id %s)" % (key, name, partner_of[key].id))
    else:
        print("  %-12s -> %-24s (TIDAK ADA, pembuatan dimatikan)" % (key, name))
        fails.append("partner %s tidak ada" % name)

# ---------------------------------------------------------------------------
# 5) ringkasan rencana
# ---------------------------------------------------------------------------
head("5) Rencana penulisan")
to_write = [l for l in lines if not l.partner_id and l.id in channel_of]
print("  baris akan diisi partner : %s dari %s" % (len(to_write), len(lines)))
print("  baris sudah punya partner: %s (dilewati)" % (len(lines.filtered("partner_id"))))

# dampak sebelum (untuk pembanding)
RA = env["geprekyukss.dashboard.report.actions"]
AGU = {"date_from": "2026-08-01", "date_to": "2026-08-31", "outlet_ids": []}


def aged_summary(tag):
    try:
        d = RA.get_report_data("aged_partner", AGU)
        rows = d.get("rows") or []
        prt = [r for r in rows if r.get("is_partner")]
        return "%s: %d baris (+%d sub-baris partner)" % (tag, len(rows) - len(prt), len(prt))
    except Exception as exc:  # noqa: BLE001
        return "%s: laporan tidak bisa dibaca (%s)" % (tag, repr(exc)[:120])


print("  laporan umur piutang SEBELUM : %s" % aged_summary("aged_partner"))
if not RUN:
    print("\nDRY-RUN — tidak ada data ditulis. Jalankan dengan RUN=1 untuk mengeksekusi.")

# ---------------------------------------------------------------------------
# 5b) jalur RESET — mengembalikan baris AR POS ke keadaan tanpa partner
# ---------------------------------------------------------------------------
if RESET and RUN:
    head("5b) RESET — kosongkan partner pada baris AR POS")
    company = env.company
    lock_before = company.fiscalyear_lock_date
    dengan_partner = lines.filtered("partner_id")
    print("  baris yang akan dikosongkan: %s" % len(dengan_partner))
    try:
        if lock_before:
            company.write({"fiscalyear_lock_date": False})
            env.cr.commit()
        dengan_partner.write({"partner_id": False})
        env.cr.commit()
        print("  selesai — partner dikosongkan pada %s baris" % len(dengan_partner))
    except Exception as exc:  # noqa: BLE001
        env.cr.rollback()
        fails.append("reset gagal: %s" % repr(exc)[:200])
        print("  GAGAL → rollback: %s" % repr(exc)[:200])
    finally:
        if lock_before and RELOCK:
            company.write({"fiscalyear_lock_date": lock_before})
            env.cr.commit()
            print("  lock dipasang kembali: %s" % company.fiscalyear_lock_date)
    print("\nRESULT: %s" % ("RESET SELESAI" if not fails else "ADA MASALAH -> %s" % fails))
    raise SystemExit(0 if not fails else 1)

# ---------------------------------------------------------------------------
# 6) eksekusi (buka lock -> tulis -> tutup lock)
# ---------------------------------------------------------------------------
if RUN and not fails:
    head("6) Eksekusi")
    company = env.company
    lock_before = company.fiscalyear_lock_date
    print("  lock sebelum: %s" % lock_before)
    if lock_before:
        company.write({"fiscalyear_lock_date": False})
        env.cr.commit()
        print("  lock dibuka sementara (akan dipasang kembali: %s)" % (RELOCK == 1 or "ya"))
    try:
        for key, partner in partner_of.items():
            ids = [l.id for l in to_write if channel_of.get(l.id) == key]
            if not ids:
                continue
            AML.browse(ids).write({"partner_id": partner.id})
            print("      %-12s %3d baris -> %s" % (key, len(ids), partner.name))
        # verifikasi di dalam transaksi sebelum commit
        left = AML.search_count([("account_id", "in", accs.ids), ("partner_id", "=", False)])
        if left:
            raise RuntimeError("%d baris masih tanpa partner" % left)
        env.cr.commit()
        print("  transaksi di-COMMIT")
    except Exception as exc:  # noqa: BLE001
        env.cr.rollback()
        fails.append("eksekusi gagal: %s" % repr(exc)[:200])
        print("  GAGAL → rollback: %s" % repr(exc)[:200])
    finally:
        if lock_before and RELOCK:
            company.write({"fiscalyear_lock_date": lock_before})
            env.cr.commit()
            print("  lock dipasang kembali: %s" % company.fiscalyear_lock_date)
        elif lock_before and not RELOCK:
            print("  PERHATIAN: lock dibiarkan TERBUKA (RELOCK=0)")

# ---------------------------------------------------------------------------
# 7) verifikasi akhir
# ---------------------------------------------------------------------------
head("7) Verifikasi akhir")
lines2 = AML.search([("account_id", "in", accs.ids)])
tanpa = lines2.filtered(lambda l: not l.partner_id)
print("  baris tanpa partner : %s (harus 0)" % len(tanpa))
if tanpa and RUN:
    fails.append("%d baris masih tanpa partner" % len(tanpa))
print("  total debit  : %s" % money(sum(lines2.mapped("debit"))))
print("  total kredit : %s" % money(sum(lines2.mapped("credit"))))
print("  %-24s %6s %18s %18s %8s" % ("PARTNER", "BARIS", "DEBIT", "KREDIT", "SALDO"))
for key, name, _m, _j in CHANNELS:
    recs = lines2.filtered(lambda l: l.partner_id.name == name)
    d = sum(recs.mapped("debit"))
    k = sum(recs.mapped("credit"))
    print("  %-24s %6d %18s %18s %8s%s" % (
        name, len(recs), money(d), money(k), money(d - k),
        "" if abs(d - k) <= 0.01 else "   <== saldo tidak 0"))
    if abs(d - k) > 0.01:
        fails.append("saldo partner %s tidak 0" % name)

print("  laporan umur piutang SESUDAH: %s" % aged_summary("aged_partner"))
print("\n--- RINGKASAN ---")
print("  mode  : %s" % ("EKSEKUSI (RUN=1)" if RUN else "DRY-RUN"))
print("  fails : %s" % (fails or "tidak ada"))
print("RESULT: %s" % ("SELESAI" if not fails else "ADA MASALAH -> %s" % fails))
