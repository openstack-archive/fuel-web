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

import datetime
import hashlib
import itertools
import json
import six

from nailgun.middleware import utils

from nailgun.db import db
from nailgun.db.sqlalchemy.models import ActionLog

from nailgun import consts


urls_actions_mapping = {
    r'.*/clusters/(?P<cluster_id>\d+)/changes/?$': {
        'action_name': 'deploy_changes',
        'action_group': 'cluster_changes'
    },
    r'.*/clusters/(?P<cluster_id>\d+)/provision/?$': {
        'action_name': 'provision',
        'action_group': 'cluster_changes'
    },
    r'.*/clusters/(?P<cluster_id>\d+)/deploy/?$': {
        'action_name': 'deploy',
        'action_group': 'cluster_changes'
    },
    r'.*/clusters/(?P<cluster_id>\d+)/stop_deployment/?$': {
        'action_name': 'stop_deployment',
        'action_group': 'cluster_changes'
    },
    r'.*/clusters/(?P<cluster_id>\d+)/reset/?$': {
        'action_name': 'reset',
        'action_group': 'cluster_changes'
    },
    r'.*/clusters/(?P<cluster_id>\d+)/update/?$': {
        'action_name': 'update',
        'action_group': 'cluster_changes'
    },
    r'.*/clusters/?$': {
        'action_name': 'cluster_collection',
        'action_group': 'cluster_changes'
    },
    r'.*/clusters/(?P<cluster_id>\d+)/?$': {
        'action_name': 'cluster_instance',
        'action_group': 'cluster_changes'
    }
}


compiled_urls_actions_mapping = \
    utils.compile_mapping_keys(urls_actions_mapping)


class ConnectionMonitorMiddleware(object):

    methods_to_analize = ('POST', 'PUT', 'DELETE', 'PATCH')

    def __init__(self, app):
        self.app = app
        self.status = None

    def __call__(self, env, start_response):
        if env['REQUEST_METHOD'] in self.methods_to_analize:
            url_matcher = self._get_url_matcher(url=env['PATH_INFO'])
            if url_matcher:
                request_body = utils.get_body_from_env(env)

                def save_headers_start_response(status, headers, *args):
                    """Hook for saving response headers for further
                    processing
                    """
                    self.status = status
                    return start_response(status, headers, *args)

                # Prepare arguments for ActionLog instance creation
                create_kwargs = {}

                create_kwargs['start_timestamp'] = datetime.datetime.now()
                response = self.app(env, save_headers_start_response)
                create_kwargs['end_timestamp'] = datetime.datetime.now()

                # since responce is iterator to avoid its exhaustion in
                # analysing process we make two copies of it: one to be
                # processed in stats collection logic and the other to
                # propagate further on middleware stack
                response_to_analyse, response_to_propagate = \
                    itertools.tee(response)

                create_kwargs['actor_id'] = self._get_actor_id(env)

                create_kwargs['action_name'] = \
                    compiled_urls_actions_mapping[url_matcher]['action_name']
                create_kwargs['action_group'] = \
                    compiled_urls_actions_mapping[url_matcher]['action_group']

                create_kwargs['action_type'] = \
                    consts.ACTION_TYPES.http_request

                create_kwargs['additional_info'] = \
                    self._get_additional_info(env,
                                              request_body,
                                              response_to_analyse)

                # get cluster_id from url
                cluster_id = utils.get_group_from_matcher(url_matcher,
                                                          env['PATH_INFO'],
                                                          'cluster_id')
                if cluster_id:
                    cluster_id = int(cluster_id)

                create_kwargs['cluster_id'] = cluster_id

                db.add(ActionLog(**create_kwargs))
                db.commit()

                return response_to_propagate

        return self.app(env, start_response)

    def _get_url_matcher(self, url):
        for url_matcher in six.iterkeys(compiled_urls_actions_mapping):
            if url_matcher.match(url):
                return url_matcher

        return None

    def _get_actor_id(self, env):
        token_id = env.get('X_AUTH_TOKEN')

        if not token_id:
            return None

        return hashlib.sha256(token_id).hexdigest()

    def _get_additional_info(self, env, request_body, response_to_analyse):
        additional_info = {
            'request_data': self._get_request_data(env, request_body),
            'response_data': self._get_response_data(response_to_analyse)
        }
        return additional_info

    def _get_request_data(self, env, request_body):
        request_data = {
            'http_method': env['REQUEST_METHOD'],
            'url': env['PATH_INFO'],
            'data': None,
            'message': None
        }

        if request_body:
            try:
                request_data['data'] = json.loads(request_body)
            except Exception as e:
                request_data['message'] = (
                    'Error while loading incomming'
                    ' JSON. Details: {0}'.format(e)
                )

        return request_data

    def _get_response_data(self, response):
        response = [d for d in response]

        response_data = {
            'status': self.status,
            'message': None,
            'data': None
        }

        # check whether request was failed
        if not self.status.startswith('20'):
            # useful data always will be stored in first element of
            # response
            response_data['message'] = response[0]
        else:
            response_data['data'] = json.loads(response[0])

        return response_data
