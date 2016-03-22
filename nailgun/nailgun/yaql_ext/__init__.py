#    Copyright 2016 Mirantis, Inc.
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

import yaql

from nailgun.yaql_ext import datadiff
from nailgun.yaql_ext import serializers


LIMIT_ITERATORS = 5000

MEMORY_QUOTA = 20000

_global_engine = None


def create_context(add_serializers=False, add_datadiff=False, **kwargs):
    context = yaql.create_context(**kwargs)
    if add_serializers:
        serializers.register(context)
    if add_datadiff:
        datadiff.register(context)
    return context


def create_engine():
    global _global_engine

    engine_options = {
        'yaql.limitIterators': LIMIT_ITERATORS,
        'yaql.memoryQuota': MEMORY_QUOTA,
        'yaql.convertTuplesToLists': True,
        'yaql.convertSetsToLists': True
    }

    if _global_engine is None:
        _global_engine = yaql.YaqlFactory().create(engine_options)
    return _global_engine
