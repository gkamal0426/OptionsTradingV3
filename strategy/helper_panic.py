import logging
import threading
from utils.safe_variables import _int
from helper.handle_orders import OrderHelper
from utils.communication import CallTelegram
        
# ═══════════════════════════════════════════════════════════════════════════════
# PANIC HELPER
# ═══════════════════════════════════════════════════════════════════════════════


class PanicHelper:

    def __init__(self, application):
        self.users          = getattr(application, 'users', {})
        self.strategy_store = application.strategy_store
        self.helper         = OrderHelper()
        self.telegram       = CallTelegram()

    def _get_user(self, username):
        return self.users.get(username, None)

    def _get_panic_users_list(self, username):
        targets = []
        if username.upper() == 'ALL':
            for key, value in self.users.items():
                targets.append((key, value))
        else:
            user = self._get_user(username)
            if user:
                targets.append((username, user))
        return targets

    def execute(self, username):
        targets = self._get_panic_users_list(username)
        if not targets:
            return None, f"User '{username}' not logged in"

        def _run(username, user):
            msg = self._panic_one(username, user)
            with result_lock:
                results[username] = msg

        results     = {}
        result_lock = threading.Lock()

        threads = [threading.Thread(target=_run, args=(u, obj), daemon=True) for u, obj in targets]
        for thread in threads: thread.start()
        for thread in threads: 
            thread.join(timeout=30)
            if thread.is_alive():
                logging.warning(f"Panic thread for {username} did not finish in time")
        
        return "PANIC executed — " + " | ".join(f"{key}: {value}" for key, value in results.items()), None


    def _panic_one(self, username, user):
        self.telegram.telegram_message("Panic Activated", getattr(user, 'UC', None))
        parts = [
            f"cancelled {self._cancel_orders(user)} orders for {username}",
            f"squared {self._squareoff(user)} positions for {username}",
        ]
        exited = 0
        for s in self.strategy_store.all_for_user(username):
            if s.get('status') in ('RUNNING', 'PAUSED', 'SL_HIT'):
                self.strategy_store.set_status(s['id'], 'EXITED')
                exited += 1
        parts.append(f"exited {exited} strategies for {username}")
        return " | ".join(parts)


    @staticmethod
    def _cancel(order_no, user):
        if order_no:
            try:
                with user.order_lock:
                    result = user.client.cancel_order(order_id=order_no)
                if result.get('stat') == 'Ok':
                    return 1
                    #cancelled_orders.append(order_no)
            except Exception as e:
                logging.exception(f"Cancel exception {order_no}: {e}")
        return 0


    @staticmethod
    def _get_orders_report(user):
        with user.report_lock:
            orders = user.client.order_report().get('data', None)
        return orders if isinstance(orders, list) else None


    def _cancel_orders(self, user):
        cancelled = 0
        #cancelled_orders = []
        pending = {'open', 'pending', 'trigger pending'}
        try:
            orders = self._get_orders_report(user)
            if orders:
                for order in orders:
                    if order.get('ordSt', 'NA').lower() in pending:
                        cancelled += self._cancel(str(order.get('nOrdNo')), user)
        except Exception as e:
            logging.exception(f"Panic: error fetching orders: {e}")
        return cancelled #{'count': cancelled, 'orders': cancelled_orders}



    @staticmethod
    def _get_order_input(pos, user):
        net = _int(pos.get('flBuyQty', 0)) - _int(pos.get('flSellQty', 0))
        lot_size = _int(pos.get('lotSz', 1))
        quantity = abs(net) / lot_size
        symbol   = pos.get('trdSym')
        exchange = pos.get('exSeg')

        if symbol and exchange and net != 0:
            return {
                'lot_size': lot_size,
                'quantity': quantity,
                'symbol': symbol,
                'action': 'Sell' if net > 0 else 'Buy',
                'exchange': exchange,
                'orderType': 'MKT',
                'price': 0,
                'product': pos.get('prod', 'NRML'),
                'username': user
            }
        return None


    @staticmethod
    def _get_positions_report(user):
        with user.report_lock:
            positions = user.client.positions().get('data', None)
        return positions if isinstance(positions, list) else None

    @staticmethod
    def _handle_response(response, order_input):
        if response.get('stat') == 'Ok':
            message = f"Panic Squareoff success for symbol : {order_input.get('symbol')} → {response.get('nOrdNo')}"
            logging.info(message)
            return  True, message
        else:
            message = f"Panic Squareoff failed for symbol: {order_input.get('symbol')} — {response.get('errMsg','?')}"
            logging.error(message)
            return False, message


    def _call_order_helper(self, order_input, user):
        if order_input:
            try:
                with user.order_lock:
                    response = self.helper.single_order_helper(order_input, "URL_PANIC_SYS")
                    return self._handle_response(response, order_input)
            except Exception as e:
                message = f"Panic Squareoff exception for symbol : {order_input.get('symbol')} : {e}"
                logging.exception(message)
                return False, message


    def _close_positions(self, user, uc, position, success, failed):
        status, message = self._call_order_helper(self._get_order_input(position, user), user)
        if status:
            success += 1
        else:
            failed += 1
        self.telegram.telegram_message(message, uc)
        return success, failed

    @staticmethod
    def _closure_message(success, failed):
        message = f"Panic exit : {success} positions closed"
        if failed:
            message += f", and {failed} failed. Do the needful manually for failed posisiton"
        return message

    def _squareoff(self, user):
        uc = getattr(user, 'UC', "default")
        success = failed = 0
        try:
            positions = self._get_positions_report(user)
            if positions:    
                for position in positions:
                    success, failed = self._close_positions(user, uc, position, success, failed)
                message = self._closure_message(success, failed)
            else:
                message = "No positions found for panic squareoff."
        except Exception as e:
            message = f"Panic Exception: error fetching positions. Do the needful manually : {e}"
            logging.exception(message)

        self.telegram.telegram_message(message, uc)
        return success + failed
