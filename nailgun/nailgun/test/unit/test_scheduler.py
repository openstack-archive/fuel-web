import unittest
import mock
from nailgun.utils import scheduler
from time import sleep

class TestScheduler(unittest.TestCase):

    def test_calls(self):
        callback = mock.Mock()
        with scheduler.call_every(0.1, callback):
            sleep(0.35)
        self.assertEqual(callback.call_count, 3)
