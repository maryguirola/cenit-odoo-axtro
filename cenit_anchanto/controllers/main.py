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
        """
          Gets a product from the inventory module by a key and value specified

          :param key_search: Filter of the search
          :param value: Value of the filter
          :return: Product found
        """
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
        """
          Gets all products from the inventory module

          :return: List of products
       """
        db_name = self.search_connection(request)
        registry = RegistryManager.get(db_name)
        with registry.cursor() as cr:
            env = Environment(cr, SUPERUSER_ID, {})
            offset = request.jsonrequest['offset']
            prod_tm = env['product.template']
            products = prod_tm.search_read(fields=['id', 'name', 'barcode', 'standard_price', 'weight', 'default_code'],
                                           order='id', limit=50, offset=offset)
            return products

    @http.route(['/product'],
                type='json', auth='none', methods=['POST'], csrf=False)
    def update_product_weight(self):
        """
          Updates the product's weight by its id
        """
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
        """
        Updates a field of the purchase order receipt
        """
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
        '''
        Set to DONE the transfer associated with the Purchase order
        :return:
        '''
        db_name = self.search_connection(request)
        registry = RegistryManager.get(db_name)
        with registry.cursor() as cr:
            env = Environment(cr, SUPERUSER_ID, {})
            data = request.jsonrequest
            data_products = data["products"]
            pick = env['stock.picking'].search([('id', '=', data["id"])])
            if pick:
                    products = pick.pack_operation_product_ids
                    for prod in products:
                        if prod['product_id']['barcode'] in data_products:
                            barcode = prod['product_id']['barcode']
                            prod.write({'qty_done': data_products[barcode]}) # Updating product's quantities in stock.picking

                    # Validate transfer(stock.picking)
                    if pick.check_backorder(pick): # Check if create back order
                        back_order = env['stock.backorder.confirmation'].create({'pick_id': pick.id})
                        back_order.process()
                    else:
                        pick.do_new_transfer() # Else, update product's quantities and set to done the Transfer.
                    return {'response': 'success'}
            else:
                return {'response': 'Shipment ' + data['name'] + 'not found'}

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
        '''
        Gets the products of a purchase order
        :return: Products
        '''
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
                return {'response': 'Purchase order number ' + request.jsonrequest['po_number'] + ' not found'}


    @http.route(['/salesorder/delivery'],
                type='json', auth='none', methods=['POST'], csrf=False)
    def validate_delivery_order(self):
        '''
        Validates the delivery order associated with the Sales Order
        :return:
        '''
        db_name = self.search_connection(request)
        registry = RegistryManager.get(db_name)
        with registry.cursor() as cr:
            env = Environment(cr, SUPERUSER_ID, {})
            data = request.jsonrequest
            pick = env['stock.picking'].search([('name', '=', data["number"])])
            if pick:
                origin = pick['origin'] + " / " + data['tracking_number']
                pick.write({'origin': origin})  # Updating delivery order's source document

                pick.do_new_transfer()  # Set to DONE the delivery order.

                stock_transf_id = env['stock.immediate.transfer'].create({'pick_id': pick.id})
                stock_transf = env['stock.immediate.transfer'].search([('id', '=', stock_transf_id.id)])
                stock_transf.process()

                return {'response': 'success'}
            else:
                return {'response': 'Delivery order ' + data['number'] + ' not found'}
