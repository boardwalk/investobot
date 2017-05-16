#!/usr/bin/env python3
import json
import os
import requests

LOGIN_INIT_URL = 'https://login.fidelity.com/ftgw/Fas/Fidelity/RtlCust/Login/Init'
LOGIN_RESPONSE_URL = 'https://login.fidelity.com/ftgw/Fas/Fidelity/RtlCust/Login/Response'
POSITIONS_URL = 'https://oltx.fidelity.com/ftgw/fbc/ofpositions/snippet/portfolioPositions'

class InvestoBot(object):
    def __init__(self, config):
        self.config = config
        self.session = requests.Session()

    def login(self):
        resp = self.session.get(LOGIN_INIT_URL)
        resp.raise_for_status()

        form = {
            'SSN': self.config['username'],
            'PIN': self.config['password'],
            'SavedIdInd': 'N'
        }
        resp = self.session.post(LOGIN_RESPONSE_URL, form)
        resp.raise_for_status()
        assert 'Redirect to Default Page' in resp.text

    def get_positions(self):
        query = {
            'ALL_ACCTS': 'Y',
            'SAVE_SETTINGS_WASH_SALE': 'N',
            'UNADJUSTED_COST_BASIS_INFORMATION': '',
            'EXCLUDE_WASH_SALE_IND': '',
            'SHOW_FOREIGN_CURRENCY': '',
            'REFRESH_DATA': 'N',
            'REPRICE_FROM_CACHE': 'Y',
            'ALL_POS': 'Y',
            'ALL_ACCTS': 'Y',
            'TXN_SORT_ORDER': '0',
            'TABLE_SORT_ORDER': '0',
            'TABLE_SORT_DIRECTION': 'A',
            'SAVE_SETTINGS': 'N',
            'pf': 'N',
            'CSV': 'Y',
            'TXN_COLUMN_SORT_JSON_INFO': '',
            'SORT_COL_IND': '',
            'IS_ACCOUNT_CHANGED': 'Y',
            'DISP_FULL_DESC': 'Y',
            'FONT_SIZE':'S',
            'viewBy': '',
            'displayBy': '',
            'group-by': '0',
            'desc': '0',
            'NEXTGEN': 'Y',
            'ACTION': '',
            'SHOW_FULL_SECURITY_NAME': 'N',
            'REQUESTED_SHOW_TYPE_IND': 'All',
            'REQUESTED_SHOW_TYPE_IND': 'Mutual Funds',
            'REQUESTED_SHOW_TYPE_IND': 'Cash',
            'REQUESTED_SHOW_TYPE_IND': 'Stocks/ETFs'
        }
        resp = self.session.get(POSITIONS_URL, params=query)
        resp.raise_for_status()
        print( resp )
        print( resp.text )

def main():
    with open(os.path.expanduser('~/.config/investobot.json')) as f:
        config = json.load(f)
    bot = InvestoBot(config)
    bot.login()
    print( bot.get_positions() )

if __name__ == '__main__':
    main()
