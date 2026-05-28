from odoo import models, fields


class SevenopalMetalOption(models.Model):
    _name = 'sevenopal.metal.option'
    _description = 'Metal Option'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    description = fields.Char()
    ornament_id = fields.Many2one('sevenopal.ornament', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    design_ids = fields.One2many(
        'sevenopal.metal.design', 'metal_option_id', string='Designs'
    )
