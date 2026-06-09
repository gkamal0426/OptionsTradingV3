# ═══════════════════════════════════════════════════════════════════════════════
# STRIKE DATA HELPER
# ═══════════════════════════════════════════════════════════════════════════════

from utils.safe_variables import _float, _int, _epoch_to_expiry_str
import logging

class StrikeDataHelper:

    def __init__(self, application):
        self.users = getattr(application, 'users', {})

    def _get_user(self, username):
        return self.users.get(username, None)


    def _read_ltp(self, user, token):
        with user.lock:
            ltp_data = user.ltp_feed.copy()
        return _float(ltp_data.get(str(token)), 0.0)

    def _index_ltp(self, user, index):
        for data in getattr(user, 'indexandtokens', []):
            if str(data.get('token')) == str(index):
                ltp = self._read_ltp(user, data['token'])
                if ltp > 0:
                    return ltp
        return self._read_ltp(user, index)

    def _lot_size(self, user, underlying_code):
        for data in getattr(user, 'index_details', []):
            if str(data.get('index')) == str(underlying_code):
                return _int(data.get('lot_size'), 1)
        for data in getattr(user, 'nearest_expiry_data', []):
            lot_size = data.get('lLotSize')
            if lot_size:
                return _int(lot_size, 1)
        return 1


    def _expiry_str(self, user):
        for r in getattr(user, 'nearest_expiry_data', []):
            for key in ('pExpiryDate', 'ExpiryDate'):
                v = r.get(key, '')
                if v:
                    try:
                        return _epoch_to_expiry_str(int(v))  # convert to int, not str
                    except Exception:
                        return str(v)
        return 'N/A'


    def _atm(self, strikes, index_ltp):
        if not strikes or index_ltp <= 0:
            return strikes[len(strikes) // 2] if strikes else 0
        return min(strikes, key=lambda strike: abs(strike - index_ltp))


    def _nearest_expiry_data_strike(self, raw, user):
        expiry_data = getattr(user, 'nearest_expiry_data', [])
        if expiry_data:
            for row in expiry_data:
                try:
                    raw.add(round(_float(row.get('dStrikePrice', 0)), 0))
                except (TypeError, ValueError):
                    pass
        return raw

    def _symbolsandtokens_strike(self, raw, user):
        strike_data = getattr(user, 'symbolsandtokens', [])
        
        if strike_data:
            for r in strike_data:
                try:
                    if r.get('strike') !='Index':
                        raw.add(round(_float(r.get('strike', 0)), 0))
                except (TypeError, ValueError):
                    pass
        return raw

    def _strikes_dict(self, strikes, user, index):
        return {
            'strikes':    [int(strike) for strike in strikes],
            'atm':        int(self._atm(strikes, self._index_ltp(user, index))),
            'expiry_str': self._expiry_str(user),
            'lot_size':   self._lot_size(user, index),
        }        

    def _raw_strikes_data(self, user, index):
        raw  = set()
        raw = self._symbolsandtokens_strike(raw, user)
        if not raw:
            raw = self._nearest_expiry_data_strike(raw, user)
        if not raw:
            return None, f"No strikes found for {index}"

        return raw, None

    def get_strikes(self, index, username):
        user = self.users.get(username, None)
        if not user:
            return None, f"User '{username}' not logged in"

        raw, error = self._raw_strikes_data(user, index)
        if error:
            return None, error
        
        strikes = sorted(raw)
        return self._strikes_dict(strikes, user, index), None
