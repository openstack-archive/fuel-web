# coding: utf-8

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

import mock

from shotgun import utils


@mock.patch('shotgun.utils.execute')
def test_remove_subdir(mexecute):
    utils.remove('/', ['good', '**/*.py'])
    mexecute.assert_has_calls([
        mock.call('shopt -s globstar; rm -rf /good', shell=True),
        mock.call('shopt -s globstar; rm -rf /**/*.py', shell=True)])


@mock.patch('shotgun.utils.os.walk')
def test_iterfiles(mwalk):
    path = '/root'
    mwalk.return_value = [
        (path, '', ('file1', 'file2')),
        (path + '/sub', '', ('file3',))]

    result = list(utils.iterfiles(path))

    mwalk.assert_called_once_with(path, topdown=True)
    assert result == ['/root/file1', '/root/file2', '/root/sub/file3']


@mock.patch('shotgun.utils.execute')
def test_compress(mexecute):
    target = '/path/target'
    level = '-3'

    utils.compress(target, level)

    compress_call = mexecute.call_args_list[0]
    rm_call = mexecute.call_args_list[1]

    compress_env = compress_call[1]['env']
    assert compress_env['XZ_OPT'] == level
    assert (compress_call[0][0] ==
            'tar cJvf /path/target.tar.xz -C /path target')
    assert rm_call[0][0] == 'rm -r /path/target'


def test_ccstring_no_writers():
    test_string = 'some_string'

    ccstring = utils.CCStringIO()
    ccstring.write(test_string)

    assert ccstring.getvalue() == test_string


def test_ccstring_with_one_writer():
    test_string = 'some_string'

    writer = StringIO.StringIO()
    ccstring = utils.CCStringIO(writers=writer)
    ccstring.write(test_string)

    assert ccstring.getvalue() == test_string
    assert writer.getvalue() == test_string


def test_ccstring_with_multiple_writers():
    test_string = 'some_string'

    writer_a = StringIO.StringIO()
    writer_b = StringIO.StringIO()
    ccstring = utils.CCStringIO(writers=[writer_a, writer_b])
    ccstring.write(test_string)

    assert ccstring.getvalue() == test_string
    assert writer_a.getvalue() == test_string
    assert writer_b.getvalue() == test_string


def test_ccstring_with_writer_and_buffer():
    buffer = 'I am here already'

    writer = StringIO.StringIO()
    ccstring = utils.CCStringIO(buffer, writers=writer)

    assert ccstring.getvalue() == buffer
    assert writer.getvalue() == ''


def test_ccstring_non_ascii_output_with_unicode():
    ccstring = utils.CCStringIO()
    ccstring.write('привет')
    ccstring.write(u'test')

    assert ccstring.getvalue() == 'приветtest'
