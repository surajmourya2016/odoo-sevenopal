from odoo import models, fields


class SevenopalCertificate(models.Model):
    _name = 'sevenopal.certificate'
    _description = 'Certificate Option'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    cert_type = fields.Selection(
        [('free', 'Free'), ('paid', 'Paid')],
        string='Type',
        required=True,
        default='free',
    )
    charge = fields.Float(default=0.0)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    def name_get(self):
        result = []
        for rec in self:
            if rec.cert_type == 'paid' and rec.charge:
                label = f"{rec.name} (+₹{rec.charge:.0f})"
            else:
                label = f"{rec.name} (Free)"
            result.append((rec.id, label))
        return result
