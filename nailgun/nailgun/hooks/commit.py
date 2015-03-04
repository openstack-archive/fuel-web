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

import pecan.hooks

from sqlalchemy import exc as sa_exc

from nailgun.db import db


class CommitHook(pecan.hooks.PecanHook):

    def on_error(self, state, exc):
        if isinstance(exc, sa_exc.IntegrityError) or \
               isinstance(exc, sa_exc.DataError):
            db().rollback()
        elif hasattr(exc, 'code') and exc.code < 400:
            db().commit()

    def after(self, state):
        db().commit()
