from odoo import models, fields


class SevenopalRingSizer(models.Model):
    _name = 'sevenopal.ring.sizer'
    _description = 'Ring Sizer'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    price = fields.Float(default=0.0)
    description = fields.Char()
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
