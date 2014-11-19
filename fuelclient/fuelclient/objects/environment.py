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

from operator import attrgetter
import os
import shutil

from fuelclient.cli.error import ActionException
from fuelclient.cli.error import ArgumentException
from fuelclient.cli.error import ServerDataException
from fuelclient.cli.serializers import listdir_without_extensions
from fuelclient.objects.base import BaseObject
from fuelclient.objects.task import DeployTask
from fuelclient.objects.task import Task


class Environment(BaseObject):

    class_api_path = "clusters/"
    instance_api_path = "clusters/{0}/"

    @classmethod
    def create(cls, name, release_id, net, net_segment_type=None):
        data = {
            "nodes": [],
            "tasks": [],
            "name": name,
            "release_id": release_id
        }
        if net.lower() == "nova":
            data["net_provider"] = "nova_network"
        else:
            data["net_provider"] = "neutron"

            if net_segment_type is None:
                raise ArgumentException(
                    '"--net-segment-type" must be specified!')

            data["net_segment_type"] = net_segment_type

        data = cls.connection.post_request("clusters/", data)
        return cls.init_with_data(data)

    def __init__(self, *args, **kwargs):
        super(Environment, self).__init__(*args, **kwargs)
        self._testruns_ids = []

    def set(self, data):
        if data.get('mode'):
            data["mode"] = "ha_compact" \
                if data['mode'].lower() == "ha" else "multinode"

        return self.connection.put_request(
            "clusters/{0}/".format(self.id),
            data
        )

    def update_env(self):
        return Task.init_with_data(
            self.connection.put_request(
                "clusters/{0}/update/".format(self.id),
                {}
            )
        )

    def delete(self):
        return self.connection.delete_request(
            "clusters/{0}/".format(self.id)
        )

    def assign(self, nodes, roles):
        return self.connection.post_request(
            "clusters/{0}/assignment/".format(self.id),
            [{'id': node.id, 'roles': roles} for node in nodes]
        )

    def unassign(self, nodes):
        return self.connection.post_request(
            "clusters/{0}/unassignment/".format(self.id),
            [{"id": n} for n in nodes]
        )

    def get_all_nodes(self):
        from fuelclient.objects.node import Node
        return sorted(map(
            Node.init_with_data,
            self.connection.get_request(
                "nodes/?cluster_id={0}".format(self.id)
            )
        ), key=attrgetter)

    def unassign_all(self):
        nodes = self.get_all_nodes()
        if not nodes:
            raise ActionException(
                "Environment with id={0} doesn't have nodes to remove."
                .format(self.id)
            )
        return self.connection.post_request(
            "clusters/{0}/unassignment/".format(self.id),
            [{"id": n.id} for n in nodes]
        )

    def deploy_changes(self):
        deploy_data = self.connection.put_request(
            "clusters/{0}/changes".format(self.id),
            {}
        )
        return DeployTask.init_with_data(deploy_data)

    def get_network_data_path(self, directory=os.curdir):
        return os.path.join(
            os.path.abspath(directory),
            "network_{0}".format(self.id)
        )

    def get_settings_data_path(self, directory=os.curdir):
        return os.path.join(
            os.path.abspath(directory),
            "settings_{0}".format(self.id)
        )

    def write_network_data(self, network_data, directory=os.curdir,
                           serializer=None):
        return (serializer or self.serializer).write_to_file(
            self.get_network_data_path(directory),
            network_data
        )

    def write_settings_data(self, settings_data, directory=os.curdir,
                            serializer=None):
        return (serializer or self.serializer).write_to_file(
            self.get_settings_data_path(directory),
            settings_data
        )

    def read_network_data(self, directory=os.curdir,
                          serializer=None):
        network_file_path = self.get_network_data_path(directory)
        return (serializer or self.serializer).read_from_file(
            network_file_path)

    def read_settings_data(self, directory=os.curdir, serializer=None):
        settings_file_path = self.get_settings_data_path(directory)
        return (serializer or self.serializer).read_from_file(
            settings_file_path)

    @property
    def status(self):
        return self.get_fresh_data()['status']

    @property
    def settings_url(self):
        return "clusters/{0}/attributes".format(self.id)

    @property
    def default_settings_url(self):
        return self.settings_url + "/defaults"

    @property
    def network_url(self):
        return "clusters/{id}/network_configuration/{net_provider}".format(
            **self.data
        )

    @property
    def network_verification_url(self):
        return self.network_url + "/verify"

    def get_network_data(self):
        return self.connection.get_request(self.network_url)

    def get_settings_data(self):
        return self.connection.get_request(self.settings_url)

    def get_default_settings_data(self):
        return self.connection.get_request(self.default_settings_url)

    def set_network_data(self, data):
        return self.connection.put_request(
            self.network_url, data)

    def set_settings_data(self, data):
        return self.connection.put_request(
            self.settings_url, data)

    def verify_network(self):
        return self.connection.put_request(
            self.network_verification_url, self.get_network_data())

    def _get_fact_dir_name(self, fact_type, directory=os.path.curdir):
        return os.path.join(
            os.path.abspath(directory),
            "{0}_{1}".format(fact_type, self.id))

    def _get_fact_default_url(self, fact_type, nodes=None):
        default_url = "clusters/{0}/orchestrator/{1}/defaults".format(
            self.id,
            fact_type
        )
        if nodes is not None:
            default_url += "/?nodes=" + ",".join(map(str, nodes))
        return default_url

    def _get_fact_url(self, fact_type, nodes=None):
        fact_url = "clusters/{0}/orchestrator/{1}/".format(
            self.id,
            fact_type
        )
        if nodes is not None:
            fact_url += "/?nodes=" + ",".join(map(str, nodes))
        return fact_url

    def get_default_facts(self, fact_type, nodes=None):
        facts = self.connection.get_request(
            self._get_fact_default_url(fact_type, nodes=nodes))
        if not facts:
            raise ServerDataException(
                "There is no {0} info for this "
                "environment!".format(fact_type)
            )
        return facts

    def get_facts(self, fact_type, nodes=None):
        facts = self.connection.get_request(
            self._get_fact_url(fact_type, nodes=nodes))
        if not facts:
            raise ServerDataException(
                "There is no {0} info for this "
                "environment!".format(fact_type)
            )
        return facts

    def upload_facts(self, fact_type, facts):
        self.connection.put_request(self._get_fact_url(fact_type), facts)

    def delete_facts(self, fact_type):
        self.connection.delete_request(self._get_fact_url(fact_type))

    def read_fact_info(self, fact_type, directory, serializer=None):
        return getattr(
            self, "read_{0}_info".format(fact_type)
        )(fact_type, directory=directory, serializer=serializer)

    def write_facts_to_dir(self, fact_type, facts,
                           directory=os.path.curdir, serializer=None):
        dir_name = self._get_fact_dir_name(fact_type, directory=directory)
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
        os.makedirs(dir_name)
        if isinstance(facts, dict):
            engine_file_path = os.path.join(dir_name, "engine")
            (serializer or self.serializer).write_to_file(
                engine_file_path, facts["engine"])
            facts = facts["nodes"]
            name_template = u"{name}"
        else:
            name_template = "{role}_{uid}"
        for _fact in facts:
            fact_path = os.path.join(
                dir_name,
                name_template.format(**_fact)
            )
            (serializer or self.serializer).write_to_file(fact_path, _fact)
        return dir_name

    def read_deployment_info(self, fact_type,
                             directory=os.path.curdir, serializer=None):
        dir_name = self._get_fact_dir_name(fact_type, directory=directory)
        return map(
            lambda f: (serializer or self.serializer).read_from_file(f),
            [os.path.join(dir_name, json_file)
             for json_file in listdir_without_extensions(dir_name)]
        )

    def read_provisioning_info(self, fact_type,
                               directory=os.path.curdir, serializer=None):
        dir_name = self._get_fact_dir_name(fact_type, directory=directory)
        node_facts = map(
            lambda f: (serializer or self.serializer).read_from_file(f),
            [os.path.join(dir_name, fact_file)
             for fact_file in listdir_without_extensions(dir_name)
             if "engine" != fact_file]
        )
        engine = (serializer or self.serializer).read_from_file(
            os.path.join(dir_name, "engine"))
        return {
            "engine": engine,
            "nodes": node_facts
        }

    def get_testsets(self):
        return self.connection.get_request(
            'testsets/{0}'.format(self.id),
            ostf=True
        )

    @property
    def is_customized(self):
        data = self.get_fresh_data()
        return data["is_customized"]

    def is_in_running_test_sets(self, test_set):
        return test_set["testset"] in self._test_sets_to_run

    def run_test_sets(self, test_sets_to_run):
        self._test_sets_to_run = test_sets_to_run
        tests_data = map(
            lambda testset: {
                "testset": testset,
                "metadata": {
                    "config": {},
                    "cluster_id": self.id
                }
            },
            test_sets_to_run
        )

        testruns = self.connection.post_request(
            "testruns", tests_data, ostf=True)
        self._testruns_ids = [tr['id'] for tr in testruns]
        return testruns

    def get_state_of_tests(self):
        return [
            self.connection.get_request(
                "testruns/{0}".format(testrun_id), ostf=True)
            for testrun_id in self._testruns_ids
        ]

    def stop(self):
        return Task.init_with_data(
            self.connection.put_request(
                "clusters/{0}/stop_deployment/".format(self.id),
                {}
            )
        )

    def reset(self):
        return Task.init_with_data(
            self.connection.put_request(
                "clusters/{0}/reset/".format(self.id),
                {}
            )
        )

    def _get_method_url(self, method_type, nodes):
        return "clusters/{0}/{1}/?nodes={2}".format(
            self.id,
            method_type,
            ','.join(map(lambda n: str(n.id), nodes)))

    def install_selected_nodes(self, method_type, nodes):
        return Task.init_with_data(
            self.connection.put_request(
                self._get_method_url(method_type, nodes),
                {}
            )
        )
