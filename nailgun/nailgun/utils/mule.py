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

# uwsgidecorators imports uwsgi which is a 'magical' module, available
# in a Python script only when you run it via uwsgi. So when we run tests,
# we do not do it via uwsgi and this code raises ImportError and later the
# task is called synchronously -- so it should work exactly as before.
try:
    import uwsgidecorators
except ImportError:
    uwsgidecorators = None

from nailgun.logger import logger


def call_task_manager_async(klass, func, cluster_id, *args, **kwargs):
    """This function calls a TaskManager's subclass 'klass' asynchronously.

    It instantiates a TaskManager instance with given cluster_id.
    This is because this call is made in a uWSGI mule -- we want to avoid
    passing any objects (like Cluster), just simple Python objects.

    :param klass: TaskManager's subclass
    :param func: name of function to be called
    :param cluster_id:
    :param args: Arguments to pass to the function
    :return:
    """
    if uwsgidecorators:
        logger.debug('MULE STARTING for %s.%s', klass.__name__, func)
    instance = klass(cluster_id=cluster_id)
    getattr(instance, func)(*args, **kwargs)
    if uwsgidecorators:
        logger.debug('MULE FINISHED for %s.%s', klass.__name__, func)

if uwsgidecorators:
    call_task_manager_async = uwsgidecorators.mulefunc(call_task_manager_async)
