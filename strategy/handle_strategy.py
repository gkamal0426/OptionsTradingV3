import logging
import traceback
from flask import jsonify, request
from strategy.handle_strategy_store import StrategyStore
from strategy.helper_strike_data import StrikeDataHelper
from strategy.helper_strategy_preview import StrategyPreviewHelper
from strategy.helper_strategy_deploy import StrategyDeployHelper
from strategy.helper_active_strategy import ActiveStrategiesHelper
from strategy.helper_strategy_action import StrategyActionHelper
from strategy.helper_stoploss_monitor import SLMonitor
from strategy.helper_panic import PanicHelper
from utils.decorators import login_required

class StrategyHelper:

    def __init__(self):
        self.strategy_store = StrategyStore()
        self.sl_monitor     = SLMonitor(self.strategy_store)
        self.sl_monitor.start()

    def _refresh_monitor_users(self):
        self.sl_monitor.set_users(self.users)


    def _setup_strategy_routes(self):
        pass
    


    def strategy_get_strikes(self, request):
        try:
            index = request.args.get('underlying_code', '26000')
            username        = request.args.get('user', 'client1')
            user = self.users.get(username)
            if not user:
                return jsonify({'stat': 'error', 'message': f'{username} not logged in'})
            self._refresh_monitor_users()
            data, err = StrikeDataHelper(self).get_strikes(index, username)
            if err:
                return jsonify({'stat': 'error', 'message': err})
            return jsonify({'stat': 'ok', 'data': data})
        except Exception as e:
            traceback.print_exc()
            return jsonify({'stat': 'error', 'message': str(e)})

    def _get_leg_input(self, l):
        return {
            'trd_symbol': l['trd_symbol'],
            'opt_type':   l['opt_type'],
            'strike':     l['strike'],
            'action':     l['action'],
            'lots':       l['lots'],
            'quantity':   l['quantity'],
            'order_type': l['order_type'],
            'price':      l['price'],
            'entry_ltp':  l['entry_ltp'],
        }
    
    def _preview_return(self, preview):
        safe_legs = [ self._get_leg_input(l) for l in preview['legs']]
        return {'stat': 'ok', 'data': {
            'legs':        safe_legs,
            'net_premium': preview['net_premium'],
            'net_value':   preview['net_value'],
            'max_loss':    preview['max_loss'],
        }}

    def strategy_post_preview(self, request):
        try:
            payload  = request.json or {}
            username = payload.get('user', 'client1')
            user = self.users.get(username)
            if not user:
                return jsonify({'stat': 'error', 'message': f'{username} not logged in'})
            self._refresh_monitor_users()
            preview, err = StrategyPreviewHelper(self).build_preview(user, payload)
            if err:
                return jsonify({'stat': 'error', 'message': err})
            return jsonify(self._preview_return(preview))
        except Exception as e:
            traceback.print_exc()
            return jsonify({'stat': 'error', 'message': str(e)})


    def strategy_post_deploy(self, request):
        try:
            payload  = request.json or {}
            username = payload.get('user', 'client1')
            user = self.users.get(username)
            if not user:
                return jsonify({'stat': 'error', 'message': f'{username} not logged in'})
            self._refresh_monitor_users()
            sid, msg, err = StrategyDeployHelper(self).deploy(payload)
            if err:
                return jsonify({'stat': 'error', 'message': err})
            return jsonify({'stat': 'ok', 'message': msg, 'strategy_id': sid})
        except Exception as e:
            traceback.print_exc()
            return jsonify({'stat': 'error', 'message': str(e)})

    def strategy_get_active(self, request):
        try:
            username = request.args.get('user', 'client1')
            self._refresh_monitor_users()
            result = ActiveStrategiesHelper(self).get_active(username)
            return jsonify({'stat': 'ok', 'data': result})
        except Exception as e:
            traceback.print_exc()
            return jsonify({'stat': 'error', 'message': str(e)})

    def strategy_get_legs(self, request, sid):
        try:
            username  = request.args.get('user', 'client1')
            legs, err = ActiveStrategiesHelper(self).get_legs(sid, username)
            if err:
                return jsonify({'stat': 'error', 'message': err})
            return jsonify({'stat': 'ok', 'data': legs})
        except Exception as e:
            traceback.print_exc()
            return jsonify({'stat': 'error', 'message': str(e)})

    def strategy_action(self, request, sid, action):
        try:
            payload  = request.json or {}
            username = payload.get('user', 'client1')
            msg, err = StrategyActionHelper(self).run(sid, action, username)
            if err:
                return jsonify({'stat': 'error', 'message': err})
            return jsonify({'stat': 'ok', 'message': msg})
        except Exception as e:
            traceback.print_exc()
            return jsonify({'stat': 'error', 'message': str(e)})

    def strategy_post_panic(self, request):
        try:
            payload  = request.json or {}
            username = payload.get('user', 'client1')
            self._refresh_monitor_users()
            msg, err = PanicHelper(self).execute(username)
            if err:
                return jsonify({'stat': 'error', 'message': err})
            return jsonify({'stat': 'ok', 'message': msg})
        except Exception as e:
            traceback.print_exc()
            return jsonify({'stat': 'error', 'message': str(e)})
