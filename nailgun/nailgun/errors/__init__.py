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
    "DumpRunning": "Dump already running",

    # REST errors
    "CannotDelete": "Can't delete object",
    "CannotCreate": "Can't create object",
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
    "DeletionAlreadyStarted": "Environment removal already started",
    "StopAlreadyRunning": "Stopping deployment already initiated",
    "FailedProvisioning": "Failed to start provisioning",
    "WrongNodeStatus": "Wrong node status",
    "NodeOffline": "Node is offline",
    "NotEnoughControllers": "Not enough controllers",
    "RedHatSetupError": "Red Hat setup error",
    "TaskAlreadyRunning": "A task is already running",
    "InvalidReleaseId": "Release Id is invalid",
    "UnsupportedSerializer": "There are no serializers for a given cluster",
    "InvalidOperatingSystem": "Invalid operating system",
    "CannotFindPluginForRelease": "Cannot find plugin for the release",

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

    # RPC errors
    "CannotFindTask": "Cannot find task",

    # expression parser errors
    "LexError": "Illegal character",
    "ParseError": "Synxtax error",
    "UnknownModel": "Unknown model",

    # Zabbix errors
    "CannotMakeZabbixRequest": "Can't make a request to Zabbix",
    "ZabbixRequestError": "Zabbix request returned an error",

    # unknown
    "UnknownError": "Unknown error"
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

    def __getattr__(self, name):
        return self._build_exc(name, default_messages["UnknownError"])


errors = ErrorFactory()
