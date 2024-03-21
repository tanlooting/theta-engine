from utils.option_utils import round_to
from ib_insync import *


def single_leg_bracket_order(ib, action, qty, price, SL, TP, slippage_adj = 0, parent_order_type = 'MKT', rounding = 0.05):
    """Generate bracket order for short leg
    SPX has to be rounded to nearest 0.05 if not order will not be submitted
    
    Args:
        ib: ib client
        action (str): BUY or SELL
        qty (float/ int): quantity to transact
        price (float): LMT price for limit parent order and for calculation of SL and TP
        SL (float): _description_
        TP (float): _description_
        parent_order_type (str, optional): choose between MKT or LMT only. Defaults to 'MKT'.
        rounding (float, optional): _description_. Defaults to 0.05.

    Returns:
       list of ib orders [parent, take profit (LMT), stop loss (MKT)]
    """
    bracket_orders = []
    parent_order_id =  ib.client.getReqId()
    if parent_order_type == "LMT":
        parent_order = LimitOrder(action, qty, price, orderId = parent_order_id, tif="GTC", transmit = False)
    elif parent_order_type == "MKT":
        parent_order = MarketOrder(action, qty, orderId = parent_order_id, tif="GTC", transmit = False)
    if action == "BUY":
        SL = -SL if SL is not None else None
        TP = -TP if SL is not None else None
    
    child_action = "SELL" if action == "BUY" else "BUY"
    
    # consider changing to market order
    if TP is not None:
        take_profit_order = LimitOrder(
            action = child_action,
            totalQuantity = qty,
            lmtPrice = round_to(price * (1 - TP), rounding),
            tif = "GTC",
            orderId = ib.client.getReqId(),
            transmit = False,
            parentId = parent_order_id,
        )
    else:
        take_profit_order = None
    if SL is not None:
        stop_loss_order = StopOrder(
            action = child_action,
            totalQuantity = qty,
            stopPrice = round_to(price * (1 + SL) - slippage_adj, rounding),
            tif = "GTC",
            orderId = ib.client.getReqId(),
            transmit = True,
            parentId = parent_order_id
        )
    else:
        stop_loss_order = None

    return BracketOrder(parent= parent_order, 
                        takeProfit = take_profit_order, 
                        stopLoss = stop_loss_order)


def replace_bracket_order(ib: IB, target_pos: Position, add_qty, price, SL, TP, slippage_adj = 0, parent_order_type = 'MKT', rounding = 0.05):
    """ 
    If bracket order exists, """
    target_contract= target_pos.contract
    target_contract.exchange = "SMART"
    # position.contract need an exchange information
    
    avg_price = target_pos.avgCost / float(target_pos.contract.multiplier)
    exist_qty = abs(target_pos.position)
    target_price  = (price*add_qty + avg_price*exist_qty) / (exist_qty + add_qty)
    # test this (replace duplicated position)
    action = "SELL" if target_pos.position < 0 else "BUY"
    
    prev_bracket_orders = []
    # using openTrades need master clientId
    for t in ib.openTrades():
        if t.contract.localSymbol == target_contract.localSymbol:
            prev_bracket_orders.append(t)
            # cancel openTrades
            ib.cancelOrder(t.order)
    child_qty = set([p.order.totalQuantity for p in prev_bracket_orders])
    assert len(child_qty) == 1
    # new parent order
    parent_order_id =  ib.client.getReqId()
    parent_order = MarketOrder(action, add_qty, orderId = parent_order_id,tif="GTC", transmit = False)
    new_child_qty = list(child_qty)[0] + add_qty

    if action == "BUY":
        SL = -SL if SL is not None else None
        TP = -TP if SL is not None else None

    child_action = "SELL" if action == "BUY" else "BUY"

    # consider changing to market order
    if TP is not None:
        take_profit_order = LimitOrder(
            action = child_action,
            totalQuantity = new_child_qty,
            lmtPrice = round_to(target_price * (1 - TP), rounding),
            tif = "GTC",
            orderId = ib.client.getReqId(),
            transmit = False,
            parentId = parent_order_id,
        )
    else:
        take_profit_order = None
    if SL is not None:
        stop_loss_order = StopOrder(
            action = child_action,
            totalQuantity = new_child_qty,
            stopPrice = round_to(target_price * (1 + SL) - slippage_adj, rounding),
            tif = "GTC",
            orderId = ib.client.getReqId(),
            transmit = True,
            parentId = parent_order_id
        )
    else:
        stop_loss_order = None

    return BracketOrder(parent= parent_order, 
                        takeProfit = take_profit_order, 
                        stopLoss = stop_loss_order)


def rel_pegged_to_primary():
    """Not implemented"""