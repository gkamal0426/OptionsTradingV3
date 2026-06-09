

import sqlite3
import threading
import logging
from utils.safe_variables import _now


def leg_input(sid, leg):
    return (
        sid,
        leg['trd_symbol'], leg['token'],    leg['opt_type'],
        leg['strike'],     leg['action'],   leg['lots'],
        leg['lot_size'],   leg['quantity'], leg['exchange'],
        leg['entry_ltp'],  leg['entry_ltp'], leg.get('pnl', 0),
        leg.get('order_id', 'NA'), 'OPEN',
    )


def strategy_input(strat, now):
    return (
        strat['user'],            strat['strategy_name'],
        strat['strategy_type'],   strat['underlying_code'],
        strat['underlying_name'], strat['expiry_str'],
        strat['lots'],            strat['total_premium'],
        strat['sl_type'],         strat['sl_value'],
        strat['sl_pct'],
        1 if strat.get('trail_sl') else 0,
        strat.get('trail_step', 0),
        strat.get('target_value', 0),
        'RUNNING', 0, now,
    )

def strategy_insert_sql():
    return """
        INSERT INTO strategies
        (user, strategy_name, strategy_type, underlying_code,
        underlying_name, expiry_str, lots, total_premium,
        sl_type, sl_value, sl_pct, trail_sl, trail_step,
        target_value, status, sl_hit, deployed_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """

def leg_insert_sql():
    return """
        INSERT INTO strategy_legs
        (strategy_id, trd_symbol, token, opt_type, strike,
        action, lots, lot_size, quantity, exchange,
        entry_ltp, current_ltp, pnl, order_id, status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """

def cache_update(sid, strat, now):
    return {
        'id': sid, 'status': 'RUNNING', 'sl_hit': False,
        'deployed_at': now, 'mtm_pnl': 0.0,
        'peak_premium': strat['total_premium'],
    }

def create_strategy_table():
    return """
    CREATE TABLE IF NOT EXISTS strategies (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user            TEXT    NOT NULL,
        strategy_name   TEXT    NOT NULL,
        strategy_type   TEXT    NOT NULL,
        underlying_code TEXT    NOT NULL,
        underlying_name TEXT    NOT NULL,
        expiry_str      TEXT    NOT NULL,
        lots            INTEGER NOT NULL DEFAULT 1,
        total_premium   REAL    NOT NULL DEFAULT 0,
        sl_type         TEXT    NOT NULL DEFAULT 'none',
        sl_value        REAL    NOT NULL DEFAULT 0,
        sl_pct          REAL    NOT NULL DEFAULT 0,
        trail_sl        INTEGER NOT NULL DEFAULT 0,
        trail_step      REAL    NOT NULL DEFAULT 0,
        target_value    REAL    NOT NULL DEFAULT 0,
        status          TEXT    NOT NULL DEFAULT 'RUNNING',
        sl_hit          INTEGER NOT NULL DEFAULT 0,
        deployed_at     TEXT    NOT NULL
    )
    """

def create_legs_table():
    return """
        CREATE TABLE IF NOT EXISTS strategy_legs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER NOT NULL,
            trd_symbol  TEXT    NOT NULL,
            token       TEXT    NOT NULL,
            opt_type    TEXT    NOT NULL,
            strike      REAL    NOT NULL,
            action      TEXT    NOT NULL,
            lots        INTEGER NOT NULL DEFAULT 1,
            lot_size    INTEGER NOT NULL DEFAULT 1,
            quantity    INTEGER NOT NULL,
            exchange    TEXT    NOT NULL,
            entry_ltp   REAL    NOT NULL DEFAULT 0,
            current_ltp REAL    NOT NULL DEFAULT 0,
            pnl         REAL    NOT NULL DEFAULT 0,
            order_id    TEXT    NOT NULL DEFAULT 'NA',
            status      TEXT    NOT NULL DEFAULT 'OPEN',
            FOREIGN KEY (strategy_id) REFERENCES strategies(id)
        )
    """
class StrategyStore:

    def __init__(self):
        self.db_path = "strategy_store.db"
        self._lock  = threading.Lock()
        self._cache = {}
        self._init_db()
        self._reload()
        

    def _conn(self):
        c = sqlite3.connect(self.db_path, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    def _init_db(self):
        with self._conn() as c:
            c.execute(create_strategy_table())
            c.execute(create_legs_table())
            c.commit()

    def _reload(self):
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM strategies WHERE status NOT IN ('EXITED','FAILED')"
            ).fetchall()
            for row in rows:
                s = dict(row)
                s['trail_sl']     = bool(s['trail_sl'])
                s['sl_hit']       = bool(s['sl_hit'])
                s['peak_premium'] = s['total_premium']
                s['legs']         = self._legs_from_db(c, s['id'])
                with self._lock:
                    self._cache[s['id']] = s

    def _legs_from_db(self, conn, strategy_id):
        rows = conn.execute(
            "SELECT * FROM strategy_legs WHERE strategy_id = ?",
            (strategy_id,)
        ).fetchall()
        return [dict(r) for r in rows]


    
    def save(self, strat, legs):
        now = _now()
        with self._conn() as c:
            cur = c.execute(strategy_insert_sql(), strategy_input(strat, now))
            sid = cur.lastrowid
            for leg in legs:
                c.execute(leg_insert_sql(), leg_input(sid, leg))
            c.commit()

        cached = dict(strat)
        cached.update(cache_update(sid, strat, now))
        with self._conn() as c:
            cached['legs'] = self._legs_from_db(c, sid)
        with self._lock:
            self._cache[sid] = cached
        return sid  


    def set_status(self, strategy_id, status):
        with self._lock:
            if strategy_id in self._cache:
                self._cache[strategy_id]['status'] = status
        with self._conn() as c:
            c.execute("UPDATE strategies SET status=? WHERE id=?", (status, strategy_id))
            c.commit()

    def set_sl_hit(self, strategy_id):
        with self._lock:
            if strategy_id in self._cache:
                self._cache[strategy_id]['sl_hit'] = True
                self._cache[strategy_id]['status'] = 'SL_HIT'
        with self._conn() as c:
            c.execute("UPDATE strategies SET sl_hit=1, status='SL_HIT' WHERE id=?", (strategy_id,))
            c.commit()

    def set_leg_status(self, leg_id, status):
        with self._conn() as c:
            c.execute("UPDATE strategy_legs SET status=? WHERE id=?", (status, leg_id))
            c.commit()

    def update_mtm(self, strategy_id, mtm_pnl):
        with self._lock:
            if strategy_id in self._cache:
                self._cache[strategy_id]['mtm_pnl'] = mtm_pnl

    def update_leg_ltp(self, strategy_id, leg_id, ltp):
        with self._lock:
            for leg in self._cache.get(strategy_id, {}).get('legs', []):
                if leg['id'] == leg_id:
                    leg['current_ltp'] = ltp
                    break

    def update_peak_premium(self, strategy_id, peak):
        with self._lock:
            if strategy_id in self._cache:
                self._cache[strategy_id]['peak_premium'] = peak

    def tighten_sl(self, strategy_id, new_sl_value):
        with self._lock:
            if strategy_id in self._cache:
                self._cache[strategy_id]['sl_value'] = new_sl_value

    def get(self, strategy_id):
        with self._lock:
            s = self._cache.get(strategy_id)
            return dict(s) if s else None

    def get_legs(self, strategy_id):
        with self._lock:
            return list(self._cache.get(strategy_id, {}).get('legs', []))

    def all_for_user(self, username):
        with self._lock:
            return [dict(s) for s in self._cache.values() if s.get('user') == username]

    def all_running(self):
        with self._lock:
            return [dict(s) for s in self._cache.values() if s.get('status') == 'RUNNING']
