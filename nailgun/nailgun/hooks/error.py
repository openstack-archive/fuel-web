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

from oslo.serialization import jsonutils

import pecan
import pecan.hooks
import webob
import webob.exc
import traceback

from nailgun import errors


class ErrorHook(pecan.hooks.PecanHook):
    def format_error_message(self, message, details=None):
        try:
            jsonutils.loads(message)
            return message
        except (ValueError, TypeError):
            return jsonutils.dumps({
                # TODO(pkaminski): decide on one of these
                # (error is required in test_public_api::test_500_no_html_dev)
                'error': message,
                'message': message,
                'details': details,
            })

    def on_error(self, state, e):
        if isinstance(e, errors.NailgunException):
            message = e.message or \
                errors.default_messages.get(e.__class__.__name__,
                                            e.__class__.__name__)
            status = 400
            if isinstance(e, errors.errors.ObjectNotFound):
                status = 404
            return webob.Response(
                body=self.format_error_message(message),
                status=status,
                headerlist=[
                    ('Content-Type', 'application/json'),
                ]
            )

        if isinstance(e, webob.exc.HTTPException):
            return webob.Response(
                body=self.format_error_message(e.detail),
                status=e.status,
                headerlist=[
                    ('Content-Type', 'application/json'),
                ]
            )

        return webob.Response(
            body=self.format_error_message(e.message,
                                           details=traceback.format_exc()),
            status=500,
            headerlist=[
                ('Content-Type', 'application/json'),
            ]
        )
