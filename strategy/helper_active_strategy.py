# ═══════════════════════════════════════════════════════════════════════════════
# ACTIVE STRATEGIES HELPER
# ═══════════════════════════════════════════════════════════════════════════════

def _append_strategy(legs, strategy):
    return {
        'id':              strategy['id'],
        'strategy_name':   strategy['strategy_name'],
        'underlying_name': strategy['underlying_name'],
        'expiry_str':      strategy['expiry_str'],
        'leg_count':       len(legs),
        'open_leg_count':  sum(1 for l in legs if l.get('status') == 'OPEN'),
        'lots':            strategy['lots'],
        'total_premium':   strategy['total_premium'],
        'mtm_pnl':         strategy.get('mtm_pnl', 0.0),
        'sl_hit':          strategy.get('sl_hit', False),
        'sl_type':         strategy.get('sl_type', 'none'),
        'sl_value':        strategy.get('sl_value', 0),
        'sl_pct':          strategy.get('sl_pct', 0),
        'trail_sl':        strategy.get('trail_sl', False),
        'deployed_at':     strategy.get('deployed_at', ''),
        'status':          strategy.get('status', 'RUNNING'),
    }

def _append_leg(leg):
    entry   = _float(leg.get('entry_ltp'), 0)
    current = _float(leg.get('current_ltp'), entry)
    qty     = _int(leg.get('quantity'), 0)
    sign    = 1 if leg['action'] == 'SELL' else -1

    return {
        'trd_symbol':  leg['trd_symbol'],
        'opt_type':    leg['opt_type'],
        'strike':      leg['strike'],
        'action':      leg['action'],
        'lots':        leg['lots'],
        'quantity':    qty,
        'entry_ltp':   entry,
        'current_ltp': current,
        'mtm_pnl':     round(sign * (entry - current) * qty, 2),
        'status':      leg.get('status', 'OPEN'),
        'order_id':    leg.get('order_id', 'NA'),
    }

from utils.safe_variables import _float, _int

class ActiveStrategiesHelper:

    def __init__(self, application):
        self.strategy_store = application.strategy_store

    def get_active(self, username):
        result = []
        for strategy in self.strategy_store.all_for_user(username):
            legs = self.strategy_store.get_legs(strategy['id'])
            result.append(_append_strategy(legs, strategy))
        return result

    def get_legs(self, strategy_id, username):
        strat = self.strategy_store.get(strategy_id)
        if not strat:
            return None, f"Strategy {strategy_id} not found"
        if strat.get('user') != username:
            return None, "Access denied"
        result = []
        for leg in self.strategy_store.get_legs(strategy_id):
            result.append(_append_leg(leg))
        return result, None