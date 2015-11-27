# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

import requests

from nailgun.settings import settings


class BareonAPIAdapter(object):
    nodes_path = '/v1/nodes/{0}'
    disks_path = nodes_path + '/disks'
    partitioning_path = nodes_path + '/partitioning'
    node_id_template = 'nailgun_{0}'

    def __init__(self, bareon_address=None):
        if not bareon_address:
            bareon_address = settings.BAREON_ADDRESS

        self.bareon_address = 'http://{0}'.format(bareon_address)

    def _request(self, method, path, data=None, headers=None,
                 check_status=200):
        method = method.upper()
        data = data or {}
        headers = headers or {}

        url = self.bareon_address + path       # json=? too old requests
        response = requests.request(method, url, data=json.dumps(data),
                                    headers=headers)
        if response.status_code != check_status:
            raise RuntimeError('Expected {0} status code, not {1}.'.format(
                check_status, response.status_code))
        return response

    def exists(self, node_id):
        path = self.nodes_path.format(
            self.node_id_template.format(node_id)
        )
        try:
            self._request('GET', path, check_status=200)
        except RuntimeError:
            return False
        return True

    def partitioning(self, node_id):
        "GET only"
        node_id = self.node_id_template.format(node_id)
        path = self.partitioning_path.format(node_id)
        return self._request('GET', path).json()

    def disks(self, node_id, data=None):
        node_id = self.node_id_template.format(node_id)
        path = self.disks_path.format(node_id)
        if data:
            self._request('PUT', path, data=data)
        else:
            return self._request('GET', path).json()

    def create_node(self, data):
        data['source_id'] = data['id']
        data['id'] = self.node_id_template.format(data['source_id'])
        self._request('POST', self.nodes_path.format(''), data=data)

    def delete_node(self, node_id):
        node_id = self.node_id_template.format(node_id)
        self._request('DELETE', self.nodes_path.format(node_id),
                      check_status=204)
