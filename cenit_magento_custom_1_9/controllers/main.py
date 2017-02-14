import logging
from openerp import http
from openerp.http import request
from openerp import SUPERUSER_ID, workflow
from openerp.modules.registry import RegistryManager
import json, simplejson
from datetime import datetime


_logger = logging.getLogger(__name__)


class MagentoController(http.Controller):
    '''
      Creates a sales order
    '''

    @http.route(['/orders/<string:action>',
                 '/orders/<string:action>/<string:root>'],
                type='json', auth='none', methods=['POST'], csrf=False)
    def create_sales_orders(self, action, root=None):
        status_code = 400
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
                r = self.create_order(cr, request, registry)
                if not r:
                    status_code = '200'
                else:
                    return r
            else:
                status_code = 404

        return {'status': status_code}

    def create_order(self, cr, request, registry):
        order_data = json.dumps(request.jsonrequest)
        order_data = simplejson.loads(str(order_data.decode()))

        partner_name = order_data['partner_id']['name']
        context = request.context

        order_id = self.get_id_from_record(cr, registry, 'sale.order', [('jmd_po_number_so', '=', order_data.get('jmd_po_number_so'))], context=context)
        if order_id and not data['force_creation']:
            return {'errors': {'notify': 'The order ' + order_data.get('jmd_po_number_so') + 'is already created in Odoo'}}

        partner_id = self.get_id_from_record(cr, registry, 'res.partner', [('name', '=', partner_name)], context=context)
        if partner_id:
            order_data['partner_id'] = partner_id  # Updating partner_id(Customer)
            order_data['partner_invoice_id'] = partner_id  # Updating invoice address
            order_data['partner_shipping_id'] = partner_id  # Updating shipping address

            partner = registry['res.partner'].browse(cr, SUPERUSER_ID, partner_id, context=context)[0]
            order_data['payment_term_id'] = partner['property_payment_term_id']['id']

            order_data['warehouse_id'] = self.get_id_from_record(cr, registry, 'stock.warehouse',
                                                                 [('name', '=', order_data['warehouse_id'])],
                                                                 context=context)

            order_data['user_id'] = self.get_id_from_record(cr, registry, 'res.users', [('name', '=', order_data['user_id'])],
                                                            context=context)  # Updating sales person

            order_data['team_id'] = self.get_id_from_record(cr, registry,'crm.team', [('name', '=', order_data['team_id'])],
                                                            context=context)
            order_data['invoice_status'] = 'invoiced'

            errors = None

            lines = {}
            if order_data.get('order_line'):
                lines = order_data.pop('order_line')
                saleorder_registry = registry['sale.order']
            try:
                order_id = self.get_id_from_record(cr, registry, 'sale.order', [('name', '=', order_data.get('name'))], context=context)
                if not order_id:
                    order_id = saleorder_registry.create(cr, SUPERUSER_ID, order_data)
                else:
                    saleorder_registry.write(cr, SUPERUSER_ID, order_id, order_data)
                if order_id:
                    # Create order lines
                    if lines:
                        for line in lines:
                            i_registry = registry['product.product']
                            domain = [('barcode', '=', line['jmd_product_barcode'])]
                            line['product_id'] = self.get_id_from_record(cr, registry, 'product.product', domain, context=context)

                            if not line['product_id']:
                                errors = 'Product '+line['name'] + ' -' + line['jmd_product_barcode'] + ' is found in Magento but not in Odoo'
                            else:
                                product = i_registry.browse(cr, SUPERUSER_ID, line['product_id'], context=context)[0]
                                line['name'] = product['name']
                                line['order_id'] = order_id
                                line['product_uom'] = product['uom_id']['id']

                                line['customer_lead'] = product['sale_delay']

                                line['tax_id'] = [[x.id] for x in product['taxes_id']]
                                line['tax_id'] = [(6, False, line['tax_id'][0])]

                                if product['property_account_income_id']['id']:
                                    line['property_account_income_id'] = product['property_account_income_id']['id']
                                else:
                                    line['property_account_income_id'] = product['categ_id']['property_account_income_categ_id']['id']

                                if product['property_account_expense_id']['id']:
                                    line['property_account_expense_id'] = product['property_account_expense_id']['id']
                                else:
                                    line['property_account_expense_id'] = product['categ_id']['property_account_expense_categ_id']['id']

                                line_id = self.get_id_from_record(cr,  registry, 'sale.order.line', [('order_id', '=', order_id),
                                                                                          ('product_id', '=', product['id'])], context=context)
                                if not line_id:
                                    registry['sale.order.line'].create(cr, SUPERUSER_ID, line)
                                else:
                                    registry['sale.order.line'].write(cr, SUPERUSER_ID, line_id, line)
            except Exception as e:
                _logger.error(e)
                errors = e

            if not errors:
                order_data['order_line'] = lines
                ord_id = self.get_id_from_record(cr,  registry, 'sale.order', [('name', '=', order_data['name'])], context=context)
                ord = registry['sale.order'].browse(cr, SUPERUSER_ID, ord_id, context=context)[0]
                try:
                    ord.action_confirm() #Creating delivery
                    ord.action_done()  #Confirm order to status "Done"
                    inv_id = ord.action_invoice_create() #Creating invoice

                    if order_data['amount_total'] == 0:
                       inv = registry['account.invoice'].browse(cr, SUPERUSER_ID, inv_id, context=context)[0]
                       inv.action_move_create()
                       inv_date = order_data.get('date_order', datetime.now())
                       registry['account.invoice'].write(cr, SUPERUSER_ID, inv_id, {'date_invoice': inv_date, 'state': 'paid'})
                       inv._onchange_payment_term_date_invoice()
                    else:
                       workflow.trg_validate(SUPERUSER_ID, 'account.invoice', inv_id[0], 'invoice_open', cr)

                    #STOCK
                    stock_pick_id = self.get_id_from_record(cr,  registry, 'stock.picking', [('origin', '=', order_data['name'])], context=context)
                    stock_pick = registry['stock.picking'].browse(cr, SUPERUSER_ID, stock_pick_id, context=context)[0]

                    if stock_pick["state"] == "confirmed":
                       stock_pick.force_assign() # Forcing assign
                    else:
                       stock_pick.do_new_transfer() #Validating assign

                    stock_transf_id = registry['stock.immediate.transfer'].create(cr, SUPERUSER_ID, {'pick_id': stock_pick.id}, context=context)
                    stock_transf = registry['stock.immediate.transfer'].browse(cr, SUPERUSER_ID, stock_transf_id, context=context)[0]
                    stock_transf.process()

                except Exception as e:
                  _logger.error(e)
                  errors = e

            return {'errors': {'notify': errors}} if errors else None

        return {'errors:': {'notify': 'There is no Customer named ' + partner_name}}

    def get_id_from_record(self, cr, registry, model, domain, context):
        i_registry = registry[model]
        rc = i_registry.search(cr, SUPERUSER_ID, domain, context=context)  # Returns id
        if rc:
            return rc[0]
        else:
            return None
