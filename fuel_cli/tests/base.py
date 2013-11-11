# -*- coding: utf-8 -*-

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

try:
    from unittest.case import TestCase
except ImportError:
    # Runing unit-tests in production environment
    from unittest2.case import TestCase

from itertools import izip
import subprocess
import os
from time import sleep


class NailgunServer:
    def __init__(self):
        self.root_path = self.find_repo_root()
        self.clean_cmd = os.path.join(
            self.root_path,
            "run_tests.sh"
        ) + " -c"
        self.manage_path = os.path.join(
            self.root_path,
            "nailgun/manage.py"
        )
        self.fuel_path = os.path.join(
            self.root_path,
            "fuel_cli/fuel"
        )
        self.run_flags = "run -p 8000 --fake-tasks"
        self.server_handle = None

        self.runCommand(self.clean_cmd)
        preparation_actions = [
            "dropdb",
            "syncdb",
            "loaddefault",
            "loaddata {0}".format(
                os.path.join(
                    self.root_path,
                    "nailgun/nailgun/fixtures/sample_environment.json"
                )
            )
        ]
        for action in preparation_actions:
            self.runCommand(self.manage_path, action, wait=True)
        self.runCommand(self.clean_cmd)

    def runCommand(self, *args, **kwargs):
        handle = subprocess.Popen(
            " ".join(args),
            shell=True
        )
        if kwargs.get("wait", False):
            handle.wait()
            return None
        else:
            return handle

    def startServer(self):
        self.server_handle = self.runCommand(
            self.manage_path,
            self.run_flags
        )
        sleep(2)

    def __del__(self):
        self.server_handle.kill()

    def find_repo_root(self):
        current_path = os.path.abspath(os.curdir)
        current_folder_name = os.path.basename(current_path)
        one_dir_up_path = os.path.abspath(
            os.path.join(
                current_path,
                os.path.pardir
            )
        )
        if current_folder_name == 'fuel_cli':
            return one_dir_up_path
        else:
            os.chdir(one_dir_up_path)
            return self.find_repo_root()

    def run_cli_command(self, command_line=None):
        proc = subprocess.Popen(
            [self.fuel_path] + command_line.split(" "),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        proc.wait()
        return {
            "retcode": proc.returncode,
            "stdout": proc.stdout.read(),
            "stderr": proc.stderr.read()
        }


class BaseTestCase(TestCase):
    def __init__(self, *args, **kwargs):
        super(BaseTestCase, self).__init__(*args, **kwargs)

    @classmethod
    def setUpClass(cls):
        cls.ns = NailgunServer()
        cls.ns.startServer()

    @classmethod
    def tearDownClass(cls):
        del cls.ns

    def assertNotRaises(self, exception, method, *args, **kwargs):
        try:
            method(*args, **kwargs)
        except exception:
            self.fail('Exception "{0}" raised.'.format(exception))

    def datadiff(self, node1, node2, path=None):
        if path is None:
            path = []

        print("Path: {0}".format("->".join(path)))

        if not isinstance(node1, dict) or not isinstance(node2, dict):
            if isinstance(node1, list):
                newpath = path[:]
                for i, keys in enumerate(izip(node1, node2)):
                    newpath.append(str(i))
                    self.datadiff(keys[0], keys[1], newpath)
                    newpath.pop()
            elif node1 != node2:
                err = "Values differ: {0} != {1}".format(
                    str(node1),
                    str(node2)
                )
                raise Exception(err)
        else:
            newpath = path[:]
            for key1, key2 in zip(
                sorted(node1.keys()),
                sorted(node2.keys())
            ):
                if key1 != key2:
                    err = "Keys differ: {0} != {1}".format(
                        str(key1),
                        str(key2)
                    )
                    raise Exception(err)
                newpath.append(key1)
                self.datadiff(node1[key1], node2[key2], newpath)
                newpath.pop()


# this method is for development and troubleshooting purposes
def datadiff(data1, data2, branch, p=True):
    def iterator(data1, data2):
        if isinstance(data1, (list,)) and isinstance(data2, (list,)):
            return xrange(max(len(data1), len(data2)))
        elif isinstance(data1, (dict,)) and isinstance(data2, (dict,)):
            return (set(data1.keys()) | set(data2.keys()))
        else:
            raise TypeError

    diff = []
    if data1 != data2:
        try:
            it = iterator(data1, data2)
        except Exception:
            return [(branch, data1, data2)]

        for k in it:
            newbranch = branch[:]
            newbranch.append(k)

            if p:
                print("Comparing branch: %s" % newbranch)
            try:
                try:
                    v1 = data1[k]
                except (KeyError, IndexError):
                    if p:
                        print("data1 seems does not have key = %s" % k)
                    diff.append((newbranch, None, data2[k]))
                    continue
                try:
                    v2 = data2[k]
                except (KeyError, IndexError):
                    if p:
                        print("data2 seems does not have key = %s" % k)
                    diff.append((newbranch, data1[k], None))
                    continue

            except Exception:
                if p:
                    print("data1 and data2 cannot be compared on "
                          "branch: %s" % newbranch)
                return diff.append((newbranch, data1, data2))

            else:
                if v1 != v2:
                    if p:
                        print("data1 and data2 do not match "
                              "each other on branch: %s" % newbranch)
                        # print("data1 = %s" % data1)
                        print("v1 = %s" % v1)
                        # print("data2 = %s" % data2)
                        print("v2 = %s" % v2)
                    diff.extend(datadiff(v1, v2, newbranch))
    return diff
