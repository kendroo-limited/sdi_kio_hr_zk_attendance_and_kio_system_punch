import pytz
import sys
import datetime
import logging
import binascii

from . import zklib
from .zkconst import *
from struct import unpack
from odoo import api, fields, models
from odoo import _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, time, timedelta,date
from collections import defaultdict
from odoo import models, api, exceptions, _
from datetime import datetime
from odoo.tools import format_datetime
from pytz import timezone, utc
from odoo.exceptions import UserError
from operator import itemgetter
from collections import defaultdict
from zk.finger import Finger



_logger = logging.getLogger(__name__)
try:
    from zk import ZK, const
except ImportError:
    _logger.error("Please Install pyzk library.")

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    device_id = fields.Char(string='Biometric Device ID')
    device_no = fields.Char(string='Device No')
    address_id = fields.Char(string='Device Address', help="Address")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id)
    total_punches = fields.Integer(string='Total Check Outs', default='0')
    checked_out = fields.Boolean(default=False, string='Checked Out')
    check_in_location = fields.Selection([
        ('system', 'System'),
        ('attendance_device', 'Biometric'),
        ('auto', 'Auto')
    ], string='Check In Type')
    check_out_location = fields.Selection([
        ('system', 'System'),
        ('attendance_device', 'Biometric'),
        ('auto', 'Auto')
    ], string='Check Out Type')


    # @api.depends('check_in_location')
    # def _compute_check_out_location(self):
    #     for record in self:
    #         if record.check_in_location == 'system':
    #             record.check_out_location = 'system'
    #         elif record.check_in_location == 'attendance_device':
    #             record.check_out_location = 'attendance_device'
    #         else:
    #             record.check_out_location = ''
            

    @api.constrains('check_in', 'check_out', 'employee_id')
    def _check_validity(self):
        _logger.info("Custom validity check is executed...................................................")

        """ Custom validity check without specific conditions causing validation errors. """
        for attendance in self:
            last_attendance_before_check_in = self.env['hr.attendance'].search([
                ('employee_id', '=', attendance.employee_id.id),
                ('check_in', '<=', attendance.check_in),
                ('id', '!=', attendance.id),
            ], order='check_in desc', limit=1)
            if last_attendance_before_check_in and last_attendance_before_check_in.check_out and last_attendance_before_check_in.check_out > attendance.check_in:
                continue

            if not attendance.check_out:
                # if our attendance is "open" (no check_out), we verify there is no other "open" attendance
                no_check_out_attendances = self.env['hr.attendance'].search([
                    ('employee_id', '=', attendance.employee_id.id),
                    ('check_out', '=', False),
                    ('id', '!=', attendance.id),
                ], order='check_in desc', limit=1)
                if no_check_out_attendances:
                    continue
            else:
                # we verify that the latest attendance with check_in time before our check_out time
                # is the same as the one before our check_in time computed before, otherwise it overlaps
                last_attendance_before_check_out = self.env['hr.attendance'].search([
                    ('employee_id', '=', attendance.employee_id.id),
                    ('check_in', '<', attendance.check_out),
                    ('id', '!=', attendance.id),
                ], order='check_in desc', limit=1)
                if last_attendance_before_check_out and last_attendance_before_check_in != last_attendance_before_check_out:
                    continue
        

    @api.constrains('check_in', 'check_out')
    def _check_validity_check_in_check_out(self):
        """ verifies if check_in is earlier than check_out. """
        for attendance in self:
            if attendance.check_in and attendance.check_out:
                if attendance.check_out < attendance.check_in:
                 continue        
    
    def auto_checkout_employees(self):
        employees_to_checkout = self.search([
            ('checked_out', '=', False),  # Employee should not be checked out
            ('check_out', '=', False),    # Employee should not have a checkout timestamp
            ('check_in', '!=', False),    # Employee should have checked in (non-empty check_in field)
        ])
    
        # Initialize employees_data inside the loop
        employees_data = []
        for employee in employees_to_checkout: 
            employee.write({'checked_out': True, 'check_out': fields.Datetime.now()})
            employee.write({'check_out_location': 'auto'})
            
            employees_data.append({
                'name': employee.employee_id.name if hasattr(employee, 'employee_id') and hasattr(employee.employee_id, 'name') else 'Unknown Employee',
                'work_email': employee.employee_id.work_email if hasattr(employee.employee_id, 'work_email') else 'Unknown Email',
            })
            
            self.send_checkout_reminder_email_to_employee(employee)

        if employees_data:
            self.send_checkout_reminder_email_to_hr(employees_data)
        
        return True


    

    def send_checkout_reminder_email_to_employee(self, employee):
        company_email = self.env.user.company_id.email
        subject_employee = "Checkout Reminder"
        body_employee = f"Dear {employee.employee_id.name if hasattr(employee, 'employee_id') and hasattr(employee.employee_id, 'name') else 'Employee'},\n\n"

        body_employee += "You have forgotten to check out from the biometric device today.\n\n"
        body_employee += "Please ensure you have checked out before leaving the premises.\n\n"
        body_employee += "Best regards,\nThe HR Team"

        # Send email to employee
        self.env['mail.mail'].create({
            'subject': subject_employee,
            'body_html': body_employee,
            'email_from': company_email,
            'email_to': employee.employee_id.work_email,
            'auto_delete': True,
        }).send()

        return True

    def send_checkout_reminder_email_to_hr(self, employees_data):
        
        hr_emails = self.env.user.company_id.employee_ids.mapped('work_email')
        company_email = self.env.user.company_id.email
        # Prepare email content for HR with HTML table
        subject_hr = "Employee Checkout Reminder"
        body_hr = """<p>Dear HR Team,</p>
                    <p>Below is a list of employees who have not checked out from the biometric device today:</p>
                    <table style="border-collapse: collapse; width: 100%;">
                        <tr>
                            <th style="border: 1px solid #dddddd; text-align: left; padding: 8px;">Employee Name</th>
                            <th style="border: 1px solid #dddddd; text-align: left; padding: 8px;">Email</th>
                        </tr>
                    """

        for employee_info in employees_data:
            body_hr += f"""<tr>
                            <td style="border: 1px solid #dddddd; text-align: left; padding: 8px;">{employee_info["name"]}</td>
                            <td style="border: 1px solid #dddddd; text-align: left; padding: 8px;">{employee_info["work_email"]}</td>
                        </tr>
                        """

        body_hr += """</table>
                    <p>Please take appropriate action to ensure the employees check out.</p> \n\n
                    
                """

        # Send email to HR
        self.env['mail.mail'].create({
            'subject': subject_hr,
            'body_html': body_hr,
            'email_from': company_email,
            'email_to': ', '.join(hr_emails),
            'auto_delete': True,
        }).send()
        
        return True
            
class ZkMachine(models.Model):
    _name = 'zk.machine'
    _inherit = 'hr.attendance'
    _rec_name = "machine_name"

    name = fields.Char(string='Machine IP', required=True)
    device_no = fields.Char(string='Device No')
    machine_name = fields.Char(string='Machine Name' , required=True)
    port_no = fields.Integer(string='Port No', required=True, default=4370)
    address_id = fields.Char(string='Device Address', related='company_id.partner_id.street', help="Address", readonly=False)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id)
    attendance_id = fields.Many2one('hr.attendance', string='Attendane')
    active= fields.Boolean(string = 'Activate Status', default = True)
    model_id= fields.Char(string = "Model")
    tz = fields.Selection('_tz_get', string='Time zone', default=lambda self: self.env.context.get('tz') or self.env.user.tz)
    protocol = fields.Selection([('udp', 'UDP'), ('tcp', 'TCP')], string='Protocol', required=True, default='tcp',
                                tracking=True,
                                help="Some old devices do not support TCP. In such the case, please try on switching to UDP.")

    current_time = fields.Datetime(string="Current Time", compute="_compute_current_time", store=False, readonly=True)
    fingerprint_ids = fields.One2many("hr.employee.fingerprint", "machine_id", string="Fingerprints")

    @api.depends('machine_name', 'name')
    def name_get(self):
        """ Display records as 'Machine Name [Machine IP]' """
        result = []
        for record in self:
            machine_name = record.machine_name or "Unnamed Machine"
            machine_ip = record.name or "Unknown IP"
            display_name = f"{machine_name} [{machine_ip}]"
            result.append((record.id, display_name))
        return result


    @api.model
    def _tz_get(self):
            """Returns all available time zones"""
            return [(tz, tz) for tz in pytz.all_timezones]

    @api.depends('tz')
    def _compute_current_time(self):
        """
        Stores the current time in UTC but as a naive datetime (no timezone info).
        """
        for record in self:
            # Get the current UTC time (timezone-aware)
            utc_now = datetime.now(pytz.utc)

            # Convert to naive datetime by removing timezone info
            naive_utc_now = utc_now.replace(tzinfo=None)

            # Store the naive UTC time (Odoo will automatically convert it when displayed)
            record.current_time = naive_utc_now


    

    @api.onchange('name')
    def onchange_device_no(self):
        if self.name:
            self.device_no = str(self.name)

    def device_connect(self, zk):
        try:
            conn = zk.connect()
            return conn
        except:
            return False




    def clear_attendance(self):
        for info in self:
            try:
                machine_ip = info.name
                zk_port = info.port_no
                timeout = 30
                
                try:
                    zk = ZK(machine_ip, port=zk_port, timeout=timeout, password=0, force_udp=False, ommit_ping=False)
                except NameError:
                    raise UserError(_("Please install it with 'pip3 install pyzk'."))
                    
                conn = self.device_connect(zk)
                
                if conn:
                    conn.enable_device()
                    clear_data = zk.get_attendance()
                    
                    if clear_data:
                        conn.clear_attendance()
                        self._cr.execute("""delete from zk_machine_attendance""")
                        conn.disconnect()
                        return {'success': True, 'message': _('Attendance Records Deleted.')}
                    else:
                        raise UserError(_('Unable to clear Attendance log. Are you sure attendance log is not empty.'))
                else:
                    raise UserError(_('Unable to connect to Attendance Device. Please use Test Connection button to verify.'))
            
            except Exception as e:
                raise ValidationError('Unable to clear Attendance log. Error: %s' % str(e))


    def fetch_fingerprints_from_machine(self):
        """Retrieve fingerprints from the biometric device and store them in Odoo."""
        for info in self:
            machine_ip = info.name
            zk_port = info.port_no
            timeout = 15

            try:
                # Initialize the ZK instance
                zk = ZK(machine_ip, port=zk_port, timeout=timeout, password=0, force_udp=False, ommit_ping=False)
                conn = zk.connect()

                if not conn:
                    raise UserError(_("Cannot connect to the biometric machine."))

                templates = conn.get_templates()
                
                if not templates:
                    _logger.warning("No fingerprint templates found on the device.")
                    raise UserError(_("No fingerprint templates found on the device."))

                for template in templates:
                    _logger.info(f"Fetched template: UID={template.uid}, FingerID={template.fid}, Size={template.size}")

                    employee = self.env['hr.employee'].search([('device_id', '=', template.uid)], limit=1)

                    if not employee:
                        _logger.warning(f"No employee found for UID {template.uid}, skipping...")
                        continue

                    # Check if fingerprint already exists
                    existing_fp = self.env['hr.employee.fingerprint'].search([
                        ('employee_id', '=', employee.id),
                        ('finger_id', '=', template.fid)
                    ])

                    # Ensure template is stored as a **hex string**.
                    template_data_hex = template.template.hex()

                    if not existing_fp:
                        self.env['hr.employee.fingerprint'].create({
                            'employee_id': employee.id,
                            'finger_id': template.fid,
                            'template_data': template_data_hex,
                            'device_id': employee.device_id,  
                            'valid': template.valid,
                            'machine_id': info.id
                        })
                        _logger.info(f"Fingerprint {template.fid} saved for employee {employee.name}.")

                conn.disconnect()

                return {
                    'effect': {
                        'fadeout': 'slow',
                        'message': _("Fingerprint data fetched successfully."),
                        'type': 'rainbow_man',
                    }
                }
            except Exception as e:
                _logger.error(f"Fetching fingerprint data failed: {str(e)}")
                raise UserError(_("Failed to fetch fingerprint data. Error: %s" % str(e)))



    def upload_fingerprint_data(self):
        """Uploads fingerprint templates to biometric machine."""
        for machine in self:
            machine_ip = machine.name
            zk_port = machine.port_no
            timeout = 15

            try:
                # Initialize the ZK instance
                zk = ZK(machine_ip, port=zk_port, timeout=timeout, password=0, force_udp=False, ommit_ping=False)
                conn = zk.connect()

                if not conn:
                    raise UserError(_("Cannot connect to the biometric machine."))

                # Retrieve fingerprint records from Odoo
                fingerprints = self.env['hr.employee.fingerprint'].search([('machine_id', '=', machine.id)])

                if not fingerprints:
                    raise UserError(_("No fingerprint data found to upload."))

                _logger.info(f"Starting fingerprint upload for {len(fingerprints)} entries...")

                for employee in self.env['hr.employee'].search([('device_id', '!=', False)]):
                    user_id = int(employee.device_id)  # Biometric user ID

                    # Fetch user from the biometric device
                    users = conn.get_users()
                    user = next((u for u in users if u.uid == user_id or u.user_id == str(user_id)), None)

                    if not user:
                        _logger.warning(f"User {employee.name} (UID: {user_id}) does not exist on the device, skipping...")
                        continue

                    # Get all fingerprints for the user
                    user_fingerprints = fingerprints.filtered(lambda fp: fp.employee_id == employee)

                    if not user_fingerprints:
                        _logger.warning(f"No fingerprints found for {employee.name}, skipping...")
                        continue

                    # Convert fingerprints to `Finger` objects
                    fingers = []
                    for fingerprint in user_fingerprints:
                        try:
                            # Attempt to decode fingerprint template correctly
                            template_data = fingerprint.template_data.strip()

                            try:
                                # Convert hexadecimal string to binary
                                template_binary = bytes.fromhex(template_data)
                            except binascii.Error:
                                _logger.error(f"Fingerprint {fingerprint.finger_id} contains invalid hex data! Skipping...")
                                continue  # Skip this fingerprint

                            fingers.append(Finger(
                                uid=user_id,
                                fid=fingerprint.finger_id,
                                valid=fingerprint.valid,
                                template=template_binary
                            ))

                            _logger.info(f"Prepared Finger ID {fingerprint.finger_id} (Size: {len(template_binary)} bytes)")
                        
                        except Exception as e:
                            _logger.error(f"Error processing fingerprint {fingerprint.finger_id}: {str(e)}")

                    try:
                        # Upload user with fingerprint templates
                        if fingers:
                            conn.save_user_template(user, fingers)
                            _logger.info(f"Uploaded {len(fingers)} fingerprints for employee {employee.name} (UID: {user_id})")
                    except Exception as e:
                        _logger.error(f"Failed to upload fingerprints for {employee.name}: {str(e)}")

                conn.disconnect()

                return {
                    'effect': {
                        'fadeout': 'slow',
                        'message': _("Fingerprint data uploaded successfully."),
                        'type': 'rainbow_man',
                    }
                }
            except Exception as e:
                _logger.error(f"Uploading fingerprint data failed: {str(e)}")
                raise UserError(_("Failed to upload fingerprint data. Error: %s" % str(e)))


    def remove_all_users_from_machine(self):
        """
        Removes all users from the biometric device.
        """
        for info in self:
            machine_ip = info.name
            zk_port = info.port_no
            timeout = 15

            try:
                # Initialize the ZK instance
                zk = ZK(machine_ip, port=zk_port, timeout=timeout, password=0, force_udp=False, ommit_ping=False)
            except NameError:
                raise UserError(_("Pyzk module not found. Please install it with 'pip3 install pyzk'."))

            _logger.info(f"Attempting to remove ALL users from device {machine_ip}")

            # Connect to the device
            conn = self.device_connect(zk)

            if conn:
                try:
                    conn.enable_device()  # Ensure the device is ready for operations

                    # Fetch all users from the device
                    users = conn.get_users()

                    if not users:
                        _logger.warning(f"No users found on device {machine_ip}.")
                        conn.disconnect()
                        return

                    # Loop through all users and delete each one
                    for user in users:
                        conn.delete_user(uid=user.uid, user_id=user.user_id)
                        _logger.info(f"Deleted user {user.name} (ID: {user.user_id}) from device {machine_ip}.")

                    _logger.info(f"Successfully removed all users from device {machine_ip}.")
                    conn.disconnect()
                except Exception as e:
                    conn.disconnect()
                    _logger.error(f"Failed to remove all users from device {machine_ip}: {str(e)}")
                    raise UserError(_('Error removing user %s from device %s: %s') % (user.name, machine_ip, str(e)))
            else:
                raise UserError(_('Unable to connect to the device. Please check the parameters and network connections.'))


    def remove_specific_user_from_machine(self, user_id=None, employee_name=None):
        """
        Removes a specific user from the biometric device by User ID.
        Ensures that only the intended user is deleted.
        """
        for info in self:
            # Ensure user_id and employee_name are available
            user_id = user_id or info.device_id
            employee_name = employee_name or info.name

            if not user_id or not employee_name:
                raise UserError(_("Missing parameters: 'user_id' and 'employee_name' are required."))

            machine_ip = info.name
            zk_port = info.port_no
            timeout = 15

            try:
                # Initialize the ZK instance
                zk = ZK(machine_ip, port=zk_port, timeout=timeout, password=0, force_udp=False, ommit_ping=False)
            except NameError:
                raise UserError(_("Pyzk module not found. Please install it with 'pip3 install pyzk'."))

            # Convert user ID to integer
            try:
                original_user_id = int(user_id)
            except ValueError:
                raise UserError(_("Invalid Device ID. It must be a valid number."))

            _logger.info(f"Attempting to remove user: ID {original_user_id}, Name: {employee_name}")

            # Connect to the device
            conn = self.device_connect(zk)

            if conn:
                try:
                    conn.enable_device()  # Ensure the device is ready for operations

                    # Fetch all users from the device
                    users = conn.get_users()

                    # Find the correct `uid` by matching `user_id`
                    target_user = next((user for user in users if user.user_id == str(original_user_id)), None)

                    if not target_user:
                        _logger.warning(f"User {employee_name} (ID: {original_user_id}) not found on device {machine_ip}. Skipping deletion.")
                        conn.disconnect()
                        return

                    # Delete the user using both `uid` and `user_id`
                    conn.delete_user(uid=target_user.uid, user_id=target_user.user_id)

                    _logger.info(f"Successfully removed user {employee_name} (ID: {original_user_id}) from device {machine_ip}.")
                    conn.disconnect()
                except Exception as e:
                    conn.disconnect()
                    _logger.error(f"Failed to remove user {employee_name} from device {machine_ip}: {str(e)}")
                    raise UserError(_('Error removing user %s from device: %s') % (employee_name, str(e)))
            else:
                raise UserError(_('Unable to connect to the device. Please check the parameters and network connections.'))

    def upload_employees(self):
            for info in self:
                machine_ip = info.name
                zk_port = info.port_no
                timeout = 15
                company_id = info.company_id.id

                try:
                    zk = ZK(machine_ip, port=zk_port, timeout=timeout, password=0, force_udp=False, ommit_ping=False)
                except NameError:
                    raise UserError(_("Pyzk module not found. Please install it with 'pip3 install pyzk'."))

                conn = self.device_connect(zk)

                if conn:
                    try:
                        # Filter employees by the company ID (company_id is related to the hr.employee model)
                        employees = self.env['hr.employee'].search([('device_id', '!=', False), ('company_id', '=', company_id)])

                        if not employees:
                            _logger.warning(f"No employees found for company {info.company_id.name}.")
                            raise UserError(_("No employees found for the selected company."))
                            
                        for employee in employees:
                            user_id = int(employee.device_id)
                            employee_name = employee.name.strip() if employee.name else 'Unknown'
                            password = employee.device_password.strip() if employee.device_password else '1'
                            privilege = const.USER_DEFAULT
                            card = int(employee.device_card_id) if employee.device_card_id else 0

                            _logger.info(f"Uploading user: {user_id}, Name: {employee_name}, Privilege: {privilege}, Password: {password}, Card: {card}")

                            try:
                                conn.set_user(uid=user_id, name=employee_name, privilege=privilege, password=password, card=card)
                                _logger.info(f"Successfully uploaded user {employee_name} to the device.")
                            except Exception as e:
                                _logger.error(f"Failed to upload user {employee_name}. Error: {str(e)}")
                                raise UserError(_('Error uploading user %s: %s') % (employee_name, str(e)))

                        conn.disconnect()
                        return {'success': True, 'message': _('Employees uploaded successfully to the attendance device.')}
                    except Exception as e:
                        conn.disconnect()
                        raise UserError(_('Error uploading employees to the device: %s') % str(e))
                else:
                    raise UserError(_('Unable to connect to the device. Please check the parameters and network connections.'))

            return {
                    'effect': {
                        'fadeout': 'slow',
                        'message': _("Employee uploaded successfully."),
                        'type': 'rainbow_man',
                    }
                }

    
    def restart_device(self):
        """
        Restarts the biometric device.
        """
        for info in self:
            machine_ip = info.name
            zk_port = info.port_no
            timeout = 15

            try:
                # Initialize the ZK instance
                zk = ZK(machine_ip, port=zk_port, timeout=timeout, password=0, force_udp=False, ommit_ping=False)
            except NameError:
                raise UserError(_("Pyzk module not found. Please install it with 'pip3 install pyzk'."))

            _logger.info(f"Attempting to restart the biometric device at {machine_ip}")

            # Connect to the device
            conn = self.device_connect(zk)

            if conn:
                try:
                    _logger.info(f"Restarting device {machine_ip}...")
                    conn.restart()
                    _logger.info(f"Device {machine_ip} restarted successfully.")

                    # Check if still connected before disconnecting
                    if conn.is_connect:
                        conn.disconnect()

                    return {'success': True, 'message': _('Device restarted successfully.')}

                except Exception as e:
                    _logger.error(f"Failed to restart device {machine_ip}: {str(e)}")
                    raise UserError(_('Error restarting device %s: %s') % (machine_ip, str(e)))

            else:
                raise UserError(_('Unable to connect to the device. Please check the parameters and network connections.'))


    def sync_device_time(self):
        """
        Synchronizes the biometric device time with the Odoo server's current time, adjusted for the selected timezone.
        """
        for info in self:
            machine_ip = info.name
            zk_port = info.port_no
            timeout = 15

            try:
                # Initialize the ZK instance
                zk = ZK(machine_ip, port=zk_port, timeout=timeout, password=0, force_udp=False, ommit_ping=False)
            except NameError:
                raise UserError(_("Pyzk module not found. Please install it with 'pip3 install pyzk'."))

            _logger.info(f"Attempting to sync time with biometric device at {machine_ip}")

            # Connect to the device
            conn = self.device_connect(zk)

            if conn:
                try:
                    # Get the computed current time from Odoo (stored in UTC)
                    current_time_utc = info.current_time

                    if not current_time_utc:
                        raise UserError(_("Current time is not available. Please ensure the field is computed properly."))

                    # Get the selected time zone (default to UTC if none selected)
                    tz_name = info.tz or "UTC"
                    tz = pytz.timezone(tz_name)

                    # Convert UTC time to the selected timezone
                    local_time = pytz.utc.localize(current_time_utc).astimezone(tz)

                    # Convert to naive datetime before sending to device
                    naive_local_time = local_time.replace(tzinfo=None)

                    _logger.info(f"Syncing time on device {machine_ip} to {naive_local_time} ({tz_name})...")

                    # Sync device time with the correct timezone
                    conn.set_time(naive_local_time)

                    _logger.info(f"Device {machine_ip} time synchronized successfully to {naive_local_time} ({tz_name}).")

                    # Disconnect only if still connected
                    if conn.is_connect:
                        conn.disconnect()

                    # ✅ Show success message with local time
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'type': 'success',
                            'title': _('Time Synchronized'),
                            'message': _('Device time synchronized successfully to %s (%s)' % (
                                naive_local_time.strftime('%Y-%m-%d %H:%M:%S'), tz_name
                            )),
                            'sticky': False,  # Notification disappears after a few seconds
                        }
                    }

                except Exception as e:
                    _logger.error(f"Failed to sync time on device {machine_ip}: {str(e)}")
                    raise UserError(_('Error syncing time on device %s: %s') % (machine_ip, str(e)))

            else:
                raise UserError(_('Unable to connect to the device. Please check the parameters and network connections.'))


    def getSizeUser(self, zk):
        """Checks a returned packet to see if it returned CMD_PREPARE_DATA,
        indicating that data packets are to be sent

        Returns the amount of bytes that are going to be sent"""
        command = unpack('HHHH', zk.data_recv[:8])[0]
        if command == CMD_PREPARE_DATA:
            size = unpack('I', zk.data_recv[8:12])[0]
            return size
        else:
            return False

    def zkgetuser(self, zk):
        """Start a connection with the time clock"""
        try:
            users = zk.get_users()
            return users
        except:
            return False

    @api.model
    def cron_download(self):
        machines = self.env['zk.machine'].search([])
        for machine in machines:
            machine.download_attendance()

            
    def check_device_connection(self):
        for machine in self:
            machine_ip = machine.name
            zk_port = machine.port_no
            timeout = 15

            try:
                zk = ZK(machine_ip, port=zk_port, timeout=timeout, password=0, force_udp=False, ommit_ping=False)
            except NameError:
                raise UserError(_("Pyzk module not found. Please install it with 'pip3 install pyzk'."))

            conn = self.device_connect(zk)

            if conn:
                raise UserError(_('Successfully connected to the device.'))
            else:
                raise UserError(_('Sorry, unable to connect to the device. Please check the parameters and network connections.'))



    def error_device_connection(self):
        disconnected_machines = []  # List to store disconnected machine details
        error_machines = self.env['zk.machine'].search([])

        for machine in error_machines:
            machine_ip = machine.name
            zk_port = machine.port_no
            timeout = 15

            try:
                zk = ZK(machine_ip, port=zk_port, timeout=timeout, password=0, force_udp=False, ommit_ping=False)
            except NameError:
                raise UserError(_("Pyzk module not found. Please install it with 'pip3 install pyzk'."))

            conn = self.device_connect(zk)

            if not conn:
                disconnected_machines.append(machine)

        if disconnected_machines:
            self.send_disconnected_machines_email(disconnected_machines)

        return True


    def send_disconnected_machines_email(self, disconnected_machines):
        company_email = self.env.user.company_id.email
        hr_emails = self.env.user.company_id.employee_ids.mapped('work_email')

        # Prepare email content
        subject = "Disconnected Machines Notification"
        body = """<p>Dear IT Team,</p>
                <p>The following attendance devices are not connected to the server:</p>
                <table style="border-collapse: collapse; width: 100%;">
                    <tr>
                        <th style="border: 1px solid #dddddd; text-align: left; padding: 8px;">Machine IP</th>
                        <th style="border: 1px solid #dddddd; text-align: left; padding: 8px;">Port No</th>
                        <th style="border: 1px solid #dddddd; text-align: left; padding: 8px;">Company</th>
                        <th style="border: 1px solid #dddddd; text-align: left; padding: 8px;">Device Address</th>
                    </tr>"""

        # Populate the table with disconnected machine details
        for machine in disconnected_machines:
            body += f"""<tr>
                        <td style="border: 1px solid #dddddd; text-align: left; padding: 8px;">{machine["name"]}</td>
                        <td style="border: 1px solid #dddddd; text-align: left; padding: 8px;">{machine["port_no"]}</td>
                        <td style="border: 1px solid #dddddd; text-align: left; padding: 8px;">{machine.company_id.name}</td>
                        <td style="border: 1px solid #dddddd; text-align: left; padding: 8px;">{machine.address_id.name}</td>
                    </tr>"""

        body += """</table>
                <p>Please check the parameters and network connections.</p> \n\n
                """

                # Send email to HR
        self.env['mail.mail'].create({
            'subject': subject,
            'body_html': body,
            'email_from': company_email,
            'email_to': ', '.join(hr_emails),
            'auto_delete': True,
        }).send()
        
        return True



    def reset_mode(self):
        zk_attendance = self.env['zk.machine.attendance']
        for info in self:
            machine_ip = info.name
            zk_port = info.port_no
            timeout = 15
            try:
                zk = ZK(machine_ip, port=zk_port, timeout=timeout, password=0, force_udp=False, ommit_ping=False)
            except NameError:
                raise UserError(_("Pyzk module not Found. Please install it with 'pip3 install pyzk'."))
            conn = self.device_connect(zk)
            if conn:
                try:
                    attendance = conn.get_attendance()
                except:
                    attendance = False
                if attendance:
                    # Sort attendance by time in ascending order
                    sorted_attendance = sorted(attendance, key=lambda x: x.timestamp)
                    first_punch = sorted_attendance[0]  # Get the first punch of the day
                    first_punch.punch = 0  # Set the first punch as check-in
                    conn.disconnect()
                    return True
                else:
                    raise UserError(_('Unable to get the attendance log, please try again later.'))
            else:
                raise UserError(_('Unable to connect, please check the parameters and network connections.'))


    # def process_delete_marked_users(self):
    #     """
    #     Processes employees marked for deletion from biometric devices.
    #     """
    #     devices = self.env['zk.machine'].search([])
    #     if not devices:
    #         raise UserError("No devices are configured. Please check the setup.")

    #     employees_to_delete = self.env['hr.employee'].search([('delete_mark_user', '=', True), ('device_id', '!=', False)])

    #     if not employees_to_delete:
    #         _logger.info("No employees marked for deletion.")
    #         return

    #     for employee in employees_to_delete:
    #         for device in devices:
    #             try:
    #                 # Remove the employee from the device
    #                 device.remove_user_from_machine(int(employee.device_id), employee.name)

    #                 # Log the success and reset the field
    #                 _logger.info(f"Successfully removed user {employee.name} (Device ID: {employee.device_id}) from device {device.name}.")
    #                 employee.delete_mark_user = False

    #             except Exception as e:
    #                 _logger.error(f"Failed to remove user {employee.name} from device {device.name}: {str(e)}")
    #                 raise UserError(_(
    #                     'Error removing user %s from device %s: %s' % (employee.name, device.name, str(e))
    #                 ))


    def download_attendance(self):
        _logger.info("++++++++++++Cron Executed++++++++++++++++++++++")
        zk_attendance = self.env['zk.machine.attendance']
        att_obj = self.env['hr.attendance']
        
        # Dictionary to store '255' data date-wise
        punch_temp_dict = defaultdict(list)

        for info in self:
            machine_ip = info.name
            zk_port = info.port_no
            timeout = 15
            try:
                zk = ZK(machine_ip, port=zk_port, timeout=timeout, password=0, force_udp=False, ommit_ping=False)
            except NameError:
                raise UserError(_("Pyzk module not Found. Please install it with 'pip3 install pyzk'."))
            conn = self.device_connect(zk)
            if conn:
                try:
                    user = conn.get_users()
                except:
                    user = False
                try:
                    attendance = conn.get_attendance()
                except:
                    attendance = False
                if attendance:
                    # Sort attendance records by timestamp before processing
                    sorted_attendance = sorted(attendance, key=lambda x: x.timestamp)
                    for each in sorted_attendance:
                        atten_time = each.timestamp
                        atten_time = datetime.strptime(atten_time.strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')
                        local_tz = pytz.timezone(self.env.user.partner_id.tz or 'GMT')
                        local_dt = local_tz.localize(atten_time, is_dst=None)
                        utc_dt = local_dt.astimezone(pytz.utc)
                        utc_dt = utc_dt.strftime("%Y-%m-%d %H:%M:%S")
                        atten_time = datetime.strptime(utc_dt, "%Y-%m-%d %H:%M:%S")
                        atten_time_str = fields.Datetime.to_string(atten_time)

                        if str(each.punch) == '255':
                            # Store '255' data date-wise into punch_temp_dict
                            atten_date = atten_time.date()
                            punch_temp_dict[atten_date].append({
                                'user_id': each.user_id,
                                'punch_time': atten_time,
                                'status': each.status,
                                'punch': each.punch,
                            })
                        else:
                            continue

                    # Process '255' data stored in punch_temp_dict
                    for date, punches in punch_temp_dict.items():
                                for punch in punches:
                                    employee_id = punch['user_id']
                                    punch_time = punch['punch_time']
                                    get_user_id = self.env['hr.employee'].search([('device_id', '=', employee_id)])

                                    if get_user_id:
                                        duplicate_atten_ids = zk_attendance.search(
                                            [('employee_id', '=', get_user_id.id), 
                                            ('punching_time', '=', punch_time)
                                        ])
                                                                                                
                                        if duplicate_atten_ids:
                                            continue
                                        else:
                                            zk_attendance.create({'employee_id': get_user_id.id,
                                                                    'device_id': punch['user_id'],
                                                                    'attendance_type': str(punch['status']),
                                                                    'punch_type': str(punch['punch']),
                                                                    'punching_time': punch_time,
                                                                    'company_id': info.company_id.id,
                                                                    'address_id': info.address_id
                                                                    })

                                        local_tz = pytz.timezone(self.env.user.partner_id.tz or 'Asia/Dhaka')
                                        utc_dt = pytz.utc.localize(punch_time)
                                        local_dt = utc_dt.astimezone(local_tz)
                                        punch_date = local_dt.date()

                                        start_utc = local_tz.localize(datetime.combine(punch_date, datetime.min.time())).astimezone(pytz.utc)
                                        end_utc = local_tz.localize(datetime.combine(punch_date, datetime.max.time())).astimezone(pytz.utc)

                                        # Check if there is already a check-in record for this day
                                        existing_check_in = att_obj.search([
                                            ('employee_id', '=', get_user_id.id),
                                            ('check_in', '>=', start_utc),
                                            ('check_in', '<=', end_utc),
                                            # ('check_out', '=', False),
                                        ], limit=1)
                                        _logger.info("#########################Existing Check in#######")
                                        _logger.info(existing_check_in)
                                        
                                        existing_check_out = att_obj.search([
                                            ('employee_id', '=', get_user_id.id),
                                            ('check_in', '!=', False),
                                            ('check_out', '>=', start_utc),
                                            ('check_out', '<=', end_utc),
                                        ], limit=1)

                                        existing_auto_check_out = att_obj.search([
                                            ('employee_id', '=', get_user_id.id),
                                            ('check_in', '>=', start_utc),
                                            ('check_in', '<=', end_utc),
                                            ('check_out', '!=', False),
                                        ], limit=1)

                                        
                                        if existing_check_in:
                                            # If there is already a check-in, create a check-out record
                                            existing_check_in.write({
                                                'check_out': punch_time,
                                                'check_out_location': 'attendance_device',
                                                'address_id': info.address_id,
                                                'check_out_address': info.address_id,
                                                'device_no':info.device_no,
                                                'company_id': info.company_id.id,
                                            })

                                            existing_check_in.total_punches += 1 
                                            
                                            
                                        elif existing_check_out:
                                            # If there is already a check-in, create a check-out record
                                            existing_check_out.write({
                                                'check_out': punch_time,
                                                'check_out_location': 'attendance_device',
                                                'address_id': info.address_id,
                                                'check_out_address': info.address_id,
                                                'device_no':info.device_no,
                                                'company_id': info.company_id.id,
                                            })
                                            existing_check_out.total_punches += 1

                                        elif existing_auto_check_out:
                                            # If there is already a check-in, create a check-out record
                                            existing_auto_check_out.write({
                                                'check_out': punch_time,
                                                'check_out_location': 'auto',
                                                'address_id': info.address_id,
                                                'company_id': info.company_id.id,
                                            })
                                            existing_auto_check_out.total_punches += 1 

                                        else:
                                            # If there is no existing check-in, create a new check-in record
                                            att_obj.create({
                                                'employee_id': get_user_id.id,
                                                'check_in': punch_time,
                                                'company_id': info.company_id.id,
                                                'device_no':info.device_no,
                                                'address_id': info.address_id,
                                                'check_in_location': 'attendance_device',
                                                'check_in_address': info.address_id,
                                            })
                                            att_obj.total_punches += 1 
                                    else:
                                        continue
                    # Marked users will be deleted from the machine, Comment this function if dont want to set this into cron.
                    # self.process_delete_marked_users()
                    conn.disconnect()
                    return True
                else:
                    continue
            else:
                continue

