/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * <ReportMatrix> — renderer matrix untuk laporan MIS Builder (F1, §B.4).
 *
 * Props:
 *   payload : hasil MIS mis.report.instance.compute() — shape resmi OCA
 *             (KpiMatrix.as_dict()):
 *     header : [{cols: [{label, description, colspan}]}, {cols: [...]}]
 *     body   : [{label, description, style, cells: [{cell_id, val, val_r,
 *              val_c, style, can_be_annotated, drilldown_arg?}]}]
 *     notes  : {cell_id: {text, sequence}}
 *
 * Prinsip "pinjam, bukan tulis ulang": nilai ditampilkan apa adanya dari
 * `val_r` (val_rendered — sudah terformat oleh engine MIS). Style row/cell
 * (string CSS dari engine) dirender via binding; token visual PowerBI tetap
 * dipegang SCSS (border, font, warna dasar). Sel kosong = "—" agar grid rapi.
 */
import { formatRp } from "../dashboard/dashboard.js";

export class ReportMatrix extends Component {
    static template = "geprekyukss_dashboard.ReportMatrix";
    static props = {
        payload: { type: Object },
    };

    setup() {
        this.formatRp = formatRp;
    }

    cellText(cell) {
        if (!cell) return "—";
        if (cell.val_r !== undefined && cell.val_r !== null && cell.val_r !== "") {
            return String(cell.val_r);
        }
        const v = cell.val;
        if (v === null || v === undefined || v === "") return "—";
        return typeof v === "number" ? this.formatRp(v) : String(v);
    }

    cellClass(cell) {
        if (!cell) return "";
        let cls = "";
        const v = cell.val;
        if (typeof v === "number" && v < 0) cls += " gk-neg";
        return cls;
    }

    cellStyle(cell) {
        // style CSS per-sel dari engine MIS (indent dsb) — tanpa warna liar
        return (cell && cell.style) || "";
    }

    rowStyle(row) {
        // style CSS per-baris dari engine MIS (bold/underline dsb)
        return row.style || "";
    }
}
