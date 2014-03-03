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
import shutil

from fuelclient.client import APIServer
from fuelclient.objects import BaseObject
from fuelclient.cli.serializers import Serializer
from fuelclient.cli.serializers import folder_or_one_up
from fuelclient.cli.serializers import listdir_without_extensions


class Environment(BaseObject):

    def __init__(self, params):
        # dict initialisation
        #super(Environment, self).__init__()

        self.connection = APIServer(params=params)
        self.serializer = Serializer(params=params)
        self.id = params.env
        self.params = params

    def create(self, name, release):
        pass

    def _get_fact_dir_name(self, fact_type):
        return os.path.join(
            os.path.abspath(self.params.dir or os.path.curdir),
            "{0}_{1}".format(fact_type, self.id))

    def _get_fact_default_url(self, fact_type):
        default_url = "clusters/{0}/orchestrator/{1}/defaults".format(
            self.id,
            fact_type
        )
        if self.params.node:
            default_url += "/?nodes=" + ",".join(map(str, self.params.node))
        return default_url

    def _get_fact_url(self, fact_type):
        return "clusters/{0}/orchestrator/{1}/".format(
            self.id,
            fact_type
        )

    def get_default_facts(self, fact_type):
        return self.connection.get_request(
            self._get_fact_default_url(fact_type))

    def get_facts(self, fact_type):
        return self.connection.get_request(
            self._get_fact_url(fact_type))

    def upload_facts(self, facts, fact_type):
        self.connection.put_request(self._get_fact_url(fact_type), facts)

    def delete_facts(self, fact_type):
        self.connection.delete_request(self._get_fact_url(fact_type))

    def read_fact_info(self, fact_type):
        if fact_type == "deployment":
            return self.read_deployment_info(fact_type)
        elif fact_type == "provisioning":
            return self.read_provisioning_info(fact_type)

    def write_facts_to_dir(self, facts, fact_type):
        dir_name = self._get_fact_dir_name(fact_type)
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print("old directory {0} was removed".format(dir_name))
        os.makedirs(dir_name)
        print("directory {0} was created".format(dir_name))
        if isinstance(facts, dict):
            engine_file_path = os.path.join(dir_name, "engine")
            engine_file_path = self.serializer.write_to_file(engine_file_path, facts["engine"])
            print("Created {0}".format(engine_file_path))
            facts = facts["nodes"]
            name_template = "{name}"
        else:
            name_template = "{role}_{uid}"
        for _fact in facts:
            fact_path = os.path.join(
                dir_name,
                name_template.format(**_fact)
            )
            fact_path = self.serializer.write_to_file(fact_path, _fact)
            print("Created {0}".format(fact_path))

    def read_deployment_info(self, fact_type):
        dir_name = folder_or_one_up(
            self._get_fact_dir_name(fact_type)
        )
        return map(
            lambda f: self.serializer.read_from_file(f)[0],
            [os.path.join(dir_name, json_file)
             for json_file in listdir_without_extensions(dir_name)]
        )

    def read_provisioning_info(self, fact_type):
        dir_name = folder_or_one_up(
            self._get_fact_dir_name(fact_type)
        )
        node_facts = map(
            lambda f: self.serializer.read_from_file(f)[0],
            [os.path.join(dir_name, fact_file)
             for fact_file in listdir_without_extensions(dir_name)
             if "engine" != fact_file]
        )
        engine, _ = self.serializer.read_from_file(os.path.join(dir_name, "engine"))
        return {
            "engine": engine,
            "nodes": node_facts
        }
