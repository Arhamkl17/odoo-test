"""test_narrative.py — verifikasi ringkasan naratif rule-based (SPEC_V2 #6).

READ-ONLY; upgrade modul di awal.

Verifikasi:
- payload["narrative"] selalu list[str]
- Panjang 1-5 kalimat (tergantung kondisi data)
- Untuk Agustus 2026 dengan data penuh: minimal 2 kalimat muncul
  (headline omzet + status laba)
- Filter outlet=None → ada kalimat "Outlet X unggul dari Y"
- Filter outlet=[1] / [2] → kalimat outlet-comparison TIDAK muncul
- Bulan tanpa data (Juli) → narrative adalah list kosong []
- HPP kalimat muncul bila HPP > 30% total beban
- Output ke console untuk inspeksi manual

Jalankan:
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 --db_user odoo --db_password odoo" < scripts/test_narrative.py
"""
import json

env  # noqa: F821

env["ir.module.module"].search([("name", "=", "geprekyukss_dashboard")]).button_immediate_upgrade()
env.cr.commit()

Data = env["geprekyukss.dashboard.data"]


def narrate(label, outlet_ids):
    d = Data.get_dashboard_data("2026-08-01", "2026-08-31", outlet_ids=outlet_ids)
    narr = d.get("narrative") or []
    print(f"\n=== {label} ({len(narr)} kalimat) ===")
    for i, line in enumerate(narr, 1):
        print(f"  {i}. {line}")
    return narr, d


print("=" * 60)
print("AGUSTUS 2026 — ringkasan naratif")
print("=" * 60)

n_all, d_all = narrate("ALL (outlet_ids=None)", None)
n_pal, d_pal = narrate("PALLANGGA (outlet_ids=[1])", [1])
n_mal, d_mal = narrate("MALLENGKERI (outlet_ids=[2])", [2])

# Bulan tanpa data (Juli) → narrative kosong
d_jul = Data.get_dashboard_data("2026-07-01", "2026-07-31", outlet_ids=None)
print(f"\n=== JULI (placeholder, {len(d_jul.get('narrative', []))} kalimat) ===")
print("(diharapkan kosong)")
print(json.dumps(d_jul.get("narrative", []), indent=1, ensure_ascii=False))


# ---- Asersi
print("\n=== INVARIANTS ===")
errs = []

# Syarat 1: setiap payload punya field narrative sebagai list
for label, d in [("ALL", d_all), ("PALLANGGA", d_pal), ("MALLENGKERI", d_mal), ("JULI", d_jul)]:
    narr = d.get("narrative")
    if not isinstance(narr, list):
        errs.append(f"{label}: narrative bukan list (type={type(narr).__name__})")

# Syarat 2: Agustus dengan data punya minimal 1 kalimat (biasanya 2-5)
for label, narr in [("ALL", n_all), ("PALLANGGA", n_pal), ("MALLENGKERI", n_mal)]:
    if len(narr) < 2:
        errs.append(f"{label}: hanya {len(narr)} kalimat (minimal 2 untuk Agustus)")
    if len(narr) > 5:
        errs.append(f"{label}: {len(narr)} kalimat (maksimal 5)")

# Syarat 3: kalimat outlet-comparison HANYA muncul saat filter=None
all_text = " ".join(n_all)
pal_text = " ".join(n_pal)
mal_text = " ".join(n_mal)
outlet_keywords = ["sedikit unggul", "sedikit di bawah"]
for label, narr, text in [("ALL", n_all, all_text), ("PALLANGGA", n_pal, pal_text), ("MALLENGKERI", n_mal, mal_text)]:
    has_outlet_sentence = any(kw in text for kw in outlet_keywords)
    expected = (label == "ALL")
    if has_outlet_sentence != expected:
        errs.append(f"{label}: kalimat outlet-comparison muncul={has_outlet_sentence}, expected={expected}")

# Syarat 4: kalimat omzet headline muncul di semua skenario Agustus
for label, narr in [("ALL", n_all), ("PALLANGGA", n_pal), ("MALLENGKERI", n_mal)]:
    if not any("Omzet Agustus 2026" in s for s in narr):
        errs.append(f"{label}: tidak ada kalimat headline omzet")

# Syarat 5: kalimat HPP muncul bila HPP > 30% beban
# (dari data Agustus: HPP food+beverage ≈ 100 jt dari total 246 jt → ~41%, harus muncul)
for label, narr in [("ALL", n_all), ("PALLANGGA", n_pal), ("MALLENGKERI", n_mal)]:
    if not any("HPP" in s and "beban" in s for s in narr):
        errs.append(f"{label}: kalimat HPP tidak muncul (padahal >30% dari total beban)")

# Syarat 6: Juli (placeholder) → narrative kosong
if d_jul.get("narrative"):
    errs.append(f"JULI: narrative tidak kosong ({len(d_jul['narrative'])} kalimat)")

# Syarat 7: kalimat laba bersih muncul di Agustus
for label, narr in [("ALL", n_all), ("PALLANGGA", n_pal), ("MALLENGKERI", n_mal)]:
    if not any("Laba bersih" in s for s in narr):
        errs.append(f"{label}: tidak ada kalimat status laba bersih")

# ---- Output hasil
if errs:
    print("[GAGAL]")
    for e in errs:
        print(f"   - {e}")
else:
    print("[LULUS]")
    print(f"  - 3 skenario Agustus menghasilkan {len(n_all)}/{len(n_pal)}/{len(n_mal)} kalimat (maks 5)")
    print(f"  - kalimat outlet-comparison hanya muncul di filter ALL ✓")
    print(f"  - headline omzet + HPP + laba bersih konsisten antar filter ✓")
    print(f"  - Juli (placeholder) menghasilkan narrative kosong ✓")

env.cr.rollback()
print("\nTEST SELESAI.")
