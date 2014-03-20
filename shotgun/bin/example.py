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

import json
import logging
import os
import sys

sys.path[:0] = [os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))]

from shotgun.config import Config
from shotgun.manager import Manager

logging.basicConfig(level=logging.DEBUG)


with open("snapshot.json", "r") as fo:
    data = json.loads(fo.read())
    config = Config(data)


manager = Manager(config)
manager.snapshot()
