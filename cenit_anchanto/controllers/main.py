__author__ = 'mary'

import logging
import simplejson
from openerp import http
from openerp.http import request
from openerp import SUPERUSER_ID, workflow
from openerp.modules.registry import RegistryManager
import json, simplejson
from datetime import datetime

_logger = logging.getLogger(__name__)


class AnchantoController(http.Controller):
    '''
       Search a product by domain
    '''

    @http.route(['/product'],
                type='http', auth='none', methods=['GET'], csrf=False)
    def get_product(self, key_search, value):
        environ = request.httprequest.headers.environ.copy()

        key = environ.get('HTTP_X_USER_ACCESS_KEY', False)
        token = environ.get('HTTP_X_USER_ACCESS_TOKEN', False)
        db_name = environ.get('HTTP_TENANT_DB', False)

        if not db_name:
            host = environ.get('HTTP_HOST', "")
            db_name = host.replace(".", "_").split(":")[0]

        registry = RegistryManager.get(db_name)
        with registry.cursor() as cr:
            connection_model = registry['cenit.connection']
            domain = [('key', '=', key), ('token', '=', token)]
            _logger.info(
                "Searching for a 'cenit.connection' with key '%s' and "
                "matching token", key)
            rc = connection_model.search(cr, SUPERUSER_ID, domain)
            _logger.info("Candidate connections: %s", rc)
            if rc:
                domain = [(key_search, '=', value)]
                product_id = registry['product.template'].search(cr, SUPERUSER_ID, domain)
                product = registry['product.template'].browse(cr, SUPERUSER_ID, product_id)
                if product:
                    data = {
                        "response": "success",
                        "product": {
                            "id": product["id"],
                            "name": product["name"],
                            "barcode": product["barcode"],
                            "price": product["price"],
                            "cost_method": product["cost_method"]
                        }
                    }
                else:
                    data = {
                        "response": "Product not found"
                    }
                return simplejson.dumps(data)
            else:
                status_code = 404
        r = {'status': status_code}
        return simplejson.dumps(r)


    @http.route(['/product'],
                type='json', auth='none', methods=['POST'], csrf=False)
    def update_product(self):
        environ = request.httprequest.headers.environ.copy()

        key = environ.get('HTTP_X_USER_ACCESS_KEY', False)
        token = environ.get('HTTP_X_USER_ACCESS_TOKEN', False)
        db_name = environ.get('HTTP_TENANT_DB', False)

        if not db_name:
            host = environ.get('HTTP_HOST', "")
            db_name = host.replace(".", "_").split(":")[0]

        registry = RegistryManager.get(db_name)
        with registry.cursor() as cr:
            connection_model = registry['cenit.connection']
            domain = [('key', '=', key), ('token', '=', token)]
            _logger.info(
                "Searching for a 'cenit.connection' with key '%s' and "
                "matching token", key)
            rc = connection_model.search(cr, SUPERUSER_ID, domain)
            _logger.info("Candidate connections: %s", rc)
            if rc:
                data = request.jsonrequest
                prod = registry['product.template'].search(cr, SUPERUSER_ID, [('id', '=',data["odoo_product_id"])])

                if prod:
                    registry['product.template'].write(cr, SUPERUSER_ID, data["odoo_product_id"], {'weight': data["weight"]})
                    return {'response': 'success'}
                else:
                    return {'response': 'Product not found'}