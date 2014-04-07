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

import json
import urllib2

from nailgun.db import db
from nailgun.db.sqlalchemy.models import Attributes
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.task.helpers import TaskHelper


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
            name = TaskHelper.make_slave_fqdn(node['id'])
            hostid = cls._get_zabbix_hostid(url, auth, name)
            if hostid:
                hostids.append(hostid)

        if hostids:
            cls._make_zabbix_request(url, method, hostids, auth=auth)

    @classmethod
    def parse_cluster(cls, cluster):
        zabbix = {}
        role_filter = lambda role: role.name == 'zabbix-server'
        node_filter = lambda node: filter(role_filter, node.role_list)
        zabbix_node = filter(node_filter, cluster.nodes)

        if not zabbix_node:
            return None

        zabbix_node = zabbix_node[0]
        attributes = db().query(Attributes).get(cluster.id)
        zabbix_attrs = attributes.editable['zabbix']
        zabbix['user'] = zabbix_attrs['username']['value']
        zabbix['password'] = zabbix_attrs['password']['value']
        zabbix['url'] = "http://%s/zabbix/api_jsonrpc.php" % zabbix_node.ip
        return zabbix
