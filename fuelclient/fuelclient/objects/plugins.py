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
import tarfile

from requests import exceptions
import yaml

from fuelclient.cli import error
from fuelclient.objects import base


EXTRACT_PATH = "/var/www/nailgun/plugins/{name}-{version}/"
VERSIONS_PATH = '/etc/fuel/versions.yaml'


class Plugins(base.BaseObject):

    class_api_path = "plugins/"
    class_instance_path = "plugins/{id}"

    metadata_config = 'metadata.yaml'

    @classmethod
    def validate_environment(cls):
        return os.path.exists(VERSIONS_PATH)

    @classmethod
    def get_metadata(cls, plugin_tar):
        for member_name in plugin_tar.getnames():
            if cls.metadata_config in member_name:
                return yaml.load(plugin_tar.extractfile(member_name).read())
        raise error.BadDataException("Tarfile {0} doesnot have {1}".format(
            plugin_tar.name, cls.metadata_config))

    @classmethod
    def add_plugin(cls, plugin_meta, plugin_tar):
        extract_to = EXTRACT_PATH.format(
            name=plugin_meta['name'], version=plugin_meta['version'])
        plugin_tar.extractall(extract_to)
        return True

    @classmethod
    def install_plugin(cls, plugin_path, force=False):
        if not cls.validate_environment():
            raise error.WrongEnvironmentError(
                'Plugin can be installed only on master node.')
        with tarfile.open(plugin_path, 'r') as plugin_tar:
            metadata = cls.get_metadata(plugin_tar)
            resp = cls.connection.post_request_raw(
                cls.class_api_path, metadata)
            if resp.status_code == 409 and force:
                url = cls.class_instance_path.format(id=resp.json()['id'])
                resp = cls.connection.put_request(
                    url, metadata)
            elif resp.status_code == 201:
                return resp
            else:
                raise exceptions.HTTPError(response=resp)
            cls.add_plugin(metadata, plugin_tar)
        return resp
