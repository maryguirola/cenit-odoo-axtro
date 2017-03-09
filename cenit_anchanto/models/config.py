# -*- coding: utf-8 -*-
# #############################################################################
#
# OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010, 2014 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import logging

from openerp import models, fields


_logger = logging.getLogger(__name__)

COLLECTION_NAME = "anchanto"
COLLECTION_VERSION = "1.0.0"
COLLECTION_PARAMS = {
    # WITHOUT COLLECTION_PARAMS.
}


class CenitIntegrationSettings(models.TransientModel):
    _name = "cenit.anchanto.settings"
    _inherit = 'cenit.hub.settings'


    ############################################################################
    # Pull Parameters
    ############################################################################
    # WITHOUT PULL PARAMETERS.

    ############################################################################
    # Default Getters
    ############################################################################
    # WITHOUT GETTERS.

    ############################################################################
    # Default Setters
    ############################################################################
    # WITHOUT SETTERS.

    ############################################################################
    # Actions
    ############################################################################
    def install(self, cr, uid, context=None):

        installer = self.pool.get('cenit.collection.installer')
        installer.install_collection(cr, uid, {'name': COLLECTION_NAME})


    def update_connection_role(self, cr, uid, context):
        role_pool = self.pool.get("cenit.connection.role")
        conn_rol = role_pool.get(cr, uid, "/setup/connection_role", {'name': 'My Odoo role'})
        if conn_rol:
            if len(conn_rol["connection_role"]) > 0:
                conn_rol = conn_rol["connection_role"][0]
                webhook = {
                    "_reference": "True",
                    "namespace": "Odoo",
                    "name": "Get product"
                }
                conn_rol["webhooks"].append(webhook)
                webhook = {
                    "_reference": "True",
                    "namespace": "Odoo",
                    "name": "Update product"
                }
                conn_rol["webhooks"].append(webhook)
                webhook = {
                    "_reference": "True",
                    "namespace": "Odoo",
                    "name": "Update purchase order number"
                },
                conn_rol["webhooks"].append(webhook)

                role_pool.post(cr, uid, "/setup/connection_role", conn_rol)