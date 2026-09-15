/** @odoo-module **/

import { Component, useState, useRef, useExternalListener, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";
import { REPORTS } from "../report/reports_registry.js";

const FONT_URL = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap";

function loadInterFont() {
    if (document.querySelector(`link[href="${FONT_URL}"]`)) return;
    const pre = document.createElement("link");
    pre.rel = "preconnect";
    pre.href = "https://fonts.googleapis.com";
    document.head.appendChild(pre);
    const pre2 = document.createElement("link");
    pre2.rel = "preconnect";
    pre2.href = "https://fonts.gstatic.com";
    pre2.crossOrigin = "";
    document.head.appendChild(pre2);
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = FONT_URL;
    document.head.appendChild(link);
}

// SPEC_OVERHAUL 15 Sep: 7 menu utama (Tab 1→4 + Beranda/HPP/Persediaan)
const TABS = [
    { id: "beranda", label: "Beranda", icon: "fa-home" },
    { id: "laporan", label: "Laporan", icon: "fa-file-text-o" },
    { id: "penjualan", label: "Penjualan", icon: "fa-shopping-cart" },
    { id: "hpp", label: "Biaya & HPP", icon: "fa-cutlery" },
    { id: "kas", label: "Kas & Bank", icon: "fa-university" },
    { id: "aset", label: "Aset", icon: "fa-building-o" },
    { id: "persediaan", label: "Persediaan", icon: "fa-cubes" },
];

const MONTHS = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
];
const MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
const MAX_RANGE_DAYS = 366;

const CHART_COLORS = ["#0F7C6C", "#E8A33D", "#3B6FE0", "#D64545", "#8B5CF6", "#64748B"];

// OVERHAUL 15 Sep: const GAUGE dihapus — gauge "Status Keuangan" tidak lagi dipakai (K1).

export function formatRp(v, compact = false) {
    if (v === null || v === undefined) return "—";
    const n = Number(v);
    if (compact) {
        if (Math.abs(n) >= 1e9) return `Rp ${(n / 1e9).toFixed(1).replace(".", ",")} M`;
        if (Math.abs(n) >= 1e6) return `Rp ${(n / 1e6).toFixed(1).replace(".", ",")} jt`;
        if (Math.abs(n) >= 1e3) return `Rp ${(n / 1e3).toFixed(0)} rb`;
    }
    return "Rp " + n.toLocaleString("id-ID", { maximumFractionDigits: 0 });
}

export class GkDashboard extends Component {
    static template = "geprekyukss_dashboard.Main";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            activeTab: "beranda",
            // SPEC_OVERHAUL F0: date range — default "month" pill, toggle to custom.
            // Default = Agustus 2026 (bulan data pertama — konsisten dgn data existing).
            rangeMode: "month",
            activeYear: 2026,
            activeMonth: 8,        // 8 = Agustus
            date_from: "2026-08-01",
            date_to: "2026-08-31",
            rangeError: "",
            activePreset: "",
            loading: false,
            data: null,
            charts: [],
            outletFilter: { id: "all", name: "Semua Outlet", ids: [] },
            availableOutlets: [{ id: "all", name: "Semua Outlet", ids: [] }],
            outletMenuOpen: false,
            lastUpdated: null,
        });
        this.tabs = TABS;
        this.months = MONTHS;
        this.reports = REPORTS;
        this.mainRef = useRef("main");
        this.outletWrapRef = useRef("outletWrap");
        this.formatRp = formatRp;
        onWillStart(() => loadInterFont());
        useExternalListener(window, "click", (ev) => {
            const wrap = this.outletWrapRef.el;
            if (wrap && !wrap.contains(ev.target)) {
                this.state.outletMenuOpen = false;
            }
        });
        this.loadAvailableOutlets();
        this.load();
    }

    // ---- header helpers ----
    get rangeLabel() {
        if (this.state.rangeError) return "Rentang tidak valid";
        if (!this.state.date_from || !this.state.date_to) return "Pilih rentang";
        return `${this.formatShort(this.state.date_from)} – ${this.formatShort(this.state.date_to)}`;
    }

    formatShort(iso) {
        const [y, m, d] = (iso || "").split("-").map(Number);
        if (!y || !m || !d) return iso || "…";
        return `${d} ${MONTHS_SHORT[m - 1]} ${y}`;
    }

    _monthPeriod(y, m) {
        const lastDay = new Date(y, m, 0).getDate();
        return {
            date_from: `${y}-${String(m).padStart(2, "0")}-01`,
            date_to: `${y}-${String(m).padStart(2, "0")}-${String(lastDay).padStart(2, "0")}`,
        };
    }

    get lastUpdatedLabel() {
        if (!this.state.lastUpdated) return "—";
        const d = this.state.lastUpdated;
        return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    }

    get period() {
        // SPEC_OVERHAUL F0: month mode → turun dari activeYear/Month; custom → apa adanya
        if (this.state.rangeMode === "custom") {
            return { date_from: this.state.date_from || "", date_to: this.state.date_to || "" };
        }
        return this._monthPeriod(this.state.activeYear, this.state.activeMonth);
    }

    get monthLabel() {
        // F0: label pill di mode month = "Agustus 2026"; di mode custom = range
        if (this.state.rangeMode === "custom") {
            return this.rangeLabel;
        }
        return `${this.months[this.state.activeMonth - 1]} ${this.state.activeYear}`;
    }

    async load() {
        if (this.state.rangeMode === "month") {
            // Sync date_from/date_to dgn bulan aktif (kalau ada perubahan via prev/next)
            const p = this._monthPeriod(this.state.activeYear, this.state.activeMonth);
            this.state.date_from = p.date_from;
            this.state.date_to = p.date_to;
        }
        if (!this.state.date_from || !this.state.date_to) return;
        if (this.state.rangeError) return;
        this.state.loading = true;
        this.destroyCharts();
        try {
            this.state.data = await this.orm.call(
                "geprekyukss.dashboard.data",
                "get_dashboard_data",
                [this.period.date_from, this.period.date_to, this.state.outletFilter.ids],
            );
            this.state.lastUpdated = new Date();
        } catch (e) {
            console.error("dashboard load failed", e);
            this.state.data = { has_data: false, summary: null, finance: null, sales: null, ops: null };
        } finally {
            this.state.loading = false;
        }
        setTimeout(() => this.renderCharts(), 50);
    }

    async loadAvailableOutlets() {
        try {
            const rows = await this.orm.call(
                "geprekyukss.dashboard.data",
                "list_available_outlets",
                [],
            );
            const all = { id: "all", name: "Semua Outlet", ids: [] };
            this.state.availableOutlets = [
                all,
                ...rows.map((r) => ({ id: r.id, name: r.name, ids: [r.id] })),
            ];
        } catch (e) {
            console.warn("list_available_outlets failed; pakai default", e);
        }
    }

    // ---- date range handlers (F0 foundation, referensi: 1 Jan – 31 Jan 2025 ▼) ----
    setRangeMode(mode) {
        if (this.state.rangeMode === mode) return;
        this.state.rangeError = "";
        if (mode === "custom") {
            // Prefill dari bulan aktif → user bisa geser manual
            const p = this._monthPeriod(this.state.activeYear, this.state.activeMonth);
            this.state.date_from = p.date_from;
            this.state.date_to = p.date_to;
            this.state.activePreset = "";
            this.state.rangeMode = "custom";
        } else {
            // kembali ke mode bulan: pastikan date_from/date_to sinkron dgn bulan
            const p = this._monthPeriod(this.state.activeYear, this.state.activeMonth);
            this.state.date_from = p.date_from;
            this.state.date_to = p.date_to;
            this.state.activePreset = "";
            this.state.rangeMode = "month";
        }
        this.load();
    }

    onCustomRangeChange() {
        // Triggered saat input date di mode custom berubah
        const f = this.state.date_from, t = this.state.date_to;
        this.state.activePreset = "";
        if (!f || !t) {
            this.state.rangeError = "";
            return;
        }
        if (f > t) {
            this.state.rangeError = "Tanggal awal melebihi tanggal akhir.";
            return;
        }
        const days = (new Date(t) - new Date(f)) / 86400000;
        if (days > MAX_RANGE_DAYS) {
            this.state.rangeError = "Rentang maksimal 1 tahun.";
            return;
        }
        this.state.rangeError = "";
        this.load();
    }

    applyPreset(key) {
        const today = new Date();
        const iso = (d) =>
            `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
        let f, t;
        if (key === "today") {
            f = today; t = today;
        } else if (key === "7d") {
            t = today; f = new Date(today); f.setDate(f.getDate() - 6);
        } else if (key === "30d") {
            t = today; f = new Date(today); f.setDate(f.getDate() - 29);
        } else if (key === "month_current") {
            f = new Date(today.getFullYear(), today.getMonth(), 1);
            t = new Date(today.getFullYear(), today.getMonth() + 1, 0);
        } else if (key === "month_prev") {
            f = new Date(today.getFullYear(), today.getMonth() - 1, 1);
            t = new Date(today.getFullYear(), today.getMonth(), 0);
        } else if (key === "ytd") {
            f = new Date(today.getFullYear(), 0, 1); t = today;
        }
        if (!f || !t) return;
        if (this.state.rangeMode === "month") {
            // preset → pindah ke mode custom dgn tanggal terisi
            this.state.date_from = iso(f);
            this.state.date_to = iso(t);
            this.state.activePreset = key;
            this.state.rangeMode = "custom";
            this.state.rangeError = "";
            this.load();
        } else {
            this.state.date_from = iso(f);
            this.state.date_to = iso(t);
            this.state.activePreset = key;
            this.state.rangeError = "";
            this.load();
        }
    }

    // month mode → prev/next nav (referensi: ‹ pill ›)
    prevMonth() {
        if (this.state.rangeMode === "custom") {
            this.setRangeMode("month");
            return;
        }
        let m = this.state.activeMonth - 1, y = this.state.activeYear;
        if (m < 1) { m = 12; y -= 1; }
        this.state.activeMonth = m; this.state.activeYear = y;
        this.load();
        this.scrollTop();
    }

    nextMonth() {
        if (this.state.rangeMode === "custom") {
            this.setRangeMode("month");
            return;
        }
        let m = this.state.activeMonth + 1, y = this.state.activeYear;
        if (m > 12) { m = 1; y += 1; }
        this.state.activeMonth = m; this.state.activeYear = y;
        this.load();
        this.scrollTop();
    }

    destroyCharts() {
        for (const c of this.state.charts) {
            try { c.destroy(); } catch (_) {}
        }
        this.state.charts = [];
    }

    CHART_COLOR(idx) { return CHART_COLORS[idx % CHART_COLORS.length]; }

    async renderCharts() {
        const d = this.state.data;
        if (!d || !d.has_data) return;
        await loadBundle("web.chartjs_lib");
        const Chart = window.Chart;
        if (!Chart) return;
        this.destroyCharts();
        if (this.state.activeTab === "beranda") {
            this.renderBerandaTren(Chart);
            this.renderBerandaKategori(Chart);
            this.renderBerandaMonthly(Chart);
        } else if (this.state.activeTab === "laporan" && d.summary) {
            this.renderLineDaily(Chart, d.summary.daily || []);
        } else if (this.state.activeTab === "penjualan" && d.sales) {
            this.renderDonutChannels(Chart, d.sales.channels || []);
        } else if (this.state.activeTab === "hpp" && d.finance) {
            if (d.summary) this.renderLineDaily(Chart, d.summary.daily || []);
        }
        this.renderKpiSparklines(Chart);
    }

    renderBerandaTren(Chart) {
        const el = document.querySelector(".gk-chart-beranda-tren canvas");
        if (!el) return;
        const tren = (this.state.data.beranda && this.state.data.beranda.tren) || [];
        if (!tren.length) return;
        const labels = tren.map((x) => x.date.slice(8));
        const pendapatan = tren.map((x) => x.pendapatan);
        const laba = tren.map((x) => x.laba);
        const ctx = el.getContext("2d");
        const h = (el.parentElement && el.parentElement.clientHeight) || 260;
        const gTeal = ctx.createLinearGradient(0, 0, 0, h);
        gTeal.addColorStop(0, "rgba(15,124,108,0.18)");
        gTeal.addColorStop(1, "rgba(15,124,108,0)");
        const gBlue = ctx.createLinearGradient(0, 0, 0, h);
        gBlue.addColorStop(0, "rgba(59,111,224,0.16)");
        gBlue.addColorStop(1, "rgba(59,111,224,0)");
        this.state.charts.push(new Chart(el, {
            type: "line",
            data: {
                labels,
                datasets: [
                    { label: "Pendapatan", data: pendapatan, borderColor: "#0F7C6C", backgroundColor: gTeal, fill: true, tension: 0.35, pointRadius: 0, pointHoverRadius: 3, borderWidth: 2 },
                    { label: "Laba", data: laba, borderColor: "#3B6FE0", backgroundColor: gBlue, fill: true, tension: 0.35, pointRadius: 0, pointHoverRadius: 3, borderWidth: 2 },
                ],
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${formatRp(c.parsed.y, true)}` } } },
                scales: {
                    y: { grid: { color: "#E4E7EC", drawTicks: false }, border: { display: false }, ticks: { color: "#6B7280", callback: (v) => (v >= 1e6 ? `Rp ${Math.round(v / 1e6)} jt` : formatRp(v, true)) } },
                    x: { grid: { display: false }, border: { display: false }, ticks: { color: "#6B7280" } },
                },
            },
        }));
    }

    // K3b-rev 15 Sep: donut Beranda = 5 kategori produk (category_map.json).
    // Warna dikunci per kategori — urutan = CHART_COLORS.
    gkKategoriColor(name) {
        const MAP = {
            "Ayam Geprek": CHART_COLORS[0],
            "Paket Hemat": CHART_COLORS[1],
            "Snack & Tambahan": CHART_COLORS[2],
            "Minuman": CHART_COLORS[3],
            "Lainnya": CHART_COLORS[5],
        };
        return MAP[name] || CHART_COLORS[5];
    }

    renderBerandaKategori(Chart) {
        const el = document.querySelector(".gk-chart-beranda-kategori canvas");
        if (!el) return;
        const src = (this.state.data.beranda && this.state.data.beranda.kategori_produk) || [];
        if (!src.length) return;
        const total = src.reduce((s, c) => s + (c.amount || 0), 0);
        this.state.charts.push(new Chart(el, {
            type: "doughnut",
            data: {
                labels: src.map((c) => c.name),
                datasets: [{ data: src.map((c) => c.amount), backgroundColor: src.map((c) => this.gkKategoriColor(c.name)), borderWidth: 2, borderColor: "#fff" }],
            },
            options: { responsive: true, maintainAspectRatio: false, cutout: "68%", plugins: { legend: { display: false } } },
            plugins: [{
                id: "centerTextBerandaKategori",
                afterDraw(chart) {
                    const { ctx } = chart;
                    const meta = chart.getDatasetMeta(0);
                    if (!meta.data.length) return;
                    const { x, y } = meta.data[0];
                    ctx.save(); ctx.textAlign = "center";
                    ctx.font = "700 16px 'Inter', 'Segoe UI', sans-serif"; ctx.fillStyle = "#1A1D29"; ctx.fillText(formatRp(total, true), x, y - 2);
                    ctx.font = "11px 'Inter', sans-serif"; ctx.fillStyle = "#6B7280"; ctx.fillText("Total", x, y + 14);
                    ctx.restore();
                },
            }],
        }));
    }

    renderBerandaMonthly(Chart) {
        const el = document.querySelector(".gk-chart-beranda-monthly canvas");
        if (!el) return;
        const rows = (this.state.data.beranda && this.state.data.beranda.laba_bulanan) || [];
        if (!rows.length) return;
        const labels = rows.map((r) => r.label);
        const values = rows.map((r) => r.value);
        const bg = values.map((v) => v >= 0 ? "#0F7C6C" : "#D64545");
        this.state.charts.push(new Chart(el, {
            type: "bar",
            data: { labels, datasets: [{ label: "Laba", data: values, backgroundColor: bg, borderRadius: 6, borderSkipped: false, barThickness: 22 }] },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => formatRp(c.parsed.y) } } },
                scales: {
                    y: { grid: { color: "#EEF1F4", drawTicks: false }, border: { display: false }, ticks: { color: "#6B7280", callback: (v) => (v >= 1e6 ? `${Math.round(v/1e6)}jt` : String(v)) } },
                    x: { grid: { display: false }, border: { display: false }, ticks: { color: "#6B7280", maxRotation: 0 } },
                },
            },
        }));
    }

    renderLineDaily(Chart, daily) {
        const el = document.querySelector(".gk-chart-daily canvas");
        if (!el) return;
        const labels = daily.map(x => x.date.slice(8));
        const values = daily.map(x => x.amount);
        const maxV = Math.max(...values, 1);
        const ctx = el.getContext("2d");
        const h = (el.parentElement && el.parentElement.clientHeight) || 300;
        const gradient = ctx.createLinearGradient(0, 0, 0, h);
        gradient.addColorStop(0, "rgba(15, 124, 108, 0.18)");
        gradient.addColorStop(1, "rgba(15, 124, 108, 0)");
        let maxIdx = -1, minIdx = -1;
        values.forEach((v, i) => {
            if (maxIdx < 0 || v > values[maxIdx]) maxIdx = i;
            if (minIdx < 0 || v < values[minIdx]) minIdx = i;
        });
        const avg = values.reduce((s, v) => s + v, 0) / Math.max(values.length, 1);
        this.state.charts.push(new Chart(el, {
            type: "line",
            data: {
                labels,
                datasets: [
                    {
                        label: "Omzet Harian",
                        data: values,
                        borderColor: "#0F7C6C",
                        backgroundColor: gradient,
                        fill: true,
                        tension: 0.35,
                        pointRadius: 2,
                        pointHoverRadius: 4,
                        order: 1,
                    },
                    {
                        label: "Rata-rata Harian",
                        data: labels.map(() => avg),
                        borderColor: "rgba(107, 114, 128, 0.55)",
                        borderDash: [5, 5],
                        borderWidth: 1,
                        pointRadius: 0,
                        fill: false,
                        order: 2,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        filter: (item) => item.datasetIndex === 0,
                        callbacks: { label: (c) => formatRp(c.parsed.y) },
                    },
                },
                scales: {
                    y: {
                        grid: { color: "#E4E7EC", drawTicks: false },
                        border: { display: false },
                        ticks: {
                            color: "#6B7280",
                            callback: (v) => (v >= 1e6 ? `Rp ${Math.round(v / 1e6)} jt` : formatRp(v, true)),
                        },
                        suggestedMax: maxV * 1.15,
                    },
                    x: {
                        grid: { display: false },
                        border: { display: false },
                        ticks: { color: "#6B7280" },
                    },
                },
            },
            plugins: [{
                id: "gkHighLow",
                afterDatasetsDraw(chart) {
                    const cctx = chart.ctx;
                    const meta = chart.getDatasetMeta(0);
                    const area = chart.chartArea;
                    if (!meta || !meta.data || !area) return;
                    const drawTag = (idx, dotColor) => {
                        const pt = meta.data[idx];
                        if (!pt) return;
                        const val = formatRp(values[idx], true);
                        cctx.save();
                        cctx.fillStyle = dotColor;
                        cctx.beginPath();
                        cctx.arc(pt.x, pt.y, 3, 0, Math.PI * 2);
                        cctx.fill();
                        cctx.strokeStyle = "#fff";
                        cctx.lineWidth = 1.5;
                        cctx.stroke();
                        cctx.font = "600 11px 'Inter', 'Segoe UI', sans-serif";
                        const w = cctx.measureText(val).width;
                        let tx = Math.min(Math.max(pt.x - w / 2 - 5, area.left), area.right - w - 10);
                        let ty = pt.y - 20;
                        if (ty < area.top) ty = pt.y + 10;
                        cctx.fillStyle = "rgba(255, 255, 255, 0.85)";
                        cctx.fillRect(tx, ty, w + 10, 15);
                        cctx.fillStyle = "#1A1D29";
                        cctx.fillText(val, tx + 5, ty + 11);
                        cctx.restore();
                    };
                    if (maxIdx >= 0) drawTag(maxIdx, "#0F7C6C");
                    if (minIdx >= 0 && minIdx !== maxIdx) drawTag(minIdx, "#D64545");
                },
            }],
        }));
    }

    gkChannelColor(name) {
        const MAP = {
            "Dine-in / Walk-in": CHART_COLORS[0],
            "Gofood": CHART_COLORS[1],
            "Grabfood": CHART_COLORS[2],
            "Shopeefood": CHART_COLORS[3],
            "ShopeeFood": CHART_COLORS[3],
        };
        return MAP[name] || null;
    }

    renderDonutChannels(Chart, channels) {
        const el = document.querySelector(".gk-chart-channel canvas");
        if (!el) return;
        const total = channels.reduce((s, c) => s + c.amount, 0);
        this.state.charts.push(new Chart(el, {
            type: "doughnut",
            data: {
                labels: channels.map(c => c.name),
                datasets: [{
                    data: channels.map(c => c.amount),
                    backgroundColor: channels.map((c) => this.gkChannelColor(c.name) || "#64748B"),
                    borderWidth: 2,
                    borderColor: "#fff",
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "68%",
                plugins: { legend: { display: false } },
            },
            plugins: [{
                id: "centerText",
                afterDraw(chart) {
                    const { ctx } = chart;
                    const meta = chart.getDatasetMeta(0);
                    if (!meta.data.length) return;
                    const { x, y } = meta.data[0];
                    ctx.save();
                    ctx.textAlign = "center";
                    ctx.font = "700 18px 'Inter', 'Segoe UI', sans-serif";
                    ctx.fillStyle = "#1A1D29";
                    ctx.fillText(formatRp(total, true), x, y - 4);
                    ctx.font = "12px 'Inter', 'Segoe UI', sans-serif";
                    ctx.fillStyle = "#6B7280";
                    ctx.fillText("Total Omzet", x, y + 14);
                    ctx.restore();
                },
            }],
        }));
    }

    renderKpiSparklines(Chart) {
        const d = this.state.data;
        if (!d || !d.has_data) return;
        const sources = {
            omzet: (d.summary && d.summary.daily || []).map((x) => x.amount),
            net_profit: (d.finance && d.finance.daily_net_profit || []).map((x) => x.value),
            orders: (d.summary && d.summary.daily_orders || []).map((x) => x.count),
            avg_ticket: (d.summary && d.summary.daily_avg_ticket || []).map((x) => (x.count ? x.value : null)),
        };
        document.querySelectorAll(".gk-kpi-spark[data-kpi]").forEach((box) => {
            const key = box.getAttribute("data-kpi");
            const canvas = box.querySelector("canvas");
            if (!canvas || !(key in sources)) return;
            const values = sources[key];
            if (!values.length || values.every((v) => v === null || v === 0)) return;
            this.state.charts.push(new Chart(canvas, {
                type: "line",
                data: {
                    labels: values.map((_, i) => String(i + 1)),
                    datasets: [{
                        data: values,
                        borderColor: "#0F7C6C",
                        borderWidth: 1.5,
                        tension: 0.35,
                        pointRadius: 0,
                        fill: false,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: false,
                    plugins: { legend: { display: false }, tooltip: { enabled: false } },
                    scales: { x: { display: false }, y: { display: false, beginAtZero: false } },
                },
            }));
        });
    }

    scrollTop() {
        if (this.mainRef && this.mainRef.el) this.mainRef.el.scrollTop = 0;
    }

    selectTab(tabId) {
        this.state.activeTab = tabId;
        this.scrollTop();
        setTimeout(() => this.renderCharts(), 50);
    }

    toggleOutletMenu() {
        this.state.outletMenuOpen = !this.state.outletMenuOpen;
    }

    selectOutlet(opt) {
        this.state.outletFilter = { id: opt.id, name: opt.name, ids: opt.ids };
        this.state.outletMenuOpen = false;
        this.scrollTop();
        this.load();
    }

    pct(vsValue) {
        if (vsValue === null || vsValue === undefined) return null;
        return `${vsValue >= 0 ? "+" : ""}${vsValue}%`;
    }

    pctArrow(vsValue) {
        if (vsValue === null || vsValue === undefined) return null;
        return `${vsValue >= 0 ? "↑" : "↓"} ${Math.abs(vsValue)}%`;
    }

    pctClass(vsValue) {
        if (vsValue === null || vsValue === undefined) return "";
        return vsValue >= 0 ? "up" : "down";
    }

    barPct(amount, max) {
        return max ? `${Math.max(2, Math.round(amount / max * 100))}%` : "0%";
    }

    gkExpenseColor(category) {
        const MAP = {
            "hpp": "#0F7C6C",
            "depreciation": "#3B6FE0",
            "operational": "#E8A33D",
        };
        return MAP[category] || "#64748B";
    }

    gkPaymentColor(group) {
        const MAP = {
            "qris": "#0F7C6C",
            "cash": "#E8A33D",
            "ewallet": "#3B6FE0",
            "card": "#8B5CF6",
        };
        return MAP[group] || "#64748B";
    }

    pctLabel(amount, total) {
        if (!total) return "";
        return ` · ${(amount / total * 100).toFixed(1).replace(".", ",")}%`;
    }

    paymentsTotal() {
        const p = (this.state.data && this.state.data.sales && this.state.data.sales.payments) || [];
        return p.reduce((s, x) => s + (x.amount || 0), 0);
    }

    cashTotal() {
        const c = (this.state.data && this.state.data.finance && this.state.data.finance.cash_positions) || [];
        return c.reduce((s, x) => s + (x.balance || 0), 0);
    }

    cashKindIcon(kind) {
        return { kas: "fa fa-money", ewallet: "fa fa-mobile-phone", bank: "fa fa-university" }[kind] || "fa fa-circle";
    }

    cashKindLabel(kind) {
        return { kas: "Kas", ewallet: "E-Wallet", bank: "Bank" }[kind] || kind;
    }

    cashCardColor(idx, accent = false) {
        const CASH_PALETTE = [0, 1, 2, 4, 5].map((i) => CHART_COLORS[i]);
        const hex = CASH_PALETTE[idx % CASH_PALETTE.length];
        if (accent) return hex;
        const n = parseInt(hex.slice(1), 16);
        const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
        return `rgba(${r}, ${g}, ${b}, 0.10)`;
    }

    heroDelta() {
        const fin = (this.state.data && this.state.data.finance) || {};
        if (fin.net_profit_prev === null || fin.net_profit_prev === undefined) return null;
        if (!fin.net_profit_prev) return null;
        return Math.round((fin.net_profit - fin.net_profit_prev) / Math.abs(fin.net_profit_prev) * 1000) / 10;
    }

    // --- Beranda helpers (F1) ---
    // OVERHAUL 15 Sep (K1): helper hero band & gauge dihapus — Laba Bersih
    // tampil sebagai KPI ke-5. heroDelta() dipertahankan (dipakai tab Laporan).
    berandaKpi(key) {
        const b = this.state.data && this.state.data.beranda;
        if (b && b.kpi && b.kpi[key] !== undefined) return b.kpi[key];
        const f = (this.state.data && this.state.data.finance) || {};
        const MAP = {
            net_revenue: f.income_total || 0,
            hpp_total: f.hpp_total || 0,
            gross_profit: (f.income_total || 0) - (f.hpp_total || 0),
            opex: (f.expense_total || 0) - (f.hpp_total || 0),
            net_profit: f.net_profit || 0,
            margin_pct: f.income_total ? (f.net_profit || 0)/(f.income_total)*100 : 0,
        };
        return MAP[key] ?? 0;
    }
    berandaVs(key) {
        const b = this.state.data && this.state.data.beranda;
        if (b && b.vs && b.vs[key] !== undefined) return b.vs[key];
        return null;
    }
    berandaKas(key) {
        const ks = this.state.data && this.state.data.beranda && this.state.data.beranda.kas_settlement;
        if (ks && ks[key] !== undefined) return ks[key];
        return 0;
    }
    berandaArus(key) {
        const a = this.state.data && this.state.data.beranda && this.state.data.beranda.arus_kas_psak;
        if (a && a[key] !== undefined) return a[key];
        return 0;
    }
    berandaNeraca(key) {
        const s = this.state.data && this.state.data.beranda && this.state.data.beranda.snapshot_neraca;
        if (s && s[key] !== undefined) return s[key];
        const fb = (this.state.data && this.state.data.finance && this.state.data.finance.balance) || {};
        const MAP = { aset: fb.total_assets||0, kewajiban: fb.liabilities||0, ekuitas: fb.equity||0, laba_ditahan: fb.net_income_ytd||0, total_liab_ekuitas: fb.total_liab_equity||0 };
        return MAP[key] ?? 0;
    }
    get gauge() {
        return null; // OVERHAUL 15 Sep: gauge dihapus (K1) — dipertahankan sebagai no-op agar referensi lama tidak error
    }

    printReport() { window.print(); }
    exportExcel() {
        // F0: placeholder — akan jadi xlsx via report_actions di F5
        window.print();
    }

    openReports(reportKey = null) {
        const props = {
            initialYear: 2026,
            initialMonth: 8,
            outletFilter: { ...this.state.outletFilter },
        };
        // derive year/month from date_from for deep-link context
        if (this.state.date_from) {
            const [y,m] = this.state.date_from.split("-").map(Number);
            props.initialYear = y; props.initialMonth = m;
        }
        if (reportKey) props.initialReport = reportKey;
        this.action.doAction("geprekyukss_dashboard.action_geprekyukss_reports", { props });
    }
}

registry.category("actions").add("geprekyukss_dashboard.main", GkDashboard);
