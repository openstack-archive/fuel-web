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

from oslo_serialization import jsonutils

from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema import ip_address
from nailgun.errors import errors
from nailgun.objects import IPAddressCollection


class IPAddressValidator(BasicValidator):
    single_schema = ip_address.IP_ADDRESS_WITH_VIP_UPDATE_SCHEMA
    collection_schema = ip_address.IP_ADDRESSES_UPDATE_SCHEMA

    @classmethod
    def validate_collection_update(cls, data, cluster_id=None):
        data_to_update = cls.validate_json(data)
        existing_vips = IPAddressCollection.get_vips_by_cluster_id(cluster_id)
        existing_vips_id = set(vip.id for vip in existing_vips)

        records_with_no_id = [
            record for record in data_to_update if not record.get('id')]
        if records_with_no_id:
            raise errors.InvalidData(
                "{0} record{1} have no 'id' field:\n{2}".format(
                    len(records_with_no_id),
                    "s" if len(records_with_no_id) > 1 else "",
                    "\n".join(jsonutils.dumps(r) for r in records_with_no_id)
                )
            )

        not_found_id = [
            record.get('id') for record in data_to_update
            if record.get('id') not in existing_vips_id]
        if not_found_id:
            raise errors.InvalidData(
                "IP address{0} with id{1} {2} not found in "
                "cluster (ID={3})".format(
                    "es" if len(not_found_id) > 1 else "",
                    "s" if len(not_found_id) > 1 else "",
                    not_found_id,
                    cluster_id
                )
            )

        return data_to_update
