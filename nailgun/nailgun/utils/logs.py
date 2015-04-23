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

import os
import shutil

from nailgun.db import db
from nailgun.db.sqlalchemy.models import IPAddr
from nailgun.logger import logger
from nailgun.settings import settings


def prepare_syslog_dir(node, admin_net_id, prefix=settings.SYSLOG_DIR):
    logger.debug("Preparing syslog directories for node: %s", node.fqdn)
    logger.debug("prepare_syslog_dir prefix=%s", prefix)
    log_paths = generate_log_paths_for_node(node, admin_net_id, prefix)
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
        os.symlink(str(node.fqdn), l)

    os.system("/usr/bin/pkill -HUP rsyslog")


def generate_log_paths_for_node(node, admin_net_id, prefix):
    links = map(
        lambda i: os.path.join(prefix, i.ip_addr),
        db().query(IPAddr.ip_addr).
        filter_by(node=node.id).
        filter_by(network=admin_net_id).all()
    )

    return {
        'links': links,
        'old': os.path.join(prefix, str(node.ip)),
        'bak': os.path.join(prefix, "%s.bak" % str(node.fqdn)),
        'new': os.path.join(prefix, str(node.fqdn)),
    }


def remove_log(path):
    """Removes log from file system

    no matter if it's file, folder or symlink

    :param path: log path
    """
    try:
        if os.path.islink(path):
            os.unlink(path)
        elif os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
    except OSError as e:
        logger.exception(e)


def delete_node_logs(node, admin_net_id, prefix=settings.SYSLOG_DIR):
    node_logs = generate_log_paths_for_node(node, admin_net_id, prefix)

    log_paths = node_logs.pop('links') + node_logs.values()
    logger.debug("Deleting logs for removed environment's nodes")

    for log_path in log_paths:
        if os.path.exists(log_path):
            logger.debug('delete_node_logs log_path="%s"', log_path)
            remove_log(log_path)
