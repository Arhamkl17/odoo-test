# -*- coding: utf-8 -*-
"""
geprekyukss.dashboard.category_map — pemetaan nama produk POS → 5 kategori
(OVERHAUL 15 Sep K3b-rev: donut Beranda = kategori produk, bukan channel).

Sumber mapping: data/category_map.json (199 produk dari odoo_products_export.json).
Fallback: rule-based untuk produk baru yang belum ada di json — supaya donut
tidak pernah kosong saat user membuat produk baru di POS.

Kategori (terkunci, sesuai SPEC_OVERHAUL_2026-09-15.md §4.3):
    Ayam Geprek / Paket Hemat / Snack & Tambahan / Minuman / Lainnya

Warna per kategori dikunci di frontend (dashboard.js gkKategoriColor) dan
harus konsisten urutannya dengan CHART_COLORS.
"""
import json
import os

KATEGORI = ["Ayam Geprek", "Paket Hemat", "Snack & Tambahan", "Minuman", "Lainnya"]

_MAP = None


def _load_map():
    """Load data/category_map.json sekali per proses (cache module-level)."""
    global _MAP
    if _MAP is None:
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "category_map.json",
        )
        try:
            with open(path, "r", encoding="utf-8") as f:
                _MAP = json.load(f)
        except Exception:
            _MAP = {}  # jangan pernah raise — donut tetap jalan via rule fallback
    return _MAP


# Urutan rule PENTING: Paket dicek SEBELUM Ayam ("PAKET AYAM CRISPY" = Paket Hemat).
_RULE_PAKET = ("PAKET", "PKG", "PKC", "BIG HEMAT", "SEGEPOK", "MENU SAMBAL", "YUKSSS RAMA", "SETIA")
_RULE_AYAM = ("AYAM", "GEPREK", "KULIT")
_RULE_MINUM = ("ES ", "MINUMAN", "AIR", "TEH", "COLA", "JUICE", "KOPI", "ORANGE", "LEMON", "CHOCO", "BLACKCURRANT", "GALON")
_RULE_SNACK = ("INDOMIE", "MIE", "TELUR", "TAHU", "TEMPE", "NASI", "SAMBAL", "SAOS SASET")


def get_category(product_name):
    """Nama produk (str) → salah satu dari 5 kategori KATEGORI.

    Prioritas: exact match json → rule-based → 'Lainnya'.
    """
    if not product_name:
        return "Lainnya"
    key = str(product_name).strip()
    m = _load_map()
    if key in m:
        cat = m[key]
        return cat if cat in KATEGORI else "Lainnya"
    up = key.upper()
    if any(k in up for k in _RULE_PAKET):
        return "Paket Hemat"
    if any(k in up for k in _RULE_AYAM):
        return "Ayam Geprek"
    if any(k in up for k in _RULE_MINUM):
        return "Minuman"
    if any(k in up for k in _RULE_SNACK):
        return "Snack & Tambahan"
    return "Lainnya"
