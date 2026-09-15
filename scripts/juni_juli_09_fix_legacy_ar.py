# -*- coding: utf-8 -*-
"""
juni_juli_09_fix_legacy_ar.py — betulkan akun 11210010 & 11120003.

Temuan: P5.6 menamai keduanya "(legacy, tidak dipakai)" — SALAH. Keduanya dipakai
oleh 2 invoice catering korporat Agustus:

  INV/2026/00001 (8 Agu)  Dr 11210010 4.750.000 / Cr 4101.02
  INV/2026/00002 (14 Agu) Dr 11210010 2.850.000 / Cr 4101.02
  PBNK1/00031,00032       Dr 11120003 / Cr 11210010   (pelunasan)
  MISC/2026/08/0036       Dr 1101.01 7.600.000 / Cr 11120003

Keduanya bersaldo 0 dan `active=False` -> persis kelas masalah Bank BNI (P1).

Strategi:
  * Kalau baris AR-nya TIDAK terekonsiliasi -> konsolidasi ke akun kanonik
    (11210010 -> 1102.01 Piutang Usaha, 11120003 -> 1103.06 Outstanding Receipts)
    supaya akun legacy benar-benar kosong dan bisa tetap nonaktif.
  * Kalau TEREKONSILIASI -> jangan disentuh (rewrite akan memutus rekonsiliasi);
    cukup diaktifkan kembali + diberi nama yang jujur.

  RUN=1   eksekusi  (default: dry-run)
"""
import os

RUN = os.environ.get("RUN") == "1"
cr = env.cr
AA = env["account.account"]
AML = env["account.move.line"]

MAP = [
    ("11210010", "1102.01", "Piutang Usaha (Catering B2B)"),
    ("11120003", "1103.06", "Tanda Terima Belum Lunas (Catering)"),
]


def acc(code):
    cr.execute("SELECT id FROM account_account WHERE code_store->>'1'=%s LIMIT 1", (code,))
    r = cr.fetchone()
    return AA.browse(r[0]) if r else AA.browse()


print("=" * 78)
print("PERBAIKAN AKUN LEGACY AR   |   RUN=%s" % RUN)
print("=" * 78)

for legacy_code, canon_code, name in MAP:
    leg = acc(legacy_code)
    can = acc(canon_code)
    lines = AML.search([("account_id", "=", leg.id)])
    lines_bal = sum(lines.mapped("balance"))
    rec = [l for l in lines if l.reconciled]
    moves = lines.move_id
    print("")
    print("akun %s %r (active=%s)" % (legacy_code, leg.name, leg.active))
    print("   baris=%d | saldo=%s | terekonsiliasi=%d/%d" % (
        len(lines), "{:,.2f}".format(lines_bal), len(rec), len(lines)))
    print("   move: %s" % sorted(set(moves.mapped("name"))))
    print("   kanonik %s %r (active=%s)" % (canon_code, can.name, can.active))

    if not lines:
        print("   -> tidak ada baris; cukup nonaktifkan + nama jujur")
        if RUN:
            leg.write({"active": False, "name": name + " (legacy, kosong)"})
        continue

    if rec:
        print("   -> ada baris TEREKONSILIASI: rewrite DIBATALKAN (akan memutus rekonsiliasi)")
        print("   -> tindakan: aktifkan kembali + beri nama jujur")
        if RUN:
            if not leg.active:
                leg.write({"active": True})
            leg.write({"name": name})
        print("      active=%s name=%r" % ("True (diaktifkan)" if RUN else True, name))
    else:
        print("   -> tidak terekonsiliasi: konsolidasi %d baris ke %s" % (len(lines), canon_code))
        if RUN:
            for l in lines:
                l.with_context(skip_readonly_check=True).write({"account_id": can.id})
            leg.write({"active": False, "name": name + " (legacy, kosong)"})

print("")
print("=" * 78)
print("VERIFIKASI")
if RUN:
    env.cr.commit()
    env.invalidate_all()

for legacy_code, canon_code, name in MAP:
    leg = acc(legacy_code)
    print("   %s %-46s active=%-5s baris=%-4d saldo=%s" % (
        legacy_code, (leg.name or "")[:46], leg.active,
        AML.search_count([("account_id", "=", leg.id)]),
        "{:,.2f}".format(sum(AML.search([("account_id", "=", leg.id)]).mapped("balance")))))

print("")
print("audit: akun NONAKTIF yang masih dipakai di jurnal posted")
cr.execute("""
    SELECT aa.code_store->>'1', aa.name->>'en_US', aa.active, COUNT(*), COALESCE(SUM(aml.balance),0)
    FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
    JOIN account_account aa ON aa.id=aml.account_id
    WHERE am.state='posted' AND aa.active = false
    GROUP BY 1,2,3 ORDER BY 4 DESC
""")
rows = cr.fetchall()
if not rows:
    print("   (bersih)")
for r in rows:
    print("   %-10s %-44s baris=%-5s saldo=%s" % (
        r[0], (r[1] or "")[:44], r[3], "{:,.2f}".format(r[4] or 0)))

cr.execute("""SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) FROM account_move_line aml
              JOIN account_move am ON am.id=aml.move_id WHERE am.state='posted'""")
d, k = cr.fetchone()
print("   TB debit=%s credit=%s diff=%s" % (
    "{:,.2f}".format(d), "{:,.2f}".format(k), "{:,.2f}".format(d - k)))
print("=" * 78)
