from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    pos_wa_number = fields.Char(
        string="Nomor WhatsApp (Member)",
        help="Nomor WA yang dipakai untuk verifikasi member di kasir POS.",
    )
    pos_wa_verified = fields.Boolean(
        string="WA Terverifikasi",
        default=False,
        help="Dicentang otomatis setelah pelanggan berhasil verifikasi OTP WA.",
    )
    pos_loyalty_points = fields.Integer(
        string="Poin Loyalti (Manual)",
        default=0,
        help=(
            "Placeholder poin loyalti sederhana. Kalau butuh sistem poin/diskon "
            "yang lebih lengkap (reward, kupon, tier member), pertimbangkan pakai "
            "modul bawaan Odoo 'loyalty' (Loyalty & Referral / Coupon) daripada "
            "reinvent lewat field ini — field ini cukup untuk MVP sederhana."
        ),
    )

    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        return fields_list + ["pos_wa_number", "pos_wa_verified", "pos_loyalty_points"]

    # -------------------------------------------------------------------
    # CATATAN PENTING soal OTP/verifikasi WhatsApp:
    # Odoo tidak punya built-in pengiriman OTP via WhatsApp. Untuk verifikasi
    # yang beneran (bukan simulasi seperti di preview), butuh integrasi ke
    # provider pihak ketiga, misalnya:
    #   - WhatsApp Business API resmi (Meta/Twilio/360dialog)
    #   - Provider lokal Indonesia (Fonnte, Wablas, dll — pastikan yang dipakai
    #     sesuai kebijakan WhatsApp Business, bukan API tidak resmi)
    # Alurnya nanti: JS di kasir panggil method Python (lewat RPC) -> method itu
    # request OTP ke API provider -> simpan kode+expiry sementara (mis. di cache
    # atau field terenkripsi) -> endpoint verify dipanggil balik dari kasir untuk
    # cocokkan kode -> set pos_wa_verified = True.
    # Bagian ini sengaja belum diimplementasikan di sini karena butuh keputusan
    # provider WA yang dipilih dulu.
    # -------------------------------------------------------------------
