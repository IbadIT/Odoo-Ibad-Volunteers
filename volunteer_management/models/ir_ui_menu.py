from odoo import models, api, tools


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    @tools.ormcache('frozenset(self.env.user.groups_id.ids)', 'debug')
    def _visible_menu_ids(self, debug=False):
        menus = super(IrUiMenu, self)._visible_menu_ids(debug)
        # menus.discard(self.env.ref('contacts.menu_contacts').id)
        return menus
