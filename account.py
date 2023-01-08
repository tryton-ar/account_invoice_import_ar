# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'

    import_invoice_taxed_net = fields.Many2One('account.tax',
        'Import Invoice Taxed Net',
        domain=[('parent', '=', None), ['OR',
            ('group', '=', None),
            ('group.kind', 'in', ['purchase', 'both'])],
            ])
    import_invoice_not_taxed_net = fields.Many2One('account.tax',
        'Import Invoice Not Taxed Net',
        domain=[('parent', '=', None), ['OR',
            ('group', '=', None),
            ('group.kind', 'in', ['purchase', 'both'])],
            ])
    import_invoice_exempt_operations = fields.Many2One('account.tax',
        'Import Invoice Exempt Operations',
        domain=[('parent', '=', None), ['OR',
            ('group', '=', None),
            ('group.kind', 'in', ['purchase', 'both'])],
            ])
