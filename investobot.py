#!/usr/bin/env python3
import csv
import io
import json
import os
import re
import requests

LOGIN_INIT_URL = 'https://login.fidelity.com/ftgw/Fas/Fidelity/RtlCust/Login/Init'
LOGIN_RESPONSE_URL = 'https://login.fidelity.com/ftgw/Fas/Fidelity/RtlCust/Login/Response'
POSITIONS_URL = 'https://oltx.fidelity.com/ftgw/fbc/ofpositions/snippet/portfolioPositions'
TRADE_INIT_URL = 'https://oltx.fidelity.com/ftgw/fbc/oftrade/rest/mfPlaceOrderInit'
TRADE_VERIFY_URL = 'https://oltx.fidelity.com/ftgw/fbc/oftrade/rest/mfPlaceOrderVerify'
TRADE_CONFIRM_URL = 'https://oltx.fidelity.com/ftgw/fbc/oftrade/rest/mfPlaceOrderConfirm'
HEADERS = {
    'Accept': 'application/json, text/javascript, */*; q=0.01'
}

def trim_footer(f):
    blank_seen = False
    for line in f:
        blank_seen = blank_seen or not line.strip()
        if not blank_seen: yield line

def process_position(position):
    number_fields = {
        'Quantity',
        'Last Price',
        'Last Price Change',
        'Current Value',
        'Today\'s Gain/Loss Dollar',
        'Today\'s Gain/Loss Percent',
        'Total Gain/Loss Dollar',
        'Total Gain/Loss Percent',
        'Cost Basis Per Share',
        'Cost Basis Total'
    }
    def process_field(field, value):
        if field in number_fields:
            value = float(re.sub(r'[^0-9\.]', '', value) if value != 'n/a' else 'nan')
        return value
    return {field: process_field(field, value) for field, value in position.items()}

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
        return [process_position(position) for position in csv.DictReader(trim_footer(io.StringIO(resp.text)))]

    def _trade_init(self):
        form = {
            'ACCOUNT': self.config['account'],
            'ORDER_TYPE': 'E',
            'PRODUCT': 'ANGRBE',
            'CACHE_DATA': 'N'
        }
        resp = self.session.post(TRADE_INIT_URL, form, headers=HEADERS)
        resp.raise_for_status()
        return resp.json()

    def _trade_verify(self, symbol, amount):
        form = {
            'ACCOUNT': self.config['account'],
            'FUND': 'on',
            'ORDER_TYPE': 'M',
            'SYMBOL': symbol,
            'QTY_TYPE_D': str(amount),
            'QTY': '',
            'QTY_TYPE_S': '',
            'QTY_TYPE_A': '',
            'ORDER_ACTION': 'BF',
            'ACCT_TYPE': 'C',
            'PRODUCT': 'ANGRBE',
            'FUND_NEW': ''
        }
        resp = self.session.post(TRADE_VERIFY_URL, form, headers=HEADERS)
        resp.raise_for_status()
        return resp.json()

    def _trade_confirm(self, symbol, amount, order_num):
        form = {
            'ACCOUNT': self.config['account'],
            'ACCT_TYPE': 'C',
            'QTY_TYPE': 'D',
            'QTY_TYPE_D': str(amount),
            'QTY_TYPE_S': str(amount),
            'ORDER_ACTION': 'BF',
            'SYMBOL': symbol,
            'FUND_NEW': '',
            'PRODUCT': 'ANGRBE',
            'ORDER_NUM': order_num,
            'ORDER_TYPE': 'M'
        }
        resp = self.session.post(TRADE_CONFIRM_URL, form, headers=HEADERS)
        resp.raise_for_status()
        return resp.json()

    def trade(self, symbol, amount):
        self._trade_init()
        resp = self._trade_verify(symbol, amount)
        order_num = resp['mutualFundVerify']['order']['orderNum']
        self._trade_confirm(symbol, amount, order_num)

def main():
    with open(os.path.expanduser('~/.config/investobot.json')) as f:
        config = json.load(f)
    bot = InvestoBot(config)
    bot.login()
    #print( bot.get_positions() )
    #print( bot._trade_init() )
    #print( bot._trade_verify('FUSVX', 5) )
    #print( bot.trade('FUSVX', 10) )

if __name__ == '__main__':
    main()
