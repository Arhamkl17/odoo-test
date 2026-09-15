# -*- coding: utf-8 -*-
"""
RECON READ-ONLY LANJUTAN (teknis) — bahan untuk tahap 8-11 JUNI_JULI_DATA-spec.md.

A. POS SESSION — field wajib, cara Agustus dibuat, JE yang terbentuk, integrity
   payment-method -> journal/account (temuan BNKB aktif tapi akunnya mati).
B. account.asset (OCA account_asset_management) — model & field profil 7 kelas.
C. BOM & STOK — komponen per menu, konsumsi Agustus per komponen, kebutuhan
   pembelian Juni/Juli.

Read-only: env.cr.rollback() di akhir.
"""
from collections import defaultdict

SEP = "=" * 78
def sec(t): print("\n" + SEP + "\n" + t + "\n" + SEP)
def rp(v): return "%16.2f" % (v or 0.0)

Aml = env["account.move.line"]
Acc = env["account.account"].with_context(active_test=False)
Journal = env["account.journal"].with_context(active_test=False)
POST = [("parent_state", "=", "posted")]


# ===========================================================================
sec("A1. POS SESSION — model & field relevan")
# ===========================================================================
Sess = env["pos.session"]
fields = ["name", "state", "start_at", "stop_at", "config_id", "user_id", "move_id",
          "cash_register_balance_start", "cash_register_balance_end_real",
          "update_stock_at_closing", "sequence_number", "opening_control", "closing_control"]
print("field yang ada:")
for f in fields:
    print("   %-34s %s" % (f, "ADA (%s)" % Sess._fields[f].type if f in Sess._fields else "TIDAK ADA"))
print("\nsemua method action_* di pos.session:")
print("   ", [m for m in dir(Sess) if m.startswith("action_")])

print("\nsesi Agustus (10 contoh pertama):")
aug = Sess.search([("start_at", ">=", "2026-08-01"), ("start_at", "<", "2026-09-01")], order="start_at", limit=10)
for s in aug:
    print("   [%d] %-22s %s -> %-19s state=%-8s move=%s" % (
        s.id, s.name, s.start_at, s.stop_at, s.state, s.move_id.name if s.move_id else "-"))

print("\ncreate/write info sesi Agustus (dibuat script atau interaktif?):")
for s in aug[:5]:
    print("   %-22s create_uid=%s create_date=%s | write_uid=%s write_date=%s" % (
        s.name, s.create_uid.name if s.create_uid else "-", s.create_date,
        s.write_uid.name if s.write_uid else "-", s.write_date))

print("\njurnal POS (pos.config):")
for c in env["pos.config"].search([]):
    print("   [%d] %-24s journal=%s | payment_methods=%s" % (
        c.id, c.name, getattr(c, "journal_id", None) and c.journal_id.code,
        c.payment_method_ids.mapped("name")))

print("\nJUMAL POSS & statement line sesi Agustus:")
poss_moves = env["account.move"].search([("journal_id.code", "=", "POSS"), ("date", ">=", "2026-08-01"), ("date", "<", "2026-09-01")])
print("   move jurnal POSS Agustus: %d" % len(poss_moves))
for m in poss_moves[:4]:
    print("   %s | %s | %s" % (m.name, m.date, m.state))
ssl = env["account.bank.statement.line"].search_count([("date", ">=", "2026-08-01"), ("date", "<", "2026-09-01")])
print("   account.bank.statement.line Agustus: %d" % ssl)


# ===========================================================================
sec("A2. INTEGRITY: pos.payment.method -> journal & akun (RISIKO utk Juni/Juli)")
# ===========================================================================
print("%-4s %-26s %-8s %-8s %-30s" % ("ID", "NAME", "ACTIVE", "JOURNAL", "RECEIVABLE ACCOUNT"))
risky = []
for pm in env["pos.payment.method"].with_context(active_test=False).search([], order="id"):
    j = pm.journal_id
    rc = pm.receivable_account_id
    print("%-4d %-26s %-8s %-8s %-30s" % (
        pm.id, (pm.name or "-")[:26], pm.active, j.code if j else "-",
        ("%s %s active=%s" % (rc.code, rc.name[:18], rc.active)) if rc else "-"))
    if j and not j.active:
        risky.append("PM %s -> journal %s NONAKTIF" % (pm.name, j.code))
    if j and j.default_account_id and not j.default_account_id.active:
        risky.append("PM %s -> journal %s default account %s NONAKTIF" % (
            pm.name, j.code, j.default_account_id.code))
print("\nRISIKO yang terdeteksi:")
for r in sorted(set(risky)) or ["(tidak ada)"]:
    print("   -", r)


# ===========================================================================
sec("B1. ACCOUNT.ASSET (OCA) — model yang tersedia")
# ===========================================================================
for m in env["ir.model"].search([("model", "like", "asset")], order="model"):
    print("   %-42s %s" % (m.model, m.name))
print("\nrecord per model:")
for mn in ("account.asset", "account.asset.category", "account.asset.profile", "account.asset.line"):
    if mn in env:
        print("   %-30s %d record" % (mn, env[mn].search_count([])))


# ===========================================================================
sec("B2. FIELD account.asset yang relevan untuk 7 kelas aset")
# ===========================================================================
if "account.asset" in env:
    A = env["account.asset"]
    wanted = ["name", "code", "asset_type", "profile_id", "category_id", "date", "date_start",
              "purchase_value", "salvage_value", "method", "method_number", "method_period",
              "method_progress_factor", "method_end", "prorata_date", "account_asset_id",
              "account_depreciation_id", "account_depreciation_expense_id", "journal_id",
              "state", "company_id", "currency_id"]
    print("%-38s %-10s %s" % ("FIELD", "TYPE", "CATATAN"))
    for f in wanted:
        if f in A._fields:
            fl = A._fields[f]
            print("%-38s %-10s store=%s required=%s" % (f, fl.type, fl.store, fl.required))
        else:
            print("%-38s %-10s (tidak ada)" % (f, "-"))
    print("\nfield lain yang mungkin berguna:")
    print("   ", sorted([k for k in A._fields if any(s in k for s in ("account", "method", "date", "value", "profile", "deprec"))]))
    print("\nselection 'method':", A._fields["method"].selection if "method" in A._fields else "-")


# ===========================================================================
sec("C1. BOM — struktur & komponen")
# ===========================================================================
Bom = env["mrp.bom"]
boms = Bom.search([("type", "=", "phantom")])
print("mrp.bom phantom: %d | bom.line: %d" % (len(boms), env["mrp.bom.line"].search_count([])))
print("contoh 3 BOM:")
for b in boms[:3]:
    print("   [%d] %s (qty %s) — %d komponen" % (
        b.id, b.product_tmpl_id.name[:34], b.product_qty, len(b.bom_line_ids)))
    for bl in b.bom_line_ids:
        print("        - %-38s qty %-10s %s" % (
            bl.product_id.display_name[:38], bl.product_qty, bl.product_uom_id.name))

comp_usage = defaultdict(float)   # component_id -> qty total Agustus
menu_qty = defaultdict(float)
POL = env["pos.order.line"]
rows = POL._read_group(
    [("order_id.date_order", ">=", "2026-08-01"), ("order_id.date_order", "<", "2026-09-01"),
     ("order_id.state", "in", ["done", "invoiced", "paid"])],
    ["product_id"], ["qty:sum", "price_subtotal:sum"])
print("\nmenu terjual Agustus: %d produk" % len(rows))
bom_by_tmpl = {}
for b in boms:
    bom_by_tmpl.setdefault(b.product_tmpl_id.id, b)

n_missing_bom = 0
for prod, qty, subtotal in sorted(rows, key=lambda x: -(x[1] or 0)):
    qty = qty or 0.0
    menu_qty[prod.id] = qty
    b = bom_by_tmpl.get(prod.product_tmpl_id.id)
    if not b:
        n_missing_bom += 1
        continue
    for bl in b.bom_line_ids:
        per = (bl.product_qty or 0.0) / (b.product_qty or 1.0)
        comp_usage[bl.product_id.id] += per * qty

print("menu tanpa BOM: %d" % n_missing_bom)
print("\nkomponen: %d produk | total baris konsumsi dihitung: %d" % (len(comp_usage), len(boms)))


# ===========================================================================
sec("C2. KEBUTUHAN PEMBELIAN JUNI/JULI (turunan)")
# ===========================================================================
print("skala: Juni 0,35x Agustus (11 hari) · Juli 0,97x · Agustus 1,00x")
aug_cons = 109548621.18
purch_aug = 98424681.63
stock_now = 25002950.61
target_end_jul = 32973597.10
cons_jun_jul = aug_cons * (0.35 + 0.97)
purch_jun_jul = target_end_jul + cons_jun_jul - 0.0   # mulai stok 0 di Juni
print("   konsumsi Juni+Juli (estimasi) : Rp %s" % rp(cons_jun_jul).strip())
print("   pembelian Juni+Juli harus ≈   : Rp %s" % rp(purch_jun_jul).strip())
print("   cek Agustus: %s + %s - %s + 3.153.293,06 = %s" % (
    rp(target_end_jul).strip(), rp(purch_aug).strip(), rp(aug_cons).strip(),
    rp(target_end_jul + purch_aug - aug_cons + 3153293.06).strip()))

print("\nstok 15 komponen terbesar (nilai quant saat ini):")
Quant = env["stock.quant"]
qrows = Quant._read_group([("location_id.usage", "=", "internal")], ["product_id"], ["quantity:sum", "value:sum"])
for prod, qty, val in sorted(qrows, key=lambda x: -(x[2] or 0))[:15]:
    need = comp_usage.get(prod.id, 0.0)
    print("   %-40s stok %-12.2f nilai %s | kebutuhan/bln (Agustus) %-10.2f" % (
        prod.display_name[:40], qty or 0.0, rp(val).strip(), need))

print("\nkomponen dengan kebutuhan Agustus TERTINGGI (dari BOM):")
for pid, need in sorted(comp_usage.items(), key=lambda x: -x[1])[:15]:
    p = env["product.product"].browse(pid)
    print("   %-40s butuh %-12.2f %s" % (p.display_name[:40], need, p.uom_id.name))

print("\n[RECON DEEP SELESAI — read-only]")
env.cr.rollback()
