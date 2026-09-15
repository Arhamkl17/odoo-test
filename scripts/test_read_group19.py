"""test_read_group19.py — cek API _read_group Odoo 19. READ-ONLY."""
env  # noqa: F821

Order = env["pos.order"]
dom = [["date_order", ">=", "2026-08-01"], ["date_order", "<", "2026-09-01"],
       ["state", "in", ["done", "invoiced"]]]

# total tanpa groupby
try:
    r = Order._read_group(dom, [], ["amount_total:sum"])
    print("no-groupby:", r)
except Exception as e:
    print("no-groupby ERR:", e)

# groupby config
try:
    r = Order._read_group(dom, ["config_id"], ["amount_total:sum", "id:count"])
    print("by-config:", r)
except Exception as e:
    print("by-config ERR:", e)

# groupby day (date.truncate)
try:
    r = Order._read_group(dom, ["date_order:day"], ["amount_total:sum"])
    print("by-day len:", len(r), "| first:", r[0] if r else None)
except Exception as e:
    print("by-day ERR:", e)

# groupby relation with spec dict?
try:
    r = Order._read_group(dom, ["partner_id"], ["amount_total:sum"])
    print("by-partner:", r[:6])
except Exception as e:
    print("by-partner ERR:", e)

env.cr.rollback()
print("DONE")
