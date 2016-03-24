import mock
from nailgun.test.base import BaseUnitTest
import nailgun.app


def handler():
    raise Exception('Heeey, we got an unexpected exception here!')


class TestApp(BaseUnitTest):

    @mock.patch('nailgun.app.urls', return_value=('/test', handler))
    def test_exceptions_are_logged(self, _):
        app = nailgun.app.build_app()
        with mock.patch('nailgun.app.logger') as mock_logger:
            app.request(localpart='/test')
            self.assertTrue(mock_logger.exception.called)
