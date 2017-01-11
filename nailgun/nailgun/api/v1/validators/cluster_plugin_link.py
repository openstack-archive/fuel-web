#    Copyright 2016 Mirantis, Inc.
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

from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema import plugin_link
from nailgun import errors
from nailgun import objects


class ClusterPluginLinkValidator(BasicValidator):
    collection_schema = plugin_link.PLUGIN_LINKS_SCHEMA

    @classmethod
    def validate(cls, data, **kwargs):
        parsed = super(ClusterPluginLinkValidator, cls).validate(data)
        cls.validate_schema(parsed, plugin_link.PLUGIN_LINK_SCHEMA)
        if objects.ClusterPluginLinkCollection.filter_by(
            None,
            url=parsed['url'],
            cluster_id=kwargs['cluster_id']
        ).first():
            raise errors.AlreadyExists(
                "Cluster plugin link with URL {0} and cluster ID={1} already "
                "exists".format(parsed['url'], kwargs['cluster_id']),
                log_message=True)
        return parsed

    @classmethod
    def validate_update(cls, data, instance):
        parsed = super(ClusterPluginLinkValidator, cls).validate(data)
        cls.validate_schema(parsed, plugin_link.PLUGIN_LINK_UPDATE_SCHEMA)
        cluster_id = parsed.get('cluster_id', instance.cluster_id)
        if objects.ClusterPluginLinkCollection.filter_by_not(
            objects.ClusterPluginLinkCollection.filter_by(
                None,
                url=parsed.get('url', instance.url),
                cluster_id=cluster_id,
            ),
            id=instance.id
        ).first():
            raise errors.AlreadyExists(
                "Cluster plugin link with URL {0} and cluster ID={1} already "
                "exists".format(parsed['url'], cluster_id),
                log_message=True)
        return parsed
