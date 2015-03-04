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

"""
Controllers dealing with logs
"""

import logging
import os
import pecan
import re
import time

from oslo.serialization import jsonutils

from nailgun.api.v1.handlers.logs import read_log
from nailgun.api.v2.controllers.base import BaseController

from nailgun import consts
from nailgun import objects
from nailgun.settings import settings
from nailgun.task.manager import DumpTaskManager
from nailgun.task.task import DumpTask


logger = logging.getLogger(__name__)


class LogPackageDefaultConfig(BaseController):

    @pecan.expose(template='json:', content_type='application/json')
    def get_all(self):
        """Generates default config for snapshot
        :http: * 200
        """
        return DumpTask.conf()


class LogPackageConfigController(BaseController):
    default = LogPackageDefaultConfig()


class LogPackageController(BaseController):
    """Log package handler
    """

    config = LogPackageConfigController()

    @pecan.expose(template='json:', content_type='application/json')
    def put(self, dummy=None):
        """:returns: JSONized Task object.
        :http: * 200 (task successfully executed)
               * 202 (network checking task failed)
               * 400 (failed to execute task)
               * 404 (cluster not found in db)
        """
        request = pecan.request
        try:
            conf = jsonutils.loads(request.body) if request.body else None
            task_manager = DumpTaskManager()
            task = task_manager.execute(conf=conf)
        except Exception as exc:
            logger.warn(u'DumpTask: error while execution '
                        'dump environment task: {0}'.format(str(exc)))
            raise self.http(400, str(exc))

        self.raise_task(task)


class LogSourceByNodeController(BaseController):
    """Log source by node collection handler
    """

    single = objects.Node

    @pecan.expose(template='json:', content_type='application/json')
    def get_one(self, node_id):
        """:returns: Collection of log sources by node (from settings)
        :http: * 200 (OK)
               * 404 (node not found in db)
        """
        node = self.get_object_or_404(objects.Node, node_id)

        def getpath(x):
            if x.get('fake'):
                if settings.FAKE_TASKS:
                    return x['path']
                else:
                    return ''
            else:
                if node.status == "discover":
                    ndir = node.ip
                else:
                    ndir = node.fqdn
                return os.path.join(x['base'], ndir, x['path'])

        f = lambda x: (
            x.get('remote') and x.get('path') and x.get('base') and
            os.access(getpath(x), os.R_OK) and os.path.isfile(getpath(x))
        )
        sources = filter(f, settings.LOGS)
        return sources


class LogSourceController(BaseController):
    """Log source collection handler
    """

    nodes = LogSourceByNodeController()

    @pecan.expose(template='json:', content_type='application/json')
    def get_all(self):
        """:returns: Collection of log sources (from settings)
        :http: * 200 (OK)
        """
        return settings.LOGS


class LogEntryController(BaseController):
    """Log entry collection handler
    """

    package = LogPackageController()
    sources = LogSourceController()

    @pecan.expose(template='json:', content_type='application/json')
    def get_all(self):
        """Receives following parameters:

        - *date_before* - get logs before this date
        - *date_after* - get logs after this date
        - *source* - source of logs
        - *node* - node id (for getting node logs)
        - *level* - log level (all levels showed by default)
        - *to* - number of entries
        - *max_entries* - max number of entries to load

        :returns: Collection of log entries, log file size
            and if there are new entries.
        :http:
            * 200 (OK)
            * 400 (invalid *date_before* value)
            * 400 (invalid *date_after* value)
            * 400 (invalid *source* value)
            * 400 (invalid *node* value)
            * 400 (invalid *level* value)
            * 400 (invalid *to* value)
            * 400 (invalid *max_entries* value)
            * 404 (log file not found)
            * 404 (log files dir not found)
            * 404 (node not found)
            * 500 (node has no assigned ip)
            * 500 (invalid regular expression in config)
        """
        data = self.read_and_validate_data()

        log_file = data['log_file']
        fetch_older = data['fetch_older']
        from_byte = data['from_byte']
        to_byte = data['to_byte']

        log_file_size = os.stat(log_file).st_size
        if (not fetch_older and to_byte >= log_file_size) or \
                (fetch_older and from_byte == 0):
            return jsonutils.dumps({
                'entries': [],
                'from': from_byte,
                'to': log_file_size,
                'has_more': False,
            })

        return read_log(**data)

    def read_and_validate_data(self):
        request = pecan.request
        user_data = request.GET

        if not user_data.get('source'):
            logger.debug("'source' must be specified")
            raise self.http(400, "'source' must be specified")

        try:
            max_entries = int(user_data.get('max_entries',
                                            settings.TRUNCATE_LOG_ENTRIES))
        except ValueError:
            logger.debug("Invalid 'max_entries' value: %r",
                         user_data.get('max_entries'))
            raise self.http(400, "Invalid 'max_entries' value")

        from_byte = None
        try:
            from_byte = int(user_data.get('from', -1))
        except ValueError:
            logger.debug("Invalid 'from' value: %r", user_data.get('from'))
            raise self.http(400, "Invalid 'from' value")

        to_byte = None
        try:
            to_byte = int(user_data.get('to', 0))
        except ValueError:
            logger.debug("Invalid 'to' value: %r", user_data.get('to'))
            raise self.http(400, "Invalid 'to' value")

        fetch_older = 'fetch_older' in user_data and \
                      user_data['fetch_older'].lower() in ('1', 'true')

        date_before = user_data.get('date_before')
        if date_before:
            try:
                date_before = time.strptime(date_before,
                                            settings.UI_LOG_DATE_FORMAT)
            except ValueError:
                logger.debug("Invalid 'date_before' value: %r", date_before)
                raise self.http(400, "Invalid 'date_before' value")

        date_after = user_data.get('date_after')
        if date_after:
            try:
                date_after = time.strptime(date_after,
                                           settings.UI_LOG_DATE_FORMAT)
            except ValueError:
                logger.debug("Invalid 'date_after' value: %r", date_after)
                raise self.http(400, "Invalid 'date_after' value")

        log_config = filter(lambda lc: lc['id'] == user_data.get('source'),
                            settings.LOGS)
        # If log source not found or it is fake source but we are run without
        # fake tasks.
        if not log_config or (log_config[0].get('fake') and
                              not settings.FAKE_TASKS):
            logger.debug("Log source %r not found", user_data.get('source'))
            raise self.http(404, "Log source not found")
        log_config = log_config[0]

        # If it is 'remote' and not 'fake' log source then calculate log file
        # path by base dir, node IP and relative path to file.
        # Otherwise return absolute path.
        node = None
        if log_config['remote'] and not log_config.get('fake'):
            if not user_data.get('node'):
                raise self.http(400, "'node' must be specified")
            node = objects.Node.get_by_uid(user_data.get('node'))
            if not node:
                raise self.http(404, "Node not found")
            if not node.ip:
                logger.error('Node %r has no assigned ip', node.id)
                raise self.http(500, "Node has no assigned ip")

            if node.status == consts.NODE_STATUSES.discover:
                ndir = node.ip
            else:
                ndir = node.fqdn

            remote_log_dir = os.path.join(log_config['base'], ndir)
            if not os.path.exists(remote_log_dir):
                logger.debug("Log files dir %r for node %s not found",
                             remote_log_dir, node.id)
                raise self.http(404, "Log files dir for node not found")

            log_file = os.path.join(remote_log_dir, log_config['path'])
        else:
            log_file = log_config['path']

        if not os.path.exists(log_file):
            if node:
                logger.debug("Log file %r for node %s not found",
                             log_file, node.id)
            else:
                logger.debug("Log file %r not found", log_file)
            raise self.http(404, "Log file not found")

        level = user_data.get('level')
        if level is not None and level not in log_config['levels']:
            raise self.http(400, "Invalid level")

        try:
            regexp = re.compile(log_config['regexp'])
        except re.error:
            logger.exception('Invalid regular expression for file %r',
                             log_config['id'])
            raise self.http(500, "Invalid regular expression in config")

        if 'skip_regexp' in log_config:
            try:
                re.compile(log_config['skip_regexp'])
            except re.error:
                logger.exception('Invalid regular expression for file %r',
                                 log_config['id'])
                raise self.http(500, "Invalid regular expression in config")

        return {
            'date_after': date_after,
            'date_before': date_before,
            'level': level,
            'log_file': log_file,
            'log_config': log_config,
            'max_entries': max_entries,
            'node': node,
            'regexp': regexp,

            'fetch_older': fetch_older,
            'from_byte': from_byte,
            'to_byte': to_byte,
        }
