
import logging
import copy
import traceback
import pandas as pd
from symbol_creation.creator import CreateStrikes
from variables.start_from_here import to_start_get
import openpyxl
from utils.safe_variables import _float
from helper.handle_load_symbols import  create_url_symbols_and_tokens

def _manual_excel_strike_input():
    manual_file = to_start_get("manual_strike")
    manual_data = pd.read_excel(manual_file)
    return manual_data.to_dict(orient="records")

def _get_nearest_expiry_data(user, index):
    getfile=CreateStrikes(user, index)
    df=getfile._load_or_fetch_symbols()
    if "dStrikePrice;" in df.columns:
        df.rename(columns={"dStrikePrice;": "dStrikePrice"}, inplace=True)
    return df.to_dict(orient="records")    

def _symbols_tokens(user):
    try:
        if user.indexandtokens:
            return copy.deepcopy(user.indexandtokens)
    except Exception:
        return []    

def _tokens_list(user):
    try:
        if user.indexexchange:
            return copy.deepcopy(user.indexexchange)
    except Exception:
        return []

def _append_symbols_tokens(data1, data):
    return {"strike": data1["strike"], 
            "token": data["pSymbol"], 
            "tag": data["pOptionType"], 
            "symbol": data["pTrdSymbol"], 
            "ltp": 0, 
            "exchange": data["pExchSeg"], 
            "lot_size": data["lLotSize"]}

def map_msexcel_strikes(user, index):
    
    manual_strikes = _manual_excel_strike_input()
    nearest_expiry_data = _get_nearest_expiry_data(user, index)
    symbols_tokens =_symbols_tokens(user)    
    tokens_list = _tokens_list(user)

    for data1 in manual_strikes:
        for data in nearest_expiry_data:
            if data["dStrikePrice"] ==data1["strike"] and data1["tag"].lower()== data["pOptionType"].lower():
                symbols_tokens.append(_append_symbols_tokens(data1, data))      

    for row in symbols_tokens:
        if row.get("tag") != "Index":
            tokens_list.append({"instrument_token": row.get("token"), "exchange_segment": row.get("exchange")})

    return symbols_tokens, tokens_list





class SubscribeHelper:
    def __init__(self, application):
        self.users = getattr(application, "users", {})
        self.index = getattr(application, "index", None)

    def unsubscribe_oldlist_and_subscribe_newlist(self, user, symbols_tokens, tokens_list):       
        try:
            userstatus = user.unsubscribe(user.listoftokens) # This listoftokens are the tokens already at websocket
            if userstatus:
                user.listoftokens = tokens_list # This replace the old list(already at websocket) after unsubscribe
                               
                user.subscribe(user.listoftokens) #This subscribe the new list at websocket
                user.symbolsandtokens = symbols_tokens # This needs to be replaced only after new list subscription
                create_url_symbols_and_tokens(user)
                message = f"Excel list subscribed for user {user.name}\n"
            else:
                message = f"excel list for user {user.name} not initated as unable to un-subscribe exiting list\n"
                logging.info(message)
        except Exception as e:
            message = f"🔴 Exception : {e}\n"
            logging.error(f"🔴 Exception : {e}\n")
            traceback.print_exc()
        return message


    def msexcel_subscribe(self):
        messages = []

        for user in self.users.values():
            if user:
                try:
                    symbols_tokens, tokens_list = map_msexcel_strikes(user, self.index)
                    if symbols_tokens:
                        messages.append(self.unsubscribe_oldlist_and_subscribe_newlist(user, symbols_tokens, tokens_list))
                except Exception as e:
                    logging.error(f"🔴 Exception : {e}")
                    messages.append(f"Exception {e}")
                    traceback.print_exc()
                
        return "\n".join(messages)
    



class SymbolsTokensAddition:
    def __init__(self, application):
        self.users = getattr(application, "users", {})
        self.index = getattr(application, "index", None)
        self.manual_symbols_path = to_start_get("manual_symbols")
        self.manual_strike_path =to_start_get("manual_strike")

    def _xlrow(self, strike, data):
        return [
            strike,
            data.get('pSymbol'),   
            data.get('pOptionType'),
            data.get('pTrdSymbol'),
            data.get('pExchSeg'),
            data.get('lLotSize'),
            0
        ]

    def append_tokens_n_symbols_xl(self): #CALLED FOR MAPPING STRIKE FROM EXCEL FiLE And APPENDiNG iN ANOTHER EXCELFILE
        try:

            if not self.users:
                return None
            user = next(iter(self.users.values()))
            df_strikes = pd.read_excel(self.manual_strike_path)  # use strike file here
            addition_required = df_strikes.to_dict(orient="records")
            add_symbols = []
            for data1 in addition_required:
                for data in user.nearest_expiry_data:        
                    strike = int(float(data.get('dStrikePrice')))
                    if str(data1.get('strike')) == str(strike) and data1.get('tag') == data.get('pOptionType'):
                        add_symbols.append(self._xlrow(strike, data))  

            wb = openpyxl.load_workbook(self.manual_symbols_path)  # write to symbols file
            ws = wb.active
            for row in add_symbols:
                ws.append(row)

            wb.save(self.manual_symbols_path)
            message = f"Appended {len(add_symbols)} rows to {self.manual_symbols_path}"
            logging.info(message)
            return message
        except Exception:
            logging.exception("Exception occurred while appending tokens and symbols")
            return None


    def additional_symbol_addition(self, user):
        token_to_subscribe =[]
        symbols_list = None
        try:
            symbols_data = pd.read_excel(self.manual_symbols_path)
            symbols_list = symbols_data.to_dict(orient="records")
            if not symbols_list:
                logging.info("No data found for symbols updation")
                return
            x = 0
            for data in symbols_list:
                user.symbolsandtokens.append(data)
                token_to_subscribe.append({'instrument_token' : data.get('token'),'exchange_segment' : data.get('exchange')})
                x +=1
            user.subscribe(token_to_subscribe)
            logging.info(f"Total {x} symbols added")
        except Exception as e:
            logging.exception(f"🔴 Error while fetching symbols data. Exception : ")

    # Mapping with excel file for fetching tokens are subscribe for live feed
    def additional_tokens_addition(self, user): 

        tokens_list = None
        manual_list = []
        try:
            manual_tokens = to_start_get("manual_tokens")
            manual_tokens_data = pd.read_excel(manual_tokens)
            tokens_list = manual_tokens_data.to_dict(orient="records")
            if not tokens_list:
                logging.info("No data found for tokens subscriptions")
                return
            x = 0
            for data in tokens_list:
                manual_list.append(data)
                x +=1
            logging.info(f"Total {x} tokens added")
        except Exception as e:
            logging.exception(f"🔴 Error while fetching tokens data. Exception :")

        
        if manual_list:
            user.subscribe(manual_list)
            logging.info(f"Total {x} tokens subscribed for live feed")
        else:
            logging.info("🔴 Token not found to subscribe for live feed")
        return manual_list

    def add_symbols_n_tokens(self):     #CALLED FOR ADDING DATA INSIDE TOKENS AND SYMBOLS OBJECT
        messages = []
        try:
            for user in self.users.values():
                if user:
                    self.additional_symbol_addition(user)
                    manual_list = self.additional_tokens_addition(user)
                    user.subscribe(manual_list)
                    messages.append(f"Symbols added with exiting list and tokens subscribed({user.name}) for live feed")
        except Exception as e:
            logging.exception(f"🔴 Exception ")

        return "\n".join(messages)



class UrlStrikeAddition:
    def __init__(self, application):
        self.users = getattr(application, "users", {})
        self.append_input = None

    def _append_input(self, strike, tag, data):
        return {"strike": strike,
            "token": data.get('pSymbol'),
            "tag": tag.upper(), 
            "symbol": data.get('pTrdSymbol'), 
            "ltp": 0, 
            "exchange": data.get('pExchSeg'), 
            "lot_size": data.get('lLotSize')
            }


    def _user_to_append_n_subscribe(self):
        messages = []
        for user in self.users.values():
            if user:
                inst_token = {
                    'instrument_token': str(self.append_input.get('token')), 
                    'exchange_segment': self.append_input.get('exchange')}
                user.subscribe([inst_token])
                user.symbolsandtokens.append(self.append_input)
                user.listoftokens.append(inst_token)        
                messages.append(f"\nStrike added and uploaded for live feed user - {user.name}")
        return "\n".join(messages)

    def _get_strike_details(self, strike, tag):

        if not self.users:
            return None
        user = next(iter(self.users.values()))

        for data in user.nearest_expiry_data:
            if float(strike) == float(data.get('dStrikePrice')) and tag.lower() == data.get('pOptionType').lower():
                if data.get('pSymbol') and data.get('pTrdSymbol') and data.get('pExchSeg'):
                    self.append_input=self._append_input(strike, tag, data)
                    return True
        return None

    def symbol_n_tokens_from_url_strike(self, strike, tag):
        try:        
            if not self._get_strike_details(strike, tag):
                return "❌ Error", "No user available to subscribe"
            elif not self.append_input:
                return "❌ Error", f"Unable to find {strike} in nearest expiry data"
            else:
                return "SUCCESS", self._user_to_append_n_subscribe()

        except Exception as e:
            logging.exception("Error while fetching strike")
            return "🔴 Error", f" nException while processing : {e}"



class UrlStrikeDeletion:
    def __init__(self, application):
        self.users = getattr(application, "users", {})

    def _return_dict(self, data, strike, tag):
        return (
            _float(data.get('strike')) == _float(strike)
            and data.get('tag', '').upper() == tag.upper()
        )

    def _filter_strike(self, tokens, strike, tag):
        return [d for d in tokens if not self._return_dict(d, strike, tag)]
    
    def _remove_strike(self, user, strike, tag):
        user.symbolsandtokens = self._filter_strike(user.symbolsandtokens, strike, tag)
        user.symbolsandtokens      = self._filter_strike(user.symbolsandtokens, strike, tag)
        return f"Strike deleted from live feed for user - {user.name}"

    def del_from_url_strike_input(self, strike, tag):       
        if not self.users:
            return "Error", "No active user !"

        messages = []
        try:
            for user in self.users.values():
                if user:
                    messages.append(self._remove_strike(user, strike, tag))
            
            message = "\n".join(messages)
            return "SUCCESS", message

        except Exception as e:
            logging.exception("strike delete process failed")
            return "Error", f"Exception: {type(e).__name__} - {e}"
