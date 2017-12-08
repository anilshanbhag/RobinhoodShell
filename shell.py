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

    # Cache file used to store instrument cache
    watchlist_file = 'watchlist.data'

    # List of stocks in watchlist
    watchlist = []

    def __init__(self):
        cmd.Cmd.__init__(self)
        self.trader = Robinhood()
        self.trader.login(username=USERNAME, password=PASSWORD)

        try:
            data = open(self.instruments_cache_file).read()
            self.instruments_cache = json.loads(data)
            for k in self.instruments_cache:
                self.instruments_reverse_cache[self.instruments_cache[k]] = k
        except:
            pass

        try:
            data = open(self.watchlist_file).read()
            self.watchlist = json.loads(data)
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

        quotes_data = {}
        if len(symbols) > 0:
            raw_data = self.trader.quotes_data(symbols)
            for quote in raw_data:
                quotes_data[quote['symbol']] = quote



        table = BeautifulTable()
        table.column_headers = ["symbol", "current price", "quantity", "total equity", "cost basis", "p/l" , "day change", "day %"]

        for position in positions['results']:
            quantity = int(float(position['quantity']))
            symbol = self.get_symbol(position['instrument'])
            price = quotes_data[symbol]['last_trade_price']
            total_equity = float(price) * quantity
            buy_price = float(buy_price_data[symbol])
            p_l = total_equity - buy_price * quantity
            day_change = float(quotes_data[symbol]['last_trade_price']) - float(quotes_data[symbol]['previous_close'])
            day_change_pct = ( day_change / float(quotes_data[symbol]['previous_close']) ) * 100
            table.append_row([symbol, price, quantity, total_equity, buy_price, p_l, day_change,day_change_pct])

        print(table)

    def do_w(self, arg):
        'Show watchlist w \nAdd to watchlist w a <symbol> \nRemove from watchlist w r <symbol>'
        parts = arg.split()
        if len(parts) == 2:
            if parts[0] == 'a':
                self.watchlist.append(parts[1].strip())
            if parts[0] == 'r':
                self.watchlist = [r for r in self.watchlist if not r == parts[1].strip()]
            print "Done"
        else:
            table = BeautifulTable()
            table.column_headers = ["symbol", "current price"]

            if len(self.watchlist) > 0:
                raw_data = self.trader.quotes_data(self.watchlist)
                quotes_data = {}
                for quote in raw_data:
                    table.append_row([quote['symbol'], quote['last_trade_price']])
                print(table)
            else:
                print "Watchlist empty!"

    def do_b(self, arg):
        'Buy stock b <symbol> <quantity> <price>'
        parts = arg.split()
        if len(parts) >= 2 and len(parts) <= 3:
            symbol = parts[0]
            quantity = parts[1]
            if len(parts) == 3:
                price = float(parts[2])
            else:
                price = 0.0

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
        'Sell stock s <symbol> <quantity> <?price>'
        parts = arg.split()
        if len(parts) >= 2 and len(parts) <= 3:
            symbol = parts[0]
            quantity = parts[1]
            if len(parts) == 3:
                price = float(parts[2])
            else:
                price = 0.0

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

    def do_sl(self, arg):
        'Setup stop loss on stock sl <symbol> <quantity> <price>'
        parts = arg.split()
        if len(parts) == 3:
            symbol = parts[0]
            quantity = parts[1]
            price = float(parts[2])

            stock_instrument = self.trader.instruments(symbol)[0]
            res = self.trader.place_stop_loss_order(stock_instrument, quantity, price)

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
            table.column_headers = ["index", "symbol", "price", "quantity", "type", "id"]

            index = 1
            for order in open_orders:

                if order['trigger'] == 'stop':
                    order_price = order['stop_price']
                    order_type  = "stop loss"
                else:
                    order_price = order['price']
                    order_type  = order['side']+" "+order['type']

                table.append_row([
                    index,
                    self.get_symbol(order['instrument']),
                    order_price,
                    int(float(order['quantity'])),
                    order_type,
                    order['id'],
                ])
                index += 1

            print(table)
        else:
            print "No Open Orders"

    def do_c(self, arg):
        'Cancel open order c <index> or c <id>'
        order_id = arg.strip()
        order_index = -1
        try:
            order_index = int(order_id)
        except:
            pass

        if order_index > 0:
            order_index = order_index - 1
            open_orders = self.trader.get_open_orders()
            if order_index < len(open_orders):
                order_id = open_orders[order_index]['id']
            else:
                print "Bad index"
                return

        try:
            self.trader.cancel_order(order_id)
            print "Done"
        except Exception as e:
            print "Error executing cancel"
            print e

    def do_ca(self, arg):
        'Cancel all open orders'
        open_orders = self.trader.get_open_orders()
        for order in open_orders:
            try:
                self.trader.cancel_order(order['id'])
            except Exception as e:
                pass
        print "Done"

    def do_q(self, arg):
        'Get quote for stock q <symbol>'
        symbol = arg.strip()
        try:
            self.trader.print_quote(symbol)
        except:
            print "Error getting quote for:", symbol

    def do_bye(self, arg):
        open(self.instruments_cache_file, 'w').write(json.dumps(self.instruments_cache))
        open(self.watchlist_file, 'w').write(json.dumps(self.watchlist))
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
