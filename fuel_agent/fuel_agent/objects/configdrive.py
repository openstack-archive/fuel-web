# Copyright 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from fuel_agent import errors


class ConfigDriveCommon(object):
    def __init__(self, ssh_auth_keys, hostname, fqdn, name_servers,
                 search_domain, master_ip, master_url, udevrules, admin_mac,
                 admin_ip, admin_mask, admin_iface_name, timezone, ks_repos):
        self.ssh_auth_keys = ssh_auth_keys
        self.hostname = hostname
        self.fqdn = fqdn
        self.name_servers = name_servers
        self.search_domain = search_domain
        self.master_ip = master_ip
        self.master_url = master_url
        self.udevrules = udevrules
        self.admin_mac = admin_mac
        self.admin_ip = admin_ip
        self.admin_mask = admin_mask
        self.admin_iface_name = admin_iface_name
        self.timezone = timezone
        self.ks_repos = ks_repos


class ConfigDrivePuppet(object):
    def __init__(self, master, enable):
        self.master = master
        self.enable = enable


class ConfigDriveMcollective(object):
    def __init__(self, pskey, vhost, host, user, password, connector, enable):
        self.pskey = pskey
        self.vhost = vhost
        self.host = host
        self.user = user
        self.password = password
        self.connector = connector
        self.enable = enable


class ConfigDriveScheme(object):
    def __init__(self, common=None, puppet=None,
                 mcollective=None, profile=None):
        self.common = common
        self.puppet = puppet
        self.mcollective = mcollective
        self._profile = profile or 'ubuntu'

    # TODO(kozhukalov) make it possible to validate scheme according to
    # chosen profile which means chosen set of cloud-init templates.
    # In other words make this templating scheme easily extendable.

    def set_common(self, **kwargs):
        self.common = ConfigDriveCommon(**kwargs)

    def set_puppet(self, **kwargs):
        self.puppet = ConfigDrivePuppet(**kwargs)

    def set_mcollective(self, **kwargs):
        self.mcollective = ConfigDriveMcollective(**kwargs)

    def template_data(self):
        if self.common is None:
            raise errors.WrongConfigDriveDataError(
                'Common attribute should be defined, but it is not')
        template_data = {'common': self.common}
        if self.puppet is not None:
            template_data.update(puppet=self.puppet)
        if self.mcollective is not None:
            template_data.update(mcollective=self.mcollective)
        return template_data

    def set_profile(self, profile):
        # TODO(kozhukalov) validate profile
        self._profile = profile

    @property
    def profile(self):
        return self._profile

    def template_names(self, what):
        # such a complicated scheme is used to cover a range of profile names
        # which might be either dash or underline separated
        # ubuntu_1204_x86_64
        # centos-65_x86_64
        return [
            '%s_%s.jinja2' % (what, self._profile),
            '%s_%s.jinja2' % (what, self._profile.split('_')[0]),
            '%s_%s.jinja2' % (what, self._profile.split('-')[0]),
            '%s.jinja2' % what
        ]
