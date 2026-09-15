# Copyright 2026 Geprekyukss
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

"""Keep inactive accounts resolvable in MIS Builder detail rows.

mis_builder's account expression engine (``aep.py``) evaluates
expressions with ``active_test=False``, so KPI detail rows ("details by
account") can reference accounts that have been archived — e.g. old
bank/e-wallet accounts deactivated during a chart-of-accounts cleanup
while their historical posted journal entries are retained for audit.

``KpiMatrix`` however loads detail row labels with a plain ``search()``
on ``account.account``, which implicitly excludes inactive records, so
``get_account_name()`` raises ``KeyError`` when rendering the report
(an upstream gap — there is no official option for this).

Building the KPI matrix with ``active_test=False`` in the environment
aligns the account name lookup with the expression evaluation behaviour:
every account that can appear in a detail row can also get its name
resolved. This is deliberately done at ``mis.report.prepare_kpi_matrix``
level, the single choke point through which every ``KpiMatrix`` is
created (instance compute, PDF/XLSX reports, drilldown), so it applies
to all report instances, existing and future.
"""

from odoo import models


class MisReport(models.AbstractModel):
    _inherit = "mis.report"

    def prepare_kpi_matrix(self, companies=None):
        self.ensure_one()
        return super(
            MisReport, self.with_context(active_test=False)
        ).prepare_kpi_matrix(companies)
