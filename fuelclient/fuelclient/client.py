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

from fuelclient.cli.error import exceptions_decorator


class APIServer(object):
    """This class handles API requests
    """
    def __init__(self, debug=False):
        self.debug = debug
        path_to_config = "/etc/fuel-client.yaml"
        defaults = {
            "LISTEN_ADDRESS": "127.0.0.1",
            "LISTEN_PORT": "8000"
        }
        if os.path.exists(path_to_config):
            with open(path_to_config, "r") as fh:
                config = yaml.load(fh.read())
            defaults.update(config)
        else:
            defaults.update(os.environ)
        self.root = "http://{LISTEN_ADDRESS}:{LISTEN_PORT}".format(**defaults)
        self.api_root = self.root + "/api/v1/"
        self.ostf_root = self.root + "/ostf/"

    def print_debug(self, message):
        if self.debug:
            print(message)

    def delete_request(self, api):
        """Make DELETE request to specific API with some data
        """
        self.print_debug(
            "DELETE {0}".format(self.api_root + api)
        )
        opener = urllib2.build_opener(urllib2.HTTPHandler)
        request = urllib2.Request(self.api_root + api)
        request.add_header('Content-Type', ' application/json')
        request.get_method = lambda: 'DELETE'
        opener.open(request)
        return {}

    def put_request(self, api, data):
        """Make PUT request to specific API with some data
        """
        data_json = json.dumps(data)
        self.print_debug(
            "PUT {0} data={1}"
            .format(self.api_root + api, data_json)
        )
        opener = urllib2.build_opener(urllib2.HTTPHandler)
        request = urllib2.Request(self.api_root + api, data=data_json)
        request.add_header('Content-Type', ' application/json')
        request.get_method = lambda: 'PUT'
        return json.loads(
            opener.open(request).read()
        )

    def get_request(self, api, ostf=False):
        """Make GET request to specific API
        """
        url = (self.ostf_root if ostf else self.api_root) + api
        self.print_debug(
            "GET {0}"
            .format(url)
        )
        request = urllib2.urlopen(url)
        return json.loads(
            request.read()
        )

    def post_request(self, api, data, ostf=False):
        """Make POST request to specific API with some data
        """
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
