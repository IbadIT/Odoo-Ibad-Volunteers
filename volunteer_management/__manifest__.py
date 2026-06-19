{
    'name': "Volunteer Management",
    'summary': """Managing Volunteer Data""",
    'description': """Managing Volunteer Data""",
    'author': "",
    'category': '',
    'license': 'LGPL-3',
    'version': '17.0.0.0.2',
    'depends': ['contacts'],
    'data': [
        'security/ir.model.access.csv',
        'data/governorate.xml',
        'data/district.xml',
        'data/volunteer_section.xml',
        'data/volunteer_section_detail.xml',
        'data/volunteer_identification_method.xml',
        'views/res_partner.xml',
        'views/volunteer.xml',
        'views/department.xml',
        'data/volunteer_nationality.xml',
        'views/task.xml',
        'views/volunteer_task_report_wizard_view.xml',
        'views/certification.xml'
    ],

    'assets': {
        'web.assets_backend': [
            'volunteer_management/static/src/custom_styles.scss',
        ],
    },
}
