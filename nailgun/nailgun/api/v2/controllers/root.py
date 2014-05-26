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
from nailgun.api.v2.controllers.cluster import VmwareController
from nailgun.api.v2.controllers.fake_keystone import FakeKeystoneController
from nailgun.api.v2.controllers.node import NodeController
from nailgun.api.v2.controllers.node_group import NodeGroupController
from nailgun.api.v2.controllers.notification import NotificationController
from nailgun.api.v2.controllers.registration import RegistrationController
from nailgun.api.v2.controllers.release import ReleaseController
from nailgun.api.v2.controllers.task import TaskController
from nailgun.api.v2.controllers.version import VersionController

from nailgun.settings import settings


class APIController(BaseController):

    capacity = CapacityLogController()
    clusters = ClusterController()
    nodegroups = NodeGroupController()
    nodes = NodeController()
    notifications = NotificationController()
    registration = RegistrationController()
    releases = ReleaseController()
    tasks = TaskController()
    version = VersionController()
    vmware = VmwareController()


class RootController(object):

    api = APIController()

    if settings.AUTH['AUTHENTICATION_METHOD'] == 'fake':
        keystone = FakeKeystoneController()

    @pecan.expose('jinja:index.html')
    def index(self):
        return dict()
