"""verify_uninstall_candidates.py — READ-ONLY re-verification before uninstall.

Run:
  odoo shell -d Test1 --no-http --db_host db --db_port 5432 --db_user odoo --db_password odoo < scripts/verify_uninstall_candidates.py

Checks (against DB Test1, today):
  1. The 4 candidate modules: state, ir_model_data count, record counts of their
     primary models (new models only — _inherit-only modules have no new table).
  2. Reverse dependency graph: which installed modules depend on each candidate.
  3. Active usage traces: account.journal referencing deposit/check accounts,
     view/model-data references from OTHER modules.
No writes are performed; every transaction is rolled back.
"""

CANDIDATES = [
    "account_check_deposit",
    "account_move_template",
    "account_netting",
    "account_fiscal_position_vat_check",
]

# primary NEW models per candidate (_inherit-only modules own no records)
PRIMARY_MODELS = {
    "account_check_deposit": ["account.check.deposit"],
    "account_move_template": ["account.move.template", "account.move.template.line"],
    "account_netting": ["account.move.make.netting"],
    "account_fiscal_position_vat_check": [],
}

IrModule = env["ir.module.module"]
IrModelData = env["ir.model.data"]
IrModel = env["ir.model"]

print("=" * 70)
print("RE-VERIFICATION %s — DB Test1" % env.cr.now())

# 0) which DBs exist / current db name
print("current database:", env.cr.dbname)

# 1) module state + record counts
for name in CANDIDATES:
    mod = IrModule.search([("name", "=", name)])
    print("-" * 70)
    if not mod:
        print("%s: NOT FOUND in ir_module_module" % name)
        continue
    print("%s: state=%s | version=%s" % (
        name, mod.state, mod.latest_version))
    n_data = IrModelData.search_count([("module", "=", name)])
    print("  ir.model.data entries owned by module: %d" % n_data)
    for model_name in PRIMARY_MODELS.get(name, []):
        try:
            count = env[model_name].search_count([])
        except Exception as e:  # noqa: BLE001
            count = "ERROR: %s" % e
        print("  %s: %s record(s)" % (model_name, count))

# 2) reverse dependency graph among installed modules
print("=" * 70)
print("REVERSE DEPENDENCY CHECK (installed modules that depend on candidates)")
Dep = env["ir.module.module.dependency"]
for name in CANDIDATES:
    deps = Dep.search([("name", "=", name)])
    dependents = []
    for d in deps:
        m = d.module_id
        if m.name != name and m.state == "installed":
            dependents.append(m.name)
    if dependents:
        print("  %s <- DEPENDED ON BY: %s" % (name, ", ".join(dependents)))
    else:
        print("  %s <- no installed module depends on it ✔" % name)

# 3) usage traces beyond record counts
print("=" * 70)
print("USAGE TRACES")
# 3a. journals pointing at check-deposit style accounts
journals = env["account.journal"].search([])
jd = {}
for j in journals:
    labels = []
    for f in ("default_account_id", "suspense_account_id", "payment_credit_account_id", "payment_debit_account_id"):
        acc = getattr(j, f, False)
        if acc:
            labels.append("%s=%s" % (f, acc.code))
    if labels:
        jd[j.name] = labels
print("  journals with deposit/suspense accounts:")
for jn, labels in jd.items():
    print("    -", jn, "->", "; ".join(labels))

# 3b. any ir.model.data owned by candidate modules referenced by other modules
for name in CANDIDATES:
    xmlids = IrModelData.search([("module", "=", name)])
    other_refs = []
    for x in xmlids:
        # count external xmlid references pointing at the same record
        same_rec = IrModelData.search_count([
            ("model", "=", x.model), ("res_id", "=", x.res_id), ("id", "!=", x.id),
        ])
        if same_rec:
            other_refs.append("%s/%s (%s)" % (x.module, x.name, x.model))
    print("  %s: xmlids also referenced by other module data: %s" % (
        name, other_refs if other_refs else "none ✔"))

# 3c. fiscal position vat check: usage = field show_warning_vat_required set on partners
# (non-stored computed field -> check in Python, not SQL)
n_flagged = sum(
    1 for p in env["res.partner"].search([]) if p.show_warning_vat_required
)
print("  res.partner with show_warning_vat_required=True: %d" % n_flagged)

env.cr.rollback()
print("=" * 70)
print("DONE — read-only, all rolled back.")
