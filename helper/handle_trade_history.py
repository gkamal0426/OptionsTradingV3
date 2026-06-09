from datetime import datetime
from collections import defaultdict
import logging


class TradeHistoryHandler:

    def __init__(self, user):

        self.user = user

    # ── Public entry point ─────────────────────────────────────────────────

    def get_summary(self, from_date: str = None, to_date: str = None) -> dict:

        try:
            raw = self._fetch_report(from_date, to_date)
            if not raw:
                return self._empty_response('No trades found')

            fills = self._parse_fills(raw)
            if not fills:
                return self._empty_response('No valid fills found')

            symbol_summary = self._build_symbol_summary(fills)
            order_summary  = self._build_order_summary(fills)
            day_summary    = self._build_day_summary(symbol_summary, fills)
            trade_log      = self._build_trade_log(fills)

            return {
                'stat':           'ok',
                'day_summary':    day_summary,
                'symbol_summary': symbol_summary,
                'order_summary':  order_summary,
                'trade_log':      trade_log,
            }

        except Exception as e:
            logging.error(f"TradeHistoryHandler.get_summary error: {e}")
            import traceback
            traceback.print_exc()
            return self._empty_response(str(e))

    # ── Step 1: Fetch from API ─────────────────────────────────────────────

    def _fetch_report(self, from_date=None, to_date=None) -> list:

        try:
            """if from_date and to_date:
                raw = self.user.client.trade_report(
                    from_date=from_date,
                    to_date=to_date
                )
            else:"""
            raw = self.user.client.trade_report()

            if not raw or raw.get('stat') != 'ok':
                msg = raw.get('message', 'trade_report failed') if raw else 'Empty response'
                logging.warning(f"trade_report API: {msg}")
                return []

            return raw.get('data', [])

        except Exception as e:
            logging.error(f"_fetch_report error: {e}")
            return []

    # ── Step 2: Parse raw fills ────────────────────────────────────────────

    def _parse_fills(self, raw_data: list) -> list:
        """
        Converts raw API dicts into clean, typed fill records.

        Key mappings:
            trnsTp  → 'B' (Buy) or 'S' (Sell)
            fldQty  → filled quantity (shares, not lots)
            avgPrc  → average fill price
            lotSz   → lot size (to compute lots)
            exTm    → execution datetime string
        """
        fills = []
        for item in raw_data:
            try:
                qty    = int(item.get('fldQty', 0))
                price  = float(item.get('avgPrc', 0))
                lot_sz = int(item.get('lotSz', 1)) or 1

                if qty <= 0 or price <= 0:
                    continue  # skip unfilled / bad records

                side = item.get('trnsTp', '').upper()  # 'B' or 'S'
                if side not in ('B', 'S'):
                    continue

                # Parse execution time
                exec_time_str = item.get('exTm', '') or item.get('hsUpTm', '')
                exec_dt = self._parse_datetime(exec_time_str)

                fills.append({
                    # Identity
                    'ordNo':    item.get('nOrdNo', ''),
                    'fillId':   item.get('flId', ''),
                    'symbol':   item.get('sym', ''),
                    'trdSym':   item.get('trdSym', ''),
                    'optType':  item.get('optTp', ''),
                    'strike':   float(item.get('stkPrc', 0)),
                    'expiry':   item.get('expDt', ''),
                    'segment':  item.get('exSeg', ''),
                    'product':  item.get('prod', ''),

                    # Trade data
                    'side':     side,           # 'B' or 'S'
                    'qty':      qty,            # in shares/units
                    'lots':     round(qty / lot_sz, 2),
                    'price':    price,
                    'value':    round(qty * price, 2),  # total trade value
                    'lotSz':    lot_sz,

                    # Time
                    'execTime': exec_dt.strftime('%H:%M:%S') if exec_dt else exec_time_str,
                    'execDate': exec_dt.strftime('%d %b %Y')  if exec_dt else '',
                    'execDt':   exec_dt,        # for sorting
                    'fillTime': item.get('flTm', ''),

                    # Order meta
                    'priceType': item.get('prcTp', ''),   # MKT / L (limit)
                    'guiOrdId':  item.get('GuiOrdId', ''),
                })

            except Exception as e:
                logging.warning(f"Skipping fill parse error: {e} — {item.get('trdSym','?')}")
                continue

        # Sort chronologically
        fills.sort(key=lambda x: x['execDt'] or datetime.min)
        return fills

    # ── Step 3: Symbol-wise summary (round-trip P&L) ──────────────────────

    def _build_symbol_summary(self, fills: list) -> list:
        """
        Groups fills by trdSym and computes per-symbol P&L.

        Logic:
          - buy_value  = sum of (qty × price) for all Buy fills
          - sell_value = sum of (qty × price) for all Sell fills
          - buy_qty    = total qty bought
          - sell_qty   = total qty sold
          - realised_pnl = sell_value - buy_value
            (works correctly for both long and short round-trips)
          - net_qty    = buy_qty - sell_qty
            (0 = fully closed, +ve = still long, -ve = still short)
          - avg_buy    = buy_value / buy_qty
          - avg_sell   = sell_value / sell_qty
        """
        grouped = defaultdict(lambda: {
            'buy_qty': 0, 'sell_qty': 0,
            'buy_value': 0.0, 'sell_value': 0.0,
            'fills': [], 'times': []
        })

        for f in fills:
            g = grouped[f['trdSym']]
            g['fills'].append(f)
            g['times'].append(f['execDt'])

            if f['side'] == 'B':
                g['buy_qty']   += f['qty']
                g['buy_value'] += f['value']
            else:
                g['sell_qty']   += f['qty']
                g['sell_value'] += f['value']

        results = []
        for trd_sym, g in grouped.items():
            buy_qty    = g['buy_qty']
            sell_qty   = g['sell_qty']
            buy_val    = g['buy_value']
            sell_val   = g['sell_value']
            lot_sz     = g['fills'][0]['lotSz']

            avg_buy    = round(buy_val  / buy_qty,  2) if buy_qty  > 0 else 0.0
            avg_sell   = round(sell_val / sell_qty, 2) if sell_qty > 0 else 0.0
            net_qty    = buy_qty - sell_qty
            net_lots   = round(net_qty / lot_sz, 2)

            # Realised P&L on closed portion only
            closed_qty   = min(buy_qty, sell_qty)
            realised_pnl = round((avg_sell - avg_buy) * closed_qty, 2) if closed_qty > 0 else 0.0

            # Trade direction (net)
            if net_qty > 0:
                net_direction = 'LONG'
            elif net_qty < 0:
                net_direction = 'SHORT'
            else:
                net_direction = 'CLOSED'

            # First/last fill times
            valid_times = [t for t in g['times'] if t]
            first_fill  = min(valid_times).strftime('%H:%M:%S') if valid_times else '—'
            last_fill   = max(valid_times).strftime('%H:%M:%S') if valid_times else '—'

            # Reference fill for identity fields
            ref = g['fills'][0]

            results.append({
                'trdSym':       trd_sym,
                'symbol':       ref['symbol'],
                'optType':      ref['optType'],
                'strike':       ref['strike'],
                'expiry':       ref['expiry'],
                'product':      ref['product'],

                'buyQty':       buy_qty,
                'sellQty':      sell_qty,
                'netQty':       net_qty,
                'netLots':      net_lots,
                'buyLots':      round(buy_qty  / lot_sz, 2),
                'sellLots':     round(sell_qty / lot_sz, 2),
                'lotSz':        lot_sz,

                'avgBuy':       avg_buy,
                'avgSell':      avg_sell,
                'buyValue':     round(buy_val,  2),
                'sellValue':    round(sell_val, 2),

                'realisedPnl':  realised_pnl,
                'netDirection': net_direction,

                'fillCount':    len(g['fills']),
                'firstFill':    first_fill,
                'lastFill':     last_fill,
            })

        # Sort by |realised_pnl| descending — biggest trades first
        results.sort(key=lambda x: abs(x['realisedPnl']), reverse=True)
        return results

    # ── Step 4: Day summary ────────────────────────────────────────────────

    def _build_day_summary(self, symbol_summary: list, fills: list) -> dict:
        """
        Aggregates across all symbols for the top-level day stats.

        Trader-relevant metrics:
          - gross_pnl      : sum of all realised P&L
          - total_lots     : total lots traded (buy + sell side)
          - total_turnover : total value of all fills (buy + sell)
          - win_rate       : % of symbols with positive P&L (closed only)
          - avg_win        : average P&L of winning symbols
          - avg_loss       : average P&L of losing symbols
          - best_trade     : highest single symbol P&L
          - worst_trade    : lowest single symbol P&L
          - total_fills    : number of individual fills
          - unique_symbols : number of unique instruments traded
        """
        gross_pnl     = round(sum(s['realisedPnl'] for s in symbol_summary), 2)
        total_turnover = round(sum(f['value'] for f in fills), 2)
        total_fills   = len(fills)
        unique_syms   = len(symbol_summary)

        # Total lots traded (buy-side + sell-side, not net)
        total_buy_lots  = round(sum(f['lots'] for f in fills if f['side'] == 'B'), 2)
        total_sell_lots = round(sum(f['lots'] for f in fills if f['side'] == 'S'), 2)
        total_lots      = round(total_buy_lots + total_sell_lots, 2)

        # Win/loss breakdown — only on CLOSED positions (full round-trips)
        closed  = [s for s in symbol_summary if s['netDirection'] == 'CLOSED' and s['realisedPnl'] != 0]
        winners = [s for s in closed if s['realisedPnl'] > 0]
        losers  = [s for s in closed if s['realisedPnl'] < 0]

        win_rate  = round(len(winners) / len(closed) * 100, 1) if closed else 0.0
        avg_win   = round(sum(s['realisedPnl'] for s in winners) / len(winners), 2) if winners else 0.0
        avg_loss  = round(sum(s['realisedPnl'] for s in losers)  / len(losers),  2) if losers  else 0.0

        # Profit factor = gross wins / abs(gross losses)
        gross_wins   = sum(s['realisedPnl'] for s in winners)
        gross_losses = abs(sum(s['realisedPnl'] for s in losers))
        profit_factor = round(gross_wins / gross_losses, 2) if gross_losses > 0 else 0.0

        # Best and worst single symbol
        if symbol_summary:
            best  = max(symbol_summary, key=lambda s: s['realisedPnl'])
            worst = min(symbol_summary, key=lambda s: s['realisedPnl'])
        else:
            best = worst = None

        # Estimated charges (rough: 0.05% of turnover, capped at ₹20/order for FO)
        est_charges = round(total_turnover * 0.0005, 2)

        return {
            'grossPnl':      gross_pnl,
            'estCharges':    est_charges,
            'netPnl':        round(gross_pnl - est_charges, 2),

            'totalLots':     total_lots,
            'buyLots':       total_buy_lots,
            'sellLots':      total_sell_lots,
            'totalTurnover': total_turnover,
            'totalFills':    total_fills,
            'uniqueSymbols': unique_syms,

            'winRate':       win_rate,
            'avgWin':        avg_win,
            'avgLoss':       avg_loss,
            'profitFactor':  profit_factor,
            'totalWinners':  len(winners),
            'totalLosers':   len(losers),
            'totalClosed':   len(closed),

            'bestTrade': {
                'symbol': best['trdSym'],
                'pnl':    best['realisedPnl']
            } if best else None,

            'worstTrade': {
                'symbol': worst['trdSym'],
                'pnl':    worst['realisedPnl']
            } if worst else None,
        }

    # ── Step 5: Order-wise net position summary ───────────────────────────

    def _build_order_summary(self, fills: list) -> list:
        """
        Groups fills by (trdSym + nOrdNo) to show net position
        per individual order number.

        This answers: "For each order I placed today, what was the
        net qty, direction, price, and contribution to P&L?"

        Structure of each row:
          - ordNo       : order number
          - trdSym      : instrument
          - symbol      : underlying
          - optType     : CE / PE
          - strike      : strike price
          - expiry      : expiry date
          - side        : BUY / SELL (direction of THIS order)
          - qty         : filled quantity
          - lots        : filled lots
          - price       : average fill price of this order
          - value       : qty × price
          - priceType   : MKT / L
          - execTime    : fill time
          - netQtyImpact: +qty for BUY, -qty for SELL
                          (shows how this order moved net position)
          - runningNetQty: cumulative net qty for this symbol
                           after this order executes (running total)
        """
        from collections import defaultdict

        # Running net qty tracker per symbol
        running_net = defaultdict(int)

        # Group by ordNo (one ordNo = one order, may have multiple fills in edge cases)
        # But Kotak trade_report gives one row per fill, so group by ordNo
        order_groups = defaultdict(list)
        for f in fills:
            order_groups[f['ordNo']].append(f)

        results = []
        for ord_no, ord_fills in order_groups.items():
            # Aggregate fills within same order number
            ref      = ord_fills[0]
            total_qty   = sum(f['qty']   for f in ord_fills)
            total_val   = sum(f['value'] for f in ord_fills)
            avg_price   = round(total_val / total_qty, 2) if total_qty > 0 else 0.0
            lots        = round(total_qty / ref['lotSz'], 2)
            side        = ref['side']    # all fills of same order have same side

            # Net qty impact: +qty for BUY, -qty for SELL
            impact = total_qty if side == 'B' else -total_qty

            # Update running net for this symbol
            sym_key = ref['trdSym']
            running_net[sym_key] += impact
            running_net_qty = running_net[sym_key]

            # Running direction after this order
            if running_net_qty > 0:
                running_dir = 'LONG'
            elif running_net_qty < 0:
                running_dir = 'SHORT'
            else:
                running_dir = 'FLAT'   # fully squared off at this point

            results.append({
                # Identity
                'ordNo':          ord_no,
                'trdSym':         ref['trdSym'],
                'symbol':         ref['symbol'],
                'optType':        ref['optType'],
                'strike':         ref['strike'],
                'expiry':         ref['expiry'],
                'product':        ref['product'],
                'priceType':      ref['priceType'],

                # This order
                'side':           'BUY' if side == 'B' else 'SELL',
                'qty':            total_qty,
                'lots':           lots,
                'price':          avg_price,
                'value':          round(total_val, 2),
                'execTime':       ref['execTime'],

                # Net position tracking
                'netQtyImpact':   impact,          # +ve = added long, -ve = added short
                'runningNetQty':  running_net_qty,  # cumulative for this symbol
                'runningNetLots': round(running_net_qty / ref['lotSz'], 2),
                'runningDir':     running_dir,      # LONG / SHORT / FLAT after this order
            })

        # Sort chronologically by fill time
        results.sort(key=lambda x: x['execTime'])
        return results

    # ── Step 6: Raw trade log ──────────────────────────────────────────────

    def _build_trade_log(self, fills: list) -> list:
        """
        Returns each individual fill enriched with display-ready fields.
        Sorted chronologically.
        """
        log = []
        for f in fills:
            log.append({
                'ordNo':     f['ordNo'],
                'fillId':    f['fillId'],
                'time':      f['execTime'],
                'date':      f['execDate'],
                'symbol':    f['symbol'],
                'trdSym':    f['trdSym'],
                'optType':   f['optType'],
                'strike':    f['strike'],
                'expiry':    f['expiry'],
                'side':      'BUY'  if f['side'] == 'B' else 'SELL',
                'qty':       f['qty'],
                'lots':      f['lots'],
                'price':     f['price'],
                'value':     f['value'],
                'priceType': f['priceType'],  # MKT or L (Limit)
                'product':   f['product'],
            })
        return log

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_datetime(dt_str: str):
        """Tries multiple Kotak datetime formats."""
        if not dt_str:
            return None
        formats = [
            '%d-%b-%Y %H:%M:%S',   # 02-Mar-2026 09:19:16  (exTm)
            '%Y/%m/%d %H:%M:%S',   # 2026/03/02 09:19:16   (hsUpTm)
            '%d-%m-%Y %H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
        ]
        for fmt in formats:
            try:
                return datetime.strptime(dt_str.strip(), fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _empty_response(message: str = '') -> dict:
        return {
            'stat':    'error',
            'message': message,
            'day_summary': {
                'grossPnl': 0, 'estCharges': 0, 'netPnl': 0,
                'totalLots': 0, 'buyLots': 0, 'sellLots': 0,
                'totalTurnover': 0, 'totalFills': 0, 'uniqueSymbols': 0,
                'winRate': 0, 'avgWin': 0, 'avgLoss': 0,
                'profitFactor': 0, 'totalWinners': 0, 'totalLosers': 0,
                'totalClosed': 0, 'bestTrade': None, 'worstTrade': None,
            },
            'symbol_summary': [],
            'order_summary':  [],
            'trade_log':      [],
        }