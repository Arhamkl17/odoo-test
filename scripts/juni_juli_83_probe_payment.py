# -*- coding: utf-8 -*-
"""juni_juli_83_probe_payment.py — recon metode bayar / jurnal kas (READ-ONLY)."""
PM = env["pos.payment.method"]
AJ = env["account.journal"]
AA = env["account.account"]
Config = env["pos.config"]
say = lambda m="": print(m)

say("=" * 112)
say("METODE BAYAR")
say("=" * 112)
for m in PM.search([]):
    j = m.journal_id
    cfgs = Config.search([("payment_method_ids", "in", m.ids)])
    say("id=%-4s %-28s journal=%-22s type=%-6s company=%s | config: %s" % (
        m.id, m.name[:28], (j.code or "-") if j else "-", (j.type or "-") if j else "-",
        m.company_id.name, ", ".join(cfgs.mapped("name")) or "-"))

say("")
say("=" * 112)
say("FIELD WAJIB (required) yang belum ada default")
say("=" * 112)
for model, keys in [
    ("pos.payment.method", ["name", "journal_id", "company_id", "receivable_account_id"]),
    ("account.journal", ["name", "code", "type", "company_id", "default_account_id"]),
    ("account.account", ["name", "code", "account_type", "company_ids", "currency_id"]),
    ("pos.config", ["name", "journal_id", "invoice_journal_id", "picking_type_id", "payment_method_ids"]),
]:
    f = env[model].fields_get()
    say("")
    say("   %s" % model)
    for k in keys:
        if k in f:
            say("      %-22s type=%-12s required=%-5s default=%s" % (
                k, f[k].get("type"), bool(f[k].get("required")),
                str(f[k].get("default"))[:40]))

say("")
say("=" * 112)
say("JURNAL yang ada")
say("=" * 112)
for j in AJ.search([]):
    n = PM.search_count([("journal_id", "=", j.id)])
    say("id=%-4s %-8s %-30s type=%-8s akun=%s | dipakai %d metode bayar" % (
        j.id, j.code, j.name[:30], j.type, (j.default_account_id.code if j.default_account_id else "-"), n))

env.cr.rollback()
