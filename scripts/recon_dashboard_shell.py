"""
recon_dashboard_shell.py — Recon 100% READ-ONLY via `odoo shell`.

Jalankan:
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 --db_user odoo --db_password odoo" < scripts/recon_dashboard_shell.py
"""
import json

env  # noqa: F821  (disediakan odoo shell)

DATE_FROM = "2026-08-01"
DATE_TO_EX = "2026-09-01"


def sec(title):
    print("\n" + "=" * 60 + f"\n== {title}\n" + "=" * 60)


def sr(model, domain, fields, **kw):
    return env[model].search_read(domain, fields, **kw)


def cnt(model, domain):
    return env[model].search_count(domain)


# ------------------------------------------------------------------
sec("0. Company & currency")
print(json.dumps(env["res.company"].search_read([], ["name", "currency_id"]), ensure_ascii=False, default=str))

# ------------------------------------------------------------------
sec("1. POS config/outlet & session Agustus")
print("pos.config:", json.dumps(sr("pos.config", [], ["name"]), ensure_ascii=False, default=str))
sess = sr("pos.session",
          [["start_at", ">=", DATE_FROM], ["start_at", "<", DATE_TO_EX]],
          ["name", "config_id", "start_at", "stop_at", "state"], order="start_at")
print(f"pos.session Agustus: {len(sess)}")
for s in sess[:8]:
    print("  ", s)

# ------------------------------------------------------------------
sec("2. pos.order Agustus — state, channel fields, omzet")
dom_aug = [["date_order", ">=", DATE_FROM], ["date_order", "<", DATE_TO_EX]]
ST = ["posted", "paid", "done", "invoiced"]
for st in ST + ["draft", "cancel"]:
    print(f"  state={st}: {cnt('pos.order', dom_aug + [['state', '=', st]])}")

flds = env["pos.order"].fields_get([], attributes=["string", "type"])
cand = [k for k in flds if any(w in k for w in ("take", "channel", "order_type", "customer_count", "table"))]
print("kandidat field channel:", cand)

print("omzet per config:",
      json.dumps(env["pos.order"].read_group(dom_aug + [["state", "in", ST]],
                                             ["amount_total:sum"], ["config_id"]),
                 ensure_ascii=False, default=str))
print("sample:",
      json.dumps(sr("pos.order", dom_aug + [["state", "in", ST]],
                    ["name", "date_order", "config_id", "amount_total", "partner_id",
                     "table_id", "customer_count"], limit=3, order="date_order desc"),
                 ensure_ascii=False, default=str))

# ------------------------------------------------------------------
sec("3. pos.payment & metode")
print("payment methods:",
      json.dumps(sr("pos.payment.method", [], ["name", "journal_id", "is_cash_count"]),
                 ensure_ascii=False, default=str))
order_ids = env["pos.order"].search(dom_aug + [["state", "in", ST]]).ids
print("total per metode:",
      json.dumps(env["pos.payment"].read_group([["pos_order_id", "in", order_ids]],
                                               ["amount:sum"], ["payment_method_id"]),
                 ensure_ascii=False, default=str))

# ------------------------------------------------------------------
sec("4. account.move Agustus per journal + tipe akun")
print("per journal:",
      json.dumps(env["account.move"].read_group(
          [["invoice_date", ">=", DATE_FROM], ["invoice_date", "<", DATE_TO_EX], ["state", "=", "posted"]],
          ["amount_total:sum", "amount_untaxed:sum"], ["journal_id"]),
          ensure_ascii=False, default=str))
accs = sr("account.account", [], ["code", "name", "account_type"], limit=500)
tc = {}
for a in accs:
    tc[a["account_type"]] = tc.get(a["account_type"], 0) + 1
print("distribusi account_type:", tc)

# ------------------------------------------------------------------
sec("5. Aset & penyusutan (account_asset_management)")
ims = [m for m in env["ir.model"].search([]).mapped("model") if "account.asset" in m]
print("model aset:", ims)
for m in ims:
    try:
        n = cnt(m, [])
        print(f"  {m}: {n}")
        if n:
            print("   sample:", json.dumps(sr(m, [], ["name", "state"], limit=5), ensure_ascii=False, default=str))
    except Exception as e:
        print(f"  {m}: ERR {e}")

# ------------------------------------------------------------------
sec("6. Stok — gudang, valuasi, scrap")
print("gudang:", json.dumps(sr("stock.warehouse", [], ["name", "code", "lot_stock_id"]),
                            ensure_ascii=False, default=str))
try:
    print("nilai persediaan (quants):",
          env["stock.quant"].read_group([["location_id.usage", "=", "internal"]],
                                        ["value:sum", "quantity:sum"], []))
except Exception as e:
    print("quant value ERR:", e)
try:
    print("valuation layer Agustus:",
          env["stock.valuation.layer"].read_group(
              [["create_date", ">=", DATE_FROM], ["create_date", "<", DATE_TO_EX]],
              ["value:sum", "quantity:sum"], []))
except Exception as e:
    print("svl ERR:", e)
n_scrap = cnt("stock.scrap", [["date", ">=", DATE_FROM], ["date", "<", DATE_TO_EX]])
print("stock.scrap Agustus:", n_scrap)
if n_scrap:
    print(" sample:", json.dumps(sr("stock.scrap", [["date", ">=", DATE_FROM], ["date", "<", DATE_TO_EX]],
                                    ["product_id", "scrap_qty", "state"], limit=5),
                                  ensure_ascii=False, default=str))

# ------------------------------------------------------------------
sec("7. Piutang corporate belum lunas")
rec = sr("account.move",
         [["move_type", "in", ["out_invoice", "out_refund"]], ["state", "=", "posted"],
          ["payment_state", "in", ["not_paid", "partial"]]],
         ["name", "partner_id", "invoice_date_due", "amount_total", "amount_residual"],
         limit=20, order="invoice_date_due")
print(f"faktur customer open: {len(rec)}")
for r in rec[:10]:
    print("  ", r)

# ------------------------------------------------------------------
sec("8. Juli vs Agustus (POS)")
for label, d1, d2 in [("Juli", "2026-07-01", "2026-08-01"), ("Agustus", DATE_FROM, DATE_TO_EX)]:
    print(label, env["pos.order"].read_group(
        [["date_order", ">=", d1], ["date_order", "<", d2], ["state", "in", ST]],
        ["amount_total:sum", "id:count"], []))

env.cr.rollback()  # safety: pastikan tidak ada perubahan tersimpan
print("\nRECON SELESAI — read-only, rollback dilakukan.")
