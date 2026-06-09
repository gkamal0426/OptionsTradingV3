import time
import logging
from utils.safe_variables import _float, _int

def ratio_trade_eligibility(
    user,
    buy_token,
    sell_token,
    buy_price: float = 0.0,
    sell_price: float = 0.0,
    multiplier: float = 2.5,
    time_delay: int = 15
):
    buy_price = _float(buy_price)
    sell_price = _float(sell_price)
    multiplier = _float(multiplier, 2.5)
    time_delay = _int(time_delay, 15)
    logging.info("Starting Ratio trade eligibility check")    
    while True:
        buy_ltp = 0.0
        sell_ltp = 0.0

        with user.lock:
            ltpdata = user.ltp_feed.copy()

        for token, ltp in ltpdata.items():
            if str(token) == str(buy_token):
                buy_ltp = float(ltp)
            elif str(token) == str(sell_token):
                sell_ltp = float(ltp)
            if buy_ltp > 0 and sell_ltp > 0:
                break

        if buy_price > 0 and sell_price > 0:
            message = f"Buy ≤ {buy_price}, Sell ≥ {sell_price}"
            if buy_ltp <= buy_price and sell_ltp >= sell_price:
                logging.info(f"✅ Condition met: Buy ≤ {buy_price}, Sell ≥ {sell_price}")
                break
        elif buy_price > 0:
            message = f"Buy ≤ {buy_price}"
            if buy_ltp <= buy_price:
                logging.info(f"✅ Condition met: Buy ≤ {buy_price}")
                break
        elif sell_price > 0:
            message = f"Sell ≥ {sell_price}, ratio ≤ {multiplier}"
            if sell_ltp >= sell_price:
                if buy_ltp / sell_ltp <= multiplier:
                    logging.info(f"✅ Condition met: Sell ≥ {sell_price}, ratio ≤ {multiplier}")
                    break
                else:
                    logging.info("⚠️ Sell leg price reached but buy price exceeding. Monitoring...")
        else:
            logging.warning("❌ Invalid input: both buy_price and sell_price are zero")
            break

        logging.info(f"⏳ Monitoring : ({message})... Current- Buy LTP: {buy_ltp}, Sell LTP: {sell_ltp}")
        time.sleep(time_delay)
