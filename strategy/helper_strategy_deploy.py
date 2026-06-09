# ═══════════════════════════════════════════════════════════════════════════════
# STRATEGY DEPLOY HELPER
# ═══════════════════════════════════════════════════════════════════════════════


import logging
from strategy.helper_strike_data import StrikeDataHelper
from strategy.helper_strategy_preview import StrategyPreviewHelper
from utils.safe_variables import _float
from helper.handle_orders import OrderHelper
from utils.communication import CallTelegram

def order_input_helper(user, leg, action, order_type, price, source):
    
    return {
        'lot_size': leg.get('lot_size'),
        'quantity': leg.get('lots'),
        'symbol': leg.get('trd_symbol'),
        'action': action,
        'exchange': leg.get('exchange'),
        'orderType': order_type,
        'price': price,
        'product': 'NRML',
        'username': user,
        'source' : source
    }

class StrategyDeployHelper:

    def __init__(self, application):
        self.users          = getattr(application, 'users', {})
        self.strategy_store = application.strategy_store
        self._preview       = StrategyPreviewHelper(application)
        self._strikes       = StrikeDataHelper(application)
        self.helper         = OrderHelper()
        self.telegram       = CallTelegram()


    def _get_user(self, username):
        return self.users.get(username, None)

    def _exchange_for(self, user):
        for r in getattr(user, 'nearest_expiry_data', []):
            exch = r.get('pExchSeg', '')
            if exch:
                return exch
        return 'nse_fo'

    def _name_for(self, user, index_code):
        for entry in getattr(user, 'index_details', []):
            if str(entry.get('index')) == str(index_code):
                return str(entry.get('name', index_code))
        return str(index_code)


    def _call_order_helper(self, leg, user):
        action = leg['action']
        order_type = leg['order_type']
        price = leg['price']
        source = "Strategy_Order_sys"
        endpoint = "URL_STRATEGY_SYS"
        return self.helper.single_order_helper(order_input_helper(user, leg, action, order_type, price , source), endpoint)



    def _execute_order(self, leg, user):
        order_id = None
        try:
            response = self._call_order_helper(leg, user)
            if response.get('stat') == 'Ok':
                order_id = response.get('nOrdNo')
                logging.info(f"Leg placed: {leg.get('trd_symbol','?')} {leg.get('action','?')} → {order_id}")
            else:
                logging.error(f"Leg failed: {leg.get('trd_symbol','?')} — {response.get('errMsg','?')}")
        except Exception as e:
            logging.exception(f"Exception placing leg {leg.get('trd_symbol','?')}: {e}")
        return order_id


    def _track_place_order(self, user, preview):

        placed_legs = []
        with user.order_lock:
            for leg in preview['legs']:
                order_id = self._execute_order(leg, user)
                placed_legs.append({
                    **leg,
                    'pnl': 0,
                    'order_id': order_id if order_id else 'FAILED'
                })
        return placed_legs


    def _validate_input(self, payload):
        username        = payload.get('user', 'client1')
        underlying_code = str(payload.get('underlying_code', ''))
        user = self._get_user(username)
        if not user:
            return {'status' : None, 'error': f"User '{username}' not logged in"}
        preview, error = self._preview.build_preview(user, payload)
        if error:
            return {'status' : None, 'error': error}
        underlying_name = self._name_for(user, underlying_code)
        expiry_str      = self._strikes._expiry_str(user)
        return {'status' : 'Ok', 'user' : user, 'preview' : preview, 'underlying_name' : underlying_name, 'expiry_str' :expiry_str}

    def _append_strategy(self, strategy_name, payload, variables, placed_legs):
        return {
            'user':            payload.get('user'),
            'strategy_name':   strategy_name,
            'strategy_type':   payload.get('strategy_type'),
            'underlying_code': payload.get('underlying_code'),
            'underlying_name': variables.get('underlying_name'),
            'expiry_str':      variables.get('expiry_str'),
            'lots':            max(l['lots'] for l in placed_legs),
            'total_premium':   variables.get('preview', {}).get('net_premium'),
            'sl_type':         payload.get('sl_type', 'none'),
            'sl_value':        _float(payload.get('sl_value'), 0),
            'sl_pct':          _float(payload.get('sl_pct'), 0),
            'trail_sl':        bool(payload.get('trail_sl', False)),
            'trail_step':      _float(payload.get('trail_step'), 0),
            'target_value':    _float(payload.get('target_value'), 0),
        }

    def _save_strategy(self, strategy, placed_legs, strategy_name, variables):
        sid    = self.strategy_store.save(strategy, placed_legs)
        failed = sum(1 for l in placed_legs if l.get('order_id') == 'FAILED')
        message    = f"Strategy '{strategy_name}' deployed (id={sid})"
        if failed:
            message += f" — WARNING: {failed} leg(s) failed"        
        #self.telegram.telegram_message(message, getattr(variables.get('user'), 'UC', 'default'))
        self.helper.initiate_queue.put((getattr(variables.get('user'), 'UC', 'default'), message))
        
        return sid, message, None


    def deploy(self, payload):
        variables = self._validate_input(payload)
        if not variables.get('status', None):
            print("not variable conditions got true")
            return None, None, variables.get('error')        
        placed_legs = self._track_place_order(variables.get('user'), variables.get('preview'))
        if not placed_legs:
            return None, None, "No legs could be placed"
        strategy_name = payload.get('strategy_name', payload.get('strategy_type'))        
        strategy = self._append_strategy(strategy_name, payload, variables, placed_legs)
        return self._save_strategy(strategy, placed_legs, strategy_name, variables)

