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


from datetime import datetime

from nailgun import objects


def _added(time, prev, curr):
    prev_ids = set([res['id'] for res in prev])
    curr_ids = set([res['id'] for res in curr])
    added_ids = curr_ids - prev_ids
    return dict([(res['id'], {'time': time})
                 for res in curr if res['id'] in added_ids])


def _removed(time, prev, curr):
    prev_ids = set([res['id'] for res in prev])
    curr_ids = set([res['id'] for res in curr])
    removed_ids = prev_ids - curr_ids
    removed_data = {}
    for res in prev:
        if res['id'] in removed_ids:
            removed_data[res['id']] = res
            removed_data[res['id']]['time'] = time
    return removed_data


def _modified(time, prev, curr):
    prev_dict = dict([(res['id'], res) for res in prev])
    curr_dict = dict([(res['id'], res) for res in curr])
    same = set(prev_dict.keys()) & set(curr_dict.keys())
    modified_data = []
    for id in same:
        if curr_dict[id] != prev_dict[id]:
            m = curr_dict[id]
            m['time'] = time
            modified_data.append(m)
    return modified_data


def _checksum(data):
    return ""


def oswl_statistics_save(cluster_id, resource_type, data):
    """Save OSWL statistics data for given cluster and resource_type to DB.
    DB changes are not commited here.
    """
    dt = datetime.utcnow()
    rec = objects.OpenStackWorkloadStats.get_last_by_cluster_id_resource_type(
        cluster_id, resource_type)
    if rec:
        cs = _checksum(data)
        if cs == rec.resource_current_checksum:
            return
        obj_data = {
            'update_time': dt.time(),

            'resource_data_added': _added(
                dt.time(), rec.resource_data_current, data),
            'resource_data_removed': _removed(
                dt.time(), rec.resource_data_current, data),
            'resource_data_modified': _modified(
                dt.time(), rec.resource_data_current, data),
            'resource_data_current': data,
            'resource_current_checksum': cs
        }
        if rec.creation_date == dt.date():
            # update record
            obj_data['resource_data_added'].update(rec.resource_data_added)
            obj_data['resource_data_removed'].update(rec.resource_data_removed)
            obj_data['resource_data_modified'].extend(
                rec.resource_data_modified)
            objects.OpenStackWorkloadStats.update(rec, obj_data)
        else:
            # create new record
            obj_data.update({
                'cluster_id': cluster_id,
                'resource_type': resource_type,
                'creation_date': dt.date()
            })
            objects.OpenStackWorkloadStats.create(obj_data)
    else:
        obj_data = {
            'cluster_id': cluster_id,
            'resource_type': resource_type,

            'creation_date': dt.date(),
            'update_time': dt.time(),

            'resource_data_added': _added(dt.time(), [], data),
            'resource_data_current': data,
            'resource_current_checksum': _checksum(data)
        }
        objects.OpenStackWorkloadStats.create(obj_data)
