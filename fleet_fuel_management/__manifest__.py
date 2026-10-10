{
    'name': "Fleet Fuel Management",
    'summary': "Fuel refills for vehicles and electric generators",
    'description': """
Fuel refill logs for fleet vehicles and electric generators.
Vehicles: full-to-full consumption (L/100km) and an abnormal-consumption flag.
Generators: refill and cost tracking only.
""",
    'author': "",
    'category': 'Human Resources/Fleet',
    'version': '17.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['fleet'],
    'data': [
        'security/ir.model.access.csv',
        'security/fuel_security.xml',
        'views/fleet_vehicle_log_fuel_views.xml',
        'views/fleet_vehicle_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
}
