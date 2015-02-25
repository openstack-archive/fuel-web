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

from oslo.serialization import jsonutils

from nailgun.settings import settings


def make_upload_task(uids, data, path):
    return {
        'type': 'upload_file',
        'uids': uids,
        'parameters': {
            'path': path,
            'data': data}}


def make_ubuntu_sources_task(uids, repo):
    sources_content = 'deb {uri} {suite} {section}'.format(**repo)
    sources_path = '/etc/apt/sources.list.d/{name}.list'.format(
        name=repo['name'])
    return make_upload_task(uids, sources_content, sources_path)


def make_ubuntu_preferences_task(uids, repo):
    # NOTE(kozhukalov): maybe here we need to have more robust preferences
    # template because in general it allows us to set priorities for
    # releases, codenames, origins, etc. (see man apt_preferences)
    preferences_content = '\n'.join([
        'Package: *',
        'Pin: release a={suite}',
        'Pin-Priority: {priority}']).format(**repo)
    preferences_path = '/etc/apt/preferences.d/{name}'.format(
        name=repo['name'])
    return make_upload_task(uids, preferences_content, preferences_path)


def make_ubuntu_unauth_repos_task(uids):
    # NOTE(kozhukalov): This task is to allow installing packages
    # from unauthenticated repositories. Apt has special
    # mechanism for this.
    config_content = 'APT::Get::AllowUnauthenticated 1;\n'
    config_path = '/etc/apt/apt.conf.d/02mirantis-allow-unsigned'
    return make_upload_task(uids, config_content, config_path)


def make_centos_repo_task(uids, repo):
    repo_content = '\n'.join([
        '[{name}]',
        'name=Plugin {name} repository',
        'baseurl={uri}',
        'gpgcheck=0',
        'priority={priority}']).format(**repo)
    repo_path = '/etc/yum.repos.d/{name}.repo'.format(name=repo['name'])
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
            'retries': task['parameters'].get(
                'retries', settings.SHELL_TASK_RETRIES),
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


def make_provisioning_images_task(uids, repos, provision_data):
    conf = {
        'repos': repos,
        'image_data': provision_data['image_data'],
        'codename': provision_data['codename'],
        'output': settings.PROVISIONING_IMAGES_PATH,
    }
    # TODO(ikalnitsky):
    # Upload settings before using and pass them as command line argument.
    conf = jsonutils.dumps(conf)

    return make_shell_task(uids, {
        'parameters': {
            'cmd': "fuel-image '{0}'".format(conf),
            'timeout': settings.PROVISIONING_IMAGES_BUILD_TIMEOUT,
            'retries': 1}})
