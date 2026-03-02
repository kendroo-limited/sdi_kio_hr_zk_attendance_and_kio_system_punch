{
    'name': "KIO System Punch",
    'version': '17.0.1.0.4',
    'author': 'Daffodil Software Limited',
    'summary': """Accept multiple punch and connect with zk machine""",
    'description': """Accept multiple punch and connect with zk machine""",
    'category': 'Human Resources',
    'company': 'DSL',
    'website': "https://daffodilsoft.com",
    'depends': ['base', 'web', 'hr', 'hr_attendance', 'kio_hr_zk_attendance'],
    'external_dependencies': {
        'python': ['pandas'],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'kio_system_punch/static/src/css/attendance_dashboard.css',
            'kio_system_punch/static/src/js/attendance_dashboard.js',
            'kio_system_punch/static/src/xml/attendance_dashboard.xml',
        ],
    },
    # 'images': ["static/description/banner.gif"],
    'license': "AGPL-3",
    'installable': True,
    'application': True,
    'contributors': [
        'Ibrahim Khalil Ullah',
        'Md Azharul amin Mulla <https://github.com/azharul77>',
        'Rasel Ali'
    ]
}
