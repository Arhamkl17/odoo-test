# Copyright 2026 Geprekyukss
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    "name": "MIS Builder - Resolve Inactive Account Names",
    "version": "19.0.1.0.0",
    "category": "Accounting/Accounting",
    "summary": "Fix KeyError when MIS report detail rows reference archived accounts",
    "description": """
KPI detail rows ("details by account") may reference accounts that were
archived while their posted journal entries are kept for the audit trail.
mis_builder evaluates account expressions including inactive accounts
(AEP uses active_test=False), but loads the detail row labels with a
plain search() that hides them, raising KeyError (e.g. "KeyError: 225")
when rendering the report.

This module builds the KPI matrix with active_test=False so every
account that can appear in a detail row also gets its name resolved.
No account is reactivated and no mis_builder file is modified; it
applies to all report instances (existing and future).
""",
    "author": "Custom - Geprekyukss",
    "license": "AGPL-3",
    "depends": [
        "mis_builder",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
