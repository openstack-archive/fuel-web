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

from contextlib import contextmanager
import glob
import gzip
from itertools import dropwhile
import logging
import os
import re
import struct
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


logger = logging.getLogger(__name__)


# It turns out that strftime/strptime are costly functions in Python
# http://stackoverflow.com/questions/13468126/a-faster-strptime
# We don't call them if the log and UI date formats aren't very different
STRPTIME_PERFORMANCE_HACK = {}
if settings.UI_LOG_DATE_FORMAT == '%Y-%m-%d %H:%M:%S':
    STRPTIME_PERFORMANCE_HACK = {
        '%Y-%m-%dT%H:%M:%S': lambda date: date.replace('T', ' '),
        '%Y-%m-%d %H:%M:%S': lambda date: date,
    }


class BaseLogParser(object):

    def __init__(self, log_file, fetch_older=False, log_config={},
                 regexp=None, level=None):

        self.log_file = log_file
        self.fetch_older = fetch_older
        self.log_config = log_config
        self.regexp = regexp
        self.level = level


class LogParser(BaseLogParser):

    """Log parser"""

    def __init__(self, log_file, fetch_older=False, log_config={},
                 regexp=None, level=None):
        """Initiate log parser

        :param log_file: log file
        :type log_file: string
        :param fetch_older: indicates that parser will skip newest bytes
        :type fetch_older: bool
        :param log_config: log parsing configuration
        :type log_config: dict
        :param regexp: date, level, text are being discovered using this regexp
        :type regexp: regular expression object
        :param level: log level of entries which needs to be fetched
        :type level: string
        """
        super(LogParser, self).__init__(
            log_file, fetch_older=fetch_older, log_config=log_config,
            regexp=regexp, level=level)

        self.log_date_format = self.log_config.get('date_format')
        self.multiline = self.log_config.get('multiline', False)
        self.skip_regexp = None
        if 'skip_regexp' in self.log_config:
            self.skip_regexp = re.compile(self.log_config.get('skip_regexp'))

        self.allowed_levels = self.log_config.get('levels')
        if self.level:
            self.allowed_levels = set(dropwhile(lambda l: l != self.level,
                                                self.log_config.get('levels')))

        if self.log_date_format in STRPTIME_PERFORMANCE_HACK:
            self.strptime_function = \
                STRPTIME_PERFORMANCE_HACK[self.log_date_format]
        else:
            self.strptime_function = lambda date: time.strftime(
                settings.UI_LOG_DATE_FORMAT,
                time.strptime(date, self.log_date_format))

    def _read_backwards(self, file, from_byte=None, bufsize=0x20000):
        """Backward read from given `file` starting from `from_byte`"""
        cache_pos = file.tell()
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(cache_pos, os.SEEK_SET)
        if size == 0:
            return
        if from_byte is None:
            from_byte = size
        lines = ['']
        read_size = bufsize
        rem = from_byte % bufsize
        if rem == 0:
            # Perform bufsize reads only
            pos = max(0, (from_byte // bufsize - 1) * bufsize)
        else:
            # One more iteration will be done to read rem bytes so that we
            # are aligned to exactly bufsize reads later on
            read_size = rem
            pos = (from_byte // bufsize) * bufsize

        while pos >= 0:
            file.seek(pos, os.SEEK_SET)
            data = file.read(read_size) + lines[0]
            lines = re.findall('[^\n]*\n?', data)
            ix = len(lines) - 2
            while ix > 0:
                yield lines[ix]
                ix -= 1
            pos -= bufsize
            read_size = bufsize
        else:
            yield lines[0]
            # Set cursor position to last read byte
            try:
                file.seek(max(0, pos), os.SEEK_SET)
            except IOError:
                pass

    def readlines(self, f, from_byte=-1, to_byte=0):
        """Read lines from log file `f`

        Read lines from log file from `from_byte` to `to_byte`.

        :param f: log file to read from
        :type f: fileobj
        :param from_byte: read from `from_byte`
        :type from_byte: int
        :param to_byte: read to `to_byte`
        :type to_byte: int
        """
        return self._read_backwards(f, from_byte=from_byte)

    def parse(self, from_byte=-1, to_byte=0, max_entries=None):
        """Parse a log file from `from_byte` to `to_byte`.

        Parse a log file from `from_byte` to `to_byte`. If `from_byte`
        is omitted then read from the beginning of a file. If
        `to_byte` is omitted then read a log file to the end of a log
        file.

        :param from_byte: parse log file from `from_byte`
        :type from_byte: int
        :param to_byte: parse the log file to `to_byte`
        :type to_byte: int
        :param max_entries: max count of entries to fetch
        :type max_entries: int
        """
        entries = []
        has_more = False
        with self.open_file() as f:
            pos = self._init_pos(f, from_byte)
            self.multilinebuf = []
            for line in self.readlines(f, from_byte=pos, to_byte=to_byte):
                pos -= len(line)
                if not self.fetch_older and pos < to_byte:
                    has_more = pos > 0
                    break

                entry = self._parse_log_line(line)
                if not entry:
                    continue

                entries.append(entry)

                if max_entries and len(entries) >= max_entries:
                    has_more = True
                    break

            if self.fetch_older or (not self.fetch_older
                                    and from_byte == -1):
                from_byte = pos
                if from_byte == 0:
                    has_more = False

        return (entries, has_more, from_byte)

    def _parse_log_line(self, line):
        """Parse a log `line`"""
        entry = line.rstrip('\n')
        if not len(entry):
            return
        if self.skip_regexp and self.skip_regexp.match(entry):
            return
        m = self.regexp.match(entry)
        if m is None:
            if self.multiline:
                #  Add next multiline part to last entry if it exist.
                self.multilinebuf.append(entry)
            else:
                logger.debug("Unable to parse log entry '%s' from %s",
                             entry, self.log_file)
            return
        entry_text = m.group('text')
        if len(self.multilinebuf):
            self.multilinebuf.reverse()
            entry_text += '\n' + '\n'.join(self.multilinebuf)
            self.multilinebuf = []
        entry_level = m.group('level').upper() or 'INFO'
        if self.level and not (entry_level in self.allowed_levels):
            return
        try:
            entry_date = self.strptime_function(m.group('date'))
        except ValueError:
            logger.debug("Unable to parse date from log entry."
                         " Date format: %r, date part of entry: %r",
                         self.log_date_format,
                         m.group('date'))
            return

        return entry_date, entry_level, entry_text

    def open_file(self):
        """Open log file for further parsing"""
        return open(self.log_file)

    def _init_pos(self, fileobj, from_byte):
        fileobj.seek(0, os.SEEK_END)
        pos = fileobj.tell()
        if from_byte != -1 and self.fetch_older:
            pos = from_byte
        return pos

    @property
    def file_size(self):
        """Get file size"""
        return os.stat(self.log_file).st_size


class GzipLogParser(LogParser):

    @contextmanager
    def open_file(self):
        """Open gzip file using context manager"""
        yield gzip.open(self.log_file)

    def readlines(self, fileobj, from_byte=-1, to_byte=0):
        lines = []
        if from_byte == -1:
            from_byte = self.file_size
        pos = 0
        for line in fileobj:
            lines.append(line)
            pos += len(line)
            if pos < to_byte:
                lines.pop()
                continue
            if pos > from_byte:
                lines.pop()
                break
        return reversed(lines)

    def _init_pos(self, fileobj, from_byte):
        pos = self.file_size
        if from_byte != -1 and self.fetch_older:
            pos = from_byte
        return pos

    @property
    def file_size(self):
        with open(self.log_file) as f:
            f.seek(-4, 2)
            return struct.unpack("<I", f.read(4))[0]


class LogrotatedLogParser(BaseLogParser):

    """Logrotated log parser

    Logrotated log files are such files which was rotated using
    `logrotate` linux tool.

    This class is able to parse such logrotated log files in the way
    that for the consumer it looks like that there is only one log file
    exist.
    """

    def __init__(self, log_file, fetch_older, log_config, regexp, level):
        """Initiate logrotated log parser

        :param log_file: path to the base log file
        (e.g. /var/log/puppet-apply.log). All other logrotated logs will
        be found using this base path.
        :type log_file: string
        :param fetch_older: indicates whether we need to fetch older
        entries, i.e. skip most recent entries
        :type fetch_older: bool
        :param log_config: is used for log parser configuration
        :type log_config: dict
        :param regexp: regexp which will be used for log parsing
        :type regexp: string
        :param level: specifies the level of log entries which will be fetched
        :type level: string
        """
        super(LogrotatedLogParser, self).__init__(
            log_file, fetch_older=fetch_older, log_config=log_config,
            regexp=regexp, level=level)

    def parse(self, from_byte=-1, to_byte=0, max_entries=None):
        """Parse log files

        Parse all logs collected together from `from_byte` to
        `to_byte`. Maximum count of entries which will be retrieved is
        equal to `max_entries` (if specified).

        :param from_byte: read logs from `from_byte` position
        :type from_byte: int
        :param to_byte: read logs to `to_byte` position
        :type to_byte: int
        :param max_entries: maximum count of entries
        :type max_entries: int
        """
        factory = LPSFactory.create_log_parsing_strategy(
            self, from_byte, to_byte, max_entries, self.fetch_older)
        return factory.parse()

    @property
    def total_log_files_size(self):
        """Total size of all rotated log files plus the base one"""
        logs_size = 0
        for _, parser in self.log_parsers:
            logs_size += parser.file_size
        return logs_size

    @property
    def log_parsers(self):
        """Create and return log parsers and theirs offsets

        Create and return log parsers which will be involved in log
        parsing. Actually it returns the list of lists. Each entry
        contains offset and log parser.
        """
        offset = 0
        log_parsers = []
        filenames = glob.iglob(self.log_file + '*')
        for filename in reversed(sorted(filenames)):
            # `logrotate` (when rotates a log file) copies a log file
            # (e.g. puppet-apply.log) to the temporary numbered file
            # (puppet-apply.log.1) and only then it archives it (to the
            # puppet-apply.log.1.gz). If such numbered file exists, don't use
            # archived log file because it is not completed.
            numbered_log_file, _ = os.path.splitext(filename)
            if (filename.endswith('.gz')
                    and not os.path.isfile(numbered_log_file)):
                parser_class = GzipLogParser
            else:
                parser_class = LogParser
            parser = parser_class(
                filename, fetch_older=self.fetch_older,
                log_config=self.log_config, regexp=self.regexp,
                level=self.level)
            log_parsers.append((offset, parser, ))
            offset += parser.file_size

        return reversed(log_parsers)


class LogParsingStrategy(object):

    """Base log parsing strategy"""

    def __init__(self, logrotated_log_parser, from_byte=None,
                 to_byte=None, max_entries=None):
        self.logrotated_log_parser = logrotated_log_parser
        self.from_byte = from_byte
        self.parse_from_byte = from_byte
        self.to_byte = to_byte
        self.parse_to_byte = to_byte
        self.max_entries = max_entries
        self.parse_max_entries = max_entries

    def before_log_parsing(self, offset, parser):
        pass

    def after_log_parsing(self, offset, parser):
        pass

    def parse(self):
        self.entries = []
        parsed_from_byte = self.from_byte
        has_more = False
        for offset, parser in self.logrotated_log_parser.log_parsers:
            try:
                self.before_log_parsing(offset, parser)
            except ContinueIteration:
                continue
            items, has_more, from_byte = \
                parser.parse(
                    from_byte=self.parse_from_byte,
                    to_byte=self.parse_to_byte,
                    max_entries=self.parse_max_entries)
            parsed_from_byte = offset + from_byte
            self.entries += items
            try:
                self.after_log_parsing(offset, parser)
            except StopIteration:
                break
        return self.entries, parsed_from_byte, has_more


class TailLPS(LogParsingStrategy):

    """Tail log parsing strategy"""

    def after_log_parsing(self, *args):
        if len(self.entries) >= self.max_entries:
            raise StopIteration()
        else:
            self.parse_max_entries = self.max_entries - len(self.entries)


class RecentlyAddedLPS(LogParsingStrategy):

    """Log parsing strategy for recently added log entries"""

    log_was_rotated = False

    stop_iteration = False

    def before_log_parsing(self, offset, parser):
        self.parse_from_byte = self.from_byte - offset
        self.parse_to_byte = self.to_byte - offset
        if not self.log_was_rotated:
            if self.parse_from_byte < 0 or self.parse_to_byte < 0:
                self.log_was_rotated = True
            if self.parse_from_byte < 0:
                self.parse_from_byte = 0
        else:
            self.stop_iteration = True

    def parse(self):
        size = self.logrotated_log_parser.total_log_files_size
        if self.to_byte >= size:
            return [], self.from_byte, False
        return super(RecentlyAddedLPS, self).parse()

    def after_log_parsing(self, *args):
        if self.stop_iteration:
            raise StopIteration()


class FetchOlderLPS(LogParsingStrategy):

    """Parsing strategy for retrieving older logs entries"""

    first_parser = True

    def before_log_parsing(self, offset, parser):
        if self.first_parser:
            self.parse_from_byte = self.from_byte - offset
            if self.parse_from_byte <= 0:
                # The end of current log file is found. It is needed to be
                # proceed to the next log file
                raise ContinueIteration()
        else:
            # parse all other log files (except first one) from the beginning
            # of a log file
            self.parse_from_byte = -1
        self.first_parser = False

    def parse(self):
        if self.from_byte == 0:
            return [], self.from_byte, False
        return super(FetchOlderLPS, self).parse()

    def after_log_parsing(self, offset, parser):
        if len(self.entries) >= self.max_entries:
            raise StopIteration()
        else:
            self.parse_max_entries = self.max_entries - len(self.entries)


class LPSFactory(object):

    """Log parsing strategy factory

    The purpose of this strategy factory is to create appropriate strategy
    instance based on the input data.
    """

    @staticmethod
    def create_log_parsing_strategy(
            logrotated_log_parser, from_byte, to_byte,
            max_entries, fetch_older):
        if from_byte == -1 and to_byte == 0:
            strategy_class = TailLPS
        if from_byte != -1 and to_byte != 0:
            strategy_class = RecentlyAddedLPS
        if from_byte != -1 and fetch_older:
            strategy_class = FetchOlderLPS
        return strategy_class(
            logrotated_log_parser, from_byte, to_byte, max_entries)


class ContinueIteration(Exception):

    pass


class LogEntryCollectionHandler(BaseHandler):
    """Log entry collection handler"""

    @content
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

        data = self.read_and_validate_data()

        logrotated_log_parser = LogrotatedLogParser(
            data.get('log_file'), data.get('fetch_older'),
            data.get('log_config'), data.get('regexp'), data.get('level'))

        entries, parsed_from_byte, has_more = \
            logrotated_log_parser.parse(
                data.get('from_byte'),
                data.get('to_byte'),
                data.get('max_entries'))

        return {
            'entries': entries,
            'from': parsed_from_byte,
            'to': logrotated_log_parser.total_log_files_size,
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
    """Log package handler"""
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
        """Generates default config for snapshot

        :http: * 200
        """
        return DumpTask.conf()


class LogSourceCollectionHandler(BaseHandler):
    """Log source collection handler"""

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
    """Log source by node collection handler"""

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
