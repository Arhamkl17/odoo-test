# -*- coding: utf-8 -*-
"""
RECON READ-ONLY LANJUTAN — data yang dibutuhkan untuk MENJAWAB §9 spec
(JUNI_JULI_DATA-spec.md §9: persediaan akhir Juli, split modal, freeze Agustus,
partner AR/AP) + status akun bank BNI (temuan §12.3 recon pertama).

Seksi:
  1. Ekuitas & modal disetor — kapan, berapa, move mana
  2. Aset tetap — kapan diakuisisi, dibiayai dari akun apa
  3. Persediaan — rollforward Agustus (untuk menurunkan target saldo akhir Juli)
  4. Partner — daftar pelanggan & supplier yang ada
  5. Bank & kas — status active, saldo, per bulan (khusus BNI), jurnal
  6. stock.move.value — stored vs computed (menentukan apakah Agustus bisa berubah)

Read-only: env.cr.rollback() di akhir.
"""
from collections import defaultdict

SEP = "=" * 78
def sec(t): print("\n" + SEP + "\n" + t + "\n" + SEP)
def rp(v): return "%16.2f" % (v or 0.0)

AML = env["account.move.line"]
Acc = env["account.account"].with_context(active_test=False)
POST = [("parent_state", "=", "posted")]


def lines(acc_ids, extra=None, limit=60):
    dom = POST + [("account_id", "in", acc_ids)] + (extra or [])
    return AML.search(dom, order="date, id", limit=limit)


# ===========================================================================
sec("1. EKUITAS & MODAL DISETOR — kapan & berapa")
# ===========================================================================
eq = Acc.search([("account_type", "=", "equity")])
tot = defaultdict(float)
print("%-12s %-38s %16s" % ("CODE", "NAME", "SALDO"))
for a in eq:
    r = AML._read_group(POST + [("account_id", "=", a.id)], [], ["balance:sum"])
    v = sum(x or 0.0 for x in r[0]) if r else 0.0
    if abs(v) >= 0.005:
        tot[a.name] += v
        print("%-12s %-38s %s" % (a.code, a.name[:38], rp(v)))

print("\n-- detail baris Modal Disetor (3101.02) --")
md = Acc.search([("code", "=", "3101.02")])
for l in lines(md.ids):
    print("   %s | %-26s | %-30s | D %s K %s | move %s" % (
        l.date, (l.journal_id.code or "-"), (l.name or "-")[:30],
        rp(l.debit), rp(l.credit), l.move_id.name))
moves = lines(md.ids).mapped("move_id")
for m in moves:
    print("   MOVE %s (%s) lines:" % (m.name, m.date))
    for l in m.line_ids:
        print("      %-10s %-40s D %s K %s" % (
            l.account_id.code, l.account_id.name[:40], rp(l.debit), rp(l.credit)))

print("\n-- detail baris Opening Balance Equity (3101.04) --")
ob = Acc.search([("code", "=", "3101.04")])
for l in lines(ob.ids, limit=20):
    print("   %s | %-26s | %-30s | D %s K %s" % (
        l.date, (l.journal_id.code or "-"), (l.name or "-")[:30], rp(l.debit), rp(l.credit)))


# ===========================================================================
sec("2. ASET TETAP — kapan diakuisisi, dibiayai apa")
# ===========================================================================
GROSS_CODES = ["1105.01", "1105.02", "1105.03", "1105.04", "1200.01", "1200.02", "1200.03"]
print("per akun: jumlah baris debit + tanggal + akun lawan (kredit di move yang sama)")
for code in GROSS_CODES:
    a = Acc.search([("code", "=", code)], limit=1)
    if not a:
        print("   %-10s (akun tidak ada)" % code)
        continue
    deb_lines = lines(a.ids, extra=[("debit", ">", 0)])
    print("\n   %-10s %-32s debit lines = %d" % (code, a.name[:32], len(deb_lines)))
    for l in deb_lines:
        others = [(x.account_id.code, x.account_id.name, x.debit, x.credit)
                  for x in l.move_id.line_ids if x.id != l.id and (x.credit or x.debit)]
        print("      %s | D %s | move %-22s | lawan: %s" % (
            l.date, rp(l.debit).strip(), l.move_id.name,
            "; ".join("%s %s K%s" % (c, n[:18], rp(cr).strip()) for c, n, _d, cr in others[:3])))


# ===========================================================================
sec("3. PERSEDIAAN — rollforward Agustus (dasar target saldo akhir Juli)")
# ===========================================================================
Quant = env["stock.quant"]
q = Quant._read_group([("location_id.usage", "=", "internal")], [], ["value:sum"])
qty_now = sum(x or 0.0 for x in q[0]) if q else 0.0
SM = env["stock.move"]
mv = SM._read_group(
    [("state", "=", "done"), ("date", ">=", "2026-08-01"), ("date", "<", "2026-09-01")],
    ["location_id.usage", "location_dest_id.usage"], ["value:sum", "id:count"])
purch = cons = adj = 0.0
for src, dst, val, cnt in mv:
    val = val or 0.0
    print("   %-10s -> %-10s Rp %s (%d move)" % (src, dst, rp(val).strip(), cnt))
    if src == "supplier" and dst == "internal":
        purch += val
    elif src == "internal" and dst == "customer":
        cons += val
    elif src == "internal" and dst == "inventory":
        adj -= val      # shrink: keluar dari internal, value positif
    elif src == "inventory" and dst == "internal":
        adj += val
print("\n   nilai persediaan SEKARANG (akhir Agu) : Rp %s" % rp(qty_now).strip())
print("   pembelian Agu  : Rp %s" % rp(purch).strip())
print("   konsumsi Agu   : Rp %s" % rp(cons).strip())
print("   penyesuaian    : Rp %s" % rp(adj).strip())
opening = qty_now - purch + cons - adj
print("   => SALDO AWAL AGU (implisit) = SALDO AKHIR JULI : Rp %s" % rp(opening).strip())
print("   cek: awal %s + beli %s - konsumsi %s + adj %s = %s" % (
    rp(opening).strip(), rp(purch).strip(), rp(cons).strip(), rp(adj).strip(),
    rp(opening + purch - cons + adj).strip()))


# ===========================================================================
sec("4. PARTNER — pelanggan & supplier yang sudah ada")
# ===========================================================================
P = env["res.partner"]
for label, dom in (("CUSTOMER (customer_rank>0)", [("customer_rank", ">", 0)]),
                   ("SUPPLIER (supplier_rank>0)", [("supplier_rank", ">", 0)]),
                   ("PLATFORM", [("name", "ilike", "food")])):
    print("\n%s:" % label)
    for x in P.search(dom, order="id"):
        print("   [%4d] %-40s customer=%s supplier=%s" % (
            x.id, x.name[:40], x.customer_rank, x.supplier_rank))


# ===========================================================================
sec("5. BANK & KAS — status active, saldo, per bulan (BNI), jurnal")
# ===========================================================================
cash = Acc.search([("account_type", "=", "asset_cash")])
for a in cash:
    r = AML._read_group(POST + [("account_id", "=", a.id)], [], ["balance:sum"])
    v = sum(x or 0.0 for x in r[0]) if r else 0.0
    ndone = env["account.move"].search_count([("state", "=", "posted"),
                                              ("line_ids.account_id", "=", a.id)])
    print("   %-10s %-32s saldo %s active=%-5s posted_moves=%d" % (
        a.code, a.name[:32], rp(v).strip(), a.active, ndone))

print("\n-- Bank BNI: mutasi per bulan (posted) --")
bni = Acc.search([("name", "=", "Bank BNI")], limit=1)
if bni:
    print("   id=%s code=%s active=%s" % (bni.id, bni.code, bni.active))
    for month, deb, cred in AML._read_group(
            POST + [("account_id", "=", bni.id)], ["date:month"], ["debit:sum", "credit:sum"]):
        print("   %-10s D %s K %s net %s" % (month, rp(deb).strip(), rp(cred).strip(),
                                             rp((deb or 0.0) - (cred or 0.0)).strip()))
    print("   BNI per akhir bulan:")
    for d in ("2026-07-31", "2026-08-31", "2026-09-30"):
        r = AML._read_group(POST + [("account_id", "=", bni.id), ("date", "<=", d)],
                            [], ["balance:sum"])
        print("      %s : Rp %s" % (d, rp(sum(x or 0.0 for x in r[0]) if r else 0.0).strip()))
    print("   jurnal default yg memakai BNI:")
    for j in env["account.journal"].search([("default_account_id", "=", bni.id)]):
        print("      %-8s %-28s type=%s" % (j.code, j.name[:28], j.type))

print("\n-- semua jurnal bank/kas & akun default --")
for j in env["account.journal"].search([("type", "in", ["bank", "cash"])]):
    d = j.default_account_id
    print("   %-8s %-24s type=%-5s default=%s (%s active=%s)" % (
        j.code, j.name[:24], j.type, d.code or "-", (d.name or "-")[:26],
        d.active if d else "-"))

print("\n-- partner/akun yang menyebut BNI/BRI/BCA/Mandiri (akun nonaktif bersaldo) --")
for a in Acc.search([("account_type", "=", "asset_cash")]):
    r = AML._read_group(POST + [("account_id", "=", a.id)], [], ["balance:sum"])
    v = sum(x or 0.0 for x in r[0]) if r else 0.0
    if not a.active and abs(v) >= 0.005:
        print("   [BERSALDO TAPI NONAKTIF] %-10s %-32s Rp %s" % (a.code, a.name[:32], rp(v).strip()))


# ===========================================================================
sec("6. STOCK.MOVE.VALUE — stored atau computed? (menentukan freeze Agustus)")
# ===========================================================================
f = SM._fields["value"]
print("   type      :", getattr(f, "type", "?"))
print("   store     :", getattr(f, "store", "?"))
print("   compute   :", getattr(f, "compute", None))
print("   readonly  :", getattr(f, "readonly", "?"))
print("   -> kalau store=True & compute=None: nilai histori TIDAK dihitung ulang")

print("\n[RECON LANJUTAN SELESAI — read-only]")
env.cr.rollback()
