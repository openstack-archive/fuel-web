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

import hashlib
import itertools
import re
import six

from nailgun.middleware import utils

from nailgun.db import db
from nailgun.db.sqlalchemy.models import action_logs


urls_actions_mapping = {
    r'/clusters/(?P<cluster_id>\d+)/changes/?$': {
        'action_name': 'deploy_changes',
        'action_group': 'cluster_changes'
    },
    r'/clusters/(?P<cluster_id>\d+)/provision/?$': {
        'action_name': 'provision',
        'action_group': 'cluster_changes'
    },
    r'/clusters/(?P<cluster_id>\d+)/deploy/?$': {
        'action_name': 'deploy',
        'action_group': 'cluster_changes'
    },
    r'/clusters/(?P<cluster_id>\d+)/stop_deployment/?$': {
        'action_name': 'stop_deployment',
        'action_group': 'cluster_changes'
    },
    r'/clusters/(?P<cluster_id>\d+)/reset/?$': {
        'action_name': 'reset',
        'action_group': 'cluster_changes'
    },
    r'/clusters/(?P<cluster_id>\d+)/update/?$': {
        'action_name': 'update',
        'action_group': 'cluster_changes'
    },
}

actions_groups = {
    ('deploy_changes', 'provision', 'deploy',
     'stop_deployment', 'reset', 'update'): 'cluster_changes',
}


urls_actions_mapping = utils.compile_mapping_keys(urls_actions_mapping)


class ConnectionMonitorMiddleware(object):

    methods_to_analize = ('POST', 'PUT', 'DELETE')

    def __init__(self, app):
        self.app = app
        self.status = None

    def __call__(self, env, start_response):

        # process incoming request
        env, request_body = utils.get_body_from_env(env)

        def save_headers_start_response(status, headers, *args):
            """Hook for saving response headers for further processing
            """
            self.status = status
            return start_response(status, headers, *args)

        response = self.app(env, save_headers_start_response)
        response_to_analyse, response_to_propagate = itertools.tee(response)

        self.analyze_request(env, request_body, response_to_analyse)

        db.commit()

        return response_to_propagate

    def analyze_request(self, env, request_body, response_to_analyse):
        create_kwargs = {}

        for key, value in six.iteritems(urls_actions_mapping):
            if re.match(key, env['PATH_INFO']):
                create_kwargs['action_name'] = value['action_name']
                create_kwargs['action_group'] = value['action_group']
                break
        else:
            # end request analysing
            return

        token_id = env.get('X_AUTH_TOKEN', 'public')
        create_kwargs['actor_id'] = hashlib.sha256(token_id).hexdigest()

        db.add(action_logs.ActionLogs(**create_kwargs))
