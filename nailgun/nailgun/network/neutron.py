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

from netaddr import IPNetwork
from netaddr import IPRange
from netaddr import IPSet

from nailgun.api.models import AttributesGenerators
from nailgun.api.models import Cluster
from nailgun.api.models import GlobalParameters
from nailgun.api.models import IPAddrRange
from nailgun.api.models import NetworkGroup
from nailgun.api.models import NeutronConfig
from nailgun.db import db
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.network.manager import NetworkManager


class NeutronManager(NetworkManager):

    def create_neutron_config(self, cluster):
        meta = cluster.release.networks_metadata["neutron"]["config"]
        neutron_config = NeutronConfig(
            cluster_id=cluster.id,
            parameters=meta["parameters"],
            predefined_networks=self._generate_predefined_networks(cluster),
            L2=self._generate_l2(cluster),
            L3=self._generate_l3(cluster),
            segmentation_type=cluster.net_segment_type,
            nova_metadata={
                "metadata_proxy_shared_secret": AttributesGenerators.password()
            }
        )
        db().add(neutron_config)
        db().flush()

    def _generate_external_network(self, cluster):
        public_cidr, public_gw = db().query(
            NetworkGroup.cidr,
            NetworkGroup.gateway
        ).filter_by(
            cluster_id=cluster.id,
            name='public'
        ).first()
        net = IPNetwork(public_cidr)
        return {
            "L3": {
                "cidr": public_cidr,
                "gateway": public_gw,
                "nameservers": [],
                "floating": [
                    str(net[len(net) / 2 + 2]),
                    str(net[-2])
                ]
            }
        }

    def _generate_internal_network(self, cluster):
        return {
            "L3": {
                "cidr": "192.168.111.0/24",
                "gateway": "192.168.111.1",
                "nameservers": [
                    "8.8.4.4",
                    "8.8.8.8"
                ],
                "floating": []
            }
        }

    def _generate_predefined_networks(self, cluster):
        return {
            "net04_ext": self._generate_external_network(cluster),
            "net04": self._generate_internal_network(cluster)
        }

    def _generate_l2(self, cluster):
        res = {
            "base_mac": "fa:16:3e:00:00:00",
            "segmentation_type": cluster.net_segment_type,
            "phys_nets": {
                "physnet1": {
                    "bridge": "br-ex",
                    "vlan_range": []
                },
                "physnet2": {
                    "bridge": "br-prv",
                    "vlan_range": []
                }
            }
        }
        if cluster.net_segment_type == 'gre':
            res["tunnel_id_ranges"] = [2, 65535]
        elif cluster.net_segment_type == 'vlan':
            res["phys_nets"]["physnet2"]["vlan_range"] = [
                1000,
                2999
            ]
        return res

    def _generate_l3(self, cluster):
        return {}

    # TODO(enchantner): refactor and DRY
    def create_network_groups(self, cluster_id):
        '''Method for creation of network groups for cluster.

        :param cluster_id: Cluster database ID.
        :type  cluster_id: int
        :returns: None
        :raises: errors.OutOfVLANs, errors.OutOfIPs,
        errors.NoSuitableCIDR
        '''
        used_nets = []
        used_vlans = []

        global_params = db().query(GlobalParameters).first()

        cluster_db = db().query(Cluster).get(cluster_id)

        networks_metadata = cluster_db.release.networks_metadata

        admin_network_range = db().query(IPAddrRange).filter_by(
            network_group_id=self.get_admin_network_group_id()
        ).all()[0]

        networks_list = networks_metadata["neutron"]["networks"]

        def _free_vlans():
            free_vlans = set(
                range(
                    *global_params.parameters["vlan_range"]
                )
            ) - set(used_vlans)
            if not free_vlans or len(free_vlans) < len(networks_list):
                raise errors.OutOfVLANs()
            return sorted(list(free_vlans))

        public_vlan = _free_vlans()[0]
        used_vlans.append(public_vlan)
        for network in networks_list:
            free_vlans = _free_vlans()
            vlan_start = public_vlan if network.get("use_public_vlan") \
                else free_vlans[0]

            logger.debug("Found free vlan: %s", vlan_start)
            pool = network.get('pool')
            if not pool:
                raise errors.InvalidNetworkPool(
                    u"Invalid pool '{0}' for network '{1}'".format(
                        pool,
                        network['name']
                    )
                )

            nets_free_set = IPSet(pool) -\
                IPSet(
                    IPNetwork(global_params.parameters["net_exclude"])
                ) -\
                IPSet(
                    IPRange(
                        admin_network_range.first,
                        admin_network_range.last
                    )
                ) -\
                IPSet(used_nets)
            if not nets_free_set:
                raise errors.OutOfIPs()

            free_cidrs = sorted(list(nets_free_set._cidrs))
            new_net = None
            for fcidr in free_cidrs:
                for n in fcidr.subnet(24, count=1):
                    new_net = n
                    break
                if new_net:
                    break
            if not new_net:
                raise errors.NoSuitableCIDR()

            new_ip_range = IPAddrRange(
                first=str(new_net[2]),
                last=str(new_net[-2])
            )

            nw_group = NetworkGroup(
                release=cluster_db.release.id,
                name=network['name'],
                cidr=str(new_net),
                netmask=str(new_net.netmask),
                gateway=str(new_net[1]),
                cluster_id=cluster_id,
                vlan_start=vlan_start,
                amount=1
            )
            db().add(nw_group)
            db().commit()
            nw_group.ip_ranges.append(new_ip_range)
            db().commit()
            self.create_networks(nw_group)

            used_vlans.append(vlan_start)
            used_nets.append(str(new_net))

        if cluster_db.net_segment_type == 'vlan':
            private_network_group = NetworkGroup(
                release=cluster_db.release.id,
                name="private",
                cluster_id=cluster_id,
                netmask='32',
                vlan_start=0,
                amount=1
            )
            db().add(private_network_group)
            db().commit()
