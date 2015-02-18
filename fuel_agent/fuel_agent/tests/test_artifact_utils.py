# Copyright 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import mock
from oslotest import base as test_base
import requests
import zlib

from oslo.config import cfg

from fuel_agent import errors
from fuel_agent.utils import artifact_utils as au


CONF = cfg.CONF


class TestTarget(test_base.BaseTestCase):
    def setUp(self):
        super(TestTarget, self).setUp()
        self.tgt = au.Target()

    def test_target_next(self):
        self.assertRaises(StopIteration, self.tgt.next)

    @mock.patch.object(au.Target, '__iter__')
    def test_target_target(self, mock_iter):
        mock_iter.return_value = iter(['chunk1', 'chunk2', 'chunk3'])
        m = mock.mock_open()
        with mock.patch('six.moves.builtins.open', m):
            self.tgt.target()

        mock_write_expected_calls = [mock.call('chunk1'), mock.call('chunk2'),
                                     mock.call('chunk3')]
        file_handle = m()
        self.assertEqual(mock_write_expected_calls,
                         file_handle.write.call_args_list)
        file_handle.flush.assert_called_once_with()


class TestLocalFile(test_base.BaseTestCase):
    def setUp(self):
        super(TestLocalFile, self).setUp()
        self.lf = au.LocalFile('/dev/null')

    def test_localfile_next(self):
        self.lf.fileobj = mock.Mock()
        self.lf.fileobj.read.side_effect = ['some_data', 'another_data']
        self.assertEqual('some_data', self.lf.next())
        self.assertEqual('another_data', self.lf.next())
        self.assertRaises(StopIteration, self.lf.next)


class TestHttpUrl(test_base.BaseTestCase):
    def test_httpurl___init__ok(self):
        def _fake_init_con(self):
            resp = mock.Mock(headers={'content-length': 123})
            self.response_obj = resp
        with mock.patch.object(au.HttpUrl, '_init_connection',
                               autospec=True) as mock_init_con:
            mock_init_con.side_effect = _fake_init_con
            httpurl = au.HttpUrl('fake_url')
            self.assertEqual(123, httpurl.length)

    def test_httpurl___init__invalid_content_length(self):
        def _fake_init_con(self):
            resp = mock.Mock(headers={'content-length': 'invalid'})
            self.response_obj = resp
        with mock.patch.object(au.HttpUrl, '_init_connection',
                               autospec=True) as mock_init_con:
            mock_init_con.side_effect = _fake_init_con
            self.assertRaises(errors.HttpUrlInvalidContentLength, au.HttpUrl,
                              'fake_url')

    @mock.patch.object(requests, 'get')
    def test_httpurl__init_connection_ok(self, mock_r_get):
        au.HttpUrl('fake_url')
        mock_r_get.assert_called_once_with(
            'fake_url', stream=True, timeout=CONF.http_request_timeout,
            headers={'Range': 'bytes=0-'})

    @mock.patch('time.sleep')
    @mock.patch.object(requests, 'get')
    def test_httpurl__init_connection_errors(self, mock_r_get, mock_s):
        mock_r = mock.Mock(status_code=200, headers={'content-length': 123})
        mock_r_get.side_effect = [requests.exceptions.ConnectionError(),
                                  requests.exceptions.Timeout(), mock_r]
        httpurl = au.HttpUrl('fake_url')
        self.assertEqual(123, httpurl.length)
        self.assertEqual(200, httpurl.response_obj.status_code)

    @mock.patch('time.sleep')
    @mock.patch.object(requests, 'get')
    def test_httpurl_connection_max_retries_exceeded(self, mock_r_get, mock_s):
        mock_r_get.side_effect = requests.exceptions.ConnectionError()
        self.assertRaises(errors.HttpUrlConnectionError, au.HttpUrl,
                          'fake_url')

    @mock.patch.object(requests, 'get')
    def test_httpurl_next_ok(self, mock_r_get):
        httpurl = au.HttpUrl('fake_url')
        content = ['fake content #1', 'fake content #2']
        httpurl.response_obj = mock.Mock()
        httpurl.response_obj.raw.read.side_effect = content
        for data in enumerate(httpurl):
            self.assertEqual(content[data[0]], data[1])


class TestGunzipStream(test_base.BaseTestCase):
    def test_gunzip_stream_next(self):
        content = ['fake content #1']
        compressed_stream = [zlib.compress(data) for data in content]
        gunzip_stream = au.GunzipStream(compressed_stream)
        for data in enumerate(gunzip_stream):
            self.assertEqual(content[data[0]], data[1])


class TestChain(test_base.BaseTestCase):
    def setUp(self):
        super(TestChain, self).setUp()
        self.chain = au.Chain()

    def test_append(self):
        self.assertEqual(0, len(self.chain.processors))
        self.chain.append('fake_processor')
        self.assertIn('fake_processor', self.chain.processors)
        self.assertEqual(1, len(self.chain.processors))

    def test_process(self):
        self.chain.processors.append('fake_uri')
        fake_processor = mock.Mock(spec=au.Target)
        self.chain.processors.append(fake_processor)
        self.chain.processors.append('fake_target')
        self.chain.process()
        expected_calls = [mock.call('fake_uri')]
        self.assertEqual(expected_calls, fake_processor.call_args_list)
