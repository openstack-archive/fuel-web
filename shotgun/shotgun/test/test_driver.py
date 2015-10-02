#    Copyright 2013 Mirantis, Inc.
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

import os
import random
import sys

import fabric
import mock

import shotgun
from shotgun.test import base


class RunOut(object):
    return_code = None
    stderr = None
    stdout = None

    def __str__(self):
        return str(self.stdout)


class TestDriver(base.BaseTestCase):
    def test_driver_factory(self):
        types = {
            "file": "File",
            "dir": "Dir",
            "postgres": "Postgres",
            "command": "Command"
        }
        for t, n in types.iteritems():
            with mock.patch("shotgun.driver.%s" % n) as mocked:
                shotgun.driver.Driver.getDriver({"type": t}, None)
                mocked.assert_called_with({"type": t}, None)

    @mock.patch('shotgun.driver.utils.CCStringIO')
    @mock.patch('shotgun.driver.fabric.api.settings')
    @mock.patch('shotgun.driver.fabric.api.run')
    def test_driver_remote_command(self, mfabrun, mfabset, mccstring):
        out = shotgun.driver.CommandOut()
        out.stdout = "STDOUT"
        out.return_code = "RETURN_CODE"
        mccstring.return_value.getvalue.return_value = out.stdout

        runout = RunOut()
        runout.return_code = "RETURN_CODE"
        mfabrun.return_value = runout

        command = "COMMAND"

        conf = mock.Mock()
        driver = shotgun.driver.Driver(
            {"host": {"address": "remote_host"}}, conf)
        result = driver.command(command)

        mfabrun.assert_called_with(
            command, stdout=mock.ANY)
        mfabset.assert_called_with(
            host_string="remote_host",
            timeout=2,
            command_timeout=driver.timeout,
            warn_only=True,
            key_filename=None,
            abort_on_prompts=True)
        self.assertEqual(result, out)

    @mock.patch('shotgun.driver.fabric.api.run')
    @mock.patch('shotgun.driver.fabric.api.settings')
    def test_fabric_use_timout_from_driver(self, mfabset, _):
        timeout = random.randint(1, 100)
        conf = mock.Mock()
        driver = shotgun.driver.Driver(
            {"host": {"address": "remote_host"}}, conf)
        driver.timeout = timeout
        driver.command("COMMAND")
        mfabset.assert_called_with(
            host_string=mock.ANY,
            timeout=mock.ANY,
            command_timeout=timeout,
            warn_only=mock.ANY,
            key_filename=mock.ANY,
            abort_on_prompts=mock.ANY)

    @mock.patch('shotgun.driver.utils.execute')
    def test_driver_local_command(self, mexecute):
        mexecute.return_value = ("RETURN_CODE", "STDOUT", "STDERR")

        out = shotgun.driver.CommandOut()
        out.stdout = "STDOUT"
        out.stderr = "STDERR"
        out.return_code = "RETURN_CODE"

        command = "COMMAND"
        conf = mock.Mock()
        driver = shotgun.driver.Driver({}, conf)
        result = driver.command(command)
        shotgun.driver.utils.execute.assert_called_with(command)
        self.assertEqual(result, out)

    @mock.patch('shotgun.driver.utils.CCStringIO')
    @mock.patch('shotgun.driver.fabric.api.settings')
    @mock.patch('shotgun.driver.fabric.api.run')
    def test_command_timeout(self, mfabrun, mfabset, mstringio):
        mfabrun.side_effect = fabric.exceptions.CommandTimeout(10)

        mstdout = mock.MagicMock()
        mstdout.getvalue.return_value = 'FULL STDOUT'
        mstringio.return_value = mstdout

        command = "COMMAND"

        conf = mock.Mock()
        driver = shotgun.driver.Driver(
            {"host": {"address": "remote_host"}}, conf)
        result = driver.command(command)

        mstringio.assert_has_calls([
            mock.call(writers=sys.stdout),
        ])
        mfabrun.assert_called_with(command, stdout=mstdout)
        self.assertEqual(result.stdout, 'FULL STDOUT')

    @mock.patch('shotgun.driver.utils.execute')
    @mock.patch('shotgun.driver.fabric.api.settings')
    @mock.patch('shotgun.driver.fabric.api.get')
    def test_driver_get(self, mfabget, mfabset, mexecute):
        mexecute.return_value = ("RETURN_CODE", "STDOUT", "STDERR")
        remote_path = "/remote_dir/remote_file"
        target_path = "/target_dir"
        conf = mock.Mock()

        driver = shotgun.driver.Driver({
            "host": {
                "address": "remote_host",
                "ssh-key": "path_to_key",
            }
        }, conf)
        driver.get(remote_path, target_path)
        mexecute.assert_called_with('mkdir -p "{0}"'.format(target_path))
        mfabget.assert_called_with(remote_path, target_path)
        mfabset.assert_called_with(
            host_string="remote_host", key_filename="path_to_key",
            timeout=2, warn_only=True, abort_on_prompts=True)

    @mock.patch('shotgun.driver.os', autospec=True)
    @mock.patch('shotgun.driver.glob.glob')
    @mock.patch('shotgun.driver.utils.execute')
    def test_driver_get_local_dir(self, mexecute, mglob, mos):
        mock_walk = [
            (
                '/var/log',
                ['3'],  # dir
                ['1', '2', 'remote_file']
            ),
            ('/var/log/3',
             ['6'],  # dir
             ['5', '4']),
            ('/var/log/3/6', [], [])
        ]
        mos.walk.return_value = mock_walk
        mos.path.isdir.return_value = True
        mglob.return_value = ['/var/log']
        driver = shotgun.driver.Driver({}, mock.Mock())
        driver.local = True

        remote_path = "/var/log"
        target_path = "/var/www/dump/log"

        mos.path.join.side_effect = os.path.join
        mos.path.dirname.side_effect = os.path.dirname

        driver.get(remote_path, target_path)
        expected_calls = [
            mock.call('mkdir -p "/var/www/dump/log"'),
            mock.call('mkdir -p "/var/www/dump/var/log/3"'),
            mock.call('ln -fs "/var/log/1" "/var/www/dump/var/log/1"'),
            mock.call('ln -fs "/var/log/2" "/var/www/dump/var/log/2"'),
            mock.call('ln -fs "/var/log/remote_file" '
                      '"/var/www/dump/var/log/remote_file"'),
            mock.call('mkdir -p "/var/www/dump/var/log/3/6"'),
            mock.call('ln -fs "/var/log/3/5" "/var/www/dump/var/log/3/5"'),
            mock.call('ln -fs "/var/log/3/4" "/var/www/dump/var/log/3/4"')]
        self.assertEqual(expected_calls, mexecute.call_args_list)

    @mock.patch('shotgun.driver.os', autospec=True)
    @mock.patch('shotgun.driver.glob.glob')
    @mock.patch('shotgun.driver.utils.execute')
    def test_driver_get_local_file(self, mexecute, mglob, mos):
        mos.path.isdir.return_value = False
        mglob.return_value = ['/var/log/atop/atop_current']
        driver = shotgun.driver.Driver({}, mock.Mock())
        driver.local = True
        remote_path = "/var/log/atop/atop_current"
        target_path = "/var/www/dump/var/log/atop"

        mos.path.join.side_effect = os.path.join
        mos.path.basename = os.path.basename

        driver.get(remote_path, target_path)
        expected_calls = [
            mock.call('mkdir -p "/var/www/dump/var/log/atop"'),
            mock.call('ln -fs "/var/log/atop/atop_current" '
                      '"/var/www/dump/var/log/atop/atop_current"')]
        self.assertEqual(expected_calls, mexecute.call_args_list)

    def test_use_timeout_from_global_conf(self):
        data = {}
        conf = mock.Mock(spec=shotgun.config.Config, target="some_target")
        cmd_driver = shotgun.driver.Driver(data, conf)
        self.assertEqual(cmd_driver.timeout, conf.timeout)

    def test_use_command_specific_timeout(self):
        timeout = 1234
        data = {
            "timeout": timeout
        }
        conf = mock.Mock(spec=shotgun.config.Config, target="some_target")
        cmd_driver = shotgun.driver.Driver(data, conf)
        self.assertEqual(cmd_driver.timeout, timeout)
        self.assertNotEqual(cmd_driver.timeout, conf.timeout)


class TestFile(base.BaseTestCase):

    @mock.patch('shotgun.driver.Driver.get')
    def test_snapshot(self, mget):
        data = {
            "type": "file",
            "path": "/remote_dir/remote_file",
            "host": {
                "address": "remote_host",
            },
        }
        conf = mock.MagicMock()
        conf.target = "/target"
        file_driver = shotgun.driver.File(data, conf)

        target_path = "/target/remote_host/remote_dir"
        file_driver.snapshot()

        mget.assert_called_with(data["path"], target_path)

    @mock.patch('shotgun.driver.utils.remove')
    @mock.patch('shotgun.driver.Driver.get')
    def test_dir_exclude_called(self, mget, mremove):
        data = {
            "type": "dir",
            "path": "/remote_dir/",
            "exclude": ["*test"],
            "host": {
                "address": "remote_host",
            },
        }
        conf = mock.MagicMock()
        conf.target = "/target"
        dir_driver = shotgun.driver.Dir(data, conf)

        target_path = "/target/remote_host/remote_dir"
        dir_driver.snapshot()

        mget.assert_called_with(data["path"], target_path)
        mremove.assert_called_with(dir_driver.full_dst_path, data['exclude'])
