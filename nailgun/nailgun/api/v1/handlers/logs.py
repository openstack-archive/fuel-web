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
Handlers dealing with logs.
"""

import logging
import os
import re
import time

from oslo_serialization import jsonutils

import web

from nailgun import consts
from nailgun import objects

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import content
from nailgun.settings import settings
from nailgun.task.manager import DumpTaskManager
from nailgun.task.task import DumpTask
from nailgun.utils.logs import LogrotatedLogParser


logger = logging.getLogger(__name__)


class LogEntryCollectionHandler(BaseHandler):
    """Log entry collection handler."""

    @content
    def GET(self):
        """Receives following parameters:

        - *date_before* - get logs before this date
        - *date_after* - get logs after this date
        - *source* - source of logs
        - *node* - node id (for getting node logs)
        - *level* - log level (all levels showed by default)
        - *from* - parse a log file from the specific byte
        - *to* - parse a log file to the specific byte
        - *fetch_older* - retrieve older log entries
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
            * 400 (invalid *from* value)
            * 400 (invalid *to* value)
            * 400 (invalid *max_entries* value)
            * 404 (log file not found)
            * 404 (log files dir not found)
            * 404 (node not found)
            * 500 (node has no assigned ip)
            * 500 (invalid regular expression in config)

        There are three uses cases regarding usage of this API entry
        point. Let's investigate it from WebUI standpoint.

        1) When a user opens log page, N most recent log entries are
        loaded and displayed on the page;

        2) When log page is opened, serial requests are repeatedly
        being sent to fetch and display recently added log entries. So
        a user is not required to reload a page and is able to see log
        entries as they appear in the log file;

        3) Not all log entries are loaded on the page at once. Only N
        records. A user wants to investigate more log entries than N
        records which are currently loaded and s/he clicks on
        appropriate link to load more log entries.

        To cover these three cases four parameters are used:
        `max_entries`, `from_byte`, `to_byte` and
        `fetch_older`. Please note that not only these mentioned
        parameters are used, but all others doesn't distinguish
        mentioned use cases, they are common for all of them.

        In the first case `max_entries` is used. This parameter
        defines maximum number of entries which is loaded on the
        page. So, just for example, WebUI may request 100 entries and
        for this purpose it sends `max_entries` with value `100`. As
        the result it gets a response with `entries`, `from` and `to`
        values which means from which and to which particular bytes
        the entries were found in the log file.

        Repeating requests are being sent in case of the second use
        case and each request includes recently mentioned `from` and
        `to` values. If `to` is equal (or greater) than size of the
        log file then response with empty entries is being
        received. When the log is enlarged then `to` will be less than
        actual file size and the client receives in the response only
        those log entries which are located between `to` byte and the
        end of the file. This method allows the client to be received
        only recently added log entries.

        In the last, third, case, a request with `max_entries`,
        `from_byte` and `fetch_older` is sent. In that case, a log
        parser backward reads the log file from `from_byte` byte till
        `max_entries` entries will be parsed. These entries are sent
        in response.

        Important appendix.

        Current implementation does allow to fetch and view log
        entries not only from the one log file but also from those log
        files which are rotated (by means of `logrotate` Linux
        tool). Just for example, a client may request to show most
        recent 100 entries. The original log file has been just
        recently rotated, so on the server there are two files:

        * app.log (20 log entries)
        * app.log.1.gz (40 log entries)

        Current implementation treats these files as the one entire
        log file. So, if a client requests 25 most recent log entries
        (first use case) then log entries are fetched from the both
        `app.log` (all 20 log entries) and `app.log.1.gz` (5 most
        recent log entries) log files. A client, in response, receives
        the following data:

        * `from`, which equals to the length of `app.log` + the length
        of the 5 most recent log entries parsed from `app.log.1.gz`;
        * `to`, which equals to the total length of log files involved
        in log parsing;
        * `entries` with 25 most recent log entries.

        So, in general, we could investigate the log parsing in the
        following way. Let's assume that we have the list of log
        files:

        * app.log.N.gz
        * ...
        * app.log.2.gz
        * app.log.1.gz
        * app.log

        Log parsing is always performed backward from the bottom to
        the top of files stack. `to` and `from` which is included in
        the responses contain values with appropriate offsets.

        """

        data = self.read_and_validate_data()

        logrotated_log_parser = LogrotatedLogParser(
            data.get('log_file'), data.get('fetch_older'),
            data.get('log_config'), data.get('regexp'), data.get('level'))

        entries, parsed_from_byte, has_more, to_byte = \
            logrotated_log_parser.parse(
                data.get('from_byte'),
                data.get('to_byte'),
                data.get('max_entries'))

        return {
            'entries': entries,
            'from': parsed_from_byte,
            'to': to_byte,
            'has_more': has_more
        }

    def read_and_validate_data(self):
        user_data = web.input()

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
                ndir = objects.Node.get_node_fqdn(node)

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


class LogPackageHandler(BaseHandler):
    """Log package handler."""
    @content
    def PUT(self):
        """:returns: JSONized Task object.

        :http: * 200 (task successfully executed)
               * 400 (data validation failed)
               * 404 (cluster not found in db)
        """
        try:
            conf = jsonutils.loads(web.data()) if web.data() else None
            task_manager = DumpTaskManager()
            task = task_manager.execute(conf=conf)
        except Exception as exc:
            logger.warn(u'DumpTask: error while execution '
                        'dump environment task: {0}'.format(str(exc)))
            raise self.http(400, str(exc))

        self.raise_task(task)


class LogPackageDefaultConfig(BaseHandler):

    @content
    def GET(self):
        """Generates default config for snapshot.

        :http: * 200
        """
        return DumpTask.conf()


class LogSourceCollectionHandler(BaseHandler):
    """Log source collection handler."""

    @content
    def GET(self):
        """:returns: Collection of log sources (from settings)

        :http: * 200 (OK)
        """
        return settings.LOGS


class SnapshotDownloadHandler(BaseHandler):

    def GET(self, snapshot_name):
        """:returns: empty response

        :resheader X-Accel-Redirect: snapshot_name
        :http: * 200 (OK)
               * 401 (Unauthorized)
               * 404 (Snapshot with given name does not exist)
        """

        web.header('X-Accel-Redirect', '/dump/' + snapshot_name)
        return ''


class LogSourceByNodeCollectionHandler(BaseHandler):
    """Log source by node collection handler."""

    @content
    def GET(self, node_id):
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
                if node.status == consts.NODE_STATUSES.discover:
                    ndir = node.ip
                else:
                    ndir = objects.Node.get_node_fqdn(node)
                return os.path.join(x['base'], ndir, x['path'])

        f = lambda x: (
            x.get('remote') and x.get('path') and x.get('base') and
            os.access(getpath(x), os.R_OK) and os.path.isfile(getpath(x))
        )
        sources = filter(f, settings.LOGS)
        return sources
