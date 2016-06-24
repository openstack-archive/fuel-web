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
import logging

from nailgun import extensions
from nailgun import objects
from nailgun.orchestrator.deployment_serializers import get_serializer_for_cluster


logger = logging.getLogger(__name__)


class ConvertPreLCMtoLCM(extensions.BasePipeline):

    @classmethod
    def pre_process_data(cls, data, cluster, nodes, **kwargs):
        return data

    @classmethod
    def post_process_data(cls, data, cluster, nodes, **kwargs):
        return data

    @classmethod
    def serialize(cls, data, cluster, nodes, **kwargs):
        if objects.Release.is_lcm_supported(cluster.release):
            return data
        serializer = get_serializer_for_cluster(cluster)()
        real_data = serializer.serialize(cluster, nodes, **kwargs)
        return real_data

    @classmethod
    def process_deployment(cls, data, cluster, nodes, **kwargs):
        pre_processed_data = cls.pre_process_data(data,
                                                  cluster, nodes, **kwargs)
        real_data = cls.serialize(pre_processed_data, cluster, nodes, **kwargs)
        post_processed_data = cls.post_process_data(real_data,
                                                    cluster, nodes, **kwargs)
        #copypaste cluster specific values from LCM serializer. This is needed
        # for tasks paramters interpolation like CLUSTER_ID
        cluster_data = data[0]['cluster']
        for node_data in post_processed_data:
            node_data['cluster'] = cluster_data
        return post_processed_data

    @classmethod
    def process_provisioning(cls, data, cluster, nodes, **kwargs):
        return data


class ConvertedSerializersExtension(extensions.BaseExtension):
    name = 'converted_serializers'
    version = '0.0.1'
    description = "Serializers Conversion extension"
    weight = 100

    data_pipelines = [
        ConvertPreLCMtoLCM,
    ]

    # urls = [
    #     {'uri': r'/clusters/(?P<cluster_id>\d+)/upgrade/clone/?$',
    #      'handler': handlers.ClusterUpgradeCloneHandler},
    #     {'uri': r'/clusters/(?P<cluster_id>\d+)/upgrade/assign/?$',
    #      'handler': handlers.NodeReassignHandler},
    #     {'uri': r'/clusters/(?P<cluster_id>\d+)/upgrade/vips/?$',
    #      'handler': handlers.CopyVIPsHandler},
    # ]
