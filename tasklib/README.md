Tasklib
=======

Tasklib is mediator between different configuration management providers
and orchestration mechanism in Fuel.

It will try to cover next areas:
- part of the plugable fuel architecture
  See tasklib/tasklib/tests/functional for detailed descriptionof
  how tasklib plugability will work
- Control mechanism for tasks in fuel
  To support different types of workflow we will provide
  ability to terminate, list all running, stop/pause task
- Abstraction layer between tasks and orchestration, which will allow
  easier development and debuging of tasks
- General reporting solution for tasks

Executions drivers
==================
- puppet
- exec

Puppet
--------
Puppet executor supports general metadata for running puppet manifests.
Example of such metadata (task.yaml):

    type: puppet                        - required
    puppet_manifest: file.pp            - default is site.pp
    puppet_moduels: /etc/puppet/modules
    puppet_options: --debug

All defaults you can find in:
>> taskcmd conf

It works next way:
After task.yaml is found - executor will look for puppet_manifest
and run:
puppet apply --modulepath=/etc/puppet/modules file.pp
with additional options you will provide

Exec
-----

    type: exec       - required
    cmd: echo 12     - required

will execute any cmd provided as subprocess

EXAMPLES:
=========

taskcmd -c tasklib/tests/functional/conf.yaml conf

taskcmd -c tasklib/tests/functional/conf.yaml list

taskcmd -c tasklib/tests/functional/conf.yaml daemon puppet/sleep
taskcmd -c tasklib/tests/functional/conf.yaml status puppet/sleep

taskcmd -c tasklib/tests/functional/conf.yaml run puppet/cmd

taskcmd -c tasklib/tests/functional/conf.yaml run puppet/invalid

HOW TO RUN TESTS:
==================
python setup.py develop
pip install -r test-requires.txt

nosetests tasklib/tests

For some functional tests installed puppet is required,
so if you dont have puppet - they will be skipped
