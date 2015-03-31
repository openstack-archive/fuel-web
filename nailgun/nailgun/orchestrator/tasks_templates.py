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

import os

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
    # TODO(ikalnitsky):
    # Research how to add host condition to the current pinning.

    template = '\n'.join([
        'Package: *',
        'Pin: release a={suite},c={section}',
        'Pin-Priority: {priority}', ])

    template_flat = '\n'.join([
        'Package: *',
        'Pin: release a={suite}',
        'Pin-Priority: {priority}', ])

    preferences_content = []
    if repo['section']:
        for section in repo['section'].split():
            preferences_content.append(template.format(
                suite=repo['suite'],
                section=section,
                priority=repo['priority']))
    else:
        preferences_content.append(template_flat.format(
            suite=repo['suite'],
            priority=repo['priority']))

    preferences_content = '\n\n'.join(preferences_content)
    preferences_path = os.path.join('/etc/apt/preferences.d', repo['name'])

    return make_upload_task(uids, preferences_content, preferences_path)


def make_ubuntu_unauth_repos_task(uids):
    # NOTE(kozhukalov): This task is to allow installing packages
    # from unauthenticated repositories. Apt has special
    # mechanism for this.
    config_content = 'APT::Get::AllowUnauthenticated 1;\n'
    config_path = '/etc/apt/apt.conf.d/02mirantis-allow-unsigned'
    return make_upload_task(uids, config_content, config_path)


def make_centos_repo_task(uids, repo):
    repo_content = [
        '[{name}]',
        'name=Plugin {name} repository',
        'baseurl={uri}',
        'gpgcheck=0',
    ]

    if repo.get('priority'):
        repo_content.append('priority={priority}')

    repo_content = '\n'.join(repo_content).format(**repo)
    repo_path = '/etc/yum.repos.d/{name}.repo'.format(name=repo['name'])

    return make_upload_task(uids, repo_content, repo_path)


def make_sync_scripts_task(uids, src, dst):
    return {
        'type': 'sync',
        'uids': uids,
        'parameters': {
            'src': src,
            'dst': dst}}


def make_shell_task(uids, task):
    return {
        'type': 'shell',
        'uids': uids,
        'parameters': {
            'cmd': task['parameters']['cmd'],
            'timeout': task['parameters']['timeout'],
            'retries': task['parameters'].get(
                'retries', settings.SHELL_TASK_RETRIES),
            'interval': task['parameters'].get(
                'interval', settings.SHELL_TASK_INTERVAL),
            'cwd': task['parameters'].get('cwd', '/')}}


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


def make_puppet_task(uids, task):
    return {
        'type': 'puppet',
        'uids': uids,
        'parameters': {
            'puppet_manifest': task['parameters']['puppet_manifest'],
            'puppet_modules': task['parameters']['puppet_modules'],
            'timeout': task['parameters']['timeout'],
            'cwd': task['parameters'].get('cwd', '/')}}


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


def make_provisioning_images_task(uids, repos, provision_data, cid):
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
            'cmd': ("fa_build_image "
                    "--log-file /var/log/fuel-agent-env-{0}.log "
                    "--data_driver nailgun_build_image "
                    "--input_data '{1}'").format(cid, conf),
            'timeout': settings.PROVISIONING_IMAGES_BUILD_TIMEOUT,
            'retries': 1}})


def make_download_debian_installer_task(
        uids, repos, installer_kernel, installer_initrd):
    # NOTE(kozhukalov): This task is going to go away by 7.0
    # because we going to get rid of classic way of provision.

    # NOTE(ikalnitsky): We can't use urljoin here because it works
    # pretty bad in cases when 'uri' doesn't have a trailing slash.
    remote_kernel = os.path.join(
        repos[0]['uri'], installer_kernel['remote_relative'])
    remote_initrd = os.path.join(
        repos[0]['uri'], installer_initrd['remote_relative'])

    return make_shell_task(uids, {
        'parameters': {
            'cmd': ('LOCAL_KERNEL_FILE={local_kernel} '
                    'LOCAL_INITRD_FILE={local_initrd} '
                    'download-debian-installer '
                    '{remote_kernel} {remote_initrd}').format(
                        local_kernel=installer_kernel['local'],
                        local_initrd=installer_initrd['local'],
                        remote_kernel=remote_kernel,
                        remote_initrd=remote_initrd),
            'timeout': 10 * 60,
            'retries': 1}})
