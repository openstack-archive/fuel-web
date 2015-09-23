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
import random
import sys

import fabric
import mock
import pytest

import shotgun


class RunOut(object):
    return_code = None
    stderr = None
    stdout = None

    def __str__(self):
        return str(self.stdout)


@pytest.fixture
def sub_fake_data():
    return {
        "type": "subs",
        "path": "/remote_dir/remote_file",
        "host": {
            "address": "remote_host",
        },
        "subs": {
            "line0": "LINE0",
            "line1": "LINE1"
        }
    }


@pytest.mark.parametrize("typ, driver", [
    ("file", "File"),
    ("dir", "Dir"),
    ("subs", "Subs"),
    ("postgres", "Postgres"),
    ("command", "Command"),
])
def test_driver_factory(typ, driver, fake_conf):
    data = {
        "type": typ,
    }
    with mock.patch("shotgun.driver.%s" % driver) as mocked:
        shotgun.driver.Driver.getDriver(data, fake_conf)
        mocked.assert_called_with(data, fake_conf)


@mock.patch('shotgun.driver.utils.CCStringIO')
@mock.patch('shotgun.driver.fabric.api.settings')
@mock.patch('shotgun.driver.fabric.api.run')
def test_driver_remote_command(mfabrun, mfabset, mccstring, fake_conf):
    out = shotgun.driver.CommandOut()
    out.stdout = "STDOUT"
    out.return_code = "RETURN_CODE"
    mccstring.return_value.getvalue.return_value = out.stdout

    runout = RunOut()
    runout.return_code = "RETURN_CODE"
    mfabrun.return_value = runout

    command = "COMMAND"

    driver = shotgun.driver.Driver(
        {"host": {"address": "remote_host"}}, fake_conf)
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
    assert result == out


@mock.patch('shotgun.driver.fabric.api.run')
@mock.patch('shotgun.driver.fabric.api.settings')
def test_fabric_use_timout_from_driver(mfabset, _, fake_conf):
    timeout = random.randint(1, 100)
    driver = shotgun.driver.Driver(
        {"host": {"address": "remote_host"}}, fake_conf)
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
def test_driver_local_command(mexecute, fake_conf):
    mexecute.return_value = ("RETURN_CODE", "STDOUT", "STDERR")

    out = shotgun.driver.CommandOut()
    out.stdout = "STDOUT"
    out.stderr = "STDERR"
    out.return_code = "RETURN_CODE"

    command = "COMMAND"
    driver = shotgun.driver.Driver({}, fake_conf)
    result = driver.command(command)
    shotgun.driver.utils.execute.assert_called_with(command)
    assert result == out


@mock.patch('shotgun.driver.utils.CCStringIO')
@mock.patch('shotgun.driver.fabric.api.settings')
@mock.patch('shotgun.driver.fabric.api.run')
def test_command_timeout(mfabrun, mfabset, mstringio, fake_conf):
    mfabrun.side_effect = fabric.exceptions.CommandTimeout(10)

    mstdout = mock.MagicMock()
    mstdout.getvalue.return_value = 'FULL STDOUT'
    mstringio.return_value = mstdout

    command = "COMMAND"

    driver = shotgun.driver.Driver(
        {"host": {"address": "remote_host"}}, fake_conf)
    result = driver.command(command)

    mstringio.assert_has_calls([
        mock.call(writers=sys.stdout),
    ])
    mfabrun.assert_called_with(command, stdout=mstdout)
    assert result.stdout == 'FULL STDOUT'


@mock.patch('shotgun.driver.utils.execute')
@mock.patch('shotgun.driver.fabric.api.settings')
@mock.patch('shotgun.driver.fabric.api.get')
def test_driver_get(mfabget, mfabset, mexecute, fake_conf):
    mexecute.return_value = ("RETURN_CODE", "STDOUT", "STDERR")
    remote_path = "/remote_dir/remote_file"
    target_path = "/target_dir"

    driver = shotgun.driver.Driver({
        "host": {
            "address": "remote_host",
            "ssh-key": "path_to_key",
        }
    }, fake_conf)
    driver.get(remote_path, target_path)
    mexecute.assert_called_with('mkdir -p "{0}"'.format(target_path))
    mfabget.assert_called_with(remote_path, target_path)
    mfabset.assert_called_with(
        host_string="remote_host", key_filename="path_to_key",
        timeout=2, warn_only=True, abort_on_prompts=True)

    mexecute.reset_mock()
    driver = shotgun.driver.Driver({}, fake_conf)
    driver.get(remote_path, target_path)
    assert (mexecute.mock_calls == [
            mock.call('mkdir -p "{0}"'.format(target_path)),
            mock.call('cp -r "{0}" "{1}"'.format(remote_path, target_path))])


def test_use_timeout_from_global_conf(fake_conf):
    data = {}
    cmd_driver = shotgun.driver.Driver(data, fake_conf)
    assert cmd_driver.timeout == fake_conf.timeout


def test_use_command_specific_timeout(fake_conf):
    timeout = 1234
    data = {
        "timeout": timeout
    }
    cmd_driver = shotgun.driver.Driver(data, fake_conf)
    assert cmd_driver.timeout == timeout
    assert cmd_driver.timeout != fake_conf.timeout


@mock.patch('shotgun.driver.Driver.get')
def test_driver_snapshot(mget, fake_conf):
    data = {
        "type": "file",
        "path": "/remote_dir/remote_file",
        "host": {
            "address": "remote_host",
        },
    }
    file_driver = shotgun.driver.File(data, fake_conf)

    target_path = "/target/remote_host/remote_dir"
    file_driver.snapshot()

    mget.assert_called_with(data["path"], target_path)


@mock.patch('shotgun.driver.utils.remove')
@mock.patch('shotgun.driver.Driver.get')
def test_dir_exclude_called(mget, mremove, fake_conf):
    data = {
        "type": "dir",
        "path": "/remote_dir/",
        "exclude": ["*test"],
        "host": {
            "address": "remote_host",
        },
    }
    dir_driver = shotgun.driver.Dir(data, fake_conf)

    target_path = "/target/remote_host/remote_dir"
    dir_driver.snapshot()

    mget.assert_called_with(data["path"], target_path)
    mremove.assert_called_with(dir_driver.full_dst_path, data['exclude'])


@mock.patch('shotgun.driver.tempfile.NamedTemporaryFile')
@mock.patch('shotgun.driver.Driver.get')
@mock.patch('shotgun.driver.utils.execute')
def test_sed(mexecute, mget, mntemp, fake_conf, sub_fake_data):
    sedscript = mock.Mock()
    sedscript.name = "SEDSCRIPT"

    mexecute.return_value = ("RETURN_CODE", "STDOUT", "STDERR")
    mntemp.return_value = sedscript

    subs_driver = shotgun.driver.Subs(sub_fake_data, fake_conf)
    subs_driver.sed("from_file", "to_file")

    assert (sedscript.write.mock_calls == [
        mock.call("s/{0}/{1}/g\n".format(old, new))
        for old, new in sub_fake_data["subs"].iteritems()])
    shotgun.driver.utils.execute.assert_called_with(
        "cat from_file | sed -f SEDSCRIPT", to_filename="to_file")

    subs_driver.sed("from_file.gz", "to_file.gz")
    shotgun.driver.utils.execute.assert_called_with(
        "cat from_file.gz | gunzip -c | sed -f SEDSCRIPT | gzip -c",
        to_filename="to_file.gz")

    subs_driver.sed("from_file.bz2", "to_file.bz2")
    shotgun.driver.utils.execute.assert_called_with(
        "cat from_file.bz2 | bunzip2 -c | sed -f SEDSCRIPT | bzip2 -c",
        to_filename="to_file.bz2")


@mock.patch('shotgun.driver.os.walk')
@mock.patch('shotgun.driver.Subs.sed')
@mock.patch('shotgun.driver.Driver.get')
@mock.patch('shotgun.driver.utils.execute')
def test_subs_snapshot(mexecute, mdriverget, msed, mwalk, fake_conf,
                       sub_fake_data):
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

    subs_driver = shotgun.driver.Subs(sub_fake_data, fake_conf)
    subs_driver.snapshot()

    sed_calls = []
    execute_calls = []
    for root, _, files in mock_walk:
        for filename in files:
            fullfilename = os.path.join(root, filename)
            # /target/remote_host
            tgt_host = os.path.join(
                fake_conf.target, sub_fake_data["host"]["address"])
            rel_tgt_host = os.path.relpath(fullfilename, tgt_host)
            # /remote_dir/remote_file
            match_orig_path = os.path.join("/", rel_tgt_host)
            if not fnmatch.fnmatch(match_orig_path, sub_fake_data["path"]):
                continue
            tempfilename = "STDOUT"
            execute_calls.append(mock.call("mktemp"))
            sed_calls.append(mock.call(fullfilename, tempfilename))
            execute_calls.append(
                mock.call('mv -f "{0}" "{1}"'.format(
                    tempfilename, fullfilename)))

    assert msed.mock_calls == sed_calls
    assert mexecute.mock_calls == execute_calls
