# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import account
from . import invoice
from . import party


def register():
    Pool.register(
        account.Configuration,
        invoice.ImportInvoiceInStart,
        party.Party,
        party.PartyAccount,
        module='account_invoice_import_ar', type_='model')
    Pool.register(
        invoice.ImportInvoiceIn,
        module='account_invoice_import_ar', type_='wizard')
