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

"""
Handlers dealing with clusters
"""

import traceback

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import CollectionHandler
from nailgun.api.v1.handlers.base import content
from nailgun.api.v1.handlers.base import DeferredTaskHandler
from nailgun.api.v1.handlers.base import DeploymentTasksHandler
from nailgun.api.v1.handlers.base import SingleHandler

from nailgun.api.v1.validators.cluster import AttributesValidator
from nailgun.api.v1.validators.cluster import ClusterChangesValidator
from nailgun.api.v1.validators.cluster import ClusterValidator
from nailgun.api.v1.validators.cluster import VmwareAttributesValidator

from nailgun.api.v1.validators.extension import ExtensionValidator

from nailgun.extensions.base import set_extensions_for_object

from nailgun.logger import logger
from nailgun import objects

from nailgun.task.manager import ApplyChangesTaskManager
from nailgun.task.manager import ClusterDeletionManager
from nailgun.task.manager import ResetEnvironmentTaskManager
from nailgun.task.manager import StopDeploymentTaskManager
from nailgun.task.manager import UpdateEnvironmentTaskManager


class ClusterHandler(SingleHandler):
    """Cluster single handler"""

    single = objects.Cluster
    validator = ClusterValidator

    @content
    def DELETE(self, obj_id):
        """:returns: {}

        :http: * 202 (cluster deletion process launched)
               * 400 (failed to execute cluster deletion process)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(self.single, obj_id)
        task_manager = ClusterDeletionManager(cluster_id=cluster.id)
        try:
            logger.debug('Trying to execute cluster deletion task')
            task_manager.execute()
        except Exception as e:
            logger.warn('Error while execution '
                        'cluster deletion task: %s' % str(e))
            logger.warn(traceback.format_exc())
            raise self.http(400, str(e))

        raise self.http(202, '{}')


class ClusterCollectionHandler(CollectionHandler):
    """Cluster collection handler"""

    collection = objects.ClusterCollection
    validator = ClusterValidator


class ClusterChangesHandler(DeferredTaskHandler):

    log_message = u"Trying to start deployment at environment '{env_id}'"
    log_error = u"Error during execution of deployment " \
                u"task on environment '{env_id}': {error}"
    task_manager = ApplyChangesTaskManager
    validator = ClusterChangesValidator


class ClusterStopDeploymentHandler(DeferredTaskHandler):

    log_message = u"Trying to stop deployment on environment '{env_id}'"
    log_error = u"Error during execution of deployment " \
                u"stopping task on environment '{env_id}': {error}"
    task_manager = StopDeploymentTaskManager


class ClusterResetHandler(DeferredTaskHandler):

    log_message = u"Trying to reset environment '{env_id}'"
    log_error = u"Error during execution of resetting task " \
                u"on environment '{env_id}': {error}"
    task_manager = ResetEnvironmentTaskManager


class ClusterUpdateHandler(DeferredTaskHandler):

    log_message = u"Trying to update environment '{env_id}'"
    log_error = u"Error during execution of update task " \
                u"on environment '{env_id}': {error}"
    task_manager = UpdateEnvironmentTaskManager


class ClusterAttributesHandler(BaseHandler):
    """Cluster attributes handler"""

    fields = (
        "editable",
    )

    validator = AttributesValidator

    @content
    def GET(self, cluster_id):
        """:returns: JSONized Cluster attributes.

        :http: * 200 (OK)
               * 404 (cluster not found in db)
               * 500 (cluster has no attributes)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        if not cluster.attributes:
            raise self.http(500, "No attributes found!")

        return {
            'editable': objects.Cluster.get_editable_attributes(
                cluster, all_plugins_versions=True)
        }

    def PUT(self, cluster_id):
        """:returns: JSONized Cluster attributes.

        :http: * 200 (OK)
               * 400 (wrong attributes data specified)
               * 404 (cluster not found in db)
               * 500 (cluster has no attributes)
        """
        # Due to the fact that we don't support PATCH requests and we're
        # using PUT requests for the same purpose with non-complete data,
        # let's follow DRY principle and call PATCH handler for now.
        # In future, we have to use PUT method for overwrite the whole
        # entity and PATCH method for changing its parts.
        return self.PATCH(cluster_id)

    @content
    def PATCH(self, cluster_id):
        """:returns: JSONized Cluster attributes.

        :http: * 200 (OK)
               * 400 (wrong attributes data specified)
               * 403 (attribute changing is not allowed)
               * 404 (cluster not found in db)
               * 500 (cluster has no attributes)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)

        if not cluster.attributes:
            raise self.http(500, "No attributes found!")

        data = self.checked_data(cluster=cluster)
        objects.Cluster.patch_attributes(cluster, data)

        return {
            'editable': objects.Cluster.get_editable_attributes(
                cluster, all_plugins_versions=True)
        }


class ClusterAttributesDefaultsHandler(BaseHandler):
    """Cluster default attributes handler"""

    fields = (
        "editable",
    )

    @content
    def GET(self, cluster_id):
        """:returns: JSONized default Cluster attributes.

        :http: * 200 (OK)
               * 404 (cluster not found in db)
               * 500 (cluster has no attributes)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        attrs = objects.Cluster.get_default_editable_attributes(cluster)
        if not attrs:
            raise self.http(500, "No attributes found!")
        return {"editable": attrs}

    @content
    def PUT(self, cluster_id):
        """:returns: JSONized Cluster attributes.

        :http: * 200 (OK)
               * 400 (wrong attributes data specified)
               * 404 (cluster not found in db)
               * 500 (cluster has no attributes)
        """
        cluster = self.get_object_or_404(
            objects.Cluster,
            cluster_id,
            log_404=(
                "error",
                "There is no cluster "
                "with id '{0}' in DB.".format(cluster_id)
            )
        )

        if not cluster.attributes:
            logger.error('ClusterAttributesDefaultsHandler: no attributes'
                         ' found for cluster_id %s' % cluster_id)
            raise self.http(500, "No attributes found!")

        cluster.attributes.editable = (
            objects.Cluster.get_default_editable_attributes(cluster))
        objects.Cluster.add_pending_changes(cluster, "attributes")

        logger.debug('ClusterAttributesDefaultsHandler:'
                     ' editable attributes for cluster_id %s were reset'
                     ' to default' % cluster_id)
        return {"editable": cluster.attributes.editable}


class ClusterGeneratedData(BaseHandler):
    """Cluster generated data"""

    @content
    def GET(self, cluster_id):
        """:returns: JSONized cluster generated data

        :http: * 200 (OK)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        return cluster.attributes.generated


class ClusterDeploymentTasksHandler(DeploymentTasksHandler):
    """Cluster Handler for deployment graph serialization."""

    single = objects.Cluster


class VmwareAttributesHandler(BaseHandler):
    """Vmware attributes handler"""

    fields = (
        "editable",
    )

    validator = VmwareAttributesValidator

    @content
    def GET(self, cluster_id):
        """:returns: JSONized Cluster vmware attributes.

        :http: * 200 (OK)
               * 400 (cluster doesn't accept vmware configuration)
               * 404 (cluster not found in db |
                      cluster has no vmware attributes)
        """
        cluster = self.get_object_or_404(
            objects.Cluster, cluster_id,
            log_404=(
                "error",
                "There is no cluster "
                "with id '{0}' in DB.".format(cluster_id)
            )
        )
        if not objects.Cluster.is_vmware_enabled(cluster):
            raise self.http(400, "Cluster doesn't support vmware "
                                 "configuration")

        attributes = objects.Cluster.get_vmware_attributes(cluster)
        if not attributes:
            raise self.http(404, "No vmware attributes found")

        return self.render(attributes)

    @content
    def PUT(self, cluster_id):
        """:returns: JSONized Cluster vmware attributes.

        :http: * 200 (OK)
               * 400 (wrong attributes data specified |
                      cluster doesn't accept vmware configuration)
               * 403 (attributes can't be changed)
               * 404 (cluster not found in db |
                      cluster has no vmware attributes)
        """
        cluster = self.get_object_or_404(
            objects.Cluster, cluster_id,
            log_404=(
                "error",
                "There is no cluster "
                "with id '{0}' in DB.".format(cluster_id)
            )
        )
        if not objects.Cluster.is_vmware_enabled(cluster):
            raise self.http(400, "Cluster doesn't support vmware "
                                 "configuration")

        attributes = objects.Cluster.get_vmware_attributes(cluster)
        if not attributes:
            raise self.http(404, "No vmware attributes found")

        if cluster.is_locked and \
                not objects.Cluster.has_compute_vmware_changes(cluster):
            raise self.http(403, "Environment attributes can't be changed "
                                 "after or during deployment.")

        data = self.checked_data(instance=attributes)
        attributes = objects.Cluster.update_vmware_attributes(cluster, data)

        return {"editable": attributes}


class VmwareAttributesDefaultsHandler(BaseHandler):
    """Vmware default attributes handler"""

    @content
    def GET(self, cluster_id):
        """:returns: JSONized default Cluster vmware attributes.

        :http: * 200 (OK)
               * 400 (cluster doesn't accept vmware configuration)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(
            objects.Cluster, cluster_id,
            log_404=(
                "error",
                "There is no cluster "
                "with id '{0}' in DB.".format(cluster_id)
            )
        )
        if not objects.Cluster.is_vmware_enabled(cluster):
            raise self.http(400, "Cluster doesn't support vmware "
                                 "configuration")

        attributes = objects.Cluster.get_default_vmware_attributes(cluster)

        return {"editable": attributes}


class ClusterExtensionsHandler(BaseHandler):
    """Cluster extensions handler"""

    validator = ExtensionValidator

    def _get_cluster_obj(self, cluster_id):
        return self.get_object_or_404(
            objects.Cluster, cluster_id,
            log_404=(
                "error",
                "There is no cluster with id '{0}' in DB.".format(cluster_id)
            )
        )

    @content
    def GET(self, cluster_id):
        """:returns: JSONized list of enabled Cluster extensions

        :http: * 200 (OK)
               * 404 (cluster not found in db)
        """
        cluster = self._get_cluster_obj(cluster_id)
        return cluster.extensions

    @content
    def PUT(self, cluster_id):
        """:returns: JSONized list of enabled Cluster extensions

        :http: * 200 (OK)
               * 400 (there is no such extension available)
               * 404 (cluster not found in db)
        """
        cluster = self._get_cluster_obj(cluster_id)
        data = self.checked_data()
        set_extensions_for_object(cluster, data)
        return cluster.extensions
