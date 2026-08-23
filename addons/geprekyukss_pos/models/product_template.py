from odoo import fields, models

POS_BADGES = [
    ("none", "Tidak Ada"),
    ("best_seller", "Best Seller"),
    ("new", "Baru"),
]


class ProductTemplate(models.Model):
    _inherit = "product.template"

    pos_spicy = fields.Boolean(
        string="Bisa Pilih Level Pedas",
        help=(
            "Kalau dicentang, produk ini akan memunculkan popup pilihan "
            "level pedas (1-5) saat ditambahkan ke pesanan di kasir POS. "
            "Cocok untuk semua varian Ayam Geprek."
        ),
        default=False,
    )

    pos_badge = fields.Selection(
        POS_BADGES,
        string="Badge Produk",
        default="none",
        help=(
            "Menampilkan label kecil di pojok kartu produk pada layar kasir "
            "POS, mis. 'BEST SELLER' (emas) atau 'NEW' (hijau). Badge "
            "'PEDAS' muncul otomatis kalau 'Bisa Pilih Level Pedas' dicentang, "
            "jadi tidak perlu diatur di sini."
        ),
    )

    def _load_pos_data_fields(self, config_id):
        # Sama seperti catatan di pos_order.py / res_partner.py: field custom
        # HARUS didaftarkan di sini juga supaya ikut ter-load ke data produk
        # di kasir POS. Tanpa ini, pos_spicy & pos_badge akan selalu terlihat
        # "falsy"/None di frontend walaupun sudah diisi di form produk —
        # sebelumnya pos_spicy belum terdaftar di sini sama sekali, jadi popup
        # level pedas tidak akan pernah muncul di kasir (bug, sudah diperbaiki
        # di sini).
        fields_list = super()._load_pos_data_fields(config_id)
        return fields_list + ["pos_spicy", "pos_badge"]
