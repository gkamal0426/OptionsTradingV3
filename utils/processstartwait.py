from datetime import datetime, timedelta
import traceback
import logging
import time
import os
import sys

from utils.decorators import log_exceptions

@log_exceptions
def timewait(processtime, remarks):    
    now = datetime.now()
    target_time = datetime.combine(now.date(), datetime.strptime(processtime, "%H:%M").time())
    if now >= target_time:
        return False
    else:
        TL = target_time - now
        TLIS = max(TL.total_seconds(), 2)  # Protect against negative values
        logging.info(f"⏳ {now.strftime('%H:%M:%S')} | {remarks} time not reached yet. Time left: {TL} ({int(TLIS)}s)")
        if TLIS <= 30: time.sleep(TLIS)
        else:
            sleep_time = max(TLIS / 2, 30)
            time.sleep(sleep_time)
    return True