from ib_insync import *
from utils.option_utils import get_date_today

def trade_to_dict(trade: Trade):
    tdict = {
        "symbol":trade.contract.symbol,
        "strike":trade.contract.strike,
        "right":trade.contract.right,
        "expiry":trade.contract.lastTradeDateOrContractMonth,
        "localsymbol":trade.contract.localSymbol,
        "orderid": trade.order.orderId,
        "action":trade.order.action,
        "ordertype": trade.order.orderType,
        "totalQty": trade.order.totalQuantity,
        "orderstatus": trade.orderStatus.status,    
        "filled": trade.orderStatus.filled,
        "avgFillPrice": trade.orderStatus.avgFillPrice,
        "remaining":trade.orderStatus.remaining,
    }
    return tdict
    
def order_to_dict(order: Order):
    raise NotImplementedError

def is_market_open_today(ib, underlying) -> bool:
    """Req contract details (liquidHours) return the following string
        20090507:0700-1830,1830-2330;20090508:CLOSED"""
    today = get_date_today()
    trading_days = ib.reqContractDetails(underlying)[0].liquidHours
    trading_days_dict = {d.split(':')[0]:d.split(':')[1] for d in trading_days.split(';')}
    for k,v in trading_days_dict.items():
        if (today in k) and (v == "CLOSED"):
            return False
    return True