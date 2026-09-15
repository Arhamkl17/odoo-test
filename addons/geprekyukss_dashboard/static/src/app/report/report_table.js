/** @odoo-module **/

import { Component, useState } from "@odoo/owl";

/**
 * <ReportTable> — renderer tabel untuk laporan AFR (F1, roadmap §B.4).
 *
 * Props:
 *   columns : [{key, label, align: "left"|"right", format: "currency"|null,
 *               sortable, searchable}]
 *   rows    : [{<key>: value, ..., style?: "muted"|"total"}]
 *   meta    : optional {totals?: [{label, debit, credit}], ...}
 *
 * Fitur bawaan (roadmap §B.4): search substring (kolom searchable),
 * sort klik header (kolom sortable), paging klien (50 baris/halaman).
 * Tidak fetch sendiri — data dari parent (ReportShell).
 *
 * F3 (GL & VAT):
 *  - baris `style: "muted"|"total"` dirender italic/tebal (Saldo Awal/Akhir,
 *    sub-detail pajak) — sorting/search tetap bekerja (baris ikut aliran).
 *  - footer totals dari meta.totals (Σ engine AFR, bukan sum client-side).
 *
 * Format angka: formatRp() diimpor dari dashboard.js (satu sumber,
 * sudah dipakai 4 tab existing).
 */
import { formatRp } from "../dashboard/dashboard.js";

const PAGE_SIZE = 50;

export class ReportTable extends Component {
    static template = "geprekyukss_dashboard.ReportTable";
    static props = {
        columns: { type: Array, element: Object },
        rows: { type: Array, element: Object },
        meta: { type: Object, optional: true },
    };

    setup() {
        this.state = useState({
            search: "",
            sortKey: null,
            sortDir: "asc",
            page: 0,
        });
        this.formatRp = formatRp;
    }

    // --------------------------------------------------------------
    // F7 — reskin tabel gaya FinanceFlow (foto 01 Riwayat Transaksi):
    // warna arah (debit merah / kredit hijau), chip sisi kolom D/K,
    // "–" utk sel nol. Murni presentasional — nilai & urutan tak berubah.
    // --------------------------------------------------------------
    /** Kelas warna utk sel currency: minus → merah, plus → hijau bila
     *  kolomnya kolom arah (debit/kredit/bucket), netral utk lainnya. */
    amountCls(col, value) {
        if (col.format !== "currency") return "";
        const v = Number(value) || 0;
        if (Math.abs(v) < 0.005) return " is-zero";
        const sideCols = new Set(["debit", "credit"]);
        if (sideCols.has(col.key)) {
            return col.key === "debit"
                ? (v < 0 ? " is-neg" : " is-debit")
                : (v < 0 ? " is-neg" : " is-credit");
        }
        return v < 0 ? " is-neg" : "";
    }

    /** Tampilkan "–" utk nol persis (gaya FinanceFlow), angka selain itu. */
    amountText(col, value) {
        if (col.format !== "currency") return value;
        const v = Number(value) || 0;
        return Math.abs(v) < 0.005 ? "–" : this.formatRp(value);
    }

    get filteredRows() {
        const q = this.state.search.trim().toLowerCase();
        let rows = this.props.rows;
        if (q) {
            const searchable = this.props.columns.filter((c) => c.searchable).map((c) => c.key);
            rows = rows.filter((row) =>
                searchable.some((k) => String(row[k] ?? "").toLowerCase().includes(q))
            );
        }
        if (this.state.sortKey) {
            const key = this.state.sortKey;
            const dir = this.state.sortDir === "asc" ? 1 : -1;
            const isNum = this.props.columns.some(
                (c) => c.key === key && c.format === "currency"
            );
            rows = [...rows].sort((a, b) => {
                const va = a[key], vb = b[key];
                if (isNum) {
                    return ((Number(va) || 0) - (Number(vb) || 0)) * dir;
                }
                return String(va ?? "").localeCompare(String(vb ?? ""), "id") * dir;
            });
        }
        return rows;
    }

    // Footer totals — dari meta (engine AFR), bukan sum client-side.
    // Dua shape (F3/F6):
    //   debit/credit : GL & VAT (2 angka per baris footer)
    //   columns/values : Aged Partner (total per bucket — kolom arbitrer)
    // Baris all-zero disembunyikan (bulan kosong → footer "0" tidak berguna).
    get totalRows() {
        const totals = (this.props.meta && this.props.meta.totals) || [];
        const isZero = (v) => !Number(v);
        return totals.filter((t) =>
            t.values
                ? Object.values(t.values).some((v) => !isZero(v))
                : !(isZero(t.debit) && isZero(t.credit))
        );
    }

    get hasTotals() {
        return this.totalRows.length > 0;
    }

    get pageCount() {
        return Math.max(1, Math.ceil(this.filteredRows.length / PAGE_SIZE));
    }

    get pageRows() {
        const start = this.state.page * PAGE_SIZE;
        return this.filteredRows.slice(start, start + PAGE_SIZE);
    }

    get rangeLabel() {
        const total = this.filteredRows.length;
        if (!total) return "0 baris";
        const start = this.state.page * PAGE_SIZE + 1;
        const end = Math.min(start + PAGE_SIZE - 1, total);
        return `${start}–${end} dari ${total} baris`;
    }

    onSearch(ev) {
        this.state.search = ev.target.value;
        this.state.page = 0;
    }

    onSort(key) {
        const col = this.props.columns.find((c) => c.key === key);
        if (!col || !col.sortable) return;
        if (this.state.sortKey === key) {
            this.state.sortDir = this.state.sortDir === "asc" ? "desc" : "asc";
        } else {
            this.state.sortKey = key;
            this.state.sortDir = "asc";
        }
    }

    prevPage() {
        if (this.state.page > 0) this.state.page -= 1;
    }

    nextPage() {
        if (this.state.page < this.pageCount - 1) this.state.page += 1;
    }

    sortIcon(key) {
        if (this.state.sortKey !== key) return "fa-sort";
        return this.state.sortDir === "asc" ? "fa-sort-asc" : "fa-sort-desc";
    }
}
