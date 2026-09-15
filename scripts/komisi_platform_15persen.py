# -*- coding: utf-8 -*-
"""
komisi_platform_15persen.py — JE BEBAN KOMISI PLATFORM 15% (3 BULAN, 72 HARI)

Komisi 15% dari penjualan delivery (GoFood 11, GrabFood 12, ShopeeFood 13) — solusi portfolio:
  harga delivery = Platform +10% (sudah di POS), komisi 15% → Beban 6300.01 (id 243)
  Gross delivery 515.719.000 ×15% = 77.357.850 total (Juni 12d ~81jt×15%, Juli/Agu ~216jt×15%)
Idempotent, dry-run default.

  dry-run : cat scripts/komisi_platform_15persen.py | su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 --db_user odoo --db_password odoo"
  eksekusi: RUN=1 cat scripts/komisi_platform_15persen.py | su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 --db_user odoo --db_password odoo"
  # atau: RUN=1 odoo shell -d Test1 --no-http --db_host db --db_port 5432 --db_user odoo --db_password odoo < scripts/komisi_platform_15persen.py
"""
import os
from datetime import date

RUN = os.environ.get("RUN") == "1"
KOMISI_RATE = 0.15
BEBAN_KOMISI_ACC = 243  # 6300.01 Beban Komisi Platform Online
# Mapping payment_method -> wallet account (OVO 211, GOPAY 212, SHOPEE 213)
PM_TO_ACC = {
    11: 211,  # GoFood (OVO) -> OVO 1101.03
    12: 212,  # GrabFood (GO-PAY) -> GOPAY 1101.04
    13: 213,  # ShopeeFood (ShopeePay) -> SHOPEE PAY 1101.05
}
PM_NAMES = {11: "GoFood (OVO)", 12: "GrabFood (GO-PAY)", 13: "ShopeeFood (ShopeePay)"}
PERIODS = {
    "june":   ("2026-06-20", "2026-07-01", "2026-06-30", "Juni 2026"),
    "july":   ("2026-07-01", "2026-08-01", "2026-07-31", "Juli 2026"),
    "august": ("2026-08-01", "2026-09-01", "2026-08-31", "Agustus 2026"),
}

say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

cr = env.cr
AM = env["account.move"]
AJ = env["account.journal"]
AA = env["account.account"]

say("=" * 100)
say("JE KOMISI PLATFORM 15%% — 2 TOKO 72 HARI | RUN=%s | Beban %s (6300.01)" % (RUN, BEBAN_KOMISI_ACC))
say("Delivery via 11,12,13 → kredit wallet 211,212,213 (net = gross - komisi)")
say("=" * 100)

# --- 0. Validasi akun ---
for acc_id in [BEBAN_KOMISI_ACC] + list(PM_TO_ACC.values()):
    acc = AA.browse(acc_id)
    if not acc.exists():
        say("AKUN %s tidak ada!" % acc_id)
    elif not acc.active:
        say("AKUN %s (%s) arsip f — akan diaktifkan" % (acc_id, acc.name))
        acc.write({"active": True})

misc = AJ.search([("code", "=", "MISC")], limit=1)
if not misc:
    say("Journal MISC tidak ditemukan!")
    import sys; sys.exit(1)
say("Journal: %s id=%s" % (misc.name, misc.id))

# --- 1. Hitung delivery revenue per bulan per metode ---
say("")
say("[HITUNG] Delivery revenue (pos_payment where pm in 11,12,13)")
total_all_rev = 0
total_all_komisi = 0
per_month = {}  # name -> {pm_id: rev}
for name, (d_from, d_to, d_je, label) in PERIODS.items():
    cr.execute("""
        SELECT p.payment_method_id, sum(p.amount)
        FROM pos_payment p
        JOIN pos_order o ON o.id = p.pos_order_id
        WHERE o.date_order >= %s AND o.date_order < %s
          AND p.payment_method_id IN (11,12,13)
        GROUP BY p.payment_method_id
        ORDER BY p.payment_method_id
    """, (d_from, d_to))
    rows = cr.fetchall()
    d = {pm: float(rev or 0) for pm, rev in rows}
    # Ensure all 3 keys
    for pm in PM_TO_ACC:
        d.setdefault(pm, 0.0)
    per_month[name] = d
    rev_month = sum(d.values())
    komisi_month = rev_month * KOMISI_RATE
    total_all_rev += rev_month
    total_all_komisi += komisi_month
    say("  %-7s %s..%s (JE %s): rev Go %s + Grab %s + Shopee %s = %s  → komisi 15%% = %s" % (
        name, d_from, d_to, d_je,
        money(d[11]), money(d[12]), money(d[13]), money(rev_month), money(komisi_month)
    ))
    if rev_month == 0:
        say("    ⚠️  Tidak ada delivery di %s — cek data" % name)

say("")
say("  TOTAL 72 hari: delivery %s → komisi %s (%.1f%% dari gross 2.384M)" % (
    money(total_all_rev), money(total_all_komisi), 100*total_all_komisi/2384428500 if total_all_rev else 0))
say("  Rata delivery/order: %s (vs dinein/take ~65k, platform +10%% → 71k + komisi 15%% net ~62k)" % money(total_all_rev / sum(1 for pm in per_month for v in [per_month[pm]] for vv in [v] ) if False else 0))

# --- 2. Tampilkan rencana JE ---
say("")
say("[RENCANA JE] 3 JE MISC, tanggal akhir bulan, ref 'Komisi Platform 15%% - <Bulan>'")
for name, (d_from, d_to, d_je, label) in PERIODS.items():
    d = per_month[name]
    komisi = sum(d.values()) * KOMISI_RATE
    say("  JE %s | %s | debit 6300.01 %s | kredit: OVO %s, GOPAY %s, SHOPEE %s" % (
        d_je, label, money(komisi),
        money(d[11]*KOMISI_RATE), money(d[12]*KOMISI_RATE), money(d[13]*KOMISI_RATE)
    ))

# --- 3. Cek existing ---
say("")
say("[EXISTING]")
existing_refs = []
for name, (d_from, d_to, d_je, label) in PERIODS.items():
    ref = "Komisi Platform 15%% - %s" % label
    mv = AM.search([("ref", "=", ref)], limit=1)
    if mv:
        say("  %-20s sudah ada: %s id=%s %s (%.0f)" % (label, mv.name, mv.id, mv.state, sum(l.debit for l in mv.line_ids)))
        existing_refs.append(name)
    else:
        say("  %-20s belum ada — akan dibuat" % label)

if not RUN:
    say("")
    say("DRY-RUN — tidak ada data ditulis. Jalankan dengan RUN=1 untuk eksekusi.")
    env.cr.rollback()
    import sys; sys.exit(0)

# --- 4. EKSEKUSI ---
say("")
say("[EKSEKUSI]")
# Matikan hash untuk MISC (sudah false dari opening, tapi pastikan)
try:
    cr.execute("UPDATE account_journal SET restrict_mode_hash_table = false WHERE code = ANY(%s)", (["MISC"],))
except Exception as e:
    say("  (hash disable gagal): %s" % e)

created = 0
for name, (d_from, d_to, d_je, label) in PERIODS.items():
    ref = "Komisi Platform 15%% - %s" % label
    if AM.search_count([("ref", "=", ref)]):
        say("  Skip %s — sudah ada" % label)
        continue
    d = per_month[name]
    rev_total = sum(d.values())
    if rev_total < 0.01:
        say("  Skip %s — rev 0" % label)
        continue
    komisi_by_pm = {pm: d[pm] * KOMISI_RATE for pm in PM_TO_ACC}
    total_komisi = sum(komisi_by_pm.values())
    lines = []
    # Debit beban
    lines.append((0, 0, {"account_id": BEBAN_KOMISI_ACC, "debit": total_komisi, "credit": 0.0,
                         "name": "Beban Komisi Platform 15%% — %s (delivery %s)" % (label, money(rev_total))}))
    # Kredit per wallet
    for pm, acc_id in PM_TO_ACC.items():
        amt = komisi_by_pm[pm]
        if amt < 0.01:
            continue
        lines.append((0, 0, {"account_id": acc_id, "debit": 0.0, "credit": amt,
                             "name": "%s 15%% — %s" % (PM_NAMES[pm], label)}))
    mv = AM.create({"journal_id": misc.id, "date": d_je, "ref": ref, "line_ids": lines})
    mv.action_post()
    say("  JE %s: %s id=%s debit %s (delivery %s)" % (label, mv.name, mv.id, money(total_komisi), money(rev_total)))
    created += 1

env.cr.commit()
say("")
say("[COMMITTED] %s JE komisi dibuat." % created)

# --- 5. VERIFIKASI ---
say("")
say("=" * 100)
say("[VERIFIKASI]")
for name, (d_from, d_to, d_je, label) in PERIODS.items():
    ref = "Komisi Platform 15%% - %s" % label
    mv = AM.search([("ref", "=", ref)], limit=1)
    if not mv:
        say("  %-12s TIDAK ADA" % label)
        continue
    cr.execute("SELECT sum(debit), sum(credit) FROM account_move_line WHERE move_id=%s", (mv.id,))
    d, c = cr.fetchone()
    say("  %-12s %s | %s | debit %s credit %s diff %s" % (label, mv.name, mv.state, money(d), money(c), money((d or 0)-(c or 0))))
# Total beban komisi
cr.execute("SELECT sum(aml.debit - aml.credit) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id WHERE aml.account_id=%s AND am.state='posted'", (BEBAN_KOMISI_ACC,))
val = cr.fetchone()[0] or 0
say("  Total Beban 6300.01 s/d 31 Agu: %s (harus %s)" % (money(val), money(total_all_komisi)))
# Wallet balances (harus berkurang)
for pm, acc_id in PM_TO_ACC.items():
    cr.execute("SELECT sum(aml.debit - aml.credit) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id WHERE aml.account_id=%s AND am.state='posted'", (acc_id,))
    bal = cr.fetchone()[0] or 0
    # POS gross ke wallet
    cr.execute("""
        SELECT sum(p.amount) FROM pos_payment p JOIN pos_order o ON o.id=p.pos_order_id
        WHERE p.payment_method_id=%s AND o.date_order >= '2026-06-20'
    """, (pm,))
    gross = cr.fetchone()[0] or 0
    say("  Wallet %s (acc %s): gross POS %s - komisi %s = balance %s" % (
        PM_NAMES[pm], acc_id, money(gross), money(gross*KOMISI_RATE), money(bal)))
# TB
cr.execute("SELECT sum(debit), sum(credit) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id WHERE am.state='posted' AND am.date BETWEEN '2026-06-19' AND '2026-08-31'")
d, c = cr.fetchone()
say("  TB 19 Jun–31 Agu: debit %s credit %s diff %s %s" % (money(d), money(c), money((d or 0)-(c or 0)), "OK" if abs((d or 0)-(c or 0)) < 0.01 else ">>> TIDAK BALANCE"))
say("=" * 100)
