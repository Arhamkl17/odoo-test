Tolong cek kesiapan sistem Odoo 19 ini (database Test1) untuk mulai testing dengan
data transaksi real, khususnya dari sisi akuntansi/keuangan.

Baca dulu PROGRESS.md di root repo untuk konteks lengkap project ini (data apa yang
sudah diimport, struktur folder, cara koneksi ke Odoo).

Lakukan pengecekan berikut lewat XML-RPC (kredensial ambil dari environment variable
ODOO_URL/ODOO_DB/ODOO_USER/ODOO_PASSWORD, jangan hardcode):

1. **Payment Methods POS** (`pos.payment.method`) - apa saja yang sudah ada, dan
   apakah masing-masing sudah terhubung ke journal yang benar (terutama Cash dan
   metode non-tunai seperti QRIS/OVO/GOPAY yang akunnya sudah kita buat di COA).

2. **Journals** (`account.journal`) - apakah Sales Journal, Purchase Journal, dan
   Cash/Bank Journal sudah ada dan terhubung ke akun default yang sesuai
   (bandingkan dengan COA yang sudah diimport, kode akun 1100-1103 dst).

3. **Konfigurasi POS** (`pos.config`) - apakah `payment_method_ids` sudah terisi
   dengan payment methods yang relevan, dan `journal_id`/`invoice_journal_id`
   sudah benar.

4. **Metode valuasi stok** - cek `property_cost_method` dan
   `property_valuation` di tiap `product.category` yang sudah kita buat
   (7 kategori: Bahan Baku Food/Beverage, Bahan Pendukung Menu, Barang
   Perlengkapan Operasional, Gas, Menu Food, Menu Beverage) - apakah sudah
   konsisten (FIFO/Average) atau masih default kosong.

5. **Fiscal Year** - cek `fiscalyear_last_day`/`fiscalyear_last_month` di
   `res.company`, dan apakah ada `account.fiscal.year` yang relevan untuk
   periode berjalan.

6. **Saldo awal** - cek apakah ada `account.move` sama sekali di sistem
   (search_count kosong berarti belum ada opening balance atau transaksi apapun).

7. **Data transaksi existing** - cek `pos.order` search_count, pastikan memang
   masih 0 (belum ada transaksi test yang keburu masuk tanpa sengaja).

Setelah semua dicek, buat laporan singkat dalam bahasa Indonesia:
- Tabel status tiap poin di atas (✅ Siap / ⚠️ Perlu diisi / ❌ Belum ada)
- Untuk yang ⚠️ atau ❌, jelaskan SPESIFIK apa yang perlu diisi dan lewat menu
  Odoo mana (path menu UI, bukan cuma nama teknis field)
- Kesimpulan akhir: apakah sistem sudah SIAP untuk mulai input data transaksi
  1 bulan sebagai testing, atau ada blocker yang harus diselesaikan dulu

Jangan ubah/tulis apapun ke database di tahap ini - murni read-only investigation
dan laporan.
