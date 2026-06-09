from functools import wraps
from flask import session, jsonify, redirect, url_for

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated




import logging
import traceback
import functools
import time

def log_exceptions(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logging.error(f"❌ Exception in {func.__name__}:\n{e}\nTraceback:\n{traceback.format_exc()}")
            return None
    return wrapper

def log_execution(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logging.info(f"🔄 Starting {func.__qualname__}")
        result = func(*args, **kwargs)
        logging.info(f"✅ Completed {func.__qualname__}")
        return result
    return wrapper

def timeit(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        logging.info(f"⏱ {func.__qualname__} took {duration:.2f} sec")
        return result
    return wrapper

STRATEGY_REGISTRY = {}

def strategy(name):
    def decorator(func):
        STRATEGY_REGISTRY[name.lower()] = func
        return func
    return decorator

def strategy_log_execution(func):
    def wrapper(self, *args, **kwargs):
        logging.info(f"🚀 Starting strategy: {self.strategy}")
        result = func(self, *args, **kwargs)
        logging.info(f"✅ Completed strategy: {self.strategy}")
        return result
    return wrapper

from functools import wraps

def retry_on_exception(retries=3, wait=2, fallback=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logging.error(f"🔄 Attempt {attempt+1}/{retries} failed in {func.__name__}: {e}\n Traceback: {traceback.format_exc()}")
                    time.sleep(wait)
            logging.error(f"❌ All {retries} attempts failed for {func.__name__}")
            return fallback
        return wrapper
    return decorator

def timetaken(threshold=None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start
            if threshold and duration > threshold:
                logging.warning(f"⏱ {func.__qualname__} exceeded {threshold}s ({duration:.2f}s)")
            else:
                logging.info(f"⏱ {func.__qualname__} took {duration:.2f} sec")
            return result
        return wrapper
    return decorator
