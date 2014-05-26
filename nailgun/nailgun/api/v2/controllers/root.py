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

import pecan

from nailgun.api.v2.controllers.base import BaseController

from nailgun.api.v2.controllers.capacity import CapacityLogController
from nailgun.api.v2.controllers.cluster import ClusterController
from nailgun.api.v2.controllers.node import NodeController
from nailgun.api.v2.controllers.notification import NotificationController
from nailgun.api.v2.controllers.release import ReleaseController
from nailgun.api.v2.controllers.registration import RegistrationController
from nailgun.api.v2.controllers.task import TaskController
from nailgun.api.v2.controllers.version import VersionController


class APIController(BaseController):

    releases = ReleaseController()
    clusters = ClusterController()
    capacity = CapacityLogController()
    nodes = NodeController()
    notifications = NotificationController()
    registration = RegistrationController()
    tasks = TaskController()
    version = VersionController()


class RootController(object):

    api = APIController()

    @pecan.expose('jinja:index.html')
    def index(self):
        return dict()
