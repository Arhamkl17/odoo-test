from odoo import fields, models

CATEGORY_ICONS = [
    ("none", "Tidak Ada"),
    ("🔥", "🔥 Paket Geprek Recomended"),
    ("🍚🍗", "🍚🍗 Paket Crispy"),
    ("🍗", "🍗 Single Ayam"),
    ("🥤", "🥤 Minuman"),
    ("🌶️", "🌶️ Sambal"),
    ("🍛", "🍛 Paket Geprek Sambal"),
    ("🍜", "🍜 Paket Indomie Crispy"),
    ("➕", "➕ Add On"),
]


class PosCategory(models.Model):
    _inherit = "pos.category"

    pos_category_icon = fields.Selection(
        CATEGORY_ICONS,
        string="Ikon Preset",
        default="none",
        help=(
            "Ikon bawaan (font-icon) yang tampil di depan nama kategori pada "
            "tab horizontal di kasir POS. Kalau kategorimu butuh ikon yang "
            "tidak ada di preset ini (mis. ayam/drumstick/mangkuk seperti di "
            "screenshot referensi), upload ikon custom di field "
            "'Ikon Kustom' di bawah — kalau diisi, ikon kustom itu yang "
            "dipakai dan preset ini diabaikan."
        ),
    )

    pos_category_icon_image = fields.Image(
        string="Ikon Kustom (opsional)",
        max_width=64,
        max_height=64,
        help=(
            "Upload PNG/SVG persegi transparan (idealnya 64x64) untuk ikon "
            "kategori yang tidak tersedia di preset font-icon bawaan Odoo "
            "(mis. ikon ayam untuk 'Paket Crispy', drumstick untuk 'Single "
            "Ayam', mangkuk untuk 'Side Dish' — lihat screenshot referensi). "
            "Kalau kosong, sistem pakai 'Ikon Preset' di atas; kalau "
            "keduanya kosong, tab kategori tampil tanpa ikon."
        ),
    )

    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        return fields_list + ["pos_category_icon", "pos_category_icon_image"]
