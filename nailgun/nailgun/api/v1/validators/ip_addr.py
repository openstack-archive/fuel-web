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
import six

from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema import ip_addr
from nailgun.errors import errors
from nailgun.objects import IPAddrCollection


class IPAddrValidator(BasicValidator):
    single_schema = ip_addr.IP_ADDR_UPDATE_SCHEMA
    collection_schema = ip_addr.IP_ADDRS_UPDATE_SCHEMA
    updatable_fields = (
        "ip_addr",
        "is_user_defined",
    )

    @classmethod
    def validate_collection_update(cls, data, cluster_id=None):
        error_messages = []
        data_to_update = cls.validate_json(data)

        # check id field presence
        records_with_no_id = [
            record for record in data_to_update if record.get("id") is None
        ]

        if records_with_no_id:
            error_messages.extend(
                ["The following records have no 'id' field:"] +
                [jsonutils.dumps(r) for r in records_with_no_id]
            )

        # check id existence
        existing_data_by_id = {
            vip.id: dict(vip)
            for vip in IPAddrCollection.get_vips_by_cluster_id(cluster_id)
        }
        new_data_by_id = {
            vip.get('id'): vip
            for vip in data_to_update
            if vip.get('id') is not None
        }

        not_found_ids = set(new_data_by_id.keys()).difference(
            set(existing_data_by_id.keys())
        )

        if not_found_ids:
            error_messages.append(
                "IP addresses with ID(s) {0} were not found in "
                "cluster {1}".format(list(not_found_ids), cluster_id)
            )

        # check fields
        for id, new_data in six.iteritems(new_data_by_id):
            bad_fields = []
            if id not in existing_data_by_id:
                continue
            for field, value in six.iteritems(new_data):
                old_value = existing_data_by_id[id].get(field)
                # field that not allowed to be changed is changed
                if value != old_value and field not in cls.updatable_fields:
                    bad_fields.append(field)

            if bad_fields:
                bad_fields_verbose = ", ".join(
                    "'{0}'".format(bf) for bf in bad_fields
                )
                error_messages.extend([
                    "The following fields: {0} are not allowed to be "
                    "updated for record:".format(bad_fields_verbose),
                    jsonutils.dumps(new_data),
                ])

        if error_messages:
            raise errors.InvalidData("\n".join(error_messages))

        return data_to_update
