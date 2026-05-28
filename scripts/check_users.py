users = env['res.users'].sudo().search([('share', '=', False)], limit=10)
for u in users:
    print(u.id, repr(u.login), repr(u.name))
