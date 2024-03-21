from zoneinfo import ZoneInfo
import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
from ib_insync import *

class noChainFoundException(Exception):
    pass

def get_date_today(tz : str = "US/Eastern") -> str:
    """Return today date in yyyymmdd format"""
    dt = datetime.datetime.now(ZoneInfo(tz))
    return dt.date().strftime("%Y%m%d")


def convert_str_date(date):
    """convert string (format: 20230623) to date"""
    return datetime.datetime.strptime(date,'%Y%m%d')

def get_nearest_expiry(expiries, dte):
    """Given DTE from today, find the date from the list of expiration date"""
    date = convert_str_date(get_date_today())
    target_date = date + relativedelta(days = dte)
    nearest_date = min(expiries, key=lambda x: abs(convert_str_date(x) - target_date))
    difference = convert_str_date(nearest_date) - target_date
    return nearest_date

def round_to(n, precision):
    correction = 0.5 if n >= 0 else -0.5
    return int( n/precision+correction ) * precision

def convert_tickers_to_full_chain(tickers: list[Ticker], need_greeks = True):
    full_chain = {}
    for ticker in tickers:
        if ticker.contract.localSymbol not in full_chain:
            full_chain[ticker.contract.localSymbol] = {}
            full_chain[ticker.contract.localSymbol]['strike'] = ticker.contract.strike
            full_chain[ticker.contract.localSymbol]['right'] = ticker.contract.right
            full_chain[ticker.contract.localSymbol]['expiration'] = ticker.contract.lastTradeDateOrContractMonth
            full_chain[ticker.contract.localSymbol]['bid'] = ticker.bid
            full_chain[ticker.contract.localSymbol]['ask'] = ticker.ask
            full_chain[ticker.contract.localSymbol]['bid_size'] = ticker.bidSize
            full_chain[ticker.contract.localSymbol]['ask_size'] = ticker.askSize
            full_chain[ticker.contract.localSymbol]['volume'] = ticker.volume
            # full_chain[ticker.contract.localSymbol]['put_OI'] = ticker.putOpenInterest
            # full_chain[ticker.contract.localSymbol]['call_OI'] = ticker.callOpenInterest

            # handle missing greeks
            if ticker.modelGreeks is None:
                if need_greeks:               
                    raise noChainFoundException
                else:
                    continue
            else:
                full_chain[ticker.contract.localSymbol]['IV'] = ticker.modelGreeks.impliedVol
                full_chain[ticker.contract.localSymbol]['delta'] = ticker.modelGreeks.delta
                full_chain[ticker.contract.localSymbol]['gamma'] = ticker.modelGreeks.gamma
                full_chain[ticker.contract.localSymbol]['vega'] = ticker.modelGreeks.vega
                full_chain[ticker.contract.localSymbol]['theta'] = ticker.modelGreeks.theta
                full_chain[ticker.contract.localSymbol]['undprice'] = ticker.modelGreeks.undPrice

        else:
            continue

    return pd.DataFrame(full_chain).T.reset_index()

def dist_from_ITM(contract: Contract, und_price):
    """if +ve, it will be ITM """
    if contract.right == "P":
        return contract.strike - und_price
    elif contract.right == "C":
        return und_price - contract.strike