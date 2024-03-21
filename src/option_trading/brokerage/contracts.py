from ib_insync import *

# def us_equity_contract(ticker, sec_type = "STK", currency="USD",exchange = "SMART"):
#     contract= Contract()
#     contract.symbol = ticker
#     contract.secType = sec_type
#     contract.currency = currency
#     contract.exchange = exchange
#     return contract

# def us_index_contract(ticker, sec_type = "IND", currency = "USD", exchange = "CBOE"):
#     contract = Contract()
#     contract.symbol = ticker
#     contract.secType =sec_type
#     contract.currency = currency
#     contract.exchange = exchange
#     return contract
    
    
def specific_option_contract(localSymbol):
    try:
        con_details = localSymbol.split()
        symbol = con_details[0]
        expiry = "20"+con_details[1][:6]
        right = con_details[1][6]
        strike = float(con_details[1][7:])/1000
        return Option(symbol, expiry, strike, right, 'SMART', tradingClass = symbol)
    except:
        return None
    
    