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

import os

import pecan
import pecan.deploy
import pecan.hooks

from sqlalchemy import exc as sa_exc

from nailgun.db import db
from nailgun.settings import settings


class CommitHook(pecan.hooks.PecanHook):

    def on_error(self, state, exc):
        if exc in (sa_exc.IntegrityError, sa_exc.DataError):
            db().rollback()
        return

    def after(self, state):
        db().commit()


def setup_app(pecan_config):
    config = dict(pecan_config)

    config['app']['debug'] = bool(settings.DEVELOPMENT)
    config['app']['static_root'] = os.path.join(settings.STATIC_DIR, "..")
    config['app']['hooks'] = [CommitHook()]

    pecan.configuration.set_config(config, overwrite=True)

    app = pecan.make_app(
        pecan_config.app.root,
        debug=getattr(pecan_config.app, 'debug', False),
        force_canonical=getattr(pecan_config.app, 'force_canonical', True),
        static_root=getattr(pecan_config.app, 'static_root', None),
        template_path=getattr(pecan_config.app, 'template_path', None),
        hooks=getattr(pecan_config.app, 'hooks', []),
    )

    return app
