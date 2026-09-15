"""explain_unused_modules.py — READ-ONLY evidence why the 4 candidates were never used.

Run:
  odoo shell -d Test1 --no-http --db_host db --db_port 5432 --db_user odoo --db_password odoo < scripts/explain_unused_modules.py
All read-only; rolled back at the end.
"""

print("=" * 70)
print("WHY ARE THESE MODULES UNUSED? — evidence from Test1")

# ---- 1. account_check_deposit: is there ANY check/giro payment in the business?
print("-" * 70)
print("1) account_check_deposit — needs checks/giro (cek/giro) from customers")
try:
    methods = env["account.payment.method"].search([])
    check_like = [m for m in methods if "check" in (m.code or "").lower() or "check" in (m.name or "").lower()]
    print("   payment methods total: %d | check-like: %s" % (
        len(methods), [(m.code, m.name) for m in check_like] or "NONE"))
except Exception as e:  # noqa: BLE001
    print("   payment method probe failed:", e)
try:
    pml = env["account.payment.method.line"].search([])
    j_with_check = sorted({l.journal_id.name for l in pml if "check" in (l.payment_method_id.code or "").lower()})
    print("   journals configured for check payments:", j_with_check or "NONE")
except Exception as e:  # noqa: BLE001
    print("   payment method line probe failed:", e)
print("   account.check.deposit records: 0 (verified earlier)")

# ---- 2. account_move_template: recurring JE templates
print("-" * 70)
print("2) account_move_template — needs recurring manual journal entries")
print("   account.move.template records: 0 (verified earlier)")
try:
    n_misc = env["account.move"].search_count([("move_type", "=", "entry")])
    print("   manual journal entries (move_type=entry) exist: %d — booked directly, no templates" % n_misc)
except Exception as e:  # noqa: BLE001
    print("   misc JE probe failed:", e)

# ---- 3. account_netting: needs a partner that is BOTH customer AND supplier
print("-" * 70)
print("3) account_netting — needs partners with both AR and AP to offset")
try:
    aml = env["account.move.line"]
    ar_partners = aml.search([
        ("account_id.account_type", "=", "asset_receivable"),
        ("parent_state", "=", "posted"),
    ]).mapped("partner_id")
    ap_partners = aml.search([
        ("account_id.account_type", "=", "liability_payable"),
        ("parent_state", "=", "posted"),
    ]).mapped("partner_id")
    both = (ar_partners & ap_partners).mapped("name")
    print("   partners with AR: %d | with AP: %d | with BOTH: %s" % (
        len(ar_partners), len(ap_partners), both or "NONE"))
except Exception as e:  # noqa: BLE001
    print("   AR/AP probe failed:", e)

# ---- 4. account_fiscal_position_vat_check: needs fiscal positions + VAT warnings configured
print("-" * 70)
print("4) account_fiscal_position_vat_check — needs fiscal positions with VAT check on")
try:
    fps = env["account.fiscal.position"].search([])
    print("   account.fiscal.position records: %d" % len(fps))
    for fp in fps:
        vat = getattr(fp, "vat_required", "n/a")
        print("     - %s | vat_required=%s" % (fp.name, vat))
except Exception as e:  # noqa: BLE001
    print("   fiscal position probe failed:", e)
print("   res.partner with show_warning_vat_required=True: 0 (verified earlier)")

env.cr.rollback()
print("=" * 70)
print("DONE — read-only.")
