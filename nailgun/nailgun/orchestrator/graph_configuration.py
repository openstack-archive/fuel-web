# -*- coding: utf-8 -*-

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

#(dshulyak) temporary, this config will be moved to fuel-library
#until we will stabilize our api
DEPLOYMENT_CURRENT = """
- id: deploy
  type: stage
- id: primary-controller
  type: group
  role: [primary-controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: controller
  type: group
  role: [controller]
  requires: [primary-controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: parallel
      amount: 6
- id: cinder
  type: group
  role: [cinder]
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: parallel
- id: compute
  type: group
  role: [compute]
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: parallel
- id: zabbix-server
  type: group
  role: [zabbix-server]
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: mongo
  type: group
  role: [mongo]
  requires: [zabbix-server]
  required_for: [deploy, primary-controller, controller]
  parameters:
    strategy:
      type: parallel
- id: primary-mongo
  type: group
  role: [primary-mongo]
  requires: [mongo]
  required_for: [deploy, primary-controller, controller]
  parameters:
    strategy:
      type: one_by_one
- id: ceph-osd
  type: group
  role: [ceph-osd]
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: parallel
- id: base-os
  type: group
  role: [base-os]
  required_for: [deploy]
  parameters:
    strategy:
      type: parallel
- id: deploy_legacy
  type: puppet
  groups: [primary-controller, controller,
           cinder, compute, ceph-osd,
           zabbix-server, primary-mongo, mongo]
  required_for: [deploy]
  parameters:
    puppet_manifest: /etc/puppet/manifests/site.pp
    puppet_modules: /etc/puppet/modules
    timeout: 3600
"""

DEPLOYMENT_50 = """
- id: deploy
  type: stage
- id: primary-controller
  type: group
  role: [primary-controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: controller
  type: group
  role: [controller]
  requires: [primary-controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: cinder
  type: group
  role: [cinder]
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: parallel
- id: compute
  type: group
  role: [compute]
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: parallel
- id: zabbix-server
  type: group
  role: [zabbix-server]
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: mongo
  type: group
  role: [mongo]
  requires: [zabbix-server]
  required_for: [deploy, primary-controller, controller]
  parameters:
    strategy:
      type: one_by_one
- id: primary-mongo
  type: group
  role: [primary-mongo]
  requires: [mongo]
  required_for: [deploy, primary-controller, controller]
  parameters:
    strategy:
      type: one_by_one
- id: ceph-osd
  type: group
  role: [ceph-osd]
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: parallel
- id: deploy_legacy
  type: puppet
  groups: [primary-controller, controller,
           cinder, compute, ceph-osd,
           zabbix-server, primary-mongo, mongo]
  required_for: [deploy]
  parameters:
    puppet_manifest: /etc/puppet/manifests/site.pp
    puppet_modules: /etc/puppet/modules
    timeout: 3600
"""

PATCHING = """
- id: deploy
  type: stage
- id: primary-controller
  type: group
  role: [primary-controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: controller
  type: group
  role: [controller]
  requires: [primary-controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: cinder
  type: group
  role: [cinder]
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: compute
  type: group
  role: [compute]
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: zabbix-server
  type: group
  role: [zabbix-server]
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: mongo
  type: group
  role: [mongo]
  requires: [zabbix-server]
  required_for: [deploy, primary-controller, controller]
  parameters:
    strategy:
      type: one_by_one
- id: primary-mongo
  type: group
  role: [primary-mongo]
  requires: [mongo]
  required_for: [deploy, primary-controller, controller]
  parameters:
    strategy:
      type: one_by_one
- id: ceph-osd
  type: group
  role: [ceph-osd]
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: deploy_legacy
  type: puppet
  groups: [primary-controller, controller,
           cinder, compute, ceph-osd,
           zabbix-server, primary-mongo, mongo]
  required_for: [deploy]
  parameters:
    puppet_manifest: /etc/puppet/manifests/site.pp
    puppet_modules: /etc/puppet/modules
    timeout: 3600
"""
