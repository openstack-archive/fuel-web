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

import datetime

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun import objects
from nailgun.objects.serializers.oswl import OpenStackWorkloadStatsSerializer
from nailgun.settings import settings


class OpenStackWorkloadStats(objects.NailgunObject):

    #: SQLAlchemy model for OpenStackWorkloadStats
    model = models.OpenStackWorkloadStats

    #: Serializer for OpenStackWorkloadStats
    serializer = OpenStackWorkloadStatsSerializer

    @classmethod
    def get_last_by(cls, cluster_id, resource_type):
        """Get last entry by cluster_id and resource type.
        """
        instance = db().query(models.OpenStackWorkloadStats) \
            .order_by(models.OpenStackWorkloadStats.created_date.desc()) \
            .filter_by(cluster_id=cluster_id) \
            .filter_by(resource_type=resource_type) \
            .first()

        return instance


class OpenStackWorkloadStatsCollection(objects.NailgunCollection):
    single = OpenStackWorkloadStats

    @classmethod
    def get_ready_to_send(cls):
        """Get entries which are ready to send but were not sent yet.
        """
        last_date = datetime.datetime.utcnow().date() - \
            datetime.timedelta(days=settings.OSWL_COLLECT_PERIOD)
        instance = db().query(models.OpenStackWorkloadStats) \
            .filter_by(is_sent=False) \
            .filter(models.OpenStackWorkloadStats.created_date <= last_date)

        return instance

    @classmethod
    def clean_expired_entries(cls):
        """Delete expired oswl entries from db
        """
        # CAVEAT(aroma): if settings.OSWL_COLLECT_PERIOD is 0
        # then all oswl entries will be deleted from db
        last_date = datetime.datetime.utcnow().date() - \
            datetime.timedelta(days=settings.OSWL_STORING_PERIOD)
        instances = db().query(models.OpenStackWorkloadStats) \
            .filter(models.OpenStackWorkloadStats.created_date <= last_date)

        return instances.delete(synchronize_session=False)

    @classmethod
    def get_last_by_resource_type(cls, resource_type):
        """Get records for given resource_type which have most recent
        created_date (today or yesterday). Records (for some clusters)
        which were updated earlier will not be selected.
        """
        instances = db().query(models.OpenStackWorkloadStats) \
            .order_by(models.OpenStackWorkloadStats.created_date.desc()) \
            .filter_by(resource_type=resource_type)
        if instances.count():
            date = instances.first().created_date
            return instances.filter(
                models.OpenStackWorkloadStats.created_date == date)
        return instances
