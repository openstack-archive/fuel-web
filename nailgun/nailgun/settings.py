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

import os

import yaml

from nailgun.logger import logger


class NailgunSettings(object):
    def __init__(self):
        settings_files = []
        logger.debug("Looking for settings.yaml package config "
                     "using old style __file__")
        project_path = os.path.dirname(__file__)
        project_settings_file = os.path.join(project_path, 'settings.yaml')
        settings_files.append(project_settings_file)
        settings_files.append('/etc/nailgun/settings.yaml')

        version_paths = ["/etc/fuel/version.yaml",
                         "/etc/fuel/nailgun/version.yaml",
                         "/etc/nailgun/version.yaml"]
        for path in version_paths:
            if os.access(path, os.R_OK):
                settings_files.append(path)
                break
        else:
            logger.error("'version.yaml' config file is not found")

        test_config = os.environ.get('NAILGUN_CONFIG')
        if test_config:
            settings_files.append(test_config)

        self.config = {}
        for sf in settings_files:
            try:
                logger.debug("Trying to read config file %s" % sf)
                self.update_from_file(sf)
            except Exception as e:
                logger.error("Error while reading config file %s: %s" %
                             (sf, str(e)))

        if int(self.config.get("DEVELOPMENT")):
            logger.info("DEVELOPMENT MODE ON:")
            here = os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..')
            )
            self.config.update({
                'STATIC_DIR': os.path.join(here, 'static'),
                'TEMPLATE_DIR': os.path.join(here, 'static')
            })
            logger.info("Static dir is %s" % self.config.get("STATIC_DIR"))
            logger.info("Template dir is %s" % self.config.get("TEMPLATE_DIR"))

    def update(self, dct):
        self.config.update(dct)

    def update_from_file(self, path):
        with open(path, "r") as custom_config:
            self.config.update(
                yaml.load(custom_config.read())
            )

    def dump(self):
        return yaml.dump(self.config)

    def __getattr__(self, name):
        return self.config.get(name, None)

    def __repr__(self):
        return "<settings object>"


settings = NailgunSettings()
