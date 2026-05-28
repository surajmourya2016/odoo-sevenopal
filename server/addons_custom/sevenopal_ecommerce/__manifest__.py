{
    'name': 'SevenOpal Ecommerce',
    'version': '19.0.1.0.0',
    'category': 'Website/eCommerce',
    'summary': 'Certification, Ornament (Ring/Pendant), Metal Options for opal products',
    'author': 'Digimonk',
    'depends': ['website_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/certificate_views.xml',
        'views/ornament_views.xml',
        'views/product_views.xml',
        'views/menu_views.xml',
        'views/frontend_templates.xml',
        'views/homepage_templates.xml',
        'views/layout_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'sevenopal_ecommerce/static/src/css/sevenopal_theme.css',
            'sevenopal_ecommerce/static/src/js/product_configurator.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
