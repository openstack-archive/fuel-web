import signal
import time
import thread
from threading import Timer


class TimeoutError(Exception):
    pass


def handler(signum, frame):
    raise TimeoutError('Timeout error')


def wait_for_true(check, args=[], kwargs={},
                  timeout=60, error_message='Timeout error'):
    start_time = time.time()
    sig = signal.signal(signal.SIGALRM, handler)
    signal.alarm(timeout)
    while True:
        result = check(*args, **kwargs)
        if result:
            signal.alarm(0)  # disable alarm
            return result
        if time.time() - start_time > timeout:
            raise TimeoutError(error_message)
        time.sleep(0.1)


def run_with_timeout(check, args=[], kwargs={}, timeout=60, default=False):
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
