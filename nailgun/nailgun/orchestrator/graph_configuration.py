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
- id: pre_deployment
  type: stage
- id: post_deployment
  type: stage
- id: primary-controller
  type: role
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: controller
  type: role
  requires: [primary-controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: parallel
      amount: 6
- id: cinder
  type: role
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: parallel
- id: compute
  type: role
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: parallel
- id: zabbix-server
  type: role
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: mongo
  type: role
  requires: [zabbix-server]
  required_for: [deploy, primary-controller, controller]
  parameters:
    strategy:
      type: parallel
- id: primary-mongo
  type: role
  requires: [mongo]
  required_for: [deploy, primary-controller, controller]
  parameters:
    strategy:
      type: one_by_one
- id: ceph-osd
  type: role
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: parallel
- id: deploy_legacy
  type: puppet
  role: [primary-controller, controller,
         cinder, compute, ceph-osd,
         zabbix-server, primary-mongo, mongo]
  required_for: [deploy]
  parameters:
    puppet_manifest: /etc/puppet/manifests/site.pp
    puppet_modules: /etc/puppet/modules
    timeout: 3600

#PREDEPLOYMENT HOOKS

#after we will introduce condition engine - it will be changed
- id: upload_mos_repos
  type: upload_file
  role: '*'
  stage: pre_deployment

- id: rsync_mos_puppet
  type: sync
  role: '*'
  stage: pre_deployment
  requires: [upload_mos_repos]
  parameters:
    src: /etc/puppet/{OPENSTACK_VERSION}/
    dst: /etc/puppet
    timeout: 180
"""

DEPLOYMENT_50 = """
- id: deploy
  type: stage
- id: pre_deployment
  type: stage
- id: post_deployment
  type: stage
- id: primary-controller
  type: role
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: controller
  type: role
  requires: [primary-controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: cinder
  type: role
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: parallel
- id: compute
  type: role
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: parallel
- id: zabbix-server
  type: role
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: mongo
  type: role
  requires: [zabbix-server]
  required_for: [deploy, primary-controller, controller]
  parameters:
    strategy:
      type: one_by_one
- id: primary-mongo
  type: role
  requires: [mongo]
  required_for: [deploy, primary-controller, controller]
  parameters:
    strategy:
      type: one_by_one
- id: ceph-osd
  type: role
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: parallel
- id: deploy_legacy
  type: puppet
  role: [primary-controller, controller,
         cinder, compute, ceph-osd,
         zabbix-server, primary-mongo, mongo]
  required_for: [deploy]
  parameters:
    puppet_manifest: /etc/puppet/manifests/site.pp
    puppet_modules: /etc/puppet/modules
    timeout: 3600

#PREDEPLOYMENT HOOKS

#after we will introduce condition engine - it will be changed
- id: upload_mos_repos
  type: upload_file
  role: '*'
  stage: pre_deployment

- id: rsync_mos_puppet
  type: sync
  role: '*'
  stage: pre_deployment
  requires: [upload_mos_repos]
  parameters:
    src: /etc/puppet/{OPENSTACK_VERSION}/
    dst: /etc/puppet
    timeout: 180
"""

PATCHING = """
- id: deploy
  type: stage
- id: pre_deployment
  type: stage
- id: post_deployment
  type: stage
- id: primary-controller
  type: role
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: controller
  type: role
  requires: [primary-controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: cinder
  type: role
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: compute
  type: role
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: zabbix-server
  type: role
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: mongo
  type: role
  requires: [zabbix-server]
  required_for: [deploy, primary-controller, controller]
  parameters:
    strategy:
      type: one_by_one
- id: primary-mongo
  type: role
  requires: [mongo]
  required_for: [deploy, primary-controller, controller]
  parameters:
    strategy:
      type: one_by_one
- id: ceph-osd
  type: role
  requires: [controller]
  required_for: [deploy]
  parameters:
    strategy:
      type: one_by_one
- id: deploy_legacy
  type: puppet
  role: [primary-controller, controller,
         cinder, compute, ceph-osd,
         zabbix-server, primary-mongo, mongo]
  required_for: [deploy]
  parameters:
    puppet_manifest: /etc/puppet/manifests/site.pp
    puppet_modules: /etc/puppet/modules
    timeout: 3600

#PREDEPLOYMENT HOOKS

#after we will introduce condition engine - it will be changed
- id: upload_mos_repos
  type: upload_file
  role: '*'
  stage: pre_deployment

- id: rsync_mos_puppet
  type: sync
  role: '*'
  stage: pre_deployment
  requires: [upload_mos_repos]
  parameters:
    src: /etc/puppet/{OPENSTACK_VERSION}/
    dst: /etc/puppet
    timeout: 180
"""
