# -*- coding: utf-8 -*-
"""
juni_juli_12_verify.py — verifikasi lintas-laporan Juni / Juli / Agustus 2026.

READ-ONLY: semua query dijalankan lalu di-rollback di akhir.

Melaporkan per bulan: POS, laba rugi, neraca akhir bulan, mutasi kas/bank,
guard piutang (§14), cek kas negatif, dan trial balance.
"""
from dateutil.relativedelta import relativedelta
from odoo import fields

cr = env.cr
say = lambda m="": print(m)

M = [
    ("Jun", "2026-06-01", "2026-07-01"),
    ("Jul", "2026-07-01", "2026-08-01"),
    ("Agu", "2026-08-01", "2026-09-01"),
]


def one(sql, args=None):
    cr.execute(sql, args or ())
    r = cr.fetchone()
    return r[0] if r else 0


def rows(sql, args=None):
    cr.execute(sql, args or ())
    return cr.fetchall()


def acct_bal(types, a, b):
    """Saldo mentah akun tipe tertentu pada rentang tanggal (debit +, credit -)."""
    return one("""SELECT COALESCE(SUM(aml.balance),0)
                    FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND am.date >= %s AND am.date < %s
                     AND aa.account_type IN %s""", (a, b, tuple(types)))


def cum_bal(types, last):
    return one("""SELECT COALESCE(SUM(aml.balance),0)
                    FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND am.date <= %s
                     AND aa.account_type IN %s""", (last, tuple(types)))


say("=" * 96)
say("VERIFIKASI LINTAS-LAPORAN  JUNI / JULI / AGUSTUS 2026")
say("=" * 96)

# --- 1. POS ----------------------------------------------------------------
say("")
say("[1] POS")
say("    %-6s %6s %8s %20s %12s %10s" % ("bln", "sesi", "order", "omzet POS", "avg/order", "sesi kosong"))
for name, a, b in M:
    n_s = one("SELECT COUNT(*) FROM pos_session WHERE start_at >= %s AND start_at < %s", (a, b))
    n_o, rev = rows("""SELECT COUNT(*), COALESCE(SUM(amount_total),0) FROM pos_order
                        WHERE date_order >= %s AND date_order < %s""", (a, b))[0]
    n_used = one("""SELECT COUNT(DISTINCT session_id) FROM pos_order
                     WHERE date_order >= %s AND date_order < %s""", (a, b))
    say("    %-6s %6d %8d %20s %12s %10d" % (
        name, n_s, n_o, "{:,.2f}".format(rev),
        "{:,.0f}".format(rev / n_o if n_o else 0), n_s - n_used))

# --- 2. Laba rugi ---------------------------------------------------------
say("")
say("[2] LABA RUGI (posted, per rentang tanggal)")
say("    %-6s %18s %18s %18s %18s" % ("bln", "Pendapatan", "HPP", "Beban lain", "Laba bersih"))
for name, a, b in M:
    inc = -acct_bal(["income", "income_other"], a, b)
    hpp = acct_bal(["expense_direct_cost"], a, b)
    exp = acct_bal(["expense", "expense_depreciation"], a, b)
    say("    %-6s %18s %18s %18s %18s" % (
        name, "{:,.2f}".format(inc), "{:,.2f}".format(hpp),
        "{:,.2f}".format(exp), "{:,.2f}".format(inc - hpp - exp)))

# --- 3. Neraca per akhir bulan -------------------------------------------
say("")
say("[3] NERACA per akhir bulan (kumulatif) + cek keseimbangan")
say("    %-6s %18s %18s %16s %18s %16s %18s %14s" % (
    "bln", "Kas & Bank", "Persediaan", "Aset Tetap", "Total Aset",
    "Liabilitas", "Ekuitas", "Aset-Liab-Ek"))
for name, a, b in M:
    last = (fields.Date.to_date(b) - relativedelta(days=1)).isoformat()
    kas = cum_bal(["asset_cash"], last)
    stok = one("""SELECT COALESCE(SUM(aml.balance),0)
                    FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND am.date <= %s
                     AND aa.account_type='asset_current'""", (last,))
    tetap = cum_bal(["asset_fixed", "asset_non_current", "asset_prepayments"], last)
    aset = kas + stok + tetap + cum_bal(["asset_receivable"], last)
    lia = -cum_bal(["liability_current", "liability_non_current", "liability_payable",
                    "liability_credit_card"], last)
    eku = -cum_bal(["equity", "equity_unaffected"], last)
    say("    %-6s %18s %18s %16s %18s %16s %18s %14s" % (
        name, "{:,.2f}".format(kas), "{:,.2f}".format(stok), "{:,.2f}".format(tetap),
        "{:,.2f}".format(aset), "{:,.2f}".format(lia), "{:,.2f}".format(eku),
        "{:,.2f}".format(aset - lia - eku)))

# --- 4. Arus kas bulanan --------------------------------------------------
say("")
say("[4] MUTASI KAS & BANK per bulan")
say("    %-6s %18s %18s %18s" % ("bln", "Masuk", "Keluar", "Net"))
for name, a, b in M:
    d, k = rows("""SELECT COALESCE(SUM(aml.debit),0), COALESCE(SUM(aml.credit),0)
                     FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                     JOIN account_account aa ON aa.id=aml.account_id
                    WHERE am.state='posted' AND am.date >= %s AND am.date < %s
                      AND aa.account_type='asset_cash'""", (a, b))[0]
    say("    %-6s %18s %18s %18s" % (name, "{:,.2f}".format(d), "{:,.2f}".format(k),
                                     "{:,.2f}".format(d - k)))

# --- 5. Guard no-piutang --------------------------------------------------
say("")
say("[5] GUARD §14 — piutang & outstanding harus 0 di akhir bulan")
out_acc = one("SELECT id FROM account_account WHERE code_store->>'1' = '1103.06'") or 0
for name, a, b in M:
    last = (fields.Date.to_date(b) - relativedelta(days=1)).isoformat()
    pi = one("""SELECT COALESCE(SUM(aml.balance),0)
                  FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                  JOIN account_account aa ON aa.id=aml.account_id
                 WHERE am.state='posted' AND am.date <= %s AND aa.account_type='asset_receivable'""", (last,))
    out = one("""SELECT COALESCE(SUM(aml.balance),0)
                   FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                  WHERE am.state='posted' AND am.date <= %s AND aml.account_id = %s""", (last, out_acc))
    flag = "OK" if abs(pi) < 0.01 and abs(out) < 0.01 else ">>> BELUM BERSIH"
    say("    %-6s s/d %s | piutang =%18s | 1103.06 =%18s  %s" % (
        name, last, "{:,.2f}".format(pi), "{:,.2f}".format(out), flag))

# --- 6. Kas negatif / selisih kas -----------------------------------------

say("")
say("[6] AKUN KAS — saldo akhir bulan & selisih kas yang dibebankan")
for name, a, b in M:
    last = (fields.Date.to_date(b) - relativedelta(days=1)).isoformat()
    neg = rows("""SELECT aa.code_store->>'1', COALESCE(aa.name->>'en_US', aa.name->>'1'), SUM(aml.balance)
                    FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND am.date <= %s AND aa.account_type='asset_cash'
                   GROUP BY 1,2 HAVING SUM(aml.balance) < -0.01 ORDER BY 3""", (last,))
    # pola LIKE dilewatkan sebagai parameter -> tidak perlu escape '%' psycopg2
    sd = one("""SELECT COALESCE(SUM(aml.balance),0)
                  FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                  JOIN account_account aa ON aa.id=aml.account_id
                 WHERE am.state='posted' AND am.date >= %s AND am.date < %s
                   AND aa.account_type='expense' AND aml.name ILIKE %s""",
               (a, b, "Perbedaan kas%"))
    say("    %-6s s/d %s | akun kas negatif: %-3d | beban 'Perbedaan kas': %18s" % (
        name, last, len(neg), "{:,.2f}".format(sd)))
    for code, nm, bal in neg[:5]:
        say("        %-10s %-42s %18s" % (code, (nm or "")[:42], "{:,.2f}".format(bal)))

# --- 6b. Saldo kas/bank HARIAN minimum (bukan hanya akhir bulan) ----------
say("")
say("[6b] SALDO KAS & BANK HARIAN — cek tidak pernah negatif")
for name, a, b in M:
    rws = rows("""SELECT am.date, SUM(aml.balance)
                     FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                     JOIN account_account aa ON aa.id=aml.account_id
                    WHERE am.state='posted' AND aa.account_type='asset_cash' AND am.date < %s
                    GROUP BY 1 ORDER BY 1""", (b,))
    run = mn = 0.0
    mn_d = None
    for dt, bal in rws:
        run += bal
        if mn_d is None or run < mn:
            mn, mn_d = run, dt
    say("    %-6s akumulatif terendah=%18s (pada %s)  akhir=%18s" % (
        name + " s/d", "{:,.2f}".format(mn), mn_d, "{:,.2f}".format(run)))

# --- 6c. Arus kas langsung (direct) ---------------------------------------
say("")
say("[6c] ARUS KAS LANGSUNG per bulan")
say("    %-6s %18s %18s %18s %18s" % ("bln", "+ dari pelanggan", "- ke pemasok", "- beban oper.", "net"))
for name, a, b in M:
    masuk = one("""SELECT COALESCE(SUM(aml.debit),0)
                    FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND aa.account_type='asset_cash'
                     AND am.date >= %s AND am.date < %s
                     AND aml.name NOT ILIKE %s""", (a, b, "Setoran QRIS%"))
    pemasok = one("""SELECT COALESCE(SUM(aml.credit),0)
                      FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                      JOIN account_account aa ON aa.id=aml.account_id
                     WHERE am.state='posted' AND aa.account_type='asset_cash'
                       AND am.date >= %s AND am.date < %s
                       AND aml.name ILIKE %s""", (a, b, "Pembelian bahan tunai%"))
    beban = one("""SELECT COALESCE(SUM(aml.credit),0)
                     FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                     JOIN account_account aa ON aa.id=aml.account_id
                    WHERE am.state='posted' AND aa.account_type='asset_cash'
                      AND am.date >= %s AND am.date < %s
                      AND aml.name NOT ILIKE %s AND aml.name NOT ILIKE %s""",
                (a, b, "Pembelian bahan tunai%", "Setoran QRIS%"))
    say("    %-6s %18s %18s %18s %18s" % (
        name, "{:,.2f}".format(masuk), "{:,.2f}".format(pemasok), "{:,.2f}".format(beban),
        "{:,.2f}".format(masuk - pemasok - beban)))

# --- 7. TB -----------------------------------------------------------------
say("")
say("[7] TRIAL BALANCE")
for name, a, b in M:
    d, k = rows("""SELECT COALESCE(SUM(aml.debit),0), COALESCE(SUM(aml.credit),0)
                     FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                    WHERE am.state='posted' AND am.date >= %s AND am.date < %s""", (a, b))[0]
    say("    %-6s debit=%18s credit=%18s diff=%s" % (
        name, "{:,.2f}".format(d), "{:,.2f}".format(k), "{:,.2f}".format(d - k)))
d, k = rows("""SELECT COALESCE(SUM(aml.debit),0), COALESCE(SUM(aml.credit),0)
                 FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                WHERE am.state='posted'""")[0]
say("    TOTAL  debit=%18s credit=%18s diff=%s" % (
    "{:,.2f}".format(d), "{:,.2f}".format(k), "{:,.2f}".format(d - k)))
say("=" * 96)

env.cr.rollback()
