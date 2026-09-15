# -*- coding: utf-8 -*-
"""
settlement_10hari_plus_sweep.py — Settlement outstanding 1103.06 + Sweep wallet -> Bank per 10 hari

Solusi untuk Bank BSI tetap minus -62jt setelah sweep 10 hari:
  Masalah: outstanding 1103.06 (POS) hanya disettle bulanan (30 Jun,31 Jul,31 Agu), jadi
  wallet QRIS/OVO dll tidak dapat dana tengah bulan, sementara pembelian fresh tiap 3 hari.
  -> wallets kosong tengah bulan, Bank minus karena beli pakai Bank.

Perbaikan: settle outstanding tiap 10 hari juga (sinkron sweep), jadi uang POS cair ke wallet tiap 10 hari,
lalu sweep wallet 95% ke Bank tiap 10 hari juga -> Bank terisi rutin.

Tanggal settle+sweep: 30 Jun, 10 Jul,20 Jul,31 Jul,10 Agu,20 Agu,31 Agu (7 titik)
+ juga 23 Jun,27 Jun untuk tutup minus awal? Kita tambah 2 ekstra di Juni akhir untuk hilangkan -17jt 27-29 Jun.

Aksi idempotent: hapus semua JE lama ref Settlement outstanding 1103.06% + Pencairan Wallet 10hari%/bulanan,
lalu buat ulang per bucket 10 hari.

  dry-run: cat scripts/settlement_10hari_plus_sweep.py | odoo shell -d Test1 ...
  RUN=1 : RUN=1 cat scripts/settlement_10hari_plus_sweep.py | odoo shell -d Test1 ...
"""
import os
RUN = os.environ.get("RUN")=="1"
SWEEP_RATE = 0.95
cr = env.cr
AM = env["account.move"]
AJ = env["account.journal"]
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

# Dates aligned to cover purchases: Juni 23,27,30 extra to handle early minus
SETTLE_DATES = [
    "2026-06-23",  # extra: tutup minus Juni 23 purchase
    "2026-06-27",  # extra
    "2026-06-30",
    "2026-07-10", "2026-07-20", "2026-07-31",
    "2026-08-10", "2026-08-20", "2026-08-31",
]
# Sweep same dates (settle dulu, lalu sweep)
SWEEP_DATES = SETTLE_DATES

OUT_ACC = None
cr.execute("SELECT id FROM account_account WHERE code_store->>'1'='1103.06' LIMIT 1")
OUT_ACC = cr.fetchone()[0]
if not OUT_ACC:
    raise SystemExit("1103.06 tidak ada")

WALLETS = {
    210: ("1101.02","QRIS"),
    211: ("1101.03","OVO/GoFood"),
    212: ("1101.04","GOPAY/GrabFood"),
    213: ("1101.05","SHOPEE PAY"),
}
BANK = 122

def acc_balance(acc_id, date_to):
    cr.execute("SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id WHERE aml.account_id=%s AND am.state='posted' AND am.date <= %s",(acc_id,date_to))
    return float(cr.fetchone()[0] or 0)

say("="*120)
say("SETTLEMENT + SWEEP 10 HARI (PLUS JUNI 23,27) | RUN=%s | OUT %s | BANK %s | rate %.0f%%" % (RUN, OUT_ACC, BANK, SWEEP_RATE*100))
say("Settle dates: %s" % ", ".join(SETTLE_DATES))
say("Sweep dates: %s" % ", ".join(SWEEP_DATES))
say("="*120)

cr.execute("UPDATE account_journal SET restrict_mode_hash_table=false WHERE code IN ('BNK1','BNKB','QRIW','OVOW','GPYW','SPPW','MISC','POSS')")
misc = AJ.search([("code","=","MISC")],limit=1)
say("MISC id %s" % misc.id)

# check existing
old_settle = AM.search([("ref","like","Settlement outstanding 1103.06%")])
old_sweep_monthly = AM.search([("ref","like","Pencairan Wallet ke Bank BSI%")])
old_sweep_10 = AM.search([("ref","like","Pencairan Wallet 10hari%")])
old_settle_new = AM.search([("ref","like","Settlement 10hari%")])
say("Existing: settle old %d + sweep monthly %d + sweep 10hari %d + settle new %d = %d JE" % (len(old_settle),len(old_sweep_monthly),len(old_sweep_10),len(old_settle_new),len(old_settle)+len(old_sweep_monthly)+len(old_sweep_10)+len(old_settle_new)))

if not RUN:
    # show outstanding per bucket if we were to settle per date
    say("")
    say("[DRY-RUN ESTIMASI] Outstanding 1103.06 per bucket (jika settle 10 hari):")
    prev = "2026-06-19"
    for d_to in SETTLE_DATES:
        cr.execute("""
            SELECT aj.code, sum(aml.balance) FROM account_move_line aml
            JOIN account_move am ON am.id=aml.move_id
            JOIN account_journal aj ON aj.id=am.journal_id
            WHERE aml.account_id=%s AND am.state='posted' AND am.date > %s AND am.date <= %s
            GROUP BY 1 ORDER BY 1
        """,(OUT_ACC, prev, d_to))
        rows=cr.fetchall()
        tot=sum(v for _,v in rows) if rows else 0
        say("  %s -> %s : total outstanding %s %s" % (prev, d_to, money(tot), ", ".join("%s %s"%(c,money(v)) for c,v in rows) if rows else "(0)"))
        prev=d_to
    # also wallet estimate
    say("")
    say("[BANK MINUS CHECK BEFORE] terendah saat ini:")
    cr.execute("""
        SELECT d::date, sum(h) OVER (ORDER BY d) as cum FROM (
         SELECT am.date as d, sum(aml.balance)::bigint as h
         FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id JOIN account_account aa ON aa.id=aml.account_id
         WHERE aa.code_store->>'1'='1101.01' AND am.state='posted' GROUP BY 1
        ) t ORDER BY d
    """)
    rows=cr.fetchall()
    mins=min(v for _,v in rows)
    worst=min(rows, key=lambda x: x[1])
    say("  Terendah %s pada %s" % (money(mins), worst[0]))
    say("")
    say("DRY-RUN — tidak menulis. RUN=1 untuk eksekusi (hapus lama + buat %d settle + %d sweep = %d JE)" % (len(SETTLE_DATES)*6, len(SWEEP_DATES), len(SETTLE_DATES)*6 + len(SWEEP_DATES)))
    env.cr.rollback()
    import sys; sys.exit(0)

# --- EKSEKUSI: hapus semua lama ---
say("")
say("[EKSEKUSI] Hapus %d JE lama (settle + sweep)" % (len(old_settle)+len(old_sweep_monthly)+len(old_sweep_10)+len(old_settle_new)))
to_del = old_settle + old_sweep_monthly + old_sweep_10 + old_settle_new
for m in to_del:
    try:
        if m.state=="posted":
            m.button_draft()
        m.unlink()
    except Exception as e:
        say("  gagal hapus %s: %s" % (m.name, e))
env.cr.commit()
say("  Dihapus, commit")

# --- Recreate settlement per bucket ---
say("")
say("[1] Buat Settlement Outstanding -> Wallet per 10 hari")
created_settle=0
prev = "2026-06-19"
for d_to in SETTLE_DATES:
    # For each journal, sum outstanding in bucket (prev, d_to]
    cr.execute("""
        SELECT aj.id as jid, aj.code, aj.default_account_id, sum(aml.balance) as bal
        FROM account_move_line aml
        JOIN account_move am ON am.id=aml.move_id
        JOIN account_journal aj ON aj.id=am.journal_id
        WHERE aml.account_id=%s AND am.state='posted' AND am.date > %s AND am.date <= %s
        GROUP BY 1,2,3 HAVING sum(aml.balance) > 0.5
        ORDER BY 2
    """,(OUT_ACC, prev, d_to))
    rows=cr.fetchall()
    if not rows:
        say("  %s -> %s : tidak ada outstanding" % (prev, d_to))
        prev=d_to
        continue
    tot=sum(r[3] for r in rows)
    say("  %s -> %s : %d journal total %s" % (prev, d_to, len(rows), money(tot)))
    for jid, code, def_acc, bal in rows:
        if not def_acc:
            say("    %s skip no default_account" % code)
            continue
        # buat JE settlement: Dr wallet default / Cr outstanding, di journal asli (jid) agar mutasi per journal jelas
        # Tapi untuk simplify, pakai journal asli (QRIW etc) — default_account adalah wallet asset cash, outstanding adalah 1103.06
        # Entry: Dr def_acc (wallet) / Cr OUT_ACC
        ref="Settlement 10hari %s %s (%s->%s)" % (code, d_to, prev, d_to)
        # cek existing? already deleted, so create
        j = AJ.browse(jid)
        lines=[
            (0,0,{"account_id":def_acc,"debit":bal,"credit":0.0,"name":"Settle %s %s" % (code, d_to)}),
            (0,0,{"account_id":OUT_ACC,"debit":0.0,"credit":bal,"name":"Settle %s %s" % (code, d_to)}),
        ]
        mv=AM.create({"journal_id":jid,"date":d_to,"ref":ref,"line_ids":lines})
        mv.action_post()
        # say detail
        # verify
        created_settle+=1
    env.cr.commit()
    prev=d_to
say("  Total settlement JE dibuat: %d" % created_settle)

# --- Now sweep wallets -> Bank per sweep date ---
say("")
say("[2] Buat Sweep Wallet -> Bank 95% per 10 hari")
created_sweep=0
for d_to in SWEEP_DATES:
    tot_wallet_before = sum(acc_balance(a,d_to) for a in WALLETS)
    # sweep 95% of each wallet
    lines=[]
    total=0.0
    for acc_id,(code,name) in WALLETS.items():
        bal=acc_balance(acc_id,d_to)
        if bal < 1000:
            continue
        amt=round(bal*SWEEP_RATE,2)
        if amt<0.01:
            continue
        total+=amt
        lines.append((0,0,{"account_id":acc_id,"debit":0.0,"credit":amt,"name":"Sweep %s 10hari %s 95%%" % (name,d_to)}))
    if total<0.01:
        say("  %s wallet 0 -> skip" % d_to)
        continue
    lines.insert(0,(0,0,{"account_id":BANK,"debit":total,"credit":0.0,"name":"Sweep wallets -> Bank 10hari %s" % d_to}))
    ref="Pencairan Wallet 10hari %s" % d_to
    mv=AM.create({"journal_id":misc.id,"date":d_to,"ref":ref,"line_ids":lines})
    mv.action_post()
    say("  %s sweep %s (wallet before %s, sisa 5%% %s) JE %s" % (d_to, money(total), money(tot_wallet_before), money(tot_wallet_before-total), mv.name))
    created_sweep+=1
    env.cr.commit()
say("  Total sweep JE: %d" % created_sweep)

# --- Verifikasi ---
say("")
say("[VERIFIKASI] Setelah settle+sweep 10 hari")
cr.execute("SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id WHERE aml.account_id=%s AND am.state='posted'",(OUT_ACC,))
out_bal=float(cr.fetchone()[0] or 0)
say("  Outstanding 1103.06: %s %s" % (money(out_bal), "OK 0" if abs(out_bal)<0.01 else ">>>"))
for acc_id,(code,name) in WALLETS.items():
    bal=acc_balance(acc_id,"2026-08-31")
    say("  Wallet %-12s %s %s" % (code, money(bal), name))
bank_final=acc_balance(BANK,"2026-08-31")
say("  Bank BSI final s/d 31 Agu: %s" % money(bank_final))
# per sweep date kas check
say("  Per sweep date kas check (asset_cash):")
for d_to in SWEEP_DATES:
    cr.execute("""
        SELECT COUNT(*) FROM (
         SELECT aa.id FROM account_move_line aml
         JOIN account_move am ON am.id=aml.move_id
         JOIN account_account aa ON aa.id=aml.account_id
         WHERE aa.account_type='asset_cash' AND am.state='posted' AND am.date <= %s
         GROUP BY 1 HAVING SUM(aml.balance) < -0.01) x
    """,(d_to,))
    neg=cr.fetchone()[0]
    cr.execute("SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id JOIN account_account aa ON aa.id=aml.account_id WHERE aa.account_type='asset_cash' AND am.state='posted' AND am.date <= %s",(d_to,))
    kas=float(cr.fetchone()[0] or 0)
    say("    %s kas %s negatif %d %s" % (d_to, money(kas), neg, "OK" if neg==0 else "<<<"))
# daily Bank BSI running min
cr.execute("""
    SELECT d::date, sum(h) OVER (ORDER BY d) as cum FROM (
     SELECT am.date as d, sum(aml.balance)::bigint as h
     FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id JOIN account_account aa ON aa.id=aml.account_id
     WHERE aa.code_store->>'1'='1101.01' AND am.state='posted' GROUP BY 1
    ) t ORDER BY d
""")
rows=cr.fetchall()
mins=min(v for _,v in rows)
worst=min(rows, key=lambda x: x[1])
say("  Bank BSI terendah harian: %s pada %s %s" % (money(mins), worst[0], "OK >=0" if mins>=0 else "<<< MASIH MINUS"))
# also check all cash accounts min
cr.execute("""
    SELECT d::date, sum(h) OVER (ORDER BY d) as cum FROM (
     SELECT am.date as d, sum(aml.balance)::bigint as h
     FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id JOIN account_account aa ON aa.id=aml.account_id
     WHERE aa.account_type='asset_cash' AND am.state='posted' GROUP BY 1
    ) t ORDER BY d
""")
rows2=cr.fetchall()
mins2=min(v for _,v in rows2)
say("  Total kas terendah: %s (akhir %s)" % (money(mins2), money(rows2[-1][1])))
# TB
cr.execute("SELECT sum(debit),sum(credit) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id WHERE am.state='posted'")
d,c=cr.fetchone()
say("  TB debit %s credit %s diff %s %s" % (money(d),money(c),money(float(d or 0)-float(c or 0)),"OK" if abs(float(d or 0)-float(c or 0))<0.01 else ">>>"))
# L/R
for d_from,d_to,label in [("2026-06-20","2026-06-30","Juni 20-30"),("2026-07-01","2026-07-31","Juli"),("2026-08-01","2026-08-31","Agustus")]:
    cr.execute("SELECT COALESCE(-SUM(aml.balance),0) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id JOIN account_account aa ON aa.id=aml.account_id WHERE aa.account_type LIKE 'income%%' AND am.state='posted' AND am.date >= %s AND am.date <= %s",(d_from,d_to))
    inc=float(cr.fetchone()[0] or 0)
    cr.execute("SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id JOIN account_account aa ON aa.id=aml.account_id WHERE aa.account_type='expense_direct_cost' AND am.state='posted' AND am.date >= %s AND am.date <= %s",(d_from,d_to))
    hpp=float(cr.fetchone()[0] or 0)
    cr.execute("SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id JOIN account_account aa ON aa.id=aml.account_id WHERE aa.account_type IN ('expense','expense_depreciation') AND am.state='posted' AND am.date >= %s AND am.date <= %s",(d_from,d_to))
    opex=float(cr.fetchone()[0] or 0)
    laba=inc-hpp-opex
    say("  %-12s inc %12s HPP %12s (%.1f%%) OPEX %12s Laba %12s (%.1f%%)" % (label,money(inc),money(hpp),100*hpp/inc if inc else 0,money(opex),money(laba),100*laba/inc if inc else 0))
say("="*120)
env.cr.commit()
