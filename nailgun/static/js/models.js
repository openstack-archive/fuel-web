/*
 * Copyright 2013 Mirantis, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
**/
define(['utils', 'deepModel'], function(utils) {
    'use strict';

    var models = {};

    models.Release = Backbone.Model.extend({
        constructorName: 'Release',
        urlRoot: '/api/releases'
    });

    models.Releases = Backbone.Collection.extend({
        constructorName: 'Releases',
        model: models.Release,
        url: '/api/releases',
        comparator: function(release) {
            return release.id;
        }
    });

    models.Cluster = Backbone.Model.extend({
        constructorName: 'Cluster',
        urlRoot: '/api/clusters',
        defaults: function() {
            var defaults = {
                nodes: new models.Nodes(),
                tasks: new models.Tasks()
            };
            defaults.nodes.cluster = defaults.tasks.cluster = this;
            return defaults;
        },
        validate: function(attrs) {
            var errors = {};
            if (!$.trim(attrs.name) || $.trim(attrs.name).length == 0) {
                errors.name = 'Environment name cannot be empty';
            }
            if (!attrs.release) {
                errors.release = 'Please choose OpenStack release';
            }
            return _.isEmpty(errors) ? null : errors;
        },
        groupings: function() {
            return {roles: $.t('cluster_page.nodes_tab.roles'), hardware: $.t('cluster_page.nodes_tab.hardware_info'), both: $.t('cluster_page.nodes_tab.roles_and_hardware_info')};
        },
        task: function(filter1, filter2) {
            var filters = _.isPlainObject(filter1) ? filter1 : {name: filter1, status: filter2};
            return this.get('tasks') && this.get('tasks').findTask(filters);
        },
        tasks: function(filter1, filter2) {
            var filters = _.isPlainObject(filter1) ? filter1 : {name: filter1, status: filter2};
            return this.get('tasks') && this.get('tasks').filterTasks(filters);
        },
        hasChanges: function() {
            return this.get('nodes').hasChanges() || (this.get('changes').length && this.get('nodes').currentNodes().length);
        },
        needsRedeployment: function() {
            return this.get('nodes').where({pending_addition: false, status: 'error'}).length;
        },
        canChangeMode: function(newMode) {
            var nodes = this.get('nodes');
            return !(nodes.currentNodes().length || nodes.where({role: 'controller'}).length > 1 || (newMode && newMode == 'singlenode' && (nodes.length > 1 || (nodes.length == 1 && !nodes.where({role: 'controller'}).length))));
        },
        canAddNodes: function(role) {
            // forbid adding when tasks are running
            if (this.task({group: ['deployment', 'network'], status: 'running'})) {
                return false;
            }
            // forbid add more than 1 controller in simple mode
            if (role == 'controller' && this.get('mode') != 'ha_compact' && _.filter(this.get('nodes').nodesAfterDeployment(), function(node) {return node.get('role') == role;}).length >= 1) {
                return false;
            }
            return true;
        },
        canDeleteNodes: function(role) {
            // forbid deleting when tasks are running
            if (this.task({group: ['deployment', 'network'], status: 'running'})) {
                return false;
            }
            // forbid deleting when there is nothing to delete
            if (!_.filter(this.get('nodes').nodesAfterDeployment(), function(node) {return node.get('role') == role;}).length) {
                return false;
            }
            return true;
        },
        availableModes: function() {
            return ['multinode', 'ha_compact'];
        },
        fetchRelated: function(related, options) {
            return this.get(related).fetch(_.extend({data: {cluster_id: this.id}}, options));
        },
        isAvailableForSettingsChanges: function() {
            return this.get('status') == 'new' || (this.get('status') == 'stopped' && !this.get('nodes').where({status: 'ready'}).length);
        }
    });

    models.Clusters = Backbone.Collection.extend({
        constructorName: 'Clusters',
        model: models.Cluster,
        url: '/api/clusters',
        comparator: function(cluster) {
            return cluster.id;
        }
    });

    models.Node = Backbone.Model.extend({
        constructorName: 'Node',
        urlRoot: '/api/nodes',
        resource: function(resourceName) {
            var resource = 0;
            try {
                if (resourceName == 'cores') {
                    resource = this.get('meta').cpu.total;
                } else if (resourceName == 'hdd') {
                    resource = _.reduce(this.get('meta').disks, function(hdd, disk) {return _.isNumber(disk.size) ?  hdd + disk.size : hdd;}, 0);
                } else if (resourceName == 'ram') {
                    resource = this.get('meta').memory.total;
                } else if (resourceName == 'disks') {
                    resource = _.pluck(this.get('meta').disks, 'size').sort(function(a, b) {return a - b;});
                } else if (resourceName == 'interfaces') {
                    resource = this.get('meta').interfaces.length;
                }
            } catch (ignore) {}
            if (_.isNaN(resource)) {
                resource = 0;
            }
            return resource;
        },
        sortedRoles: function() {
            var preferredOrder = this.collection.cluster.get('release').get('roles');
            return _.union(this.get('roles'), this.get('pending_roles')).sort(function(a, b) {
                return _.indexOf(preferredOrder, a) - _.indexOf(preferredOrder, b);
            });
        },
        canDiscardDeletion: function() {
            return this.get('pending_deletion') && !(_.contains(this.get('roles'), 'controller') && this.collection.cluster.get('mode') == 'multinode' && this.collection.cluster.get('nodes').filter(function(node) {return _.contains(node.get('pending_roles'), 'controller');}).length);
        },
        toJSON: function(options) {
            var result = this.constructor.__super__.toJSON.call(this, options);
            return _.omit(result, 'checked');
        },
        isSelectable: function() {
            return this.get('status') != 'error' || this.get('cluster');
        },
        hasRole: function(role, onlyDeployedRoles) {
            var roles = onlyDeployedRoles ? this.get('roles') : _.union(this.get('roles'), this.get('pending_roles'));
            return _.contains(roles, role);
        },
        getRolesSummary: function() {
            var rolesMetaData = this.collection.cluster.get('release').get('roles_metadata');
            return _.map(this.sortedRoles(), function(role) {return rolesMetaData[role].name;}).join(', ');
        },
        getHardwareSummary: function() {
            return $.t('node_details.hdd') + ': ' + utils.showDiskSize(this.resource('hdd')) + ' \u00A0 ' + $.t('node_details.ram') + ': ' + utils.showMemorySize(this.resource('ram'));
        }
    });

    models.Nodes = Backbone.Collection.extend({
        constructorName: 'Nodes',
        model: models.Node,
        url: '/api/nodes',
        comparator: function(node) {
            return node.id;
        },
        hasChanges: function() {
            return !!this.filter(function(node) {
                return node.get('pending_addition') || node.get('pending_deletion') || node.get('pending_roles').length;
            }).length;
        },
        currentNodes: function() {
            return this.filter(function(node) {return !node.get('pending_addition');});
        },
        nodesAfterDeployment: function() {
            return this.filter(function(node) {return node.get('pending_addition') || !node.get('pending_deletion');});
        },
        nodesAfterDeploymentWithRole: function(role) {
            return _.filter(this.nodesAfterDeployment(), function(node) {return _.contains(_.union(node.get('roles'), node.get('pending_roles')), role);}).length;
        },
        resources: function(resourceName) {
            var resources = this.map(function(node) {return node.resource(resourceName);});
            return _.reduce(resources, function(sum, n) {return sum + n;}, 0);
        },
        getByIds: function(ids) {
            return this.filter(function(node) {return _.contains(ids, node.id);});
        },
        groupByAttribute: function(attr) {
            if (attr == 'roles') {
                return this.groupBy(function(node) {return node.getRolesSummary();});
            }
            if (attr == 'hardware') {
                return this.groupBy(function(node) {return node.getHardwareSummary();});
            }
            return this.groupBy(function(node) {return node.getRolesSummary() + '; \u00A0' + node.getHardwareSummary();});
        }
    });

    models.NodesStatistics = Backbone.Model.extend({
        constructorName: 'NodesStatistics',
        urlRoot: '/api/nodes/allocation/stats'
    });

    models.Task = Backbone.Model.extend({
        constructorName: 'Task',
        urlRoot: '/api/tasks',
        releaseId: function() {
            var id;
            try {
                id = this.get('result').release_info.release_id;
            } catch (ignore) {}
            return id;
        },
        groups: {
            release_setup: ['redhat_setup'],
            network: ['verify_networks', 'check_networks'],
            deployment: ['stop_deployment', 'deploy', 'reset_environment']
        },
        extendGroups: function(filters) {
            return _.union(utils.composeList(filters.name), _.flatten(_.map(utils.composeList(filters.group), _.bind(function(group) {return this.groups[group];}, this))));
        },
        match: function(filters) {
            filters = filters || {};
            var result = false;
            if (filters.group || filters.name) {
                if (_.contains(this.extendGroups(filters), this.get('name'))) {
                    result = true;
                    if (filters.status) {
                        result = _.contains(utils.composeList(filters.status), this.get('status'));
                    }
                    if (filters.release) {
                        result = result && this.releaseId() == filters.release;
                    }
                }
            } else if (filters.status) {
                result = _.contains(utils.composeList(filters.status), this.get('status'));
            }
            return result;
        }
    });

    models.Tasks = Backbone.Collection.extend({
        constructorName: 'Tasks',
        model: models.Task,
        url: '/api/tasks',
        toJSON: function(options) {
            return this.pluck('id');
        },
        comparator: function(task) {
            return task.id;
        },
        filterTasks: function(filters) {
            return _.flatten(_.map(this.model.prototype.extendGroups(filters), function(name) {
                return this.filter(function(task) {
                    return task.match(_.extend(_.omit(filters, 'group'), {name: name}));
                });
            }, this));
        },
        findTask: function(filters) {
            return this.filterTasks(filters)[0];
        }
    });

    models.Notification = Backbone.Model.extend({
        constructorName: 'Notification',
        urlRoot: '/api/notifications'
    });

    models.Notifications = Backbone.Collection.extend({
        constructorName: 'Notifications',
        model: models.Notification,
        url: '/api/notifications',
        comparator: function(notification) {
            return notification.id;
        }
    });

    models.Settings = Backbone.DeepModel.extend({
        constructorName: 'Settings',
        urlRoot: '/api/clusters/',
        isNew: function() {
            return false;
        },
        preferredOrder: ['access', 'additional_components', 'common', 'glance', 'syslog', 'storage']
    });

    models.Disk = Backbone.Model.extend({
        constructorName: 'Disk',
        urlRoot: '/api/nodes/',
        parse: function(response) {
            response.volumes = new models.Volumes(response.volumes);
            response.volumes.disk = this;
            return response;
        },
        toJSON: function(options) {
            return _.extend(this.constructor.__super__.toJSON.call(this, options), {volumes: this.get('volumes').toJSON()});
        },
        getUnallocatedSpace: function(options) {
            options = options || {};
            var volumes = options.volumes || this.get('volumes');
            var allocatedSpace = volumes.reduce(function(sum, volume) {return volume.get('name') == options.skip ? sum : sum + volume.get('size');}, 0);
            return this.get('size') - allocatedSpace;
        },
        validate: function(attrs) {
            var error;
            var unallocatedSpace = this.getUnallocatedSpace({volumes: attrs.volumes});
            if (unallocatedSpace < 0) {
                error = 'Volume groups total size exceeds available space of ' + utils.formatNumber(unallocatedSpace * -1) + ' MB';
            }
            return error;
        }
    });

    models.Disks = Backbone.Collection.extend({
        constructorName: 'Disks',
        model: models.Disk,
        url: '/api/nodes/',
        comparator: function(disk) {
            return disk.get('name');
        }
    });

    models.Volume = Backbone.Model.extend({
        constructorName: 'Volume',
        urlRoot: '/api/volumes/',
        getMinimalSize: function(minimum) {
            var currentDisk = this.collection.disk;
            var groupAllocatedSpace = currentDisk.collection.reduce(function(sum, disk) {return disk.id == currentDisk.id ? sum : sum + disk.get('volumes').findWhere({name: this.get('name')}).get('size');}, 0, this);
            return minimum - groupAllocatedSpace;
        },
        validate: function(attrs, options) {
            var error;
            var min = this.getMinimalSize(options.minimum);
            if (_.isNaN(attrs.size)) {
                error = 'Invalid size';
            } else if (attrs.size < min) {
                error = 'The value is too low. You must allocate at least ' + utils.formatNumber(min) + ' MB';
            }
            return error;
        }
    });

    models.Volumes = Backbone.Collection.extend({
        constructorName: 'Volumes',
        model: models.Volume,
        url: '/api/volumes/'
    });

    models.Interface = Backbone.Model.extend({
        constructorName: 'Interface',
        bondingModes: ['active-backup', 'balance-slb', 'lacp-balance-tcp'],
        parse: function(response) {
            response.assigned_networks = new models.InterfaceNetworks(response.assigned_networks);
            response.assigned_networks.interface = this;
            return response;
        },
        toJSON: function(options) {
            return _.omit(_.extend(this.constructor.__super__.toJSON.call(this, options), {
                assigned_networks: this.get('assigned_networks').toJSON()
            }), 'checked');
        },
        isBond: function() {
            return this.get('type') == 'bond';
        },
        validate: function() {
            var errors = [];
            var networks = new models.Networks(this.get('assigned_networks').invoke('getFullNetwork'));
            var untaggedNetworks = networks.filter(function(network) {
                return !network.get('vlan_start');
            });
            var maxUntaggedNetworksCount = 1;
            // public and floating networks are allowed to be assigned to the same interface
            if (networks.where({name: 'public'}).length && networks.where({name: 'floating'}).length) {
                maxUntaggedNetworksCount += 1;
            }
            // networks with flag "neutron_vlan_range" behave like tagged and allow to have one more untagged network
            maxUntaggedNetworksCount += networks.filter(function(network) {
                return network.get('meta').neutron_vlan_range;
            }).length;
            if (untaggedNetworks.length > maxUntaggedNetworksCount) {
                errors.push($.t('cluster_page.nodes_tab.configure_interfaces.validation.too_many_untagged_networks'));
            }
            return errors;
        }
    });

    models.Interfaces = Backbone.Collection.extend({
        constructorName: 'Interfaces',
        model: models.Interface,
        generateBondName: function() {
            var index, proposedName, base = 'ovs-bond';
            for (index = 0; true; index += 1) {
                proposedName = base + index;
                if (!this.where({name: proposedName}).length) {
                    return proposedName;
                }
            }
        },
        comparator: function(ifc) {
            return [!ifc.isBond(), ifc.get('name')];
        }
    });

    models.InterfaceNetwork = Backbone.Model.extend({
        constructorName: 'InterfaceNetwork'
    });

    models.InterfaceNetworks = Backbone.Collection.extend({
        constructorName: 'InterfaceNetworks',
        model: models.InterfaceNetwork,
        preferredOrder: ['public', 'floating', 'storage', 'management', 'fixed'],
        comparator: function(network) {
            return _.indexOf(this.preferredOrder, network.get('name'));
        }
    });

    models.Network = Backbone.Model.extend({
        constructorName: 'Network',
        getAttributes: function(provider) {
            var attributes;
            if (provider == 'nova_network') {
                attributes = {
                    'floating': ['ip_ranges', 'vlan_start'],
                    'public': ['ip_ranges', 'vlan_start', 'netmask', 'gateway'],
                    'management': ['cidr', 'vlan_start'],
                    'storage': ['cidr', 'vlan_start'],
                    'fixed': ['cidr', 'amount', 'network_size', 'vlan_start'],
                    'fuelweb_admin': []
                };
            }
            if (provider == 'neutron') {
                attributes = {
                    'public': ['ip_ranges', 'vlan_start', 'netmask', 'gateway'],
                    'management': ['cidr', 'vlan_start'],
                    'storage': ['cidr', 'vlan_start'],
                    'private': [],
                    'fuelweb_admin': []
                };
            }
            return attributes[this.get('name')] || ['vlan_start'];
        }
    });

    models.Networks = Backbone.Collection.extend({
        constructorName: 'Networks',
        model: models.Network,
        preferredOrder: ['public', 'floating', 'management', 'storage', 'fixed'],
        comparator: function(network) {
            return _.indexOf(this.preferredOrder, network.get('name'));
        }
    });

    models.NeutronConfiguration = Backbone.DeepModel.extend({
        constructorName: 'NeutronConfiguration'
    });

    models.NovaNetworkConfiguration = Backbone.Model.extend({
        constructorName: 'NovaNetworkConfiguration'
    });

    models.NetworkConfiguration = Backbone.Model.extend({
        constructorName: 'NetworkConfiguration',
        parse: function(response) {
            response.networks = new models.Networks(response.networks);
            response.neutron_parameters = new models.NeutronConfiguration(response.neutron_parameters);
            response.dns_nameservers = new models.NovaNetworkConfiguration(response.dns_nameservers);
            return response;
        },
        toJSON: function() {
            return {
                net_manager: this.get('net_manager'),
                networks: this.get('networks').toJSON(),
                neutron_parameters: this.get('neutron_parameters').toJSON(),
                dns_nameservers: this.get('dns_nameservers').toJSON()
            };
        },
        isNew: function() {
            return false;
        },
        getValidIPRanges: function(network, errors) {
            var invalidRanges = _.pluck(errors, 'index');
            return _.filter(network.get('ip_ranges'), function(range, i) {
                return _.compact(range).length && !_.contains(invalidRanges, i);
            });
        },
        validateIpRange: function(range, errorKeys) {
            var errors = {};
            errorKeys = errorKeys || ['start', 'end', 'both'];
            if (utils.validateIP(range[0])) {
                errors[errorKeys[0]] = {text: 'invalid', params: {opt1: 'ip_start'}};
            } else if (utils.validateIP(range[1])) {
                errors[errorKeys[1]] = {text: 'invalid', params: {opt1: 'ip_end'}};
            } else if (utils.ipToInt(range[0]) - utils.ipToInt(range[1]) > 0) {
                errors[errorKeys[2]] = {text: 'invalid_range', params: {opt1: 'ip_start', opt2: 'ip_end'}};
            }
            return errors;
        },
        validate: function(attrs) {
            var errors = {};
            var fixedNetwork = attrs.networks.findWhere({name: 'fixed'});
            var publicNetwork = attrs.networks.findWhere({name: 'public'});
            var publicIp = _.compact(_.flatten(publicNetwork.get('ip_ranges')))[0];
            var publicCidr = !utils.validateIP(publicIp) && !utils.validateNetmask(publicNetwork.get('netmask')) ? utils.composeCidr(publicIp, publicNetwork.get('netmask')) : null;
            var floatingNetwork = attrs.networks.findWhere({name: 'floating'});
            var floatingIp = _.compact(_.flatten(floatingNetwork.get('ip_ranges')))[0];
            var floatingCidr = !utils.validateIP(floatingIp) && !utils.validateNetmask(floatingNetwork.get('netmask')) ? utils.composeCidr(floatingIp, floatingNetwork.get('netmask')) : null;
            
            // validate networks
            var networksErrors = {};
            var netProvider = attrs.net_manager ? 'nova_network' : 'neutron';
            attrs.networks.each(function(network) {
                var networkErrors = {};
                if (network.has('cidr')) {
                    networkErrors = _.extend(networkErrors, utils.validateCidr(network.get('cidr')));
                }
                if (network.has('netmask') && utils.validateNetmask(network.get('netmask'))) {
                    networkErrors.netmask = {text: 'invalid', params: {opt1: 'netmask'}};
                }
                if (network.has('amount') && network.get('vlan_start')) {
                    if (!utils.isNaturalNumber(network.get('amount'))) {
                        networkErrors.amount = {text: 'invalid', params: {opt1: 'number_of_networks'}};
                    } else if (network.get('amount') > 4095 - network.get('vlan_start')) {
                        networkErrors.amount = {text: 'need_more_vlan'};
                    }
                }
                if (network.has('vlan_start') && network.get('name') != 'floating' && (!_.isNull(network.get('vlan_start')) || (network.get('name') == 'fixed' && attrs.net_manager == 'VlanManager'))) {
                    var vlan = network.get('vlan_start');
                    var forbiddenVlans = _.compact(attrs.networks.map(function(net) {return net.id != network.id && net.get('name') != 'floating' ? net.get('vlan_start') : null;}));
                    if (!utils.isNaturalNumber(vlan) || vlan < 1 || vlan > 4094) {
                        networkErrors.vlan_start = {text: 'invalid', params: {opt1: 'vlan_id'}};
                    } else if (_.contains(forbiddenVlans, vlan) || (netProvider == 'nova_network' && network.get('name') != 'fixed' && utils.validateVlanRange(fixedNetwork.get('vlan_start'), fixedNetwork.get('vlan_start') + fixedNetwork.get('amount') - 1, vlan))) {
                        networkErrors.vlan_start = {text: 'conflicts_with_other_networks', params: {opt1: 'vlan_id'}};
                    }
                }
                var validRanges;
                if (network.has('ip_ranges')) {
                    var networkRanges = network.get('ip_ranges');
                    var ipRangesErrors = [];
                    var notEmptyRanges = _.filter(networkRanges, function(range) {return range[0] || range[1];});
                    if (notEmptyRanges.length) {
                        _.each(notEmptyRanges, function(range) {
                            var error = this.validateIpRange(range);
                            // Public network validation
                            if (_.isEmpty(error)) {
                                // check IP corresponds to CIDR
                                if (network.get('name') == 'public' && publicCidr) {
                                    if (!utils.validateIpCorrespondsToCIDR(publicCidr, range[0])) {
                                        error.start = {text: 'invalid', params: {opt1: 'ip_start'}};
                                    } else if (!utils.validateIpCorrespondsToCIDR(publicCidr, range[1])) {
                                        error.end = {text: 'invalid', params: {opt1: 'ip_end'}};
                                    }
                                }
                                // check IP is not equal to broadcast or subnet addresses
                                var netmask = network.get('netmask');
                                if (_.isEmpty(error) && !networkErrors.netmask) {
                                    var subnetAddress = utils.composeSubnetAddress(range[0], netmask);
                                    if (range[0] == subnetAddress) {
                                        error.start = {text: 'conflicts', params: {opt1: 'ip_start', opt2: 'subnet'}};
                                    } else  if (range[0] == utils.composeBroadcastAddress(subnetAddress, netmask)) {
                                        error.start = {text: 'conflicts', params: {opt1: 'ip_start', opt2: 'broadcast'}};
                                    } else  if (range[1] == subnetAddress) {
                                        error.end = {text: 'conflicts', params: {opt1: 'ip_end', opt2: 'subnet'}};
                                    } else  if (range[1] == utils.composeBroadcastAddress(subnetAddress, netmask)) {
                                        error.end = {text: 'conflicts', params: {opt1: 'ip_end', opt2: 'broadcast'}};
                                    }
                                }
                            }
                            if (!_.isEmpty(error)) {
                                ipRangesErrors.push(_.extend(error, {index: $.inArray(range, networkRanges)}));
                            }
                        }, this);
                        // network IP ranges must not intersect each other
                        validRanges = this.getValidIPRanges(network, ipRangesErrors);
                        _.each(validRanges, function(range1, index1) {
                            _.each(validRanges, function(range2, index2) {
                                if (index1 != index2 && utils.validateIPRangesIntersection(range1, range2)) {
                                    ipRangesErrors.push({index: index1, both: {text: 'ip_ranges_intersection'}});
                                }
                            }, this);
                        }, this);
                    } else {
                        ipRangesErrors.push({index: 0, both: {text: 'empty_ip_range'}});
                    }
                    if (ipRangesErrors.length) {
                        networkErrors.ip_ranges = ipRangesErrors;
                    }
                }
                if (network.has('gateway')) {
                    var gateway = network.get('gateway');
                    var netmask = network.get('netmask');
                    if (utils.validateIP(gateway)) {
                        networkErrors.gateway = {text: 'invalid', params: {opt1: 'gateway'}};
                    } else if (netmask && !networkErrors.netmask) {
                        var subnetAddress = utils.composeSubnetAddress(gateway, netmask);
                        if (gateway == subnetAddress) {
                            networkErrors.gateway = {text: 'conflicts', params: {opt1: 'gateway', opt2: 'subnet'}};
                        } else  if (gateway == utils.composeBroadcastAddress(subnetAddress, netmask)) {
                            networkErrors.gateway = {text: 'conflicts', params: {opt1: 'gateway', opt2: 'broadcast'}};
                        }
                    }
                    if (!networkErrors.netmask && network.get('name') == 'public') {
                        if (publicCidr && !utils.validateIpCorrespondsToCIDR(publicCidr, gateway)) {
                            networkErrors.gateway = {text: 'out_of_public', params: {opt1: 'gateway', opt2: 'ip_range'}};
                        } else { // Public network gateway field must not be in any of Public or Floating IP ranges.
                            var gatewayInt = utils.ipToInt(gateway);
                            _.each(validRanges, function(range) {
                                if (gatewayInt >= utils.ipToInt(range[0]) && gatewayInt <= utils.ipToInt(range[1])) {
                                    networkErrors.gateway = {text: 'conflicts_with_public', params: {opt1: 'gateway', opt2: 'ip_range'}};
                                }
                            }, this);
                        }
                    }
                }
                if (!_.isEmpty(networkErrors)) {
                    networksErrors[network.get('name')] = networkErrors;
                }
            }, this);
            
            // networks CIDR should not intersect each other (except Public and Floating networks)
            var networksToValidate = attrs.networks.filter(function(net) {
                var cidrError;
                try {
                    cidrError = networksErrors[net.get('name')].cidr;
                } catch (ignore) {}
                return net.has('cidr') && !cidrError && net.get('name') != 'fuelweb_admin';
            });
            _.each(networksToValidate, function(network) {
                var cidrs = [];
                _.each(networksToValidate, function(net) {
                    var exception = ['public', 'floating'];
                    if (network.get('name') != net.get('name') && !_.isEqual([network.get('name'), net.get('name')], exception) && !_.isEqual([net.get('name'), network.get('name')], exception)) {
                        if (net.get('name') == 'public') {
                            if (publicCidr) {
                                cidrs.push(publicCidr);
                            }
                        } else if (net.get('name') == 'floating') {
                            if (floatingCidr) {
                                cidrs.push(floatingCidr);
                            }
                        } else {
                            cidrs.push(net.get('cidr'));
                        }
                    }
                });
                _.each(cidrs, function(cidr) {
                    if (utils.validateCIDRIntersection(network.get('cidr'), cidr)) {
                        if (!networksErrors[network.get('name')]) {
                            networksErrors[network.get('name')] = {};
                        }
                        networksErrors[network.get('name')].cidr = {text: 'cidr_intersection'};
                    }
                }, this);
            }, this);
            
            var publicErrors = networksErrors['public'] ? networksErrors['public'].ip_ranges : [];
            var publicRanges = this.getValidIPRanges(publicNetwork, publicErrors);
            // Floating IP ranges should not intersect Public IP ranges and gateway
            if (netProvider == 'nova_network') {
                var floatingErrors = networksErrors.floating ? networksErrors.floating.ip_ranges : [];
                var floatingRanges = this.getValidIPRanges(floatingNetwork, floatingErrors);
                _.each(floatingRanges, function(floatingRange, index) {
                    _.each(publicRanges, function(publicRange) {
                        if (utils.validateIPRangesIntersection(publicRange, floatingRange)) {
                            if (!floatingErrors) {
                                floatingErrors = {ip_ranges: []};
                            } else if (!floatingErrors.ip_ranges) {
                                floatingErrors.ip_ranges = [];
                            }
                            floatingErrors.ip_ranges.push({index: index, both: {text: 'conflicts_with_public', params: {opt1: 'ip_range', opt2: 'ip_range'}}});
                        }
                    }, this);
                }, this);
                if (_.isEmpty(floatingErrors) && (!networksErrors.floating || !networksErrors.floating.ip_ranges)) {
                    _.each(floatingRanges, function(range, index) {
                        if (range[0] == publicNetwork.get('gateway')) {
                            if (!floatingErrors) {
                                floatingErrors = {ip_ranges: []};
                            } else if (!floatingErrors.ip_ranges) {
                                floatingErrors.ip_ranges = [];
                            }
                            floatingErrors.ip_ranges.push({index: index, start: {text: 'conflicts_with_public', params: {opt1: 'ip_start', opt2: 'gateway'}}});
                        } else if (range[1] == publicNetwork.get('gateway')) {
                            if (!floatingErrors) {
                                floatingErrors = {ip_ranges: []};
                            } else if (!floatingErrors.ip_ranges) {
                                floatingErrors.ip_ranges = [];
                            }
                            floatingErrors.ip_ranges.push({index: index, end: {text: 'conflicts_with_public', params: {opt1: 'ip_end', opt2: 'gateway'}}});
                        }
                    }, this);
                }
                if (!_.isEmpty(floatingErrors)) {
                    networksErrors.floating = networksErrors.floating || {};
                    networksErrors.floating.ip_ranges = floatingErrors;
                }
            }
            if (!_.isEmpty(networksErrors)) {
                errors.networks = networksErrors;
            }

            // validate Nova Network configuration
            if (netProvider == 'nova_network') {
                var novaNetworkErrors = {};
                _.each(attrs.dns_nameservers.get('nameservers'), function(nameserver, i) {
                    if (utils.validateIP(nameserver)) {
                        novaNetworkErrors['nameservers-' + i] =  {text: 'invalid', params: {opt1: 'nameserver'}};
                    }
                }, this);
                if (!_.isEmpty(novaNetworkErrors)) {
                    errors.dns_nameservers = novaNetworkErrors;
                }
            }

            // validate Neutron configuration
            if (netProvider == 'neutron') {
                var neutronErrors = {};
                var segmentation = attrs.neutron_parameters.get('segmentation_type');
                var config = attrs.neutron_parameters.get('L2');
                var idRange = segmentation == 'gre' ? config.tunnel_id_ranges : config.phys_nets.physnet2.vlan_range;
                var maxId = segmentation == 'gre' ? 65535 : 4094;

                if (!utils.isNaturalNumber(idRange[0]) || idRange[0] < 2 || idRange[0] > maxId) {
                    neutronErrors.id0 = {text: 'invalid', params: {opt1: 'id_start'}};
                } else if (!utils.isNaturalNumber(idRange[1]) || idRange[1] < 2 || idRange[1] > maxId) {
                    neutronErrors.id1 = {text: 'invalid', params: {opt1: 'id_end'}};
                } else if (idRange[0] > idRange[1]) {
                    neutronErrors.ids = {text: 'invalid', params: {opt1: 'id_range'}};
                } else if (segmentation == 'vlan') {
                    _.each(_.compact(attrs.networks.pluck('vlan_start')), function(vlan) {
                        if (utils.validateVlanRange(idRange[0], idRange[1], vlan)) {
                            neutronErrors.ids = {text: 'conflicts_with_other_networks', params: {opt1: 'vlan_id'}};
                        }
                    }, this);
                }
                if (config.base_mac == '' || !(_.isString(config.base_mac) && config.base_mac.match(utils.regexes.mac))) {
                    neutronErrors.base_mac = {text: 'invalid', params: {opt1: 'base_mac'}};
                }

                config = attrs.neutron_parameters.get('predefined_networks');
                var cidr = config.net04.L3.cidr;
                var gateway = config.net04.L3.gateway;
                var floatingIpRange = config.net04_ext.L3.floating;

                neutronErrors = _.extend(neutronErrors, utils.validateCidr(cidr, 'cidr-int'));
                var floatingRangeErrors = this.validateIpRange(floatingIpRange, ['floating-0', 'floating-1', 'floating-0']);
                neutronErrors = _.extend(neutronErrors, floatingRangeErrors);
                if (publicCidr && _.isEmpty(floatingRangeErrors)) {
                    if (!utils.validateIpCorrespondsToCIDR(publicCidr, floatingIpRange[0])) {
                        neutronErrors['floating-0'] = {text: 'out_of_public', params: {opt1: 'ip_start', opt2: 'ip_range'}};
                    } else if (!utils.validateIpCorrespondsToCIDR(publicCidr, floatingIpRange[1])) {
                        neutronErrors['floating-1'] = {text: 'out_of_public', params: {opt1: 'ip_end', opt2: 'ip_range'}};
                    } else if (floatingIpRange[0] == publicNetwork.get('gateway')) {
                        neutronErrors['floating-0'] = {text: 'conflicts_with_public', params: {opt1: 'ip_start', opt2: 'gateway'}};
                    } else if (floatingIpRange[1] == publicNetwork.get('gateway')) {
                        neutronErrors['floating-1'] = {text: 'conflicts_with_public', params: {opt1: 'ip_end', opt2: 'gateway'}};
                    } else if (utils.validateIPRangesIntersection(publicRanges[0], floatingIpRange)) {
                        neutronErrors['floating-0'] = {text: 'conflicts_with_public', params: {opt1: 'ip_range', opt2: 'ip_range'}};
                    } 
                }
                if (!neutronErrors['floating-0'] && !neutronErrors['floating-1']) {
                    var subnetAddress = config.net04_ext.L3.cidr.split('/')[0];
                    if (floatingIpRange[0] == subnetAddress) {
                        neutronErrors['floating-0'] = {text: 'conflicts_with', params: {opt1: 'ip_start', opt2: 'subnet'}};
                    } else if (floatingIpRange[1] == subnetAddress) {
                        neutronErrors['floating-1'] = {text: 'conflicts_with', params: {opt1: 'ip_end', opt2: 'subnet'}};
                    }/* else if (floatingIpRange[0] == utils.composeBroadcastAddress(subnetAddress, netmask)) {
                        neutronErrors['floating-0'] = {text: 'conflicts_with', params: {opt1: 'ip_start', opt2: 'broadcast'}};
                    } else if (floatingIpRange[1] == utils.composeBroadcastAddress(subnetAddress, netmask)) {
                        neutronErrors['floating-1'] = {text: 'conflicts_with', params: {opt1: 'ip_end', opt2: 'broadcast'}};
                    }*/
                }
                if (_.isEmpty(floatingRangeErrors) && !neutronErrors['cidr-int'] && utils.validateIpCorrespondsToCIDR(cidr, floatingIpRange[0])) {
                    neutronErrors['floating-0'] = {text: 'conflicts_with', params: {opt1: 'ip_range', opt2: 'internal_cidr'}};
                }
                
                if (utils.validateIP(gateway)) {
                    neutronErrors.gateway = {text: 'invalid', params: {opt1: 'gateway'}};
                } else if (!utils.validateIpCorrespondsToCIDR(cidr, gateway)) {
                    neutronErrors.gateway = {text: 'gateway_is_out_of_internal_ip_range'};
                } else if (!neutronErrors['cidr-int'] && !neutronErrors['floating-0'] && utils.validateIpCorrespondsToCIDR(cidr, floatingIpRange[0])) {
                    neutronErrors.gateway = {text: 'conflicts_with', params: {opt1: 'gateway', opt2: 'external_floating'}};
                } else if (gateway == cidr.split('/')[0]) {
                    neutronErrors.gateway = {text: 'conflicts_with', params: {opt1: 'gateway', opt2: 'subnet'}};
                }/* else if (gateway == utils.composeBroadcastAddress(cidr.split('/')[0], netmask)) {
                    neutronErrors.gateway = {text: 'conflicts_with', params: {opt1: 'gateway', opt2: 'broadcast'}};
                }*/
                _.each(config.net04.L3.nameservers, function(nameserver, i) {
                    if (utils.validateIP(nameserver)) {
                        neutronErrors['nameservers-' + i] = {text: 'invalid', params: {opt1: 'nameserver'}};
                    }
                }, this);

                if (!_.isEmpty(neutronErrors)) {
                    errors.neutron_parameters = neutronErrors;
                }
            }
            return _.isEmpty(errors) ? null : errors;
        }
    });

    models.LogSource = Backbone.Model.extend({
        constructorName: 'LogSource',
        urlRoot: '/api/logs/sources'
    });

    models.LogSources = Backbone.Collection.extend({
        constructorName: 'LogSources',
        model: models.LogSource,
        url: '/api/logs/sources'
    });

    models.RedHatAccount = Backbone.Model.extend({
        constructorName: 'RedHatAccount',
        urlRoot: '/api/redhat/account',
        validate: function(attrs) {
            var errors = {};
            var regexes = {
                username: /^[A-z0-9\._%\+\-@]+$/,
                password: /^[\x21-\x7E]+$/,
                satellite: /(^(?:(?!\d+\.)[a-zA-Z0-9_\-]{1,63}\.?)+(?:[a-zA-Z]{2,})$)/,
                activation_key: /^[A-z0-9\*\.\+\-]+$/
            };
            var messages = {
                username: 'Invalid username',
                password: 'Invalid password',
                satellite: 'Only valid fully qualified domain name is allowed for the hostname field',
                activation_key: 'Invalid activation key'
            };
            var fields = ['username', 'password'];
            if (attrs.license_type == 'rhn') {
                fields = _.union(fields, ['satellite', 'activation_key']);
            }
            _.each(fields, function(attr) {
                if (!regexes[attr].test(attrs[attr])) {
                    errors[attr] = messages[attr];
                }
            });
            return _.isEmpty(errors) ? null : errors;
        }
    });

    models.TestSet = Backbone.Model.extend({
        constructorName: 'TestSet',
        urlRoot: '/ostf/testsets'
    });

    models.TestSets = Backbone.Collection.extend({
        constructorName: 'TestSets',
        model: models.TestSet,
        url: '/ostf/testsets'
    });

    models.Test = Backbone.Model.extend({
        constructorName: 'Test',
        urlRoot: '/ostf/tests'
    });

    models.Tests = Backbone.Collection.extend({
        constructorName: 'Tests',
        model: models.Test,
        url: '/ostf/tests'
    });

    models.TestRun = Backbone.Model.extend({
        constructorName: 'TestRun',
        urlRoot: '/ostf/testruns'
    });

    models.TestRuns = Backbone.Collection.extend({
        constructorName: 'TestRuns',
        model: models.TestRun,
        url: '/ostf/testruns'
    });

    models.OSTFClusterMetadata = Backbone.Model.extend({
        constructorName: 'TestRun',
        urlRoot: '/api/ostf'
    });

    models.FuelKey = Backbone.Model.extend({
        constructorName: 'FuelKey',
        urlRoot: '/api/registration/key'
    });

    models.LogsPackage = Backbone.Model.extend({
        constructorName: 'LogsPackage',
        urlRoot: '/api/logs/package'
    });

    models.CapacityLog = Backbone.Model.extend({
        constructorName: 'CapacityLog',
        urlRoot: '/api/capacity'
    });

    return models;
});
