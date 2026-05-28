from odoo import models, fields


class SevenopalMetalDesign(models.Model):
    _name = 'sevenopal.metal.design'
    _description = 'Metal Design'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    price = fields.Float(default=0.0)
    description = fields.Char()
    image = fields.Image(max_width=256, max_height=256)
    metal_option_id = fields.Many2one('sevenopal.metal.option', ondelete='cascade')
    ornament_id = fields.Many2one('sevenopal.ornament', ondelete='cascade')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
