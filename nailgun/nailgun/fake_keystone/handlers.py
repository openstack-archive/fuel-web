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

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import content
from nailgun.fake_keystone import generate_token
from nailgun.fake_keystone import validate_password_credentials
from nailgun.fake_keystone import validate_token
from nailgun.settings import settings


class TokensHandler(BaseHandler):

    @content
    def POST(self):
        data = self.checked_data()
        try:
            if 'passwordCredentials' in data['auth']:
                if not validate_password_credentials(
                        **data['auth']['passwordCredentials']):
                    raise self.http(401)
            elif 'token' in data['auth']:
                if not validate_token(data['auth']['token']['id']):
                    raise self.http(401)
            else:
                raise self.http(400)
        except (KeyError, TypeError):
            raise self.http(400)

        token = generate_token()

        return {
            "access": {
                "token": {
                    "issued_at": "2012-07-10T13:37:58.708765",
                    "expires": "2012-07-10T14:37:58Z",
                    "id": token,
                    "tenant": {
                        "description": None,
                        "enabled": True,
                        "id": "12345",
                        "name": "admin"
                    }
                },
                "serviceCatalog": [],
                "user": {
                    "username": "admin",
                    "roles_links": [],
                    "id": "9876",
                    "roles": [{"name": "admin"}],
                    "name": "admin"
                },
                "metadata": {
                    "is_admin": 0,
                    "roles": ["4567"]
                }
            }
        }


class VersionHandler(BaseHandler):

    @content
    def GET(self):
        keystone_href = 'http://{ip_addr}:{port}/keystone/v2.0/'.format(
            ip_addr=settings.LISTEN_ADDRESS, port=settings.LISTEN_PORT)
        return {
            'version': {
                'id': 'v2.0',
                'status': 'stable',
                'updated': '2014-04-17T00:00:00Z',
                'links': [
                    {
                        'rel': 'self',
                        'href': keystone_href,
                    }, {
                        'rel': 'describedby',
                        'type': 'text/html',
                        'href': 'http://docs.openstack.org/',
                    },
                ],
                'media-types': [
                    {
                        'base': 'application/json',
                        'type': 'application/vnd.openstack.identity-v2.0+json',
                    }, {
                        'base': 'application/xml',
                        'type': 'application/vnd.openstack.identity-v2.0+xml',
                    },
                ],
            },
        }


class ServicesHandler(BaseHandler):

    @content
    def GET(self):
        return {
            'OS-KSADM:services': [{'type': 'ostf', 'enabled': True,
                                   'id': '8022ba1deb954c358168a84334bd69c3',
                                   'name': 'ostf', 'description': 'OSTF'},
                                  {'type': 'identity', 'enabled': True,
                                   'id': '832897e705d74c289d9b2250b8013740',
                                   'name': 'keystone',
                                   'description':
                                       'OpenStack Identity Service'},
                                  {'type': 'fuel', 'enabled': True,
                                   'id': 'b192638664804529b455cf2a1aacf661',
                                   'name': 'nailgun',
                                   'description': 'Nailgun API'}],
        }


class EndpointsHandler(BaseHandler):

    @content
    def GET(self):
        keystone_href = 'http://{ip_addr}:{port}/keystone/v2.0'.format(
            ip_addr=settings.AUTH['auth_host'], port=settings.LISTEN_PORT)
        nailgun_href = 'http://{ip_addr}:{port}/api'.format(
            ip_addr=settings.AUTH['auth_host'], port=settings.LISTEN_PORT)
        ostf_href = 'http://{ip_addr}:{port}/ostf'.format(
            ip_addr=settings.AUTH['auth_host'], port=settings.LISTEN_PORT)
        return {
            'endpoints': [{'adminurl': keystone_href,
                           'region': 'RegionOne',
                           'enabled': True,
                           'internalurl': keystone_href,
                           'service_id': '832897e705d74c289d9b2250b8013740',
                           'id': 'bc231214ba63458e927f9163e9bd291e',
                           'publicurl': keystone_href},
                          {'adminurl': nailgun_href,
                           'region': 'RegionOne', 'enabled': True,
                           'internalurl': nailgun_href,
                           'service_id': 'b192638664804529b455cf2a1aacf661',
                           'id': 'e6c36dd455274e4092c6f959795a9cd0',
                           'publicurl': nailgun_href},
                          {'adminurl': ostf_href,
                           'region': 'RegionOne', 'enabled': True,
                           'internalurl': ostf_href,
                           'service_id': '8022ba1deb954c358168a84334bd69c3',
                           'id': '7c0ab0939231438a83a5b930b88dc7b2',
                           'publicurl': ostf_href}],
        }
