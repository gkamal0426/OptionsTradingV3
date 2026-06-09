

# ═══════════════════════════════════════════════════════════════════════════════
# STRATEGY PREVIEW HELPER
# ═══════════════════════════════════════════════════════════════════════════════


import logging
import time
from utils.safe_variables import _float, _int

class StrategyPreviewHelper:


    def __init__(self, application):
        self.users = getattr(application, 'users', {})


    def _get_user(self, username):
        return self.users.get(username, None)


    @staticmethod
    def _read_ltp(user, token):
        with user.lock:
            ltp_data = user.ltp_feed.copy()
        return _float(ltp_data.get(str(token)), 0.0)


    @staticmethod
    def _get_symbol_exchange(user, token):
        for data in getattr(user, 'nearest_expiry_data', []):
            if str(data.get('pSymbol')) == str(token):
                return data.get('pTrdSymbol'), data.get('pExchSeg')
        return None, None


    @staticmethod
    def _subscribe_token(user, token, exchange, symbol):
        user.subscribe([{'instrument_token': str(token), 'exchange_segment': exchange}])
        logging.info(f"token : {token}, symbol : {symbol} subscribed for live feed")


    def _retry_attempts_to_read_ltp(self, user, token):
        wait = getattr(user, 'token_wait', 0.1)
        for _ in range(getattr(user, 'subscribe_retry', 10)):
            time.sleep(wait)
            ltp = self._read_ltp(user, token)
            if  ltp > 0:
                return ltp
        return 0


    def _if_token_not_subscribe(self, user, token):
        symbol, exchange = self._get_symbol_exchange(user, token)
        if not exchange:
            return 0
        self._subscribe_token(user, token, exchange, symbol)
        return self._retry_attempts_to_read_ltp(user, token)


    def _get_ltp(self, user, token):
        ltp = self._read_ltp(user, token)
        if ltp > 0:
            return ltp
        return self._if_token_not_subscribe(user, token)


    @staticmethod
    def _exchange_for(user):
        for record in getattr(user, 'nearest_expiry_data', []):
            exch = record.get('pExchSeg', '')
            if exch:
                return exch
        return 'nse_fo'


    @staticmethod
    def _symbol_input(data):
        return {
            'trd_symbol': data.get('pTrdSymbol'),
            'token':      str(data.get('pSymbol')),
            'exchange':   data.get('pExchSeg'),
            'lot_size':   _int(data.get('lLotSize'), 1),
        }


    @staticmethod
    def _check_eligible_criteria(data, opt_type, strike, tolerance=0.01):
        return (
            str(data.get('pOptionType', '')).upper() == opt_type.upper()
            and abs(float(data.get('dStrikePrice', 0)) - float(strike)) <= tolerance
        )


    def _find_symbol(self, user, strike, opt_type):
        for data in getattr(user, 'nearest_expiry_data', []):
            try:
                if self._check_eligible_criteria(data, opt_type, strike):
                    return self._symbol_input(data)
            except (TypeError, ValueError):
                continue
        logging.warning(f"Symbol not found: {strike} {opt_type}")
        return None


    @staticmethod
    def _legs(strike1, strike2, s1_type, s2_type, s1_action, s2_action, lots):
        return [
            {'strike': strike1, 'opt_type': s1_type, 'action': s1_action, 'lots': lots},
            {'strike': strike2, 'opt_type': s2_type, 'action': s2_action, 'lots': lots},
        ]


    def _straddle_legs(self, payload, lots):
        strike = _float(payload.get('strike'))
        if not strike: 
            return "strike required"
        return self._legs(strike, strike, "CE", "PE", "SELL", "SELL", lots)


    def _strangle_legs(self, payload, lots):
        ce_strike = _float(payload.get('ce_strike'))
        pe_strike = _float(payload.get('pe_strike'))
        if not ce_strike or not pe_strike: 
            return "ce_strike and pe_strike required"
        return self._legs(ce_strike, pe_strike, "CE", "PE", "SELL", "SELL", lots)


    def _bull_spread_legs(self, payload, lots):
        buy_strike = _float(payload.get('buy_strike'))
        sell_strike = _float(payload.get('sell_strike'))
        if not buy_strike or not sell_strike: 
            return "buy_strike and sell_strike required"
        return self._legs(buy_strike, sell_strike, "CE", "CE", "BUY", "SELL", lots)


    def _bear_spread_legs(self, payload, lots):
        buy_strike = _float(payload.get('buy_strike'))
        sell_strike = _float(payload.get('sell_strike'))
        if not buy_strike or not sell_strike: 
            return "buy_strike and sell_strike required"
        return self._legs(buy_strike, sell_strike, "PE", "PE", "BUY", "SELL", lots)

    
    @staticmethod
    def _iron_condor_list(buy_pe, sell_pe, sell_ce, buy_ce, lots):
        return [
            {'strike': buy_pe,  'opt_type': 'PE', 'action': 'BUY',  'lots': lots},
            {'strike': sell_pe, 'opt_type': 'PE', 'action': 'SELL', 'lots': lots},
            {'strike': sell_ce, 'opt_type': 'CE', 'action': 'SELL', 'lots': lots},
            {'strike': buy_ce,  'opt_type': 'CE', 'action': 'BUY',  'lots': lots},
        ]


    def _iron_condor_legs(self, payload, lots):
        buy_pe  = _float(payload.get('buy_pe'))
        sell_pe = _float(payload.get('sell_pe'))
        sell_ce = _float(payload.get('sell_ce'))
        buy_ce  = _float(payload.get('buy_ce'))
        if not all([buy_pe, sell_pe, sell_ce, buy_ce]):
            return "All four strikes required"
        return self._iron_condor_list(buy_pe, sell_pe, sell_ce, buy_ce, lots)
    

    @staticmethod
    def _custom_strategy_list(raw, lots):
        return [{'strike'   :   _float(data.get('strike')),
                'opt_type'  :   str(data.get('opt_type', '')).upper(),
                'action'    :   str(data.get('action', '')).upper(),
                'lots'      :   _int(data.get('lots'), lots),
                'order_type':   str(data.get('order_type', 'MKT')),
                'price'     :   _float(data.get('price'), 0)} for data in raw]


    def _custom_legs(self, payload, lots):    
        raw = payload.get('custom_legs', [])
        if not raw: 
            return "custom_legs required"
        return self._custom_strategy_list(raw, lots)


    def _leg_fetch(self, strategy_type, payload, lots):
        if strategy_type == 'straddle'    :  return self._straddle_legs(payload, lots)       
        if strategy_type == 'strangle'    :  return self._strangle_legs(payload, lots)
        if strategy_type == 'bull_spread' :  return self._bull_spread_legs(payload, lots)
        if strategy_type == 'bear_spread' :  return self._bear_spread_legs(payload, lots)
        if strategy_type == 'iron_condor' :  return self._iron_condor_legs(payload, lots)
        if strategy_type == 'custom'      :  return self._custom_legs(payload, lots)
        return f"Unknown strategy_type: {strategy_type}"


    def _max_loss(self, strategy_type, legs, net_premium):
        if strategy_type in ('straddle', 'strangle'):
            return 0.0 # it is unlimited due to open sell from both side
        
        if strategy_type in ('bull_spread', 'bear_spread') and len(legs) == 2:
            spread = abs(legs[0]['strike'] - legs[1]['strike'])
            return max(0.0, spread * legs[0]['lot_size'] * legs[0]['lots'] - abs(net_premium))
        
        if strategy_type == 'iron_condor' and len(legs) == 4:
            wing = abs(legs[0]['strike'] - legs[1]['strike'])
            return max(0.0, wing * legs[0]['lot_size'] * legs[0]['lots'] - abs(net_premium))
        return abs(net_premium) if net_premium < 0 else 0.0


    def _make_leg_dict(self, strike, record, opt_type, row, order_type, limit_price, user):
        lots = row.get('lots', 1)
        lot_size = _float(record.get('lot_size'), 0)
        token = record.get('token', '')
        return {
            'trd_symbol'    :   record.get('trd_symbol', ''),
            'token'         :   token,
            'opt_type'      :   opt_type.upper(),
            'strike'        :   float(strike),
            'action'        :   row.get('action', '').upper(),
            'lots'          :   lots,
            'quantity'      :   lots * lot_size,
            'lot_size'      :   lot_size,
            'exchange'      :   record['exchange'],
            'order_type'    :   order_type,
            'price'         :   _float(row.get('price', limit_price)) if order_type == 'L' else 0.0,
            'entry_ltp'     :   self._get_ltp(user, token),
        }


    def _build_leg(self, user, row, order_type, limit_price):
        strike = row['strike']
        opt_type = row['opt_type']
        record = self._find_symbol(user, strike, opt_type)
        if not record:
            return None, f"Symbol not found: {strike} {opt_type}"
        order_type = row.get('order_type', order_type)
        return self._make_leg_dict(strike, record, opt_type, row, order_type, limit_price, user), None


    def _built_legs(self, legs_input, order_type, limit_price, user):
        built_legs = []
        for row in legs_input:
            leg, err = self._build_leg(user, row, order_type, limit_price)
            if err:
                return None, err
            built_legs.append(leg)
        return built_legs


    def _net_premium(self, built_legs):
        return sum(
            data['entry_ltp'] * data['lots'] * data['lot_size'] * (1 if data['action'] == 'SELL' else -1)
            for data in built_legs
        )


    def _preview_dict(self, built_legs, net_premium, strategy_type):
        return {
            'legs':        built_legs,
            'net_premium': round(net_premium, 2),
            'net_value':   round(net_premium, 2),
            'max_loss':    round(self._max_loss(strategy_type, built_legs, net_premium), 2),
        }


    def build_preview(self, user, payload):
        strategy_type   = payload.get('strategy_type')

        legs_input = self._leg_fetch(strategy_type, payload, _int(payload.get('lots'), 1))

        if isinstance(legs_input, str):
            return None, legs_input

        built_legs = self._built_legs(legs_input, payload.get('order_type', 'MKT'), _float(payload.get('limit_price'), 0), user)

        return self._preview_dict(built_legs, self._net_premium(built_legs), strategy_type), None


