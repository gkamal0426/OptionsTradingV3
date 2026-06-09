import os
import logging
import pandas as pd
from datetime import datetime, timedelta
from accounting_manager.save_variable_files import savedatainexcelfile
from symbol_creation.exchange_scrip_master import nearest_expiry_data
import traceback
import time
import yaml
from variables.start_from_here import to_start_get
import copy
from utils.decorators import log_execution, log_exceptions
from variables.start_from_here import to_start_get
class CreateStrikes:

    def __init__(self, session, instrument_code, max_strikes = 30):
        self.session = session
        self.instrument_code = str(instrument_code)
        self.max_strikes = int(max_strikes)

        self._load_yaml_config()
        self._copy_index_data()

    
    def _copy_index_data(self):
        for data in self.session.index_details:
            if str(data["index"])== self.instrument_code:
                self.lotsize = data["lot_size"]
                self.exchange = data["exchange"]
                break
        try:
            self.tokens_and_symbols = copy.deepcopy(self.session.indexandtokens)
            self.tokens_list = copy.deepcopy(self.session.indexexchange)
        except Exception:
            logging.exception("Exception:")
 
    def _set_segments(self, value: dict[str, dict]) -> None:
        for name, config in value.items():
            if self.instrument_code in config["instruments"]:
                self.segment = name
                self.report_day = config.get("report_day")
                return


    def _load_yaml_config(self):
        config_path = to_start_get("symbol_var_path")
        self.segment = None
        self.report_day = None

        try:
            with open(config_path, "r") as f:
                self.config = yaml.safe_load(f)
            for key, value in self.config.items():
                if key =="segments":
                    self._set_segments(value)
                else:
                    setattr(self, key, value)
            self.rounded = self.rounding_map.get(str(self.instrument_code), None)

        except Exception as e:
            logging.exception(f"Symbol creation YAML configration load failed {e}")


    def get_file_names(self, ref_date: datetime) -> dict[str, object]:
        ex_file = None
        week_day = None
        inst = str(self.instrument_code)

        if self.segment and self.report_day is not None:
            self.exchange_segment = self.segment
            offset = (self.report_day - ref_date.weekday()) % 7
            week_day = ref_date + timedelta(days=offset)
            ex_file = f"{self.segment}.csv"
            return {"exch_file_name" : ex_file, "week_day" : week_day, "report_day" : self.report_day}

        logging.error(f"Index-{inst} is not listed in config.yaml")
        return {"exch_file_name": None, "week_day": None, "report_day": None}




    def _set_file_names(self, week_day, folderpath):
        master_file = os.path.join(folderpath, f"scrip_master_{self.instrument_code}_{week_day.strftime('%Y-%m-%d')}.xlsx")
        ne_file = os.path.join(folderpath, f"nearest_expiry_data_{self.instrument_code}_{week_day.strftime('%Y-%m-%d')}.xlsx")
        next_ne_file = os.path.join(folderpath, f"next_nearest_expiry_data_{self.instrument_code}_{week_day.strftime('%Y-%m-%d')}.xlsx")
        return master_file, ne_file, next_ne_file

    @log_exceptions
    def _load_or_fetch_symbols(self):
        folderpath = to_start_get("tokens_data_path")
        today = datetime.now()

        details = self.get_file_names(today)
        week_day = details.get('week_day', None)
        ex_file = details.get('exch_file_name', None)

        if not ex_file or not week_day:
            return None

        master_file, ne_file, next_ne_file = self._set_file_names(week_day, folderpath)
           
        if not os.path.exists(master_file):
            return nearest_expiry_data(master_file, ne_file, next_ne_file, today, self.instrument_code, ex_file)
        
        try:
            return pd.read_excel(ne_file)
        except Exception:
            return nearest_expiry_data(master_file, ne_file, next_ne_file, today, self.instrument_code, ex_file)


    @log_exceptions
    def _save_token_list(self):
        try:
            savedatainexcelfile(self.tokens_list, "options_tokens_list")
            print("file_saved")
        except Exception as e:
            logging.error(f"❌ Failed to save tokens to Excel: {e}\n Traceback: {traceback.format_exc()}")

    def _get_ltp_data(self):
        with self.session.lock:
            return self.session.ltp_feed.copy()

    def _correct_index_input(self):
        for data in self.session.index_subscribe:
            if str(data["instrument_token"]) == str(self.instrument_code):
                return True    
        logging.info(f"Invalid Index {self.instrument_code}. Please provide correct Index Code and try again")
        return False
    
    def _subscribed(self, ltp_data):
        if not ltp_data:
            self.session.subscribe(self.session.index_subscribe)
            time.sleep(1)
            return False
        return True

    def _check_ltp_updated(self, ltp_data):
        for token, ltp in ltp_data.items():
            if str(token) == str(self.instrument_code):
                self.instltp = float(ltp)
                if self.instltp >0:
                    logging.info(f"Last traded price of {self.instrument_code} is {self.instltp}. creating strikes for {self.session.name}")
                    return True   
        return False
    
    def get_index_ltp(self):

        if not self._correct_index_input():
            return False

        while self.session.index_subscribe_flag:
            ltp_data = self._get_ltp_data()
            if not self._subscribed(ltp_data):
                continue
            if self._check_ltp_updated(ltp_data):
                self.session.index_subscribe_flag = False
                return True
            
    def _append_strike(self, strike, tag):
        return {"strike": strike, 
                "token": None, 
                "tag": tag, 
                "symbol": None,
                "ltp": 0, 
                "exchange": self.exchange, 
                "lot_size": self.lotsize}

    def _strike_creation(self):
        atm_strike = round(float(self.instltp) / float(self.rounded)) * float(self.rounded)
        for i in range(self.max_strikes):
            call_strike = atm_strike + (i * self.rounded)
            put_strike = atm_strike - (i * self.rounded)
            self.tokens_and_symbols.append(self._append_strike(call_strike, "CE"))
            self.tokens_and_symbols.append(self._append_strike(put_strike, "PE"))

    @log_exceptions
    def create_strikes(self):
        indexpricestatus = self.get_index_ltp()
        if not indexpricestatus:
            logging.info(f"⚠️ Unable to fetch Last Traded price for index code {self.instrument_code}")
            return
        
        if not self.rounded:
            logging.error("Rounding value not set for instrument.")
            return

        self._strike_creation()


    @staticmethod
    def _update_symbol_records(record):
        return {
            "token": record.get("pSymbol"),
            "symbol": record.get("pTrdSymbol"),
            "exchange": record.get("pExchSeg"),
            "lot_size": record.get("lLotSize"),
        }

    @staticmethod
    def _append_token(record):
        return {
            "instrument_token": record.get("pSymbol"),
            "exchange_segment": record.get("pExchSeg"),
        }

    @log_exceptions
    def update_symbols_tokens(self, df):
        self.create_strikes()
        symbol_records = df.to_dict(orient="records")
        self.session.nearest_expiry_data = symbol_records
        for row in self.tokens_and_symbols:
            for record in symbol_records:
                if (record.get("dStrikePrice") == row["strike"]) and (record.get("pOptionType") == row["tag"]):
                    row.update(self._update_symbol_records(record))
                    self.tokens_list.append(self._append_token(record))


    #@log_execution
    @log_exceptions
    def fetch(self):
        symbols_df = self._load_or_fetch_symbols()
        if symbols_df is None or symbols_df.empty:
            logging.error("🚫 Invlaid or No symbols to process.")
            return None, None

        self.update_symbols_tokens(symbols_df)

        return self.tokens_and_symbols, self.tokens_list
