import json
from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


class SevenopalShop(WebsiteSale):
    """Extend the website_sale shop to support carat/ratti weight filtering."""

    def _get_search_domain(self, search, category, attrib_values, search_in_description=True):
        domain = super()._get_search_domain(search, category, attrib_values, search_in_description)
        params = request.params

        min_carat = params.get('min_carat')
        max_carat = params.get('max_carat')
        min_ratti = params.get('min_ratti')
        max_ratti = params.get('max_ratti')

        try:
            if min_carat:
                domain.append(('so_weight_carat', '>=', float(min_carat)))
            if max_carat:
                domain.append(('so_weight_carat', '<=', float(max_carat)))
            if min_ratti:
                domain.append(('so_weight_ratti', '>=', float(min_ratti)))
            if max_ratti:
                domain.append(('so_weight_ratti', '<=', float(max_ratti)))
        except (ValueError, TypeError):
            pass

        return domain


class SevenopalController(http.Controller):
    """API endpoints for SevenOpal ecommerce features."""

    @http.route(
        '/sevenopal/designs/<int:metal_option_id>',
        type='http',
        auth='public',
        website=True,
        methods=['GET'],
    )
    def get_designs(self, metal_option_id, **kwargs):
        """Return JSON list of active metal designs for the given metal option."""
        domain = [('metal_option_id', '=', metal_option_id), ('active', '=', True)]
        ornament_id = kwargs.get('ornament_id')
        if ornament_id:
            try:
                domain.append(('ornament_id', '=', int(ornament_id)))
            except (TypeError, ValueError):
                pass
        designs = request.env['sevenopal.metal.design'].sudo().search(
            domain,
            order='sequence, id',
        )
        result = [
            {
                'id': d.id,
                'name': d.name,
                'description': d.description or '',
                'price': d.price,
                'image': bool(d.image),
            }
            for d in designs
        ]
        return request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')],
        )

    @http.route(
        '/sevenopal/update_line_by_product',
        type='jsonrpc',
        auth='public',
        website=True,
        methods=['POST'],
    )
    def update_line_by_product(
        self,
        product_template_id,
        certificate_id=None,
        certificate_charge=0,
        ornament_id=None,
        metal_option_id=None,
        metal_design_id=None,
        metal_design_price=0,
        ring_size=None,
        ring_size_system=None,
        **kwargs,
    ):
        """Called after add-to-cart via add_to_cart_event.
        Finds the most recently added line for the product and writes SevenOpal options."""
        order = request.cart
        if not order:
            return {'error': 'No active cart'}

        line = order.order_line.filtered(
            lambda l: l.product_id.product_tmpl_id.id == int(product_template_id)
        ).sorted(key=lambda l: l.id, reverse=True)[:1]

        if not line:
            return {'error': 'Line not found'}

        return self._write_sevenopal_options(
            line,
            certificate_id=certificate_id,
            ornament_id=ornament_id,
            metal_option_id=metal_option_id,
            metal_design_id=metal_design_id,
            ring_size=ring_size,
            ring_size_system=ring_size_system,
        )

    @http.route(
        '/sevenopal/update_line',
        type='jsonrpc',
        auth='public',
        website=True,
        methods=['POST'],
    )
    def update_line_options(
        self,
        line_id,
        certificate_id=None,
        ornament_id=None,
        metal_option_id=None,
        metal_design_id=None,
        ring_size=None,
        ring_size_system=None,
        **kwargs,
    ):
        """Called by frontend JS after product is added to cart.

        Updates the order line with SevenOpal-specific options and adjusts the
        price to include certificate / metal design extra charges.
        """
        order = request.cart
        if not order:
            return {'error': 'No active cart'}

        line = order.order_line.filtered(lambda l: l.id == int(line_id))
        if not line:
            return {'error': 'Line not found'}

        return self._write_sevenopal_options(
            line,
            certificate_id=certificate_id,
            ornament_id=ornament_id,
            metal_option_id=metal_option_id,
            metal_design_id=metal_design_id,
            ring_size=ring_size,
            ring_size_system=ring_size_system,
        )

    # ── Shared helper ─────────────────────────────────────────────────────────

    def _write_sevenopal_options(
        self, line,
        certificate_id=None, ornament_id=None,
        metal_option_id=None, metal_design_id=None,
        ring_size=None, ring_size_system=None,
    ):
        Certificate = request.env['sevenopal.certificate'].sudo()
        Design      = request.env['sevenopal.metal.design'].sudo()

        vals        = {}
        extra_price = 0.0

        if certificate_id:
            cert = Certificate.browse(int(certificate_id)).exists()
            if cert:
                vals['so_certificate_id']     = cert.id
                charge = cert.charge if cert.cert_type == 'paid' else 0.0
                vals['so_certificate_charge'] = charge
                extra_price += charge

        if ornament_id:
            vals['so_ornament_id'] = int(ornament_id)

        if metal_option_id:
            vals['so_metal_option_id'] = int(metal_option_id)

        if metal_design_id:
            design = Design.browse(int(metal_design_id)).exists()
            if design:
                vals['so_metal_design_id']    = design.id
                vals['so_metal_design_price'] = design.price
                extra_price += design.price

        if ring_size:
            vals['so_ring_size'] = ring_size

        if ring_size_system:
            vals['so_ring_size_system'] = ring_size_system

        if vals:
            if extra_price:
                vals['price_unit'] = line.price_unit + extra_price
            line.sudo().write(vals)

        return {'success': True, 'line_id': line.id, 'extra_price': extra_price}
