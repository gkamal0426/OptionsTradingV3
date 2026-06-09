import logging
from utils.safe_variables import _float

def get_margin_details(user):
    with user.margin_lock:
        tot_mar = 0
        used_mar = 0
        bal_mar = 0

        try:

            string = next((d for d in user.symbolsandtokens if d.get('tag', '').upper() != "INDEX"), {})

            """
            string = {}
            for d in user.symbolsandtokens:
                if d.get('tag').upper() != "INDEX":
                    string = d
                    break
            """
            
            if not string:
                logging.info("Add strike/symbol to fetch margins details !")
                return {}

            quantity = string.get('lot_size', 1)
            instrument_token = string.get('token', "")
            exchange = string.get('exchange', 'nse_fo')
        
            result = user.client.margin_required(
                exchange_segment = exchange, 
                price = "0", 
                order_type= "MKT", 
                product = "NRML",   
                quantity = str(quantity), 
                instrument_token = str(instrument_token),  
                transaction_type = "S")
            
            data = result.get('data', {})
            if data:
                tot_mar = round(_float(data.get('avlCash'), 0.0)/100000,2)
                used_mar = round(_float(data.get('mrgnUsd'), 0.0)/100000,2)
                bal_mar = round((tot_mar-used_mar),2)
                user.margins = {'total_margin' :tot_mar, 'used_margin' : used_mar, 'balance_margin' : (bal_mar)}

        except Exception:
            logging.exception("Exception while feching margins")
            return {}    

        
        return {'total_margin' :tot_mar, 'used_margin' : used_mar, 'balance_margin' : (bal_mar)}