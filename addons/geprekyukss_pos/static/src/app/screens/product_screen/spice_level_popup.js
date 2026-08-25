/** @odoo-module */

import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export const SPICE_LEVELS = [
    { value: "1", label: "1 🌶️" },
    { value: "2", label: "2 🌶️🌶️" },
    { value: "3", label: "3 🌶️🌶️🌶️" },
    { value: "4", label: "4 🌶️🌶️🌶️🌶️" },
    { value: "5", label: "5 🌶️🌶️🌶️🌶️🌶️" },
];

// Popup dibangun di atas komponen Dialog generik dari @web/core (bukan
// service "popup" lama yang sudah dihapus dari POS sejak refactor OWL).
// Dipanggil lewat this.dialog.add(SpiceLevelPopup, { productName, getPayload }).
export class SpiceLevelPopup extends Component {
    static template = "geprekyukss_pos.SpiceLevelPopup";
    static components = { Dialog };
    static props = {
        productName: String,
        close: Function,
        getPayload: Function,
    };

    setup() {
        this.levels = SPICE_LEVELS;
    }

    selectLevel(value) {
        this.props.getPayload(value);
        this.props.close();
    }

    cancel() {
        this.props.getPayload(null);
        this.props.close();
    }
}
