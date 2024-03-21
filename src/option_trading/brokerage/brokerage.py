### NOT USED
from ibapi.client import EClient
from ibapi.common import SetOfFloat, SetOfString, TickAttrib, TickerId
from ibapi.ticktype import TickType
from ibapi.wrapper import EWrapper
import pandas as pd


class TradingApp(EWrapper, EClient):
    def __init__(self, contract_event ):
        EClient.__init__(self, self)
        self.conId = 0
        self.contract_event = contract_event
        self.contracts = list()
        self.data = {}
        self.df_data = {}
        self.lastprice = {}
        self.option_chain = {} # symbol: bid, ask, underlying, OI, volume, strike, delta, gamma, vega, theta, IV
    
    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson = ""):
        print(f"Error {reqId} {errorCode} {errorString}")
    
    def tickPrice(self, reqId: TickerId, tickType: TickType, price: float, attrib: TickAttrib):
        """to split otm/itm"""
        super().tickPrice(reqId, tickType, price, attrib)
        if tickType in [1,2]:
            print(f"{reqId}: {price}")
        if tickType == 1:
            self.option_chain[reqId]["bid"] = price
        if tickType == 2:
            self.option_chain[reqId]["ask"] = price
    
    def tickSize(self, reqId, tickType: TickType, size: int):
        """
        27 call option OI
        28 put option OI
        8 volume
        """
        super().tickSize(reqId, tickType, size)
        if tickType in [8,27,28]:
            print(f"tick size: {reqId}, tickType: {tickType}, size: {size}")
        if tickType == 8:
            self.option_chain[reqId]['volume'] = size
        if tickType == 27:
            self.option_chain[reqId]['call OI'] = size
        if tickType == 28:
            self.option_chain[reqId]['put OI'] = size
    
    def tickSnapshotEnd(self, reqId: int):
        super().tickSnapshotEnd(reqId)
        print(f"{reqId} completed")


    
    def contractDetails(self, reqId, contractDetails):
        # print(f"reqID: {reqId}, symbol:{contractDetails.contract.symbol}, \
        #         date: {contractDetails.contract.lastTradeDateOrContractMonth},\
        #         strike:{contractDetails.contract.strike},\
        #         right:{contractDetails.contract.right},\
        #         multiplier: {contractDetails.contract.multiplier}")
        #self.conId = contractDetails.contract.conId
        
        details = {
                "expiry":contractDetails.contract.lastTradeDateOrContractMonth,
                "strike":contractDetails.contract.strike,
                "right":contractDetails.contract.right,
                "localSymbol": contractDetails.contract.localSymbol,
                }
        if reqId not in self.data:
            self.data[reqId] = [details]
        else:
            self.data[reqId].append(details)
            
    def contractDetailsEnd(self, reqId):
        self.df_data[reqId] = pd.DataFrame(self.data[reqId]).sort_values("expiry")
        self.contract_event.set()
    
    def securityDefinitionOptionParameter(self, reqId: int, exchange: str, underlyingConId: int, tradingClass: str, multiplier: str, expirations: SetOfString, strikes: SetOfFloat):
        """Return option chain with expirations and strikes"""
        
        super().securityDefinitionOptionParameter(reqId, exchange, underlyingConId, tradingClass, multiplier, expirations, strikes)
        self.contracts.append({
            "exchange": exchange,
            "underlying_conId": underlyingConId,
            "tradingClass": tradingClass,
            "expirations": expirations, 
            "strikes": strikes,
        })
        
    def securityDefinitionOptionParameterEnd(self, reqId: int):
        super().securityDefinitionOptionParameterEnd(reqId)
        self.contract_event.set()
        
    def tickOptionComputation(self, 
                              reqId: TickerId, 
                              tickType: TickType, 
                              tickAttrib: int, 
                              impliedVol: float, 
                              delta: float, 
                              optPrice: float, 
                              pvDividend: float, 
                              gamma: float, 
                              vega: float, 
                              theta: float, 
                              undPrice: float):
        super().tickOptionComputation(reqId, tickType, tickAttrib, impliedVol, delta, optPrice, pvDividend, gamma, vega, theta, undPrice)
        if tickType in [10,11, 13]:
            print(f"tick option computation: {reqId}, tickType: {tickType}, optPrice: {optPrice}, undprice: {undPrice}, impliedVol: {impliedVol}, delta: {delta}")
        if tickType == 13: # model computation
            self.option_chain[reqId]["delta"] = delta
            self.option_chain[reqId]["gamma"] = gamma
            self.option_chain[reqId]["vega"] = vega
            self.option_chain[reqId]["theta"] = theta
            self.option_chain[reqId]["impliedVol"] = impliedVol
            self.option_chain[reqId]['spot_price'] = undPrice
        # if tickType == 10:
        #     self.option_chain[reqId]["bid"] = optPrice
        # if tickType == 11:
        #     self.option_chain[reqId]["ask"] = optPrice
            
        

    # def get_last_price(self):
    #     return self.lastprice