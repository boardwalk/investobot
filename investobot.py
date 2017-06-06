#!/usr/bin/env python3
import argparse
import csv
import io
import json
import os
import re
import requests
import sys

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
        if field == 'Symbol':
            value = value.rstrip('*')
        elif field in number_fields:
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
            'ORDER_TYPE': 'M',
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
            'QTY_TYPE_D': '{:.2f}'.format(amount), # Yes, we must round or Fidelity will throw an error
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
            'QTY_TYPE_D': '{:.2f}'.format(amount),
            'QTY_TYPE_S': '{:.2f}'.format(amount),
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

# these might be better suited to the config file, but I don't want to lose them!
SYMBOL_GROUPS = {
    #'CORE': 'cash',
    'FBIDX': 'bonds',
    #'FCASH': 'cash',
    'FSEMX': 'midsmall_cap',
    'FSEVX': 'midsmall_cap',
    'FSGDX': 'intl',
    'FSGUX': 'intl',
    'FSITX': 'bonds',
    'FSRVX': 'real_estate',
    'FUSEX': 'large_cap',
    'FUSVX': 'large_cap',
    'FXSIX': 'large_cap',
    #'SPAXX': 'cash',
    #'TSLA': 'other'
}

GROUP_TARGETS = {
    'large_cap': 0.40,
    'midsmall_cap': 0.20,
    'intl': 0.20,
    'bonds': 0.10,
    'real_estate': 0.10
}

GROUP_SYMBOLS = {
    'large_cap': 'FUSVX',
    'midsmall_cap': 'FSEVX',
    'intl': 'FSGDX',
    'bonds': 'FSITX',
    'real_estate': 'FSRVX'
}

CASH_BUFFER = 3000

assert 0.99 < sum(GROUP_TARGETS.values()) < 1.01

ORDERS_PATH = os.path.expanduser('~/.config/investobot.orders.json')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('calculate-orders', 'execute-orders'))
    args = parser.parse_args()

    with open(os.path.expanduser('~/.config/investobot.json')) as f:
        config = json.load(f)

    bot = InvestoBot(config)
    bot.login()

    action = globals()[args.action.replace('-', '_')]
    action(bot)

def calculate_orders(bot):
    # delete orders
    try:
        os.unlink(ORDERS_PATH)
    except FileNotFoundError:
        pass

    positions = bot.get_positions()

    # calculate group_totals and grand_total
    group_totals = {}
    grand_total = 0
    for position in positions:
        symbol = position['Symbol']
        value = position['Current Value']
        if symbol not in SYMBOL_GROUPS:
            continue
        group = SYMBOL_GROUPS[symbol]
        group_totals[group] = group_totals.get(group, 0) + value
        grand_total = grand_total + value

    # calculate free_cash
    free_cash = next(position for position in positions if position['Symbol'] == 'FCASH')['Current Value'] - CASH_BUFFER

    # calculate group_buys and total_buys
    group_buys = {}
    total_buys = 0

    while total_buys < free_cash:
        target_groups = set()
        min_below_target = sys.float_info.max

        for group, total in group_totals.items():
            cur = (total + group_buys.get(group, 0.0)) / (grand_total  + total_buys)
            tgt = GROUP_TARGETS[group]
            if cur >= tgt:
                continue
            target_groups.add(group)
            min_below_target = min(min_below_target, tgt - cur)

        if target_groups:
            buy_size = min(free_cash - total_buys, min_below_target * grand_total * len(target_groups))
        else:
            target_groups = GROUP_SYMBOLS.keys()
            buy_size = free_cash - total_buys

        for group in target_groups:
            group_buys[group] = group_buys.get(group, 0.0) + buy_size / len(target_groups)

        total_buys += buy_size

    print('{:12s} {:>8s} {:>6s} {:>9s} {:>5s} {:>9s} {:>5s} {:>5s}'.format('group', 'change$', '%', 'before$', '%', 'after$', '%', 'tgt%'))
    for group, target in sorted(GROUP_TARGETS.items(), key=lambda gt: gt[1], reverse=True):
        buy = group_buys.get(group, 0.0)
        before_abs = group_totals[group]
        before_pct = before_abs / grand_total * 100
        after_abs = before_abs + buy
        after_pct = after_abs / (grand_total + total_buys) * 100
        delta_pct = after_pct - before_pct
        target_pct = GROUP_TARGETS[group] * 100
        print('{group:12s} {buy:>+8.2f} {delta_pct:>+6.2f} {before_abs:>9.2f} {before_pct:>5.2f} {after_abs:>9.2f} {after_pct:>5.2f} {target_pct:>5.2f}'
            .format(**locals()))

    # write orders
    with open(ORDERS_PATH, 'w') as f:
        json.dump(group_buys, f)

def execute_orders(bot):
    # read orders
    with open(ORDERS_PATH) as f:
        group_buys = json.load(f)

    # execute orders
    for group, amount in group_buys.items():
        bot.trade(GROUP_SYMBOLS[group], amount)

    # delete orders
    try:
        os.unlink(ORDERS_PATH)
    except FileNotFoundError:
        pass

if __name__ == '__main__':
    main()
