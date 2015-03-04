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

from nailgun.api.v1.handlers.logs import LogEntryController
from nailgun.api.v1.handlers.notifications import NotificationController
from nailgun.api.v1.handlers.tasks import TaskController
from nailgun.api.v1.handlers.registration import TrackingController
from nailgun.api.v1.handlers.version import VersionController

from nailgun.api.v2.controllers.capacity import CapacityLogController
from nailgun.api.v2.controllers.cluster import ClusterController
from nailgun.api.v2.controllers.fake_keystone import FakeKeystoneController
from nailgun.api.v2.controllers.master_node_settings import \
    MasterNodeSettingsController
from nailgun.api.v2.controllers.node import NodeController
from nailgun.api.v2.controllers.node_group import NodeGroupController
from nailgun.api.v2.controllers.plugin import PluginController
from nailgun.api.v2.controllers.redhat import RedHatController
from nailgun.api.v2.controllers.release import ReleaseController

from nailgun.settings import settings


class APIController(BaseController):

    capacity = CapacityLogController()
    clusters = ClusterController()
    logs = LogEntryController()
    nodegroups = NodeGroupController()
    nodes = NodeController()
    notifications = NotificationController()
    plugins = PluginController()
    redhat = RedHatController()
    tracking = TrackingController()
    releases = ReleaseController()
    settings = MasterNodeSettingsController()
    tasks = TaskController()
    version = VersionController()


class RootController(object):

    api = APIController()

    if settings.AUTH['AUTHENTICATION_METHOD'] == 'fake':
        keystone = FakeKeystoneController()

    @pecan.expose('jinja:index.html')
    def index(self):
        return dict()
