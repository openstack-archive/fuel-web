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

import pecan

from nailgun import hooks


def setup_app(pecan_config):
    config = dict(pecan_config)

    config['app']['hooks'] = [
        hooks.ErrorHook(),
        hooks.CommitHook(),
    ]

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
