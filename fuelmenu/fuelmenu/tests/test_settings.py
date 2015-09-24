# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

import mock
import ordereddict

from fuelmenu import settings


def test_read_settings(tmpdir):
    yaml_file = tmpdir.join("yamlfile.yaml")
    yaml_file.write("""
sample:
    - one
    - a: b
      c: d
""")
    data = settings.Settings().read(yaml_file.strpath)
    assert data == {
        'sample': [
            'one',
            {
                'a': 'b',
                'c': 'd',
            }
        ]
    }
    assert isinstance(data, ordereddict.OrderedDict)


@mock.patch('fuelmenu.settings.file', side_effect=Exception('Error'))
def test_read_settings_with_error(_):
    data = settings.Settings().read('some_path')
    assert data == {}
    assert isinstance(data, ordereddict.OrderedDict)
