# -*- coding: utf-8 -*-
#Author: Ibrahim Khalil Ullah ######
from odoo import tools
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

from . import zklib
from .zkconst import *
from struct import unpack
from odoo import api, fields, models
from odoo import _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, time, timedelta,date
from collections import defaultdict
from odoo import models, api, exceptions, _
from odoo.tools import format_datetime
from zk import ZK, const
import logging

_logger = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = 'res.company'
    
    employee_ids = fields.Many2many('hr.employee', 'company_employee_rel', 'company_id', 'employee_id', string='HR Employees for Attendance', help="HR employees linked to the company")



class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    device_id = fields.Char(string='Biometric Device ID', help="Give the biometric device id")
    device_password = fields.Char(string='Device Password', help="Password for the employee in the biometric device.")
    device_card_id = fields.Integer(string='Device Card ID', help="Card number for the employee in the biometric device.")
    # delete_mark_user = fields.Boolean(
    #     string="Delete Marked User from machine",
    #     default=False,
    #     help="If enabled, the user will be deleted from the biometric device."
    # )
    
    _sql_constraints = [
        ('unique_device_id', 'unique(device_id)', 'Biometric Device ID must be unique!'),
    ]
    
    @api.onchange('employee_id')
    def onchange_employee_id(self):
        if self.employee_id:
            self.device_id = str(self.employee_id)


    def action_remove_user_from_device(self):
        """
        Removes the specific user from the biometric machine.
        Ensures the function is executed on the correct `zk.machine` record.
        """
        if not self.device_id:
            raise UserError(_("This employee does not have a valid Device ID associated with the biometric machine."))

        devices = self.env['zk.machine'].search([])
        if not devices:
            raise UserError(_("No biometric devices are configured. Please check the setup."))

        for device in devices:
            try:
                device.remove_specific_user_from_machine(user_id=self.device_id, employee_name=self.name)
            except Exception as e:
                raise UserError(_('Error removing user %s from device %s: %s') % (self.name, device.name, str(e)))

        return {'type': 'ir.actions.client', 'tag': 'reload'}


 
class ZkMachine(models.Model):
    _name = 'zk.machine.attendance'
    _inherit = 'hr.attendance'

    @api.constrains('check_in', 'check_out', 'employee_id')
    def _check_validity(self):
        """overriding the __check_validity function for employee attendance."""
        pass

    device_id = fields.Char(string='Biometric Device ID', help="Biometric device id")
    punch_type = fields.Selection([('0', 'Check In'),
                                   ('1', 'Check Out'),
                                   ('255', 'Check In / Check Out'),
                                   ('2', 'Break Out'),
                                   ('3', 'Break In'),
                                   ('4', 'Overtime In'),
                                   ('5', 'Overtime Out')],
                                  string='Punching Type')

    attendance_type = fields.Selection([('1', 'Finger'),
                                        ('16', 'Face'),
                                        ('25', 'Palm'),
                                        ('2', 'Type_2'),
                                        ('3', 'Password'),
                                        ('4', 'Card')], string='Category', help="Select the attendance type")
    punching_time = fields.Datetime(string='Punching Time', help="Give the punching time")
    address_id = fields.Char(string='Device Address', help="Address")



class ReportZkDevice(models.Model):
    _name = 'zk.report.daily.attendance'
    _auto = False
    _order = 'punching_day desc'

    name = fields.Many2one('hr.employee', string='Employee', help="Employee")
    punching_day = fields.Datetime(string='Download Time', help="Punching Date/Time")
    address_id = fields.Char(string='Device Address', help="Address")
    attendance_type = fields.Selection([('1', 'Finger'),
                                        ('15', 'Face'),
                                        ('25', 'Palm'),
                                        ('2', 'Type_2'),
                                        ('3', 'Password'),
                                        ('4', 'Card')],
                                       string='Category', help="Select the attendance type")
    punch_type = fields.Selection([('0', 'Check In'),
                                   ('1', 'Check Out'),
                                   ('255', 'Check In / Check Out'),
                                   ('2', 'Break Out'),
                                   ('3', 'Break In'),
                                   ('4', 'Overtime In'),
                                   ('5', 'Overtime Out')], string='Punching Type', help="Select the punch type")
    punching_time = fields.Datetime(string='Punching Time', help="Punching Time")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id)


    def init(self):
        tools.drop_view_if_exists(self._cr, 'zk_report_daily_attendance')
        query = """
            create or replace view zk_report_daily_attendance as (
                select
                    min(z.id) as id,
                    z.employee_id as name,
                    z.write_date as punching_day,
                    z.address_id as address_id,
                    z.company_id as company_id,
                    z.attendance_type as attendance_type,
                    z.punching_time as punching_time,
                    z.punch_type as punch_type
                from zk_machine_attendance z
                    join hr_employee e on (z.employee_id=e.id)
                GROUP BY
                    z.employee_id,
                    z.write_date,
                    z.address_id,
                    z.attendance_type,
                    z.punch_type,
                    z.company_id,
                    z.punching_time
            )
        """
        self._cr.execute(query)


class HrEmployeeFingerprint(models.Model):
    _name = "hr.employee.fingerprint"
    _description = "Employee Fingerprint Data"
    
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True, ondelete="cascade")
    machine_id = fields.Many2one("zk.machine", string="Biometric Machine", required=True, ondelete="cascade")
    device_id = fields.Char(string="Biometric Device ID", related="employee_id.device_id", store=True, readonly=True)
    finger_id = fields.Integer(string="Finger ID", required=True)
    template_data = fields.Text(string="Fingerprint Template", required=True)
    valid = fields.Boolean(string="Valid", default=True)

    _sql_constraints = [
        ("unique_employee_finger", "unique(employee_id, finger_id)", "Each finger must be unique per employee!")
    ]


    def name_get(self):
        result = []
        for record in self:
            device_id = record.device_id or "Unknown"
            employee_name = record.employee_id.name or "No Employee"
            display_name = f"[{device_id}] {employee_name}"
            result.append((record.id, display_name))
        return result



