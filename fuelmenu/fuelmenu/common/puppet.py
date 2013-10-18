# Copyright 2013 Mirantis, Inc.
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

#Python 2.6 hack to add check_output command

if "check_output" not in dir(subprocess):  # duck punch it in!
    def f(*popenargs, **kwargs):
        if 'stdout' in kwargs:
            raise ValueError('stdout argument not allowed, \
itwill be overridden.')
        process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs,
                                   **kwargs)
        output, unused_err = process.communicate()
        retcode = process.poll()
        if retcode:
            cmd = kwargs.get("args")
            if cmd is None:
                cmd = popenargs[0]
            raise Exception(retcode, cmd)
        return output
    subprocess.check_output = f


def puppetApply(classname, name=None, params=None):
    #name should be a string
    #params should be a dict
    '''Runs puppet apply -e "classname {'name': params}".'''
    log = logging
    log.info("Puppet start")

    command = ["puppet", "apply", "-d", "-v", "--logdest", "/tmp/puppet.log"]
    input = [classname, "{", '"%s":' % name]
    #Build params
    for key, value in params.items():
        if type(value) == bool:
            input.extend([key, "=>", '%s,' % str(value).lower()])
        else:
            input.extend([key, "=>", '"%s",' % value])
    input.append('}')

    log.debug(' '.join(command))
    log.debug(' '.join(input))
    output = ""
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stdin=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        output, errout = process.communicate(input=' '.join(input))
    except Exception as e:
        import traceback
        log.error(traceback.print_exc())
        if "err:" in output:
            log.error(e)
            return False
        else:
            log.debug(output)
            return True
