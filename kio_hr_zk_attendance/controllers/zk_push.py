# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import datetime
import pytz
import logging

_logger = logging.getLogger(__name__)

class ZKIclockPush(http.Controller):

    @http.route('/zkpush', type='http', auth='public', methods=['GET'], csrf=False)
    def iclock_push(self, **post):
        """
        This handles ZKTeco iClock push requests.
        The device will send attendance logs as URL query params (GET) or form data (POST).
        """
        _logger.info("📌 ZK iClock Push Received: %s", post)

        # Example iClock push data: PIN=1001&DateTime=2025-07-03 15:15:12&Status=0&Punch=0&WorkCode=0

        pin = post.get('PIN')  # employee PIN/device ID
        punch_time = post.get('DateTime')
        status = post.get('Status')
        punch = post.get('Punch')

        if not pin or not punch_time:
            _logger.warning("Invalid push data: %s", post)
            return "OK"

        try:
            # Parse punch time & convert to UTC
            local_tz = pytz.timezone('Asia/Dhaka')  # change if needed
            local_dt = local_tz.localize(datetime.strptime(punch_time, '%Y-%m-%d %H:%M:%S'))
            utc_dt = local_dt.astimezone(pytz.utc)
        except Exception as e:
            _logger.error("Time parse error: %s", e)
            return "OK"

        employee = request.env['hr.employee'].sudo().search([('device_id', '=', pin)], limit=1)
        if not employee:
            _logger.warning("No matching employee for PIN: %s", pin)
            return "OK"

        att_obj = request.env['hr.attendance'].sudo()

        # Basic logic: always create new check_in (customize this!)
        att_obj.create({
            'employee_id': employee.id,
            'check_in': utc_dt,
            'check_in_location': 'iclock',
            'company_id': employee.company_id.id,
        })

        _logger.info("✅ Punch saved for %s at %s", employee.name, utc_dt)

        return "OK"
