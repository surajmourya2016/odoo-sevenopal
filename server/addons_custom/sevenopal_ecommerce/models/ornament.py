from odoo import models, fields


class SevenopalOrnament(models.Model):
    _name = 'sevenopal.ornament'
    _description = 'Ornament Type (Ring / Pendant / etc.)'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    image = fields.Image(max_width=256, max_height=256)
    tax_percentage = fields.Float(default=0.0)
    sequence = fields.Integer(default=10)
    enable_metal_option = fields.Boolean(default=False)
    enable_design_option = fields.Boolean(default=False)
    enable_ring_sizer = fields.Boolean(default=False)
    active = fields.Boolean(default=True)

    metal_option_ids = fields.One2many(
        'sevenopal.metal.option', 'ornament_id', string='Metal Options'
    )
    metal_design_ids = fields.One2many(
        'sevenopal.metal.design', 'ornament_id', string='Metal Designs'
    )
