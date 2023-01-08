# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    import_invoice_account_expense = fields.MultiValue(fields.Many2One(
        'account.account', "Import Invoice Account Expense",
        domain=[
            ('type.expense', '=', True),
            ('closed', '!=', True),
            ('party_required', '!=', True),
            ('company', '=', Eval('context', {}).get('company', -1)),
            ],
        states={
            'invisible': ~Eval('context', {}).get('company'),
            }))
    import_invoice_tax = fields.Many2One('account.tax', 'Import Invoice Tax',
        domain=[('parent', '=', None), ['OR',
            ('group', '=', None),
            ('group.kind', 'in', ['purchase', 'both'])],
            ])

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'import_invoice_account_expense':
            return pool.get('party.party.account')
        return super(Party, cls).multivalue_model(field)


class PartyAccount(metaclass=PoolMeta):
    __name__ = 'party.party.account'

    import_invoice_account_expense = fields.Many2One(
        'account.account', "Import Invoice Account Expense",
        domain=[
            ('type.expense', '=', True),
            ('closed', '!=', True),
            ('party_required', '!=', True),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'], ondelete='RESTRICT')
