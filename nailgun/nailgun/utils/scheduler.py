import threading


class PeriodicalTimer(threading.Thread):

    def __init__(self, interval, fn):
        super(PeriodicalTimer, self).__init__()
        self.interval = interval
        self.fn = fn
        self.stop_event = threading.Event()

    def run(self):
        while not self.stop_event.wait(self.interval):
            self.fn()

    def __enter__(self):
        self.start()

    def __exit__(self, *_):
        self.stop_event.set()


def call_every(interval, fn):
    return PeriodicalTimer(interval, fn)
