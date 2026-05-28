from odoo import models, fields, api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    so_certificate_id = fields.Many2one('sevenopal.certificate', string='Certificate')
    so_certificate_charge = fields.Float('Certificate Charge', default=0.0)
    so_ornament_id = fields.Many2one('sevenopal.ornament', string='Ornament')
    so_metal_option_id = fields.Many2one('sevenopal.metal.option', string='Metal')
    so_metal_design_id = fields.Many2one('sevenopal.metal.design', string='Design')
    so_metal_design_price = fields.Float('Design Price', default=0.0)
    so_ring_size = fields.Char('Ring Size')
    so_ring_size_system = fields.Char('Ring Size System')

    @api.depends('so_certificate_charge', 'so_metal_design_price')
    def _compute_extra_charge(self):
        for line in self:
            line.so_extra_charge = line.so_certificate_charge + line.so_metal_design_price

    so_extra_charge = fields.Float(
        'Extra Charges',
        compute='_compute_extra_charge',
        store=True,
    )
