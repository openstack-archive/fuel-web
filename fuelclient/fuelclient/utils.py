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

import six


def get_display_data(fields, data):
    """Performs slice of data by set of given fields

    params:
        fields: iterable containing names of fields to be retrieved from data
        data: collection of JSON objects representing some external entities

        returns: iterable with collections of values corresponding to fields
        param
    """
    return ([elem[field] for field in fields] for elem in data)


def update_entity_attributes(entity, attributes_to_update,
                             attributes_to_filter):
    """Updated given entity with params which was made as slice of
    `attributes_to_filter` data holder by `attributes_to_update` param


    :param entity: object to be processed
    :param attributes_to_update: iterable containing names of attributes
         to be retrieved from attributes_to_filter param
    :param attributes_to_filter: dict with attributes names and its values

    :return: data that was return after updated operation on `enitity`
    """
    update_kwargs = dict()
    for attr_name, attr_value in six.iteritems(attributes_to_filter):
        if attr_name in attributes_to_update:
            update_kwargs[attr_name] = attr_value

    data = entity.set(update_kwargs)
    return data
