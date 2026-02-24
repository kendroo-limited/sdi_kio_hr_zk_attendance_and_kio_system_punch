from odoo import models

class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _filter_visible_menus(self):
        res = super(IrUiMenu, self)._filter_visible_menus()

        # Hide the attendance menu by ID for ALL users
        menu_to_hide = self.env.ref('hr_attendance.menu_hr_attendance_my_attendances', raise_if_not_found=False)
        if menu_to_hide:
            res = res.filtered(lambda menu: menu.id != menu_to_hide.id)

        return res
