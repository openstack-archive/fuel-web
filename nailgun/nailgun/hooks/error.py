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

import pecan
import pecan.hooks
import webob
import webob.exc
import traceback

from nailgun import errors
from nailgun.openstack.common import jsonutils


class ErrorHook(pecan.hooks.PecanHook):
    def on_error(self, state, e):
        if isinstance(e, errors.NailgunException):
            message = e.message or \
                errors.default_messages.get(e.__class__.__name__,
                                            e.__class__.__name__)
            return webob.Response(
                body=message,
                status=400,
                headerlist=[
                    ('Content-Type', 'application/json'),
                ]
            )

        if isinstance(e, webob.exc.HTTPException):
            return webob.Response(
                body=e.detail,
                status=e.status,
                headerlist=[
                    ('Content-Type', 'application/json'),
                ]
            )

        return webob.Response(
            body=jsonutils.dumps({
                'error': e.message,
                'details': traceback.format_exc(),
            }),
            status=500,
            headerlist=[
                ('Content-Type', 'application/json'),
            ]
        )
