{
    'name': 'KIO Biometric Device Integration',
    'version': '17.0.1.0.3',
    'author': 'Ibrahim Khalil Ullah',
    'summary': """Biometric Device Integration With HR Attendance (Face + Thumb). """,
    'description': 'This module integrates Odoo HR Attendance with the ZK biometric devices. It allowes first punch check-in and all other punches of a day is check-out. Also have day end auto check-out system and error device mailing notification system.',
    'category': 'Human Resources',
    'company': 'DSL',
    'website': "https://daffodilsoft.com",
    'depends': ['base','base_setup', 'hr_attendance'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/zk_machine_view.xml',
        'views/zk_machine_attendance_view.xml',
        'views/hr_employee_fingerprint_views.xml',
        'data/download_data.xml'
    ],
    'license': "AGPL-3",
    'installable': True,
    'auto_install': False,
    'application': False,
    'contributors': [
        'Rasel Ali', 'Imran Chowdhury'
    ]
}
