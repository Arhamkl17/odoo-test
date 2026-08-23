/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { Orderline } from "@point_of_sale/app/components/orderline/orderline";
import { OrderDisplay } from "@point_of_sale/app/components/order_display/order_display";
import { MemberCard } from "@geprekyukss_pos/app/screens/product_screen/member_card";
import { SpiceLevelPopup, SPICE_LEVELS } from "@geprekyukss_pos/app/screens/product_screen/spice_level_popup";
import { QuantityButtons } from "@point_of_sale/app/components/buttons/quantity_buttons/quantity_buttons";

const SPICE_LABEL_BY_VALUE = Object.fromEntries(SPICE_LEVELS.map((l) => [l.value, l.label]));

// Tambah getter di komponen Orderline (dipakai bareng layar kasir & struk)
// supaya template orderline_patch.xml bisa nampilin label "Pedas", "Extra
// Pedas", dst dari kode "1".."5" yang tersimpan di field spice_level.
patch(Orderline.prototype, {
    get spiceLevelLabel() {
        return SPICE_LABEL_BY_VALUE[this.props.line.spice_level] || "";
    },
    gySetLineQuantity(line, qty) {
        if (qty <= 0) {
            line.order_id.removeOrderline(line);
        } else {
            line.setQuantity(qty);
        }
    },
    gyDeleteLine(line) {
        line.order_id.removeOrderline(line);
    },
});

// Daftarkan QuantityButtons sebagai sub-component Orderline (dipakai orderline_patch.xml)
patch(Orderline, {
    components: { ...Orderline.components, QuantityButtons },
});

// CATATAN KOMPATIBILITAS:
// Titik ekstensi resmi untuk "apa yang terjadi saat produk ditambahkan ke
// order" di Odoo 17-19 ada di service PosStore, method addLineToCurrentOrder
// (dipakai juga oleh fitur bawaan seperti tracking lot/serial, timbangan,
// dan product configurator). Kalau setelah upgrade Odoo nama method ini
// berubah, cara paling cepat cek: buka Codespace, jalankan
//   grep -rn "addLineToCurrentOrder" /path/ke/source/point_of_sale/static/src/app/services/pos_store.js
// Titik hook resmi popup spice level: ProductScreen.addProductToOrder
// (kepanggil langsung saat klik card produk - dikonfirmasi banner debug + grep source)
patch(ProductScreen.prototype, {
    async addProductToOrder(product) {
        if (product && product.pos_spicy) {
            const spiceLevel = await new Promise((resolve) => {
                this.dialog.add(SpiceLevelPopup, {
                    productName: product.display_name,
                    getPayload: (value) => resolve(value),
                });
            });

            // Kasir batal pilih level -> jangan tambahkan produk ke order.
            if (!spiceLevel) {
                return;
            }

            const options = {};
            if (this.searchWord && product.isConfigurable()) {
                const barcode = this.searchWord;
                const searchedProduct = product.product_variant_ids.filter(
                    (p) => p.barcode && p.barcode.includes(barcode)
                );
                if (searchedProduct.length === 1) {
                    options["presetVariant"] = searchedProduct[0];
                }
            }

            await this.pos.addLineToCurrentOrder(
                { product_tmpl_id: product, spice_level: spiceLevel },
                options
            );
            this.showOptionalProductPopupIfNeeded(product);
            return;
        }
        return super.addProductToOrder(product);
    },

    gyClearOrder() {
        const order = this.pos.get_order();
        if (!order || order.isEmpty()) return;
        for (const line of [...order.lines]) {
            order.removeOrderline(line);
        }
    },

    async gyAddOrderNote() {
        const order = this.pos.get_order();
        if (!order) return;
        const { TextInputPopup } = await import("@point_of_sale/app/components/popups/text_input_popup/text_input_popup");
        const payload = await this.dialog.add(TextInputPopup, {
            title: "Tambah Catatan",
            placeholder: "Tulis catatan untuk pesanan ini...",
            startingValue: order.general_customer_note || "",
        });
        if (payload) {
            order.general_customer_note = payload;
        }
    },
});


patch(OrderDisplay, {
    components: { ...OrderDisplay.components, MemberCard },
});
