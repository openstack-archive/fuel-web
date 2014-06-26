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

class Common(object):
    def __init__(self, ssh_auth_key, hostname, fqdn, name_servers,
                 search_domain, master_node, master_url, timezone):
        self.ssh_auth_key = ssh_auth_key
        self.hostname = hostname
        self.fqdn = fqdn
        self.name_servers = name_servers
        self.search_domain = search_domain
        self.master_node = master_node
        self.master_url = master_url
        self.timezone = timezone


class Puppet(object):
    def __init__(self, master):
        self.master = master


class Mcollective(object):
    def __init__(self, pskey, vhost, host, user, password, connector):
        self.pskey = pskey
        self.vhost = vhost
        self.host = host
        self.user = user
        self.password = password
        self.connector = connector


class ConfigDrive(object):
    def __init__(self):
        self.common = None
        self.puppet = None
        self.mcollective = None

    def set_common(self, **kwargs):
        self.common = Common(kwargs)

    def set_puppet(self, **kwargs):
        self.puppet = Puppet(**kwargs)

    def set_mcollective(self, **kwargs):
        self.mcollective = Mcollective(**kwargs)
