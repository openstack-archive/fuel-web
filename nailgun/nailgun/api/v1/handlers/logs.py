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
Handlers dealing with logs
"""

from itertools import dropwhile
import logging
import os
import re
import time

import web

from nailgun import consts
from nailgun import objects

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import content_json
from nailgun.openstack.common import jsonutils
from nailgun.settings import settings
from nailgun.task.manager import DumpTaskManager


logger = logging.getLogger(__name__)


def read_backwards(file, bufsize=4096):
    buf = ""
    try:
        file.seek(-1, 1)
    except IOError:
        return
    trailing_newline = False
    if file.read(1) == "\n":
        trailing_newline = True
        file.seek(-1, 1)

    while True:
        newline_pos = buf.rfind("\n")
        pos = file.tell()
        if newline_pos != -1:
            line = buf[newline_pos + 1:]
            buf = buf[:newline_pos]
            if pos or newline_pos or trailing_newline:
                line += "\n"
            yield line
        elif pos:
            toread = min(bufsize, pos)
            file.seek(-toread, 1)
            buf = file.read(toread) + buf
            file.seek(-toread, 1)
            if pos == toread:
                buf = "\n" + buf
        else:
            return


class LogEntryCollectionHandler(BaseHandler):
    """Log entry collection handler
    """

    @content_json
    def GET(self):
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
        user_data = web.input()
        date_before = user_data.get('date_before')
        if date_before:
            try:
                date_before = time.strptime(date_before,
                                            settings.UI_LOG_DATE_FORMAT)
            except ValueError:
                logger.debug("Invalid 'date_before' value: %s", date_before)
                raise self.http(400, "Invalid 'date_before' value")
        date_after = user_data.get('date_after')
        if date_after:
            try:
                date_after = time.strptime(date_after,
                                           settings.UI_LOG_DATE_FORMAT)
            except ValueError:
                logger.debug("Invalid 'date_after' value: %s", date_after)
                raise self.http(400, "Invalid 'date_after' value")
        truncate_log = bool(user_data.get('truncate_log'))

        if not user_data.get('source'):
            logger.debug("'source' must be specified")
            raise self.http(400, "'source' must be specified")

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
        allowed_levels = log_config['levels']
        if level is not None:
            if not (level in log_config['levels']):
                raise self.http(400, "Invalid level")
            allowed_levels = [l for l in dropwhile(lambda l: l != level,
                                                   log_config['levels'])]
        try:
            regexp = re.compile(log_config['regexp'])
        except re.error as e:
            logger.error('Invalid regular expression for file %r: %s',
                         log_config['id'], e)
            raise self.http(500, "Invalid regular expression in config")

        entries = []
        to_byte = None
        try:
            to_byte = int(user_data.get('to', 0))
        except ValueError:
            logger.debug("Invalid 'to' value: %d", to_byte)
            raise self.http(400, "Invalid 'to' value")

        log_file_size = os.stat(log_file).st_size
        if to_byte >= log_file_size:
            return jsonutils.dumps({
                'entries': [],
                'to': log_file_size,
                'has_more': False,
            })

        try:
            max_entries = int(user_data.get('max_entries',
                                            settings.TRUNCATE_LOG_ENTRIES))
        except ValueError:
            logger.debug("Invalid 'max_entries' value: %d", max_entries)
            raise self.http(400, "Invalid 'max_entries' value")

        has_more = False
        with open(log_file, 'r') as f:
            f.seek(0, 2)
            # we need to calculate current position manually instead of using
            # tell() because read_backwards uses buffering
            pos = f.tell()
            multilinebuf = []
            for line in read_backwards(f):
                pos -= len(line)
                if not truncate_log and pos < to_byte:
                    has_more = pos > 0
                    break
                entry = line.rstrip('\n')
                if not len(entry):
                    continue
                if 'skip_regexp' in log_config and \
                        re.match(log_config['skip_regexp'], entry):
                    continue
                m = regexp.match(entry)
                if m is None:
                    if log_config.get('multiline'):
                        #  Add next multiline part to last entry if it exist.
                        multilinebuf.append(entry)
                    else:
                        logger.debug("Unable to parse log entry '%s' from %s",
                                     entry, log_file)
                    continue
                entry_text = m.group('text')
                if len(multilinebuf):
                    multilinebuf.reverse()
                    entry_text += '\n' + '\n'.join(multilinebuf)
                    multilinebuf = []
                entry_level = m.group('level').upper() or 'INFO'
                if level and not (entry_level in allowed_levels):
                    continue
                try:
                    entry_date = time.strptime(m.group('date'),
                                               log_config['date_format'])
                except ValueError:
                    logger.debug("Unable to parse date from log entry."
                                 " Date format: %r, date part of entry: %r",
                                 log_config['date_format'],
                                 m.group('date'))
                    continue

                entries.append([
                    time.strftime(settings.UI_LOG_DATE_FORMAT, entry_date),
                    entry_level,
                    entry_text
                ])
                if truncate_log and len(entries) >= max_entries:
                    has_more = True
                    break

        return {
            'entries': entries,
            'to': log_file_size,
            'has_more': has_more,
        }


class LogPackageHandler(BaseHandler):
    """Log package handler
    """
    @content_json
    def PUT(self):
        """:returns: JSONized Task object.
        :http: * 200 (task successfully executed)
               * 400 (failed to execute task)
        """
        try:
            task_manager = DumpTaskManager()
            task = task_manager.execute()
        except Exception as exc:
            logger.warn(u'DumpTask: error while execution '
                        'dump environment task: {0}'.format(str(exc)))
            raise self.http(400, str(exc))
        raise self.http(202, objects.Task.to_json(task))


class LogSourceCollectionHandler(BaseHandler):
    """Log source collection handler
    """

    @content_json
    def GET(self):
        """:returns: Collection of log sources (from settings)
        :http: * 200 (OK)
        """
        return settings.LOGS


class LogSourceByNodeCollectionHandler(BaseHandler):
    """Log source by node collection handler
    """

    @content_json
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
                    ndir = node.fqdn
                return os.path.join(x['base'], ndir, x['path'])

        f = lambda x: (
            x.get('remote') and x.get('path') and x.get('base') and
            os.access(getpath(x), os.R_OK) and os.path.isfile(getpath(x))
        )
        sources = filter(f, settings.LOGS)
        return sources
