# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

from nailgun.errors.base import NailgunException

default_messages = {
    # common errors
    "InvalidData": "Invalid data received",
    "AlreadyExists": "Object already exists",
    "TaskAlreadyRunning": "Task is already running",

    # REST errors
    "CannotDelete": "Can't delete object",
    "CannotCreate": "Can't create object",
    "CannotUpdate": "Can't update object",
    "NotAllowed": "Action is not allowed",
    "InvalidField": "Invalid field specified for object",
    "ObjectNotFound": "Object not found in DB",

    # node discovering errors
    "InvalidInterfacesInfo": "Invalid interfaces info",
    "InvalidMetadata": "Invalid metadata specified for node",
    "CannotFindNodeIDForDiscovering": "Cannot find node for discovering",

    # deployment errors
    "CheckBeforeDeploymentError": "Pre-Deployment check wasn't successful",
    "DeploymentAlreadyStarted": "Deployment already started",
    "DeploymentNotRunning": "Deployment is not running",
    "NoDeploymentTasks": "Deployment tasks not found for specific release in the database",
    "DeletionAlreadyStarted": "Environment removal already started",
    "StopAlreadyRunning": "Stopping deployment already initiated",
    "FailedProvisioning": "Failed to start provisioning",
    "WrongNodeStatus": "Wrong node status",
    "NodeOffline": "Node is offline",
    "NotEnoughControllers": "Not enough controllers",
    "RedHatSetupError": "Red Hat setup error",
    "TaskAlreadyRunning": "A task is already running",
    "InvalidReleaseId": "Release Id is invalid",
    "InvalidOperatingSystem": "Invalid operating system",
    "CannotFindPluginForRelease": "Cannot find plugin for the release",
    "UnavailableRelease": "Release is unavailable",
    "ControllerInErrorState": ("One of the cluster controllers is in error "
                               "state, please, eliminate the problem prior "
                               "to proceeding further"),
    "SerializerNotSupported": ("Serialization of the task is not supported "
                               "because of unknown type"),

    # mongo errors
    "ExtMongoCheckerError": "Mongo nodes shouldn`t be used with external mongo",
    "MongoNodesCheckError": "Mongo nodes have to be present if ceilometer is chosen",

    # disk errors
    "NotEnoughFreeSpace": "Not enough free space",
    "NotEnoughOsdNodes": "Not enough OSD nodes",

    # network errors
    "AdminNetworkNotFound": "Admin network info not found",
    "InvalidNetworkCidr": "Invalid network CIDR",
    "InvalidNetworkVLANIDs": "Invalid network VLAN IDs",
    "AssignIPError": "Failed to assign IP to node",
    "NetworkCheckError": "Network checking failed",
    "CantRemoveOldVerificationTask": "Can't remove old verification task, still running",
    "OutOfVLANs": "Not enough available VLAN IDs",
    "OutOfIPs": "Not enough free IP addresses in pool",
    "NoSuitableCIDR": "Cannot find suitable CIDR",
    "CanNotFindInterface": "Cannot find interface",
    "CanNotDetermineEndPointIP": "Cannot determine end point IP",
    "CanNotFindNetworkForNode": "Cannot find network for node",
    "CanNotFindNetworkForNodeGroup": "Cannot find network for node group",
    "CanNotFindCommonNodeGroup": "Node role doesn't have common node group",
    "NetworkRoleConflict": "Cannot override existing network role",
    "NetworkTemplateMissingRoles": "Roles are missing from network template",
    "NetworkTemplateMissingNetRoles": "Network roles are missing",
    "NetworkTemplateMissingNetworkGroup": "Network group is missing",
    "DuplicatedVIPNames": ("Cannot assign VIPs for the cluster due to "
                           "overlapping of names of the VIPs"),
    "UpdateDnsmasqTaskIsRunning": ("update_dnsmasq task is not finished "
                                   "after the previous configuration change. "
                                   "Please try again after a few seconds."),
    "NovaNetworkNotSupported": ("Nova network is not supported in current "
                                "release"),

    # RPC errors
    "CannotFindTask": "Cannot find task",

    # expression parser errors
    "LexError": "Illegal character",
    "ParseError": "Synxtax error",
    "UnknownModel": "Unknown model",

    # Tracking errors
    "TrackingError": "Action failed",

    # Zabbix errors
    "CannotMakeZabbixRequest": "Can't make a request to Zabbix",
    "ZabbixRequestError": "Zabbix request returned an error",

    # Plugin errors
    "PackageVersionIsNotCompatible": "Package version is not compatible",

    # Extensions
    "CannotFindExtension": "Cannot find extension",

    # unknown
    "UnknownError": "Unknown error",
    "UnresolvableConflict": "Unresolvable conflict",
    "NodeNotBelongToCluster": "The Node doesn't belong to the Cluster",
    "TaskBaseDeploymentNotAllowed": "The task-based deployment is not allowed"
}


class ErrorFactory(object):

    def __init__(self):
        for name, msg in default_messages.iteritems():
            setattr(self, name, self._build_exc(name, msg))

    def _build_exc(self, name, msg):
        return type(
            name,
            (NailgunException,),
            {
                "message": msg
            }
        )


errors = ErrorFactory()
