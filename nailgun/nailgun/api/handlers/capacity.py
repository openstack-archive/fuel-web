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

import csv
from hashlib import md5
import tempfile

import web

from nailgun.api.handlers.base import build_json_response
from nailgun.api.handlers.base import content_json
from nailgun.api.handlers.base import JSONHandler
from nailgun.api.handlers.tasks import TaskHandler
from nailgun.api.models import CapacityLog
from nailgun.db import db
from nailgun.task.manager import GenerateCapacityLogTaskManager

"""
Capacity audit handlers
"""


class CapacityLogHandler(JSONHandler):
    """Task single handler
    """

    fields = (
        "id",
        "report"
    )

    model = CapacityLog

    @content_json
    def GET(self):
        capacity_log = db().query(CapacityLog).\
            order_by(CapacityLog.datetime.desc()).first()
        if not capacity_log:
            raise web.notfound()
        return self.render(capacity_log)

    def PUT(self):
        """Starts capacity data generation.

        :returns: JSONized Task object.
        :http: * 202 (setup task created and started)
        """
        manager = GenerateCapacityLogTaskManager()
        task = manager.execute()

        data = build_json_response(TaskHandler.render(task))
        raise web.accepted(data=data)


class CapacityLogCsvHandler(object):
    def GET(self):
        capacity_log = db().query(CapacityLog).\
            order_by(CapacityLog.datetime.desc()).first()
        if not capacity_log:
            raise web.notfound()

        report = capacity_log.report
        f = tempfile.TemporaryFile(mode='r+b')
        csv_file = csv.writer(f, delimiter=',',
                              quotechar='|', quoting=csv.QUOTE_MINIMAL)

        csv_file.writerow(['Fuel version', report['fuel_data']['release']])
        csv_file.writerow(['Fuel UUID', report['fuel_data']['uuid']])

        csv_file.writerow(['Checksum', md5(report).hexdigest()])

        csv_file.writerow(['Environment Name', 'Node Count'])
        for stat in report['environment_stats']:
            csv_file.writerow([stat['cluster'], stat['nodes']])

        csv_file.writerow(['Total number allocated of nodes',
                           report['allocation_stats']['allocated']])
        csv_file.writerow(['Total number of unallocated nodes',
                           report['allocation_stats']['unallocated']])

        csv_file.writerow([])
        csv_file.writerow(['Node role(s)',
                           'Number of nodes with this configuration'])
        for roles, count in report['roles_stat'].iteritems():
            csv_file.writerow([roles, count])
        filename = 'fuel-capacity-audit.csv'
        web.header('Content-Type', 'application/octet-stream')
        web.header('Content-Disposition', 'attachment; filename="%s"' % (
            filename))
        web.header('Content-Length', f.tell())
        f.seek(0)
        return f
