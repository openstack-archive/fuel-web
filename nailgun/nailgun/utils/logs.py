# -*- coding: utf-8 -*-

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

import errno
import glob
from gzip import GzipFile
from itertools import dropwhile
import os
import re
import shutil
import struct
import time

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import IPAddr
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import Node
from nailgun.logger import logger
from nailgun import objects
from nailgun.settings import settings
from nailgun.utils import remove_silently


# It turns out that strftime/strptime are costly functions in Python
# http://stackoverflow.com/questions/13468126/a-faster-strptime
# We don't call them if the log and UI date formats aren't very different
STRPTIME_PERFORMANCE_HACK = {}
if settings.UI_LOG_DATE_FORMAT == '%Y-%m-%d %H:%M:%S':
    STRPTIME_PERFORMANCE_HACK = {
        '%Y-%m-%dT%H:%M:%S': lambda date: date.replace('T', ' '),
        '%Y-%m-%d %H:%M:%S': lambda date: date,
    }


class LogParser(object):

    """Log parser."""

    def __init__(self, log_fileobj, fetch_older=False, log_config={},
                 regexp=None, level=None):
        """Initiate log parser.

        :param log_fileobj: log file object
        :type log_fileobj: fileobj
        :param fetch_older: indicates that parser will skip newest bytes
        :type fetch_older: bool
        :param log_config: log parsing configuration
        :type log_config: dict
        :param regexp: date, level, text are being discovered using this regexp
        :type regexp: regular expression object
        :param level: log level of entries which needs to be fetched
        :type level: string
        """

        self.log_fileobj = log_fileobj
        self.fetch_older = fetch_older
        self.log_config = log_config
        self.regexp = regexp
        self.level = level

        self.file_size = 0

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
        """Backward read from given `file` starting from `from_byte`."""
        if self.get_file_size() == 0:
            return
        if from_byte is None:
            from_byte = self.get_file_size()
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
        """Read lines from log file `f`.

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
        pos = self.get_file_size()
        if from_byte != -1 and self.fetch_older:
            pos = from_byte
        self.multilinebuf = []
        for line in self.readlines(
                self.log_fileobj, from_byte=pos, to_byte=to_byte):
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

        if self.fetch_older or (not self.fetch_older and from_byte == -1):
            from_byte = pos
            if from_byte == 0:
                has_more = False

        return (entries, has_more, from_byte)

    def _parse_log_line(self, line):
        """Parse a log `line`."""
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
                             entry, self.log_filename)
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

    def get_file_size(self):
        """Get file size."""
        if not self.file_size:
            self.file_size = os.stat(self.log_filename).st_size
        return self.file_size

    @property
    def log_filename(self):
        """Get filename."""
        return self.log_fileobj.name

    @classmethod
    def open(cls, filename, options):
        parser = None
        try:
            parser = cls(open(filename), **options)
        except IOError as e:
            if e.errno != errno.ENOENT:
                raise
            raise LogFileDoesntExist(
                "Log file '{0}' doesn't exist!".format(filename))
        return parser

    def close(self):
        self.log_fileobj.close()


class GzipLogParser(LogParser):

    def __init__(self, log_fileobj, fetch_older=False, log_config={},
                 regexp=None, level=None):
        super(GzipLogParser, self).__init__(
            GzipFile(fileobj=log_fileobj), fetch_older=fetch_older,
            log_config=log_config, regexp=regexp, level=level)
        log_fileobj.seek(-4, 2)
        self.file_size = struct.unpack("<I", log_fileobj.read(4))[0]
        log_fileobj.seek(0, 0)

    def readlines(self, fileobj, from_byte=-1, to_byte=0):
        lines = []
        if from_byte == -1:
            from_byte = self.get_file_size()
        pos = 0
        for line in fileobj:
            pos += len(line)
            if pos < to_byte:
                continue
            if pos > from_byte:
                break
            lines.append(line)
        lines.reverse()
        return lines

    def get_file_size(self):
        return self.file_size


class LogrotatedLogParser(object):

    """Logrotated log parser.

    Logrotated log files are such files which was rotated using
    `logrotate` linux tool.

    This class is able to parse such logrotated log files in the way
    that for the consumer it looks like that there is only one log file
    exist.
    """

    def __init__(self, log_file, fetch_older, log_config, regexp, level):
        """Initiate logrotated log parser.

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
        self.log_file = log_file
        self.fetch_older = fetch_older

        self.parser_options = {
            'fetch_older': fetch_older,
            'log_config': log_config,
            'regexp': regexp,
            'level': level
        }

    def parse(self, from_byte=-1, to_byte=0, max_entries=None):
        """Parse log files.

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
        total_logs_size = 0
        log_parsers = []
        retries_num = 10
        data = ([], 0, False, )
        while retries_num:
            try:
                filenames = sorted(glob.iglob(self.log_file + '*'))
                filenames.reverse()
                log_parsers = self._make_log_parsers(filenames)

                factory = LPSFactory.create_log_parsing_strategy(
                    log_parsers, from_byte, to_byte,
                    max_entries, self.fetch_older)

                data = factory.parse()

                for _, parser in log_parsers:
                    total_logs_size += parser.get_file_size()

                break
            except LogFileDoesntExist:
                if retries_num > 0:
                    retries_num -= 1
                    continue
                raise
            finally:
                for _, parser in log_parsers:
                    parser.close()

        data += (total_logs_size, )

        return data

    def _make_log_parsers(self, filenames):
        """Make and return log parsers and theirs offsets.

        Make and return log parsers which will be involved in log
        parsing. Actually it returns the list of lists. Each entry
        contains offset and log parser.
        """
        offset = 0
        log_parsers = []
        opened_numbered_logfile = None
        for filename in filenames:
            if filename.endswith('.gz'):
                # `logrotate` (when rotates a log file) copies a log
                # file (e.g. puppet-apply.log) to the temporary numbered
                # file (puppet-apply.log.1) and only then it archives it
                # (to the puppet-apply.log.1.gz). If such numbered file
                # exists, don't use archived log file because it is not
                # completed.
                numbered_log_file, _ = os.path.splitext(filename)
                try:
                    parser = LogParser.open(
                        numbered_log_file, self.parser_options)
                    opened_numbered_logfile = numbered_log_file
                except LogFileDoesntExist:
                    # numbered log file doesn't exist, so archived log
                    # file is probably completed and we can use it
                    parser = GzipLogParser.open(filename, self.parser_options)
            else:
                if filename != opened_numbered_logfile:
                    parser = LogParser.open(filename, self.parser_options)
            if not parser:
                continue
            log_parsers.append((offset, parser, ))
            filesize = parser.get_file_size()
            offset += filesize

        log_parsers.reverse()

        return log_parsers

    def get_log_parsers(self):
        return self.log_parsers


class LogParsingStrategy(object):

    """Base log parsing strategy."""

    def __init__(self, log_parsers, from_byte=None,
                 to_byte=None, max_entries=None):
        self.log_parsers = log_parsers
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
        for offset, parser in self.log_parsers:
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

    """Tail log parsing strategy."""

    def after_log_parsing(self, *args):
        if len(self.entries) >= self.max_entries:
            raise StopIteration()
        else:
            self.parse_max_entries = self.max_entries - len(self.entries)


class RecentlyAddedLPS(LogParsingStrategy):

    """Log parsing strategy for recently added log entries."""

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
        size = sum([p.get_file_size() for _, p in self.log_parsers])
        if self.to_byte >= size:
            return [], self.from_byte, False
        return super(RecentlyAddedLPS, self).parse()

    def after_log_parsing(self, *args):
        if self.stop_iteration:
            raise StopIteration()


class FetchOlderLPS(LogParsingStrategy):

    """Parsing strategy for retrieving older logs entries."""

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

    """Log parsing strategy factory.

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


class LogFileDoesntExist(Exception):

    pass


def prepare_syslog_dir(node, prefix=settings.SYSLOG_DIR):
    logger.debug("Preparing syslog directories for node: %s",
                 objects.Node.get_node_fqdn(node))
    logger.debug("prepare_syslog_dir prefix=%s", prefix)
    log_paths = generate_log_paths_for_node(node, prefix)
    links = log_paths['links']
    old = log_paths['old']
    bak = log_paths['bak']
    new = log_paths['new']

    logger.debug("prepare_syslog_dir old=%s", old)
    logger.debug("prepare_syslog_dir new=%s", new)
    logger.debug("prepare_syslog_dir bak=%s", bak)
    logger.debug("prepare_syslog_dir links=%s", str(links))

    # backup directory if it exists
    if os.path.isdir(new):
        logger.debug("New %s already exists. Trying to backup", new)
        if os.path.islink(bak):
            logger.debug("Bak %s already exists and it is link. "
                         "Trying to unlink", bak)
            os.unlink(bak)
        elif os.path.isdir(bak):
            logger.debug("Bak %s already exists and it is directory. "
                         "Trying to remove", bak)
            shutil.rmtree(bak)
        os.rename(new, bak)

    # rename bootstrap directory into fqdn
    if os.path.islink(old):
        logger.debug("Old %s exists and it is link. "
                     "Trying to unlink", old)
        os.unlink(old)
    if os.path.isdir(old):
        logger.debug("Old %s exists and it is directory. "
                     "Trying to rename into %s", old, new)
        os.rename(old, new)
    else:
        logger.debug("Creating %s", new)
        os.makedirs(new)

    # creating symlinks
    for l in links:
        if os.path.islink(l) or os.path.isfile(l):
            logger.debug("%s already exists. "
                         "Trying to unlink", l)
            os.unlink(l)
        if os.path.isdir(l):
            logger.debug("%s already exists and it directory. "
                         "Trying to remove", l)
            shutil.rmtree(l)
        logger.debug("Creating symlink %s -> %s", l, new)
        os.symlink(objects.Node.get_node_fqdn(node), l)

    os.system("/usr/bin/pkill -HUP rsyslog")


def generate_log_paths_for_node(node, prefix):
    links = map(
        lambda i: os.path.join(prefix, i.ip_addr),
        db().query(IPAddr.ip_addr)
            .join(Node)
            .join(NetworkGroup)
            .filter(Node.id == node.id)
            .filter(NetworkGroup.name == consts.NETWORKS.fuelweb_admin))

    fqdn = objects.Node.get_node_fqdn(node)
    return {
        'links': links,
        'old': os.path.join(prefix, str(node.ip)),
        'bak': os.path.join(prefix, "%s.bak" % fqdn),
        'new': os.path.join(prefix, fqdn),
    }


def delete_node_logs(node, prefix=settings.SYSLOG_DIR):
    node_logs = generate_log_paths_for_node(node, prefix)

    log_paths = node_logs.pop('links') + node_logs.values()
    logger.debug("Deleting logs for removed environment's nodes")

    for log_path in log_paths:
        if os.path.lexists(log_path):
            logger.debug('delete_node_logs log_path="%s"', log_path)
            remove_silently(log_path)
