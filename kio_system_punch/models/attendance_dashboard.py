# -*- coding: utf-8 -*-

from datetime import datetime, time
from odoo import models, fields, api, _
from geopy.geocoders import Nominatim
import pytz


class AttendanceDashboard(models.Model):
    _name = 'attendance.dashboard'
    _description = 'Attendance Dashboard'

    @api.model
    def punch_attendance(self, lat=False, long=False, browser="", os_name=""):
        employee = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.uid)], limit=1)

        if not employee:
            return {'warning': 'No employee linked to this user.'}

        # Get current time in Bangladesh timezone
        bd_tz = pytz.timezone('Asia/Dhaka')
        utc_now = fields.Datetime.now()
        now_bd = utc_now.astimezone(bd_tz)
        
        # Use UTC time for database operations
        now = utc_now
        today_start = datetime.combine(now.date(), time.min)
        today_end = datetime.combine(now.date(), time.max)

        address = ""
        if lat and long:
            try:
                geolocator = Nominatim(user_agent="odoo-attendance")
                location = geolocator.reverse((lat, long), timeout=10)
                if location:
                    address = location.address
            except Exception as e:
                address = f"[Location Error: {str(e)}]"

        today_attendance = self.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', today_start),
            ('check_in', '<=', today_end),
        ], limit=1)

        if today_attendance:
            today_attendance.write({
                'check_out': now,
                'check_out_lat': lat,
                'check_out_long': long,
                'check_out_address': address,
                'browser': browser,
                'os_name': os_name,
                'check_out_location': 'system',
                'total_punches': today_attendance.total_punches + 1
            })
        else:
            self.env['hr.attendance'].sudo().create({
                'employee_id': employee.id,
                'check_in': now,
                'check_in_lat': lat,
                'check_in_long': long,
                'check_in_address': address,
                'browser': browser,
                'os_name': os_name,
                'check_in_location': 'system',
                'total_punches': 1
            })

        return {
            'effect': {
                'fadeout': 'slow',
                'message': 'Punched Successfully! 🎉',
                'type': 'rainbow_man',
            },
            'location_info': {
                'address': address,
                'lat': lat,
                'long': long,
                'browser': browser,
                'os_name': os_name,
                'punch_time': now_bd.strftime('%d %B %Y, %I:%M:%S %p')
            }
        }