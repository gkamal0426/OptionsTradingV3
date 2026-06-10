import logging
import threading 
import time
import pandas as pd
import datetime
import os
import traceback
import queue
from utils.safe_variables import _float, _int, custom_round_b, custom_round_s, _today
from utils.margins import get_margin_details
from variables.start_from_here import to_start_get
from utils.communication import CallTelegram

def amo_time(start_time, end_time):
    now = datetime.datetime.now()
    start = datetime.datetime.combine(now.date(), datetime.datetime.strptime(start_time, "%H:%M").time())
    end = datetime.datetime.combine(now.date(), datetime.datetime.strptime(end_time, "%H:%M").time())
    return start <= now <= end

def get_mcx_ltp_feed(user, symbol):
    token = None
    for data in user.mcx_symbols_tokens:
        if data.get('symbol') == symbol:
            token =  str(data.get('token')) or None
    
    if not token:
        return None
    
    with user.lock:
        ltp_data= user.ltp_feed.copy()

    if token in ltp_data:
        return ltp_data[token]
    
    feed = user.client.quotes(instrument_tokens = [{"instrument_token": token, "exchange_segment": "mcx_fo"}], quote_type = "ltp")
    return feed[0].get('ltp') if feed else None



def place_order(session, symbol, quantity, trans_type, order_type, price, exchange, product = "NRML", amo = "NO", trigger_price="0"):
    response = session.client.place_order(
        exchange_segment=exchange,
        product=product,
        price=str(price),
        order_type=order_type,
        quantity=str(quantity),
        validity="DAY",
        trading_symbol=symbol,
        transaction_type=trans_type,
        amo=amo,
        disclosed_quantity="0",
        market_protection="0",
        pf="N",
        trigger_price=str(trigger_price),
        tag=None,
        scrip_token=None,
        square_off_type=None,
        stop_loss_type=None,
        stop_loss_value=None,
        square_off_value=None,
        last_traded_price=None,
        trailing_stop_loss=None,
        trailing_sl_value=None)
    #logging.info(response)
    return response        


class OrderReport:
    def __init__(self):
        pass

    @staticmethod
    def _get_order_history(user, order_id):
        try:
            if order_id:    
                with user.report_lock:
                    return user.client.order_history(order_id=order_id).get('data').get('data') or []
        except Exception as e:
            logging.exception(f"Exception while extractig order report for {order_id}. Exception : {e}")
        return []



    def update_order_history(self, user):
        if not user.orders_report:
            return
        for data in user.orders_report:
            order_data = self._get_order_history(user, data.get('order_no'))
            if isinstance(order_data, list) and order_data:
                order_status = order_data[0]
                data['status'] = (order_status.get('ordSt') or "NA").upper()
                data['reason'] = order_status.get('rejRsn')
            else:
                data['status'] = "NA"

    def _append_order(self, order_no, data):
        return {
            'order_no': order_no,
            'Order_place': 'SUCCESS',
            'Process': "MANUAL",
            'source': "Order_report",
            'symbol': data.get('trdSym'),
            'trans_type': data.get('trnsTp'),
            'Order_Type': data.get('prcTp'),
            'Order_Price': data.get('avgPrc'),
            'Lots': data.get('lotSz'),
            'Quantity': data.get('qty'),
            'status': (data.get('ordSt') or "").upper(),
            'reason': data.get('rejRsn')
            }
    

    def add_order_from_order_history(self, user):
        with user.report_lock:                
            result = user.client.order_report()
            orders_data = result.get('data', [])
            if not isinstance(orders_data, list) or not orders_data:
                return None            
            existing_orders = {order.get('order_no') for order in user.orders_report}
            for data in orders_data:
                order_no = data.get('nOrdNo')
                if order_no not in existing_orders:
                    user.orders_report.append(self._append_order(order_no, data))
                    existing_orders.add(order_no)


    @staticmethod
    def _get_trade_report(user, order_id):
        try:    
            if order_id:
                with user.report_lock:
                    return user.client.trade_report(order_id=order_id).get('data') or {}
        except Exception as e:
            logging.exception(f"Exception while extractig trade report for {order_id}. Exception : {e}")
        return {}
        
    def update_trade_history(self, user):
        if not user.orders_report:
            return
        for data in user.orders_report:
            trade_data = self._get_trade_report(user, data.get('order_no'))
            if isinstance(trade_data, dict):
                    
                data['Avg_Price'] = _float(trade_data.get('avgPrc')) or 0.0
                data['Time'] = trade_data.get('exTm') or 'NA'
            else:
                data['Avg_Price'] =  0.0
                data['Time'] =  'NA'


    def _orders_report_available(self, user):
        if not user or not getattr(user, "orders_report", None):
            logging.warning("No orders_report found for user")
            return False
        return True

    def _return_path(self, orders_path, user):
        return f"{orders_path}/{getattr(user, 'UC', 'UNKNOWN')}_ORDERS_REPORT_{_today()}.csv"


    def export_orders_report(self, user):
        try:
            if not self._orders_report_available(user):     return
            orders_path = to_start_get('or_path')
            with user.report_lock:
                df = pd.DataFrame(user.orders_report)
            os.makedirs(orders_path, exist_ok=True)
            df.to_csv(self._return_path(orders_path, user), index=False)
        except Exception as e:
            logging.exception(f"Orders Report export error. Exception: {e}")


    def run_update_functions(self, user):
        result = get_margin_details(user)
        self.update_order_history(user)
        self.add_order_from_order_history(user)
        self.update_trade_history(user)
        self.export_orders_report(user)

    def order_trade_history_update(self, user):
        while True:
            delay = user.history_update_time - time.time()
            if delay > 0:
                time.sleep(delay)
            else:
                user.order_history_flag = True
                self.run_update_functions(user)
                break





class MessageMaker:
    def __init__(self):
        pass

    def _print_message(self):
        return (
            f"\n{'='*32}\n"
            f"  user : {self.user.name}\n"
            f"📊 Order Request:\n"
            f"   Source: {self.source}\n"
            f"   Symbol: {self.symbol}\n"
            f"   Action: {self.action.upper()}\n"
            f"   Order Type: {self.order_type}\n"
            f"   Price: {self.price}\n"
            f"   Lots: {self.lot_quantity}\n"
            f"   Lot Size: {self.lot_size}\n"
            f"   Total Quantity: {self.actual_quantity}\n"
            f"   Transaction Type: {self.trans_type}\n"
            f"   Last Trade Price: {self.ltp}\n"
            f"{'='*32}\n\n"
        )




    def _start_end_message(self, order_no, failed_reason):
        if failed_reason =="NA":
            return f"✅ SUCCESS! : ", f"Order ID: {order_no}"
        else:
            return f"❌ FAILED! :", f"Reason : {failed_reason}\n"

    def _center_message(self, order_type_text, input_type):
        if input_type == 'single_order':                
            return (f"\nSymbol: {self.symbol}\nAction: {self.action.upper()}\nOrder Type: {order_type_text}\n"
                            f"Lots: {self.lot_quantity}\nQuantity: {self.actual_quantity}\n\n")
        elif input_type == 'bulk_order':
            return (f"Symbol: {self.symbol} ({self.actual_quantity}) : {self.action.upper()} - {order_type_text} : ")

    def _json_message(self, order_no, failed_reason, input_type):
        order_type_text = "MARKET" if self.order_type == "MKT" else f"LIMIT @ ₹{_float(self.price):.2f}"
        message_start, message_end = self._start_end_message(order_no, failed_reason)
        return message_start + self._center_message(order_type_text, input_type) + message_end

    def _bulk_order_not_initiated_message(self, message):
        return {'summary' : {"success": 0, "failed": 0, "total": 0},
                'results' : [{'symbol': 'NA','status': 'failed', 'message': message}]}




class OrderCalculationHelper:
    def __init__(self):
        pass

    def _get_capping_amount(self):
        for key, value in self.mcx_price_cap.items():
            if self.symbol.startswith(key):
                return _float(value, 0.05)
        return 0.05


    def _ltp_quotes(self, token):        
        inst_token = [{"instrument_token": str(token), "exchange_segment": self.exchange}]
        try:
            result = self.user.client.quotes(instrument_tokens = inst_token, quote_type = "ltp")
            if isinstance(result, list) and result:
                return result[0].get('ltp', 0)
        except Exception:
            logging.exception("Exception while fetching LTP")
        return 0
    

    def _set_limit_price(self, ltp, tolrance):       
        if self.trans_type == 'B':
            self.price =  custom_round_b((ltp * (1 + tolrance)))
            return True
        elif self.trans_type == 'S':
            self.price = custom_round_s((ltp * (1 - tolrance)))
            return True
        return False

    def _convert_to_limit_order(self):
        token = next((data.get('token') for data in self.user.symbolsandtokens if data.get('symbol') == self.symbol),None)
        if not token:
            return False
        self.ltp = _float(self._ltp_quotes(token), 0.0)
        if self.ltp and self.ltp>0:
            tolrance = self._set_price_buffer(self.ltp, _float(self.limit_price_buffer, 0.1))
            if tolrance >0:
                self.order_type = 'L'
                return self._set_limit_price(self.ltp, tolrance)
        return False

    def _mcx_ltp_check_before_orderprocess(self):
        ltp = _float(get_mcx_ltp_feed(self.user, self.symbol), 0.0)
        if not ltp:
            return f"LTP not updated for {self.symbol}"
        limit_pct = _float(self.ltp_vs_limit_price)        
        caping = self._get_capping_amount()        
        pct = round((ltp / self.price * 100), 0) if self.price else 0

        if (not self.price or self.price == 0) and (ltp > caping):
            return f"LTP is greater than {caping} of {self.symbol}. Market price order not allowed."            
        if (self.trans_type == "S") and (ltp > caping) and (ltp > min( (limit_pct * self.price), (self.price + caping))):
            return f"LTP is greater than {caping} of {self.symbol} and {pct}% of limit price. Not processing SELL order"
        if (self.trans_type == "B") and (self.price > caping) and (self.price > min( (ltp *limit_pct), (ltp+caping))) :
                return f"LTP({ltp}) is too less compare to limit price({self.price}). Not processing order"
        return None



class OrderHelper(MessageMaker, OrderCalculationHelper): 
    def __init__(self, users=None):
        self.report_queue = queue.Queue()
        self.initiate_queue = queue.Queue()
        self.completed_queue = queue.Queue()

        threading.Thread(target=self._process_reports, daemon=True).start()
        threading.Thread(target=self._initiate_order_message, daemon=True).start()
        threading.Thread(target=self._completed_order_message, daemon=True).start()
        self.telegram_flag = False
        self._get_yaml_variables()
        self._re_set_variables()
        self.users = users
        self.telegram = CallTelegram()


    def _initiate_order_message(self):
        while True:
            uc, message = self.initiate_queue.get()
            try:
               self._confirmation(uc, message)
            finally:
                self.initiate_queue.task_done()

    def _get_message_from_trade_report(self, t, ordno, symb):
        if isinstance(t, dict) and t:
            return f"🎉{symb}-{ordno}-{t.get('fldQty')}-{_float(t.get('avgPrc'))}-{t.get('trnsTp')}-{t.get('exTm')}"
        return None

    def _get_message_from_order_report(self, orders_data, ordno, symbol):
        if isinstance(orders_data, list) and orders_data:
            s = orders_data[0]
            return f"❌ {symbol}-{ordno}-status-{(s.get('ordSt') or 'NA').upper()}-{s.get('rejRsn')})"
        return None


    def _completed_order_message(self):
        while True:
            user, order_no, symbol = self.completed_queue.get()
            try:

                message = self._get_message_from_trade_report(OrderReport._get_trade_report(user, order_no), order_no, symbol)
                if not message:
                    message = self._get_message_from_order_report(OrderReport._get_order_history(user, order_no), order_no, symbol)
                if not message:
                    logging.info(f"{order_no} now found in Trade and order reports. retrying")
                    time.sleep(getattr(self, 'wait', 10))
                    self.completed_queue.put((user, order_no, symbol))
                else:
                    self.initiate_queue.put((getattr(user,'UC','default'), message))

            finally:
                self.completed_queue.task_done()


    def _response_place_order(self, response):
        order_no = None
        failed_reason = 'NA'
        if response.get("stat") == 'Ok':
            order_no = response.get('nOrdNo')
            print_confirmation = f'✅ Order placed successfully: {self.symbol} - {order_no}'
        else:
            failed_reason = response.get('errMsg', 'UNKNOWN')
            if failed_reason == 'UNKNOWN':
                logging.error(f'API Response of order place :\n {response}')
            print_confirmation = f'❌ Order placement failed : {self.symbol}, Reason : {failed_reason} \n {response}'
        self.initiate_queue.put((getattr(self.user,'UC','default'), print_confirmation))
        
        if order_no:
            self.completed_queue.put((self.user, order_no, self.symbol))
        
        return order_no, failed_reason


    def _get_yaml_variables(self):
        import yaml
        from variables.start_from_here import to_start_get
        config_path = to_start_get('orders_variables')
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        for key, value in config.items():
            setattr(self, key, value)


    def _re_set_variables(self):
        for key in getattr(self, 'resettable_variables', []):
            setattr(self, key, None)


    def _set_price_buffer(self, ltp, price_buffer):
        for condition in getattr(self, 'price_buffer_conditions', []):
            if all(k in condition for k in ('low', 'high', 'multiplier')):
                if condition['low'] <= ltp < condition['high']:
                    return price_buffer * condition['multiplier']
        return 0


    def _confirmation(self, uc, message):
        logging.info(message)
        if self.telegram_flag:    
            self.telegram.telegram_message(message, uc)


    def _process_reports(self):
        while True:
            try:
                user, order_input = self.report_queue.get()
                user.orders_report.append(order_input)
                user.history_update_time = time.time() + user.delay_in_history_update
                process = OrderReport()
                if getattr(user, "order_history_flag", True):
                    user.order_history_flag = False
                    threading.Thread(target=process.order_trade_history_update, args=(user,), daemon=True).start()
                self.report_queue.task_done()
            except Exception as e:
                logging.error(f"Error processing order report: {e}")


    def _set_variables(self, data):
        for attr in self.resettable_variables:
            if attr in data:
                setattr(self, attr, data[attr])

        self.order_type = data.get('orderType', 'MKT')

        timing = getattr(self, "order_timing", {}).get(self.exchange, {}) or {}
        start = timing.get('start', '09:15')
        end = timing.get('end', '15:30')
        self.amo = "NO" if amo_time(start, end) else "YES"

        self.lot_quantity = _int(getattr(self, "quantity", 0))
        self.actual_quantity = self.lot_quantity * _int(getattr(self, "lot_size", 0))
        self.quty = str(self.actual_quantity)

        self.price = _float(getattr(self, "price", 0.0), 0.0)



    def _validate_inputs(self):

        if self.order_type == 'L' and (not self.price or _float(self.price) <= 0):
            return {'status':'error','message':'❌ Invalid price for Limit order!'}
        if not self.trans_type:
            return {'status':'error','message':'❌ Invalid action type'}
        return None



    def _place_order(self):

        if self.exchange == 'mcx_fo':                
            message = self._mcx_ltp_check_before_orderprocess()
            if message:
                logging.error(message)
                return {'stat': 'NotOk','errMsg': message }

        elif self.order_type == 'MKT':                
            if not self._convert_to_limit_order():
                return {'stat': 'NotOk','errMsg': "Market order not allowed. Place Limit order" }


        return place_order(
            self.user,  
            self.symbol, 
            self.quty, 
            self.trans_type, 
            self.order_type, 
            self.price, 
            self.exchange,
            self.product,
            self.amo
            )


    def _order_input(self, order_no, failed_reason, process = 'API_NON_SYS'):
        return {
            'order_no': order_no,
            'Order_place': 'SUCCESS' if failed_reason =='NA' else 'FAILED',
            'Process': process,
            'source': self.source,
            'symbol': self.symbol,
            'trans_type': self.action.upper(),
            'Order_Type': self.order_type,
            'Order_Price': self.price,
            'Lots': self.lot_quantity,
            'Quantity': self.actual_quantity,
            'status': 'OPEN' if failed_reason =='NA' else 'CLOSED',
            'reason': failed_reason
        }


            
    def _set_action(self):
        if self.action.lower() == "sell":
            return "S"
        elif self.action.lower() == "buy":
            return "B"
        else:
            return None



    def _response_handling(self, response, process, input_type):
        order_no, failed_reason = self._response_place_order(response)
        message = self._json_message(order_no, failed_reason, input_type)
        order_input = self._order_input(order_no, failed_reason, process)
        self.report_queue.put((self.user, order_input))
        self._re_set_variables()     
        if process != 'API_NON_SYS':
            return response
        if response.get("stat") == "Ok":
            return {'status': 'success', 'message': message, 'order_id': order_no}
        else:
            return {'status': 'error', 'message': message}        
    

    def order_helper(self, data, process = 'API_NON_SYS'):
        try:               
            self._set_variables(data)
            self.trans_type = self._set_action()
            error = self._validate_inputs()
            if error and process == 'API_NON_SYS':
                return error
            self.initiate_queue.put((getattr(self.user,'UC','default'), self._print_message()))
            return self._place_order()
        except Exception as e:
            logging.exception("Exception in Order Helper")
            return {'status': 'error', 'message': f"Exception while processing order {e}"}
    


    def single_order_helper(self, data, process = 'API_NON_SYS'):
        try:
            if process == 'API_NON_SYS':
                self.user = self.users.get(data.get('username'))
            else:
                self.user = data.get('username')
            if not self.user:
                return {'status':'error','message':'❌ Unknown username'}
            self.source =  data.get('source', 'NA')
            response = self.order_helper(data, process)
            return self._response_handling(response, process, 'single_order')
        except Exception as e:
            logging.exception("Exception in Order Helper")
            return {'status': 'error', 'message': f"Exception while processing order {e}"}



    def _append_result(self, order, status, message):
        return {"symbol": order.get("symbol"), "status": status, "message": message}        


    def _bulk_order_processing(self, sorted_orders, process, source):
        results = []
        summary = {"success": 0, "failed": 0}
        with self.user.order_lock:
            for order in sorted_orders:
                try:
                    self.source = source
                    response = self.order_helper(order)
                    processed = self._response_handling(response, process, 'bulk_order')
                    status = "success" if processed.get("status", "").lower() == "success" else "failed"
                    summary[status] += 1
                    results.append(self._append_result(order, status, processed.get('message') or ''))
                except Exception as e:
                    summary['failed'] +=1
                    results.append(self._append_result(order, "failed", str(e)))
            summary['total'] = summary['success'] + summary['failed']

            return {"summary": summary, "results": results}        



    def bulk_order_helper(self, data, process = 'API_NON_SYS'):
        try:               
            username = data.get("username")
            source   = data.get("source", "NA")

            self.user = self.users.get(username, None)
            if not self.user:
                return self._bulk_order_not_initiated_message(f'{username} not logged in')
            orders   = data.get("orders", [])
            if not orders or not isinstance (orders, list):
                return self._bulk_order_not_initiated_message(f'data to place order not available')

            sorted_orders = sorted(orders, key=lambda o: 0 if o.get("action") == "buy" else 1)
            return self._bulk_order_processing(sorted_orders, process, source)

        except Exception as e:
            return self._bulk_order_not_initiated_message(str(e))


    def display_orders(self, username):
            try:
                user = self.users.get(username)
                if not user:
                    return {'status': 'error', 'message': f'{username} not logged in', 'orders': []}
                process = OrderReport()
                process.run_update_functions(user)
                orders = user.orders_report  
                return {'status': 'success', 'orders': orders, 'user': username}
            except Exception as e:
                logging.exception(f"❌ Error fetching orders: {str(e)}")
                
                
                return {'status': 'error', 'message': f'Failed to fetch orders: {str(e)}', 'orders': []}


