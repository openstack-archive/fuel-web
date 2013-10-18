import thread
from threading import Timer


class TimeoutError(Exception):
    pass


def handler(signum, frame):
    raise TimeoutError('Timeout error')


def run_with_timeout(check, args=None, kwargs=None, timeout=60, default=False):
    args = args if args else []
    kwargs = kwargs if kwargs else dict()
    if not timeout:
        return check(*args, **kwargs)
    try:
        timeout_timer = Timer(timeout, thread.interrupt_main)
        timeout_timer.start()
        result = check(*args, **kwargs)
        return result
    except KeyboardInterrupt:
        return default
    finally:
        timeout_timer.cancel()
