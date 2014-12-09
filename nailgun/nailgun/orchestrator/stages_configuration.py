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

"""
NOTE(dshulyak)
We need to store configuration for predeployment tasks and postdeployment
tasks in nailgun for several reasons:
1. Compatibility for old releases.
2. Example for testing and development purposes
3. We need to be able to modify most of them (based on mask)

Why they are different from graph_configuratin approach:
- Currently all stages is hardcoded, we have plans to make them configurable
and probably get rid from entity stage at all

"""

PRE_DEPLOYMENT_TASKS = """
#after we will introduce condition engine - it will be changed
- id: upload_mos_repos
  type: upload_file
  role: '*'
  stage: predeployment

- id: rsync_mos_puppet
  type: sync
  role: '*'
  stage: predeployment
  parameters:
    src: /etc/puppet/{OPENSTACK_VERSION}/
    dst: /etc/puppet
    timeout: 180
"""
