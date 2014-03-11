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

import json
import traceback

from nailgun.api.handlers.base import BaseHandler
from nailgun.api.handlers.base import DeferredTaskHandler

from nailgun.api.handlers.base import content_json

from nailgun.api.validators.cluster import AttributesValidator
from nailgun.api.validators.cluster import ClusterValidator
from nailgun.db import db
from nailgun.db.sqlalchemy.models import Attributes
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import Release
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.task.manager import ApplyChangesTaskManager
from nailgun.task.manager import ClusterDeletionManager
from nailgun.task.manager import ResetEnvironmentTaskManager
from nailgun.task.manager import StopDeploymentTaskManager
from nailgun import utils


class ClusterHandler(BaseHandler):
    """Cluster single handler
    """

    fields = (
        "id",
        "name",
        "mode",
        "changes",
        "status",
        "grouping",
        "is_customized",
        "net_provider",
        "net_segment_type",
        "release_id"
    )

    model = Cluster
    validator = ClusterValidator

    @content_json
    def GET(self, cluster_id):
        """:returns: JSONized Cluster object.
        :http: * 200 (OK)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(Cluster, cluster_id)
        return self.render(cluster)

    @content_json
    def PUT(self, cluster_id):
        """:returns: JSONized Cluster object.
        :http: * 200 (OK)
               * 400 (invalid cluster data specified)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(Cluster, cluster_id)
        data = self.checked_data(cluster_id=cluster_id)
        network_manager = cluster.network_manager

        for key, value in data.iteritems():
            if key == "nodes":
                # TODO(NAME): sepatate nodes
                #for deletion and addition by set().
                new_nodes = db().query(Node).filter(
                    Node.id.in_(value)
                )
                nodes_to_remove = [n for n in cluster.nodes
                                   if n not in new_nodes]
                nodes_to_add = [n for n in new_nodes
                                if n not in cluster.nodes]
                for node in nodes_to_add:
                    if not node.online:
                        raise self.http(
                            400, "Can not add offline node to cluster"
                        )
                map(cluster.nodes.remove, nodes_to_remove)
                map(cluster.nodes.append, nodes_to_add)
                for node in nodes_to_remove:
                    network_manager.clear_assigned_networks(node)
                for node in nodes_to_add:
                    network_manager.assign_networks_by_default(node)
            else:
                setattr(cluster, key, value)
        db().commit()
        return self.render(cluster)

    @content_json
    def DELETE(self, cluster_id):
        """:returns: {}
        :http: * 202 (cluster deletion process launched)
               * 400 (failed to execute cluster deletion process)
               * 404 (cluster not found in db)
        """
        cluster = self.get_object_or_404(Cluster, cluster_id)
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


class ClusterCollectionHandler(BaseHandler):
    """Cluster collection handler
    """

    validator = ClusterValidator

    @content_json
    def GET(self):
        """:returns: Collection of JSONized Cluster objects.
        :http: * 200 (OK)
        """
        return map(
            ClusterHandler.render,
            db().query(Cluster).all()
        )

    @content_json
    def POST(self):
        """:returns: JSONized Cluster object.
        :http: * 201 (cluster successfully created)
               * 400 (invalid cluster data specified)
               * 409 (cluster with such parameters already exists)
        """
        # It's used for cluster creating only.
        data = self.checked_data()

        cluster = Cluster()
        cluster.release = db().query(Release).get(data["release"])
        # TODO(NAME): use fields
        for field in (
            "name",
            "mode",
            "net_provider",
            "net_segment_type",
            "status"
        ):
            if data.get(field):
                setattr(cluster, field, data.get(field))
        db().add(cluster)
        db().commit()
        attributes = Attributes(
            editable=cluster.release.attributes_metadata.get("editable"),
            generated=cluster.release.attributes_metadata.get("generated"),
            cluster=cluster
        )
        attributes.generate_fields()

        netmanager = cluster.network_manager

        try:
            netmanager.create_network_groups(cluster.id)
            if cluster.net_provider == 'neutron':
                netmanager.create_neutron_config(cluster)

            cluster.add_pending_changes("attributes")
            cluster.add_pending_changes("networks")

            if 'nodes' in data and data['nodes']:
                nodes = db().query(Node).filter(
                    Node.id.in_(data['nodes'])
                ).all()
                map(cluster.nodes.append, nodes)
                db().commit()
                for node in nodes:
                    netmanager.assign_networks_by_default(node)

            raise self.http(
                201, json.dumps(ClusterHandler.render(cluster), indent=4)
            )

        except (
            errors.OutOfVLANs,
            errors.OutOfIPs,
            errors.NoSuitableCIDR,
            errors.InvalidNetworkPool
        ) as e:
            # Cluster was created in this request,
            # so we no need to use ClusterDeletionManager.
            # All relations wiil be cascade deleted automaticly.
            # TODO(NAME): investigate transactions
            db().delete(cluster)

            raise self.http(400, e.message)


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
        cluster = self.get_object_or_404(Cluster, cluster_id)
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
        cluster = self.get_object_or_404(Cluster, cluster_id)
        if not cluster.attributes:
            raise self.http(500, "No attributes found!")

        if cluster.is_locked:
            raise self.http(403, "Environment attributes can't be changed "
                                 "after, or in deploy.")

        data = self.checked_data()

        for key, value in data.iteritems():
            setattr(cluster.attributes, key, value)

        cluster.add_pending_changes("attributes")
        db().commit()
        return {"editable": cluster.attributes.editable}

    @content_json
    def PATCH(self, cluster_id):
        """:returns: JSONized Cluster attributes.
        :http: * 200 (OK)
               * 400 (wrong attributes data specified)
               * 404 (cluster not found in db)
               * 500 (cluster has no attributes)
        """
        cluster = self.get_object_or_404(Cluster, cluster_id)

        if not cluster.attributes:
            raise self.http(500, "No attributes found!")

        if cluster.is_locked:
            raise self.http(403, "Environment attributes can't be changed "
                                 "after, or in deploy.")

        data = self.checked_data()

        cluster.attributes.editable = utils.dict_merge(
            cluster.attributes.editable, data['editable'])

        cluster.add_pending_changes("attributes")
        db().commit()
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
        cluster = self.get_object_or_404(Cluster, cluster_id)
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
            Cluster,
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
        db().commit()
        cluster.add_pending_changes("attributes")

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
        cluster = self.get_object_or_404(Cluster, cluster_id)
        return cluster.attributes.generated
