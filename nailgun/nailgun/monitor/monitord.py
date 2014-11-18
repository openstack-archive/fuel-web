# -*- coding: utf-8 -*-

# Copyright 2014 Mirantis, Inc.
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
import six
import sys
import yaml

sys.path.insert(0, os.path.dirname(__file__))

import time

from datetime import datetime

from nailgun import notifier

from nailgun.db import db
from nailgun.logger import logger
from nailgun.settings import settings


DEFAULT_STATE_SCHEMA = {
    'alert_date': None,
    'message': '',
}


def safe_read_states():
    try:
        f = open(settings.MONITORD['states_file'])
        return yaml.load(f.read()) or {}
    except IOError:
        f = open(settings.MONITORD['states_file'], 'w')
        f.close()

    return {}


def read_state(state_name):
    return safe_read_states().get(state_name, DEFAULT_STATE_SCHEMA.copy())


def write_state(state_name, value):
    r = safe_read_states()
    r[state_name] = value

    f = open(settings.MONITORD['states_file'], 'w')
    f.write(yaml.dump(r, default_flow_style=False))


def error_already_reported(state_name):
    state = read_state(state_name)

    return bool(state.get('alert_date', False))


def notify(state_name, message, topic=None):
    schema = DEFAULT_STATE_SCHEMA.copy()

    now = datetime.now().isoformat()

    if topic == 'error':
        schema['alert_date'] = now
        schema['message'] = message

    write_state(state_name, schema)

    notifier.notify(topic, message)
    db().commit()


def get_disk_space_error():
    """Check free disk space.
    """
    s = os.statvfs('/')
    free_gb = s.f_bavail * s.f_frsize / (1024.0 ** 3)

    if free_gb <= settings.MONITORD['free_disk_error']:
        return (
            True,
            'Your disk space is running low (%.2f GB currently available).'
            % free_gb
        )

    return (
        False,
        'Your free disk space is back to normal.'
    )


def monitor_fuel_master():
    """Monitor Fuel Master node.
    """
    checks = {
        'disk_space': get_disk_space_error,
    }

    for name, check in six.iteritems(checks):
        has_error, message = check()

        if has_error:
            # Notify about detected problems
            if not error_already_reported(name):
                notify(name, message, topic='error')
        else:
            # Notify about no more valid problems
            if error_already_reported(name):
                notify(name, message, topic='done')


def run():
    logger.info('Running Monitord...')
    try:
        while True:
            monitor_fuel_master()
            time.sleep(settings.MONITORD['interval'])
    except (KeyboardInterrupt, SystemExit):
        logger.info('Stopping Monitord...')
        sys.exit(1)


if __name__ == '__main__':
    run()
