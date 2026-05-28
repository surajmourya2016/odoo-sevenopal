from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _get_images(self):
        """Override: fix first carousel slide for products imported via product.template.

        product.product.image_1920 is a computed (non-stored) field that falls back to
        the template. Odoo's /web/image endpoint can be unreliable for computed image
        fields, resulting in the persistent spinner seen on the first thumbnail.

        Fix: when the variant has no own image (image_variant_1920 is empty), return
        product.template as the first slide instead. product.template.image_1920 is
        a stored field and is served instantly by /web/image.
        """
        self.ensure_one()
        variant_images  = list(self.product_variant_image_ids)
        template_images = list(self.product_tmpl_id.product_template_image_ids)

        if self.image_variant_1920:
            # Variant has its own image stored — show it first
            return [self] + variant_images + template_images

        if self.product_tmpl_id.image_1920:
            # No variant image, but template has a stored image — use template as first slide
            # This renders /web/image/product.template/ID/image_1920 (stored, fast)
            return [self.product_tmpl_id] + variant_images + template_images

        # No main image at all — skip the blank slot, start on first extra image
        return variant_images + template_images or [self]
