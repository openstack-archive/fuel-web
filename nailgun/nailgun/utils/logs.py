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
