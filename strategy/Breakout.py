# ═══════════════════════════════════════════════════════════════════════════════
# STRIKE DATA HELPER
# ═══════════════════════════════════════════════════════════════════════════════

import logging
import threading
import time
from utils.safe_variables import _float, _int

class BreakoutMonitor:

    def __init__(self, strategy_store, feed_check_interval=1):
        self.interval       = feed_check_interval
        self.strategy_store = strategy_store
        self._thread        = None
        self._lock          = threading.Lock()
        self.users          = {}

    def set_users(self, users):
        with self._lock:
            self.users = users

    def start(self):
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._loop, name='BreakoutMonitor', daemon=True)
            self._thread.start()
            logging.info("BreakoutMonitor started")

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
                logging.exception("BreakoutMonitor tick error")
            time.sleep(self.interval)

    def _tick(self):
        # Scan all strategies or instruments
        for strategy in self.strategy_store.all_running():
            user = self._get_user(strategy['user'])
            if user:
                self._process(strategy, user)

    # ---------------- Ratio Helpers ---------------- #

    def _pcr_breakout(self, option_chain):
        puts = _int(option_chain.get('put_volume'), 0)
        calls = _int(option_chain.get('call_volume'), 0)
        if calls == 0:
            return None
        pcr = puts / calls
        if pcr > 1.5:
            return "Bullish breakout potential (PCR high)"
        if pcr < 0.5:
            return "Bearish breakout potential (PCR low)"
        return None

    def _volume_price_breakout(self, price_change, current_volume, avg_volume):
        if avg_volume <= 0:
            return None
        volume_ratio = current_volume / avg_volume
        if volume_ratio > 3 and abs(price_change) > 0.02:  # 2% move
            return f"Breakout confirmed (Vol/Price ratio {volume_ratio:.2f})"
        return None

    def _range_atr_breakout(self, day_high, day_low, atr):
        if atr <= 0:
            return None
        range_ratio = (day_high - day_low) / atr
        if range_ratio > 2:
            return f"Range breakout detected (Range/ATR {range_ratio:.2f})"
        return None

    def _oi_volume_breakout(self, oi_change, volume_change):
        if volume_change <= 0:
            return None
        ratio = oi_change / volume_change
        if ratio > 1.5:
            return f"OI/Volume breakout detected (ratio {ratio:.2f})"
        return None

    # ---------------- Processing ---------------- #

    def _process(self, strategy, user):
        sid = strategy['id']
        ltp_data = self._get_ltp_data(user)

        # Example: fetch option chain + historical averages from strategy_store
        option_chain = self.strategy_store.get_option_chain(sid)
        avg_volume   = self.strategy_store.get_avg_volume(sid)
        atr          = self.strategy_store.get_atr(sid)

        # Compute signals
        signals = []
        pcr_signal = self._pcr_breakout(option_chain)
        if pcr_signal: signals.append(pcr_signal)

        price_change = _float(strategy.get('price_change'), 0)
        current_volume = _int(strategy.get('current_volume'), 0)
        vol_signal = self._volume_price_breakout(price_change, current_volume, avg_volume)
        if vol_signal: signals.append(vol_signal)

        day_high = _float(strategy.get('day_high'), 0)
        day_low  = _float(strategy.get('day_low'), 0)
        atr_signal = self._range_atr_breakout(day_high, day_low, atr)
        if atr_signal: signals.append(atr_signal)

        oi_change = _int(strategy.get('oi_change'), 0)
        vol_change = _int(strategy.get('volume_change'), 0)
        oi_signal = self._oi_volume_breakout(oi_change, vol_change)
        if oi_signal: signals.append(oi_signal)

        # Act on signals
        if signals:
            logging.warning(f"Breakout signals for strategy {sid}: {signals}")
            self.strategy_store.set_breakout_signals(sid, signals)
