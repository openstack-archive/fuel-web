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

import six

from oslo_serialization import jsonutils

from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema import ip_addr
from nailgun import consts
from nailgun.db.sqlalchemy import models
from nailgun.errors import errors
from nailgun import objects


class IPAddrValidator(BasicValidator):
    single_schema = ip_addr.IP_ADDR_UPDATE_SCHEMA
    collection_schema = ip_addr.IP_ADDRS_UPDATE_SCHEMA
    updatable_fields = (
        "ip_addr",
        "is_user_defined",
        "vip_namespace",
    )

    @classmethod
    def validate_update(cls, data, existing_obj):
        """Validate single IP address entry update information.

        :param data: new data
        :type data: dict
        :param existing_obj: existing object
        :type existing_obj: instance if fuel.objects.IPAddr
        :return: validated data
        :rtype: dict
        """
        if isinstance(data, six.string_types):
            data = cls.validate_json(data)

        existing_data = dict(existing_obj)

        bad_fields = []
        for field, value in six.iteritems(data):
            old_value = existing_data.get(field)
            # field that not allowed to be changed is changed
            if value != old_value and field not in cls.updatable_fields:
                bad_fields.append(field)

        if bad_fields:
            bad_fields_verbose = ", ".join(repr(bf) for bf in bad_fields)
            raise errors.InvalidData(
                "\n".join([
                    "The following fields: {0} are not allowed to be "
                    "updated for record: {1}".format(
                        bad_fields_verbose,
                        jsonutils.dumps(data)
                    )
                ])
            )

        # we have to check if user defined vip is not intersecting
        # with other ips from existing clusters
        if data.get('is_user_defined') and data.get('ip_addr'):
            cls._check_vip_addr_intersection(existing_obj,
                                             data['ip_addr'])

        return data

    @classmethod
    def _check_vip_addr_intersection(cls, ip_instance, addr):
        """Check intersection with ip addresses of existing clusters

        If ip address is being updated for a VIP manually its intersection
        with ips of all existing clusters must be checked

        :param obj_id: id of the VIP being updated
        :param addr: new ip address for VIP
        """
        intersecting_ip = objects.IPAddr.get_intersecting_ip(ip_instance, addr)
        if intersecting_ip:
            err_msg = (
                "IP address {0} is already allocated within "
                "{1} network with CIDR {2}"
                .format(addr,
                        intersecting_ip.network_data.name,
                        intersecting_ip.network_data.cidr)
            )
            raise errors.AlreadyExists(err_msg)

    @classmethod
    def validate_collection_update(cls, data, cluster_id):
        """Validate IP address collection update information.

        :param data: new data
        :type data: list(dict)
        :param cluster_id: if od objects.Cluster instance
        :type cluster_id: int
        :return: validated data
        :rtype: list(dict)
        """

        error_messages = []
        data_to_update = cls.validate_json(data)
        existing_instances = objects.IPAddrCollection.get_vips_by_cluster_id(
            cluster_id)

        for record in data_to_update:
            instance = existing_instances.filter(
                models.IPAddr.id == record.get('id')
            ).first()

            if instance:
                try:
                    cls.validate_update(record, instance)
                except errors.InvalidData as e:
                    error_messages.append(e.message)
            else:
                error_messages.append(
                    "IPAddr with (ID={0}) does not exist or does not "
                    "belong to cluster (ID={1})".format(
                        record.get('id'),
                        cluster_id
                    )
                )

        if error_messages:
            raise errors.InvalidData("\n".join(error_messages))

        return data_to_update
