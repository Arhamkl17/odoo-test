from odoo import fields, models

SPICE_LEVELS = [
    ("1", "Anti Pedas"),
    ("2", "Sedang"),
    ("3", "Pedas"),
    ("4", "Extra Pedas"),
    ("5", "Level Neraka"),
]


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    spice_level = fields.Selection(
        SPICE_LEVELS,
        string="Level Pedas",
        help="Level pedas yang dipilih kasir/pelanggan saat order dibuat di POS.",
    )

    def _load_pos_data_fields(self, config_id):
        # PENTING: field baru harus didaftarkan di sini juga, atau field
        # spice_level tidak akan ikut ter-load ke frontend POS maupun
        # ter-terima balik saat order disinkronkan dari kasir ke server.
        # Nama method ini konsisten di Odoo 17-19 (dipanggil per model
        # lewat models/pos_session.py -> _load_pos_data). Kalau setelah
        # instal ternyata spice_level tidak muncul di record pos.order.line,
        # cek ulang nama method ini di source point_of_sale/models/pos_order.py
        # versi yang benar-benar ter-install (bisa beda 1-2 kata antar rilis).
        fields_list = super()._load_pos_data_fields(config_id)
        return fields_list + ["spice_level"]
