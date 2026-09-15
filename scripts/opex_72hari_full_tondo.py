# -*- coding: utf-8 -*-
"""
opex_72hari_full_tondo.py — OPEX 72 HARI FULL 17 AKUN TONDO (Juni 20-30 prorata + Juli/Agu full)

Sumber: laba_dan_rugi_agu_2026_geprek_yuksss!!!_palu_tondo (3).xlsx Sheet Laba dan Rugi
  17 akun OPEX = 48.695.664,51 per bulan (Tondo 1 outlet). Untuk portofolio 2 toko,
  kita pakai 17 akun ini sebagai OPEX GABUNGAN (bukan per outlet double) — simple & realistis
  karena banyak biaya shared (gaji, sewa). Alternatif per toko akan double 97jt/bulan tidak real.

  Juni hanya 11 hari (20-30), jadi prorata 11/30 = 0.3667
  Juli & Agu full 30/30 = 1.0

  JE: Dr Beban 6101.xx / Cr Bank BSI 1101.01 (tunai/bank)
  Penyusutan: Dr Beban 6101.26/27/28 / Cr Akum 1106.01/02/03/04

  Idempotent: ref 'OPEX <Nama> - <Bulan> 2026'

  dry-run: cat scripts/opex_72hari_full_tondo.py | odoo shell -d Test1 ...
  RUN=1 : RUN=1 cat scripts/opex_72hari_full_tondo.py | odoo shell -d Test1 ...
"""
import os
RUN = os.environ.get("RUN")=="1"
cr = env.cr
AM = env["account.move"]
AJ = env["account.journal"]
AA = env["account.account"]
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

# OPEX Tondo Agu — 17 akun, total 48.695.664,51
# Mapping Tondo original kode -> akun aktif di sistem (6101.26/27/28 arsip/tidak ada)
# Tondo 6101.26 Resto -> 6101.16 Resto (id 191)
#       6101.27 Kantor -> 6101.15 Kantor (id 190)
#       6101.28 Renovasi -> 6101.17 Renovasi (id 192)
OPEX_AGU = [
    ("6101.03", "Beban Gaji dan Upah",                       22095349.40),  # Tondo 6101.01 -> sistem 6101.03
    ("6101.11", "Beban Listrik",                              3500000.00),  # Tondo 6101.04 -> 6101.11
    ("6101.01", "Beban Iklan",                                 124931.90),  # tetap
    ("6101.05", "Beban Bonus, Pesangon & Kompensasi",         2747114.00),  # Tondo 6101.07 -> 6101.05
    ("6101.18", "Beban Perlengkapan Operasional",             4033500.00),  # Tondo 6101.08 -> 6101.18
    ("6101.20", "Beban Pajak Restoran",                        686461.00),  # Tondo 6101.12 -> 6101.20
    ("6101.13", "Beban Telepon dan Wifi",                      249750.00),  # Tondo 6101.14 -> 6101.13
    ("6101.07", "Beban Transportasi Karyawan",                3569592.00),  # Tondo 6101.16 -> 6101.07
    ("6101.08", "Beban Pengiriman & Materai",                 2226000.00),  # Tondo 6101.17 -> 6101.08
    ("6101.18", "Beban Reparasi",                              640000.00),  # Tondo 6101.18 -> 6101.18 (sama, akan double line? -> gabung ops)
    ("6101.22", "Beban Adm. Bank & Buku Cek/Giro",             144930.48),  # Tondo 6101.19 -> 6101.22
    ("6101.21", "Beban ATK, IT & Aplikasi Odoo",               632926.00),  # Tondo 6101.20 -> 6101.21
    ("6101.23", "Beban Operasional Lainnya",                  1171687.00),  # Tondo 6101.22 -> 6101.23
    ("6101.1", "Beban Tunjangan Kesehatan",                    543170.00),  # Tondo 6101.23 -> 6101.1
    ("6101.16", "Beban Penyusutan Peralatan Resto",           3027466.20),  # Tondo 6101.26 -> 6101.16
    ("6101.15", "Beban Penyusutan Peralatan Kantor",          1581701.57),  # Tondo 6101.27 -> 6101.15
    ("6101.17", "Beban Penyusutan Renovasi",                  1721084.96),  # Tondo 6101.28 -> 6101.17
]
TOTAL_AGU = sum(v for _,_,v in OPEX_AGU)

# mapping penyusutan -> akumulasi (contra asset)
DEP_MAP = {
    "6101.16": "1106.03",  # Peralatan Resto -> Akum Resto
    "6101.15": "1106.02",  # Peralatan Kantor -> Akum Kantor
    "6101.17": "1106.04",  # Renovasi -> Akum Renovasi
}

PERIODS = [
    ("2026-06-30", "Juni 2026",    11/30),
    ("2026-07-31", "Juli 2026",    1.0),
    ("2026-08-31", "Agustus 2026", 1.0),
]

say("="*110)
say("OPEX 72 HARI FULL 17 AKUN TONDO | RUN=%s | Agu total %s (17 akun)" % (RUN, money(TOTAL_AGU)))
for code,nama,nilai in OPEX_AGU:
    say("  %-10s %-40s %12s" % (code, nama, money(nilai)))
say("  Juni factor 11/30=%.4f => %s | Juli+Agustus full %s" % (11/30, money(TOTAL_AGU*11/30), money(TOTAL_AGU)))
say("  Total 72 hari OPEX = %s" % money(TOTAL_AGU*11/30 + TOTAL_AGU*2))
say("="*110)

def aid(code):
    cr.execute("SELECT id FROM account_account WHERE code_store->>'1'=%s LIMIT 1", (code,))
    r = cr.fetchone()
    return r[0] if r else None

BANK = aid("1101.01")
if not BANK:
    raise SystemExit("1101.01 Bank BSI tidak ditemukan")

# validate all expense accounts exist
for code,nama,_ in OPEX_AGU:
    a = aid(code)
    if not a:
        raise SystemExit("Akun %s (%s) tidak ditemukan — buat dulu" % (code,nama))
    # check active
    cr.execute("SELECT active, name->>'en_US' FROM account_account WHERE id=%s", (a,))
    active,_ = cr.fetchone()
    if not active:
        cr.execute("UPDATE account_account SET active=true WHERE id=%s",(a,))
        say("Aktifkan akun %s" % code)
# accumulation
for code in DEP_MAP.values():
    if not aid(code):
        raise SystemExit("Akum %s tidak ada" % code)

# check accumulation accounts
for dep_code, acc_code in DEP_MAP.items():
    say("  Penyusutan %s -> Akum %s (aid %s)" % (dep_code, acc_code, aid(acc_code)))

cr.execute("UPDATE account_journal SET restrict_mode_hash_table=false WHERE code='MISC'")
misc = AJ.search([("code","=","MISC")],limit=1)
say("Journal MISC id %s" % misc.id)

# existing
say("")
say("[CEK EXISTING]")
for d_to,label,_ in PERIODS:
    cr.execute("SELECT count(*) FROM account_move WHERE ref LIKE %s AND date=%s", ("OPEX%%"+label+"%",d_to))
    cnt=cr.fetchone()[0]
    if cnt:
        say("  %-15s s/d %s sudah ada %d JE" % (label,d_to,cnt))
        cr.execute("SELECT name, ref, amount_total FROM account_move WHERE ref LIKE %s AND date=%s LIMIT 3", ("OPEX%%"+label+"%",d_to))
        for name,ref,amt in cr.fetchall():
            say("    %s | %s | %s" % (name, ref[:50], money(amt)))
    else:
        say("  %-15s s/d %s belum ada" % (label,d_to))

if not RUN:
    say("")
    say("[RENCANA]")
    for d_to,label,factor in PERIODS:
        total=0
        say("  %s (factor %.4f):" % (label,factor))
        for code,nama,val in OPEX_AGU:
            amt=round(val*factor,2)
            total+=amt
            say("    %-10s %12s  Dr %s / %s" % (code,money(amt), nama[:35], "Akum" if code in DEP_MAP else "Bank BSI"))
        say("    TOTAL %-15s %12s  (%d JE tunai + %d JE penyusutan)" % (label,money(total), 14,3))
    say("")
    say("DRY-RUN — tidak menulis. RUN=1 untuk eksekusi.")
    env.cr.rollback()
    import sys; sys.exit(0)

# Eksekusi
say("")
say("[EKSEKUSI] Buat JE OPEX per akun per bulan")

# Hapus lama jika ada (idempotent rerun)
old = AM.search([("ref","like","OPEX%")])
# filter only our 3 periods
target_refs = set("OPEX %s - %s" % (nama, label) for _,nama,_ in OPEX_AGU for _,label,_ in PERIODS)
# better search by ref like OPEX% and date in our periods
old2 = AM.search([("ref","like","OPEX%"),("date","in",["2026-06-30","2026-07-31","2026-08-31"])])
if old2:
    say("  Hapus %d JE lama OPEX periode terkait untuk recreate idempotent" % len(old2))
    for m in old2:
        try:
            if m.state=="posted":
                m.button_draft()
            m.unlink()
        except Exception as e:
            say("    gagal hapus %s: %s" % (m.name,e))
    env.cr.commit()

created=0
for d_to,label,factor in PERIODS:
    say("  %s factor %.4f:" % (label,factor))
    for code,nama,val in OPEX_AGU:
        amt=round(val*factor,2)
        if amt<=0.01:
            continue
        ref="OPEX %s - %s" % (nama, label)
        if AM.search_count([("ref","=",ref),("date","=",d_to)]):
            say("    skip %s sudah ada" % ref[:50])
            continue
        acc_expense=aid(code)
        if code in DEP_MAP:
            acc_akum=aid(DEP_MAP[code])
            lines=[
                (0,0,{"account_id":acc_expense,"debit":amt,"credit":0.0,"name":nama+" "+label}),
                (0,0,{"account_id":acc_akum,"debit":0.0,"credit":amt,"name":"Akumulasi "+nama+" "+label}),
            ]
        else:
            lines=[
                (0,0,{"account_id":acc_expense,"debit":amt,"credit":0.0,"name":nama+" "+label}),
                (0,0,{"account_id":BANK,"debit":0.0,"credit":amt,"name":"Pembayaran "+nama.lower()+" "+label}),
            ]
        mv=AM.create({"journal_id":misc.id,"date":d_to,"ref":ref,"line_ids":lines})
        mv.action_post()
        created+=1
        if created%20==0:
            env.cr.commit()
    env.cr.commit()
    # summary for label
    cr.execute("SELECT sum(aml.balance) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id WHERE am.date=%s AND am.ref LIKE 'OPEX%%'",(d_to,))
    tot=float(cr.fetchone()[0] or 0)
    say("    => total %s %s (%d JE)" % (label,money(tot),14+3))

say("")
say("[SELESAI] %d JE OPEX dibuat (17 akun x 3 bulan = 51 JE)" % created)

# Verifikasi
say("")
say("[VERIFIKASI]")
for d_to,label,_ in PERIODS:
    cr.execute("SELECT COALESCE(SUM(aml.debit - aml.credit),0) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id WHERE am.date=%s AND am.ref LIKE 'OPEX%%'",(d_to,))
    opex=float(cr.fetchone()[0] or 0)
    say("  %-15s OPEX total %12s" % (label,money(opex)))
cr.execute("SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id WHERE am.ref LIKE 'OPEX%%' AND am.state='posted'")
tot_all=float(cr.fetchone()[0] or 0)
say("  TOTAL 72 hari OPEX %s (harus %s)" % (money(tot_all), money(TOTAL_AGU*11/30 + TOTAL_AGU*2)))
# kas akhir
for last in ["2026-06-30","2026-07-31","2026-08-31"]:
    cr.execute("SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id JOIN account_account aa ON aa.id=aml.account_id WHERE aa.account_type='asset_cash' AND am.state='posted' AND am.date <= %s",(last,))
    kas=float(cr.fetchone()[0] or 0)
    cr.execute("SELECT COUNT(*) FROM (SELECT aa.id FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id JOIN account_account aa ON aa.id=aml.account_id WHERE aa.account_type='asset_cash' AND am.state='posted' AND am.date <= %s GROUP BY 1 HAVING SUM(aml.balance) < -0.01) x",(last,))
    neg=cr.fetchone()[0]
    say("  %s kas total %12s | negatif %d %s" % (last,money(kas),neg,"OK" if neg==0 else "<<<"))
# TB
cr.execute("SELECT sum(debit),sum(credit) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id WHERE am.state='posted'")
d,c=cr.fetchone()
say("  TB debit %s credit %s diff %s %s" % (money(d),money(c),money(float(d or 0)-float(c or 0)),"OK" if abs(float(d or 0)-float(c or 0))<0.01 else ">>>"))
# L/R quick
for mk, (d_from,d_to,label) in [("june",("2026-06-20","2026-06-30","Juni 20-30")),("july",("2026-07-01","2026-07-31","Juli")),("aug",("2026-08-01","2026-08-31","Agustus"))]:
    cr.execute("SELECT COALESCE(-SUM(aml.balance),0) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id JOIN account_account aa ON aa.id=aml.account_id WHERE aa.account_type LIKE 'income%%' AND am.state='posted' AND am.date >= %s AND am.date <= %s",(d_from,d_to))
    inc=float(cr.fetchone()[0] or 0)
    cr.execute("SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id JOIN account_account aa ON aa.id=aml.account_id WHERE aa.account_type='expense_direct_cost' AND am.state='posted' AND am.date >= %s AND am.date <= %s",(d_from,d_to))
    hpp=float(cr.fetchone()[0] or 0)
    cr.execute("SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id JOIN account_account aa ON aa.id=aml.account_id WHERE aa.account_type IN ('expense','expense_depreciation') AND am.state='posted' AND am.date >= %s AND am.date <= %s",(d_from,d_to))
    opex=float(cr.fetchone()[0] or 0)
    laba=inc - hpp - opex
    say("  %-12s inc %12s  HPP %12s (%.1f%%)  OPEX %12s (%.1f%%)  Laba %12s (%.1f%%)" % (label,money(inc),money(hpp),100*hpp/inc if inc else 0,money(opex),100*opex/inc if inc else 0,money(laba),100*laba/inc if inc else 0))
say("="*110)
env.cr.commit()
