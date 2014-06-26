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

from fuel_agent.openstack.common import log as logging

LOG = logging.getLogger(__name__)


class BaseError(Exception):
    def __init__(self, *args, **kwargs):
        super(BaseException, self).__init__(*args, **kwargs)
        LOG.error(self.message)


class WrongPartitionSchemeError(BaseError):
    pass


class WrongPartitionLabelError(BaseError):
    pass


class PartitionNotFoundError(BaseError):
    pass


class DiskNotFoundError(BaseError):
    pass


class NotEnoughSpaceError(BaseError):
    pass


class PVAlreadyExistsError(BaseError):
    pass


class PVNotFoundError(BaseError):
    pass


class PVBelongsToVGError(BaseError):
    pass


class VGAlreadyExistsError(BaseError):
    pass


class VGNotFoundError(BaseError):
    pass


class LVAlreadyExistsError(BaseError):
    pass


class LVNotFoundError(BaseError):
    pass


class MDAlreadyExistsError(BaseError):
    pass


class MDNotFoundError(BaseError):
    pass


class MDDeviceDuplicationError(BaseError):
    pass


class MDWrongSpecError(BaseError):
    pass


class WrongConfigDriveData(BaseError):
    pass