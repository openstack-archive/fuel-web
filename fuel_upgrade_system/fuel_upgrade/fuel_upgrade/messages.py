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

header = '=' * 50


docker_is_dead = """
Docker died during the upgrade. Run these commands and then restart the upgrade

    Make sure that docker is dead
    # docker ps
    2014/08/19 14:28:15 Cannot connect to the Docker daemon.
    Is 'docker -d' running on this host?
    # umount -l $(grep '/dev/mapper/docker-' /proc/mounts | awk '{ print $2}')
    # rm /var/run/docker.pid
    # service docker start

Run upgrade again from the directory with unarchived upgrade tar-ball

    # ./upgrade.sh

You can track the issue here
https://bugs.launchpad.net/fuel/+bug/1359725
"""


nailgun_is_not_running = """
REST API service (nailgun) is not running. Unable to verify that
there are no running tasks.

Use `--no-check` as a parameter for upgrade script to skip all
pre-upgrade checks.
"""


no_password_provided = """
Expecting a password provided via --password or prompted response
"""


health_checker_failed = """
Couldn't start some of the services, try to run upgrade again.
"""


ostf_is_not_running = """
Health Checker (OSTF) is not running. Unable to verify that
there are no running tasks.

Use `--no-check` as a parameter for upgrade script to skip all
pre-upgrade checks.
"""
