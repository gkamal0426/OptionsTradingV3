import datetime

def _float(value, default: float = 0.0, precision: int = 2) -> float:
    try:
        return round(float(value), precision)
    except (ValueError, TypeError):
        return round(default, precision)

    
def _int(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default

def _epoch_to_expiry_str(epoch: int) -> str:
    try:
        dt = datetime.datetime.fromtimestamp(epoch)
        return dt.strftime("%d%b%y").upper()
    except Exception:
        return str(epoch)

def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _today():
    return datetime.date.today().strftime("%Y-%m-%d")


def custom_round_b(x: float) -> float:
    import math
    int_part = math.floor(x)          
    frac_part = x - int_part          
    if frac_part < 0.5:
        return int_part + 0.5
    else:
        return int_part + 1.0
    
def custom_round_s(x: float) -> float:
    import math
    int_part = math.floor(x)          
    frac_part = x - int_part          
    if frac_part > 0.5:
        return int_part + 0.5
    else:
        return int_part if x>0 and int_part>0 else 0.05