from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _cart_update(self, product_id, line_id=None, add_qty=0, set_qty=0, **kwargs):
        values = super()._cart_update(
            product_id, line_id=line_id, add_qty=add_qty, set_qty=set_qty, **kwargs
        )

        line = self.env['sale.order.line'].browse(values.get('line_id'))
        if not line:
            return values

        certificate_id = kwargs.get('so_certificate_id')
        ornament_id = kwargs.get('so_ornament_id')
        metal_option_id = kwargs.get('so_metal_option_id')
        metal_design_id = kwargs.get('so_metal_design_id')
        ring_size = kwargs.get('so_ring_size')
        ring_size_system = kwargs.get('so_ring_size_system')

        update_vals = {}

        if certificate_id:
            cert = self.env['sevenopal.certificate'].browse(int(certificate_id))
            if cert.exists():
                update_vals['so_certificate_id'] = cert.id
                update_vals['so_certificate_charge'] = cert.charge if cert.cert_type == 'paid' else 0.0
                line.price_unit = line.price_unit + update_vals['so_certificate_charge']

        if ornament_id:
            update_vals['so_ornament_id'] = int(ornament_id)

        if metal_option_id:
            update_vals['so_metal_option_id'] = int(metal_option_id)

        if metal_design_id:
            design = self.env['sevenopal.metal.design'].browse(int(metal_design_id))
            if design.exists():
                update_vals['so_metal_design_id'] = design.id
                update_vals['so_metal_design_price'] = design.price
                line.price_unit = line.price_unit + design.price

        if ring_size:
            update_vals['so_ring_size'] = ring_size

        if ring_size_system:
            update_vals['so_ring_size_system'] = ring_size_system

        if update_vals:
            line.write(update_vals)

        return values
