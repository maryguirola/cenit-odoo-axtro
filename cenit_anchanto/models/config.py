# -*- coding: utf-8 -*-
# #############################################################################
#
# OpenERP, Open Source Management Solution
# Copyright (C) 2004-2010, 2014 Tiny SPRL (<http://tiny.be>).
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
from openerp import SUPERUSER_ID
from openerp import models, fields, api
from openerp.api import Environment
import json
import os

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
    @api.model
    def install(self):

        installer = self.env['cenit.collection.installer']
        installer.install_collection({'name': COLLECTION_NAME})
        self.import_mapping()


    def update_connection_role(self):
        role_pool = self.env["cenit.connection.role"]
        conn_rol = role_pool.get("/setup/connection_role", {'name': 'My Odoo role'})
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
                    "name": "Update product's weight"
                }
                conn_rol["webhooks"].append(webhook)
                webhook = {
                              "_reference": "True",
                              "namespace": "Odoo",
                              "name": "Update purchase order number"
                          },
                conn_rol["webhooks"].append(webhook)

                role_pool.post("/setup/connection_role", conn_rol)


    @api.multi
    def update_collection(self):
        installer = self.env['cenit.collection.installer']
        installer.install_collection({'name': COLLECTION_NAME})


    def import_mapping(self):
        irmodel_pool = self.env['ir.model']
        schema_pool = self.env['cenit.schema']
        namespace_pool = self.env['cenit.namespace']
        datatype_pool = self.env['cenit.data_type']
        line_pool = self.env['cenit.data_type.line']
        domain_pool = self.env['cenit.data_type.domain_line']
        trigger_pool = self.env['cenit.data_type.trigger']

        basepath = os.path.dirname(__file__)
        filepath = os.path.abspath(os.path.join(basepath, "..", "data/data_types.json"))
        with open(filepath) as json_file:
            json_data = json.load(json_file)

            for data in json_data:
                odoo_model = data['model']
                namespace = data['namespace']
                schema = data['schema']

                domain = [('model', '=', odoo_model)]
                candidates = irmodel_pool.search(domain)
                if not candidates:
                    raise exceptions.MissingError(
                        "There is no %s module installed" % odoo_model
                    )
                odoo_model = candidates.id

                domain = [('name', '=', namespace)]
                candidates = namespace_pool.search(domain)
                if not candidates:
                    raise exceptions.MissingError(
                        "There is no %s namespace in Namespaces" % namespace
                    )
                namespace = candidates.id

                domain = [('name', '=', schema), ('namespace', '=', namespace)]
                candidates = schema_pool.search(domain)
                if not candidates:
                    raise exceptions.MissingError(
                        "There is no %s schema in Schemas" % schema
                    )
                schema = candidates.id

                vals = {'name': data['name'], 'model': odoo_model, 'namespace': namespace, 'schema': schema}
                dt = datatype_pool.search([('name', '=', data['name'])])
                updt = False
                if dt:
                    dt.write(vals)
                    updt = True
                else:
                    dt = datatype_pool.create(vals)

                if updt:
                        for d in dt.domain:
                            d.unlink()
                        for d in dt.triggers:
                            d.unlink()
                        for d in dt.lines:
                            d.unlink()

                for domain in data['domains']:
                    vals = {'data_type': dt.id, 'field': domain['field'], 'value': domain['value'],
                            'op': domain['op']}
                    domain_pool.create(vals)

                for trigger in data['triggers']:
                    vals = {'data_type': dt.id, 'name': trigger['name'], 'cron_lapse': trigger['cron_lapse'],
                            'cron_units': trigger['cron_units'], 'cron_restrictions': trigger['cron_restrictions'],
                            'cron_name': trigger['cron_name']}
                    trigger_pool.create(vals)

                for line in data['lines']:
                    domain = [('name', '=', line['reference'])]
                    candidate = datatype_pool.search(domain)
                    vals = {
                        'data_type': dt.id, 'name': line['name'], 'value': line['value'],
                        'line_type': line['line_type'], 'line_cardinality': line['line_cardinality'],
                        'primary': line['primary'], 'inlined': line['inlined'], 'reference': candidate.id
                    }
                    line_pool.create(vals)
                dt.sync_rules()
                _logger.info("Data imported successfully")