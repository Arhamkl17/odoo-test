# -*- coding: utf-8 -*-
"""
juni_juli_68_hpp_harga_asli.py — HPP PAKAI HARGA BAHAN ASLI KLIEN (READ-ONLY, odoo shell).

Sumber harga : product_photos/data sheet master/HARGA BAHAN BAKU GUDANG.xlsx (sheet Agustus)
Kuantitas    : stock_move konsumsi yang sudah posted (BOM)

  su odoo ... < scripts/juni_juli_68_hpp_harga_asli.py
"""
import re
from collections import defaultdict

import openpyxl

PATH = "product_photos/data sheet master/HARGA BAHAN BAKU GUDANG.xlsx"

cr = env.cr
Prod = env["product.product"]
Bom = env["mrp.bom"]
say = lambda m="": print(m)


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def sp(p):
    v = p.standard_price
    return float((v.get("1") if isinstance(v, dict) else v) or 0.0)


# ---------- 1. baca harga klien ----------
wb = openpyxl.load_workbook(PATH, data_only=True, read_only=True)
ws = wb.worksheets[0]
rows = list(ws.iter_rows(values_only=True))
wb.close()
hi = next(i for i, r in enumerate(rows[:8])
          if any((c or "") == "Nama Barang" for c in r))
hdr = [("" if c is None else str(c).strip()) for c in rows[hi]]
i_nama, i_kecil = hdr.index("Nama Barang"), next(j for j, h in enumerate(hdr) if h.upper().startswith("HRG/SAT"))

klien = {}
for r in rows[hi + 1:]:
    cells = list(r) + [None] * 8
    nm = cells[i_nama]
    if not nm:
        continue
    try:
        v = float(cells[i_kecil])
    except (TypeError, ValueError):
        continue
    klien[norm(nm)] = (str(nm).strip(), v)

say("=" * 118)
say("HPP PAKAI HARGA BAHAN ASLI KLIEN")
say("=" * 118)
say("harga klien terbaca: %d item" % len(klien))

# ---------- 2. komponen daun yang dipakai BOM ----------
komp = {}
for bom in Bom.search([("type", "in", ("phantom", "normal"))]):
    tmpl = bom.product_tmpl_id
    if not tmpl:
        continue
    _b, lines = bom.explode(tmpl, 1.0)
    for bl, vals in lines:
        c = bl.product_id
        if not c:
            continue
        if Bom.search_count([("product_tmpl_id", "=", c.product_tmpl_id.id)]):
            continue
        komp[c.id] = c

say("komponen daun dipakai BOM: %d" % len(komp))

# ---------- 3. pemetaan nama ----------
ALIAS = {
    # nama komponen di sistem  ->  nama di berkas harga klien
    "BUBUKLEMONTEA": "LEMONTEA",
    "PLASTIKKLIP8X5": "PLASTIKKLIP5X8",
    "KEMASANSEGEPOK": "KEMASANSEGEPOKBIASA",
    "AIRGELAS": "AIRMINERALGELAS",
    "MIKABUNDAR": "MIKABURGER",
}
cocok, beda, takada = [], [], []
target = {}
for pid, p in komp.items():
    n = norm(p.display_name)
    hit = klien.get(n) or klien.get(ALIAS.get(n, ""))
    if hit:
        target[pid] = hit[1]
        lama = sp(p)
        if abs(lama - hit[1]) > 0.005:
            beda.append((p.display_name, lama, hit[1]))
        else:
            cocok.append((p.display_name, lama))
    else:
        takada.append((p.display_name, sp(p)))

say("")
say("-" * 118)
say("A. HARGA BEDA (%d komponen) — sistem vs klien" % len(beda))
say("%-40s %14s %14s %10s" % ("komponen", "sistem", "klien", "selisih"))
say("-" * 118)
for nm, lama, baru in sorted(beda, key=lambda x: -abs(x[2] - x[1])):
    say("%-40s %14s %14s %9.1f%%" % (
        nm[:40], "{:,.4f}".format(lama), "{:,.4f}".format(baru),
        ((baru - lama) / lama * 100) if lama else 0))

say("")
say("-" * 118)
say("B. HARGA SUDAH SAMA (%d komponen)" % len(cocok))
say("   " + ", ".join(nm for nm, _ in cocok))
say("")
say("-" * 118)
say("C. TIDAK ADA DI DAFTAR HARGA KLIEN (%d komponen) — masih pakai isian agent" % len(takada))
say("%-44s %14s" % ("komponen", "harga sistem"))
say("-" * 118)
for nm, lama in sorted(takada, key=lambda x: -x[1]):
    say("%-44s %14s" % (nm[:44], "{:,.4f}".format(lama)))

# ---------- 4. dampak ke HPP ----------
cr.execute("""
    SELECT to_char(sm.date,'YYYY-MM'), sm.product_id, sm.quantity, COALESCE(sm.value,0), sm.account_move_id
      FROM stock_move sm
     WHERE sm.state='done' AND sm.origin LIKE 'HPP-BOM konsumsi%%'""")
moves = cr.fetchall()
delta = defaultdict(float)
pair = defaultdict(lambda: defaultdict(float))
nchg = 0
for m, pid, qty, val, amid in moves:
    pid = int(pid)
    if pid not in target:
        continue
    old = float(val or 0)
    new = float(qty or 0) * target[pid]
    d = new - old
    if abs(d) < 0.005:
        continue
    nchg += 1
    delta[m] += d
    hpp = inv = None
    if amid:
        cr.execute("""SELECT aa.id FROM account_move_line aml JOIN account_account aa ON aa.id=aml.account_id
                       WHERE aml.move_id=%s AND aml.debit>0 AND aa.account_type='expense_direct_cost' LIMIT 1""", (amid,))
        r = cr.fetchone()
        hpp = r[0] if r else None
        cr.execute("""SELECT aa.id FROM account_move_line aml JOIN account_account aa ON aa.id=aml.account_id
                       WHERE aml.move_id=%s AND aml.credit>0 AND aa.account_type IN ('asset_current','asset_fixed') LIMIT 1""", (amid,))
        r = cr.fetchone()
        inv = r[0] if r else None
    if hpp and inv:
        pair[m][(hpp, inv)] += d

cr.execute("""SELECT to_char(am.date,'YYYY-MM'), COALESCE(SUM(aml.balance),0)
                FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                JOIN account_account aa ON aa.id=aml.account_id
               WHERE am.state='posted' AND aa.account_type='expense_direct_cost'
                 AND am.date >= '2026-06-01' AND am.date < '2026-09-01'
               GROUP BY 1 ORDER BY 1""")
hpp_act = {str(m): float(v) for m, v in cr.fetchall()}
say("   [debug] bulan HPP terbaca: %s" % sorted(hpp_act))
cr.execute("""SELECT to_char(am.date,'YYYY-MM'), COALESCE(SUM(aml.balance),0)
                FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                JOIN account_account aa ON aa.id=aml.account_id
               WHERE am.state='posted' AND aa.account_type IN ('income','income_other')
               GROUP BY 1 ORDER BY 1""")
rev = {m: -float(v) for m, v in cr.fetchall()}
cr.execute("""SELECT to_char(am.date,'YYYY-MM'), COALESCE(SUM(aml.balance),0)
                FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                JOIN account_account aa ON aa.id=aml.account_id
               WHERE am.state='posted' AND aa.account_type IN ('expense','expense_depreciation')
               GROUP BY 1 ORDER BY 1""")
opex = {m: float(v) for m, v in cr.fetchall()}

say("")
say("=" * 118)
say("D. SIMULASI HPP & LABA (kuantitas konsumsi nyata, harga bahan asli klien)")
say("=" * 118)
say("move konsumsi yang nilainya berubah: %d" % nchg)
say("%-8s %16s %16s %16s %16s %16s" % ("bulan", "Pendapatan", "HPP sekarang", "HPP asli", "Laba skrg", "Laba asli"))
for m in sorted(hpp_act):
    o = hpp_act[m]
    n = o + delta.get(m, 0.0)
    r, e = rev.get(m, 0.0), opex.get(m, 0.0)
    say("%-8s %16s %16s %16s %16s %16s" % (
        m, "{:,.0f}".format(r), "{:,.0f}".format(o), "{:,.0f}".format(n),
        "{:,.0f}".format(r - o - e), "{:,.0f}".format(r - n - e)))
say("")
for m in sorted(pair):
    say("   JE penyesuaian %s: %s akun, total %s" % (
        m, len(pair[m]), "{:,.2f}".format(delta[m])))
say("")
say("CATATAN: komponen kategori C (%d) masih memakai harga isian agent." % len(takada))
say("=" * 118)
env.cr.rollback()
