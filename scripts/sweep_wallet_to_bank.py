# -*- coding: utf-8 -*-
"""
sweep_wallet_to_bank.py — Sweep 95% dari QRIS/OVO/GOPAY/SHOPEE ke Bank BSI tiap akhir bulan

Tujuannya: hilangkan saldo negatif Bank BSI (-312M) karena pembelian HPP fifo dari Bank
sedangkan omzet banyak nyangkut di wallet QRIS dkk (1.22M di QRIS). Di dunia nyata,
wallet dicairkan ke rekening bank harian/mingguan. Untuk portofolio, kita sweep 95% akhir bulan
(biar wallet tetap ada saldo kecil realistis).

- Dr Bank BSI 1101.01 / Cr QRIS 1101.02, OVO 1101.03, GOPAY 1101.04, SHOPEE 1101.05
- Tanggal: 30 Jun, 31 Jul, 31 Agu
- Sweep 95% saldo kumulatif s/d tanggal tsb (sisakan 5% untuk demo e-wallet masih ada)

Idempotent: hapus JE lama ref 'Pencairan Wallet ke Bank BSI%'

  dry-run: cat scripts/sweep_wallet_to_bank.py | odoo shell -d Test1 ...
  RUN=1 : RUN=1 cat scripts/sweep_wallet_to_bank.py | odoo shell -d Test1 ...
"""
import os
RUN = os.environ.get("RUN")=="1"
SWEEP_RATE = 0.95
cr = env.cr
AM = env["account.move"]
AJ = env["account.journal"]
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

PERIODS = [
    ("2026-06-30","Juni 2026"),
    ("2026-07-31","Juli 2026"),
    ("2026-08-31","Agustus 2026"),
]
WALLETS = {
    210: ("1101.02","QRIS"),
    211: ("1101.03","OVO/GoFood"),
    212: ("1101.04","GOPAY/GrabFood"),
    213: ("1101.05","SHOPEE PAY"),
}
BANK = 122 # 1101.01 default_account_id bank
BANK_CODE = "1101.01"

def acc_balance(acc_id, date_to):
    cr.execute("""
        SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml
        JOIN account_move am ON am.id=aml.move_id
        WHERE aml.account_id=%s AND am.state='posted' AND am.date <= %s
    """,(acc_id,date_to))
    return float(cr.fetchone()[0] or 0)

say("="*100)
say("SWEEP WALLET -> BANK BSI (95%%) | RUN=%s | rate %.0f%% | Bank %s (%s)" % (RUN, SWEEP_RATE*100, BANK, BANK_CODE))
say("="*100)

# hash
cr.execute("UPDATE account_journal SET restrict_mode_hash_table=false WHERE code IN ('BNK1','MISC')")
misc = AJ.search([("code","=","MISC")],limit=1)
if not misc:
    misc = AJ.search([("type","=","general")],limit=1)
say("Journal sweep pakai MISC id %s (%s)" % (misc.id, misc.name))

# existing
old = AM.search([("ref","like","Pencairan Wallet ke Bank BSI%")])
say("Existing sweep JE: %d" % len(old))
if old and RUN:
    # hapus untuk idempotent
    for m in old:
        try:
            if m.state=="posted":
                m.button_draft()
            m.unlink()
        except Exception as e:
            say("  gagal hapus %s: %s" % (m.name, e))
    env.cr.commit()
    say("  Dihapus untuk recreate")

# dry-run estimate
say("")
say("[ESTIMASI] Saldo wallet s/d tiap akhir bulan (sebelum sweep)")
for d_to, label in PERIODS:
    say("  %s s/d %s:" % (label,d_to))
    total=0
    for acc_id,(code,name) in WALLETS.items():
        bal=acc_balance(acc_id,d_to)
        total+=bal
        say("    %-12s %-20s %14s (code %s)" % (code,name,money(bal),acc_id))
    # bank
    bal_bank=acc_balance(BANK,d_to)
    say("    %-12s Bank BSI                %14s  | total kas %s" % ("1101.01",money(bal_bank),money(bal_bank+total)))
    # what sweep would be
    sweep_total=sum(acc_balance(a,d_to)*SWEEP_RATE for a in WALLETS)
    say("    -> sweep 95%% = %s -> Bank jadi %s | wallet sisa 5%% = %s" % (money(sweep_total),money(bal_bank+sweep_total),money(total-sweep_total)))

if not RUN:
    say("")
    say("DRY-RUN — tidak menulis. RUN=1 untuk eksekusi.")
    env.cr.rollback()
    import sys; sys.exit(0)

# Eksekusi
say("")
say("[EKSEKUSI] Buat JE sweep per bulan")
created=0
for d_to,label in PERIODS:
    ref="Pencairan Wallet ke Bank BSI - %s" % label
    if AM.search_count([("ref","=",ref)]):
        say("  %s sudah ada -> skip" % label)
        continue
    # hitung saldo wallet saat ini s/d d_to (sebelum sweep ini, after HPP etc tapi before sweep JE ini)
    # karena sweep sebelumnya sudah commit, saldo sudah termasuk sweep sebelumnya? we compute fresh.
    lines=[]
    total_sweep=0
    for acc_id,(code,name) in WALLETS.items():
        bal=acc_balance(acc_id,d_to)
        # but bal includes previous sweeps? We just recreated, so for July, bal is after June sweep + July transactions before sweep
        # June sweep removed 95% of June balances, so July bal is 5% sisa June + new July transactions
        # Sweep again 95% of that
        if bal < 1000:
            continue
        amt=round(bal*SWEEP_RATE,2)
        if amt<0.01:
            continue
        total_sweep+=amt
        lines.append((0,0,{"account_id":acc_id,"debit":0.0,"credit":amt,"name":"Pencairan %s ke Bank BSI %s (95%%)" % (name,label)}))
    if total_sweep<0.01:
        say("  %s tidak ada saldo wallet -> skip" % label)
        continue
    # debit bank
    lines.insert(0,(0,0,{"account_id":BANK,"debit":total_sweep,"credit":0.0,"name":"Penerimaan pencairan wallet %s" % label}))
    mv=AM.create({"journal_id":misc.id,"date":d_to,"ref":ref,"line_ids":lines})
    mv.action_post()
    say("  %s JE %s sweep %s (%d wallet)" % (label,mv.name,money(total_sweep),len(lines)-1))
    created+=1
    env.cr.commit()

say("")
say("[VERIFIKASI] Setelah sweep")
for d_to,label in PERIODS:
    say("  %s s/d %s:" % (label,d_to))
    for acc_id,(code,name) in WALLETS.items():
        bal=acc_balance(acc_id,d_to)
        say("    %-12s %14s" % (code,money(bal)))
    bal_bank=acc_balance(BANK,d_to)
    say("    Bank BSI %14s" % money(bal_bank))
    # check negative cash accounts
    cr.execute("""
        SELECT aa.code_store->>'1', sum(aml.balance) FROM account_move_line aml
        JOIN account_move am ON am.id=aml.move_id
        JOIN account_account aa ON aa.id=aml.account_id
        WHERE am.state='posted' AND am.date <= %s AND aa.account_type='asset_cash'
        GROUP BY 1 HAVING sum(aml.balance) < -0.01
    """,(d_to,))
    negs=cr.fetchall()
    if negs:
        say("    NEGATIF MASIH ADA: %s" % ", ".join("%s %s"%(c,money(b)) for c,b in negs))
    else:
        say("    Semua kas >=0 OK")
# TB
cr.execute("SELECT sum(debit),sum(credit) FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id WHERE am.state='posted'")
d,c=cr.fetchone()
say("  TB debit %s credit %s diff %s %s" % (money(d),money(c),money(float(d or 0)-float(c or 0)),"OK" if abs(float(d or 0)-float(c or 0))<0.01 else ">>>"))
say("="*100)
env.cr.commit()
