# Copyright 2019 Ecosoft Co., Ltd (https://ecosoft.co.th/)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class Agreement(models.Model):
    _inherit = 'agreement'

    contract_type = fields.Selection(
        string="Contract Type",
        selection=[
            ('sale', 'Customer'),
            ('purchase', 'Supplier'),
        ],
        default="sale",
        required=True,
    )
    active_contract = fields.Integer(
        string="Active Contract",
        compute="_compute_contract_count",
    )
    all_contract = fields.Integer(
        string="All Contract",
        compute="_compute_contract_count",
    )

    @api.multi
    def _compute_contract_count(self):
        Contract = self.env['account.analytic.account']
        for agreement in self:
            domain = [('agreement_id', '=', agreement.id)]
            agreement.active_contract = Contract.search_count(domain)
            agreement.all_contract = Contract.with_context(active_test=False).\
                search_count(domain)

    @api.multi
    def action_view_contract(self):
        self.ensure_one()
        Contract = self.env['account.analytic.account']
        search_contract = Contract.with_context(active_test=False).\
            search([('agreement_id', '=', self.id)])
        # Is contract created?
        if not search_contract:
            raise UserError(_('Please create contract.'))
        # Update action
        if self.contract_type == 'sale':
            xml_id = 'contract.action_account_analytic_sale_overdue_all'
            view_id = 'contract.account_analytic_account_sale_form'
        else:
            xml_id = 'contract.action_account_analytic_purchase_overdue_all'
            view_id = 'contract.account_analytic_account_purchase_form'
        action = self.env.ref(xml_id).read()[0]
        if len(search_contract) == 1:
            form = self.env.ref(view_id)
            action.update({
                'views': [(form.id, 'form')],
                'res_id': search_contract.id,
            })
        else:
            action.update({'domain': [
                    '|', ('active', '=', True), ('active', '=', False),
                    ('id', 'in', search_contract.ids)],
            })
        return action

    @api.multi
    def prepare_contract(self):
        self.ensure_one()
        journal = self.env['account.journal'].search(
            [('type', '=', self.contract_type),
             ('company_id', '=', self.company_id.id),
             ], limit=1
        )
        vals = self.env['account.analytic.account'].new({
            'name': self.name,
            'contract_type': self.contract_type,
            'agreement_id': self.id,
            'partner_id': self.partner_id.id,
            'journal_id': journal.id,
            'pricelist_id': self.partner_id.property_product_pricelist.id,
            'date_start': self.start_date,
            'date_end': self.end_date,
            'recurring_invoices': True,
        })
        vals._onchange_date_start()
        return vals._convert_to_write(vals._cache)

    @api.multi
    def prepare_contract_line(self, line, analytic_id):
        val = ({
            'analytic_account_id': analytic_id,
            'product_id': line.product_id.id,
            'name': line.name,
            'quantity': line.qty,
            'uom_id': line.uom_id.id,
            'price_unit': line.product_id.lst_price,
        })
        return val

    @api.multi
    def create_new_contract(self):
        if self.active_contract != 0:
            raise UserError(_('You created contract already.'))
        for agreement in self:
            val = agreement.prepare_contract()
            contract = self.env['account.analytic.account'].create(val)
            # Prepare contract's product lines
            for line in self.line_ids:
                new_line = line.prepare_contract_line(line, contract.id)
                self.env['account.analytic.invoice.line'].create(new_line)
        return contract
