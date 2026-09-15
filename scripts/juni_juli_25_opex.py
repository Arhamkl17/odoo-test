# -*- coding: utf-8 -*-
"""
juni_juli_25_opex.py — rekalibrasi BEBAN OPERASIONAL Juni/Juli/Agustus.

Latar: beban Agustus (buatan backfill lama) Rp 118,08 jt = 49,4% omzet, dan isinya
penuh JE bolak-balik ("Gaji 74 jt" lalu "Efisiensi 3 karyawan", "Komisi +12,3 jt"
lalu "REVERSAL -12,3 jt"). Harga menu & biaya bahan = DATA ASLI KLIEN (tidak diubah),
jadi satu-satunya tuas adalah beban operasional.

Struktur baru (wajar untuk 2 outlet warung, omzet ±Rp 230 jt/bulan):

  TETAP / bulan
    6101.03 Gaji dan upah            22.000.000
    6101.06 Sewa ruko 2 outlet       15.000.000
    6101.11 Listrik                   3.500.000
    6101.12 PDAM / air                  500.000
    6101.21 IT & aplikasi Odoo           750.000
    6101.22 Adm. bank                    300.000
    penyusutan (7 akun)               5.871.528
  VARIABEL (x omzet bulan itu)
    6300.01 Komisi platform online      3,43%
    6101.20 Pajak restoran              1,50%

Juni hanya beroperasi 20-30 Juni (11 hari) -> pos tetap diprorata 11/30.

Untuk Agustus: seluruh JE beban lama DIBATALKAN dulu (state=cancel, tetap terekam
jejaknya) supaya tidak dobel.

  RUN=1      eksekusi (default dry-run)
  MONTHS=all|june,july,august
"""
import os

RUN = os.environ.get("RUN") == "1"
MONTHS = [m.strip() for m in os.environ.get("MONTHS", "june,july,august").split(",") if m.strip()]

cr = env.cr
AM = env["account.move"]
AA = env["account.account"]
say = lambda m="": print(m)

FIXED = [
    ("6101.03", "Beban Gaji dan Upah", 22_000_000),
    ("6101.06", "Beban Sewa Ruko", 15_000_000),
    ("6101.11", "Beban Listrik", 3_500_000),
    ("6101.12", "Beban PDAM", 500_000),
    ("6101.21", "Beban IT & Aplikasi Odoo", 750_000),
    ("6101.22", "Beban Adm. Bank & Buku Cek/Giro", 300_000),
]
VARIABLE = [("6300.01", "Beban Komisi Platform Online", 0.0343),
            ("6101.20", "Beban Pajak Restoran", 0.0150)]
DEP_MONTH = {   # akun beban -> (akun akumulasi, nilai per bulan)
    "6101.14": ("1200.11", 260_416.67, "Beban Penyusutan Kendaraan"),
    "6101.15": ("1200.10", 625_000.00, "Beban Penyusutan Peralatan Kantor"),
    "6101.16": ("1200.08", 2_083_333.33, "Beban Penyusutan Peralatan Resto"),
    "6101.17": ("1200.09", 1_736_111.11, "Beban Penyusutan Renovasi"),
    "6200.05": ("1200.07", 250_000.00, "Beban Penyusutan Bangunan Gudang"),
    "6200.06": ("1200.12", 416_666.67, "Beban Penyusutan Peralatan Gudang"),
    "6200.07": ("1200.13", 500_000.00, "Beban Penyusutan Sistem IT/POS"),
}
PERIODS = {
    "june": ("2026-06-20", "2026-06-30", 11.0 / 30.0, "Juni"),
    "july": ("2026-07-01", "2026-07-31", 1.0, "Juli"),
    "august": ("2026-08-01", "2026-08-31", 1.0, "Agustus"),
}
OPEX_CODES = tuple([c for c, _n, _v in FIXED] + [c for c, _n, _r in VARIABLE] +
                   ["6101.14", "6101.15", "6101.16", "6101.17"] + ["6200.05", "6200.06", "6200.07"])


def aid(code):
    cr.execute("SELECT id FROM account_account WHERE code_store->>'1'=%s LIMIT 1", (code,))
    r = cr.fetchone()
    if not r:
        raise SystemExit("akun %s tidak ditemukan" % code)
    return r[0]


BANK = aid("1101.01")
JOUR = env["account.journal"].search([("code", "=", "MISC")], limit=1)


def revenue(a, b):
    cr.execute("""SELECT COALESCE(SUM(aml.balance),0)
                    FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND aa.account_type IN ('income','income_other')
                     AND am.date >= %s AND am.date <= %s""", (a, b))
    return -cr.fetchone()[0]


def post(dt, ref, lines):
    if not RUN:
        return None
    mv = AM.create({"journal_id": JOUR.id, "date": dt, "ref": ref,
                    "line_ids": [(0, 0, l) for l in lines]})
    mv.action_post()
    return mv


say("=" * 100)
say("REKALIBRASI BEBAN OPERASIONAL   |   RUN=%s | months=%s" % (RUN, ",".join(MONTHS)))
say("=" * 100)

# --- 1. batalkan JE beban lama Agustus ------------------------------------
say("")
say("[1] Batalkan JE beban lama Agustus")
cr.execute("""
    SELECT DISTINCT am.id, am.name, am.ref
      FROM account_move am JOIN account_move_line aml ON aml.move_id = am.id
      JOIN account_account aa ON aa.id = aml.account_id
     WHERE am.state='posted' AND am.date >= '2026-08-01' AND am.date < '2026-09-01'
       AND aa.code_store->>'1' IN %s
     ORDER BY am.id""", (OPEX_CODES,))
old = cr.fetchall()
say("   ditemukan %d JE beban lama" % len(old))
for mid, nm, ref in old:
    if RUN:
        try:
            AM.browse(mid).button_cancel()
        except Exception as e:
            say("      GAGAL %s -> %s" % (nm, repr(e)[:90]))
say("   %s" % ("dibatalkan semua" if RUN else "(dry-run)"))
if RUN:
    env.cr.commit()

# --- 2. posting struktur baru ---------------------------------------------
say("")
say("[2] Posting struktur beban baru")
for key in MONTHS:
    a, b, factor, label = PERIODS[key]
    rev = revenue(a, b)
    say("   %s (%s..%s) omzet=%s | prorata tetap=%.4f" % (
        label, a, b, "{:,.2f}".format(rev), factor))
    tot = 0.0
    for code, nama, val in FIXED:
        amount = round(val * factor, 2)
        if amount <= 0:
            continue
        mv = post(b, "%s %s - %s" % (nama, label, "2026"), [
            {"account_id": aid(code), "debit": amount, "credit": 0.0,
             "name": "%s %s 2026" % (nama, label)},
            {"account_id": BANK, "debit": 0.0, "credit": amount,
             "name": "Pembayaran %s %s 2026" % (nama.lower(), label)},
        ])
        tot += amount
        say("      %-38s %16s %s" % (nama, "{:,.2f}".format(amount), mv.name if mv else ""))
    for code, nama, rate in VARIABLE:
        amount = round(rev * rate, 2)
        if amount <= 0:
            continue
        mv = post(b, "%s %s - 2026" % (nama, label), [
            {"account_id": aid(code), "debit": amount, "credit": 0.0,
             "name": "%s %s 2026 (%.2f%% x omzet)" % (nama, label, rate * 100)},
            {"account_id": BANK, "debit": 0.0, "credit": amount,
             "name": "Pembayaran %s %s 2026" % (nama.lower(), label)},
        ])
        tot += amount
        say("      %-38s %16s %s" % (nama, "{:,.2f}".format(amount), mv.name if mv else ""))
    for code, (acc_code, val, nama) in sorted(DEP_MONTH.items()):
        amount = round(val * factor, 2)
        if amount <= 0:
            continue
        mv = post(b, "Penyusutan %s 2026 - %s" % (label, nama.replace("Beban Penyusutan ", "")), [
            {"account_id": aid(code), "debit": amount, "credit": 0.0, "name": "%s %s" % (nama, label)},
            {"account_id": aid(acc_code), "debit": 0.0, "credit": amount,
             "name": "Akumulasi penyusutan %s" % label},
        ])
        tot += amount
        say("      %-38s %16s %s" % (nama, "{:,.2f}".format(amount), mv.name if mv else ""))
    say("      %-38s %16s  (%.1f%% omzet)" % ("TOTAL BEBAN " + label, "{:,.2f}".format(tot),
                                              100.0 * tot / rev if rev else 0))
    if RUN:
        env.cr.commit()

# --- 3. ringkasan ---------------------------------------------------------
say("")
say("[3] Ringkasan laba rugi per bulan")
say("   %-9s %16s %16s %16s %16s %9s" % ("bulan", "Pendapatan", "HPP", "Beban", "Laba", "net%"))
grand = 0.0
for key in ("june", "july", "august"):
    a, b, _f, label = PERIODS[key]
    cr.execute("""SELECT COALESCE(SUM(aml.balance),0)
                    FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND am.date >= %s AND am.date <= %s
                     AND aa.account_type IN ('income','income_other')""", (a, b))
    inc = -cr.fetchone()[0]
    cr.execute("""SELECT COALESCE(SUM(aml.balance),0)
                    FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND am.date >= %s AND am.date <= %s
                     AND aa.account_type = 'expense_direct_cost'""", (a, b))
    hpp = cr.fetchone()[0]
    cr.execute("""SELECT COALESCE(SUM(aml.balance),0)
                    FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND am.date >= %s AND am.date <= %s
                     AND aa.account_type IN ('expense','expense_depreciation')""", (a, b))
    ope = cr.fetchone()[0]
    laba = inc - hpp - ope
    grand += laba
    say("   %-9s %16s %16s %16s %16s %8.1f%%" % (
        label, "{:,.2f}".format(inc), "{:,.2f}".format(hpp), "{:,.2f}".format(ope),
        "{:,.2f}".format(laba), 100.0 * laba / inc if inc else 0))
say("   %-9s %60s" % ("TOTAL laba", "{:,.2f}".format(grand)))
cr.execute("""SELECT COALESCE(SUM(aml.debit),0), COALESCE(SUM(aml.credit),0)
                FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
               WHERE am.state='posted'""")
d, k = cr.fetchone()
say("   TB debit=%s credit=%s diff=%s" % ("{:,.2f}".format(d), "{:,.2f}".format(k),
                                          "{:,.2f}".format(d - k)))
say("=" * 100)
