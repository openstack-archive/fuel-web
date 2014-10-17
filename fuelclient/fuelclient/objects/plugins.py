#    Copyright 2014 Mirantis, Inc.
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
from subprocess import Popen, PIPE

import yaml

from fuelclient.objects import base

INSTALL_COMMAND = """
plugin_name={name}-{version}
repo_path=/var/www/nailgun
plugin_path=$repo_path/plugins/$plugin_name

rm -rf  $plugin_path
mkdir -p $plugin_path
cp -rf * $plugin_path/
"""


class Plugins(base.BaseObject):

    class_api_path = "plugins/"
    class_instance_path = "plugins/{id}"

    @classmethod
    def get_plugins_for_cluster(cls, cluster_id):
        data = cls.connection.get_request(
            "clusters/{0}/plugins".format(cluster_id))
        return data

    @classmethod
    def get_metadata(cls, directory):
        metadata_path = os.path.join(directory, 'metadata.yaml')
        with open(metadata_path) as f:
            return yaml.load(f.read())

    @classmethod
    def add_plugin(cls, metadata):
        command = INSTALL_COMMAND.format(
            name=metadata['name'], version=metadata['version'])
        execute = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
        out, err = execute.communicate()
        return execute.returncode

    @classmethod
    def install_plugin(cls, directory):
        metadata = cls.get_metadata(directory)
        resp = cls.connection.post_request(cls.class_api_path, metadata)
        # if exception is not raised - copy files
        cls.add_plugin(metadata)
        return resp

    @classmethod
    def update_plugin(cls, plugin_id, directory):
        metadata = cls.get_metadata(directory)
        url = cls.class_instance_path.format(id=plugin_id)
        resp = cls.connection.put_request(url, metadata)
        # if exception is not raised - copy files
        cls.add_plugin(metadata)
        return resp
