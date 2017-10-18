#!/usr/bin/env python

import cmd, json
from Robinhood import Robinhood
from beautifultable import BeautifulTable
from config import USERNAME, PASSWORD

class RobinhoodShell(cmd.Cmd):
    intro = 'Welcome to the Robinhood shell. Type help or ? to list commands.\n'
    prompt = '> '

    # API Object
    trader = None

    # Cache file used to store instrument cache
    instruments_cache_file = 'instruments.data'

    # Maps Symbol to Instrument URL
    instruments_cache = {}

    # Maps URL to Symbol
    instruments_reverse_cache = {}

    def __init__(self):
        cmd.Cmd.__init__(self)
        self.trader = Robinhood()
        self.trader.login(username=USERNAME, password=PASSWORD)

        try:
            data = open('instruments.data').read()
            self.instruments_cache = json.loads(data)
            for k in self.instruments_cache:
                self.instruments_reverse_cache[self.instruments_cache[k]] = k
        except:
            pass

    # ----- basic commands -----
    def do_l(self, arg):
        'Lists current portfolio'
        portfolio = self.trader.portfolios()
        print 'Equity Value:', portfolio['equity']

        account_details = self.trader.get_account()
        if 'margin_balances' in account_details:
            print 'Buying Power:', account_details['margin_balances']['unallocated_margin_cash']

        positions = self.trader.securities_owned()

        symbols = []
        buy_price_data = {}
        for position in positions['results']:
            symbol = self.get_symbol(position['instrument'])
            buy_price_data[symbol] = position['average_buy_price']
            symbols.append(symbol)

        raw_data = self.trader.quotes_data(symbols)
        quotes_data = {}
        for quote in raw_data:
            quotes_data[quote['symbol']] = quote['last_trade_price']

        table = BeautifulTable()
        table.column_headers = ["symbol", "current price", "quantity", "total equity", "cost basis", "p/l"]

        for position in positions['results']:
            quantity = int(float(position['quantity']))
            symbol = self.get_symbol(position['instrument'])
            price = quotes_data[symbol]
            total_equity = float(price) * quantity
            buy_price = float(buy_price_data[symbol])
            p_l = total_equity - buy_price * quantity
            table.append_row([symbol, price, quantity, total_equity, buy_price, p_l])

        print(table)

    def do_b(self, arg):
        'Buy stock b <symbol> <quantity> <price>'
        parts = arg.split()
        if len(parts) == 3:
            symbol = parts[0]
            quantity = parts[1]
            price = float(parts[2])

            stock_instrument = self.trader.instruments(symbol)[0]
            res = self.trader.place_buy_order(stock_instrument, quantity, price)

            if not (res.status_code == 200 or res.status_code == 201):
                print "Error executing order"
                try:
                    data = res.json()
                    if 'detail' in data:
                        print data['detail']
                except:
                    pass
            else:
                print "Done"
        else:
            print "Bad Order"

    def do_s(self, arg):
        'Sell stock s <symbol> <quantity> <price>'
        parts = arg.split()
        if len(parts) == 3:
            symbol = parts[0]
            quantity = parts[1]
            price = float(parts[2])

            stock_instrument = self.trader.instruments(symbol)[0]
            res = self.trader.place_sell_order(stock_instrument, quantity, price)

            if not (res.status_code == 200 or res.status_code == 201):
                print "Error executing order"
                try:
                    data = res.json()
                    if 'detail' in data:
                        print data['detail']
                except:
                    pass
            else:
                print "Done"
        else:
            print "Bad Order"

    def do_o(self, arg):
        'List open orders'
        open_orders = self.trader.get_open_orders()
        if open_orders:
            table = BeautifulTable()
            table.column_headers = ["symbol", "price", "quantity", "type", "id"]

            for order in open_orders:
                table.append_row([
                    self.get_symbol(order['instrument']),
                    order['price'],
                    int(float(order['quantity'])),
                    order['side'],
                    order['id'],
                ])

            print(table)
        else:
            print "No Open Orders"

    def do_c(self, arg):
        'Cancel open order c <id>'
        order_id = arg.strip()
        try:
            self.trader.cancel_order(order_id)
            print "Done"
        except Exception as e:
            print "Error executing cancel"
            print e

    def do_q(self, arg):
        'Get quote for stock q <symbol>'
        symbol = arg.strip()
        try:
            self.trader.print_quote(symbol)
        except:
            print "Error getting quote for:", symbol

    def do_bye(self, arg):
        open(self.instruments_cache_file, 'w').write(json.dumps(self.instruments_cache))
        return True

    # ------ utils --------
    def get_symbol(self, url):
        if not url in self.instruments_reverse_cache:
            self.add_instrument_from_url(url)

        return self.instruments_reverse_cache[url]

    def add_instrument_from_url(self, url):
        data = self.trader.get_url(url)
        symbol = data['symbol']
        self.instruments_cache[symbol] = url
        self.instruments_reverse_cache[url] = symbol

def parse(arg):
    'Convert a series of zero or more numbers to an argument tuple'
    return tuple(map(int, arg.split()))

if __name__ == '__main__':
    RobinhoodShell().cmdloop()
