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
from nailgun.api.v1.validators.json_schema import ip_addr
from nailgun.errors import errors
from nailgun.objects import IPAddrCollection


class IPAddrValidator(BasicValidator):
    single_schema = ip_addr.IP_ADDR_UPDATE_SCHEMA
    collection_schema = ip_addr.IP_ADDRS_UPDATE_SCHEMA

    @classmethod
    def validate_collection_update(cls, data, cluster_id=None):
        data_to_update = cls.validate_json(data)
        existing_vips = IPAddrCollection.get_vips_by_cluster_id(cluster_id)
        existing_vips_id = set(vip.id for vip in existing_vips)

        records_with_no_id = [
            record for record in data_to_update if not record.get('id')]
        if records_with_no_id:
            raise errors.InvalidData(
                "The following records have no 'id' field:\n{0}".format(
                    "\n".join(jsonutils.dumps(r) for r in records_with_no_id)
                )
            )

        ids_to_update = set(record.get('id') for record in data_to_update)
        not_found_ids = ids_to_update.difference(existing_vips_id)

        if not_found_ids:
            raise errors.InvalidData(
                "IP addresses with ID(s) {0} were not found in "
                "cluster {1}".format(not_found_ids, cluster_id)
            )

        return data_to_update
