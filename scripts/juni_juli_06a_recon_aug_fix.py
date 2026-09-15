# -*- coding: utf-8 -*-
"""READ-ONLY recon untuk P5 (perbaikan data Agustus)."""
from collections import Counter, defaultdict
cr = env.cr
AM = env["account.move"]
AML = env["account.move.line"]

print("=" * 78)
print("P5.1  JE 'Penyelesaian outstanding' yg bertanggal 1 Sep (harus -> 31 Agu)")
mv = AM.search([("date", "=", "2026-09-01"), ("state", "=", "posted")])
print("total move posted 1 Sep:", len(mv))
for m in mv:
    tot = sum(l.balance for l in m.line_ids if l.account_id.code == "1103.06")
    print("   %-24s jr=%-5s hash=%-5s lines=%d | 1103.06=%s | ref=%s" % (
        m.name, m.journal_id.code, m.journal_id.restrict_mode_hash_table,
        len(m.line_ids), "{:,.2f}".format(tot), (m.ref or "")[:34]))
    for l in m.line_ids:
        print("        %-10s %-30s D %14s K %14s" % (
            l.account_id.code, l.account_id.name[:30],
            "{:,.2f}".format(l.debit or 0), "{:,.2f}".format(l.credit or 0)))
print("lock dates:", {f: getattr(env.company, f, None) for f in
      dir(env.company) if "lock_date" in f})

print()
print("=" * 78)
print("P5.2  AKUN AR: mana yang punya histori, mana yang dipakai Odoo sekarang")
for code in ("11210010", "11210011", "1102.01", "1102.04", "11120003", "1103.06"):
    cr.execute("""SELECT id, name->>'en_US', active FROM account_account WHERE code_store->>'1'=%s""", (code,))
    r = cr.fetchone()
    if not r:
        print("   %-10s — tidak ada" % code)
        continue
    cr.execute("""SELECT COUNT(*), COALESCE(SUM(aml.debit),0), COALESCE(SUM(aml.credit),0)
                  FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                  WHERE aml.account_id=%s AND am.state='posted'""", (r[0],))
    n, d, k = cr.fetchone()
    cr.execute("""SELECT COUNT(*) FROM account_move_line WHERE account_id=%s AND ((debit>0) OR (credit>0))""", (r[0],))
    nall = cr.fetchone()[0]
    print("   %-10s id=%-6s active=%-5s %-32s | posted n=%-5s D=%16s K=%16s | semua baris=%s" % (
        code, r[0], r[2], (r[1] or "")[:32], n, "{:,.2f}".format(d), "{:,.2f}".format(k), nall))
print("   company.account_default_pos_receivable_account_id =",
      env.company.account_default_pos_receivable_account_id.display_name)

print()
print("=" * 78)
print("P5.3  LABEL AR di JE sesi vs metode bayar SEKARANG (cek hipotesis 'label basi')")
sess = env["pos.session"].search([("start_at", ">=", "2026-08-01"), ("start_at", "<", "2026-09-01")])
bad = 0
for s in sess:
    jel = [l for l in s.move_id.line_ids if l.account_id.code == "11210011"]
    jel_map = {}
    for l in jel:
        nm = (l.name or "").split(" - ", 1)[-1]
        jel_map[nm] = jel_map.get(nm, 0.0) + (l.debit or 0)
    pay_map = defaultdict(float)
    for p in env["pos.payment"].search([("session_id", "=", s.id)]):
        pay_map[p.payment_method_id.name] += p.amount
    if set(jel_map) != set(pay_map):
        bad += 1
        if bad <= 3:
            print("   sesi %s (%s) MISMATCH" % (s.id, s.config_id.name))
            print("      JE label  :", {k: "{:,.0f}".format(v) for k, v in sorted(jel_map.items())})
            print("      data bayar:", {k: "{:,.0f}".format(v) for k, v in sorted(pay_map.items())})
print("   sesi dgn label AR tidak cocok dgn data pembayaran: %d / %d" % (bad, len(sess)))

print()
print("=" * 78)
print("P5.4  INVOICE BATAL INV/2026/00003")
inv = AM.search([("name", "=", "INV/2026/00003")], limit=1)
if inv:
    print("   %s state=%s date=%s partner=%s amount=%s" % (
        inv.name, inv.state, inv.date, inv.partner_id.name, "{:,.2f}".format(inv.amount_total)))
    print("   payment_state=%s | journal=%s" % (inv.payment_state, inv.journal_id.code))
    for l in inv.line_ids:
        print("      %-10s %-32s D %14s K %14s" % (
            l.account_id.code, l.account_id.name[:32],
            "{:,.2f}".format(l.debit or 0), "{:,.2f}".format(l.credit or 0)))
    print("   reconcile: inv.line_ids.reconciled =", [bool(x.reconciled) for x in inv.line_ids])
else:
    print("   tidak ditemukan")
print("   semua move state != posted yg masih ada baris:")
cr.execute("""SELECT am.name, am.state, am.date, COUNT(*) FROM account_move am
              JOIN account_move_line aml ON aml.move_id=am.id
              WHERE am.state IN ('draft','cancel') GROUP BY 1,2,3 ORDER BY 3 DESC LIMIT 15""")
for r in cr.fetchall():
    print("      %-26s %-8s %s n=%s" % r)

print()
print("=" * 78)
print("P5.5  NAMA SESI")
print("   nama sesi Agustus:", Counter(s.name for s in sess).most_common(5))
print("   contoh nama sesi baru (sekali buka):")
s = env["pos.session"].create({"config_id": env["pos.config"].browse(1).id})
print("      default name =", repr(s.name))
s.unlink()
s2 = env["pos.session"].create({"config_id": env["pos.config"].browse(1).id})
print("      set state opened, name =", repr(s2.name))
s2.unlink()
print("   ref pada JE POSS contoh:", [m.ref for m in sess.mapped("move_id")[:3]])

print()
print("=" * 78)
print("P5.6  MENU TANPA BOM (Qty terjual Agustus)")
POSm = env["pos.order"]
aug = POSm.search([("date_order", ">=", "2026-08-01"), ("date_order", "<", "2026-09-01")])
sold = Counter()
for o in aug:
    for l in o.lines:
        sold[l.product_id.id] += l.qty
Bom = env["mrp.bom"]
nobom = []
for pid, q in sold.most_common():
    p = env["product.product"].browse(pid)
    if not Bom.search_count([("product_tmpl_id", "=", p.product_tmpl_id.id)]):
        nobom.append((p, q))
print("   menu terjual tanpa BOM: %d dari %d" % (len(nobom), len(sold)))
for p, q in nobom:
    print("      %-46s qty=%-6s categ=%s" % (
        p.display_name[:46], q, (p.categ_id.name or "")[:22]))
env.cr.rollback()
