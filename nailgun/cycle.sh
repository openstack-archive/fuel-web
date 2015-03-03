#!/bin/bash

set -e
while true
do
  nosetests nailgun.test.unit.test_statistics:TestInstallationInfo
done
