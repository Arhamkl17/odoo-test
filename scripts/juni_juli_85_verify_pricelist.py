# -*- coding: utf-8 -*-
"""juni_juli_85_verify_pricelist.py — verifikasi R7/R8 langkah 1-2 (READ-ONLY)."""
cr = env.cr
PL = env["product.pricelist"]
PLI = env["product.pricelist.item"]
Config = env["pos.config"]
TM = env["product.template"]
say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))

say("=" * 116)
say("A. PRICELIST")
say("=" * 116)
for pl in PL.search([], order="id"):
    items = PLI.search([("pricelist_id", "=", pl.id)])
    say("   id=%-3s %-28s %3d item" % (pl.id, pl.name, len(items)))

say("")
say("=" * 116)
say("B. POS CONFIG")
say("=" * 116)
for c in Config.search([], order="id"):
    say("   id=%-3s %-24s pricelist=%-26s metode=%d sesi=%d" % (
        c.id, c.name, c.pricelist_id.name or "(kosong)", len(c.payment_method_ids),
        env["pos.session"].search_count([("config_id", "=", c.id)])))

say("")
say("=" * 116)
say("C. SPOT-CHECK HARGA (harga dasar vs Dine In)")
say("=" * 116)
SPOT = ["SEGEPOK BERLIMA", "PKG LOKAL DUO", "PAKET GEPREK BAKAR", "PAKET MEVVAH BERDUA",
        "PAKET YUKSSS MABAR", "YUKSSS RAMA 1", "AYAM SEGEPOK SINGLE", "NASI", "ES TEH",
        "BARBEQUE", "NUGGET"]
pl_a = PL.search([("name", "=", "Harga Dasar (Take Away)")], limit=1)
pl_b = PL.search([("name", "=", "Harga Dine In")], limit=1)
say("%-42s %10s %10s %10s %8s" % ("menu", "list_price", "Take Away", "Dine In", "rasio"))
say("-" * 116)
for nm in SPOT:
    t = TM.search([("name", "=", nm)], limit=1)
    if not t:
        say("%-42s  TIDAK ADA" % nm)
        continue
    a = PLI.search([("pricelist_id", "=", pl_a.id), ("product_tmpl_id", "=", t.id)], limit=1)
    b = PLI.search([("pricelist_id", "=", pl_b.id), ("product_tmpl_id", "=", t.id)], limit=1)
    va = a.fixed_price if a else 0
    vb = b.fixed_price if b else 0
    say("%-42s %10s %10s %10s %7.2fx" % (
        nm[:42], money(t.list_price), money(va), money(vb), (vb / va) if va else 0))

say("")
say("=" * 116)
say("D. LEDGER — TIDAK BOLEH BERUBAH")
say("=" * 116)
cr.execute("""
    SELECT to_char(am.date,'YYYY-MM') AS bln,
           SUM(CASE WHEN aa.account_type IN ('income','income_other')
                    THEN -aml.balance ELSE 0 END) AS pendapatan,
           SUM(CASE WHEN aa.account_type IN ('expense','expense_depreciation',
                        'expense_direct_cost','cost_of_goods_sold')
                    THEN aml.balance ELSE 0 END) AS beban
      FROM account_move_line aml
      JOIN account_move am ON am.id = aml.move_id
      JOIN account_account aa ON aa.id = aml.account_id
     WHERE am.state = 'posted' AND am.date >= '2026-06-01' AND am.date < '2026-09-01'
     GROUP BY 1 ORDER BY 1""")
say("%-10s %18s %18s %18s" % ("bulan", "pendapatan", "beban", "laba"))
# Baseline 13 Sep 2026 SESUDAH regenerate dua channel (§24.7).
# Sebelum regenerate: Jun +34.027.810,17 | Jul +80.921.909,04 | Agu −40.161.292,61.
# Agustus sengaja tidak di-regenerate, jadi nilainya harus tetap sama.
# Baseline §25: Juni/Juli sudah termasuk beban operasional proporsional Agustus
harap = {"2026-06": 9056671.63, "2026-07": 16491104.87, "2026-08": -40161292.61}
ok = True
for bln, p, b in cr.fetchall():
    laba = float(p or 0) - float(b or 0)
    mark = ""
    if bln in harap:
        if abs(laba - harap[bln]) < 0.05:
            mark = "  OK (sesuai baseline §25)"
        else:
            mark = "  ⚠ BEDA (harap %s)" % money(harap[bln])
            ok = False
    say("%-10s %18s %18s %18s%s" % (bln, money(p), money(b), money(laba), mark))

cr.execute("""
    SELECT to_char(am.date,'YYYY-MM'),
           SUM(aml.debit) - SUM(aml.credit)
      FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
     WHERE am.state='posted' AND am.date >= '2026-06-01' AND am.date < '2026-09-01'
     GROUP BY 1 ORDER BY 1""")
say("")
for bln, diff in cr.fetchall():
    say("   TB %s : diff = %s %s" % (bln, money(diff), "OK" if abs(float(diff or 0)) < 0.005 else "⚠"))

say("")
say("KESIMPULAN: %s" % ("LEDGER sesuai baseline yang diharapkan." if ok else "ADA SELISIH dari baseline — periksa!"))
env.cr.rollback()
