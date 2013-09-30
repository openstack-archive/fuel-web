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
define(['utils'], function(utils) {
    'use strict';

    var models = {};
    var collections = {};

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
            return {roles: 'Roles', hardware: 'Hardware Info', both: 'Roles and hardware info'};
        },
        task: function(taskName, status) {
            return this.get('tasks') && this.get('tasks').findTask({name: taskName, status: status});
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
            if (this.task('deploy', 'running') || this.task('verify_networks', 'running')) {
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
            if (this.task('deploy', 'running') || this.task('verify_networks', 'running')) {
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
        availableRoles: function() {
            return this.get('release').get('roles');
        },
        parse: function(response) {
            response.release = new models.Release(response.release);
            return response;
        },
        fetchRelated: function(related, options) {
            return this.get(related).fetch(_.extend({data: {cluster_id: this.id}}, options));
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
            } catch (e) {}
            if (_.isNaN(resource)) {
                resource = 0;
            }
            return resource;
        },
        sortRoles: function() {
            var preferredOrder = ['controller', 'compute', 'cinder'];
            return _.union(this.get('roles'), this.get('pending_roles')).sort(function(a, b) {
                return _.indexOf(preferredOrder, a) - _.indexOf(preferredOrder, b);
            });
        },
        canDiscardDeletion: function() {
            return this.get('pending_deletion') && !(_.contains(this.get('roles'), 'controller') && this.collection.cluster.get('mode') == 'multinode' && this.collection.cluster.get('nodes').filter(function(node) {return _.contains(node.get('pending_roles'), 'controller');}).length);
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
            } catch(e) {}
            return id;
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
            return _.filter(this.models, function(task) {
                var result = false;
                if (task.get('name') == filters.name) {
                    result = true;
                    if (filters.status) {
                        if (_.isArray(filters.status)) {
                            result = _.contains(filters.status, task.get('status'));
                        } else {
                            result = filters.status == task.get('status');
                        }
                    }
                    if (filters.release) {
                        result = result && filters.release == task.releaseId();
                    }
                }
                return result;
            });
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

    models.Settings = Backbone.Model.extend({
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
            return disk.id;
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
        parse: function(response) {
            response.assigned_networks = new models.InterfaceNetworks(response.assigned_networks);
            return response;
        },
        toJSON: function(options) {
            return _.extend(this.constructor.__super__.toJSON.call(this, options), {assigned_networks: this.get('assigned_networks').toJSON()});
        }
    });

    models.Interfaces = Backbone.Collection.extend({
        constructorName: 'Interfaces',
        model: models.Interface,
        comparator: function(ifc) {
            return ifc.get('name');
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

    models.NodeInterfaceConfiguration = Backbone.Model.extend({
        constructorName: 'NodeInterfaceConfiguration',
        parse: function(response) {
            response.interfaces = new models.Interfaces(response.interfaces);
            return response;
        }
    });

    models.NodeInterfaceConfigurations = Backbone.Collection.extend({
        url: '/api/nodes/interfaces',
        constructorName: 'NodeInterfaceConfigurations',
        model: models.NodeInterfaceConfiguration
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
                    'fixed': ['cidr', 'amount', 'network_size', 'vlan_start']
                };
            }
            if (provider == 'neutron') {
                attributes = {
                    'public': ['cidr', 'vlan_start', 'gateway'],
                    'management': ['cidr', 'vlan_start'],
                    'storage': ['cidr', 'vlan_start']
                };
            }
            return attributes[this.get('name')] || ['vlan_start'];
        },
        validateNetmask: function(value) {
            var valid_values = {0:1, 128:1, 192:1, 224:1, 240:1, 248:1, 252:1, 254:1, 255:1};
            var m = value.split('.');
            var i;

            for (i = 0; i <= 3; i += 1) {
                if (!(valid_values.hasOwnProperty(m[i]))) {
                    return true;
                }
            }
            return false;
        },
        validate: function(attrs, options) {
            var errors = {};
            _.each(this.getAttributes(options.net_provider), _.bind(function(attribute) {
                if (attribute == 'ip_ranges') {
                    if (_.filter(attrs.ip_ranges, function(range) {return !_.isEqual(range, ['', '']);}).length){
                        _.each(attrs.ip_ranges, _.bind(function(range, index) {
                            if (_.first(range) || _.last(range)) {
                                var rangeErrors = {index: index};
                                var start = _.first(range);
                                var end = _.last(range);
                                if (start == '') {
                                    rangeErrors.start = 'Empty IP range start';
                                } else if (utils.validateIP(start)) {
                                    rangeErrors.start = 'Invalid IP range start';
                                }
                                if (end == '') {
                                    rangeErrors.end = 'Empty IP range end';
                                } else if (utils.validateIP(end)) {
                                    rangeErrors.end = 'Invalid IP range end';
                                }
                                if (start != '' && end != '' && !utils.validateIPrange(start, end)) {
                                    rangeErrors.start = rangeErrors.end = 'IP range start is greater than IP range end';
                                }
                                if (rangeErrors.start || rangeErrors.end) {
                                    errors.ip_ranges = _.compact(_.union([rangeErrors], errors.ip_ranges));
                                }
                            }
                        }, this));
                    } else {
                        var rangeErrors = {index: 0};
                        var emptyRangeError = 'Please specify at least one IP range';
                        rangeErrors.start = rangeErrors.end = emptyRangeError;
                        errors.ip_ranges = _.compact(_.union([rangeErrors], errors.ip_ranges));
                    }
                } else if (attribute == 'cidr') {
                    errors = _.extend(errors, utils.validateCidr(attrs.cidr));
                } else if (attribute == 'vlan_start') {
                    if (!_.isNull(attrs.vlan_start) || (attrs.name == 'fixed' && options.net_manager == 'VlanManager')) {
                        if (!utils.isNaturalNumber(attrs.vlan_start) || attrs.vlan_start < 1 || attrs.vlan_start > 4094) {
                            errors.vlan_start = 'Invalid VLAN ID';
                        }
                    }
                } else if (attribute == 'netmask' && this.validateNetmask(attrs.netmask)) {
                    errors.netmask = 'Invalid netmask';
                } else if (attribute == 'gateway' && utils.validateIP(attrs.gateway)) {
                    errors.gateway = 'Invalid gateway';
                } else if (attribute == 'amount') {
                    if (!utils.isNaturalNumber(attrs.amount)) {
                        errors.amount = 'Invalid amount of networks';
                    } else if (attrs.amount && attrs.amount > 4095 - attrs.vlan_start) {
                        errors.amount = 'Number of networks needs more VLAN IDs than available. Check VLAN ID Range field.';
                    }
                }
            }, this));
            return _.isEmpty(errors) ? null : errors;
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

    models.NeutronConfiguration = Backbone.Model.extend({
        constructorName: 'NeutronConfiguration',
        validate: function(attrs) {
            var errors = {};
            _.each(attrs, function(configuration, title) {
                if (title == 'L2') {
                    // ID range validation
                    var id_range = configuration.tunnel_id_ranges || configuration.phys_nets.physnet2.vlan_range;
                    if (!_.compact(id_range).length) {
                        errors.id_range = 'Invalid ID range';
                    } else {
                        if (!_.isNull(id_range[0]) && !_.isNull(id_range[1]) && id_range[0] > id_range[1] ) {
                            errors.id_range = 'ID range start is greater than ID range end';
                        }
                        if (_.isNull(id_range[0]) || !utils.isNaturalNumber(id_range[0]) || id_range[0] < 2 || id_range[0] > 65535) {
                            errors.id_start = 'Invalid ID range start';
                        }
                        if (_.isNull(id_range[1]) || !utils.isNaturalNumber(id_range[1]) || id_range[1] < 2 || id_range[1] > 65535) {
                            errors.id_end = 'Invalid ID range end';
                        }
                    }
                    // base_mac validation
                    var macRegexp = /^([0-9a-fA-F]{2}[:\-]){5}([0-9a-fA-F]{2})$/;
                    var mac = configuration.base_mac;
                    if (mac == '' || !(_.isString(mac) && mac.match(macRegexp))) {
                        errors.base_mac = 'Invalid MAC address';
                    }
                } else if (title == 'predefined_networks') {
                    // CIDR validation
                    errors = _.extend(errors, utils.validateCidr(configuration.net04.L3.cidr, 'cidr-int'));
                    // floating IP range validation
                    var floatingIpRange = configuration.net04_ext.L3.floating;
                    if (floatingIpRange[0] == '') {
                        errors.floating_start = 'Empty IP range start';
                    } else if (utils.validateIP(floatingIpRange[0])) {
                        errors.floating_start = 'Invalid IP range start';
                    }
                    if (floatingIpRange[1] == '') {
                        errors.floating_end = 'Empty IP range end';
                    } else if (utils.validateIP(floatingIpRange[1])) {
                        errors.floating_end = 'Invalid IP range end';
                    }
                    if (floatingIpRange[0] != '' && floatingIpRange[1] != '' && !utils.validateIPrange(floatingIpRange[0], floatingIpRange[1])) {
                        errors.floating = 'IP range start is greater than IP range end';
                    }
                    // nameservers validation
                    _.each(configuration.net04.L3.nameservers, function(nameserver, index) {
                        if (utils.validateIP(nameserver)) {
                            errors['nameserver-' + index] = 'Invalid nameserver';
                        }
                    });
                }
            });
            return _.isEmpty(errors) ? null : errors;
        }
    });

    models.NetworkConfiguration = Backbone.Model.extend({
        constructorName: 'NetworkConfiguration',
        urlRoot: '/api/clusters',
        parse: function(response) {
            response.networks = new models.Networks(response.networks);
            response.neutron_parameters = new models.NeutronConfiguration(response.neutron_parameters);
            return response;
        },
        toJSON: function() {
            return {
                net_manager: this.get('net_manager'),
                networks: this.get('networks').toJSON(),
                neutron_parameters: this.get('neutron_parameters').toJSON()
            };
        },
        isNew: function() {
            return false;
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
