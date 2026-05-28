from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # ── Certification ──────────────────────────────────────────────────────────
    so_enable_certification = fields.Boolean('Enable Certification Options', default=False)
    so_certificate_ids = fields.Many2many(
        'sevenopal.certificate',
        'product_template_certificate_rel',
        'product_id', 'certificate_id',
        string='Available Certificates',
    )

    # ── Ring / Pendant ─────────────────────────────────────────────────────────
    so_enable_ornament = fields.Boolean('Enable Ring/Pendant Selection', default=False)
    so_ornament_ids = fields.Many2many(
        'sevenopal.ornament',
        'product_template_ornament_rel',
        'product_id', 'ornament_id',
        string='Available Ornaments',
    )

    # ── Opal Identity ──────────────────────────────────────────────────────────
    so_is_calibrated_opal = fields.Boolean('Is Calibrated Opal', default=False)
    so_is_fire_opal       = fields.Boolean('Is Australian Fire Opal', default=False)
    so_is_jewellery       = fields.Boolean('Is Jewellery Opal', default=False)

    # ── Stone Specifications ───────────────────────────────────────────────────
    so_weight_carat     = fields.Float('Weight (Carat)',     digits=(10, 3))
    so_weight_ratti     = fields.Float('Weight (Ratti)',     digits=(10, 3))
    so_stone_dimension  = fields.Char('Stone Dimension',     help='e.g. 22.71 X 18.35 X 5.71 MM')
    so_shape            = fields.Char('Shape',               help='e.g. Oval Shaped Cabochon')
    so_origin           = fields.Char('Origin of Stone',     default='South Australia')
    so_opal_quality     = fields.Char('Opal Quality',        help='e.g. Premium Hong Kong Cut & Polish')
    so_stone_certification = fields.Char(
        'Stone Certification',
        help='e.g. Free LAB Certified – Opal Association of Australia',
    )
    so_opal_grading     = fields.Char(
        'Opal Grading',
        help='e.g. Grading as per GIA Analysis Black Opal – A to AAA+...',
    )

    # ── Pricing ────────────────────────────────────────────────────────────────
    so_price_per_carat  = fields.Float('Price per Carat',    digits=(10, 2))
    so_cost_per_carat   = fields.Float('Cost per Carat',     digits=(10, 2))
    so_total_price      = fields.Float(
        'Total Price', compute='_compute_so_total_price', store=True, digits=(10, 2),
    )

    # ── Shipping Dimensions ────────────────────────────────────────────────────
    so_weight_grams = fields.Float('Weight (g)',      digits=(10, 3))
    so_dim_length   = fields.Float('Length (mm)',     digits=(10, 2))
    so_dim_width    = fields.Float('Width (mm)',      digits=(10, 2))
    so_dim_height   = fields.Float('Height (mm)',     digits=(10, 2))

    # ── Stock / Checkout ───────────────────────────────────────────────────────
    so_allow_out_of_stock = fields.Boolean('Allow Checkout When Out of Stock', default=False)

    # ── Labels ─────────────────────────────────────────────────────────────────
    so_label_hot  = fields.Boolean('Label: Hot',  default=False)
    so_label_new  = fields.Boolean('Label: New',  default=False)
    so_label_sale = fields.Boolean('Label: Sale', default=False)

    # ── Collections ────────────────────────────────────────────────────────────
    so_is_new_arrival   = fields.Boolean('New Arrival',   default=False)
    so_is_best_seller   = fields.Boolean('Best Seller',   default=False)
    so_is_special_offer = fields.Boolean('Special Offer', default=False)

    # ── Media ──────────────────────────────────────────────────────────────────
    so_video_url  = fields.Char('Product Video URL', help='YouTube embed URL')

    # ── FAQs ───────────────────────────────────────────────────────────────────
    so_product_faq = fields.Html('Product FAQs', sanitize_tags=True)

    def _get_images(self):
        """Override: skip the template's own main image slot if image_1920 is not set,
        so the product gallery only shows actually-uploaded images."""
        self.ensure_one()
        extra = list(self.product_template_image_ids)
        if self.image_1920:
            return [self] + extra
        # No main image — show extras only (or a single placeholder if none at all)
        return extra or [self]

    @api.depends('list_price', 'so_weight_carat', 'so_price_per_carat')
    def _compute_so_total_price(self):
        for p in self:
            if p.so_price_per_carat and p.so_weight_carat:
                p.so_total_price = p.so_price_per_carat * p.so_weight_carat
            else:
                p.so_total_price = p.list_price
