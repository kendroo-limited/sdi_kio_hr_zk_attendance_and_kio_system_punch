from odoo import models, fields

class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    check_in_lat = fields.Float("Check-in Latitude", readonly=True)
    check_in_long = fields.Float("Check-in Longitude", readonly=True)
    check_in_address = fields.Text("Check-in Address", readonly=True)

    check_out_lat = fields.Float("Check-out Latitude", readonly=True)
    check_out_long = fields.Float("Check-out Longitude", readonly=True)
    check_out_address = fields.Text("Check-out Address", readonly=True)

    browser = fields.Char("Browser", readonly=True)
    os_name = fields.Char("Operating System", readonly=True)
