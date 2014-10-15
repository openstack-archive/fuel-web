# Copyright 2013 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import netaddr

from fuelmenu.common.errors import BadIPException


def inSameSubnet(ip1, ip2, netmask_or_cidr):
    try:
        cidr1 = netaddr.IPNetwork("%s/%s" % (ip1, netmask_or_cidr))
        cidr2 = netaddr.IPNetwork("%s/%s" % (ip2, netmask_or_cidr))
        return cidr1 == cidr2
    except netaddr.AddrFormatError:
        return False


def getCidr(ip, netmask):
    try:
        ipn = netaddr.IPNetwork("%s/%s" % (ip, netmask))
        return str(ipn.cidr)
    except netaddr.AddrFormatError:
        return False


def getCidrSize(cidr):
    try:
        ipn = netaddr.IPNetwork(cidr)
        return ipn.size
    except netaddr.AddrFormatError:
        return False


def getNetwork(ip, netmask, additionalip=None):
    #Return a list excluding ip and broadcast IPs
    try:
        ipn = netaddr.IPNetwork("%s/%s" % (ip, netmask))
        ipn_list = list(ipn)
        #Drop broadcast and network ip
        ipn_list = ipn_list[1:-1]
        #Drop ip
        ipn_list[:] = [value for value in ipn_list if str(value) != ip]
        #Drop additionalip
        if additionalip:
            ipn_list[:] = [value for value in ipn_list if
                           str(value) != additionalip]

        return ipn_list
    except netaddr.AddrFormatError:
        return False


def range(startip, endip):
    #Return a list of IPs between startip and endip
    try:
        return set(netaddr.iter_iprange(startip, endip))
    except netaddr.AddrFormatError:
        raise BadIPException("Invalid IP address(es) specified.")


def intersects(range1, range2):
    #Returns true if any IPs in range1 exist in range2
    return range1 & range2
