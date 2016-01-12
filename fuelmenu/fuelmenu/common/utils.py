# Copyright 2015 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import logging
import subprocess
log = logging.getLogger('fuelmenu.common.utils')


def get_deployment_mode():
    """Report if any fuel containers are already created."""
    command = ['docker', 'ps', '-a']
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stdin=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        output, errout = process.communicate()
        if "fuel" in output.lower():
            return "post"
        else:
            return "pre"
    except OSError:
        log.warning('Unable to check deployment mode via docker. Assuming'
                    ' pre-deployment stage.')
        return "pre"
