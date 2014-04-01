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

import simplejson as json
import urllib2

from nailgun.errors import errors
from nailgun.logger import logger


class ZabbixManager(object):

    @classmethod
    def _make_zabbix_request(cls, url, method, params, auth=None):
        header = {'Content-type': 'application/json'}
        data = {'jsonrpc': '2.0',
                'id': '1',
                'method': method,
                'params': params}
        if auth:
            data['auth'] = auth

        logger.debug("Zabbix request: %s", data)
        request = urllib2.Request(url, json.dumps(data), header)

        try:
            response = urllib2.urlopen(request)
        except urllib2.URLError as e:
            raise errors.CannotMakeZabbixRequest(
                "Can't make a request to Zabbix: {0}".format(e)
            )

        result = json.loads(response.read())
        logger.debug("Zabbix response: %s", result)

        if 'error' in result:
            code = result['error']['code']
            msg = result['error']['message']
            data = result['error']['data']
            raise errors.ZabbixRequestError(
                "Zabbix returned error code {0}, {1}: {2}".format(
                    code, msg, data
                )
            )

        return result['result']

    @classmethod
    def _zabbix_auth(cls, url, user, password):
        method = 'user.authenticate'
        params = {'user': user,
                  'password': password}
        auth_hash = cls._make_zabbix_request(url, method, params)
        return auth_hash

    @classmethod
    def _get_zabbix_hostid(cls, url, auth, name):
        method = 'host.get'
        params = {'filter': {'host': name}}
        result = cls._make_zabbix_request(url, method, params, auth=auth)

        if len(result) == 0:
            logger.info("Host %s does not exist in zabbix, skipping", name)
            return None

        return result[0]['hostid']

    @classmethod
    def remove_from_zabbix(cls, zabbix, nodes):
        url = zabbix['url']
        user = zabbix['user']
        password = zabbix['password']
        auth = cls._zabbix_auth(url, user, password)
        hostids = []
        method = "host.delete"

        for node in nodes:
            name = node['slave_name']
            hostid = cls._get_zabbix_hostid(url, auth, name)
            if hostid:
                hostids.append(hostid)

        if hostids:
            cls._make_zabbix_request(url, method, hostids, auth=auth)

    @classmethod
    def get_zabbix_node(cls, cluster):
        zabbix_nodes = filter(
            lambda node: filter(
                lambda role: role.name == 'zabbix-server',
                node.role_list
            ),
            cluster.nodes
        )

        if not zabbix_nodes:
            return None

        return zabbix_nodes[0]

    @classmethod
    def get_zabbix_credentials(cls, cluster):
        creds = {}

        zabbix_node = cls.get_zabbix_node(cluster)
        attributes = cluster.attributes
        zabbix_attrs = attributes.editable['zabbix']
        creds['user'] = zabbix_attrs['username']['value']
        creds['password'] = zabbix_attrs['password']['value']
        creds['url'] = "http://{0}/zabbix/api_jsonrpc.php".format(
            zabbix_node.ip
        )
        return creds
