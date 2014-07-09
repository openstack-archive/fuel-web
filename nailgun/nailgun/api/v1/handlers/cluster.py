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
from nailgun.api.v1.handlers.base import DeferredTaskHandler

from nailgun.api.v1.handlers.base import CollectionHandler
from nailgun.api.v1.handlers.base import SingleHandler

from nailgun import objects

from nailgun.api.v1.handlers.base import content_json

from nailgun.api.v1.validators.cluster import AttributesValidator
from nailgun.api.v1.validators.cluster import ClusterValidator
from nailgun.logger import logger
from nailgun.task.manager import ApplyChangesTaskManager
from nailgun.task.manager import ClusterDeletionManager
from nailgun.task.manager import ResetEnvironmentTaskManager
from nailgun.task.manager import StopDeploymentTaskManager
from nailgun.task.manager import UpdateEnvironmentTaskManager
from nailgun import utils


class ClusterHandler(SingleHandler):
    """Cluster single handler
    """

    single = objects.Cluster
    validator = ClusterValidator

    @content_json
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
    """Cluster collection handler
    """

    collection = objects.ClusterCollection
    validator = ClusterValidator


class ClusterChangesHandler(DeferredTaskHandler):

    log_message = u"Trying to start deployment at environment '{env_id}'"
    log_error = u"Error during execution of deployment " \
                u"task on environment '{env_id}': {error}"
    task_manager = ApplyChangesTaskManager


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
    """Cluster attributes handler
    """

    fields = (
        "editable",
    )

    validator = AttributesValidator

    @content_json
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
            "editable": cluster.attributes.editable
        }

    @content_json
    def PUT(self, cluster_id):
        """:returns: JSONized Cluster attributes.
        :http: * 200 (OK)
               * 400 (wrong attributes data specified)
               * 404 (cluster not found in db)
               * 500 (cluster has no attributes)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        if not cluster.attributes:
            raise self.http(500, "No attributes found!")

        if cluster.is_locked:
            raise self.http(403, "Environment attributes can't be changed "
                                 "after, or in deploy.")

        data = self.checked_data()

        for key, value in data.iteritems():
            setattr(cluster.attributes, key, value)

        objects.Cluster.add_pending_changes(cluster, "attributes")
        return {"editable": cluster.attributes.editable}

    @content_json
    def PATCH(self, cluster_id):
        """:returns: JSONized Cluster attributes.
        :http: * 200 (OK)
               * 400 (wrong attributes data specified)
               * 404 (cluster not found in db)
               * 500 (cluster has no attributes)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)

        if not cluster.attributes:
            raise self.http(500, "No attributes found!")

        if cluster.is_locked:
            raise self.http(403, "Environment attributes can't be changed "
                                 "after, or in deploy.")

        data = self.checked_data()

        cluster.attributes.editable = utils.dict_merge(
            cluster.attributes.editable, data['editable'])

        objects.Cluster.add_pending_changes(cluster, "attributes")
        return {"editable": cluster.attributes.editable}


class ClusterAttributesDefaultsHandler(BaseHandler):
    """Cluster default attributes handler
    """

    fields = (
        "editable",
    )

    @content_json
    def GET(self, cluster_id):
        """:returns: JSONized default Cluster attributes.
        :http: * 200 (OK)
               * 404 (cluster not found in db)
               * 500 (cluster has no attributes)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        attrs = cluster.release.attributes_metadata.get("editable")
        if not attrs:
            raise self.http(500, "No attributes found!")
        return {"editable": attrs}

    @content_json
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
                "warning",
                "Error: there is no cluster "
                "with id '{0}' in DB.".format(cluster_id)
            )
        )

        if not cluster.attributes:
            logger.error('ClusterAttributesDefaultsHandler: no attributes'
                         ' found for cluster_id %s' % cluster_id)
            raise self.http(500, "No attributes found!")

        cluster.attributes.editable = cluster.release.attributes_metadata.get(
            "editable"
        )
        objects.Cluster.add_pending_changes(cluster, "attributes")

        logger.debug('ClusterAttributesDefaultsHandler:'
                     ' editable attributes for cluster_id %s were reset'
                     ' to default' % cluster_id)
        return {"editable": cluster.attributes.editable}


class ClusterGeneratedData(BaseHandler):
    """Cluster generated data
    """

    @content_json
    def GET(self, cluster_id):
        """:returns: JSONized cluster generated data
        :http: * 200 (OK)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        return cluster.attributes.generated
