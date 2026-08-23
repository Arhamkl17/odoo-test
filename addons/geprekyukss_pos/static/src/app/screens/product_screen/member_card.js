/** @odoo-module */

import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";

export class MemberCard extends Component {
    static template = "geprekyukss_pos.MemberCard";
    static props = {};

    setup() {
        this.pos = usePos();
    }

    get partner() {
        return this.pos.get_order()?.get_partner();
    }

    get initials() {
        const p = this.partner;
        if (!p || !p.name) return "?";
        return p.name
            .split(" ")
            .filter(Boolean)
            .slice(0, 2)
            .map((w) => w[0].toUpperCase())
            .join("");
    }

    selectCustomer() {
        this.pos.showScreen("PartnerListScreen", { list: this.pos.models["res.partner"].getAll() });
    }
}
