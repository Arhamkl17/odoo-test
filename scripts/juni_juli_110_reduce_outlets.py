# scripts/juni_juli_110_reduce_outlets.py
# Tujuan: kembali ke 2 POS config saja (Outlet Pallangga + Outlet Mallengkeri).
# Arsipkan (active=False) config Dine In 6/7, payment method 20/21, pricelist Dine In,
# jurnal CSHD1/CSHD2, dan akun 1100.03/1100.04.
# Saldo laci 1100.03 → 1100.02 (Kas Operasional Resto) & 1100.04 → 1111001 (Kas Mallengkeri).
# Idempotent, RUN=1 untuk apply.
import sys

RUN = (len(sys.argv) > 1 and sys.argv[1] == "RUN=1")

def log(msg):
    print(f"  {msg}")

def hdr(t):
    print(f"\n=== {t} ===")

# ---------- Sanity check ----------
hdr("Sanity check pre-eksekusi")

c6 = env['pos.config'].browse(6)
c7 = env['pos.config'].browse(7)
assert c6.exists() and c6.name == 'Dine In Pallangga', "config 6 tidak ditemukan / nama beda"
assert c7.exists() and c7.name == 'Dine In Mallengkeri', "config 7 tidak ditemukan / nama beda"

c1 = env['pos.config'].browse(1)
c2 = env['pos.config'].browse(2)
log(f"POS aktif sekarang: 1={c1.name!r} · 2={c2.name!r} · 6={c6.name!r} · 7={c7.name!r}")

# Sesi count (closed history tidak dihapus)
sesi6 = env['pos.session'].search_count([('config_id','=',6),('state','=','closed')])
sesi7 = env['pos.session'].search_count([('config_id','=',7),('state','=','closed')])
log(f"Sesi closed history: Dine In Pallangga={sesi6} · Dine In Mallengkeri={sesi7} (dipertahankan utuh)")

# Saldo akun kas Dine In
a03 = env['account.account'].search([('code','=','1100.03')], limit=1)
a04 = env['account.account'].search([('code','=','1100.04')], limit=1)
a02 = env['account.account'].search([('code','=','1100.02')], limit=1)  # Kas Operasional Resto
a_mlk = env['account.account'].search([('code','=','1111001')], limit=1)  # Kas Mallengkeri

def bal(acc):
    return sum(l.balance for l in env['account.move.line'].search([
        ('account_id','=',acc.id),('parent_state','=','posted')]))

b03 = bal(a03)
b04 = bal(a04)
log(f"Saldo 1100.03 Kas Dine In Pallangga     = {b03:,.2f}")
log(f"Saldo 1100.04 Kas Dine In Mallengkeri   = {b04:,.2f}")

# Idempotent: kalau config sudah inactive, exit
if not c6.active and not c7.active:
    print("\n[SKIP] config 6 & 7 sudah inactive — eksekusi ulang tidak perlu.")
    env.cr.rollback()
    sys.exit(0)

if not RUN:
    print("\n[DRY-RUN] pass RUN=1 untuk apply. Yang akan dilakukan:")
    print(f"  1. Konsolidasi saldo {b03:,.2f} dari 1100.03 ke 1100.02")
    print(f"  2. Konsolidasi saldo {b04:,.2f} dari 1100.04 ke 1111001 (Kas Mallengkeri)")
    print(f"  3. Arsipkan pos.config 6 & 7 (active=False)")
    print(f"  4. Arsipkan pos.payment.method 20 & 21")
    print(f"  5. Arsipkan product.pricelist id=4 'Harga Dine In'")
    print(f"  6. Arsipkan account.journal CSHD1 & CSHD2")
    print(f"  7. Arsipkan account.account 1100.03 & 1100.04")
    env.cr.rollback()
    sys.exit(0)

# ---------- Eksekusi ----------
hdr("1. Konsolidasi saldo kas Dine In ke kas outlet")

# JE 1: 1100.03 -> 1100.02
if abs(b03) > 0.01:
    j = env['account.move'].create({
        'journal_id': env['account.journal'].search([('code','=','MISC')], limit=1).id,
        'date': '2026-07-31',
        'ref': 'Konsolidasi saldo Kas Dine In Pallangga → Kas Operasional Resto',
        'line_ids': [
            (0, 0, {'account_id': a02.id, 'debit': b03, 'credit': 0.0, 'name': 'Saldo laci Dine In Pallangga dipindah'}),
            (0, 0, {'account_id': a03.id, 'debit': 0.0, 'credit': b03, 'name': 'Saldo laci Dine In Pallangga dipindah'}),
        ],
    })
    j.action_post()
    log(f"  JE {j.name} posted: Dr 1100.02 / Cr 1100.03 = {b03:,.2f}")
else:
    log(f"  1100.03 saldo = 0, skip JE 1")

# JE 2: 1100.04 -> 1111001
if abs(b04) > 0.01:
    j = env['account.move'].create({
        'journal_id': env['account.journal'].search([('code','=','MISC')], limit=1).id,
        'date': '2026-07-31',
        'ref': 'Konsolidasi saldo Kas Dine In Mallengkeri → Kas Mallengkeri',
        'line_ids': [
            (0, 0, {'account_id': a_mlk.id, 'debit': b04, 'credit': 0.0, 'name': 'Saldo laci Dine In Mallengkeri dipindah'}),
            (0, 0, {'account_id': a04.id, 'debit': 0.0, 'credit': b04, 'name': 'Saldo laci Dine In Mallengkeri dipindah'}),
        ],
    })
    j.action_post()
    log(f"  JE {j.name} posted: Dr 1111001 / Cr 1100.04 = {b04:,.2f}")
else:
    log(f"  1100.04 saldo = 0, skip JE 2")

# ---------- Arsip ----------
hdr("2. Arsipkan POS config 6 & 7")
c6.write({'active': False})
c7.write({'active': False})
log(f"  config 6 active={c6.active}  ·  config 7 active={c7.active}")

hdr("3. Arsipkan payment method 20 & 21")
pm20 = env['pos.payment.method'].browse(20)
pm21 = env['pos.payment.method'].browse(21)
if pm20.exists(): pm20.write({'active': False}); log(f"  pm 20 active={pm20.active}")
if pm21.exists(): pm21.write({'active': False}); log(f"  pm 21 active={pm21.active}")

hdr("4. Arsipkan pricelist id=4 (Harga Dine In)")
pl4 = env['product.pricelist'].browse(4)
if pl4.exists():
    pl4.write({'active': False})
    log(f"  pricelist 4 active={pl4.active}")

hdr("5. Arsipkan jurnal CSHD1 & CSHD2")
for code in ['CSHD1','CSHD2']:
    j = env['account.journal'].search([('code','=',code)], limit=1)
    if j:
        j.write({'active': False})
        log(f"  journal {code} active={j.active}")

hdr("6. Arsipkan akun 1100.03 & 1100.04")
a03.write({'active': False})
a04.write({'active': False})
log(f"  1100.03 active={a03.active}  ·  1100.04 active={a04.active}")

env.cr.commit()
print("\n[COMMITTED]")

# ---------- Verifikasi ----------
hdr("Verifikasi pasca-eksekusi")

# POS config aktif
print("POS config aktif:")
for c in env['pos.config'].with_context(active_test=True).search([]):
    pl = c.pricelist_id.name if c.pricelist_id else 'NONE'
    print(f"  id={c.id}  {c.name!r}  pricelist={pl}")

# Saldo 1100.03 / 1100.04
b03n = bal(a03)
b04n = bal(a04)
b02n = bal(a02)
b_mlkn = bal(a_mlk)
print(f"\nSaldo pasca:")
print(f"  1100.02 Kas Operasional Resto = {b02n:,.2f}")
print(f"  1111001 Kas Mallengkeri       = {b_mlkn:,.2f}")
print(f"  1100.03 (inactive)            = {b03n:,.2f}")
print(f"  1100.04 (inactive)            = {b04n:,.2f}")

# TB diff per bulan
print("\nTrial Balance diff per bulan:")
for d2 in ['2026-06-30','2026-07-31','2026-08-31']:
    aml = env['account.move.line'].search([('date','<=',d2),('parent_state','=','posted')])
    d = sum(l.debit for l in aml)
    k = sum(l.credit for l in aml)
    print(f"  s.d. {d2}: D={d:,.2f} K={k:,.2f} diff={d-k:,.2f}")

# AR/AP
print("\nPiutang/AP per akhir bulan:")
for d2 in ['2026-06-30','2026-07-31','2026-08-31']:
    ar = sum(l.balance for l in env['account.move.line'].search([
        ('date','<=',d2),('parent_state','=','posted'),
        ('account_id.account_type','=','asset_receivable')]))
    ap = sum(l.balance for l in env['account.move.line'].search([
        ('date','<=',d2),('parent_state','=','posted'),
        ('account_id.account_type','=','liability_payable')]))
    print(f"  @ {d2}: AR={ar:,.2f}  AP={ap:,.2f}")

env.cr.rollback()
print("\n(verifikasi read-only — rollback setelah COMMIT, TIDAK menghapus JE yang sudah di-post)")
