# ═══════════════════════════════════════════════════════════════════════════════
# SL MONITOR
# Background thread. Receives store + users directly from StrategyHelper.
# ═══════════════════════════════════════════════════════════════════════════════


import logging
import threading
import time
from utils.safe_variables import _float, _int
from strategy.helper_strategy_deploy import order_input_helper
from helper.handle_orders import OrderHelper
from utils.communication import CallTelegram

class SLMonitor:

    def __init__(self, strategy_store, feed_check_interval = 1):
        self.interval       = feed_check_interval
        self.strategy_store = strategy_store
        self._thread        = None
        self._lock          = threading.Lock()
        self.users          = {}
        self.helper         = OrderHelper()
        self.telegram       = CallTelegram()
    
    def set_users(self, users):
        with self._lock:
            self.users = users

    def start(self):
        if self._thread is None or not self._thread.is_alive():
            
            self._thread = threading.Thread(target=self._loop, name='SLMonitor', daemon=True)
            self._thread.start()
            logging.info("SLMonitor started")


    def _get_user(self, username):
        if not username:
            return None
        with self._lock:
            return self.users.get(username)


    def _get_ltp_data(self, user):
        try:
            with user.lock:
                return user.ltp_feed.copy()
        except Exception:
            return {}

    def _loop(self):
        while True:
            try:
                self._tick()
            except Exception:
                logging.exception("SLMonitor tick error")
            
            time.sleep(self.interval)


    def _tick(self):
        for strategy in self.strategy_store.all_running():
            user = self._get_user(strategy['user'])
            if user:
                self._process(strategy, user)

    def _get_value_validation(self, entry_ltp, quantity, leg):
        if not entry_ltp or entry_ltp == 0.0:
            logging.info(f"Incorrect Entry ltp updated for symbol {leg.get('trd_symbol')} - token {leg.get('token')}")
        if not quantity or quantity == 0:
            logging.info(f"Incorrect quanitity updated for symbol {leg.get('trd_symbol')} - token {leg.get('token')}")

    def _fetch_prices(self, action, entry_ltp, ltp, quantity):
        if  action == 'BUY':
            entry_price = entry_ltp * quantity * -1
            current_price = ltp * quantity
        elif action == 'SELL':
            entry_price = entry_ltp * quantity 
            current_price = ltp * quantity * -1
        else:
            entry_price = current_price = 0
            logging.info(f"invalid action type {action}")

        return entry_price, current_price



    def _process(self, strategy, user):
        sid  = strategy['id'] # sid - strategy ID
        legs = self.strategy_store.get_legs(sid)
        entry_price = current_price  = mtm_pnl = total_current_price = 0

        ltp_data = self._get_ltp_data(user)
        for leg in legs:
            if leg.get('status') != 'OPEN':
                continue
            ltp = _float(ltp_data.get(str(leg['token'])), 0.0)
            entry_ltp = _float(leg.get('entry_ltp'))
            quantity = _int(leg.get('quantity'))
            self._get_value_validation( entry_ltp, quantity, leg)
            
            if ltp <= 0:
                ltp = entry_ltp

            action = leg.get('action').upper()
            entry_price, current_price = self._fetch_prices(action, entry_ltp, ltp, quantity)

            total_current_price += current_price
            leg['pnl'] = entry_price + current_price
            mtm_pnl += entry_price + current_price

        self.strategy_store.update_mtm(sid, round(mtm_pnl, 2))
        self._act_on_price_status(strategy, legs, mtm_pnl, sid, user, total_current_price)



    def _sl_hit(self, strategy, legs, mtm_pnl):
        sl_type  = strategy.get('sl_type', 'none')
        sl_value = _float(strategy.get('sl_value'), 0)
        sl_pct   = _float(strategy.get('sl_pct'), 0)

        if sl_type == 'combined_points':
            return mtm_pnl <= -abs(sl_value)

        if sl_type == 'combined_pct':
            premium = _float(strategy.get('total_premium'), 0)
            return premium > 0 and (-mtm_pnl / premium * 100) >= abs(sl_pct)

        if sl_type in ('individual', 'individual_pct'):
            for leg in legs:
                if leg.get('status') != 'OPEN':
                    continue
                entry_price = _float(leg.get('entry_ltp'), 0)
                leg_pnl        = _float(leg.get('pnl'), 0)
                loss = abs(leg_pnl) if leg_pnl < 0 else 0
                sl_map_value = entry_price * sl_pct / 100 if sl_type == 'individual_pct' and entry_price > 0 else sl_value
                if loss > sl_map_value:
                    return True
        return False

    def _trail(self, sid, strategy, total_current_price):
        trail_step   = _float(strategy.get('trail_step'), 0)
        peak_premium = _float(strategy.get('peak_premium'), strategy.get('total_premium', 0))
        
        if trail_step <= 0 or total_current_price >= peak_premium:
            return

        decay = peak_premium - total_current_price
        if decay >= trail_step:
            steps  = int(decay / trail_step)
            new_sl = max(0, _float(strategy.get('sl_value'), 0) - steps * trail_step)
            self.strategy_store.tighten_sl(sid, new_sl)
            self.strategy_store.update_peak_premium(sid, total_current_price)
            logging.info(f"Trail SL tightened — strategy {sid} new_sl={new_sl}")


    def _order_input(self, leg, user):
        action = 'Buy' if leg.get('action').upper()=='SELL' else 'Sell'
        return order_input_helper(user, leg, action, 'MKT', '0', 'Strategy_Stoploss_Exit')

    def _handle_exit_response(self, response, leg):
        if response.get('stat') == 'Ok':
            self.strategy_store.set_leg_status(leg['id'], 'CLOSED')
            message = f"Stoploss Exit completed for {leg['trd_symbol']} → order no - {response.get('nOrdNo')}"
            logging.info(message)
            return True, message
        else:
            message = f"Stoploss Exit failed: {leg['trd_symbol']} — {response.get('errMsg','?')}"
            logging.error(message)
            return False, message

    def _execute_order(self, leg, user):
        try:
            response = self.helper.single_order_helper(self._order_input(leg, user), "URL_STRATEGY_SL_EXIT")
            return self._handle_exit_response(response, leg)
        except Exception as e:
                message = f"Monitor Exit exception: {leg['trd_symbol']} : {e}"
                logging.exception(message)
                return False, message


    def _call_exit_process(self, leg, user, uc):
        status = False
        if leg.get('status') == 'OPEN':
            status, message = self._execute_order(leg, user)
            #self.telegram.telegram_message(message, uc)
            self.helper.initiate_queue.put((uc, message))
        return status


    def _final_update(self, strategy_id, ok, fail, uc):
        message = f"Strategy {strategy_id} exited: {ok} legs closed"
        if fail:
            message += f", {fail} failed"
            self.strategy_store.set_status(strategy_id, 'PARTIAL_EXIT')
        else:
            self.strategy_store.set_status(strategy_id, 'EXITED')
        #self.telegram.telegram_message(message, uc)
        self.helper.initiate_queue.put((uc, message))
        return message


    def _exit_legs(self, strategy_id, legs, user):
        ok = fail = 0
        uc = getattr(user, 'UC', "default")
        with user.order_lock:    
            for leg in legs:
                if leg.get('status') != 'OPEN':
                    continue
                if self._call_exit_process(leg, user, uc):
                   ok += 1
                else:
                    fail += 1        

        return self._final_update(strategy_id, ok, fail, uc)



    def _act_on_price_status(self, strategy, legs, mtm_pnl, sid, user, total_current_price):        
        if strategy.get('sl_type', 'none') == 'none':
            return

        if self._sl_hit(strategy, legs, mtm_pnl):
            print("")
            logging.warning(f"SL triggered — strategy {sid}\n\n")
            self.strategy_store.set_sl_hit(sid)
            self._exit_legs(sid, legs, user)
            return

        target = _float(strategy.get('target_value'), 0)
        if target > 0 and mtm_pnl >= target:
            logging.info(f"Target reached — strategy {sid}")
            self.strategy_store.set_status(sid, 'EXITED')
            self._exit_legs(sid, legs, user)
            return

        if strategy.get('trail_sl'):
            self._trail(sid, strategy, total_current_price)
