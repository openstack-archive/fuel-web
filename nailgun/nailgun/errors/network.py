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


class NetworkException(NailgunException):
    """Base network exception"""


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


class DuplicatedVIPNames(NetworkException):
    message = ("Cannot assign VIPs for the cluster due to overlapping of"
               " names of the VIPs")


class UpdateDnsmasqTaskIsRunning(NetworkException):
    message = ("update_dnsmasq task is not finished after the previous"
               " configuration change. Please try again after a few seconds")


class UnresolvableConflict(NetworkException):
    message = "Unresolvable conflict"
