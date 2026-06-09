
import logging
from symbol_creation.mcx_scrip_master import McxScripMaster
from utils.safe_variables import _int, _float
from utils.utils import epoch_to_datetime
from utils.margins import get_margin_details

class McxHandler:
    def __init__(self, application):
        self.users = getattr(application, "users", {})        
        self.app = application


    def _set_user(self, username = None):

        if not self.users:
            return None
        user = self.users.get(username, None)
        if user:
            return user
        
        return next(iter(self.users.values()), None)


    def mcx_report(self):
        try:            
            downloader = McxScripMaster()
            downloader.run()            
            return True
        except Exception as e:
            logging.exception("Exception occurred in processing")
            return False


    @staticmethod
    def _append_feed_symbol(symbol, ltp):
        return {
            "symbol":   symbol.get('symbol'),
            "token":    symbol.get('token'),
            "strike":   symbol.get("strike"),
            "tag":      symbol.get("tag", ""),
            "ltp":      ltp,
            "exchange": symbol.get("exchange"),
            "lot_size": symbol.get("lot_size", 1),
        }

    def _update_dashboard_feed(self, user):
        dashboard_feed = []
        ltp = 0
        with user.lock:
            ltp_feed = user.ltp_feed.copy()
        if user.mcx_symbols_tokens:    
            for symbol in user.mcx_symbols_tokens:
                ltp = ltp_feed.get(str(symbol["token"]), 0)
                dashboard_feed.append(self._append_feed_symbol(symbol, ltp))
        return dashboard_feed


    def mcx_dashboard_feed(self, username='client1'):
        try:            
            if not self.users:
                return {"status": 'error', "message": 'None of the clients are active currently', "symbols": [],"data": {}}

            user = self.users.get(username)
            if not user:
                return {"status": 'error', "message": f'invlid user - {username}', "symbols": [],"data": {}}

            dashboard_feed = self._update_dashboard_feed(user)
            margins = user.margins.copy() if user.margins else get_margin_details(user)

            return {"status":  "success", "symbols": dashboard_feed, "data":    margins}

        except Exception as e:
            logging.exception(f"mcx_symbols error for user - {username}")
            return {"status": 'error', "message": f'Exception - {e}', "symbols": [],"data": {}}

    @staticmethod
    def _append_load_symbols(row):
        return {
            'token': row.get('pSymbol'),
            'tag': (row.get('pOptionType') or "").upper(),
            'symbol': row.get('pTrdSymbol'),
            'strike' : row.get('dStrikePrice'),
            'exchange': row.get('pExchSeg'),
            'lot_size': row.get('lLotSize'),
            'index' : (row.get('pSymbolName') or "").upper()
        }
    
    def _set_mcx_nearest_expiry(self, mcx_nearest_expiry_data):
        try:
            nearest_expiry_epoc = _int(mcx_nearest_expiry_data[0].get("pExpiryDate", 0))                
            if nearest_expiry_epoc:
                self.app.mcx_nearest_expiry = epoch_to_datetime(nearest_expiry_epoc, "%d-%m-%Y")
        except Exception:
            self.app.mcx_nearest_expiry = ""

    def _update_mcx_load(self):
        downloader = McxScripMaster()
        mcx_nearest_expiry_data = downloader.run()
        self._set_mcx_nearest_expiry(mcx_nearest_expiry_data)
        self.app.mcx_symbols = []
        for row in mcx_nearest_expiry_data:
            self.app.mcx_symbols.append(self._append_load_symbols(row))
        self.app.mcx_load = True



    def _match_index_and_type(self, index, option_type):
        matching = []
        for row in self.app.mcx_symbols:
            if row.get('index').upper() == index.upper() and str(row.get('tag')).upper() == option_type.upper():
                matching.append(row)
        return matching

    def _final_status(self, index, option_type, matching):
        strikes = sorted({int(row.get("strike", 0)) for row in matching if row.get("strike")})
        return {
            "status":      "success",
            "index":       index,
            "option_type": option_type,
            "strikes":     strikes,
            "expiry":      self.app.mcx_nearest_expiry,
            "count":       len(strikes),
        }

    def mcx_strikes_from_index_input(self, index, option_type):
        if not index:
            return 1 
        try:
            if not self.app.mcx_load:
                self._update_mcx_load()         
            
            if not self.app.mcx_symbols:
                return 2

            matching = self._match_index_and_type(index, option_type)

            if not matching:
                return 3    

            return self._final_status(index, option_type, matching)

        except Exception as e:
            logging.exception("mcx_strikes error")
            return 4




    def _append_mcx_symbols(self, index, strike, tag, user):
        for row in self.app.mcx_symbols:
            if index == row.get('index') and tag == row.get('tag') and strike == int(row.get('strike')):
                new_row = dict(row)   
                new_row['ltp'] = 0
                user.mcx_symbols_tokens.append(new_row)
                user.subscribe([{"instrument_token": str(row.get('token')), "exchange_segment": row.get('exchange', 'mcx_fo')}])
                break



    def mcx_strike_in_symbols_tokens(self, body):
        index  = str(body.get("index", "")).strip().upper()
        strike_raw  = body.get("strike")
        tag = str(body.get("option_type", "")).strip().upper()
        username  = body.get("username", None)
        
        if not index or not strike_raw or not tag:
            return 1
        user = self._set_user(username)
        if not user:
            return 2
        try:
            strike = _int(strike_raw)
            self._append_mcx_symbols(index, strike, tag, user)
            return {
                "status":  "SUCCESS",
                "message": f"Added {strike} "
                        f"(of {index}) to MCX watchlist."
            }
        except Exception as e:
            logging.exception("mcx_add_symbol_by_strike error")
            return 3


    @staticmethod
    def _delete_symbol(user, symbol):
        user.mcx_symbols_tokens[:] = [
            s for s in user.mcx_symbols_tokens
            if s.get("symbol") !=symbol
        ]

        

    def mcx_symbol_deletion(self, body):
        symbol  = body.get("symbol", None)
        if not symbol:
            return 1

        username = body.get('username', None)        
        user = self._set_user(username)
        if not user:
            return 2

        try:
            before = len(user.mcx_symbols_tokens)
            self._delete_symbol(user, symbol)
            removed = before - len(user.mcx_symbols_tokens)
            message = f"Removed {symbol} from MCX watchlist." if removed >0 else f"{symbol} was not in MCX watchlist."
            logging.info(message)
            return {"status":  "SUCCESS", "message": message}

        except Exception:
            logging.exception("mcx_del_symbol_by_strike error")
            return 3



