
# ═══════════════════════════════════════════════════════════════════════════════
# STRATEGY ACTION HELPER
# ═══════════════════════════════════════════════════════════════════════════════

import logging
from helper.handle_orders import OrderHelper
from strategy.helper_strategy_deploy import order_input_helper
from utils.communication import CallTelegram


class StrategyActionHelper:

    def __init__(self, application):
        self.users = getattr(application, 'users', {})
        self.strategy_store = application.strategy_store
        self.helper = OrderHelper()
        self.telegram       = CallTelegram()

    def _get_user(self, username):
        return self.users.get(username, None)




    def _validation_check(self, strategy_id, username):
        strategy = self.strategy_store.get(strategy_id)
        if not strategy:
            return None, f"Strategy {strategy_id} not found"
        if strategy.get('user') != username:
            return None, "Access denied"
        user = self._get_user(username)
        if not user:
            return None, f"User '{username}' not logged in"
        if not strategy.get('status'):
            return None, "Strategy status is blank"
        return user, None 


    def run(self, strategy_id, action, username):
        user, error = self._validation_check(strategy_id, username)
        if error:
            return None, error 
        strategy_status = self.strategy_store.get(strategy_id).get('status', None)
        if action == 'pause':
            return self._pause_strategy(strategy_status, strategy_id)
        if action == 'resume':
            return self._resume_strategy(strategy_status, strategy_id)
        if action == 'exit':
            return self._exit_strategy(strategy_status, strategy_id, user)
        return None, f"Unknown action '{action}'"
    

    def _pause_strategy(self, strategy_status, strategy_id):
        if  strategy_status != 'RUNNING':
            return None, "Strategy is not running"
        self.strategy_store.set_status(strategy_id, 'PAUSED')
        return f"Strategy {strategy_id} paused", None


    def _resume_strategy(self, strategy_status, strategy_id):
        if strategy_status != 'PAUSED':
            return None, "Strategy is not paused"
        self.strategy_store.set_status(strategy_id, 'RUNNING')
        return f"Strategy {strategy_id} resumed", None


    def _order_input(self, leg, user):
        action = 'Buy' if leg.get('action').upper()=='SELL' else 'Sell'
        return order_input_helper(user, leg, action, 'MKT', '0', 'Strategy_Manual_Exit')

    def _handle_response(self, response, leg):
        if response.get('stat') == 'Ok':
            message = f"Exit: {leg['trd_symbol']} → {response.get('nOrdNo')}"
            self.strategy_store.set_leg_status(leg['id'], 'CLOSED')
            logging.info(message)
            return  True, message
        else:
            message = f"Exit failed: {leg['trd_symbol']} — {response.get('errMsg','?')}"
            logging.error(message)
            return False, message


    def _execute_order(self, leg, user):
        try:
            response = self.helper.single_order_helper(self._order_input(leg, user), "URL_STRATEGY_EXIT_SYS")
            return self._handle_response(response, leg)
        except Exception as e:
                message = f"Exit exception: {leg['trd_symbol']} : {e}"
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
            self.strategy_store.set_status(strategy_id, 'PARTIAL EXIT')
        else:
            self.strategy_store.set_status(strategy_id, 'EXITED')
        #self.telegram.telegram_message(message, uc)
        self.helper.initiate_queue.put((uc, message))
        return message

    def _exit_open_legs(self, strategy_id, user):
        uc = getattr(user, 'UC', "default")
        ok = fail = 0
        with user.order_lock:    
            for leg in self.strategy_store.get_legs(strategy_id):
                if self._call_exit_process(leg, user, uc):
                   ok += 1
                else:
                    fail += 1        
        return self._final_update(strategy_id, ok, fail, uc)

    def _exit_strategy(self, strategy_status, strategy_id, user):
        if strategy_status in ('EXITED', 'FAILED'):
            return None, "Strategy already exited"
        message = self._exit_open_legs(strategy_id, user)
        return message, None
