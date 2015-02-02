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


def make_upload_task(uids, data, path):
    return {
        'type': 'upload_file',
        'uids': uids,
        'parameters': {
            'path': path,
            'data': data}}


def make_ubuntu_sources_task(meta, uids):
    sources_content = 'deb {uri} {suite} {section}'.format(**meta)
    sources_path = '/etc/apt/sources.list.d/{name}.list'.format(
        name=meta['name'])
    return make_upload_task(uids, sources_content, sources_path)


def make_ubuntu_preferencies_task(meta, uids):
    preferences_content = '\n'.join([
        'Package: *',
        'Pin: release a={suite}',
        'Pin-Priority: {priority}']).format(**meta)
    preferences_path = '/etc/apt/preferences.d/{name}'.format(
        name=meta['name'])
    return make_upload_task(uids, preferences_content, preferences_path)


def make_centos_repo_task(meta, uids):
    repo_content = '\n'.join([
        '[{name}]',
        'name=Plugin {name} repository',
        'baseurl={uri}',
        'gpgcheck=0',
        'priority={priority}']).format(**meta)
    repo_path = '/etc/yum.repos.d/{name}.repo'.format(name=meta['name'])
    return make_upload_task(uids, repo_content, repo_path)


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


def make_yum_clean(uids):
    task = {
        'parameters': {
            'cmd': 'yum clean all',
            'timeout': 180}}
    return make_shell_task(uids, task)


def make_apt_update_task(uids):
    task = {
        'parameters': {
            'cmd': 'apt-get update',
            'timeout': 180}}
    return make_shell_task(uids, task)


def make_puppet_task(uids, task, cwd='/'):
    return {
        'type': 'puppet',
        'uids': uids,
        'parameters': {
            'puppet_manifest': task['parameters']['puppet_manifest'],
            'puppet_modules': task['parameters']['puppet_modules'],
            'timeout': task['parameters']['timeout'],
            'cwd': cwd}}


def make_generic_task(uids, task):
    return {
        'type': task['type'],
        'uids': uids,
        'fail_on_error': task.get('fail_on_error', True),
        'parameters': task['parameters']
    }


def make_reboot_task(uids, task):
    return {
        'type': 'reboot',
        'uids': uids,
        'parameters': {
            'timeout': task['parameters']['timeout']}}
