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


class FuelUpgradeException(Exception):
    pass


class ExecutedErrorNonZeroExitCode(FuelUpgradeException):
    pass


class CannotRunUpgrade(FuelUpgradeException):
    pass


class DockerExecutedErrorNonZeroExitCode(FuelUpgradeException):
    pass


class DockerFailedToBuildImageError(FuelUpgradeException):
    pass


class CyclicDependenciesError(FuelUpgradeException):
    pass


class CannotFindContainerError(FuelUpgradeException):
    pass


class CannotFindImageError(FuelUpgradeException):
    pass


class TimeoutError(FuelUpgradeException):
    pass


class DatabaseDumpError(FuelUpgradeException):
    pass


class UpgradeVerificationError(FuelUpgradeException):
    pass


class UnsupportedImageTypeError(FuelUpgradeException):
    pass


class WrongCobblerConfigsError(FuelUpgradeException):
    pass


class NotEnoughFreeSpaceOnDeviceError(FuelUpgradeException):
    pass


class WrongVersionError(FuelUpgradeException):
    pass


class UnsupportedActionTypeError(FuelUpgradeException):
    pass
