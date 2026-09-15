# -*- coding: utf-8 -*-
"""
juni_juli_86_opex_proporsi.py — beban operasional Juni & Juli MENGIKUTI PROPORSI AGUSTUS.

Permintaan pemilik 13 Sep 2026: *"Buat beban operasional Juni dan Juli dengan proporsi
Agustus, lalu verifikasi ulang laba ketiga bulan."*

Beda dari `25_opex.py`: skrip itu memakai **struktur karangan baru** (gaji 22 jt, listrik
3,5 jt, …) dan — penting — pembersihannya **selalu menyasar Agustus** tanpa melihat MONTHS,
sehingga menjalankannya untuk Juni/Juli akan membatalkan beban Agustus tanpa menggantinya.

Skrip ini sebaliknya **menurunkan angka dari Agustus apa adanya** (tidak mengubah Agustus):

  FIXED    = nilai tiap akun beban Agustus, dipakai sama besar tiap bulan
             (Juni diprorata 11/30 karena hanya beroperasi 20–30 Juni)
  VARIABLE = tarif Agustus x omzet bulan itu
             (6300.01 Komisi Platform Online, 6101.20 Pajak Restoran)
  Penyusutan diperlakukan sebagai FIXED dan dikreditkan ke akun akumulasi, bukan Bank.

Idempotent: JE ber-prefix 'Beban Operasional <bulan>' dihapus dulu sebelum ditulis ulang.

  dry-run : su odoo ... < scripts/juni_juli_86_opex_proporsi.py
  eksekusi: su odoo ... " RUN=1 odoo shell ..." < scripts/juni_juli_86_opex_proporsi.py

Env: RUN=1 | MONTHS=june,july (DEFAULT — Agustus tidak disentuh)
"""
import os

RUN = os.environ.get("RUN") == "1"
MONTHS = [m.strip() for m in os.environ.get("MONTHS", "june,july").split(",") if m.strip()]

cr = env.cr
AM = env["account.move"]
AA = env["account.account"]
AJ = env["account.journal"]
say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))

PERIODS = {
    "june":   ("2026-06-01", "2026-06-30", 11.0 / 30.0, "Juni"),
    "july":   ("2026-07-01", "2026-07-31", 1.0, "Juli"),
    "august": ("2026-08-01", "2026-08-31", 1.0, "Agustus"),
}
AUG = ("2026-08-01", "2026-08-31")

# akun beban penyusutan -> akun akumulasi penyusutan (untuk sisi KREDIT).
#
# PENTING: peta ini diambil BUKAN dari tebakan, tapi dari JE penyusutan Agustus
# (`MISC/2026/08/0012` .. `0018`, `0055`, `0062`) yang sudah ada. Di Odoo 19 akun
# penyusutan bertipe `expense` (BUKAN `expense_depreciation`), jadi deteksi lewat
# `account_type` gagal senyap dan penyusutan jatuh ke KREDIT Bank BSI — padahal
# penyusutan itu beban non-kas. Karena itu deteksinya lewat kode akun ini.
DEP_PAIR = {
    "6101.14": "1106.01",  # Kendaraan
    "6101.15": "1106.02",  # Peralatan Kantor
    "6101.16": "1106.03",  # Peralatan Resto
    "6101.17": "1106.04",  # Aset Renovasi
    "6200.05": "1200.11",  # Bangunan Gudang
    "6200.06": "1200.12",  # Peralatan Gudang
    "6200.07": "1200.13",  # Peralatan IT & POS
}
# akun yang tarifnya mengikuti omzet (bukan nilai tetap)
VARIABLE = {"6300.01", "6101.20"}

REF_PREFIX = "Beban Operasional"


def aid(code):
    cr.execute("SELECT id FROM account_account WHERE code_store->>'1'=%s LIMIT 1", (code,))
    r = cr.fetchone()
    if not r:
        raise SystemExit("akun %s tidak ditemukan" % code)
    return r[0]


def revenue(a, b):
    cr.execute("""SELECT COALESCE(SUM(-aml.balance),0)
                    FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND aa.account_type IN ('income','income_other')
                     AND am.date >= %s AND am.date <= %s""", (a, b))
    return float(cr.fetchone()[0] or 0)


BANK = aid("1101.01")
JOUR = AJ.search([("code", "=", "MISC")], limit=1)

say("=" * 104)
say("BEBAN OPERASIONAL JUNI & JULI — PROPORSIONAL AGUSTUS   |   RUN=%s | months=%s" % (
    RUN, ",".join(MONTHS)))
say("=" * 104)

# ---------------------------------------------------------------- 1. baca proporsi Agustus
rev_aug = revenue(*AUG)
cr.execute("""
    SELECT aa.code_store->>'1', aa.name->>'en_US', aa.account_type,
           ROUND(SUM(aml.balance)::numeric, 2)
      FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
      JOIN account_account aa ON aa.id = aml.account_id
     WHERE am.state = 'posted' AND am.date >= %s AND am.date <= %s
       AND aa.account_type IN ('expense', 'expense_depreciation')
     GROUP BY 1, 2, 3 HAVING SUM(aml.balance) <> 0
     ORDER BY 4 DESC""", AUG)
aug = cr.fetchall()

say("")
say("PROPORSI AGUSTUS (omzet %s)" % money(rev_aug))
say("%-9s %-38s %16s %10s  %s" % ("kode", "akun", "nilai Agustus", "jenis", "tarif / nilai per bulan"))
say("-" * 104)
FIXED, RATES = [], []
for code, nama, atype, val in aug:
    val = float(val)
    if code in VARIABLE:
        rate = val / rev_aug if rev_aug else 0.0
        RATES.append((code, nama, rate))
        say("%-9s %-38s %16s %10s  %.4f%% x omzet" % (code, (nama or "")[:38], money(val), "VARIABLE", rate * 100))
    else:
        FIXED.append((code, nama, val, atype))
        say("%-9s %-38s %16s %10s  %s / bulan" % (
            code, (nama or "")[:38], money(val),
            "SUSUT" if code in DEP_PAIR else "TETAP", money(val)))
fix_tot = sum(v for _c, _n, v, _t in FIXED)
say("-" * 104)
say("   total tetap + susut per bulan : %s" % money(fix_tot))
say("   variabel                     : %s" % " + ".join(
    "%.4f%% x omzet" % (r * 100) for _c, _n, r in RATES))

# ---------------------------------------------------------------- 2. rencana
say("")
say("RENCANA PER BULAN")
plan = {}
for key in MONTHS:
    a, b, factor, label = PERIODS[key]
    rev = revenue(a, b)
    rows = []
    for code, nama, val, atype in FIXED:
        amount = round(val * factor, 2)
        if amount:
            rows.append((code, nama, amount, atype))
    for code, nama, rate in RATES:
        amount = round(rev * rate, 2)
        if amount:
            rows.append((code, nama, amount, "variable"))
    tot = sum(r[2] for r in rows)
    plan[key] = {"a": a, "b": b, "label": label, "rev": rev, "rows": rows, "tot": tot}
    say("")
    say("   %s (%s..%s) omzet=%s | prorata tetap=%.4f" % (label, a, b, money(rev), factor))
    for code, nama, amount, atype in rows:
        say("      %-9s %-38s %16s  %s" % (code, (nama or "")[:38], money(amount), atype))
    say("      %-9s %-38s %16s  (%.1f%% omzet)" % ("", "TOTAL BEBAN " + label, money(tot),
                                                   100.0 * tot / rev if rev else 0))
    say("      %-9s %-38s %16s" % ("", "laba sebelum beban", money(rev)))

# ---------------------------------------------------------------- 3. eksekusi
say("")
say("[3] TULIS")
for key in MONTHS:
    p = plan[key]
    old = AM.search([("ref", "like", REF_PREFIX + " " + p["label"] + "%"),
                     ("date", ">=", p["a"]), ("date", "<=", p["b"])])
    say("   %s: %d JE lama %s" % (p["label"], len(old), "(dihapus & ditulis ulang)" if old else "(tidak ada)"))
    if RUN:
        for m in old:
            m.line_ids.remove_move_reconcile()
            m.button_draft()
            m.unlink()
        env.cr.commit()

for key in MONTHS:
    p = plan[key]
    if not RUN:
        say("   %s [dry] %d JE @%s" % (p["label"], len(p["rows"]), p["b"]))
        continue
    n = 0
    for code, nama, amount, atype in p["rows"]:
        if code in DEP_PAIR:
            kredit = aid(DEP_PAIR[code])
            lname = "Akumulasi penyusutan %s" % p["label"]
        else:
            kredit = BANK
            lname = "Pembayaran ke Bank BSI"
        ref = "%s %s 2026 - %s" % (REF_PREFIX, p["label"], (nama or "").replace("Beban ", ""))
        mv = AM.create({"journal_id": JOUR.id, "date": p["b"], "ref": ref,
                        "line_ids": [
                            (0, 0, {"account_id": aid(code), "debit": amount, "credit": 0.0,
                                    "name": "%s %s 2026" % (nama, p["label"])}),
                            (0, 0, {"account_id": kredit, "debit": 0.0, "credit": amount,
                                    "name": lname}),
                        ]})
        mv.action_post()
        n += 1
    env.cr.commit()
    say("   %s: %d JE ditulis (total %s)" % (p["label"], n, money(p["tot"])))

# ---------------------------------------------------------------- 4. verifikasi
say("")
say("=" * 104)
say("[4] LABA RUGI TIGA BULAN + TB")
say("%-9s %16s %16s %16s %16s %9s" % ("bulan", "Pendapatan", "HPP", "Beban", "Laba", "net%"))
say("-" * 104)
grand = 0.0
for key in ("june", "july", "august"):
    a, b, _f, label = PERIODS[key]
    cr.execute("""SELECT COALESCE(SUM(-aml.balance),0) FROM account_move_line aml
                    JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND am.date >= %s AND am.date <= %s
                     AND aa.account_type IN ('income','income_other')""", (a, b))
    inc = float(cr.fetchone()[0] or 0)
    cr.execute("""SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml
                    JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND am.date >= %s AND am.date <= %s
                     AND aa.account_type = 'expense_direct_cost'""", (a, b))
    hpp = float(cr.fetchone()[0] or 0)
    cr.execute("""SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml
                    JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND am.date >= %s AND am.date <= %s
                     AND aa.account_type IN ('expense','expense_depreciation')""", (a, b))
    ope = float(cr.fetchone()[0] or 0)
    laba = inc - hpp - ope
    grand += laba
    say("%-9s %16s %16s %16s %16s %8.1f%%" % (
        label, money(inc), money(hpp), money(ope), money(laba),
        100.0 * laba / inc if inc else 0))
say("-" * 104)
say("%-9s %71s" % ("TOTAL", money(grand)))

say("")
say("   Cek keseimbangan & akun kunci")
for key in ("june", "july", "august"):
    a, b, _f, label = PERIODS[key]
    cr.execute("""SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0)
                    FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                   WHERE am.state='posted' AND am.date >= %s AND am.date <= %s""", (a, b))
    d, k = cr.fetchone()
    say("      TB %-8s diff=%s" % (label, money(float(d or 0) - float(k or 0))))
for code, nm in (("1101.01", "Bank BSI"), ("1101.02", "QRIS"), ("2101.01", "Utang Usaha")):
    cr.execute("""SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml
                    JOIN account_move am ON am.id=aml.move_id
                   WHERE am.state='posted' AND aml.account_id=%s""", (aid(code),))
    say("      %-9s %-24s %16s" % (code, nm, money(cr.fetchone()[0])))
say("")
say("LANGKAH: verifikasi ulang dengan 12_verify.py.")
say("=" * 104)
