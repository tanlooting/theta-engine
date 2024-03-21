""" 0DTE streaming app 
Ref:
https://pypi.org/project/pandas-market-calendars/
"""
import math
import sys
import datetime
from ib_insync import *
from dotenv import dotenv_values
from zoneinfo import ZoneInfo
from utils.option_utils import get_date_today, get_nearest_expiry, convert_tickers_to_full_chain, noChainFoundException
from utils.trade_utils import is_market_open_today
from brokerage.orders import single_leg_bracket_order, replace_bracket_order
from brokerage.contracts import specific_option_contract
from services.db_service import DBService
from services.logging_service import loggerService
from services.telegram_service import telegram

def find_closest_credit(df, target_credit, side = 'ask'):
    if side not in ['bid','ask']:
        return
    return df.iloc[(df[side] - target_credit).abs().argsort()[0]]

def find_closest_delta(df, target_delta = -0.15):
    return df.iloc[(df['delta'] - target_delta).abs().argsort()[0]]
    
class ninetyDTE:
    def __init__(self, auth_config, services, params):
        # strategy details
        self.today = get_date_today()
        self.params = params
        self.strategy_name = self.params['STRATEGY_NAME']
        # Other services
        self.services = services
        self.db = self.services['db']
        self.db_trades = self.db['ninety-dte-trades']
        self.logger = self.services['logger']
        self.alerts: telegram = self.services['alerts']
        # IB Client
        self.ib = IB()
        self.subscribe_events()
        self.host = auth_config['TWS_HOST']
        self.port = int(auth_config['TWS_PORT'])
        self.clientId = 0
        self.connect()

        # other params: MAX attempts
        self.replace_cancelled_orders_attempt = 3
        self.get_option_chain_attempt = 3
        self.connect_attempt = 10
        
        # symbol
        self.symbol = 'SPY'
        self.exchange = 'SMART'
        self.primary_exchange = 'ARCA'
        self.ccy = 'USD'
        self.trading_class = 'SPY'
        self.multiplier = 100
        self.underlying_contract = Stock(self.symbol, self.exchange, self.ccy, primaryExchange = self.primary_exchange)
        self.ib.qualifyContracts(self.underlying_contract)
        self.ib.reqMarketDataType(3)
        self.ib.sleep(3)
        # check market open
        if not is_market_open_today(self.ib, self.underlying_contract):
            self.logger(f"{self.strategy_name}: Not trading day today. Program skipped")
            self.stop()
            sys.exit()
            
        # States - Orders, order statuses, trades, contracts etc.
        self.filtered_contracts = dict()
        self.positions = self.ib.positions()
        self.trade_dict = dict()
        
    def connect(self):
        curr_reconnect = 0 
        delay = 30
        while True:
            try:
                self.ib.connect(self.host, self.port,self.clientId)
                if self.ib.isConnected():
                    break
            except Exception as e:
                if curr_reconnect < self.connect_attempt:
                    curr_reconnect += 1
                    self.ib.sleep(delay)
                else:
                    self.logger.error(f"Reconnect failure after {self.connect_attempt} tries")
                    sys.exit()
        
    def run(self):
        self.ib.run()
    
    def stop(self):
        self.ib.disconnect()
        self.alerts.info("Initiated disconnection from IB...")
        
    def exit_program(self):
        self.alerts.info(f"{self.strategy_name}: Program exited at market close")
        sys.exit()
    
    def subscribe_events(self):
        """subscribe to callbacks to listen to events"""
        self.ib.orderStatusEvent += self.on_order_status_event
        self.ib.disconnectedEvent += self.on_disconnection
        self.ib.positionEvent += self.on_position

    
    ##################
    # STRATEGY LOGIC #
    ##################
    def get_all_expirations(self):
            chains = self.ib.reqSecDefOptParams(self.underlying_contract.symbol, 
                                                '', 
                                                self.underlying_contract.secType, 
                                                self.underlying_contract.conId)
            chain = next(c for c in chains if c.tradingClass == self.trading_class and c.exchange == self.exchange)
            all_expirations = sorted(exp for exp in chain.expirations)
            return all_expirations
    
    def get_all_contracts(self):
        exp_list = self.get_all_expirations()
        
        short_put_expiration = get_nearest_expiry(exp_list, params['SHORT_DTE'])
        hedge_expiration = get_nearest_expiry(exp_list, params['HEDGE_DTE'])
        ## SHORT LEG
        short_cds = self.ib.reqContractDetails(
            Option(
                symbol = self.underlying_contract.symbol, 
                lastTradeDateOrContractMonth=short_put_expiration, 
                right = "P",
                exchange = self.exchange, 
                tradingClass = self.trading_class)
            )
        short_contracts = [cd.contract for cd in short_cds]
        self.short_contracts = self.ib.qualifyContracts(*short_contracts)
        self.ib.sleep(15)
        ## HEDGE LEG
        hedge_cds = self.ib.reqContractDetails(
            Option(
                symbol = self.underlying_contract.symbol, 
                lastTradeDateOrContractMonth=hedge_expiration, 
                right = "P",
                exchange = self.exchange, 
                tradingClass = self.trading_class)
            )
        hedge_contracts = [cd.contract for cd in hedge_cds]
        self.hedge_contracts = self.ib.qualifyContracts(*hedge_contracts)
        self.ib.sleep(15)
    
    
    def get_option_chain(self, contracts):
        attempts = 1
        # aggregate full chain (reattempt in 30s if failed for 3 attempts)
        while attempts <= self.get_option_chain_attempt:
            self.alerts.info(f"Attempt {attempts}: Requesting option chain...")
            tickers = self.ib.reqTickers(*contracts)
            self.ib.sleep(30)
            try:
                df = convert_tickers_to_full_chain(tickers)
            except noChainFoundException as e:
                if attempts == self.get_option_chain_attempt:
                    self.alerts.info(f"{self.strategy_name}: Missing data for tickers. Program exited after 3 attempts. Please troubleshoot market data subscription manually.")
                    sys.exit()
                self.ib.sleep(30)
                attempts += 1
            else: 
                break 
            
        return df.sort_values('strike').reset_index(drop = True)
    
    def schedule_all_tasks(self):
        """INDICATE WHAT TASKS YOU WANT TO RUN HERE"""
        # avoid PYTZ (use ZoneInfo instead)
        self.ib.schedule(datetime.datetime(int(today[:4]),int(today[4:6]), int(today[6:8]), 10, 28, 0, tzinfo =ZoneInfo("US/Eastern")),
                         self.run_strategy)        
        self.ib.schedule(datetime.datetime(int(today[:4]),int(today[4:6]), int(today[6:8]), 17, 0, 0, tzinfo =ZoneInfo("US/Eastern")), 
                         self.exit_program)
        self.alerts.info(f"{self.strategy_name}: trade scheduled!")
        
    
    def run_strategy(self):
        util.startLoop()
        # Get option chain
        self.get_all_contracts()
        self.alerts.info(f"{self.strategy_name}: Getting option chain for short leg:")
        self.short_chain_df =self.get_option_chain(self.short_contracts)
        self.alerts.info(f"{self.strategy_name}: Getting option chain for long leg (hedge):")
        self.hedge_chain_df = self.get_option_chain(self.hedge_contracts)
        
        # find SHORT and LONG contract
        self.short_put = find_closest_delta(self.short_chain_df,params['SHORT_DELTA_TARGET'])
        if abs(self.short_put['delta'] - self.params['SHORT_DELTA_TARGET']) > self.params['SHORT_DELTA_TOLERANCE']:
            self.alerts.info(f"{self.strategy_name}: No short contract found within the targeted delta range. No order placed")
            return
        
        hedge_credit_target = self.short_put['bid'] * params['HEDGE_CREDIT_TARGET'] / (params['HEDGE_RATIO'])
        self.long_put = find_closest_credit(self.hedge_chain_df, hedge_credit_target, side = 'ask')
        if abs(self.long_put['ask'] - hedge_credit_target) > self.params['HEDGE_CREDIT_TOLERANCE']:
            self.alerts.info(f"{self.strategy_name}: No long put found within the targeted credit range. No order placed.")
            return

        self.filtered_contracts = {
            "short_put": specific_option_contract(self.short_put['index']),
            "long_put": specific_option_contract(self.long_put['index']),
        }
        # Qualify contracts
        tradable_contracts = self.ib.qualifyContracts(*list(self.filtered_contracts.values()))
        if len(tradable_contracts) == 2:
            self.alerts.info(f"{self.strategy_name} Short leg found:  {self.filtered_contracts['short_put'].localSymbol} @ {self.short_put['bid']}")
            self.alerts.info(f"{self.strategy_name} Long leg found:  {self.filtered_contracts['long_put'].localSymbol} @ {self.long_put['ask']}")
        else:
            exit_msg = f"{self.strategy_name}: Incomplete contracts found. No order placed."
            self.logger.info(exit_msg)
            self.alerts.info(exit_msg)
            return
        
        # Modify or add position
 
        if self.filtered_contracts['short_put'].localSymbol in [p.contract.localSymbol for p in self.positions]:
            self.alerts.info(f"{self.strategy_name}: Contracts {self.filtered_contracts['short_put'].localSymbol} already exist in position.")
            modify_position = True
        else:
            modify_position = False
        
        # Calculate positions
        short_qty = max(math.floor(params['DAILY_PREMIUM'] / (self.short_put['bid'] * self.multiplier)),1)
        hedge_qty = short_qty * params['HEDGE_RATIO']
        
        # # Place order (if naked puts not allowed in trading account level, long has to be placed first)
        long_put_order = MarketOrder('BUY', hedge_qty)
        long_put_trade = self.ib.placeOrder(self.filtered_contracts['long_put'], long_put_order)
        self.alerts.info(f"{self.strategy_name} Order placed (Long put): {long_put_trade.order.action} {long_put_trade.order.totalQuantity} unit of {long_put_trade.contract.localSymbol}")
        
        self.trade_dict['long_put'] = long_put_trade
        while not long_put_trade.isActive():
            self.ib.waitOnUpdate()
            
        if modify_position:
            positions = [p for p in self.positions if p.contract.localSymbol == self.filtered_contracts['short_put'].localSymbol]
            assert len(positions) == 1
            target_pos = positions[0]

            short_put_bracket_orders = replace_bracket_order(ib= self.ib,
                                                             target_pos = target_pos,
                                                             add_qty = short_qty,
                                                             price = self.short_put['ask'], 
                                                             SL = params['STOPLOSS'], 
                                                             TP = params['TAKEPROFIT'],
                                                             parent_order_type = "MKT")
            

            
        else:
            short_put_bracket_orders = single_leg_bracket_order(ib = self.ib, 
                                                                    action = 'SELL', 
                                                                    qty = short_qty,
                                                                    price = self.short_put['ask'], 
                                                                    SL = params['STOPLOSS'], 
                                                                    TP = params['TAKEPROFIT'],
                                                                    parent_order_type= "LMT",
                                                                    rounding = 0.01)
        
        for i, ord in enumerate(short_put_bracket_orders):
            if ord is not None:
                bracket_trade = self.ib.placeOrder(self.filtered_contracts['short_put'], ord)
                if i == 0:
                    self.trade_dict['short_put_parent'] = bracket_trade
                    self.alerts.info(f"{self.strategy_name} Parent order placed (Short put): {bracket_trade.order.action} {bracket_trade.order.totalQuantity} unit of {bracket_trade.contract.localSymbol}")
                    self.logger.info(f"{self.strategy_name} Parent order placed (Short put): {bracket_trade.order.action} {bracket_trade.order.totalQuantity} unit of {bracket_trade.contract.localSymbol}")
                else:
                    self.trade_dict[f'short_put_child_{i}'] = bracket_trade
                    self.alerts.info(f"{self.strategy_name} Bracket order placed (Short put): {bracket_trade.order.action} {bracket_trade.order.totalQuantity} unit of {bracket_trade.contract.localSymbol}")
                    self.logger.info(f"{self.strategy_name} Bracket order placed (Short put): {bracket_trade.order.action} {bracket_trade.order.totalQuantity} unit of {bracket_trade.contract.localSymbol}")
                    
                while not bracket_trade.isActive():
                    self.ib.waitOnUpdate()
        
            
        self.alerts.info(f"{self.strategy_name}: Short put bracket order is now active")
        self.alerts.info(f"{self.strategy_name} completed at {datetime.datetime.now()}")
        
    ##################
    # EVENT HANDLERS #
    ##################

    def on_order_status_event(self, trade: Trade):
        """OrderStatus Event"""
        # if cancelled, replaces order
        if (trade.orderStatus.status == 'Cancelled') or (trade.orderStatus.status == "ApiCancelled"):
            cancel_msg = f"*Order cancelled*: {trade.order.orderId} {trade.order.action} {trade.order.totalQuantity} of {trade.contract.localSymbol}"
            self.logger.info(cancel_msg)
            self.alerts.info(cancel_msg)

        if trade.orderStatus.status == "Filled":
            # post fill messages
            fill_msg = f"*Fills*: {trade.contract.localSymbol} {trade.orderStatus.filled} unit filled at {trade.orderStatus.avgFillPrice}"
            self.logger.info(f"*Fills*: {trade.contract.localSymbol} {trade.orderStatus.filled} unit filled at {trade.orderStatus.avgFillPrice}")
            self.alerts.info(fill_msg)
            
            # update child order to match the position
            if trade.order.orderId == self.trade_dict['short_put_parent'].order.orderId:
                self.ib.sleep(5) # wait for positions to get updated
                
                pos = [p for p in self.positions if p.contract.localSymbol == trade.contract.localSymbol]
                if len(pos) > 0:
                    pos = pos[0]
                    open_trades = [t for t in self.ib.openTrades() if t.contract.localSymbol == trade.contract.localSymbol]
                    for t in open_trades:
                        if t.order.totalQuantity == abs(pos.position): # if it's the same then don't update child order
                                continue
                        self.alerts.info(f"{self.strategy_name}: {t.contract.localSymbol} Update child order qty from {t.order.totalQuantity} to {abs(pos.position)}")
                        new_order = t.order
                        new_order.totalQuantity = abs(pos.position)
                        # check this
                        new_order.transmit = True
                        self.ib.placeOrder(t.contract, new_order)
                    

            
            tdict = util.tree(trade)
            # save to database
            self.db_trades.insert_one(tdict)
    
    def on_disconnection(self):
        self.logger.warning("Disconnect Event: Attempting reconnection...")
        self.connect()

    def on_position(self, position: Position):
        self.positions = self.ib.positions()
        
if __name__ == "__main__":
    
    today = get_date_today()
    auth_config = dotenv_values(".env")
    
    # Services connection (logger, DB, telegram)
    logger = loggerService(auth_config['papertrail_host'], auth_config['papertrail_port'])
    logger.info("Ping.")
    tlg = telegram(auth_config['telegram_chatid'],auth_config['telegram_token'])
    mongodb = DBService(auth_config = auth_config, logger = logger)
    mongodb.connect()
    db = mongodb.get_database('trade-buster')
    config = db['configs'].find_one({'strategy':'90dte'})
    rest_days = mongodb.get_database('trading-utils')['trading_days_halt'].find()
  
    params = {
        'STRATEGY_NAME':"90DTE", 
        'HEDGE_RATIO': config['hedge_ratio'], # no. of hedges vs shorts
        'DAILY_PREMIUM': config['daily_premium'],
        'SHORT_DELTA_TARGET': config['short_delta_target'],
        'SHORT_DELTA_TOLERANCE': 0.03, # delta
        'HEDGE_CREDIT_TARGET': config['hedge_credit_target'], 
        'HEDGE_CREDIT_TOLERANCE':0.05, #dollar
        'SHORT_DTE': config['short_dte'],
        'HEDGE_DTE': config['hedge_dte'],
        'STOPLOSS': config['stop_loss'],
        'TAKEPROFIT': config['take_profit'],
    }
    print(params)
    services = {
        'db': db,
        'logger': logger,
        'alerts': tlg,
    }
    
    for day in rest_days:
        if today == day['date'].date().strftime("%Y%m%d"):
            tlg.warning(f"{params['STRATEGY_NAME']}: Skip trading today.")
            logger.warning(f"{params['STRATEGY_NAME']}: Skip trading today.")
            sys.exit()
            
    app = ninetyDTE(auth_config, services, params)
    
    try:
        tlg.info(f"Starting {params['STRATEGY_NAME']} script...")
        app.schedule_all_tasks() # schedule all tasks
        app.run()
    except (KeyboardInterrupt, SystemExit) as e:
        app.stop()