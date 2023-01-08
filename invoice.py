# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import io
import csv
from datetime import datetime
from decimal import Decimal

from trytond.model import ModelView, fields
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.i18n import gettext

from .exceptions import AccountError


def _date(value):
    v = value.strip()
    return datetime.strptime(v, '%d/%m/%Y').date()


def _string(value):
    return value.strip()


def _amount(value):
    return Decimal(value) if value else Decimal('0.0')


INVOICE = {
    'fecha': (0, _date),
    'tipo': (1, _string),
    'punto_venta': (2, _string),
    'numero_desde': (3, _string),
    'numero_hasta': (4, _string),
    'cod_autorizacion': (5, _string),
    'tipo_doc_emisor': (6, _string),
    'numero_doc_emisor': (7, _string),
    'denominacion_emisor': (8, _string),
    'tipo_cambio': (9, _amount),
    'moneda': (10, _string),
    'neto_gravado': (11, _amount),
    'neto_no_gravado': (12, _amount),
    'op_exentas': (13, _amount),
    'iva': (14, _amount),
    'total': (15, _amount),
    }

CURRENCY = {
    '$': 'ARS',
    'U$S': 'USD',
    }

FIELDS_TAXES = {
    'neto_gravado': 'import_invoice_taxed_net',
    'neto_no_gravado': 'import_invoice_not_taxed_net',
    'op_exentas': 'import_invoice_exempt_operations',
    }

CREDIT_NOTES_TYPES = ['003', '008', '013', '021', '203', '208', '213']

AMOUNTS_CHECK = {
    'neto_gravado': 'pyafipws_imp_neto',
    'neto_no_gravado': 'pyafipws_imp_tot_conc',
    'op_exentas': 'pyafipws_imp_op_ex',
    'iva': 'pyafipws_imp_iva',
    'total': 'total_amount',
    }

DOC_TYPE_TO_IVA_CONDITION = {
    '001': 'responsable_inscripto',
    '002': 'responsable_inscripto',
    '003': 'responsable_inscripto',
    '004': 'responsable_inscripto',
    '005': 'responsable_inscripto',
    '011': 'monotributo',
    '012': 'monotributo',
    '013': 'monotributo',
    '015': 'monotributo',
    }

TIPO_DOCUMENTO = {
    'CUIT': '80',
    'CUIL': '86',
    'DNI': '96',
    }


class ImportInvoiceInStart(ModelView):
    "Invoice In Import Start"
    __name__ = 'account.invoice.import.start'
    company = fields.Many2One('company.company', "Company", required=True)
    file_ = fields.Binary("File", required=True)

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')


class ImportInvoiceIn(Wizard):
    "Invoice In Import"
    __name__ = 'account.invoice.import'
    start = StateView('account.invoice.import.start',
        'account_invoice_import_ar.invoice_in_import_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Import", 'import_', 'tryton-ok', default=True),
            ])
    import_ = StateAction('account_invoice.act_invoice_in_form')

    def _parse(self, name):
        parsed_lines = []
        line = 0
        csv_reader = csv.reader(name, delimiter=',')
        for row in csv_reader:
            line += 1
            # Ignore header
            if line == 1:
                continue
            parsed_lines.append(self._parse_invoice(row, INVOICE))
        return parsed_lines

    def _parse_invoice(self, row, squema):
        data = {}
        for name, (col, parser) in squema.items():
            data[name] = parser(row[col])
        return data

    def _get_invoice(self, data):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Party = pool.get('party.party')
        Address = pool.get('party.address')
        Currecy = pool.get('currency.currency')
        Journal = pool.get('account.journal')

        journals = Journal.search([
                ('type', '=', 'expense'),
                ], limit=1)
        if journals:
            journal, = journals
        else:
            journal = None
        currency_code = CURRENCY.get(data['moneda'], 'ARS')
        currency = Currecy.search([('code', '=', currency_code)])
        tipo_comprobante = data['tipo'].split('-')[0].strip().zfill(3)
        reference = '%s-%s' % (
            data['punto_venta'].zfill(5), data['numero_desde'].zfill(8))
        # ar_cuit / ar_dni
        tipo_doc_emisor = 'ar_%s' % data['tipo_doc_emisor'].lower()
        party = Party.search([
            ('identifiers.type', '=', tipo_doc_emisor),
            ('identifiers.code', '=', data['numero_doc_emisor']),
            ])
        if not party:
            new_party = Party(
                name=data['denominacion_emisor'],
                tipo_documento=TIPO_DOCUMENTO[data['tipo_doc_emisor']],
                iva_condition=DOC_TYPE_TO_IVA_CONDITION[tipo_comprobante],
                vat_number=data['numero_doc_emisor'],
                )
            new_party.save()
            try:
                padron = Party.get_ws_afip(new_party.vat_number)
                if padron.data:
                    new_party.set_padron(padron)
            except Exception:
                company_address = self.start.company.party.address_get(
                    type='invoice')
                new_address = Address(
                    party=new_party.id,
                    invoice=True,
                    street=company_address.street,
                    postal_code=company_address.postal_code,
                    city=company_address.city,
                    subdivision=company_address.subdivision,
                    country=company_address.country,
                    )
                new_address.save()
            party = [new_party]

        existing_invoice = Invoice.search([
            ('party', '=', party[0].id),
            ('type', '=', 'in'),
            ('tipo_comprobante', '=', tipo_comprobante),
            ('reference', '=', reference),
            ])
        if existing_invoice:
            return None
        invoice = Invoice(
            company=self.start.company,
            type='in',
            journal=journal,
            invoice_date=data['fecha'],
            party=party[0].id,
            party_tax_identifier=party[0].tax_identifier,
            invoice_address=party[0].address_get(type='invoice'),
            currency=currency[0],
            account=party[0].account_payable_used,
            tipo_comprobante=tipo_comprobante,
            reference=reference,
            payment_term=party[0].supplier_payment_term,
            currency_rate=data['tipo_cambio'],
            pyafipws_cae=data['cod_autorizacion'],
            )
        invoice.on_change_type()
        return invoice

    def _get_invoice_lines(self, data, invoice):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        Currecy = pool.get('currency.currency')
        Uom = pool.get('product.uom')
        AccountConfiguration = pool.get('account.configuration')
        account_config = AccountConfiguration(1)

        currency_code = CURRENCY.get(data['moneda'], 'ARS')
        currency = Currecy.search([('code', '=', currency_code)])
        unit, = Uom.search([('symbol', '=', 'u')])
        party = invoice.party

        # Facturas C: only 'total' is not null
        only_total_not_null = not any([data[f] != Decimal('0.0') for f in [
            'neto_gravado', 'neto_no_gravado', 'op_exentas', 'iva']])
        lines = []
        for f in ['neto_gravado', 'neto_no_gravado', 'op_exentas']:
            if only_total_not_null and f != 'neto_gravado':
                continue
            if not only_total_not_null and data[f] == Decimal('0.0'):
                continue
            invoice_line = InvoiceLine()
            invoice_line.type = 'line'
            invoice_line.currency = currency[0]
            invoice_line.company = self.start.company
            invoice_line.invoice_type = 'in'
            invoice_line.description = None

            if invoice.tipo_comprobante in CREDIT_NOTES_TYPES:
                invoice_line.quantity = -1
            else:
                invoice_line.quantity = 1
            invoice_line.unit = unit

            if only_total_not_null:
                invoice_line.unit_price = data['total']
                invoice_line.taxes = [
                    account_config.import_invoice_not_taxed_net]
            else:
                invoice_line.unit_price = data[f]
                if f == 'neto_gravado' and party.import_invoice_tax:
                    invoice_line.taxes = [party.import_invoice_tax]
                else:
                    invoice_line.taxes = [
                        getattr(account_config, FIELDS_TAXES[f])]

            if self.start.company.purchase_taxes_expense:
                invoice_line.taxes_deductible_rate = 0

            if party.import_invoice_account_expense:
                invoice_line.account = party.import_invoice_account_expense
            else:
                invoice_line.account = account_config.get_multivalue(
                    'default_category_account_expense',
                    company=self.start.company.id)
                if not invoice_line.account:
                    raise AccountError(
                        gettext('account_invoice_import_ar'
                            '.msg_import_missing_account_expense',
                            invoice=invoice.reference))
            if invoice_line.account and not invoice_line.description:
                invoice_line.description = invoice_line.account.name
            lines.append(invoice_line)

        return lines

    def do_import_(self, action):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        InvoiceLine = pool.get('account.invoice.line')

        file_ = self.start.file_
        if not isinstance(file_, str):
            file_ = file_.decode('UTF-8')
        file_ = io.StringIO(file_)
        parsed_lines = self._parse(file_)
        invoices = []
        to_validate = []
        for line in parsed_lines:
            invoice = self._get_invoice(line)
            if invoice:
                invoice.lines = self._get_invoice_lines(line, invoice)
                invoice.save()
                invoice.update_taxes()

                # Check data
                remove_lines = False
                factor = 1
                if invoice.tipo_comprobante in CREDIT_NOTES_TYPES:
                    factor = -1
                # Facturas C: only 'total' is not null
                only_total_not_null = not any([line[f] != Decimal('0.0')
                    for f in ['neto_gravado', 'neto_no_gravado',
                        'op_exentas', 'iva']])

                if only_total_not_null:
                    if line['total'] != (invoice.total_amount * factor):
                        remove_lines = True
                else:
                    for k, v in AMOUNTS_CHECK.items():
                        # Credit: total is a positive value
                        if k == 'total' and factor == -1 and \
                                line[k] == (getattr(invoice, v) * factor):
                            continue
                        if line[k] != getattr(invoice, v):
                            remove_lines = True
                            break
                if remove_lines:
                    InvoiceLine.delete([l for l in invoice.lines])
                    invoice.save()
                    invoice.update_taxes()
                else:
                    to_validate.append(invoice)

                invoices.append(invoice)

        if to_validate:
            Invoice.validate_invoice(to_validate)
            invoices = [i for i in invoices if i not in to_validate]
        data = {'res_id': list(map(int, invoices))}
        if len(invoices) == 1:
            action['views'].reverse()
        return action, data
