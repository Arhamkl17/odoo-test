# -*- coding: utf-8 -*-
"""
juni_juli_41_cost_import.py — IMPOR harga beli klien + hitung ulang HPP.

ALUR
 1. Baca CSV isian klien (kolom dari `juni_juli_40_cost_template.py`).
    Cocokkan per `product_id`; validasi nama, satuan, rentang kewajaran.
 2. Tampilkan tabel lama -> baru + dampak per bulan (dari stock move konsumsi
    yang sudah posted, jadi memakai kuantitas NYATA, bukan estimasi).
 3. RUN=1     -> tulis `standard_price` komponen.
    MENU=1    -> hitung ulang cost MENU dari BOM (untuk laporan margin).
    ADJUST=1  -> posting JE penyesuaian HPP per bulan (selisih biaya konsumsi).

CATATAN PENTING
  Komponen & menu di sistem ini `cost_method = fifo`. Menulis `standard_price`
  pada produk FIFO TIDAK memicu revaluasi otomatis (lihat
  `stock_account/models/product.py::_change_standard_price` yang melewati fifo).
  Karena itu biaya historis TIDAK berubah sendiri, dan koreksi HPP dilakukan
  sebagai JE penyesuaian per bulan pada langkah ADJUST=1 — idempotent, punya ref
  tetap, bisa ditelusuri.

PEMAKAIAN
  dry-run : su odoo ... < scripts/juni_juli_41_cost_import.py
  eksekusi: ... COST_CSV=import_data/harga_beli_klien_ISI.csv RUN=1 ADJUST=1 MENU=1
"""
import io
import csv
import os
from collections import defaultdict

RUN = os.environ.get("RUN") == "1"
ADJUST = os.environ.get("ADJUST") == "1"
MENU = os.environ.get("MENU") == "1"
COST_CSV = os.environ.get("COST_CSV", "import_data/harga_beli_klien_ISI.csv")
TEMPLATE = "import_data/harga_beli_klien_TEMPLATE.csv"

# batas kewajaran perubahan harga (rasio baru/lama)
WARN_LO, WARN_HI = 0.5, 2.0        # di luar ini -> PERINGATAN
ERR_LO, ERR_HI = 0.05, 20.0        # di luar ini -> DITOLAK

cr = env.cr
Prod = env["product.product"]
Bom = env["mrp.bom"]
AM = env["account.move"]
J = env["account.journal"]
say = lambda m="": print(m)


def money(x):
    return "{:,.2f}".format(float(x or 0))


def parse_num(s):
    """Angka dari CSV klien. Menerima format Indonesia (3.466,64) DAN polos (3466.64).

    Aturan:
      - ada '.' dan ','  -> pemisah desimal = yang paling belakang
      - hanya ','        -> desimal bila 1-2 digit di belakang, selain itu ribuan
      - hanya '.'        -> desimal bila 1-2 digit di belakang (atau angka di depan '0'),
                            selain itu pemisah ribuan
    """
    s = (s or "").strip().replace(" ", "").replace("\u00a0", "")
    if not s:
        return None
    neg = s.startswith("-")
    if neg:
        s = s[1:]
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = (head + "." + tail) if len(tail) in (1, 2) else s.replace(",", "")
    elif "." in s:
        head, _, tail = s.rpartition(".")
        if len(tail) == 3 and head and head != "0":
            s = s.replace(".", "")
    v = float(s)
    return -v if neg else v


def net_account_moves(month_from, month_to):
    """HPP aktual (net) per bulan dari JE, untuk kontrol."""
    cr.execute("""
        SELECT to_char(am.date,'YYYY-MM'), COALESCE(SUM(aml.balance),0)
          FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
          JOIN account_account aa ON aa.id=aml.account_id
         WHERE am.state='posted' AND aa.account_type='expense_direct_cost'
           AND am.date >= %s AND am.date < %s
         GROUP BY 1 ORDER BY 1""", (month_from, month_to))
    return {m: float(v) for m, v in cr.fetchall()}


say("=" * 104)
say("IMPOR HARGA BELI KLIEN   |   RUN=%s ADJUST=%s MENU=%s" % (RUN, ADJUST, MENU))
say("   berkas: %s" % COST_CSV)
say("=" * 104)

if not os.path.exists(COST_CSV):
    say("")
    say("BERKAS ISIAN BELUM ADA.")
    say("  1) Kirim %s ke klien (sudah dibuat oleh" % TEMPLATE)
    say("     scripts/juni_juli_40_cost_template.py).")
    say("  2) Klien mengisi kolom `harga_per_satuan_kecil_rp`")
    say("     (atau `harga_per_satuan_beli_rp` + `isi_per_satuan_beli`).")
    say("  3) Simpan sebagai %s lalu jalankan ulang skrip ini." % COST_CSV)
    say("=" * 104)
    env.cr.rollback()
    raise SystemExit(1)

# ---------------------------------------------------------------- 1. BACA
with io.open(COST_CSV, encoding="utf-8-sig") as f:
    raw = list(csv.DictReader(f))
say("")
say("1) BACA BERKAS — %d baris" % len(raw))

plan = []          # (product, old, new, usage, note)
problems = []
skipped = []
seen = set()
for r in raw:
    pid_s = (r.get("product_id") or "").strip()
    if not pid_s:
        continue
    try:
        pid = int(pid_s)
    except ValueError:
        problems.append("product_id bukan angka: %r" % pid_s)
        continue
    if pid in seen:
        problems.append("product_id %s muncul dua kali" % pid)
        continue
    seen.add(pid)

    p = Prod.browse(pid)
    if not p.exists():
        problems.append("product_id %s tidak ada di sistem" % pid)
        continue
    if (p.display_name or "").strip().upper() != (r.get("nama_komponen") or "").strip().upper():
        problems.append("product_id %s: nama di CSV '%s' != sistem '%s'"
                        % (pid, r.get("nama_komponen"), p.display_name))

    kecil_s = (r.get("harga_per_satuan_kecil_rp") or "").strip()
    besar_s = (r.get("harga_per_satuan_beli_rp") or "").strip()
    isi_s = (r.get("isi_per_satuan_beli") or "").strip()
    try:
        kecil, besar, isi = parse_num(kecil_s), parse_num(besar_s), parse_num(isi_s)
        if kecil is not None:
            new = kecil
            src = "per satuan pakai"
        elif besar is not None and isi:
            new = besar / isi
            src = "%s / %s" % (money(besar), isi_s)
        else:
            skipped.append((p, "belum diisi"))
            continue
    except (ValueError, ZeroDivisionError):
        problems.append("product_id %s: angka tidak valid (kecil=%r besar=%r isi=%r)"
                        % (pid, kecil_s, besar_s, isi_s))
        continue

    sp = p.standard_price
    sp = sp.get("1") if isinstance(sp, dict) else sp
    old = float(sp or 0.0)
    usage = 0.0
    cr.execute("""SELECT COALESCE(SUM(quantity),0) FROM stock_move
                   WHERE state='done' AND product_id=%s AND origin LIKE 'HPP-BOM konsumsi%%'""",
               (pid,))
    usage = float(cr.fetchone()[0] or 0.0)

    if new <= 0:
        problems.append("product_id %s (%s): harga harus > 0 (diberi %s)" % (pid, p.display_name, money(new)))
        continue
    if old > 0:
        ratio = new / old
        if ratio < ERR_LO or ratio > ERR_HI:
            problems.append("product_id %s (%s): perubahan ekstrem %.2fx (%s -> %s) — ditolak"
                            % (pid, p.display_name, ratio, money(old), money(new)))
            continue
        note = "PERINGATAN %.2fx" % ratio if (ratio < WARN_LO or ratio > WARN_HI) else ""
    else:
        note = "harga lama 0"
    plan.append((p, old, new, usage, src + (" | " + note if note else "")))

say("      siap dipakai : %d komponen" % len(plan))
say("      belum diisi  : %d" % len(skipped))
say("      bermasalah   : %d" % len(problems))
for s in problems:
    say("         !! %s" % s)
if not plan:
    say("")
    say("Tidak ada baris yang bisa dipakai — berhenti.")
    say("=" * 104)
    env.cr.rollback()
    raise SystemExit(1)

# ---------------------------------------------------------------- 2. TABEL
say("")
say("2) PERUBAHAN HARGA (diurut dampak terbesar)")
say("   %-34s %-6s %14s %14s %7s %14s %16s" % (
    "komponen", "uom", "lama", "baru", "rasio", "pemakaian", "selisih nilai"))
plan.sort(key=lambda x: -abs(x[3] * (x[2] - x[1])))
tot_old = tot_new = 0.0
for p, old, new, usage, note in plan:
    tot_old += old * usage
    tot_new += new * usage
    say("   %-34s %-6s %14s %14s %7s %14s %16s" % (
        p.display_name[:34], p.uom_id.name, money(old), money(new),
        ("%.2fx" % (new / old)) if old else "-", "%.0f" % usage,
        money(usage * (new - old))))
    if note:
        say("        -> %s" % note)
say("   %-34s %-6s %14s %14s %7s %14s %16s" % (
    "TOTAL 3 BULAN", "", "", "", "", "", money(tot_new - tot_old)))
say("      nilai biaya versi lama = %s" % money(tot_old))
say("      nilai biaya versi baru = %s" % money(tot_new))

# ---------------------------------------------------------------- 3. SIMULASI
# Sumber: stock move konsumsi yang SUDAH posted (kuantitas nyata) + JE-nya,
# jadi akun HPP & akun persediaan diambil dari jurnal yang benar-benar ada.
say("")
say("3) SIMULASI HPP & LABA per bulan (kuantitas konsumsi nyata)")
newcost = {p.id: new for p, old, new, usage, note in plan}
cr.execute("""
    SELECT to_char(sm.date,'YYYY-MM') m, sm.id, sm.product_id,
           sm.quantity, COALESCE(sm.value,0), sm.account_move_id
      FROM stock_move sm
     WHERE sm.state='done' AND sm.origin LIKE 'HPP-BOM konsumsi%%'
     ORDER BY sm.date""")
moves = cr.fetchall()
delta_by_month = defaultdict(float)
pair_by_month = defaultdict(lambda: defaultdict(float))   # month -> (hpp,inv) -> delta
moves_changed = 0
for m, mid, pid, qty, val, amid in moves:
    if pid not in newcost:
        continue
    oldval = float(val or 0)
    newval = float(qty or 0) * newcost[pid]
    d = newval - oldval
    if abs(d) < 0.005:
        continue
    moves_changed += 1
    delta_by_month[m] += d
    # akun dari JE move ini
    hpp_acc = inv_acc = None
    if amid:
        cr.execute("""SELECT aa.id, aml.debit FROM account_move_line aml
                        JOIN account_account aa ON aa.id=aml.account_id
                       WHERE aml.move_id=%s AND aml.debit>0
                         AND aa.account_type='expense_direct_cost' LIMIT 1""", (amid,))
        r = cr.fetchone()
        hpp_acc = r[0] if r else None
        cr.execute("""SELECT aa.id FROM account_move_line aml
                        JOIN account_account aa ON aa.id=aml.account_id
                       WHERE aml.move_id=%s AND aml.credit>0
                         AND aa.account_type IN ('asset_current','asset_fixed') LIMIT 1""", (amid,))
        r = cr.fetchone()
        inv_acc = r[0] if r else None
    if hpp_acc and inv_acc:
        pair_by_month[m][(hpp_acc, inv_acc)] += d
say("      move konsumsi yang nilainya berubah: %d" % moves_changed)

hpp_actual = net_account_moves("2026-06-01", "2026-09-01")
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

say("   %-8s %16s %16s %16s %16s %16s" % (
    "bulan", "Pendapatan", "HPP lama", "HPP baru", "Laba lama", "Laba baru"))
for m in sorted(hpp_actual):
    o, n = hpp_actual[m], hpp_actual[m] + delta_by_month.get(m, 0.0)
    r, e = rev.get(m, 0.0), opex.get(m, 0.0)
    say("   %-8s %16s %16s %16s %16s %16s" % (
        m, money(r), money(o), money(n), money(r - o - e), money(r - n - e)))

# ---------------------------------------------------------------- 4. EKSEKUSI
if RUN:
    say("")
    say("4) TULIS HARGA")
    ProdC = Prod.with_context(company_id=env.company.id)
    n = 0
    for p, old, new, usage, note in plan:
        ProdC.browse(p.id).write({"standard_price": new})
        n += 1
    env.cr.flush()
    bad = 0
    for p, old, new, usage, note in plan:
        got = ProdC.browse(p.id).standard_price
        got = got.get("1") if isinstance(got, dict) else got
        if got is None or abs(float(got) - new) > 0.005:
            bad += 1
            say("   MISMATCH id=%s %s: harap %s dapat %s" % (p.id, p.display_name, money(new), got))
    if bad:
        env.cr.rollback()
        say("   %d mismatch -> ROLLBACK" % bad)
        raise SystemExit(1)
    say("   %d standard_price komponen ditulis" % n)

if MENU:
    say("")
    say("5) HITUNG ULANG COST MENU dari BOM")
    menus = Prod.search([("sale_ok", "=", True), ("available_in_pos", "=", True)])
    n = 0
    for p in menus:
        bom = Bom.search([("product_tmpl_id", "=", p.product_tmpl_id.id),
                          ("type", "in", ("phantom", "normal"))], limit=1)
        if not bom:
            continue
        _b, lines = bom.explode(bom.product_tmpl_id, 1.0)
        cost = 0.0
        has_leaf = False
        for bl, vals in lines:
            comp = bl.product_id
            if not comp or Bom.search_count([("product_tmpl_id", "=", comp.product_tmpl_id.id)]):
                continue
            has_leaf = True
            c = comp.standard_price
            c = c.get("1") if isinstance(c, dict) else c
            cost += float(c or 0.0) * (vals.get("qty") or 0.0)
        if has_leaf and cost > 0:
            p.product_tmpl_id.write({"standard_price": cost})
            n += 1
    env.cr.flush()
    say("   %d cost menu dihitung ulang dari BOM" % n)

if ADJUST and RUN:
    say("")
    say("6) JE PENYESUAIAN HPP per bulan")
    JID = J.search([("code", "=", "MISC")], limit=1).id
    nx = 0
    for m in sorted(pair_by_month):
        ref = "Penyesuaian HPP dari harga beli klien %s" % m
        cr.execute("SELECT id FROM account_move WHERE ref=%s AND state='posted' LIMIT 1", (ref,))
        if cr.fetchone():
            say("   %s dilewati (sudah ada)" % m)
            continue
        end = {"2026-06": "2026-06-30", "2026-07": "2026-07-31", "2026-08": "2026-08-31"}.get(m)
        if not end:
            continue
        lines = []
        for (hpp, inv), d in sorted(pair_by_month[m].items()):
            if abs(d) < 0.005:
                continue
            lines.append((hpp, max(d, 0.0), max(-d, 0.0), "Penyesuaian HPP harga beli klien"))
            lines.append((inv, max(-d, 0.0), max(d, 0.0), "Penyesuaian persediaan harga beli klien"))
        if not lines:
            continue
        mv = AM.create({"move_type": "entry", "journal_id": JID, "date": end, "ref": ref,
                        "line_ids": [(0, 0, {"account_id": a, "debit": dr, "credit": kr, "name": nm})
                                     for a, dr, kr, nm in lines]})
        try:
            mv.action_post()
            nx += 1
            say("   %s -> %s  total penyesuaian %s" % (m, mv.name, money(delta_by_month.get(m, 0))))
        except Exception as e:
            say("   GAGAL %s: %s" % (m, repr(e)[:150]))
            env.cr.rollback()
    say("   %d JE penyesuaian dibuat" % nx)

if RUN:
    env.cr.commit()
    say("")
    say("COMMITTED.")
else:
    env.cr.rollback()
    say("")
    say("DRY-RUN — tidak ada perubahan. Jalankan dengan RUN=1 untuk menulis.")
say("=" * 104)
