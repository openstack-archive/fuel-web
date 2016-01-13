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

import logging
import os
import shutil
import sys

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import IPAddr
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import Node
from nailgun.logger import logger
from nailgun.logger import set_logger
from nailgun import objects
from nailgun.settings import settings
from nailgun.utils import remove_silently


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


def prepare_submodule_logger(submodule_name, file_path=None):
    logger = logging.getLogger(submodule_name)

    if file_path is None:
        handler = logging.FileHandler(file_path)
    else:
        handler = logging.StreamHandler(sys.stdout)

    set_logger(logger, handler)

    return logger
