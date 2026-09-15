# -*- coding: utf-8 -*-
"""
juni_juli_06_fix_august.py — P5: perbaiki data Agustus 2026 yang tidak masuk akal.

Enam perbaikan (1 lagi = BOM, dikerjakan terpisah di 07_*):

  P5.1  Outstanding Receipts Rp 26.088.951 menggantung di neraca 31 Agu
        -> geser 10 JE "Settlement pembayaran POS *" dari 2026-09-01 ke 2026-08-31
           (semua journal hash=False, jadi aman lewat ORM)

  P5.2  Sesi POS menulis AR ke akun NONAKTIF 11210011, padahal setting company
        menunjuk 1102.04 (0 baris). -> konsolidasi ke SATU akun kanonik:
           11210011  = "Piutang Usaha (PoS)"  (aktif, memegang seluruh histori)
           1102.04   = nonaktif (tanpa histori)
           company.account_default_pos_receivable_account_id = 11210011

  P5.3  1.142 baris AR di JE sesi memakai label metode bayar BASI
        (BCA/BNI/BRI/Mandiri/OVO/GO-PAY/ShopeePay — sudah di-merge Fase 12/12b).
        -> ganti nama baris ke metode yang berlaku sekarang. TIDAK dihapus/dibuat
           ulang, supaya rekonsiliasi AR tetap utuh.

  P5.4  INV/2026/00003 status cancel (Rp 5,2 jt) menyisakan baris 1102.01
        -> hapus (cancel + tidak ada rekonsiliasi)

  P5.5  Nama 59 sesi POS = '/' dan ref JE POSS juga '/'
        -> beri nama "<Config> - <tanggal>", sinkronkan ref JE

  P5.6  Rapikan nama akun legacy (11210010, 11120003) supaya jelas tidak dipakai

Jalankan (pola repo §2 PROGRESS_DASHBOARD.md):

  # DRY-RUN
  su odoo -s /bin/bash -c "cd /workspaces/odoo-test && odoo shell -d Test1 --no-http \\
      --db_host db --db_port 5432 --db_user odoo --db_password odoo" < scripts/juni_juli_06_fix_august.py

  # EKSEKUSI
  su odoo -s /bin/bash -c "cd /workspaces/odoo-test && RUN=1 odoo shell -d Test1 --no-http \\
      --db_host db --db_port 5432 --db_user odoo --db_password odoo" < scripts/juni_juli_06_fix_august.py
"""
import os
from collections import defaultdict

from odoo.exceptions import UserError

RUN = os.environ.get("RUN") == "1"
AUG_FROM, AUG_TO = "2026-08-01", "2026-09-01"
AUG_LAST = "2026-08-31"

AM = env["account.move"]
AA = env["account.account"]
Sess = env["pos.session"]
Pay = env["pos.payment"]
log = []


def say(m=""):
    log.append(m)
    print(m)


def dry(msg):
    say("   %s %s" % ("[EXEC]" if RUN else "[DRY ]", msg))


def acc(code):
    """account.account search by kode — 'code' bukan kolom SQL di Odoo 19."""
    env.cr.execute(
        "SELECT id FROM account_account WHERE code_store->>'1' = %s LIMIT 1", (code,))
    r = env.cr.fetchone()
    return AA.browse(r[0]) if r else AA.browse()


# ---------------------------------------------------------------------------
say("=" * 78)
say("P5 — PERBAIKAN DATA AGUSTUS 2026   |   RUN=%s" % RUN)
say("=" * 78)

# --- baseline yang harus tidak berubah -------------------------------------
def tb_snapshot():
    cr = env.cr
    cr.execute("""SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0)
                  FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                  WHERE am.state='posted'""")
    d, k = cr.fetchone()
    return d, k


tb_before = tb_snapshot()
say("Baseline TB: debit=%s credit=%s diff=%s" % (
    "{:,.2f}".format(tb_before[0]), "{:,.2f}".format(tb_before[1]),
    "{:,.2f}".format(tb_before[0] - tb_before[1])))

# ---------------------------------------------------------------------------
say("")
say("--- P5.1  Outstanding Receipts: geser settlement 1 Sep -> 31 Agu ---")
settle = AM.search([("date", "=", "2026-09-01"), ("state", "=", "posted")])
ardir = acc("1103.06")
total_settle = 0.0
for m in settle:
    amt = -sum(l.balance for l in m.line_ids if l.account_id == ardir)
    total_settle += amt
    dry("%-24s jr=%-5s %s -> %s  (%s)  hash=%s" % (
        m.name, m.journal_id.code, m.date, AUG_LAST, "{:,.2f}".format(amt),
        m.journal_id.restrict_mode_hash_table))
    if RUN:
        # 'date' readonly utk move posted; pakai context resmi Odoo, bukan draft/repost
        # (draft+repost akan membuat ulang nomor sequence).
        m.with_context(skip_readonly_check=True).write({"date": AUG_LAST})
say("   total digeser: %s dari %d move" % ("{:,.2f}".format(total_settle), len(settle)))

# ---------------------------------------------------------------------------
say("")
say("--- P5.2  Konsolidasi akun AR PoS ---")
acc_old = acc("11210011")     # histori
acc_new = acc("1102.04")      # 0 baris
if not acc_old or not acc_new:
    raise UserError("Akun 11210011 / 1102.04 tidak ditemukan")

canon_name = "Piutang Usaha (PoS)"
dry("11210011 -> active=True, name=%r  (sebelum: active=%s name=%r)" % (
    canon_name, acc_old.active, acc_old.name))
dry("1102.04  -> active=False  (baris jurnal: %d)" % env["account.move.line"].search_count(
    [("account_id", "=", acc_new.id), ("debit", "!=", 0)]))
dry("company.account_default_pos_receivable_account_id -> %s" % acc_old.display_name)
if RUN:
    acc_old.write({"active": True, "name": canon_name})
    env.company.write({"account_default_pos_receivable_account_id": acc_old.id})
    if acc_new.id != acc_old.id:
        acc_new.write({"active": False})

# ---------------------------------------------------------------------------
say("")
say("--- P5.3  Rapikan label metode bayar di baris AR JE sesi (59 sesi) ---")
LEGACY = {
    "BCA": "Kartu", "BNI": "Kartu", "BRI": "Kartu", "Mandiri": "Kartu",
    "OVO": "QRIS", "GO-PAY": "QRIS",
    "ShopeePay": "ShopeeFood (Delivery)",
}
sess = Sess.search([("start_at", ">=", AUG_FROM), ("start_at", "<", AUG_TO)], order="start_at")
ar_acc_id = acc_old.id
n_line, n_fix, bad_before, bad_after = 0, 0, 0, 0
per_session = []
for s in sess:
    lines = s.move_id.line_ids.filtered(lambda l: l.account_id.id == ar_acc_id)
    n_line += len(lines)
    pay_map = defaultdict(float)
    for p in Pay.search([("session_id", "=", s.id)]):
        pay_map[p.payment_method_id.name] += p.amount
    jel_map = defaultdict(float)
    for l in lines:
        nm = (l.name or "").split(" - ", 1)[-1]
        jel_map[nm] += (l.debit or 0)
    if set(jel_map) != set(pay_map):
        bad_before += 1
    if RUN:
        for l in lines:
            nm = (l.name or "").split(" - ", 1)[-1]
            if nm in LEGACY:
                l.write({"name": "%s - %s" % (s.name or "/", LEGACY[nm])})
                n_fix += 1
    # simulasi hasil
    fix_map = defaultdict(float)
    for nm, amt in jel_map.items():
        fix_map[LEGACY.get(nm, nm)] += amt
    if set(fix_map) != set(pay_map):
        bad_after += 1
        per_session.append((s.id, dict(fix_map), dict(pay_map)))
say("   baris AR diperiksa: %d | akan diganti nama: %d" % (n_line, n_fix if RUN else n_line))
say("   sesi tidak konsisten: SEBELUM=%d  SESUDAH=%d (dari %d sesi)" % (
    bad_before, bad_after, len(sess)))
for sid, fm, pm_ in per_session[:3]:
    say("      sesi %s sisa beda: %s vs %s" % (sid, sorted(fm), sorted(pm_)))

# ---------------------------------------------------------------------------
say("")
say("--- P5.4  Hapus invoice batal INV/2026/00003 ---")
inv = AM.search([("name", "=", "INV/2026/00003")], limit=1)
if not inv:
    say("   tidak ditemukan — dilewati")
else:
    rec = [bool(x.reconciled) for x in inv.line_ids]
    say("   %s state=%s partner=%s total=%s reconciled=%s" % (
        inv.name, inv.state, inv.partner_id.name, "{:,.2f}".format(inv.amount_total), rec))
    if inv.state != "cancel":
        say("   !! state bukan cancel — DILEWATI (perlu keputusan manual)")
    elif any(rec):
        say("   !! ada baris terekonsiliasi — DILEWATI")
    else:
        dry("unlink %s + %d baris" % (inv.name, len(inv.line_ids)))
        if RUN:
            inv.unlink()

# ---------------------------------------------------------------------------
say("")
say("--- P5.5  Nama sesi POS + ref JE ---")
names = defaultdict(int)
plan_names = []
for s in sess:
    base = "%s - %s" % (s.config_id.name, s.start_at.date())
    names[base] += 1
    nm = base if names[base] == 1 else "%s (%d)" % (base, names[base])
    plan_names.append((s, nm))
say("   akan dinamai ulang: %d sesi (contoh: %s)" % (
    sum(1 for s, n in plan_names if s.name != n),
    plan_names[0][1] if plan_names else "-"))
if RUN:
    for s, nm in plan_names:
        if s.name != nm:
            s.write({"name": nm})
        if s.move_id and s.move_id.ref != nm:
            s.move_id.write({"ref": nm})

# ---------------------------------------------------------------------------
say("")
say("--- P5.6  Rapikan nama akun legacy ---")
for code, newname in (("11210010", "Account Receivable (legacy, tidak dipakai)"),
                      ("11120003", "Tanda Terima Belum Lunas (legacy, tidak dipakai)")):
    a = acc(code)
    if not a:
        continue
    dry("%s %r -> %r (active=%s)" % (code, a.name, newname, a.active))
    if RUN:
        a.write({"name": newname})

# ---------------------------------------------------------------------------
say("")
say("=" * 78)
say("VERIFIKASI")
cr = env.cr
if RUN:
    env.cr.commit()
    env.invalidate_all()

for label, asof in (("31 Agu 2026", AUG_LAST), ("sekarang", "2099-12-31")):
    cr.execute("""
        SELECT COALESCE(SUM(aml.balance),0)
        FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
        JOIN account_account aa ON aa.id=aml.account_id
        WHERE am.state='posted' AND am.date <= %s AND aa.account_type='asset_receivable'
    """, (asof,))
    piutang = cr.fetchone()[0]
    cr.execute("""
        SELECT COALESCE(SUM(aml.balance),0)
        FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
        WHERE am.state='posted' AND am.date <= %s
          AND aml.account_id IN (SELECT id FROM account_account
                                 WHERE code_store->>'1' IN ('1103.06','11210011'))
    """, (asof,))
    out = cr.fetchone()[0]
    say("   %-12s piutang(asset_receivable)=%16s | 1103.06+11210011=%16s" % (
        label, "{:,.2f}".format(piutang), "{:,.2f}".format(out)))

tb_after = tb_snapshot()
say("   TB   sebelum diff=%s | sesudah diff=%s" % (
    "{:,.2f}".format(tb_before[0] - tb_before[1]),
    "{:,.2f}".format(tb_after[0] - tb_after[1])))
say("   Total TB: %s -> %s" % (
    "{:,.2f}".format(tb_before[0]), "{:,.2f}".format(tb_after[0])))

aug = env["pos.order"].search([("date_order", ">=", AUG_FROM), ("date_order", "<", AUG_TO)])
say("   AGUSTUS: %d order, omzet %s (harus TIDAK berubah)" % (
    len(aug), "{:,.2f}".format(sum(aug.mapped("amount_total")))))
say("   POSS move ref contoh: %s" % [m.ref for m in sess.mapped("move_id")[:3]])
say("   nama sesi contoh   : %s" % [s.name for s in sess[:3]])
say("   akun AR kanonik    : %s | active=%s" % (
    env.company.account_default_pos_receivable_account_id.display_name,
    env.company.account_default_pos_receivable_account_id.active))
say("=" * 78)
if not RUN:
    env.cr.rollback()
    say("DRY-RUN — tidak ada data ditulis. Jalankan ulang dgn RUN=1 untuk eksekusi.")
