"""
recon_dashboard_data.py — Recon 100% READ-ONLY untuk persiapan dashboard.

Tidak menulis/mengubah/menghapus apa pun. Semua aksi = search_read / read /
fields_get / call_kw read-only.

Cara pakai:
    ODOO_URL=http://localhost:8069 ODOO_DB=Test1 ODOO_USER=admin ODOO_PASSWORD=admin \
        python3 scripts/recon_dashboard_data.py
"""
import xmlrpc.client
import os
import json
from datetime import datetime

url = os.environ.get("ODOO_URL", "http://localhost:8069")
db = os.environ.get("ODOO_DB", "Test1")
user = os.environ.get("ODOO_USER", "admin")
password = os.environ.get("ODOO_PASSWORD", "admin")

DATE_FROM = "2026-08-01"
DATE_TO = "2026-08-31"  # inclusive saat dipakai dengan '<' → 2026-09-01

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, user, password, {})
if not uid:
    raise SystemExit("AUTH GAGAL — cek ODOO_USER/ODOO_PASSWORD")
print(f"OK auth: db={db} uid={uid} server={common.version().get('server_version')}")
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")


def call(model, method, *args, **kw):
    return models.execute_kw(db, uid, password, model, method, list(args), kw)


def search_read(model, domain, fields, **kw):
    return call(model, "search_read", domain, fields=fields, **kw)


def count(model, domain):
    return call(model, "search_count", domain)


def section(title):
    print(f"\n{'=' * 60}\n== {title}\n{'=' * 60}")


# ------------------------------------------------------------------
section("0. Company & currency")
companies = search_read("res.company", [], ["id", "name", "currency_id"])
print(json.dumps(companies, ensure_ascii=False))

# ------------------------------------------------------------------
section("1. POS — config/outlet & session Agustus")
configs = search_read("pos.config", [], ["id", "name", "stock_location_id"])
print("pos.config:", json.dumps(configs, ensure_ascii=False, default=str))
sess = search_read(
    "pos.session",
    [["start_at", ">=", DATE_FROM], ["start_at", "<", "2026-09-01"]],
    ["id", "name", "config_id", "start_at", "stop_at", "state", "cash_register_balance_end"],
    order="start_at",
)
print(f"pos.session Agustus: {len(sess)}")
for s in sess[:10]:
    print("  ", s)

# ------------------------------------------------------------------
section("2. pos.order Agustus — distribusi state, field channel, total")
dom_aug = [["date_order", ">=", DATE_FROM], ["date_order", "<", "2026-09-01"]]
for st in ["posted", "paid", "done", "invoiced", "draft", "cancel"]:
    try:
        print(f"  state={st}: {count('pos.order', dom_aug + [['state', '=', st]])}")
    except Exception as e:
        print(f"  state={st}: ERR {e}")

# field kandidat penanda channel (dine-in/takeaway) & orders
fpos = call("pos.order", "fields_get", [], attributes=["string", "type"])
cand = [k for k in fpos if any(w in k for w in ("take", "channel", "order_type", "customer_count", "table"))]
print("field kandidat channel di pos.order:", cand)

sample = search_read(
    "pos.order",
    dom_aug + [["state", "in", ["posted", "paid", "done", "invoiced"]]],
    ["id", "name", "date_order", "config_id", "session_id", "amount_total", "partner_id",
     "user_id", "table_id", "customer_count"] + cand[:6],
    limit=3, order="date_order desc",
)
print("sample orders:", json.dumps(sample, ensure_ascii=False, default=str))

total_aug = call("pos.order", "read_group",
                 dom_aug + [["state", "in", ["posted", "paid", "done", "invoiced"]]],
                 ["amount_total:sum"], groupby=["config_id"])
print("omzet per config Agustus:", json.dumps(total_aug, ensure_ascii=False, default=str))

# ------------------------------------------------------------------
section("3. pos.payment & metode pembayaran")
pays = search_read("pos.payment.method", [], ["id", "name", "journal_id", "is_cash_count", "split_transactions"])
print("payment methods:", json.dumps(pays, ensure_ascii=False, default=str))
pay_sum = call("pos.payment", "read_group",
               [["pos_order_id", "in", call("pos.order", "search", dom_aug + [["state", "in", ["posted", "paid", "done", "invoiced"]]])]],
               ["amount:sum"], groupby=["payment_method_id"])
print("total per metode (Agustus):", json.dumps(pay_sum, ensure_ascii=False, default=str))

# ------------------------------------------------------------------
section("4. account.move Agustus — journal & tipe")
am_sum = call("account.move", "read_group",
              [["invoice_date", ">=", DATE_FROM], ["invoice_date", "<", "2026-09-01"], ["state", "=", "posted"]],
              ["amount_total:sum", "amount_untaxed:sum"], groupby=["journal_id"])
print("per journal (invoice_date Agustus, posted):", json.dumps(am_sum, ensure_ascii=False, default=str))
journals = search_read("account.journal", [], ["id", "name", "type", "code"])
print("journals:", json.dumps(journals, ensure_ascii=False, default=str))

# P&L / neraca: pakai account.account + read_group saldo (read-only, tanpa wizard)
accounts = search_read("account.account", [], ["id", "name", "code", "account_type"], limit=500)
type_counts = {}
for a in accounts:
    type_counts[a["account_type"]] = type_counts.get(a["account_type"], 0) + 1
print("distribusi account_type:", type_counts)

# ------------------------------------------------------------------
section("5. Aset & penyusutan (account_asset_management)")
ir_model = search_read("ir.model", [["model", "like", "account.asset"]], ["model", "name"])
print("model aset:", json.dumps(ir_model, ensure_ascii=False))
for m in [x["model"] for x in ir_model]:
    try:
        n = count(m, [])
        print(f"  {m}: {n} record")
        if n:
            rows = search_read(m, [], ["id", "name", "state"], limit=5)
            print("   sample:", json.dumps(rows, ensure_ascii=False, default=str))
    except Exception as e:
        print(f"  {m}: ERR {e}")

# ------------------------------------------------------------------
section("6. Stok — gudang, kuant, valuasi, scrap Agustus")
whs = search_read("stock.warehouse", [], ["id", "name", "code", "lot_stock_id"])
print("gudang:", json.dumps(whs, ensure_ascii=False, default=str))
try:
    qsum = call("stock.quant", "read_group", [["location_id.usage", "=", "internal"]],
                ["value:sum", "quantity:sum"], [])
    print("nilai persediaan (stock.quant.value):", qsum)
except Exception as e:
    print("stock.quant.value ERR:", e)
try:
    vsl = call("stock.valuation.layer", "read_group",
               [["create_date", ">=", DATE_FROM], ["create_date", "<", "2026-09-01"]],
               ["value:sum", "quantity:sum"], [])
    print("stock.valuation.layer Agustus:", vsl)
except Exception as e:
    print("stock.valuation.layer ERR:", e)
n_scrap = count("stock.scrap", [["date", ">=", DATE_FROM], ["date", "<", "2026-09-01"]])
print("stock.scrap Agustus:", n_scrap)
if n_scrap:
    print("  sample:", search_read("stock.scrap", [["date", ">=", DATE_FROM], ["date", "<", "2026-09-01"]],
                                   ["id", "product_id", "scrap_qty", "scrap_location_id", "state"], limit=5))

# ------------------------------------------------------------------
section("7. Piutang corporate belum lunas")
rec = search_read(
    "account.move",
    [["move_type", "in", ["out_invoice", "out_refund"]], ["state", "=", "posted"],
     ["payment_state", "in", ["not_paid", "partial"]]],
    ["id", "name", "partner_id", "invoice_date_due", "amount_total", "amount_residual", "journal_id"],
    limit=20, order="invoice_date_due",
)
print(f"faktur customer open: {len(rec)}")
for r in rec[:10]:
    print("  ", r)

# ------------------------------------------------------------------
section("8. Data Juli (untuk perbandingan vs bln lalu)")
jul = call("pos.order", "read_group",
           [["date_order", ">=", "2026-07-01"], ["date_order", "<", "2026-08-01"],
            ["state", "in", ["posted", "paid", "done", "invoiced"]]],
           ["amount_total:sum", "id:count"], [])
print("POS Juli:", jul)
aug = call("pos.order", "read_group",
           [["date_order", ">=", DATE_FROM], ["date_order", "<", "2026-09-01"],
            ["state", "in", ["posted", "paid", "done", "invoiced"]]],
           ["amount_total:sum", "id:count"], [])
print("POS Agustus:", aug)

print("\nRECON SELESAI — tidak ada data yang diubah.")
