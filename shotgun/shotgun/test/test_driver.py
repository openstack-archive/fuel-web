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

import fnmatch
import os
try:
    from unittest.case import TestCase
except ImportError:
    # Runing unit-tests in production environment
    from unittest2.case import TestCase
from mock import call
from mock import MagicMock
from mock import patch

import shotgun.config
import shotgun.driver
import shotgun.settings


class RunOut(object):
    return_code = None
    stderr = None
    stdout = None

    def __str__(self):
        return str(self.stdout)


class TestDriver(TestCase):
    def test_driver_factory(self):
        types = {
            "file": "File",
            "dir": "Dir",
            "subs": "Subs",
            "postgres": "Postgres",
            "command": "Command"
        }
        for t, n in types.iteritems():
            with patch("shotgun.driver.%s" % n) as mocked:
                shotgun.driver.Driver.getDriver({"type": t}, None)
                mocked.assert_called_with({"type": t}, None)

    @patch('shotgun.driver.execute')
    @patch('shotgun.driver.fabric.api.settings')
    @patch('shotgun.driver.fabric.api.run')
    def test_driver_command(self, mfabrun, mfabset, mexecute):
        out = shotgun.driver.CommandOut()
        out.stdout = "STDOUT"
        out.return_code = "RETURN_CODE"
        out.stderr = "STDERR"

        runout = RunOut()
        runout.stdout = "STDOUT"
        runout.return_code = "RETURN_CODE"
        runout.stderr = "STDERR"

        mfabrun.return_value = runout
        mexecute.return_value = ("RETURN_CODE", "STDOUT", "STDERR")
        command = "COMMAND"

        driver = shotgun.driver.Driver({"host": "remote_host"}, None)
        result = driver.command(command)
        shotgun.driver.fabric.api.run.assert_called_with(command, pty=True)
        self.assertEquals(result, out)
        shotgun.driver.fabric.api.settings.assert_called_with(
            host_string="remote_host", timeout=2, command_timeout=10,
            warn_only=True)

        driver = shotgun.driver.Driver({}, None)
        result = driver.command(command)
        shotgun.driver.execute.assert_called_with(command)
        self.assertEquals(result, out)

    @patch('shotgun.driver.execute')
    @patch('shotgun.driver.fabric.api.settings')
    @patch('shotgun.driver.fabric.api.get')
    def test_driver_get(self, mfabget, mfabset, mexecute):
        mexecute.return_value = ("RETURN_CODE", "STDOUT", "STDERR")
        remote_path = "/remote_dir/remote_file"
        target_path = "/target_dir"

        driver = shotgun.driver.Driver({"host": "remote_host"}, None)
        driver.get(remote_path, target_path)
        mexecute.assert_called_with("mkdir -p %s" % target_path)
        mfabget.assert_called_with(remote_path, target_path)
        mfabset.assert_called_with(
            host_string="remote_host", timeout=2, warn_only=True)

        mexecute.reset_mock()
        driver = shotgun.driver.Driver({}, None)
        driver.get(remote_path, target_path)
        assert mexecute.mock_calls == [
            call("mkdir -p %s" % target_path),
            call("cp -r %s %s" % (remote_path, target_path))
        ]


class TestFile(TestCase):

    @patch('shotgun.driver.Driver.get')
    def test_snapshot(self, mget):
        data = {
            "type": "file",
            "path": "/remote_dir/remote_file",
            "host": "remote_host"
        }
        conf = MagicMock()
        conf.target = "/target"
        file_driver = shotgun.driver.File(data, conf)

        target_path = "/target/remote_host/remote_dir"
        file_driver.snapshot()

        mget.assert_called_with(data["path"], target_path)


class TestSubs(TestCase):
    def setUp(self):
        self.data = {
            "type": "subs",
            "path": "/remote_dir/remote_file",
            "host": "remote_host",
            "subs": {
                "line0": "LINE0",
                "line1": "LINE1"
            }
        }

        self.conf = MagicMock()
        self.conf.target = "/target"

        self.sedscript = MagicMock()
        self.sedscript.name = "SEDSCRIPT"
        self.sedscript.write = MagicMock()

    @patch('shotgun.driver.tempfile.NamedTemporaryFile')
    @patch('shotgun.driver.Driver.get')
    @patch('shotgun.driver.execute')
    def test_sed(self, mexecute, mget, mntemp):
        mexecute.return_value = ("RETURN_CODE", "STDOUT", "STDERR")
        mntemp.return_value = self.sedscript

        subs_driver = shotgun.driver.Subs(self.data, self.conf)
        subs_driver.sed("from_file", "to_file")
        assert self.sedscript.write.mock_calls == [
            call("s/%s/%s/g\n" % (old, new))
            for old, new in self.data["subs"].iteritems()]
        shotgun.driver.execute.assert_called_with(
            "cat from_file | sed -f SEDSCRIPT", to_filename="to_file")

        subs_driver.sed("from_file.gz", "to_file.gz")
        shotgun.driver.execute.assert_called_with(
            "cat from_file.gz | gunzip -c | sed -f SEDSCRIPT | gzip -c",
            to_filename="to_file.gz")

        subs_driver.sed("from_file.bz2", "to_file.bz2")
        shotgun.driver.execute.assert_called_with(
            "cat from_file.bz2 | bunzip2 -c | sed -f SEDSCRIPT | bzip2 -c",
            to_filename="to_file.bz2")

    @patch('shotgun.driver.os.walk')
    @patch('shotgun.driver.Subs.sed')
    @patch('shotgun.driver.Driver.get')
    @patch('shotgun.driver.execute')
    def test_snapshot(self, mexecute, mdriverget, msed, mwalk):
        mexecute.return_value = ("RETURN_CODE", "STDOUT", "STDERR")

        """ 1. Should get remote (or local) file (or directory)
        2. Should put it into /target/host.domain.tld
        3. Should walk through and check if files match given path pattern
        4. If matched, sed them
        """

        """this return_value corresponds to the following structure
        /target/remote_host/remote_dir/
            /target/remote_host/remote_dir/remote_file
            /target/remote_host/remote_dir/1
            /target/remote_host/remote_dir/2
            /target/remote_host/remote_dir/3/
                /target/remote_host/remote_dir/3/4
                /target/remote_host/remote_dir/3/5
                /target/remote_host/remote_dir/3/6/
        """
        mock_walk = [
            (
                '/target/remote_host/remote_dir',
                ['3'],
                ['1', '2', 'remote_file']
            ),
            ('/target/remote_host/remote_dir/3', ['6'], ['5', '4']),
            ('/target/remote_host/remote_dir/3/6', [], [])
        ]
        mwalk.return_value = mock_walk

        subs_driver = shotgun.driver.Subs(self.data, self.conf)
        subs_driver.snapshot()

        sed_calls = []
        execute_calls = []
        for root, _, files in mock_walk:
            for filename in files:
                fullfilename = os.path.join(root, filename)
                # /target/remote_host
                tgt_host = os.path.join(self.conf.target, self.data["host"])
                rel_tgt_host = os.path.relpath(fullfilename, tgt_host)
                # /remote_dir/remote_file
                match_orig_path = os.path.join("/", rel_tgt_host)
                if not fnmatch.fnmatch(match_orig_path, self.data["path"]):
                    continue
                tempfilename = "STDOUT"
                execute_calls.append(call("mktemp"))
                sed_calls.append(call(fullfilename, tempfilename))
                execute_calls.append(
                    call("mv -f %s %s" % (tempfilename, fullfilename)))

        assert msed.mock_calls == sed_calls
        assert mexecute.mock_calls == execute_calls
