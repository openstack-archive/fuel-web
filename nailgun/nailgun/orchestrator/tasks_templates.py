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


def make_repo_task(uids, repo_data, repo_path):
    return {
        'type': 'upload_file',
        'uids': uids,
        'parameters': {
            'path': repo_path,
            'data': repo_data}}


def make_ubuntu_repo_task(plugin_name, repo_url, uids):
    repo_data = 'deb {0} /'.format(repo_url)
    repo_path = '/etc/apt/sources.list.d/{0}.list'.format(plugin_name)

    return make_repo_task(uids, repo_data, repo_path)


def make_centos_repo_task(plugin_name, repo_url, uids):
    repo_data = '\n'.join([
        '[{0}]',
        'name=Plugin {0} repository',
        'baseurl={1}',
        'gpgcheck=0']).format(plugin_name, repo_url)
    repo_path = '/etc/yum.repos.d/{0}.repo'.format(plugin_name)

    return make_repo_task(uids, repo_data, repo_path)


def make_sync_scripts_task(uids, src, dst):
    return {
        'type': 'sync',
        'uids': uids,
        'parameters': {
            'src': src,
            'dst': dst}}


def make_shell_task(uids, task, cwd='/'):
    return {
        'type': 'shell',
        'uids': uids,
        'parameters': {
            'cmd': task['parameters']['cmd'],
            'timeout': task['parameters']['timeout'],
            'cwd': cwd}}


def make_apt_update_task(uids):
    task = {
        'parameters': {
            'cmd': 'apt-get update',
            'timeout': 180}}
    return make_shell_task(uids, task, '/')


def make_puppet_task(uids, task, cwd='/'):
    return {
        'type': 'puppet',
        'uids': uids,
        'parameters': {
            'puppet_manifest': task['parameters']['puppet_manifest'],
            'puppet_modules': task['parameters']['puppet_modules'],
            'timeout': task['parameters']['timeout'],
            'cwd': cwd}}
