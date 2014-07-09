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

import json
import os
import urllib2

import yaml

from keystoneclient import client as auth_client

from fuelclient.cli.error import exceptions_decorator


class Client(object):
    """This class handles API requests
    """

    def __init__(self):
        self.debug = False
        self.test_mod = bool(os.environ.get('TEST_MODE', ''))
        path_to_config = "/etc/fuel/client/config.yaml"
        defaults = {
            "SERVER_ADDRESS": "127.0.0.1",
            "LISTEN_PORT": "8000",
            "KEYSTONE_USER": "admin",
            "KEYSTONE_PASS": "admin",
            "KEYSTONE_PORT": "5000",
        }
        if os.path.exists(path_to_config):
            with open(path_to_config, "r") as fh:
                config = yaml.load(fh.read())
            defaults.update(config)
        else:
            defaults.update(os.environ)
        self.root = "http://{SERVER_ADDRESS}:{LISTEN_PORT}".format(**defaults)
        self.keystone_base = (
            "http://{SERVER_ADDRESS}:{LISTEN_PORT}/keystone/v2.0"
            .format(**defaults)
        )
        self.api_root = self.root + "/api/v1/"
        self.ostf_root = self.root + "/ostf/"
        self.auth_status()
        self.user = defaults["KEYSTONE_USER"]
        self.password = defaults["KEYSTONE_PASS"]
        self.keystone_client = None
        self.initialize_keystone_client()

    def auth_status(self):
        self.auth_required = False
        if not self.test_mod:
            request = urllib2.urlopen(''.join([self.api_root, 'version']))
            self.auth_required = json.loads(
                request.read()).get('auth_required', False)

    def initialize_keystone_client(self):
        if not self.test_mod and self.auth_required:
            self.keystone_client = auth_client.Client(
                username=self.user,
                password=self.password,
                auth_url=self.keystone_base,
                tenant_name="admin")
            self.keystone_client.authenticate()

    def debug_mode(self, debug=False):
        self.debug = debug
        return self

    def print_debug(self, message):
        if self.debug:
            print(message)

    def delete_request(self, api):
        """Make DELETE request to specific API with some data
        """
        token = self.keystone_client.auth_token if self.keystone_client else ''
        self.print_debug(
            "DELETE {0}".format(self.api_root + api)
        )
        opener = urllib2.build_opener(urllib2.HTTPHandler)
        request = urllib2.Request(self.api_root + api)
        request.add_header('Content-Type', 'application/json')
        request.add_header('X-Auth-Token', token)
        request.get_method = lambda: 'DELETE'
        opener.open(request)
        return {}

    def put_request(self, api, data):
        """Make PUT request to specific API with some data
        """
        token = self.keystone_client.auth_token if self.keystone_client else ''
        data_json = json.dumps(data)
        self.print_debug(
            "PUT {0} data={1}"
            .format(self.api_root + api, data_json)
        )
        opener = urllib2.build_opener(urllib2.HTTPHandler)
        request = urllib2.Request(self.api_root + api, data=data_json)
        request.add_header('Content-Type', 'application/json')
        request.add_header('X-Auth-Token', token)
        request.get_method = lambda: 'PUT'
        return json.loads(
            opener.open(request).read()
        )

    def get_request(self, api, ostf=False):
        """Make GET request to specific API
        """
        token = self.keystone_client.auth_token if self.keystone_client else ''
        url = (self.ostf_root if ostf else self.api_root) + api
        self.print_debug(
            "GET {0}"
            .format(url)
        )
        opener = urllib2.build_opener(urllib2.HTTPHandler)
        request = urllib2.Request(url)
        request.add_header('X-Auth-Token', token)
        return json.loads(
            opener.open(request).read()
        )

    def post_request(self, api, data, ostf=False):
        """Make POST request to specific API with some data
        """
        token = self.keystone_client.auth_token if self.keystone_client else ''
        url = (self.ostf_root if ostf else self.api_root) + api
        data_json = json.dumps(data)
        self.print_debug(
            "POST {0} data={1}"
            .format(url, data_json)
        )
        request = urllib2.Request(
            url=url,
            data=data_json,
            headers={
                'Content-Type': 'application/json'
            }
        )
        request.add_header('X-Auth-Token', token)
        try:
            response = json.loads(
                urllib2.urlopen(request)
                .read()
            )
        except ValueError:
            response = {}
        return response

    @exceptions_decorator
    def get_fuel_version(self):
        return yaml.safe_dump(
            self.get_request("version"),
            default_flow_style=False
        )

# This line is single point of instantiation for 'Client' class,
# which intended to implement Singleton design pattern.
APIClient = Client()
