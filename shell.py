#!/usr/bin/env python

import cmd, json, re, math
import pprint
from Robinhood import Robinhood
from terminaltables import SingleTable
from colorclass import Color
from blessed import Terminal
from textwrap import wrap
from config import USERNAME, PASSWORD, CHALLENGE_TYPE

"""
RobinhoodShell builds on Robinhood *unofficial* python library
to create a command line interface for interacting with Robinhood

* `l` : Lists your current portfolio
* `lo` : Lists your current portfolio's options
* `b <symbol> <quantity> <price>` : Submits a limit order to buy <quantity> stocks of <symbol> at <price>
* `s <symbol> <quantity> <price>` : Submits a limit order to sell <quantity> stocks of <symbol> at <price>
* `q <symbol>` : Get quote (current price) for symbol
* `q <symbol> <call/put> <strike_price> <(optional) expiration_date YYYY-mm-dd>` : Get quote for option, all expiration dates if none specified
* `o` : Lists all open orders
* `c <id>` : Cancel an open order identified by <id> [<id> of a open order can be got from output of `o`]
* `bye` : Exit the shell
"""

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

    # Auth file
    auth_file = 'auth.data'

    # List of stocks in watchlist
    watchlist = []

    def _save_auth_data(self):
        auth_data = {}
        auth_data['device_token'] = self.trader.device_token
        auth_data['auth_token'] = self.trader.auth_token
        auth_data['refresh_token'] = self.trader.refresh_token
        open(self.auth_file, 'w').write(json.dumps(auth_data))

    def __init__(self):
        cmd.Cmd.__init__(self)
        self.trader = Robinhood()

        # Robinhood now uses 2FA
        # The workflow we use is as follows
        # If we find auth token in auth.data - try to see if it still works
        # If yes, continue
        # If no, try to refresh the token using refresh token
        # If it still fails, we need to relogin with 2FA
        try:
            data = open(self.auth_file).read()
            auth_data = json.loads(data)
            if 'auth_token' in auth_data:
              self.trader.device_token = auth_data['device_token']
              self.trader.auth_token = auth_data['auth_token']
              self.trader.refresh_token = auth_data['refresh_token']
              self.trader.headers['Authorization'] = 'Bearer ' + self.trader.auth_token
              try:
                self.trader.user()
              except:
                del self.trader.headers['Authorization']
                self.trader.relogin_oauth2()
                self._save_auth_data()
        except:
            challenge_type = 'email'
            if CHALLENGE_TYPE == 'sms':
              challenge_type = 'sms'
            self.trader.login(username = USERNAME, password = PASSWORD, challenge_type = challenge_type)
            self._save_auth_data()

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
        t = Terminal()
        portfolio = self.trader.portfolios()
        if portfolio['extended_hours_equity']:
            equity =  float(portfolio['extended_hours_equity'])
        else:
            equity =  float(portfolio['equity'])

        eq = '%.2f' % equity
        previous_close = float(portfolio['adjusted_equity_previous_close'])
        change = equity - previous_close
        change_pct =  '%.2f' % (change/previous_close * 100.0)

        # format
        change = "{:.2f}".format(change)

        # colorize
        change_pct = color_data(change_pct)
        change = color_data(change)

        account_details = self.trader.get_account()
        if 'margin_balances' in account_details:
            buying_power = account_details['margin_balances']['unallocated_margin_cash']

        account_table = SingleTable([['Portfolio Value','Change','Buying Power'],[eq, change+' ('+change_pct+'%)', buying_power]],'Account')
        print((account_table.table))

        # Load Stocks
        positions = self.trader.securities_owned()
        instruments = [position['instrument'] for position in positions['results']]
        symbols = [self.get_symbol(position['instrument']) for position in positions['results']]

        market_data = self.trader.get_stock_marketdata(instruments)

        table_data = []
        table_data.append(["Symbol", "Last", "Shares", "Equity", "Avg Cost", "Return" , "Day", "EquityChange", "Day %"])

        i = 0
        for position in positions['results']:
            quantity = int(float(position['quantity']))
            symbol = self.get_symbol(position['instrument'])
            price = market_data[i]['last_trade_price']
            total_equity = float(price) * quantity
            buy_price = float(position['average_buy_price'])
            p_l_numerical = total_equity - (buy_price * quantity)
            p_l = "{:.2f}".format(p_l_numerical)
            total_equity = "{:.2f}".format(total_equity)
            buy_price = "{:.2f}".format(buy_price)
            day_change_numerical = float(market_data[i]['last_trade_price']) - float(market_data[i]['previous_close'])
            day_change = "{:.2f}".format(day_change_numerical)
            day_change_q_val_numerical = float(quantity) * float(day_change_numerical)
            day_change_q_val = "{:.2f}".format(day_change_q_val_numerical)
            day_change_pct_numerical = float(day_change_numerical) / float(market_data[i]['previous_close']) * 100
            day_change_pct = "{:.2f}".format(day_change_pct_numerical)
            price = "{:.2f}".format(float(price))

            table_data.append([
                symbol,
                price,
                quantity,
                total_equity,
                buy_price,
                color_data(p_l),
                color_data(day_change),
                color_data(day_change_q_val),
                color_data(day_change_pct)
                ])
            i += 1

        table = SingleTable(table_data,'Portfolio')
        table.inner_row_border = True
        table.justify_columns = {0: 'center' }

        print((table.table))

    def do_lo(self, arg):
        'Lists current options portfolio'
        # Load Options
        options_t_data=[]
        option_positions = self.trader.options_owned()
        options_table = SingleTable(options_t_data,'Options')
        options_table.inner_row_border = True
        options_table.justify_columns = {0: 'center' }
        options_t_data.append(["Symbol","Type","Experation","Strike", "Price", "QTY", "Equity", "Cost", "Total Return","Today"])

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
            # skip expired  -- verify when it changes state day of or, after market close on expieration
            if option_data['state'] == "expired":
                continue
            expiration_date = option_data['expiration_date']
            strike = float(option_data['strike_price'])
            type = option_data['type']
            symbol = op['chain_symbol']
            option_type = str(type).upper()
            expiration = expiration_date
            strike_price = '$'+str(strike)
            info = self.trader.get_option_marketdata(instrument)
            last_price = float(info['adjusted_mark_price'])
            total_equity = (100 * last_price) * quantity
            change = total_equity - (float(cost) * quantity)
            change_pct = '{:04.2f}'.format(change / float(cost) * 100)
            day_change = float(info['adjusted_mark_price']) - float(info['previous_close_price'])
            day_pct = '{:04.2f}'.format((day_change / float(info['previous_close_price']) ) * 100)
            # format after calc
            day_change = "{:.3f}".format(day_change)
            options_t_data.append([
                symbol,option_type,
                expiration,
                strike_price ,
                last_price,
                quantity,
                total_equity,
                cost,
                color_data(change) +' ('+ color_data(change_pct) +'%)',
                color_data(day_change) +' ('+ color_data(day_pct) +'%)'
                ])

        print((options_table.table))

    def do_w(self, arg):
        'Show watchlist w \nAdd to watchlist w a <symbol> \nRemove from watchlist w r <symbols>'
        parts = re.split('\W+',arg.upper())

        if len(parts) >= 2:
            if parts[0] == 'A':
                for p in parts[1:]:
                    if p not in self.watchlist:
                        self.watchlist.append(p.strip())
            if parts[0] == 'R':
                self.watchlist = [r for r in self.watchlist if r not in parts[1:]]
            print("Done")
        else:
            watch_t_data=[]
            watch_table = SingleTable(watch_t_data,'Watch List')
            watch_table.inner_row_border = True
            watch_table.justify_columns = {0: 'center', 1: 'center', 2: 'center', 3:'center',4: 'center'}
            watch_t_data.append(["Symbol","Ask Price", "Open", "Today", "%"])

            if len(self.watchlist) > 0:
                instruments = [self.get_instrument(s)['url'] for s in
                        self.watchlist]
                raw_data = self.trader.get_stock_marketdata(instruments)
                quotes_data = {}
                for quote in raw_data:
                    day_change = float(quote['last_trade_price']) - float(quote['previous_close'])
                    day_change_pct = '{:05.2f}'.format(( day_change / float(quote['previous_close']) ) * 100)
                    watch_t_data.append([
                        quote['symbol'],
                        '{:05.2f}'.format(float(quote['last_trade_price'])),
                        '{:05.2f}'.format(float(quote['previous_close'])),
                        color_data(day_change),
                        color_data(day_change_pct)
                        ])
                print((watch_table.table))
            else:
                print("Watchlist empty!")

    def do_b(self, arg):
        'Buy stock b <symbol> <quantity> <price>'
        parts = arg.split()
        if len(parts) >= 2 and len(parts) <= 3:
            symbol = parts[0].upper()
            quantity = parts[1]
            if len(parts) == 3:
                price = float(parts[2])
            else:
                price = 0.0

            stock_instrument = self.get_instrument(symbol)
            if not stock_instrument['url']:
                print("Stock not found")
                return

            res = self.trader.place_buy_order(stock_instrument, quantity, price)

            if not (res.status_code == 200 or res.status_code == 201):
                print("Error executing order")
                try:
                    data = res.json()
                    if 'detail' in data:
                        print(data['detail'])
                except:
                    pass
            else:
                print("Done")
        else:
            print("Bad Order")

    def do_s(self, arg):
        'Sell stock s <symbol> <quantity> <?price>'
        parts = arg.split()
        if len(parts) >= 2 and len(parts) <= 3:
            symbol = parts[0].upper()
            quantity = parts[1]
            if len(parts) == 3:
                price = float(parts[2])
            else:
                price = 0.0

            stock_instrument = self.get_instrument(symbol)
            if not stock_instrument['url']:
                print("Stock not found")
                return

            res = self.trader.place_sell_order(stock_instrument, quantity, price)

            if not (res.status_code == 200 or res.status_code == 201):
                print("Error executing order")
                try:
                    data = res.json()
                    if 'detail' in data:
                        print(data['detail'])
                except:
                    pass
            else:
                print("Done")
        else:
            print("Bad Order")

    def do_sl(self, arg):
        'Setup stop loss on stock sl <symbol> <quantity> <price>'
        parts = arg.split()
        if len(parts) == 3:
            symbol = parts[0].upper()
            quantity = parts[1]
            price = float(parts[2])

            stock_instrument = self.trader.instruments(symbol)[0]
            res = self.trader.place_stop_loss_order(stock_instrument, quantity, price)

            if not (res.status_code == 200 or res.status_code == 201):
                print("Error executing order")
                try:
                    data = res.json()
                    if 'detail' in data:
                        print(data['detail'])
                except:
                    pass
            else:
                print("Done")
        else:
            print("Bad Order")

    def do_o(self, arg):
        'List open orders'
        open_orders = self.trader.get_open_orders()
        if open_orders:
            open_t_data=[]
            open_table = SingleTable(open_t_data,'open List')
            open_table.inner_row_border = True
            open_table.justify_columns = {0: 'center', 1: 'center', 2: 'center', 3:'center',4: 'center'}
            open_t_data.append( ["index", "symbol", "price", "quantity", "type", "id"])

            index = 1
            for order in open_orders:

                if order['trigger'] == 'stop':
                    order_price = order['stop_price']
                    order_type  = "stop loss"
                else:
                    order_price = order['price']
                    order_type  = order['side']+" "+order['type']

                open_t_data.append([
                    index,
                    self.get_symbol(order['instrument']),
                    order_price,
                    int(float(order['quantity'])),
                    order_type,
                    order['id'],
                ])
                index += 1

            print((open_table.table))
        else:
            print("No Open Orders")

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
                print("Bad index")
                return

        try:
            self.trader.cancel_order(order_id)
            print("Done")
        except Exception as e:
            print("Error executing cancel")
            print(e)

    def do_ca(self, arg):
        'Cancel all open orders'
        open_orders = self.trader.get_open_orders()
        for order in open_orders:
            try:
                self.trader.cancel_order(order['id'])
            except Exception as e:
                pass
        print("Done")

    def do_news(self,arg,show_num=5):
        if len(arg) == 0:
            print("Missing symbol")
        else:
            news_data = self.trader.get_news(arg.upper())

            if news_data['count'] == 0:
                print("No News available")
                return

            for x in range(0,show_num):
                news_box(news_data['results'][x]['source'], news_data['results'][x]['published_at'], news_data['results'][x]['summary'], news_data['results'][x]['title'],news_data['results'][x]['url'])

    def do_mp(self, arg):
        'Buy as many shares possible by defined max dollar amount:  mp <symbol> <max_spend> <?price_limit>'
        parts = arg.split()
        if len(parts) >= 2 and len(parts) <= 3:
            symbol = parts[0].upper()
            #quantity = parts[1]
            spend = parts[1]
            if len(parts) == 3:
                print("Parts: 3")
                price_limit = float(parts[2])
            else:
                price_limit = 0.0

            try:
                cur_data = self.trader.quote_data(symbol)
                last_price = cur_data['last_trade_price']
            except:
                print("Invalid Ticker?")
                pass
                return

            # quote['last_trade_price']
            quantity = int(math.floor(float(spend) / float(last_price)))
            print(("\nBuying %s\n Max Spend: %s\nQTY: %s\n Current Price: %s\nMax Price: %s\n" % (symbol,spend, quantity, last_price, price_limit)))

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
        'Get detailed quote for stock: q <symbol(s)>'

        symbols = re.split('\W+',arg.upper())

        if len(arg) == 0:
            print("Missing symbol(s)")
        else:
            instruments = [self.get_instrument(s)['url'] for s in symbols]
            raw_data = self.trader.get_stock_marketdata(instruments)
            quotes_data = {}
            quote_t_data=[]
            quote_table = SingleTable(quote_t_data,'Quote List')
            quote_table.inner_row_border = True
            quote_table.justify_columns = {0: 'center', 1: 'center', 2: 'center', 3:'center',4: 'center'}
            quote_t_data.append(["Symbol", "Current Price", "Open","Change", "Ask","Bid"])
            for quote in raw_data:
                if not quote:
                    continue
                day_change = float(quote['last_trade_price']) - float(quote['previous_close'])
                day_change_pct = ( day_change / float(quote['previous_close']) ) * 100
                ask_price = '{:05.2f}'.format(float(quote['ask_price']))
                ask_size = quote['ask_size']
                bid_price = '{:05.2f}'.format(float(quote['bid_price']))
                bid_size  = quote['bid_size']
                quote_t_data.append([
                    quote['symbol'],
                    '{:05.2f}'.format(float(quote['last_trade_price'])),
                    '{:05.2f}'.format(float(quote['previous_close'])),
                    color_data(day_change)+' ('+color_data('{:05.2f}'.format(day_change_pct))+'%)',
                    str(ask_price)+' x '+str(ask_size),
                    str(bid_price)+' x '+str(bid_size)
                    ])
            print((quote_table.table))

    def do_qq(self, arg):
        'Get quote for stock q <symbol> or option q <symbol> <call/put> <strike> <(optional) YYYY-mm-dd>'
        arg = arg.strip().split()
        try:
            symbol = arg[0].upper()
        except:
            print("Please check arguments again. Format: ")
            print("Stock: q <symbol>")
            print("Option: q <symbol> <call/put> <strike> <(optional) YYYY-mm-dd>")
        type = strike = expiry = None
        if len(arg) > 1:
            try:
                type = arg[1]
                strike = arg[2]
            except Exception as e:
                print("Please check arguments again. Format: ")
                print("q <symbol> <call/put> <strike> <(optional) YYYY-mm-dd>")

            try:
                expiry = arg[3]
            except:
                expiry = None

            arg_dict = {'symbol': symbol, 'type': type, 'expiration_dates': expiry, 'strike_price': strike, 'state': 'active', 'tradability': 'tradable'};
            quotes = self.trader.get_option_quote(arg_dict);

            qquote_t_data=[]
            qquote_table = SingleTable(qquote_t_data,'Quote List')
            qquote_table.inner_row_border = True
            qquote_table.justify_columns = {0: 'center', 1: 'center'}
            qquote_t_data.append(['expiry', 'price'])

            for row in quotes:
                qquote_t_data.append(row)

            print((qquote_table.table))
        else:
            try:
                self.trader.print_quote(symbol)
            except:
                print("Error getting quote for:", symbol)

    def do_bye(self, arg):
        open(self.instruments_cache_file, 'w').write(json.dumps(self.instruments_cache))
        open(self.watchlist_file, 'w').write(json.dumps(self.watchlist))
        self._save_auth_data()
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

def color_data(value):
    if float(value) > 0:
        number = Color('{autogreen}'+str(value)+'{/autogreen}')
    elif float(value) < 0:
        number = Color('{autored}'+str(value)+'{/autored}')
    else:
        number = str(value)

    return number

def news_box(news_src,news_date,news_summary,news_title,news_url):
    news_data = []
    news_table = SingleTable(news_data)
    news_table.inner_row_border = True
    news_data.append(['Title',news_src+': '+news_title+' @ '+news_date])
    display_summary = '\n'.join(wrap(news_summary,80))
    news_data.append(['Summary',display_summary])
    news_data.append(['Link', news_url])

    print((news_table.table))

def parse(arg):
    'Convert a series of zero or more numbers to an argument tuple'
    return tuple(map(int, arg.split()))

if __name__ == '__main__':
    RobinhoodShell().cmdloop()
