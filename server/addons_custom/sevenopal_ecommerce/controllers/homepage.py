from odoo import http
from odoo.http import request


class SevenopalHomepage(http.Controller):

    @http.route('/', type='http', auth='public', website=True, sitemap=True)
    def homepage(self, **kwargs):
        """Serve the SevenOpal branded homepage with categories and product collections."""
        website = request.website
        base_domain = [
            ('is_published', '=', True),
            ('website_id', 'in', [False, website.id]),
        ]

        categories = request.env['product.public.category'].sudo().search(
            [('website_id', 'in', [False, website.id]), ('parent_id', '=', False)],
            order='sequence, name',
            limit=12,
        )
        featured = request.env['product.template'].sudo().search(
            base_domain, order='website_sequence, id', limit=8,
        )
        fire_opal = request.env['product.template'].sudo().search(
            base_domain + [('so_is_fire_opal', '=', True)],
            order='website_sequence, id', limit=8,
        )
        calibrated = request.env['product.template'].sudo().search(
            base_domain + [('so_is_calibrated_opal', '=', True)],
            order='website_sequence, id', limit=8,
        )
        jewellery = request.env['product.template'].sudo().search(
            base_domain + [('so_is_jewellery', '=', True)],
            order='website_sequence, id', limit=6,
        )
        new_arrivals = request.env['product.template'].sudo().search(
            base_domain + [('so_is_new_arrival', '=', True)],
            order='website_sequence, id', limit=8,
        )

        return request.render('sevenopal_ecommerce.sevenopal_homepage', {
            'so_categories':    categories,
            'so_featured_products': featured,
            'so_fire_opal':     fire_opal,
            'so_calibrated':    calibrated,
            'so_jewellery':     jewellery,
            'so_new_arrivals':  new_arrivals,
        })
