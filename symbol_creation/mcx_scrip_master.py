import os
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from io import StringIO
from utils.decorators import log_execution, log_exceptions
from variables.start_from_here import to_start_get
import yaml

class McxScripMaster:
    def __init__(self):
        self.exchange = "mcx_fo"
        self._load_yaml_config()
        self._set_file_name_path()

    def _load_yaml_config(self):
        config_path = to_start_get("symbol_var_path")
        self.mcx_file_path = to_start_get("mcx_file_path") or None
        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
            for key, value in config.items():
                setattr(self, key, value)

        except Exception:
            logging.exception("Symbol creation YAML configuration load failed")
 

    def _set_file_name_path(self):
        today = datetime.now()
        if not self.mcx_file_path:
            logging.error(f"Invalid or missing folder path: {self.mcx_file_path}")
            return
        try:        
            self.master_file = os.path.join(self.mcx_file_path, f"mcx_scrip_master_{today.strftime('%Y-%m-%d')}.xlsx")
            self.ne_file = os.path.join(self.mcx_file_path, f"nearest_expiry_data_{today.strftime('%Y-%m-%d')}.xlsx")
            self.next_ne_file = os.path.join(self.mcx_file_path, f"next_nearest_expiry_data_{today.strftime('%Y-%m-%d')}.xlsx")
        except Exception:
            logging.exception("Exception")




    @log_exceptions
    def _get_file_name(self):
        today_str = datetime.now().strftime('%Y-%m-%d')
        first = "https://lapi.kotaksecurities.com/wso2-scripmaster/v1/prod/"
        mid = "/transformed/"
        return f"{first}{today_str}{mid}{self.exchange}.csv"

    @log_exceptions
    def _download_scrip_master_csv(self):
        url = self._get_file_name()
        try:
            response = requests.get(url)
            response.raise_for_status()
            return pd.read_csv(StringIO(response.text))
        except requests.exceptions.RequestException as e:
            logging.error(f"❌ Failed to download option chain CSV: {e}")
            return None

    def _filter_nearest_next_nearest(self, df):
        nearest_expiry = None
        sorted_expiries = sorted(df["pExpiryDate"].unique())
        nearest_expiry = sorted_expiries[0]
        next_expiry = sorted_expiries[1] if len(sorted_expiries) > 1 else None
        return nearest_expiry, next_expiry
    

    def _files_already_available(self):
        if os.path.exists(self.ne_file):
            logging.info(f"⚠️ Nearest expiry file already exists: {self.ne_file}")
            try:
                df = pd.read_excel(self.ne_file)
                records = df.to_dict(orient="records")
                logging.info(f"✅ Loaded nearest expiry file into list of dicts")
                return records
            except Exception as e:
                logging.error(f"❌ Failed to read nearest expiry file: {e}")
        else:
            logging.info(f"ℹ️ File extraction process started, will be created shortly.")
        return None

    def _get_selected_filed_Scrip_master(self):
        df = self._download_scrip_master_csv()
        if df is None:
            return None
        df.columns = df.columns.str.strip()
        #df = df[~df["pInstType"].isin(["IN", "COM"])]
        df = df[df["pInstType"].isin(["OPTFUT"])]
        if "dStrikePrice;" in df.columns:
            df.rename(columns={"dStrikePrice;": "dStrikePrice"}, inplace=True)
        if "dStrikePrice" in df.columns:
            df["dStrikePrice"] = df["dStrikePrice"] / 100
        cols = ["pSymbol", "pOptionType", "pSymbolName", "pTrdSymbol", "pExpiryDate",
                "dStrikePrice", "pExchSeg", "lLotSize", "iMaxOrderSize"]
        return df[cols]

    def _export_to_excel(self, exp_df, exp_path, text):
        if exp_df is not None and not exp_df.empty:
            exp_df.to_excel(exp_path, index=False)
            logging.info(f"✅ mcx {text} file saved to {exp_path}")
            return True
        else:
            logging.info(f"⚠️ mcx {text} file not found or empty")
            return False

    @log_exceptions
    def _nearest_expiry_data(self):
        df = self._get_selected_filed_Scrip_master()
        if df is None:
            return None
        self._export_to_excel(df, self.master_file, 'scrip master')
        nearest_expiry, next_expiry = self._filter_nearest_next_nearest(df)
        ne_df = None
        if nearest_expiry:
            ne_df = df[df["pExpiryDate"] == nearest_expiry]
            self._export_to_excel(ne_df, self.ne_file, 'nearest expiry')
        if next_expiry:
            next_df = df[df["pExpiryDate"] == next_expiry]
            self._export_to_excel(next_df, self.next_ne_file, 'next nearest expiry')
        return ne_df
    
    @log_exceptions
    def run(self):
        ne_data = self._files_already_available()
        if ne_data:
            return ne_data 
        df = self._nearest_expiry_data()
        if df is None:
            return []
        return df.to_dict(orient="records")
    

    
if __name__ == "__main__":
    downloader = McxScripMaster()
    nearest = downloader.run()
    print(nearest)   
