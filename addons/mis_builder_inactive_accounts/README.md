# MIS Builder - Resolve Inactive Account Names

Patch module for OCA `mis_builder` (no upstream file is modified).

## Problem

Clicking *Preview* on a MIS Report Instance crashed with:

```
KeyError: 225
File ".../mis_builder/models/kpimatrix.py", line 507, in get_account_name
    return self._account_names[account_id]
```

Cause: `aep.py` evaluates account expressions with `active_test=False`,
so KPI detail rows can reference **archived** accounts (kept inactive on
purpose, with their posted journal entries preserved for the audit
trail). But `KpiMatrix._load_account_names()` uses a plain `search()`
that hides inactive accounts, so their label cannot be resolved.

## Fix

`mis.report.prepare_kpi_matrix()` is overridden to build the `KpiMatrix`
with `active_test=False`, aligning the label lookup with the expression
engine. Accounts are **not** reactivated.

Affected accounts in this database (all inactive with posted lines):
OVO/GOPAY/SHOPEE PAY (1101.03-05), Bank BCA/BNI/BRI/Mandiri
(1101.06-09), 11210010 Piutang Usaha, 11120003 Tanda Terima Belum Lunas.
