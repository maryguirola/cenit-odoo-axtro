__author__ = 'mary'

import logging
import simplejson
from openerp import http
from openerp.http import request
from openerp import SUPERUSER_ID, workflow
from openerp.modules.registry import RegistryManager

import json, simplejson
from datetime import datetime
from openerp.api import Environment


_logger = logging.getLogger(__name__)


class AnchantoController(http.Controller):
    @http.route(['/product'],
                type='http', auth='none', methods=['GET'], csrf=False)
    def get_product(self, key_search, value):
        db_name = self.search_connection(request)
        registry = RegistryManager.get(db_name)
        with registry.cursor() as cr:
            env = Environment(cr, SUPERUSER_ID, {})
            domain = [(key_search, '=', value)]
            product = env['product.template'].search(domain)
            # product = env['product.template'].browse(product_id)
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


    @http.route(['/products'],
                type='json', auth='none', methods=['POST'], csrf=False)
    def get_products(self):
        db_name = self.search_connection(request)
        registry = RegistryManager.get(db_name)
        with registry.cursor() as cr:
            env = Environment(cr, SUPERUSER_ID, {})
            offset = request.jsonrequest['offset']
            prod_tm = env['product.template']
            products = prod_tm.search_read(fields=['id', 'name', 'barcode', 'standard_price', 'weight', 'default_code'], order='id', limit=50, offset=offset)
            return products

    @http.route(['/product'],
                type='json', auth='none', methods=['POST'], csrf=False)
    def update_product(self):
        db_name = self.search_connection(request)
        registry = RegistryManager.get(db_name)
        with registry.cursor() as cr:
            env = Environment(cr, SUPERUSER_ID, {})
            data = request.jsonrequest
            prod = env['product.template'].search([('id', '=', data["odoo_product_id"])])

            if prod:
                env['product.template'].write({"id": data["odoo_product_id"],
                                              'weight': data["weight"]})
                return {'response': 'success'}
            else:
                return {'response': 'Product with id ' + data["odoo_product_id"] + ' wasn\'t found'}


    @http.route(['/purchaseorder'],
            type='json', auth='none', methods=['POST'], csrf=False)
    def update_receipt_from_purchase_order(self):
        db_name = self.search_connection(request)
        registry = RegistryManager.get(db_name)
        with registry.cursor() as cr:
            env = Environment(cr, SUPERUSER_ID, {})
            data = request.jsonrequest
            po = env['stock.picking'].search([('id', '=', data["id"])])
            if po:
                po.write({data["field"]: data["value"]})
                return {'response': 'success'}
            else:
                return {'response': 'Purchase order number ' + data['name'] + 'not found'}

    @http.route(['/purchaseorder/shipment'],
            type='json', auth='none', methods=['POST'], csrf=False)
    def update_shipment_purchase_order(self):
        db_name = self.search_connection(request)
        registry = RegistryManager.get(db_name)
        with registry.cursor() as cr:
            env = Environment(cr, SUPERUSER_ID, {})
            data = request.jsonrequest
            data_products = data["products"]
            po = env['purchase.order'].search([('id', '=', data["id"])])
            if po:
                pickings = po.picking_ids
                for pick in pickings:
                    products = pick.pack_operation_product_ids
                    for prod in products:
                        if prod['product_id']['barcode'] in data_products:
                            barcode = prod['product_id']['barcode']
                            prod.write({'qty_done': data_products[barcode]})

                    #Validate transfer(stock.picking)
                    if pick.check_backorder():
                        wiz = self.env['stock.backorder.confirmation'].create({'pick_id': pick.id})
                    #pick.do_new_transfer()
                    #stock_transf_id = registry['stock.immediate.transfer'].create({'pick_id': pick.id})
                    #stock_transf = registry['stock.immediate.transfer'].search(stock_transf_id)
                    #stock_transf.process()
            else:
                return {'response': 'Purchase order number ' + data['name'] + 'not found'}

    def search_connection(self, request):
        environ = request.httprequest.headers.environ.copy()

        key = environ.get('HTTP_X_USER_ACCESS_KEY', False)
        token = environ.get('HTTP_X_USER_ACCESS_TOKEN', False)
        db_name = environ.get('HTTP_TENANT_DB', False)

        if not db_name:
            host = environ.get('HTTP_HOST', "")
            db_name = host.replace(".", "_").split(":")[0]

        registry = RegistryManager.get(db_name)
        with registry.cursor() as cr:
            env = Environment(cr, SUPERUSER_ID, {})
            connection_model = env['cenit.connection']
            domain = [('key', '=', key), ('token', '=', token)]
            _logger.info(
                "Searching for a 'cenit.connection' with key '%s' and "
                "matching token", key)
            rc = connection_model.search(domain)
            _logger.info("Candidate connections: %s", rc)
            if rc:
                return db_name
            else:
                status_code = 404
        r = {'status': status_code}

        return simplejson.dumps(r)

    @http.route(['/purchaseorder/products'],
                type='json', auth='none', methods=['POST'], csrf=False)
    def get_products_purchase_order(self):
        db_name = self.search_connection(request)
        registry = RegistryManager.get(db_name)
        with registry.cursor() as cr:
            env = Environment(cr, SUPERUSER_ID, {})
            domain = [('name', '=', request.jsonrequest['po_number'])]
            po = env['purchase.order'].search(domain)

            if po:
                prods = []
                for p in po['order_line']:
                    data = {
                        'sku': p['product_id']['barcode'],
                        'cost_price': p['price_unit'],
                        'expiry_date': p['date_planned'],
                        'quantity': p['product_qty']
                    }
                    prods.append(data)
                return prods
            else:
               return {'response': 'Purchase order number ' + request.jsonrequest['po_number'] + 'not found'}