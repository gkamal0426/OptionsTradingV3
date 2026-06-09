import datetime
import logging
import os
import sys
from utils.decorators import log_exceptions
from variables.start_from_here import to_start_get


def _now():
    return datetime.datetime.now()

@log_exceptions
def getdailyfolderpath():
    basefolder = to_start_get('app_log_path')
    todaystr = _now().strftime('%Y-%m-%d')
    fullpath = os.path.join(basefolder, todaystr)        
    os.makedirs(fullpath, exist_ok=True)
    return fullpath


def _filepath(log_folder, log_prefix):
    fullpath = log_folder or getdailyfolderpath()
    datesheet = _now().strftime("%d-%b-%y")
    filename = f"{log_prefix}_{datesheet}.log"
    return os.path.join(fullpath, filename)

def _log_formatter():
    return logging.Formatter(
        '%(asctime)s,%(msecs)03d | %(levelname)s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def _console_formatter():
    return logging.Formatter(
        '%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def suppress_sdk(logfilepath):
    # Websocket logger
    sdk_logger = logging.getLogger("websocket")
    sdk_logger.setLevel(logging.DEBUG)      # allow all levels to be captured
    sdk_logger.propagate = False            # stop bubbling up to root (console handler)

    sdk_handler = logging.FileHandler("sdk.log", encoding="utf-8")
    sdk_handler.setLevel(logging.DEBUG)
    sdk_handler.setFormatter(_log_formatter())
    sdk_logger.addHandler(sdk_handler)

    logging.getLogger("neo_api_client").setLevel(logging.DEBUG)
    logging.getLogger("neo_api_client").propagate = True   # keep them in root file handler
    logging.getLogger("HSWebSocketLib").setLevel(logging.DEBUG)
    logging.getLogger("HSWebSocketLib").propagate = True

    logging.debug(f"📁 Logging started at {logfilepath}")



def setup_logger(log_prefix="app_logs", log_folder=None):
    logfilepath  = _filepath(log_folder, log_prefix)
    
    file_handler = logging.FileHandler(logfilepath, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(_log_formatter())

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(_console_formatter())

    logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, console_handler], force=True)
    
    suppress_sdk(logfilepath)
    
    return logfilepath




def user_setup_logger(user, filename = 'default', log_folder=None):
    user.logger = logging.getLogger(f"Session-{filename}")
    user.logger.setLevel(logging.DEBUG)
    logfilepath = _filepath(log_folder, f"Session_{filename}")

    handler = logging.FileHandler(logfilepath, encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(_log_formatter())

    user.logger.addHandler(handler)
    user.logger.propagate = False    # 🔹 Prevent duplication into the central app log

    user.logger.info("Session manager initialized")
