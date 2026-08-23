import { patch } from "@web/core/utils/patch";
import { CategorySelector } from "@point_of_sale/app/components/category_selector/category_selector";

patch(CategorySelector.prototype, {
    getChildCategoriesInfo(category) {
        const info = super.getChildCategoriesInfo(category);
        const hasEmoji = category.pos_category_icon && category.pos_category_icon !== "none";
        const hasCustomImg = !!category.pos_category_icon_image;
        return {
            ...info,
            gyIcon: hasEmoji
                ? category.pos_category_icon
                : hasCustomImg
                    ? `/web/image?model=pos.category&field=pos_category_icon_image&id=${category.id}`
                    : null,
            gyIconIsImage: !hasEmoji && hasCustomImg,
        };
    },
});
