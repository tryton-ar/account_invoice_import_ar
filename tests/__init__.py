# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from \
        trytond.modules.account_invoice_import_ar.tests.test import suite
except ImportError:
    from .test import suite

__all__ = ['suite']
