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
import hashlib
import json
import six

from nailgun import objects


def _added(time, prev, curr, collected):
    prev_ids = set(res['id'] for res in prev)
    curr_ids = set(res['id'] for res in curr)
    added_ids = curr_ids - prev_ids
    for id_val in added_ids:
        collected.append({'id': id_val, 'time': time.isoformat()})
    return collected


def _removed(time, prev, curr, collected):
    prev_ids = set(res['id'] for res in prev)
    curr_ids = set(res['id'] for res in curr)
    collected_ids = set(res['id'] for res in collected)
    removed_ids = prev_ids - curr_ids
    for res in prev:
        id_val = res['id']
        if id_val in removed_ids:
            # If we already have resource collected only id with removal
            # time will be saved. In case of set of removals current state
            # of removed resource can be restored by data in 'removed',
            # 'added', 'modified'
            if id_val in collected_ids:
                collected.append({'id': id_val, 'time': time.isoformat()})
            else:
                res_data = dict(res, **{'time': time.isoformat()})
                collected.append(res_data)
    return collected


def _modified(time, prev, curr, collected):
    prev_dict = dict((res['id'], res) for res in prev)
    curr_dict = dict((res['id'], res) for res in curr)
    same = set(prev_dict.keys()) & set(curr_dict.keys())
    for id_val in same:
        if curr_dict[id_val] != prev_dict[id_val]:
            m = dict((k, v)
                     for k, v in six.iteritems(prev_dict[id_val])
                     if v != curr_dict[id_val].get(k))
            m['time'] = time.isoformat()
            m['id'] = id_val
            collected.append(m)
    return collected


def oswl_data_checksum(data):
    return hashlib.sha1(json.dumps(data)).hexdigest()


def oswl_statistics_save(cluster_id, resource_type, data, version_info=None):
    """Save OSWL statistics data for given cluster and resource_type to DB.

    DB changes are not committed here.
    """
    dt = datetime.utcnow()
    rec = objects.OpenStackWorkloadStats.get_last_by(
        cluster_id, resource_type)
    cs = oswl_data_checksum(data)
    obj_data = {
        'updated_time': dt.time(),
        'resource_data': {'current': data},
        'resource_checksum': cs
    }
    if version_info is not None:
        obj_data['version_info'] = version_info

    if rec:
        if cs == rec.resource_checksum:
            return
        last_dict = rec.resource_data
        cur_dict = last_dict['current']
        if rec.created_date == dt.date():
            # update record
            obj_data['resource_data'].update({
                'added': _added(
                    dt.time(), cur_dict, data, last_dict['added']),
                'removed': _removed(
                    dt.time(), cur_dict, data, last_dict['removed']),
                'modified': _modified(
                    dt.time(), cur_dict, data, last_dict['modified'])
            })
            rec.is_sent = False
            objects.OpenStackWorkloadStats.update(rec, obj_data)
        else:
            # create new record
            obj_data.update({
                'cluster_id': cluster_id,
                'resource_type': resource_type,
                'created_date': dt.date()
            })
            obj_data['resource_data'].update({
                'added': _added(dt.time(), cur_dict, data, []),
                'removed': _removed(dt.time(), cur_dict, data, []),
                'modified': _modified(dt.time(), cur_dict, data, [])
            })
            objects.OpenStackWorkloadStats.create(obj_data)
    else:
        # it will be the first record
        obj_data.update({
            'cluster_id': cluster_id,
            'resource_type': resource_type,
            'created_date': dt.date()
        })
        obj_data['resource_data'].update({
            'added': _added(dt.time(), [], data, []),
            'removed': [],
            'modified': []
        })
        objects.OpenStackWorkloadStats.create(obj_data)
