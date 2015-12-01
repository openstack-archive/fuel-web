# -*- coding: utf-8 -*-

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

from nailgun.db.sqlalchemy import models

from nailgun.db import db
from nailgun.db.sqlalchemy.models import network as network_db_model
from nailgun.objects import base
from nailgun.objects.serializers import vip as vip_serializer


class VIP(base.NailgunObject):
    serializer = vip_serializer.VIPSerializer
    model = network_db_model.IPAddr

    @classmethod
    def delete(cls, instance):
        """Delete object (model) instance

        :param instance: object (model) instance
        :returns: None
        """
        instance.update({"vip_info": None})
        db().add(instance)
        db().flush()

    @classmethod
    def update(cls, instance, data):
        """Delete object (model) instance

        :param instance: object (model) instance
        :returns: None
        """
        vip_info = instance.vip_info
        vip_info.update(data)
        instance.update({"vip_info": vip_info})
        db().add(instance)
        db().flush()
        return instance


class VIPCollection(base.NailgunCollection):
    single = VIP

    @classmethod
    def get_by_cluster_id(cls, cluster_id):
        q = cls.all()
        if cluster_id is not None:
            q = q.join(models.NetworkGroup)\
                .join(models.NetworkGroup)\
                .join(models.NodeGroup)\
                .filter(
                    models.NodeGroup.cluster_id == cluster_id,
                )
        return q
