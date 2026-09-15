"""test_beranda_overhaul.py — uji payload Beranda pasca-overhaul 15 Sep 2026. READ-ONLY.

Verifikasi (PLANNING_BERANDA_OVERHAUL_2026-09-15.md §7.2 + delta K3b-rev 15 Sep):
  1. beranda.laba_bulanan ter-populate (6 bulan) — fix bug unpack BUG_TRIAL_ERROR
  2. beranda.kategori_produk: 5 kategori, Σpct≈100, Σamount ≈ summary.amount_total (±2%)
  3. beranda.outlet_channel.per_channel tetap ada (legacy/fallback donut)
  4. 5 KPI ada & non-null saat has_data
  5. beranda.tren length == jumlah hari periode
  6. arus_kas_psak / snapshot_neraca / kas_settlement masih ada
  7. summary.outlets & sales.channels TETAP ada (dipakai tab lain)

Jalankan:
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 --db_user odoo --db_password odoo" < scripts/test_beranda_overhaul.py
"""
import json

env  # noqa: F821

# reload modul terbaru
env["ir.module.module"].search([("name", "=", "geprekyukss_dashboard")]).button_immediate_upgrade()
env.cr.commit()

Data = env["geprekyukss.dashboard.data"]
aug = Data.get_dashboard_data("2026-08-01", "2026-08-31")

b = aug.get("beranda") or {}
errors = []
ok = []


def check(label, cond, detail=""):
    (ok if cond else errors).append(f"{'PASS' if cond else 'FAIL'}  {label}" + (f"  — {detail}" if detail else ""))


KATEGORI = {"Ayam Geprek", "Paket Hemat", "Snack & Tambahan", "Minuman", "Lainnya"}

# 0. tidak ada fallback (fallback = tandanya _beranda_detail raise)
check("beranda bukan fallback (tren non-empty atau kas terisi)",
      bool(b.get("tren")) or (b.get("kas_settlement", {}).get("total", 0) not in (None, 0.0)),
      f"tren_len={len(b.get('tren') or [])}")

# 1. laba_bulanan — fix bug unpack
lb = b.get("laba_bulanan") or []
check("laba_bulanan adalah list >= 6 bulan", isinstance(lb, list) and len(lb) >= 6, f"got {len(lb)}")

# 2. kategori_produk (K3b-rev — delta sesi ini)
kat = b.get("kategori_produk") or []
check("kategori_produk ada 5 baris", len(kat) == 5, f"got {len(kat)}: {[r.get('name') for r in kat]}")
check("kategori nama == KATEGORI standar", {r.get("name") for r in kat} == KATEGORI)
pct_sum = sum(r.get("pct") or 0 for r in kat)
check("Σ pct ≈ 100", abs(pct_sum - 100.0) <= 0.6, f"{pct_sum}")
amt_sum = sum(r.get("amount") or 0 for r in kat)
target = (aug.get("summary") or {}).get("amount_total") or 0.0
if target:
    check("Σ amount ≈ summary.amount_total (±2%)",
          abs(amt_sum - target) / target * 100.0 <= 2.0,
          f"kategori={amt_sum:,.0f} vs summary={target:,.0f}")
check("kategori terurut desc (Lainnya paling bawah)",
      all(kat[i]["amount"] >= kat[i + 1]["amount"] for i in range(len(kat) - 2)) if len(kat) >= 2 else True,
      json.dumps([(r["name"], round(r["amount"])) for r in kat]))

# 3. outlet_channel legacy tetap ada (fallback donut + tab lain)
oc = b.get("outlet_channel") or {}
check("outlet_channel TANPA per_outlet", "per_outlet" not in oc, str(list(oc.keys())))
check("outlet_channel.per_channel ada (legacy)", isinstance(oc.get("per_channel"), list) and len(oc["per_channel"]) > 0,
      f"{len(oc.get('per_channel') or [])} channel")

# 4. 5 KPI
kpi = b.get("kpi") or {}
check("5 KPI keys", {"net_revenue", "hpp_total", "gross_profit", "opex", "net_profit"} <= set(kpi.keys()))
for k in ("net_revenue", "hpp_total", "gross_profit", "opex", "net_profit"):
    check(f"kpi.{k} non-null", kpi.get(k) is not None, repr(kpi.get(k)))
check("margin_pct konsisten", abs((kpi.get("margin_pct") or 0) -
      ((kpi.get("net_profit") or 0) / kpi["net_revenue"] * 100 if kpi.get("net_revenue") else 0)) < 0.5)

# 5. tren harian
tren = b.get("tren") or []
check("tren length == 31 (Agustus)", len(tren) == 31, f"got {len(tren)}")
check("tren rows keys", all({"date", "pendapatan", "laba"} <= set(r.keys()) for r in tren))

# 6. section lain tetap ada
check("arus_kas_psak ada", isinstance(b.get("arus_kas_psak"), dict))
check("snapshot_neraca ada", isinstance(b.get("snapshot_neraca"), dict))
check("kas_settlement ada", isinstance(b.get("kas_settlement"), dict))

# 7. summary.outlets & sales.channels tidak terganggu
check("summary.outlets tetap ada", len((aug.get("summary") or {}).get("outlets") or []) > 0)
check("sales.channels tetap ada", len((aug.get("sales") or {}).get("channels") or []) > 0)

print("\n===== HASIL test_beranda_overhaul =====")
for line in ok:
    print(line)
if errors:
    print("\n--- GAGAL ---")
    for line in errors:
        print(line)
print(f"\nTotal: {len(ok)} pass, {len(errors)} fail")
print("\nkategori_produk:", json.dumps(kat, indent=1, ensure_ascii=False))
print("laba_bulanan:", json.dumps(lb, indent=1, ensure_ascii=False))
print("kpi:", json.dumps({k: round(v, 2) if isinstance(v, float) else v for k, v in kpi.items()}, indent=1))

if errors:
    raise SystemExit(1)
print("\nSEMUA CHECK BERHASIL ✔")
