# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.account.exceptions import AccountMissing


class AccountError(AccountMissing):
    pass
