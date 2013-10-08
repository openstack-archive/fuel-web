import time

class TimeoutError(Exception):
    pass

def wait_for_true(check, args=[], kwargs={},
                  timeout=60, error_message='Timeout error'):
    start_time = time.time()
    while True:
        result = check(*args, **kwargs)
        if result:
            return result
        if time.time() - start_time > timeout:
            raise TimeoutError(error_message)
        time.sleep(0.1)

