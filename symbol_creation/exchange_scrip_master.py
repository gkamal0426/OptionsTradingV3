import os
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from io import StringIO
from accounting_manager.save_variable_files import savedatainexcelfile

from utils.decorators import log_execution, log_exceptions

@log_execution
@log_exceptions
def download_scrip_master_csv(today, ex_file):
    url = f"https://lapi.kotaksecurities.com/wso2-scripmaster/v1/prod/{today.strftime('%Y-%m-%d')}/transformed/{ex_file}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return pd.read_csv(StringIO(response.text))
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Failed to download option chain CSV: {e}")
        return None


@log_execution
@log_exceptions
def nearest_expiry_data(filepath, nefilepath, nextfilepath, today, inst, ex_file):
    if not ex_file:
        logging.info(f"Invalid instrument token {inst}, unable to get scrip file name")
        return None
    df = download_scrip_master_csv(today, ex_file)
    if df is None:
        return None
    df.columns = df.columns.str.strip()
    expiry_limit = int((today + timedelta(days=8)).timestamp())
    df = df[(df["pExpiryDate"] < expiry_limit) & (df["pInstType"].isin(["OPTIDX", "IO"]))]

    if df.empty:
        logging.warning("⚠️ No option data found for nearest expiry.")
        return None

    df.to_excel(filepath, index=False)
    df = df[(df["pAssetCode"] == int(inst))]
    sorted_expiries = sorted(df["pExpiryDate"].unique())

    nearest_expiry = sorted_expiries[0]
    next_expiry = sorted_expiries[1] if len(sorted_expiries) > 1 else None
    if "dStrikePrice;" in df.columns:
        df.rename(columns={"dStrikePrice;": "dStrikePrice"}, inplace=True)
    if "dStrikePrice" in df.columns:
        df["dStrikePrice"] = df["dStrikePrice"] / 100
    cols = ["pSymbol", "pOptionType", "pTrdSymbol", "pExpiryDate", "dStrikePrice", "pExchSeg","lLotSize","iMaxOrderSize"]
    nearest_df = df[df["pExpiryDate"] == nearest_expiry]
    nearest_df = nearest_df[cols]
    nearest_df.to_excel(nefilepath, index=False)
    logging.info(f"✅ Nearest expiry file saved to {nefilepath}")

    if next_expiry:
        next_df = df[df["pExpiryDate"] == next_expiry][cols]
        next_df.to_excel(nextfilepath, index=False)
        logging.info(f"✅ Next expiry file saved to {nextfilepath}")
    else:
        logging.warning("⚠️ No next expiry data available.")

    return nearest_df
