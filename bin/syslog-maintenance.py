#!/usr/bin/env python

from nailgun import objects
from nailgun.utils import logs as logs_utils


collection = objects.NodeCollection
nodes = collection.filter_by_list(None, 'status', ('ready', 'provisioned','error', 'stopped'))

for node in nodes:
    logs_utils.prepare_syslog_dir(node, deployment=False)
