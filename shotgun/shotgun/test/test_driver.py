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
try:
    from unittest.case import TestCase
except ImportError:
    # Runing unit-tests in production environment
    from unittest2.case import TestCase
from mock import MagicMock
from mock import Mock

import shotgun.driver


class RunOut(object):
    return_code = None
    stderr = None
    stdout = None

    def __str__(self):
        return str(self.stdout)


class TestDriver(TestCase):
    def constructorMock(self, name):
        instance = Mock()
        instance._name_of_parent_class = name
        constructor = Mock(return_value=instance)
        return constructor

    def test_driver_factory(self):
        types = {
            "file": "File",
            "dir": "Dir",
            "subs": "Subs",
            "postgres": "Postgres",
            "command": "Command"
        }
        for t, n in types.iteritems():
            setattr(shotgun.driver, n, self.constructorMock(n))
            self.assertEquals(shotgun.driver.Driver.getDriver(
                {"type": t}, None)._name_of_parent_class, n)

    def test_driver_command(self):
        out = shotgun.driver.CommandOut()
        out.stdout = "STDOUT"
        out.return_code = "RETURN_CODE"
        out.stderr = "STDERR"

        runout = RunOut()
        runout.stdout = "STDOUT"
        runout.return_code = "RETURN_CODE"
        runout.stderr = "STDERR"

        shotgun.driver.fabric.api.run = MagicMock(return_value=runout)
        shotgun.driver.fabric.api.settings = MagicMock()
        shotgun.driver.execute = MagicMock(
            return_value=("RETURN_CODE", "STDOUT", "STDERR"))
        command = "COMMAND"

        driver = shotgun.driver.Driver({"host": "remote"}, None)
        result = driver.command(command)
        shotgun.driver.fabric.api.run.assert_called_with(command, pty=True)
        self.assertEquals(result, out)
        shotgun.driver.fabric.api.settings.assert_called_with(
            host_string="remote", timeout=2, warn_only=True)

        driver = shotgun.driver.Driver({}, None)
        result = driver.command(command)
        shotgun.driver.execute.assert_called_with(command)
        self.assertEquals(result, out)

    def test_driver_get(self):
        shotgun.driver.fabric.api.get = MagicMock()
        shotgun.driver.fabric.api.settings = MagicMock()
        shotgun.driver.execute = MagicMock(
            return_value=("RETURN_CODE", "STDOUT", "STDERR"))
        path = "PATH"
        target_path = "/tmp/TARGET_PATH"

        driver = shotgun.driver.Driver({"host": "remote"}, None)
        driver.get(path, target_path)
        shotgun.driver.fabric.api.get.assert_called_with(path, target_path)
        shotgun.driver.fabric.api.settings.assert_called_with(
            host_string="remote", timeout=2, warn_only=True)

        driver = shotgun.driver.Driver({}, None)
        driver.get(path, target_path)
        shotgun.driver.execute.assert_any_call(
            "mkdir -p %s" % os.path.dirname(target_path))
        shotgun.driver.execute.assert_any_call(
            "cp -r %s %s" % (path, target_path))
