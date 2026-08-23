{
    "name": "Geprekyukss - Custom POS (Spice Level & Member WA)",
    "version": "19.0.1.0.0",
    "category": "Point of Sale",
    "summary": "Level pedas per orderline + verifikasi member via nomor WhatsApp",
    "description": """
Custom module untuk POS Geprekyukss.
""",
    "author": "Custom - Geprekyukss",
    "depends": ["point_of_sale", "pos_restaurant"],
    "data": [
        "views/product_template_views.xml",
        "views/res_partner_views.xml",
        "views/pos_category_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "geprekyukss_pos/static/src/app/utils/fit_width_scale.js",
            "geprekyukss_pos/static/src/scss/pos_theme.scss",
            "geprekyukss_pos/static/src/overrides/components/category_selector/category_selector_patch.js",
            "geprekyukss_pos/static/src/overrides/components/category_selector/category_selector_patch.xml",
                "geprekyukss_pos/static/src/overrides/models/models.js",
            "geprekyukss_pos/static/src/app/screens/product_screen/spice_level_popup.js",
            "geprekyukss_pos/static/src/app/screens/product_screen/spice_level_popup.xml",
            "geprekyukss_pos/static/src/app/generic_components/orderline/orderline_patch.xml",
            "geprekyukss_pos/static/src/app/screens/product_screen/product_card_badges.xml",
            "geprekyukss_pos/static/src/app/navbar/header_brand_patch.xml",
            "geprekyukss_pos/static/src/app/screens/product_screen/product_screen_layout_patch.xml",
            "geprekyukss_pos/static/src/app/screens/product_screen/member_card.js",
            "geprekyukss_pos/static/src/app/screens/product_screen/member_card.xml",
            ("after", "pos_restaurant/static/src/app/screens/product_screen/actionpad_widget/actionpad_widget.xml", "geprekyukss_pos/static/src/app/screens/product_screen/actionpad_widget/actionpad_widget_patch.xml"),
            ("after", "pos_restaurant/static/src/app/screens/product_screen/control_buttons/control_buttons.xml", "geprekyukss_pos/static/src/app/screens/product_screen/control_buttons_patch.xml"),
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
