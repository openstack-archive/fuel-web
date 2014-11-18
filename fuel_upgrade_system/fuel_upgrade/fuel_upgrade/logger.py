# -*- coding: utf-8 -*-

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

from fuel_upgrade.config import Config
from fuel_upgrade.utils import sanitize
import logging
import sys


class UpgradeLogger(logging.Logger):
    def makeRecord(self, name, level, fn, lno, msg, args, exc_info, func=None,
                   extra=None):
        _args = []
        for arg in args:
            if isinstance(arg, (list, dict)):
                _arg = sanitize(arg, ['password', 'token'])
            elif isinstance(arg, Config):
                _arg = sanitize(arg._config, ['password', 'token'])
            else:
                _arg = arg
            _args.append(_arg)

        return logging.Logger.makeRecord(self, name, level, fn, lno, msg,
                                         tuple(_args), exc_info, func, extra)


def configure_logger(path):
    logging.setLoggerClass(UpgradeLogger)
    logger = logging.getLogger('fuel_upgrade')
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s %(process)d (%(module)s) %(message)s',
        "%Y-%m-%d %H:%M:%S")

    if sys.stdout.isatty():
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    return logger
