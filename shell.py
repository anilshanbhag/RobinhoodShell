#!/usr/bin/env python

import cmd, json, re, math
import pprint
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

    # nytime = parser.parse('2018-06-15T23:14:15Z').astimezone(to_zone)
    # from dateutil import parser

    # ----- basic commands -----
    def do_l(self, arg):
        'Lists current portfolio'
        portfolio = self.trader.portfolios()
        if portfolio['extended_hours_equity']:
            equity =  float(portfolio['extended_hours_equity'])
        else:
            equity =  float(portfolio['equity'])

        print 'Equity Value: %.2f' % equity
        previous_close = float(portfolio['adjusted_equity_previous_close'])
        change = equity - previous_close
        print '%s%.2f Today (%.2f%%)' % (('+' if change > 0 else ''), change, change/previous_close * 100.0)

        account_details = self.trader.get_account()
        if 'margin_balances' in account_details:
            print 'Buying Power:', account_details['margin_balances']['unallocated_margin_cash']

        # Load Stocks
        positions = self.trader.securities_owned()
        symbols = [self.get_symbol(position['instrument']) for position in positions['results']]

        quotes_data = {}
        if len(symbols) > 0:
            raw_data = self.trader.quotes_data(symbols)
            for quote in raw_data:
                quotes_data[quote['symbol']] = quote
                if quote['last_extended_hours_trade_price']:
                    price = quote['last_extended_hours_trade_price']
                else:
                    price = quote['last_trade_price']

        table = BeautifulTable()
        table.top_border_char = '='
        table.bottom_border_char = '='
        table.header_seperator_char = '='
        table.column_seperator_char = ':'

        table.column_headers = ["symbol", "current price", "qty", "total equity", "cost basis", "p/l" , "day change", "val change", "day %"]

        for position in positions['results']:
            quantity = int(float(position['quantity']))
            symbol = self.get_symbol(position['instrument'])
            price = quotes_data[symbol]['last_trade_price']
            total_equity = float(price) * quantity
            buy_price = float(position['average_buy_price'])
            p_l = total_equity - buy_price * quantity
            day_change = float(quotes_data[symbol]['last_trade_price']) - float(quotes_data[symbol]['previous_close'])
            day_change_q_val = '{:04.2f}'.format(quantity * day_change)
            day_change_pct = '{:04.2f}'.format(float( ( day_change / float(quotes_data[symbol]['previous_close']) ) * 100))
            table.append_row([symbol, price, quantity, total_equity, buy_price, p_l, day_change,day_change_q_val,day_change_pct])

        print "Stocks:"
        print(table)

    def do_lo(self, arg):
        'Lists current options portfolio'
        # Load Options
        option_positions = self.trader.options_owned()
        table = BeautifulTable()
        table.column_headers = ["option", "price", "quantity", "equity", "cost basis", "p/l"]

        for op in option_positions:
            quantity = float(op['quantity'])
            if quantity == 0:
                continue

            cost = float(op['average_price'])
            if op['type'] == 'short':
                quantity = -quantity
                cost = -cost

            instrument = op['option']
            option_data = self.trader.session.get(instrument).json()
            expiration_date = option_data['expiration_date']
            strike = float(option_data['strike_price'])
            type = option_data['type']
            symbol = op['chain_symbol'] + ' ' + expiration_date + ' ' + type + ' $' + str(strike)
            info = self.trader.get_option_marketdata(instrument)
            last_price = float(info['adjusted_mark_price'])
            total_equity = (100 * last_price) * quantity
            change = total_equity - (float(cost) * quantity)
            table.append_row([symbol, last_price, quantity, total_equity, cost, change])

        print "Options:"
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
            table.top_border_char = '='
            table.bottom_border_char = '='
            table.header_seperator_char = '='
            table.column_seperator_char = ':'
            table.column_headers = ["symbol", "current price", "open","today", "%"]

            if len(self.watchlist) > 0:
                raw_data = self.trader.quotes_data(self.watchlist)
                quotes_data = {}
                for quote in raw_data:
                    day_change = float(quote['last_trade_price']) - float(quote['previous_close'])
                    day_change_pct = ( day_change / float(quote['previous_close']) ) * 100
                    table.append_row([quote['symbol'], quote['last_trade_price'], quote['previous_close'], day_change,day_change_pct])
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

            stock_instrument = self.get_instrument(symbol)
            if not stock_instrument['url']:
                print "Stock not found"
                return

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

            stock_instrument = self.get_instrument(symbol)
            if not stock_instrument['url']:
                print "Stock not found"
                return

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
            table.top_border_char = '='
            table.bottom_border_char = '='
            table.header_seperator_char = '='
            table.column_seperator_char = ':'

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

    def do_mp(self, arg):
        'Buy as many shares possible by defined max dollar amount:  mp <symbol> <max_spend> <?price_limit>'
        parts = arg.split()
        if len(parts) >= 2 and len(parts) <= 3:
            symbol = parts[0]
            #quantity = parts[1]
            spend = parts[1]
            if len(parts) == 3:
                print "Parts: 3"
                price_limit = float(parts[2])
            else:
                price_limit = 0.0

            try:
                cur_data = self.trader.quote_data(symbol)
                last_price = cur_data['last_trade_price']
            except:
                print "Invalid Ticker?"
                pass
                return

            # quote['last_trade_price']
            quantity = int(math.floor(float(spend) / float(last_price)))
            print("\nBuying %s\n Max Spend: %s\nQTY: %s\n Current Price: %s\nMax Price: %s\n" % (symbol,spend, quantity, last_price, price_limit))

   #         stock_instrument = self.trader.instruments(symbol)[0]
   #         res = self.trader.place_buy_order(stock_instrument, quantity, price)

   #         if not (res.status_code == 200 or res.status_code == 201):
   #             print "Error executing order"
   #             try:
   #                 data = res.json()
   #                 if 'detail' in data:
   #                     print data['detail']
   #             except:
   #                 pass
   #         else:
   #             print "Done"
   #     else:
   #         print "Bad Order"

    def do_q(self, arg):
        'Get detailed quote for stock: q <symblol(s)>'

        symbols = re.split('\W+',arg)

        if len(arg) == 0:
            print "Missing symbol(s)"
        else:
            raw_data = self.trader.quotes_data(symbols)
            quotes_data = {}

            table = BeautifulTable()
            table.top_border_char = '='
            table.bottom_border_char = '='
            table.header_seperator_char = '='
            table.column_seperator_char = ':'
            table.column_headers = ["symbol", "current price", "open","today", "%"]
            for quote in raw_data:
                if not quote:
                    continue
                day_change = float(quote['last_trade_price']) - float(quote['previous_close'])
                day_change_pct = ( day_change / float(quote['previous_close']) ) * 100
                table.append_row([quote['symbol'], quote['last_trade_price'], quote['previous_close'], day_change,day_change_pct])
            print(table)

    def do_qq(self, arg):
        'Get quote for stock q <symbol> or option q <symbol> <call/put> <strike> <(optional) YYYY-mm-dd>'
        arg = arg.strip().split()
        try:
            symbol = arg[0];
        except:
            print "Please check arguments again. Format: "
            print "Stock: q <symbol>"
            print "Option: q <symbol> <call/put> <strike> <(optional) YYYY-mm-dd>"
        type = strike = expiry = None
        if len(arg) > 1:
            try:
                type = arg[1]
                strike = arg[2]
            except Exception as e:
                print "Please check arguments again. Format: "
                print "q <symbol> <call/put> <strike> <(optional) YYYY-mm-dd>"

            try:
                expiry = arg[3]
            except:
                expiry = None

            arg_dict = {'symbol': symbol, 'type': type, 'expiration_dates': expiry, 'strike_price': strike, 'state': 'active', 'tradability': 'tradable'};
            quotes = self.trader.get_option_quote(arg_dict);
            table = BeautifulTable();
            table.column_headers = ['expiry', 'price']

            for row in quotes:
                table.append_row(row)

            print table
        else:
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

    def get_instrument(self, symbol):
        if not symbol in self.instruments_cache:
            instruments = self.trader.instruments(symbol)
            for instrument in instruments:
                self.add_instrument(instrument['url'], instrument['symbol'])

        url = ''
        if symbol in self.instruments_cache:
            url = self.instruments_cache[symbol]

        return { 'symbol': symbol, 'url': url }

    def add_instrument_from_url(self, url):
        data = self.trader.get_url(url)
        if 'symbol' in data:
            symbol = data['symbol']
        else:
            types = { 'call': 'C', 'put': 'P'}
            symbol = data['chain_symbol'] + ' ' + data['expiration_date'] + ' ' + ''.join(types[data['type']].split('-')) + ' ' + str(float(data['strike_price']))
        self.add_instrument(url, symbol)

    def add_instrument(self, url, symbol):
        self.instruments_cache[symbol] = url
        self.instruments_reverse_cache[url] = symbol

def parse(arg):
    'Convert a series of zero or more numbers to an argument tuple'
    return tuple(map(int, arg.split()))

if __name__ == '__main__':
    RobinhoodShell().cmdloop()
