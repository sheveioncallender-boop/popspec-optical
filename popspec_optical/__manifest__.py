{
    'name': 'Pop Spec Optical Operations',
    'version': '19.0.1.1.0',
    'summary': 'Patient prescriptions, serial-linked spectacle jobs and controlled dispensing',
    'author': 'Spxcorp Limited',
    'website': 'https://popspecltd.spxcorp.site',
    'license': 'LGPL-3',
    'category': 'Sales',
    'depends': ['sale_stock', 'purchase_stock', 'stock_landed_costs', 'hr', 'mail', 'utm'],
    'data': [
        'security/groups.xml', 'security/ir.model.access.csv', 'security/rules.xml',
        'data/sequences.xml', 'data/sop.xml',
        'views/clinical.xml', 'views/operations.xml', 'views/native.xml',
        'wizard/scan.xml', 'report/reports.xml', 'report/operational_reports.xml',
        'views/usability.xml', 'views/menus.xml',
    ],
    'application': True,
    'installable': True,
}
