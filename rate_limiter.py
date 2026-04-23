import os
import random
import time
from threading import Lock

lock = Lock()
last_call = 0.0


def _get_env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return float(default)


def _get_env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return int(default)


def _rate_limit_per_sec() -> float:
    # Conservative default for single-deployment Azure OpenAI usage.
    return max(_get_env_float("RATE_LIMIT_PER_SEC", 0.2), 0.01)


def _max_retries() -> int:
    return max(_get_env_int("RATE_LIMIT_MAX_RETRIES", 8), 1)


def _base_backoff() -> float:
    return max(_get_env_float("RATE_LIMIT_BACKOFF_BASE", 2.0), 0.1)


def _max_backoff() -> float:
    return max(_get_env_float("RATE_LIMIT_BACKOFF_MAX", 60.0), 1.0)


def _reserve_request_slot() -> None:
    global last_call

    with lock:
        min_interval = 1.0 / _rate_limit_per_sec()
        now = time.time()
        wait = max(0.0, min_interval - (now - last_call))
        if wait > 0:
            time.sleep(wait)
        last_call = time.time()


def _is_retryable_throttle(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in (
        "429",
        "too many requests",
        "too_many_requests",
        "rate limit",
        "ratelimit",
    ))


def rate_limited_call(func, *args, **kwargs):
    max_retries = _max_retries()

    for attempt in range(max_retries):
        _reserve_request_slot()
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            if attempt == max_retries - 1 or not _is_retryable_throttle(exc):
                raise

            sleep_for = min(_max_backoff(), _base_backoff() * (2 ** attempt))
            sleep_for += random.uniform(0.0, min(1.0, sleep_for * 0.25))
            time.sleep(sleep_for)