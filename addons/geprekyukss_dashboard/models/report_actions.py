# -*- coding: utf-8 -*-
"""
geprekyukss.dashboard.report.actions — Thin wrapper OCA untuk report shell.

Prinsip (roadmap §C / keputusan Q1 kanonik):
- PINJAM, bukan tulis ulang: wizard AFR (TransientModel) + mis.report.instance
  di-instantiate dengan parameter minimal, lalu method resmi dipanggil:
  * Preview : AFR _get_report_values() (report model resmi, compute penuh)
              MIS compute() (KpiMatrix.as_dict() — payload resmi matrix)
  * PDF/XLSX: button_export_pdf/xlsx (AFR) — print_pdf/export_xls (MIS)
- READ-ONLY terhadap data akuntansi; satu-satunya penulisan adalah record
  wizard TransientModel (auto-vacuum Odoo) — TIDAK di-unlink segera karena
  QWeb/xlsx renderer AFR membaca wizard by wizard_id saat render.
- Preview meniru jalur UI: data wizard di-serialisasi JSON-safe (tanggal →
  string) sebelum masuk report model — sama dengan round-trip RPC asli.

Filter shell (Q3 keputusan): date range + outlet. Outlet dipetakan ke
journal wizard (pos.config.journal_id) — mapping terdekat yang tersedia
(wizard AFR tidak punya konsep pos.config). [] = tanpa filter.
"""
import datetime
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


def _jdump(obj):
    """Serialisasi JSON-safe (meniru round-trip RPC): date → iso string."""
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, tuple):
        return [_jdump(x) for x in obj]
    if isinstance(obj, list):
        return [_jdump(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _jdump(v) for k, v in obj.items()}
    return obj


class GkDashboardReportActions(models.AbstractModel):
    _name = "geprekyukss.dashboard.report.actions"
    _description = "Penghubung Report Shell ↔ Engine OCA (AFR + MIS Builder)"

    # ------------------------------------------------------------------
    # REGISTRY ENGINE (Python side — mirror dari reports_registry.js)
    # ------------------------------------------------------------------
    AFR_REPORTS = {
        "trial_balance": "trial.balance.report.wizard",
        "general_ledger": "general.ledger.report.wizard",
        "aged_partner": "aged.partner.balance.report.wizard",
        "vat": "vat.report.wizard",
        "open_items": "open.items.report.wizard",
        "journal_ledger": "journal.ledger.report.wizard",
    }
    MIS_REPORTS = {
        # xmlid instance: cash flow bawaan modul (F1); P&L & Neraca template
        # sendiri (F5a/F5b)
        "cash_flow_mis": "mis_builder_cash_flow.mis_instance_cash_flow",
        "profit_loss_mis": "geprekyukss_dashboard.mis_instance_pl",
        "balance_sheet_mis": "geprekyukss_dashboard.mis_instance_bs",
    }
    # Nama report QWeb (PDF/HTML) AFR — sumber _get_report_values().
    # Slug TIDAK seragam (aged_partner_balance, vat_report) — dipetakan
    # eksplisit, sama persis dengan report_name di tiap wizard _print_report.
    AFR_PDF_REPORT_NAME = {
        "trial_balance": "account_financial_report.trial_balance",
        "general_ledger": "account_financial_report.general_ledger",
        "aged_partner": "account_financial_report.aged_partner_balance",
        "vat": "account_financial_report.vat_report",
        "open_items": "account_financial_report.open_items",
        "journal_ledger": "account_financial_report.journal_ledger",
    }
    # Nama field Many2many journal BERBEDA antar wizard AFR — yang tidak
    # punya field journal (aged/open/vat) tidak menerima filter outlet.
    JOURNAL_FIELD = {
        "trial_balance": "journal_ids",
        "general_ledger": "account_journal_ids",
        "journal_ledger": "journal_ids",
    }

    # ------------------------------------------------------------------
    # PUBLIC API — dipanggil dari OWL via orm.call
    # ------------------------------------------------------------------
    @api.model
    def get_report_data(self, report_key, params):
        """Preview: dict siap-render untuk <ReportTable>/<ReportMatrix>.

        params: {date_from, date_to, outlet_ids: []|None}
        AFR  → {kind: "table", columns, rows, meta}
        MIS  → payload asli compute() + kind "matrix" (shape stabil, dijaga OCA).
        """
        params = dict(params or {})
        if report_key in self.AFR_REPORTS:
            table = self._afr_preview(report_key, params)
            table["kind"] = "table"
            return table
        if report_key in self.MIS_REPORTS:
            data = self._mis_preview(report_key, params)
            data["kind"] = "matrix"
            return data
        raise ValueError("Laporan tidak dikenal: %s" % report_key)

    @api.model
    def get_report_export_action(self, report_key, params, fmt):
        """PDF/XLSX: action dict resmi → client doAction() membuka report viewer.

        Action AFR hanya melewati wizard_id — record wizard HARUS masih
        hidup saat renderer membacanya (transient vacuum default cukup;
        TIDAK ada unlink manual di sini).
        """
        params = dict(params or {})
        if report_key in self.AFR_REPORTS:
            return self._afr_export(report_key, params, fmt)
        if report_key in self.MIS_REPORTS:
            return self._mis_export(report_key, params, fmt)
        raise ValueError("Laporan tidak dikenal: %s" % report_key)

    # ------------------------------------------------------------------
    # AFR — preview via report model resmi (satu sumber compute)
    # ------------------------------------------------------------------
    def _afr_preview(self, report_key, params):
        wizard = self._create_afr_wizard(report_key, params)
        data = _jdump(wizard._prepare_report_data())
        report_name = self.AFR_PDF_REPORT_NAME[report_key]
        # Model report Odoo: 'report.<report_name>' (AbstractReport AFR dengan
        # _get_report_values). ir.actions.report-nya sendiri menunjuk model
        # WIZARD (sebagai sumber docids) — bukan tempat compute.
        report_model_name = "report.%s" % report_name
        if report_model_name not in self.env:
            raise ValueError("Report model tidak ditemukan: %s" % report_model_name)
        Model = self.env[report_model_name]
        if not hasattr(Model, "_get_report_values"):
            raise ValueError(
                "Report model tidak punya _get_report_values: %s" % report_model_name
            )
        values = Model.with_context(
            active_ids=wizard.ids, active_model=wizard._name
        )._get_report_values(wizard.ids, data)
        adapter = getattr(self, "_adapt_%s" % report_key, None)
        if not adapter:
            raise ValueError("Adapter preview belum tersedia untuk: %s" % report_key)
        return adapter(wizard, values)

    def _afr_export(self, report_key, params, fmt):
        wizard = self._create_afr_wizard(report_key, params)
        if fmt == "xlsx":
            action = wizard.button_export_xlsx()
        else:
            action = wizard.button_export_pdf()
        action["name"] = action.get("name") or self._report_label(report_key)
        return action

    # ------------------------------------------------------------------
    # AFR — wizard factory (field minimal + default resmi)
    # ------------------------------------------------------------------
    def _create_afr_wizard(self, report_key, params):
        vals = self._afr_common_vals(report_key, params)
        model_name = self.AFR_REPORTS[report_key]
        builder = getattr(self, "_vals_%s" % report_key, lambda vals, params: vals)
        vals = builder(vals, params)
        # Filter outlet → journals (hanya wizard yang punya field journal)
        journal_field = self.JOURNAL_FIELD.get(report_key)
        journal_ids = journal_field and self._outlet_journal_ids(params)
        if journal_field and journal_ids:
            vals[journal_field] = [(6, 0, journal_ids)]
        wizard = self.env[model_name].create(vals)
        wizard._set_default_wizard_values()
        return wizard

    def _afr_common_vals(self, report_key, params):
        date_from = params.get("date_from")
        date_to = params.get("date_to")
        if not date_from or not date_to:
            raise ValueError("date_from & date_to wajib diisi")
        vals = {"company_id": self.env.company.id}
        Fields = self.env[self.AFR_REPORTS[report_key]]._fields
        # Field opsional hanya dikirim bila wizard memang memilikinya:
        # - foreign_currency: tidak ada di aged_partner & vat
        # - target_move: tidak ada di journal_ledger (pakai move_target)
        if "foreign_currency" in Fields:
            vals["foreign_currency"] = False  # R5: single-currency IDR
        if "target_move" in Fields:
            vals["target_move"] = "posted"
        return vals

    def _outlet_journal_ids(self, params):
        """Map outlet (pos.config ids) → journal id terkait (mapping terdekat)."""
        outlet_ids = [int(x) for x in (params.get("outlet_ids") or []) if x]
        if not outlet_ids:
            return []
        configs = self.env["pos.config"].browse(outlet_ids).exists()
        if not configs or "journal_id" not in self.env["pos.config"]._fields:
            return []
        return configs.mapped("journal_id").ids

    def _report_label(self, report_key):
        return {
            "trial_balance": "Trial Balance",
            "general_ledger": "General Ledger",
            "aged_partner": "Aged Partner Balance",
            "vat": "VAT Report",
            "open_items": "Open Items",
            "journal_ledger": "Journal Ledger",
            "cash_flow_mis": "Cash Flow",
        }.get(report_key, report_key)

    # ------------------------------------------------------------------
    # AFR — per-report vals
    # ------------------------------------------------------------------
    def _vals_trial_balance(self, vals, params):
        vals.update({
            "date_from": params["date_from"],
            "date_to": params["date_to"],
            "show_hierarchy": False,
            "hide_account_at_0": True,
            "show_partner_details": False,
        })
        return vals

    def _vals_general_ledger(self, vals, params):
        vals.update({
            "date_from": params["date_from"],
            "date_to": params["date_to"],
            "centralize": False,
            # False: GL dgn True menyembunyikan akun ber-saldo-akhir-0 MESKI
            # ada mutasi (wash/clearing) → total debit/credit GL tidak lagi
            # cocok dgn TB. False menjaga invariant antar-laporan.
            "hide_account_at_0": False,
            # "none": dgn "partners" + filter partner kosong, AFR menaruh
            # baris jurnal di acc['partners'] yang tak ter-serialize → baris
            # hilang dari preview. "none" = semua ml di acc['move_lines'].
            "grouped_by": "none",
            "show_cost_center": True,
        })
        return vals

    def _vals_vat(self, vals, params):
        vals.update({
            "date_from": params["date_from"],
            "date_to": params["date_to"],
            "based_on": "taxtags",
            "tax_detail": False,
        })
        return vals

    def _vals_journal_ledger(self, vals, params):
        vals.update({
            "date_from": params["date_from"],
            "date_to": params["date_to"],
            "move_target": "posted",
            "sort_option": "move_name",
            "group_option": "journal",
            "with_account_name": True,
        })
        return vals

    def _reconcilable_account_ids(self):
        Account = self.env["account.account"]
        accs = Account.search([("reconcile", "=", True)])
        receivable = Account.search([("account_type", "=", "asset_receivable")])
        payable = Account.search([("account_type", "=", "liability_payable")])
        return (accs | receivable | payable).ids

    def _vals_aged_partner(self, vals, params):
        # FIX 15 Sep: JANGAN kirim date_from. Di engine AFR (abstract_report
        # _get_move_lines_domain_not_reconciled) date_from itu filter OPSIONAL
        # "date > date_from" — laporan umur ini snapshot AS-OF date_at, jadi
        # membatasi ke awal periode dashboard membuang invoice open yang
        # tanggalnya sebelum periode (dataset mulai 19 Jun) → Agustus = 0 baris
        # & total tak pernah cocok dgn anchor F2. date_at = date_to sudah cukup.
        vals.update({
            "date_at": params["date_to"],
            "account_ids": [(6, 0, self._reconcilable_account_ids())],
            "show_move_line_details": False,
        })
        return vals

    def _vals_open_items(self, vals, params):
        # FIX 15 Sep: idem aged_partner — open items = snapshot AS-OF date_at;
        # date_from opsional di engine AFR hanya membuang invoice open yang
        # lebih tua dari awal periode dashboard. Tidak dikirim.
        vals.update({
            "date_at": params["date_to"],
            "account_ids": [(6, 0, self._reconcilable_account_ids())],
            "hide_account_at_0": True,
            "show_partner_details": True,
            "grouped_by": "partners",
        })
        return vals

    # ------------------------------------------------------------------
    # Helper adapter
    # ------------------------------------------------------------------
    def _f(self, record, key, default=""):
        v = record.get(key) if isinstance(record, dict) else getattr(record, key, None)
        return v if v not in (None, False) else default

    def _date_s(self, v):
        """date/datetime → iso string (aman JSON); lainnya dilewati."""
        if isinstance(v, (datetime.date, datetime.datetime)):
            return v.isoformat()
        return v or ""

    @staticmethod
    def _buckets_from(row, keys):
        out = {}
        for k in keys:
            v = row.get(k) or 0.0
            out[k] = float(v)
        return out

    def _afr_meta(self, values):
        return {
            "company_name": values.get("company_name") or "",
            "currency_name": values.get("currency_name") or "IDR",
            "date_from": self._date_s(values.get("date_from")),
            "date_to": self._date_s(values.get("date_to")),
        }

    @staticmethod
    def _totals_meta(totals):
        """meta["totals"] = [{label, debit, credit}] — footer table + test.
        Nilai di-round 2 desimal di sini agar footer == Σ baris (float noise
        di-sum client-side bisa selisih <0,01)."""
        return [
            {
                "label": lbl,
                "debit": round(float(t.get("debit") or 0.0), 2),
                "credit": round(float(t.get("credit") or 0.0), 2),
            }
            for lbl, t in totals
        ]

    # ------------------------------------------------------------------
    # AFR — adapter hasil _get_report_values → shape <ReportTable>
    # (shape diverifikasi langsung dari report model Test1, 12 Sep 2026)
    # ------------------------------------------------------------------
    def _adapt_trial_balance(self, wizard, values):
        columns = [
            {"key": "code", "label": "Kode", "align": "left", "sortable": True, "searchable": True},
            {"key": "name", "label": "Akun", "align": "left", "sortable": True, "searchable": True},
            {"key": "debit", "label": "Debit", "align": "right", "format": "currency", "sortable": True},
            {"key": "credit", "label": "Kredit", "align": "right", "format": "currency", "sortable": True},
            {"key": "balance", "label": "Saldo", "align": "right", "format": "currency", "sortable": True},
        ]
        rows = []
        for r in values.get("trial_balance") or []:
            rows.append({
                "code": self._f(r, "code"),
                "name": self._f(r, "name"),
                "debit": self._f(r, "debit", 0.0),
                "credit": self._f(r, "credit", 0.0),
                "balance": self._f(r, "ending_balance", 0.0),
            })
        return {"columns": columns, "rows": rows, "meta": self._afr_meta(values)}

    def _adapt_general_ledger(self, wizard, values):
        """values['general_ledger'] = list akun → move_lines per akun.

        F3 enhancement: init-balance row per akun ("Saldo Awal" — running
        balance GL membutuhkannya), footer totals (fin_bal), style row
        awal/akhir, dan meta.totals untuk test + UI.
        """
        journals = values.get("journals_data") or {}
        columns = [
            {"key": "date", "label": "Tanggal", "align": "left", "sortable": True},
            {"key": "entry", "label": "Entry", "align": "left", "sortable": True, "searchable": True},
            {"key": "code", "label": "Kode", "align": "left", "sortable": True, "searchable": True},
            {"key": "account", "label": "Akun", "align": "left", "sortable": True, "searchable": True},
            {"key": "journal", "label": "Journal", "align": "left", "sortable": True, "searchable": True},
            {"key": "partner", "label": "Partner", "align": "left", "sortable": True, "searchable": True},
            {"key": "label", "label": "Keterangan", "align": "left", "searchable": True},
            {"key": "debit", "label": "Debit", "align": "right", "format": "currency", "sortable": True},
            {"key": "credit", "label": "Kredit", "align": "right", "format": "currency", "sortable": True},
            {"key": "balance", "label": "Saldo", "align": "right", "format": "currency", "sortable": True},
        ]
        rows = []
        totals_d = totals_c = 0.0
        for acc in values.get("general_ledger") or []:
            acc_code = self._f(acc, "code")
            acc_name = self._f(acc, "name") or self._f(acc, "mame")
            init_bal = acc.get("init_bal") or {}
            fin_bal = acc.get("fin_bal") or {}
            mls = acc.get("move_lines") or []
            if init_bal or mls:
                rows.append({
                    "date": "",
                    "entry": "",
                    "code": acc_code,
                    "account": acc_name,
                    "journal": "",
                    "partner": "",
                    "label": "Saldo Awal",
                    "debit": 0.0,
                    "credit": 0.0,
                    "balance": float(init_bal.get("balance") or 0.0),
                    "style": "muted",
                })
            for ml in mls:
                jid = ml.get("journal_id")
                jid = jid[0] if isinstance(jid, (list, tuple)) else jid
                rows.append({
                    "date": self._date_s(ml.get("date")),
                    "entry": self._f(ml, "entry"),
                    "code": acc_code,
                    "account": acc_name,
                    "journal": self._f(journals.get(jid) or {}, "code"),
                    "partner": self._f(ml, "partner_name", "-"),
                    "label": self._f(ml, "ref_label") or self._f(ml, "ref") or self._f(ml, "name"),
                    "debit": self._f(ml, "debit", 0.0),
                    "credit": self._f(ml, "credit", 0.0),
                    "balance": self._f(ml, "balance", 0.0),
                })
            if fin_bal:
                rows.append({
                    "date": "",
                    "entry": "",
                    "code": acc_code,
                    "account": acc_name,
                    "journal": "",
                    "partner": "",
                    "label": "Saldo Akhir",
                    "debit": 0.0,
                    "credit": 0.0,
                    "balance": float(fin_bal.get("balance") or 0.0),
                    "style": "total",
                    "_total": {"debit": fin_bal.get("debit"), "credit": fin_bal.get("credit")},
                })
                totals_d += float(fin_bal.get("debit") or 0.0)
                totals_c += float(fin_bal.get("credit") or 0.0)
        meta = self._afr_meta(values)
        meta["totals"] = self._totals_meta(
            [("Buku Besar", {"debit": totals_d, "credit": totals_c})]
        )
        return {"columns": columns, "rows": rows, "meta": meta}

    def _adapt_vat(self, wizard, values):
        """Shape tergantung based_on: list 'vat_report' (taxtags/taxgroups)
        atau dict 'taxlines' — keduanya ditangani.

        F3 enhancement: baris detail pajak (tax_detail) → baris sub "— <tax>",
        meta.totals = Σ net/tax engine (footer + test).
        """
        columns = [
            {"key": "code", "label": "Kode", "align": "left", "sortable": True, "searchable": True},
            {"key": "name", "label": "Pajak", "align": "left", "sortable": True, "searchable": True},
            {"key": "net", "label": "DPP", "align": "right", "format": "currency", "sortable": True},
            {"key": "tax", "label": "Pajak", "align": "right", "format": "currency", "sortable": True},
        ]
        rows = []
        tot_net = tot_tax = 0.0
        list_rows = values.get("vat_report") or []
        if list_rows:
            for r in list_rows:
                r_net = float(self._f(r, "net", self._f(r, "base", 0.0)) or 0.0)
                r_tax = float(self._f(r, "tax", self._f(r, "amount", 0.0)) or 0.0)
                rows.append({
                    "code": self._f(r, "code"),
                    "name": self._f(r, "name"),
                    "net": r_net,
                    "tax": r_tax,
                })
                tot_net += r_net
                tot_tax += r_tax
                for t in r.get("taxes") or []:
                    if not isinstance(t, dict):
                        continue
                    t_net = float(self._f(t, "net", 0.0) or 0.0)
                    t_tax = float(self._f(t, "tax", 0.0) or 0.0)
                    rows.append({
                        "code": self._f(t, "code"),
                        "name": "— %s" % self._f(t, "name", "(pajak)"),
                        "net": t_net,
                        "tax": t_tax,
                        "style": "muted",
                    })
        else:
            for tag, entry in (values.get("taxlines") or {}).items():
                if not isinstance(entry, dict):
                    continue
                e_net = float(self._f(entry, "net", 0.0) or 0.0)
                e_tax = float(self._f(entry, "tax", 0.0) or 0.0)
                rows.append({
                    "code": self._f(entry, "code"),
                    "name": self._f(entry, "name") or str(tag),
                    "net": e_net,
                    "tax": e_tax,
                })
                tot_net += e_net
                tot_tax += e_tax
        meta = self._afr_meta(values)
        meta["totals"] = self._totals_meta([("PPN", {"debit": tot_net, "credit": tot_tax})])
        return {"columns": columns, "rows": rows, "meta": meta}

    def _adapt_aged_partner(self, wizard, values):
        """values['aged_partner_balance'] = list akun; bucket per akun +
        detail partner di row['partners'] (subtotal akun = engine AFR).

        F6 enhancement (pola final §20.4):
        - kolom by ENGINE bucket key (current/30_days/.../older) — bukan
          derivasi label (sebelumnya `b_<label>` pecah jika label berubah);
        - baris partner = sub-row style muted + prefix "— ";
        - meta.totals per bucket (footer + test), shape values (dipakai
          ReportTable footer generik).
        """
        buckets = [
            ("current", "Belum jatuh tempo"),
            ("30_days", "1–30 hari"),
            ("60_days", "31–60 hari"),
            ("90_days", "61–90 hari"),
            ("120_days", "91–120 hari"),
            ("older", "> 120 hari"),
        ]
        columns = [{"key": "partner", "label": "Akun / Partner", "align": "left",
                    "sortable": True, "searchable": True}]
        for key, label in buckets:
            columns.append({"key": "b_%s" % key, "label": label, "align": "right",
                            "format": "currency", "sortable": True})
        columns.append({"key": "total", "label": "Total", "align": "right",
                        "format": "currency", "sortable": True})

        bucket_keys = [k for k, _ in buckets]

        def _mkrow(name, vals_by_key, total, code="", is_partner=False):
            row = {"partner": name, "code": code, "is_partner": is_partner,
                   "total": round(float(total or 0.0), 2)}
            for k in bucket_keys:
                row["b_%s" % k] = round(float(vals_by_key.get(k) or 0.0), 2)
            return row

        rows = []
        tot_by_key = {k: 0.0 for k in bucket_keys}
        tot_total = 0.0
        for acc in values.get("aged_partner_balance") or []:
            acc_vals = self._buckets_from(acc, bucket_keys)
            rows.append(_mkrow(self._f(acc, "name"), acc_vals,
                               self._f(acc, "residual", 0.0),
                               code=self._f(acc, "code")))
            for k in bucket_keys:
                tot_by_key[k] += float(acc_vals.get(k) or 0.0)
            tot_total += float(self._f(acc, "residual", 0.0) or 0.0)
            for p in acc.get("partners") or []:
                prow = _mkrow("— " + str(self._f(p, "name")),
                              self._buckets_from(p, bucket_keys),
                              self._f(p, "residual", 0.0),
                              code=self._f(acc, "code"), is_partner=True)
                prow["style"] = "muted"
                rows.append(prow)
        meta = self._afr_meta(values)
        meta["totals"] = [{
            "label": "Total",
            "columns": ["b_%s" % k for k in bucket_keys] + ["total"],
            "values": dict(
                [("b_%s" % k, round(tot_by_key[k], 2)) for k in bucket_keys]
                + [("total", round(tot_total, 2))]
            ),
        }]
        return {"columns": columns, "rows": rows, "meta": meta}

    def _adapt_open_items(self, wizard, values):
        """values['Open_Items'] = {acc_id: {partner_id: [move_line, ...]}};
        meta akun dari accounts_data, partner dari partner_ids_data/line."""
        acc_data = values.get("accounts_data") or {}
        columns = [
            {"key": "code", "label": "Kode", "align": "left", "sortable": True, "searchable": True},
            {"key": "account", "label": "Akun", "align": "left", "sortable": True, "searchable": True},
            {"key": "partner", "label": "Partner", "align": "left", "sortable": True, "searchable": True},
            {"key": "date", "label": "Tanggal", "align": "left", "sortable": True},
            {"key": "due", "label": "Jatuh Tempo", "align": "left", "sortable": True},
            {"key": "entry", "label": "Entry", "align": "left", "sortable": True, "searchable": True},
            {"key": "label", "label": "Keterangan", "align": "left", "searchable": True},
            {"key": "original", "label": "Nilai", "align": "right", "format": "currency", "sortable": True},
            {"key": "open", "label": "Sisa", "align": "right", "format": "currency", "sortable": True},
        ]
        rows = []
        acc_ids_needed = set()
        for acc_id, partners in (values.get("Open_Items") or {}).items():
            arow = acc_data.get(acc_id) or {}
            acc_code = self._f(arow, "code")
            acc_name = self._f(arow, "name")
            if not isinstance(partners, dict):
                continue
            for lines in partners.values():
                if not isinstance(lines, list):
                    continue
                for line in lines:
                    if not isinstance(line, dict):
                        continue
                    residual = float(self._f(line, "amount_residual", 0.0) or 0.0)
                    if abs(residual) < 0.005:
                        continue  # sisa 0 tidak ditampilkan (hide_account_at_0)
                    acc_ids_needed.add(acc_id)
                    rows.append({
                        "code": acc_code,
                        "account": acc_name,
                        "partner": self._f(line, "partner_name", "-"),
                        "date": self._date_s(line.get("date")),
                        "due": self._date_s(line.get("date_maturity")),
                        "entry": self._f(line, "move_name"),
                        "label": self._f(line, "ref_label") or self._f(line, "name"),
                        "original": float(self._f(line, "original", 0.0) or 0.0),
                        "open": residual,
                        # F-UI.4: metadata presentasional (BAPAK compute OCA) —
                        # diisi di bawah via batch lookup account_type.
                        "_acc_id": acc_id,
                    })
        # kind ap|ar|other — sumber kebenaran = account_type akun (bukan kode
        # akun). Batch browse sekali; angka laporan TIDAK berubah (regression
        # F3/F6 tetap jadi pagar).
        acc_types = {}
        if acc_ids_needed:
            acc_recs = self.env["account.account"].with_context(
                active_test=False
            ).browse(list(acc_ids_needed))
            acc_types = {a.id: a.account_type for a in acc_recs}
        for r in rows:
            at = acc_types.get(r.pop("_acc_id"), "")
            r["kind"] = (
                "ap" if at == "liability_payable"
                else "ar" if at == "asset_receivable"
                else "other"
            )
        return {"columns": columns, "rows": rows, "meta": self._afr_meta(values)}

    def _adapt_journal_ledger(self, wizard, values):
        """values['Journal_Ledgers'] = list journal → report_moves →
        report_move_lines; lookup akun/partner via *_ids_data."""
        acc_data = values.get("account_ids_data") or {}
        part_data = values.get("partner_ids_data") or {}
        columns = [
            {"key": "date", "label": "Tanggal", "align": "left", "sortable": True},
            {"key": "entry", "label": "Entry", "align": "left", "sortable": True, "searchable": True},
            {"key": "journal", "label": "Journal", "align": "left", "sortable": True, "searchable": True},
            {"key": "account", "label": "Akun", "align": "left", "sortable": True, "searchable": True},
            {"key": "partner", "label": "Partner", "align": "left", "searchable": True},
            {"key": "label", "label": "Keterangan", "align": "left", "searchable": True},
            {"key": "debit", "label": "Debit", "align": "right", "format": "currency", "sortable": True},
            {"key": "credit", "label": "Kredit", "align": "right", "format": "currency", "sortable": True},
        ]
        rows = []
        for jrn in values.get("Journal_Ledgers") or []:
            jname = self._f(jrn, "name")
            for move in jrn.get("report_moves") or []:
                for ml in move.get("report_move_lines") or []:
                    aid = ml.get("account_id")
                    pid = ml.get("partner_id")
                    aid = aid[0] if isinstance(aid, (list, tuple)) else aid
                    pid = pid[0] if isinstance(pid, (list, tuple)) else pid
                    arow = acc_data.get(aid) or {}
                    prow = part_data.get(pid) or {}
                    rows.append({
                        "date": self._date_s(ml.get("date")),
                        "entry": self._f(ml, "entry") or self._f(move, "entry"),
                        "journal": jname,
                        "account": (self._f(arow, "code", "") +
                                    (" " + arow["name"] if arow.get("name") else "")) or "-",
                        "partner": self._f(prow, "name", "-"),
                        "label": self._f(ml, "ref_label") or self._f(ml, "label") or self._f(ml, "name"),
                        "debit": self._f(ml, "debit", 0.0),
                        "credit": self._f(ml, "credit", 0.0),
                    })
        return {"columns": columns, "rows": rows, "meta": self._afr_meta(values)}

    # ------------------------------------------------------------------
    # MIS Builder — preview compute() resmi + set periode dari filter shell
    # ------------------------------------------------------------------
    def _mis_preview(self, report_key, params):
        instance = self._get_mis_instance(report_key)
        self._apply_mis_period(instance, params)
        payload = instance.compute()  # method resmi: KpiMatrix.as_dict() + notes
        payload["title"] = instance.name
        payload["meta"] = {
            "company_name": self.env.company.display_name,
            "currency_name": instance.currency_id.name or "IDR",
        }
        return payload

    def _mis_export(self, report_key, params, fmt):
        instance = self._get_mis_instance(report_key)
        self._apply_mis_period(instance, params)
        if fmt == "xlsx":
            return instance.export_xls()
        return instance.print_pdf()

    def _get_mis_instance(self, report_key):
        xmlid = self.MIS_REPORTS[report_key]
        instance = self.env.ref(xmlid, raise_if_not_found=False)
        if not instance:
            raise ValueError(
                "mis.report.instance belum ada (%s). Selesaikan setup template MIS dulu." % xmlid
            )
        return instance

    def _apply_mis_period(self, instance, params):
        """Sinkron kolom periode dengan filter shell.

        Dua pola instance:
        - cash_flow_mis (bawaan modul): kolom pertama relatif minggu —
          override kolom pertama jadi fixed bulan shell; kolom forecast
          relatif lainnya dibiarkan (behavior resmi instance).
        - profit_loss_mis (F5a): 2 kolom fix "Bulan Ini" + "YTD" (Q4) —
          keduanya di-set dari filter shell: Bulan = date range filter;
          YTD = 1 Jan tahun date_to s.d. date_to.
        - balance_sheet_mis (F5b): 2 kolom fix ber-window tahun fiskal
          (window FY penting: balp kolom = NI YTD, selaras _net_income
          Tab 2) — kolom 1 per akhir bulan filter, kolom 2 per akhir bulan
          lalu (neraca = posisi per tanggal; 2 kolom "bulan+YTD" akan
          identik). Keduanya self-balancing.
        """
        date_from = params.get("date_from")
        date_to = params.get("date_to")
        if not date_from or not date_to:
            return
        if instance == self.env.ref(
            "mis_builder_cash_flow.mis_instance_cash_flow", raise_if_not_found=False
        ):
            first = instance.period_ids[:1]
            if not first:
                return
            first.write({
                "mode": "fix",  # MODE_FIX (bukan 'fixed')
                "manual_date_from": date_from,
                "manual_date_to": date_to,
            })
            return
        periods = instance.period_ids.sorted("sequence")
        if not periods:
            return
        if instance == self.env.ref(
            "geprekyukss_dashboard.mis_instance_bs", raise_if_not_found=False
        ):
            # Neraca (F5b): kedua kolom ber-window FY (1 Jan → akhir bulan).
            ytd_from = "%s-01-01" % date_to[:4]
            prev_to = (
                datetime.date.fromisoformat(date_from) - datetime.timedelta(days=1)
            ).isoformat()
            periods[:1].write({
                "mode": "fix",
                "manual_date_from": ytd_from,
                "manual_date_to": date_to,
            })
            periods[1:2].write({
                "mode": "fix",
                "manual_date_from": ytd_from,
                "manual_date_to": prev_to,
            })
            return
        # P&L (F5a): kolom 1 = bulan filter, kolom 2 = YTD sampai date_to
        month_col = periods[:1]
        ytd_col = periods[1:2]
        if month_col:
            month_col.write({
                "mode": "fix",
                "manual_date_from": date_from,
                "manual_date_to": date_to,
            })
        if ytd_col:
            ytd_col.write({
                "mode": "fix",
                "manual_date_from": "%s-01-01" % date_to[:4],
                "manual_date_to": date_to,
            })
