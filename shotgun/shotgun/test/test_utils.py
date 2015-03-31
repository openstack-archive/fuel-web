#    Copyright 2015 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import StringIO

from mock import call
from mock import patch

from shotgun.test import base
from shotgun import utils


class TestUtils(base.BaseTestCase):

    @patch('shotgun.utils.iterfiles')
    @patch('shotgun.utils.os.unlink')
    def test_remove_matched_files(self, munlink, mfiles):
        mfiles.return_value = ['/file1.good', '/file2.bad']
        utils.remove_matched_files('/', ['*.good'])

        munlink.assert_called_once_with('/file1.good')

    @patch('shotgun.utils.iterfiles')
    @patch('shotgun.utils.os.unlink')
    def test_remove_several_files(self, munlink, mfiles):
        mfiles.return_value = ['/file1.good', '/file2.good']
        utils.remove_matched_files('/', ['*.good'])

        munlink.assert_has_calls(
            [call('/file1.good'), call('/file2.good')])

    @patch('shotgun.utils.os.walk')
    def test_iterfiles(self, mwalk):
        path = '/root'
        mwalk.return_value = [
            (path, '', ('file1', 'file2')),
            (path + '/sub', '', ('file3',))]

        result = list(utils.iterfiles(path))

        mwalk.assert_called_once_with(path, topdown=True)
        self.assertEqual(
            result, ['/root/file1', '/root/file2', '/root/sub/file3'])

    @patch('shotgun.utils.execute')
    def test_compress(self, mexecute):
        target = '/path/target'
        level = '-3'

        utils.compress(target, level)

        compress_call = mexecute.call_args_list[0]
        rm_call = mexecute.call_args_list[1]

        compress_env = compress_call[1]['env']
        self.assertEqual(compress_env['XZ_OPT'], level)
        self.assertEqual(
            compress_call[0][0],
            'tar cJvf /path/target.tar.xz -C /path target')

        self.assertEqual(rm_call[0][0], 'rm -r /path/target')


class TestCCStringIO(base.BaseTestCase):

    def test_no_writers(self):
        test_string = 'some_string'

        ccstring = utils.CCStringIO()
        ccstring.write(test_string)

        self.assertEqual(ccstring.getvalue(), test_string)

    def test_with_one_writer(self):
        test_string = 'some_string'

        writer = StringIO.StringIO()
        ccstring = utils.CCStringIO(writers=writer)
        ccstring.write(test_string)

        self.assertEqual(ccstring.getvalue(), test_string)
        self.assertEqual(writer.getvalue(), test_string)

    def test_with_multiple_writers(self):
        test_string = 'some_string'

        writer_a = StringIO.StringIO()
        writer_b = StringIO.StringIO()
        ccstring = utils.CCStringIO(writers=[writer_a, writer_b])
        ccstring.write(test_string)

        self.assertEqual(ccstring.getvalue(), test_string)
        self.assertEqual(writer_a.getvalue(), test_string)
        self.assertEqual(writer_b.getvalue(), test_string)

    def test_with_writer_and_buffer(self):
        buffer = 'I am here already'

        writer = StringIO.StringIO()
        ccstring = utils.CCStringIO(buffer, writers=writer)

        self.assertEqual(ccstring.getvalue(), buffer)
        self.assertEqual(writer.getvalue(), '')
