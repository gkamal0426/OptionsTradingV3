import logging
from accounting_manager.pnllogger.core import save_trade_history
from accounting_manager.pnllogger.merge import merge_trades
from accounting_manager.pnllogger.utils import append_trade_entry, update_close_orders
from datetime import datetime
from utils.decorators import log_exceptions

class PnLLogger:
    def __init__(self, session):
        self.tradelog = []
        self.initiate_orders = session.initiated_orders
        self.close_orders = session.closed_orders
        self.session = session
        self.trade_id = self.generate_unique_number()
    
    def generate_unique_number(self):
        now = datetime.now()
        trade_id = "T" + now.strftime("%Y%m%d%H%M%S%f")  # Includes microseconds
        return trade_id
    
    @log_exceptions
    def process(self):
        initiated_trades = merge_trades(self.initiate_orders)
        for trade in initiated_trades:
            self.tradelog.append(append_trade_entry(trade, self.trade_id, self.session.process, self.session.trade_remarks))

        closed_trades = merge_trades(self.close_orders)
        update_close_orders(self, closed_trades)

        save_trade_history(self)
        
        logging.info(f"✅ PnL Saved: \n{self.tradelog}")

        return self.tradelog
