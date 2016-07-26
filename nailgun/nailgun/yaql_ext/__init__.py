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

from nailgun import extensions
from nailgun.settings import settings
from nailgun.yaql_ext import datadiff
from nailgun.yaql_ext import serializers

_global_engine = None


def create_context(add_serializers=False, add_datadiff=False,
                   add_extensions=False,  **kwargs):
    context = yaql.create_context(**kwargs)
    if add_serializers:
        serializers.register(context)
    if add_datadiff:
        datadiff.register(context)
    if add_extensions:
        extensions.setup_yaql_context(context)
    return context


def get_default_engine():
    """Gets the default yaql engine.

    NOTE: do not share default engine between threads(processes).
    """
    global _global_engine
    if _global_engine is None:
        _global_engine = create_engine()
    return _global_engine


def create_engine(limit_iterators=None, memory_quota=None):
    """Creates a new yaql engine instance."""
    if not limit_iterators:
        limit_iterators = settings.YAQL_LIMIT_ITERATORS or 10000
    if not memory_quota:
        memory_quota = settings.YAQL_MEMORY_QUOTA or 100 * 1024 * 1024
    engine_options = {
        'yaql.limitIterators': limit_iterators,
        'yaql.memoryQuota': memory_quota,
        'yaql.convertTuplesToLists': True,
        'yaql.convertSetsToLists': True
    }

    return yaql.YaqlFactory().create(engine_options)
