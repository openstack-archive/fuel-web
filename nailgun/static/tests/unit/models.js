define([
    'intern!object',
    'intern/chai!assert',
    'underscore',
    'models',
    'expression',
    'expression/objects'
], function (registerSuite, assert, _, models, Expression, expressionObjects) {
    'use strict';

    var dummyNovaNetworkConfig = {
        'public_vrouter_vip': '172.16.0.5',
        'management_vrouter_vip': '192.168.0.4',
        'management_vip': '192.168.0.3',
        'public_vip': '172.16.0.4',
        'networking_parameters': {
            'dns_nameservers': ['8.8.4.4', '8.8.8.8'],
            'net_manager': 'FlatDHCPManager',
            'fixed_networks_vlan_start': 103,
            'fixed_networks_cidr': '10.0.0.0/16',
            'floating_ranges': [['172.16.0.128', '172.16.0.254']],
            'fixed_network_size': 256,
            'fixed_networks_amount': 1
        },
        'networks': [
            {
                'name': 'public',
                'ip_ranges': [['172.16.0.2', '172.16.0.127']],
                'id': 6,
                'meta': {
                    'vips': ['haproxy', 'vrouter'],
                    'name': 'public',
                    'notation': 'ip_ranges',
                    'render_type': null,
                    'map_priority': 1,
                    'configurable': true,
                    'use_gateway': true,
                    'vlan_start': null,
                    'render_addr_mask': 'public',
                    'cidr': '172.16.0.0/24',
                    'gateway': '172.16.0.1',
                    'ip_range': ['172.16.0.2', '172.16.0.127']
                },
                'vlan_start': null,
                'cidr': '172.16.0.0/24',
                'group_id': 2,
                'gateway': '172.16.0.1'
            },
            {
                'name': 'management',
                'ip_ranges': [['192.168.0.1', '192.168.0.254']],
                'id': 7,
                'meta': {
                    'vips': ['haproxy', 'vrouter'],
                    'name': 'management',
                    'notation': 'cidr',
                    'render_type': 'cidr',
                    'map_priority': 2,
                    'configurable': true,
                    'use_gateway': false,
                    'vlan_start': 101,
                    'render_addr_mask': 'internal',
                    'cidr': '192.168.0.0/24'
                },
                'vlan_start': 101,
                'cidr': '192.168.0.0/24',
                'group_id': 2,
                'gateway': null
            },
            {
                'name': 'storage',
                'ip_ranges': [['192.168.1.1', '192.168.1.254']],
                'id': 8,
                'meta': {
                    'name': 'storage',
                    'notation': 'cidr',
                    'render_type': 'cidr',
                    'map_priority': 2,
                    'configurable': true,
                    'use_gateway': false,
                    'vlan_start': 102,
                    'render_addr_mask': 'storage',
                    'cidr': '192.168.1.0/24'
                },
                'vlan_start': 102,
                'cidr': '192.168.1.0/24',
                'group_id': 2,
                'gateway': null
            },
            {
                'name': 'fixed',
                'ip_ranges': [],
                'id': 9,
                'meta': {
                    'ext_net_data': ['fixed_networks_vlan_start', 'fixed_networks_amount'],
                    'name': 'fixed',
                    'notation': null,
                    'render_type': null,
                    'map_priority': 2,
                    'configurable': false,
                    'use_gateway': false,
                    'vlan_start': null,
                    'render_addr_mask': null
                },
                'vlan_start': null,
                'cidr': null,
                'group_id': 2,
                'gateway': null
            }, {
                'name': 'fuelweb_admin',
                'ip_ranges': [['10.20.0.129', '10.20.0.254']],
                'id': 1,
                'meta': {
                    'notation': 'ip_ranges',
                    'render_type': null,
                    'map_priority': 0,
                    'configurable': false,
                    'unmovable': true,
                    'use_gateway': true,
                    'render_addr_mask': null
                },
                'vlan_start': null,
                'cidr': '10.20.0.0/24',
                'group_id': null,
                'gateway': '10.20.0.1'
            }]
    };

    var dummyNeutronNetworkConfig = {
        'public_vrouter_vip': '172.16.0.3',
        'management_vrouter_vip': '192.168.0.2',
        'management_vip': '192.168.0.1',
        'public_vip': '172.16.0.2',
        'networking_parameters': {
            'floating_ranges': [['172.16.0.130', '172.16.0.254']],
            'dns_nameservers': ['8.8.4.4', '8.8.8.8'],
            'net_l23_provider': 'ovs',
            'base_mac': 'fa:16:3e:00:00:00',
            'internal_gateway': '192.168.111.1',
            'internal_cidr': '192.168.111.0/24',
            'gre_id_range': [2, 65535],
            'vlan_range': [1000, 1030],
            'segmentation_type': 'vlan'
        },
        'networks': [{
            'name': 'public',
            'ip_ranges': [['172.16.0.2', '172.16.0.126']],
            'id': 2,
            'meta': {
                'vips': ['haproxy', 'vrouter'],
                'name': 'public',
                'notation': 'ip_ranges',
                'render_type': null,
                'map_priority': 1,
                'configurable': true,
                'floating_range_var': 'floating_ranges',
                'use_gateway': true,
                'vlan_start': null,
                'render_addr_mask': 'public',
                'cidr': '172.16.0.0/24',
                'ip_range': ['172.16.0.2', '172.16.0.126']
            },
            'vlan_start': null,
            'cidr': '172.16.0.0/24',
            'group_id': 1,
            'gateway': '172.16.0.1'
        }, {
            'name': 'management',
            'ip_ranges': [['192.168.0.1', '192.168.0.254']],
            'id': 3,
            'meta': {
                'vips': ['haproxy', 'vrouter'],
                'name': 'management',
                'notation': 'cidr',
                'render_type': 'cidr',
                'map_priority': 2,
                'configurable': true,
                'use_gateway': false,
                'vlan_start': 101,
                'render_addr_mask': 'internal',
                'cidr': '192.168.0.0/24'
            },
            'vlan_start': 101,
            'cidr': '192.168.0.0/24',
            'group_id': 1,
            'gateway': null
        }, {
            'name': 'storage',
            'ip_ranges': [['192.168.1.1', '192.168.1.254']],
            'id': 4,
            'meta': {
                'name': 'storage',
                'notation': 'cidr',
                'render_type': 'cidr',
                'map_priority': 2,
                'configurable': true,
                'use_gateway': false,
                'vlan_start': 102,
                'render_addr_mask': 'storage',
                'cidr': '192.168.1.0/24'
            },
            'vlan_start': 102,
            'cidr': '192.168.1.0/24',
            'group_id': 1,
            'gateway': null
        }, {
            'name': 'private',
            'ip_ranges': [],
            'id': 5,
            'meta': {
                'name': 'private',
                'notation': null,
                'render_type': null,
                'map_priority': 2,
                'neutron_vlan_range': true,
                'use_gateway': false,
                'vlan_start': null,
                'render_addr_mask': null,
                'configurable': false,
                'seg_type': 'vlan'
            },
            'vlan_start': null,
            'cidr': null,
            'group_id': 1,
            'gateway': null
        }, {
            'name': 'fuelweb_admin',
            'ip_ranges': [['10.20.0.129', '10.20.0.254']],
            'id': 1,
            'meta': {
                'notation': 'ip_ranges',
                'render_type': null,
                'map_priority': 0,
                'configurable': false,
                'unmovable': true,
                'use_gateway': true,
                'render_addr_mask': null
            },
            'vlan_start': null,
            'cidr': '10.20.0.0/24',
            'group_id': null,
            'gateway': '10.20.0.1'
        }]
    };

    var networkNeutronConfigModel = new models.NetworkConfiguration(dummyNeutronNetworkConfig, {parse: true});

    var networkNovaConfigModel = new models.NetworkConfiguration(dummyNovaNetworkConfig, {parse: true});

    registerSuite({
        'Network Model `get` testing': function () {
            assert.deepEqual(
                networkNeutronConfigModel.get('networking_parameters'),
                dummyNeutronNetworkConfig.networking_parameters,
                'model attributes and actual values do match in case of .get()'
            );

        }
    });

    registerSuite({
        'Network Model toJSON() testing': function () {
            var networksCollection = _.each(dummyNeutronNetworkConfig.networks, function(network) {
                    new models.Network(network);
                }, this),
                networkingParametersModel = new models.NetworkingParameters(dummyNeutronNetworkConfig.networking_parameters);

            assert.deepEqual(
                networkNeutronConfigModel.toJSON(),
                {
                    networks: networksCollection.toJSON(),
                    networking_parameters: networkingParametersModel.toJSON().attributes
                },
                'toJSON() works'
            );

        }
    });

    registerSuite({
        'Network Model isNew() testing': function () {
            assert.notOk(networkNeutronConfigModel.isNew(), 'isNew() is always falsy');

        }
    });

    registerSuite({
        'Network Neutron Model validate() testing': function () {
            assert.ok(networkNeutronConfigModel.isValid(), 'validate() is true for Neutron');

        },
        
        'Network Nova Model validate() testing': function () {
            assert.ok(networkNovaConfigModel.isValid(), 'validate() is true for Nova');
        },

        'Network Neutron Model validate() fails on invalid gateway': function () {
            var networkParameters = networkNeutronConfigModel.get('networking_parameters');
            networkParameters.set('internal_gateway', 'bla');

            //publicNetwork.set('gateway', '172.16.0.2');
            assert.notOk(networkNeutronConfigModel.isValid(), 'validate() is false for Neutron');
        },
        after: function() {
            var networkParameters = networkNeutronConfigModel.get('networking_parameters');
            networkParameters.set('internal_gateway', '192.168.111.1');
        }
    });

});
