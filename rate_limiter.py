import time
from threading import Lock

RATE_LIMIT_PER_SEC = 2   # adjust based on your Azure quota
lock = Lock()
last_call = 0

def rate_limited_call(func, *args, **kwargs):
    global last_call
    with lock:
        now = time.time()
        wait = max(0, (1 / RATE_LIMIT_PER_SEC) - (now - last_call))
        if wait > 0:
            time.sleep(wait)
        last_call = time.time()
    return func(*args, **kwargs)