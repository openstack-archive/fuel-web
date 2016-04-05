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


from nailgun.errors.base import DiskException
from nailgun.errors.base import ExpressionParserException
from nailgun.errors.base import ExtensionException
from nailgun.errors.base import MongoException
from nailgun.errors.base import NetworkException
from nailgun.errors.base import NodeDiscoveringException
from nailgun.errors.base import PluginException
from nailgun.errors.base import RESTException
from nailgun.errors.base import RPCException
from nailgun.errors.base import TaskException
from nailgun.errors.base import UnhandledException
from nailgun.errors.base import ValidationException
from nailgun.errors.base import ZabbixException


class InvalidData(ValidationException):
    message = "Invalid data received"


class AlreadyExists(ValidationException):
    message = "Object already exists"


class JsonDecodeError(InvalidData):
    message = "Malformed json format"


class JsonValidationError(InvalidData):
    message = "Data is not valid"


# REST api exceptions
class CannotDelete(RESTException):
    message = "Can't delete object"


class CannotCreate(RESTException):
    message = "Can't create object"


class CannotUpdate(RESTException):
    message = "Can't update object"


class NotAllowed(RESTException):
    message = "Action is not allowed"


class ObjectNotFound(RESTException):
    message = "Object not found in DB"


# Node discovering exceptions
class InvalidInterfacesInfo(NodeDiscoveringException):
    message = "Invalid interfaces info"


class InvalidMetadata(NodeDiscoveringException):
    message = "Invalid metadata specified for node"


class CannotFindNodeIDForDiscovering(NodeDiscoveringException):
    message = "Cannot find node for discovering"


# Deployment exceptions
class DeploymentException(TaskException):
    message = "Base deployment exception"


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
    message = "Stop action is forbidden for the cluster"


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


# Mongodb exceptions
class ExtMongoCheckerError(MongoException):
    message = "Mongo nodes shouldn`t be used with external mongo"


class MongoNodesCheckError(MongoException):
    message = "Mongo nodes have to be present if ceilometer is chosen"


# Disk exceptions
class NotEnoughFreeSpace(DiskException):
    message = "Not enough free space"


class NotEnoughOsdNodes(DiskException):
    message = "Not enough OSD nodes"


# Network exceptions
class AdminNetworkNotFound(NetworkException):
    message = "Admin network info not found"


class InvalidNetworkCidr(NetworkException):
    message = "Invalid network CIDR"


class InvalidNetworkVLANIDs(NetworkException):
    message = "Invalid network VLAN IDs"


class AssignIPError(NetworkException):
    message = "Failed to assign IP to node"


class NetworkCheckError(NetworkException):
    message = "Network checking failed"


class CantRemoveOldVerificationTask(NetworkException):
    message = "Can't remove old verification task, still running"


class OutOfVLANs(NetworkException):
    message = "Not enough available VLAN IDs"


class OutOfIPs(NetworkException):
    message = "Not enough free IP addresses in pool"


class NoSuitableCIDR(NetworkException):
    message = "Cannot find suitable CIDR"


class CanNotFindInterface(NetworkException):
    message = "Cannot find interface"


class CanNotDetermineEndPointIP(NetworkException):
    message = "Cannot determine end point IP"


class CanNotFindNetworkForNode(NetworkException):
    message = "Cannot find network for node"


class CanNotFindNetworkForNodeGroup(NetworkException):
    message = "Cannot find network for node group"


class CanNotFindCommonNodeGroup(NetworkException):
    message = "Node role doesn't have common node group"


class NetworkRoleConflict(NetworkException):
    message = "Cannot override existing network role"


# network templates
class NetworkTemplateException(NetworkException):
    message = "Base network template exception"


class NetworkTemplateMissingRoles(NetworkTemplateException):
    message = "Roles are missing from network template"


class NetworkTemplateMissingNetRoles(NetworkTemplateException):
    message = "Network roles are missing"


class NetworkTemplateMissingNetworkGroup(NetworkTemplateException):
    message = "Network group is missing"


class NetworkTemplateCannotBeApplied(NetworkTemplateException):
    message = "Network template cannot be applied"


class DuplicatedVIPNames(NetworkException):
    message = ("Cannot assign VIPs for the cluster due to overlapping of"
               " names of the VIPs")


class UpdateDnsmasqTaskIsRunning(NetworkException):
    message = ("update_dnsmasq task is not finished after the previous"
               " configuration change. Please try again after a few seconds")


class NovaNetworkNotSupported(NetworkException):
    message = "Nova network is not supported in current release"


# parser exceptions
class LexError(ExpressionParserException):
    message = "Illegal character"


class ParseError(ExpressionParserException):
    message = "Synxtax error"


class UnknownModel(ExpressionParserException):
    message = "Unknown model"


# zabbix exceptions
class CannotMakeZabbixRequest(ZabbixException):
    message = "Can't make a request to Zabbix"


class ZabbixRequestError(ZabbixException):
    message = "Zabbix request returned an error"


# plugins exceptions
class PackageVersionIsNotCompatible(PluginException):
    message = "Package version is not compatible"


class CannotFindExtension(ExtensionException):
    message = "Cannot find extension"


# other exceptions
class UnresolvableConflict(UnhandledException):
    message = "Unresolvable conflict"


class NodeNotBelongToCluster(UnhandledException):
    message = "The Node doesn't belong to the Cluster"


class NoChanges(TaskException):
    message = "There is no changes to apply"


class CannotFindTask(RPCException):
    message = "Cannot find task"
