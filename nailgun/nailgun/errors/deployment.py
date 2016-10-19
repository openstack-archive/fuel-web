# coding: utf-8

# Copyright 2016 Mirantis, Inc.
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

from .base import NailgunException


class DeploymentException(NailgunException):
    """Base deployment exception"""


class CheckBeforeDeploymentError(DeploymentException):
    message = "Pre-Deployment check wasn't successful"


class DeploymentAlreadyStarted(DeploymentException):
    message = "Deployment already started"


class DeploymentNotRunning(DeploymentException):
    message = "Deployment is not running"


class NoDeploymentTasks(DeploymentException):
    message = "Deployment tasks not found for specific release in the database"


class DeletionAlreadyStarted(DeploymentException):
    message = "Environment removal already started"


class StopAlreadyRunning(DeploymentException):
    message = "Stopping deployment already initiated"


class CannotBeStopped(DeploymentException):
    message = "Stop action is forbidden for the cluster. {0}"

    def __init__(self, message=None):
        super(CannotBeStopped, self).__init__()
        self.message = self.message.format(message or '')


class WrongNodeStatus(DeploymentException):
    message = "Wrong node status"


class NodeOffline(DeploymentException):
    message = "Node is offline"


class NotEnoughControllers(DeploymentException):
    message = "Not enough controllers"


class RedHatSetupError(DeploymentException):
    message = "Red Hat setup error"


class TaskAlreadyRunning(DeploymentException):
    message = "A task is already running"


class InvalidReleaseId(DeploymentException):
    message = "Release Id is invalid"


class InvalidOperatingSystem(DeploymentException):
    message = "Invalid operating system"


class CannotFindPluginForRelease(DeploymentException):
    message = "Cannot find plugin for the release"


class UnavailableRelease(DeploymentException):
    message = "Release is unavailable"


class ControllerInErrorState(DeploymentException):
    message = ("One of the cluster controllers is in error state,"
               " please, eliminate the problem prior to proceeding further")


class SerializerNotSupported(DeploymentException):
    message = ("Serialization of the task is not supported because of"
               " unknown type")


class TaskBaseDeploymentNotAllowed(DeploymentException):
    message = "The task-based deployment is not allowed"


class NoChanges(DeploymentException):
    message = "There is no changes to apply"


class DryRunSupportedOnlyByLCM(DeploymentException):
    message = "Dry run deployment mode is supported only by LCM serializer"


class TaskNotFound(DeploymentException):
    message = "Cannot find specified task in the graph"

    def __init__(self, task_name=""):
        self.task_name = task_name
        super(TaskNotFound, self).__init__()


class LinearizationImpossible(DeploymentException):
    message = "Linearization of tasks hierarchy impossible"


class WrongTasksHierarchy(DeploymentException):
    message = "Wrong task {0} hierarchy: {1}. Order of the task parents " \
              "can't be linearized."

    def __init__(self, task_data):
        super(WrongTasksHierarchy, self).__init__()
        self.message = self.message.format(task_data.get("id"),
                                           task_data.get("inherited"))


class DifferentTasksTypesInheritance(DeploymentException):
    message = "Different task types set as parents for task {0}: " \
              "{1} and {2}"

    def __init__(self, task_data, found_type):
        super(DifferentTasksTypesInheritance, self).__init__()
        self.message = self.message.format(
            task_data.get("id"), task_data.get("type"), found_type)
