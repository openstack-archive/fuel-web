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

import netaddr
import six
import sqlalchemy.types as types

from nailgun.openstack.common import jsonutils


class JSON(types.TypeDecorator):

    impl = types.Text

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = jsonutils.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = jsonutils.loads(value)
        return value


class LowercaseString(types.TypeDecorator):

    impl = types.String

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return value.lower()


class EUIEncodedString(types.TypeDecorator):
    """Type serialized as EUI-encoded string in db."""

    # TODO(romcheg): Network address is naturally a number so
    #                there is no need to store it as a string.
    impl = types.TEXT

    def process_bind_param(self, value, dialect):
        if value is None:
            raise ValueError('Hardware address cannot be None.')

        # Validate and save value if it is already a string.
        # TODO(romcheg): this should be removed after fixture
        # manager knows how to upload correct data to the DB
        if isinstance(value, six.string_types) or isinstance(value, six.text_type):
            # NOTE(romcheg): This validation should also support
            # other kinds of hardware addresses. This should be done
            # in one of the following patches. However, netaddr
            # should be patched for supporting addresses other than
            # IEEE EUI-48 and IEEE EUI-64, e.g., hw addreses for
            # IP over Infiniband or IP over Fibre channel interfaces.
            if not netaddr.valid_mac(value):
                raise ValueError('The value is not a valid mac address')

            return value
        elif isinstance(value, netaddr.EUI):
            value.dialect=netaddr.mac_unix
            return str(value)
        else:
            raise ValueError('The value shoud be either a string or '
                             'a netaddr.EUI object.')

    def process_result_value(self, value, dialect):
        if value is None:
            raise ValueError('Hardware address cannot be None.')

        try:
            value = netaddr.EUI(value, dialect=netaddr.mac_unix)
        except netaddr.AddrFormatError as e:
            raise ValueError('%s is not a valid hardware address.')

        return value

class NodeMetaData(JSON):
    """JSON-encoded metadata

    Hooks specific values like hardware addresses from
    the metadata and converts them to correct format.

    """
    def process_result_value(self, value, dialect):
        value = super(NodeMetaData, self).process_result_value(value, dialect)

        if 'interfaces' in value:
            for i in value['interfaces']:
                i['mac'] = netaddr.EUI(i['mac'], dialect=netaddr.mac_unix)

        return value
