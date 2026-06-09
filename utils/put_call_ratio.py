from utils.safe_variables import _int, _float
from variables.start_from_here import to_start_get
import yaml
import logging
import time
import datetime
import pandas as pd
import os
import json
import threading

def _now():
    return datetime.datetime.now()

    
def _get_quotes(user, instrument_tokens, quote_type=''):
    if instrument_tokens and isinstance(instrument_tokens, list):
        with user.quote_lock:
            return user.client.quotes(instrument_tokens=instrument_tokens, quote_type=quote_type)
    return []

def _fetch_quotes(user, instrument_tokens, quote_type=''):
    total_token = len(instrument_tokens)
    if total_token <= 450:
        return _get_quotes(user, instrument_tokens, quote_type)

    result = []
    for i in range(0, total_token, 450):
        chunk = instrument_tokens[i:i+450]
        result.extend(_get_quotes(user, chunk, quote_type))

    return result
            

def _backup_oi_data(user, result):
    backup_oi = []
    if isinstance(result, list):    
        for d in result:
            token = str(d.get('exchange_token')) or  None
            open_int = d.get('open_int', None)
            if token and open_int:
                backup_oi.append({'token': token, 'open_int' : open_int})
        
    user.backup_oi = backup_oi
    return backup_oi

def back_up_oi(user):    
    instrument_tokens = []
    for d in user.nearest_expiry_data:
        token = d.get('pSymbol')
        exc_seg = d.get('pExchSeg')
        if token and exc_seg:
            instrument_tokens.append({"instrument_token": str(token), "exchange_segment": exc_seg})
    
    return _backup_oi_data(user, _fetch_quotes(user, instrument_tokens))

class PutCallRatio:


    def __init__(self, process_wait = 180):
        self.export_path = to_start_get("exports_path")
        self.rounding_map = {}
        self.direction = {}
        self._load_yaml_config()
        self.wait = process_wait
        self.exit_event = threading.Event()
        self.history = []
        self.excel_lock = threading.Lock()
        self.process_start = datetime.datetime.strptime(
            getattr(self, 'pcr_start', '09:15'), "%H:%M"
        ).time()
        self.process_end = datetime.datetime.strptime(
            getattr(self, 'pcr_end', '15:32'), "%H:%M"
        ).time()


    def read_oi_report(self, date = None):
        today = datetime.date.today().strftime("%Y-%m-%d")
        try:
            date_str = date or today
            if date_str == today and _now().time() <= self.process_start:
                    return None  
            
            report_path = f"{self.export_path}/OI_REPORT_{date_str}.csv"
            if os.path.exists(report_path):
                with self.excel_lock:
                    df = pd.read_csv(report_path)
                df['strikes'] = df['strikes'].apply(json.loads)
                return df.to_dict(orient="records")           
            else:
                logging.warning('unable to upload')
        except Exception as e:
            logging.exception(f"Error loading orders report: {e}")
        
        return None


    def _load_yaml_config(self) -> None:
        try:
            with open(to_start_get("symbol_var_path"), "r") as f:
                config = yaml.safe_load(f)
            for key in ("rounding_map", "direction", "pcr_start", "pcr_end"):
                if key in config:
                    setattr(self, key, config[key])
        except Exception as e:
            logging.exception(f"Symbol creation YAML configuration load failed: {e}")
 

    @staticmethod
    def _exchange(user, index):
        return next((d.get('exchange') for d in user.index_details if d.get('index') == str(index)),'nse_fo')


    def _get_quotes(self, user, strikes, index):
        sub_list = [{'instrument_token': str(index), 'exchange_segment': self._exchange(user, index)}]
        for data in strikes:
            token = data.get('token', None)            
            if token:
                sub_list.append({"instrument_token": str(token), "exchange_segment": data.get('exchange', 'nse_fo')})
        
        with user.quote_lock:
            return user.client.quotes(sub_list) if sub_list else None


    @staticmethod
    def _get_strikes(ltp, rounded, itm = 5, otm = 15):
        strikes = []
        atm_strike = round((ltp / rounded),0) * rounded
        for i in range(itm):
            strikes.append({'strike' : (atm_strike - (i * rounded)), 'tag' : 'CE' })
            strikes.append({'strike' : (atm_strike + (i * rounded)), 'tag' : 'PE'})
        for i in range(otm):
            if i==0:        continue
            strikes.append({'strike' : (atm_strike + (i * rounded)), 'tag' : 'CE' })
            strikes.append({'strike' : (atm_strike - (i * rounded)), 'tag' : 'PE'})

        return strikes


    @staticmethod
    def _get_token(user, strikes):
        for data in getattr(user, 'nearest_expiry_data', []):
            for row in strikes:
                if data.get('dStrikePrice') == row.get('strike') and data.get('pOptionType').upper()==row.get('tag'):                    
                    row['token'] = data.get('pSymbol', None)
                    row['symbol']= data.get('pTrdSymbol', None)
                    row['exchange']= data.get('pExchSeg', None)
                    row['lot_size']= data.get('lLotSize', None)
        return strikes


    @staticmethod
    def _update_oi(result, strikes):    
        for row in result:
            for data in strikes:
                if str(row.get('exchange_token')) == str(data.get('token')):    
                    data['open_int']= _int(row.get('open_int'), 0)
        return strikes


    @staticmethod
    def _get_ltp(user, index):
        with user.lock:
            ltp_data = user.ltp_feed.copy()
        return _float(ltp_data.get(index, 0))


    @staticmethod
    def _get_direction(thresholds, ratio):
        for label, limit in sorted(thresholds.items(), key=lambda x: -x[1]):
            if ratio >= limit:
                return label
        return "Unknown"


    @staticmethod
    def _get_oi_count(strikes):
        ce_oi = pe_oi = 0
        for data in strikes:
            if data.get('tag').upper() == 'CE':
                ce_oi += _int(data.get('open_int', 0))
            elif data.get('tag').upper() == 'PE':
                pe_oi += _int(data.get('open_int', 0))
        return ce_oi, pe_oi

    @staticmethod
    def _get_oi_change(strikes):
        ce_chg = pe_chg = 0
        for d in strikes:
            tag = d.get('tag', '').upper()
            chg = _int(d.get('oi_change', 0))
            if tag == 'CE': ce_chg += chg
            elif tag == 'PE': pe_chg += chg
        return ce_chg, pe_chg

    @staticmethod
    def _failure(strikes, message):
        logging.info(f"{message}. Please check the Index input")
        return {'index_ltp' : 0, 'call_oi': 0, 'put_oi': 0, 'ratio': 0, 'strikes': strikes}



    def _append_history(self, direction, strikes, ratio, pe_oi, ce_oi, ltp, sno, ce_chg=0, pe_chg=0):
        row_dict = {
            'SNo': sno,
            'time': _now().strftime("%d-%m-%Y %H:%M:%S"),
            'direction': direction,
            'index_ltp': ltp,
            'call_oi': ce_oi,
            'put_oi': pe_oi,
            'call_oi_change': ce_chg,
            'put_oi_change':  pe_chg,
            'ratio': ratio,
            'strikes': strikes,
        }
        self.history.append(row_dict)
        return row_dict


    def _print_message(self, strikes, ltp, sno):
        ce_oi, pe_oi  = self._get_oi_count(strikes)
        ce_chg, pe_chg = self._get_oi_change(strikes)
        ratio     = round(pe_oi / ce_oi, 4) if ce_oi else 0
        direction = self._get_direction(self.direction, ratio)
        logging.info(
            f"LTP- {ltp}  Call OI- {ce_oi} ({ce_chg:+})  "
            f"Put OI- {pe_oi} ({pe_chg:+})  PCR- {round(ratio*100,2)}%  Dir- {direction}"
        )
        return self._append_history(direction, strikes, ratio, pe_oi, ce_oi, ltp, sno, ce_chg, pe_chg)


    def export_report(self, new_record):
        try:
            df = pd.DataFrame([new_record])
            df['strikes'] = df['strikes'].apply(json.dumps)

            with self.excel_lock:
                df.to_csv(
                    self.file_path,
                    mode='a',
                    header=not os.path.exists(self.file_path),
                    index=False
                )
        except Exception as e:
            logging.exception(f"Orders Report export error. Exception: {e}")


    def _get_file_path(self):
            today_str = datetime.date.today().strftime("%Y-%m-%d")
            os.makedirs(self.export_path, exist_ok=True)
            return f"{self.export_path}/OI_REPORT_{today_str}.csv"



    @staticmethod
    def _target_time(processtime: datetime.time):
        return datetime.datetime.combine(_now().date(), processtime)


    @staticmethod
    def pcr_end_time(end_time):
        return _now() >= end_time

    @staticmethod
    def pcr_start_timewait(start_time):
        now = _now()
        if now <= start_time:
            logging.info(f"PCR process will start at {start_time}")
            time.sleep((start_time - now).total_seconds())


    @staticmethod
    def _strikes(user, strikes):
        for data in strikes:
            for row in getattr(user, 'backup_oi', []):
                if str(data.get('token')) == str(row.get('token')):   # ← str() on both
                    data['backup_oi'] = _int(row.get('open_int', 0))
                    data['oi_change'] = _int(data.get('open_int', 0)) - _int(row.get('open_int', 0))
                    break
        return strikes


    def run(self, index, user, itm = 5, otm = 15):

        self.file_path = self._get_file_path() 
        self.pcr_start_timewait(self._target_time(self.process_start))
        sno =1
        while True:
            if self.pcr_end_time(self._target_time(self.process_end)):
                logging.info("PCR endtime reached.")
                break
            if self.exit_event.is_set():
                logging.info("PCR loop stopped by signal")
                break                    
            try:
                ltp = self._get_ltp(user, index)
                if not ltp or ltp <0.05:     
                    self._failure(None, 'Unabe to fetch ltp')
                else:                
                    strikes = self._get_strikes(ltp, _float(self.rounding_map.get(index, 0)), itm, otm)
                    result = self._get_quotes(user, self._get_token(user, strikes), index)
                    if not isinstance(result, list):  
                        self._failure(strikes, 'Tokens not found')
                    
                    else:
                        strikes = self._update_oi(result, strikes)
                        strikes = self._strikes(user, strikes) 
                        new_record = self._print_message(strikes, ltp, sno)
                        self.export_report(new_record)
            except Exception as e:
                logging.error(f"error while getting put call ratio: {repr(e)}")
            
            
            if self.exit_event.wait(self.wait):
                logging.info("PCR loop interrupted during sleep")
                break

            sno += 1

        logging.info(f"Process completed. file exported on path, {self.file_path}")


    

