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

    var cacheMixin = {
        fetch: function(options) {
            if (this.cacheFor && options && options.cache && this.lastSyncTime && (this.cacheFor > (new Date() - this.lastSyncTime))) {
                return $.Deferred().resolve();
            }
            return this.constructor.__super__.fetch.apply(this, arguments);
        },
        sync: function(options) {
            if (this.cacheFor) {
                this.lastSyncTime = new Date();
            }
            return this.constructor.__super__.sync.apply(this, arguments);
        }
    };

    models.Release = Backbone.Model.extend({
        constructorName: 'Release',
        urlRoot: '/api/releases'
    });

    models.Releases = Backbone.Collection.extend({
        constructorName: 'Releases',
        model: models.Release,
        url: '/api/releases',
        comparator: function(release1, release2) {
            var version1 = release1.get('version'), version2 = release2.get('version');
            if (version1 == version2) {
                var name1 = release1.get('name').toLowerCase(), name2 = release2.get('name').toLowerCase();
                return name1 > name2 ? 1 : name1 < name2 ? -1 : 0;
            }
            return version1 < version2 ? 1 : -1;
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
            return this.get('nodes').where({pending_addition: false, status: 'error'}).length && (this.get('status') != 'update_error');
        },
        availableModes: function() {
            return ['ha_compact', 'multinode'];
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
        comparator: 'id'
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
        comparator: 'id',
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
            deployment: ['update', 'stop_deployment', 'deploy', 'reset_environment']
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
        comparator: 'id',
        filterTasks: function(filters) {
            return _.flatten(_.map(this.model.prototype.extendGroups(filters), function(name) {
                return this.filter(function(task) {
                    return task.match(_.extend(_.omit(filters, 'group'), {name: name}));
                });
            }, this));
        },
        findTask: function(filters) {
            return this.filterTasks(filters)[0];
        },
        bindToView: function(view, filters, bindCallback, addCallback, removeCallback) {
            bindCallback = _.bind(bindCallback, view);
            addCallback = _.bind(addCallback || view.render, view);
            removeCallback = _.bind(removeCallback || view.render, view);
            function taskMatchesFilters(task) {
                return _.any(filters, task.match, task);
            }
            function onTaskAdd(task) {
                if (taskMatchesFilters(task)) {
                    bindCallback(task);
                    addCallback();
                }
            }
            function onTaskRemove(task) {
                if (taskMatchesFilters(task)) {
                    removeCallback();
                }
            }
            this.each(function(task) {
                if (taskMatchesFilters(task)) {
                    bindCallback(task);
                }
            });
            this.on('add', onTaskAdd, view);
            this.on('remove', onTaskRemove, view);
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
        comparator: 'id'
    });

    models.Settings = Backbone.DeepModel.extend({
        constructorName: 'Settings',
        urlRoot: '/api/clusters/',
        cacheFor: 60 * 1000,
        isNew: function() {
            return false;
        },
        parse: function(response) {
            return response.editable;
        },
        toJSON: function(options) {
            var currentSettings = this.constructor.__super__.toJSON.call(this, options);
            if (this.initialAttributes) {
                var result = _.cloneDeep(this.initialAttributes);
                _.each(currentSettings, function(group, groupName) {
                    _.each(group, function(setting, settingName) {
                        if (settingName == 'metadata') {
                            if (!_.isUndefined(setting.toggleable)) {
                                result[groupName][settingName].enabled = setting.enabled;
                            }
                        } else  {
                            result[groupName][settingName].value = setting.value;
                        }
                    });
                }, this);
                return {editable: result};
            }
            return {editable: currentSettings};
        },
        expandRestrictions: function() {
            _.each(this.attributes, function(group, groupName) {
                _.each(group, function(setting, settingName) {
                    setting.restrictions = _.map(setting.restrictions, utils.expandRestriction);
                    _.each(setting.values, function(value) {
                        value.restrictions = _.map(value.restrictions, utils.expandRestriction);
                    });
                }, this);
            }, this);
        },
        validate: function(attrs) {
            var errors = [];
            _.each(attrs, function(group, groupName) {
                if (group.metadata && (group.metadata.disabled || !group.metadata.visible)) { return; }
                _.each(group, function(setting, settingName) {
                    if (!(setting.regex && setting.regex.source) || setting.disabled) { return; }
                    var regExp = new RegExp(setting.regex.source);
                    if (!setting.value.match(regExp)) {
                        errors.push({
                            field: groupName + '.' + settingName,
                            message: setting.regex.error
                        });
                    }
                });
            });
            return errors.length ? errors : null;
        }
    });
    _.extend(models.Settings.prototype, cacheMixin);

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
        comparator: 'name'
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
        getSlaveInterfaces: function() {
            if (!this.isBond()) {return [this];}
            var slaveInterfaceNames = _.pluck(this.get('slaves'), 'name');
            return this.collection.filter(function(slaveInterface) {
                return _.contains(slaveInterfaceNames, slaveInterface.get('name'));
            });
        },
        validate: function() {
            var errors = [];
            var networks = new models.Networks(this.get('assigned_networks').invoke('getFullNetwork'));
            var untaggedNetworks = networks.filter(function(network) { return _.isNull(network.getVlanRange()); });
            // public and floating networks are allowed to be assigned to the same interface
            var maxUntaggedNetworksCount = networks.where({name: 'public'}).length && networks.where({name: 'floating'}).length ? 2 : 1;
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
        constructorName: 'Network'
    });

    models.Networks = Backbone.Collection.extend({
        constructorName: 'Networks',
        model: models.Network
    });

    models.NetworkingParameters = Backbone.Model.extend({
        constructorName: 'NetworkingParameters'
    });

    models.NetworkConfiguration = Backbone.Model.extend({
        constructorName: 'NetworkConfiguration',
        cacheFor: 60 * 1000,
        parse: function(response) {
            response.networks = new models.Networks(response.networks);
            response.networking_parameters = new models.NetworkingParameters(response.networking_parameters);
            return response;
        },
        toJSON: function() {
            return {
                networks: this.get('networks').toJSON(),
                networking_parameters: this.get('networking_parameters').toJSON()
            };
        },
        isNew: function() {
            return false;
        },
        validate: function(attrs) {
            var errors = {};
            var networksErrors = {};
            var networkingParametersErrors = {};

            // validate networks
            attrs.networks.each(function(network) {
                if (network.get('meta').configurable) {
                    var networkErrors = {};
                    if (network.get('meta').notation == 'ip_ranges') {
                        var ipRangesErrors = utils.validateIpRanges(network.get('ip_ranges'), network.get('cidr'));
                        if (ipRangesErrors.length) {
                            networkErrors.ip_ranges = ipRangesErrors;
                        }
                    }
                    _.extend(networkErrors, utils.validateCidr(network.get('cidr')));
                    if (network.get('meta').use_gateway) {
                        if (utils.validateIP(network.get('gateway'))) {
                            networkErrors.gateway = $.t('cluster_page.network_tab.validation.invalid_gateway');
                        } else if (!utils.validateIpCorrespondsToCIDR(network.get('cidr'), network.get('gateway'))) {
                            networkErrors.gateway = $.t('cluster_page.network_tab.validation.gateway_is_out_of_ip_range');
                        }
                    }
                    var forbiddenVlans = attrs.networks.map(function(net) {return net.id != network.id ? net.get('vlan_start') : null;});
                    _.extend(networkErrors, utils.validateVlan(network.get('vlan_start'), forbiddenVlans, 'vlan_start'));
                    if (!_.isEmpty(networkErrors)) {
                        networksErrors[network.id] = networkErrors;
                    }
                }
            }, this);
            if (!_.isEmpty(networksErrors)) {
                errors.networks = networksErrors;
            }

            // validate networking parameters
            var novaNetManager = attrs.networking_parameters.get('net_manager');
            if (novaNetManager) {
                networkingParametersErrors = _.extend(networkingParametersErrors, utils.validateCidr(attrs.networking_parameters.get('fixed_networks_cidr'), 'fixed_networks_cidr'));
                var fixedAmount = attrs.networking_parameters.get('fixed_networks_amount');
                var fixedVlan = attrs.networking_parameters.get('fixed_networks_vlan_start');
                if (!utils.isNaturalNumber(fixedAmount)) {
                    networkingParametersErrors.fixed_networks_amount = $.t('cluster_page.network_tab.validation.invalid_amount');
                }
                var vlanErrors = utils.validateVlan(fixedVlan, attrs.networks.pluck('vlan_start'), 'fixed_networks_vlan_start', novaNetManager == 'VlanManager');
                _.extend(networkingParametersErrors, vlanErrors);
                if (_.isEmpty(vlanErrors)) {
                    if (!networkingParametersErrors.fixed_networks_amount && fixedAmount > 4095 - fixedVlan) {
                        networkingParametersErrors.fixed_networks_amount = $.t('cluster_page.network_tab.validation.need_more_vlan');
                    }
                    var vlanIntersection = false;
                    _.each(_.compact(attrs.networks.pluck('vlan_start')), function(vlan) {
                        if (utils.validateVlanRange(fixedVlan, fixedVlan + fixedAmount - 1, vlan)) {
                            vlanIntersection = true;
                        }
                    });
                    if (vlanIntersection) {
                        networkingParametersErrors.fixed_networks_vlan_start = $.t('cluster_page.network_tab.validation.vlan_intersection');
                    }
                }
            } else {
                var idRangeErrors = ['', ''];
                var segmentation = attrs.networking_parameters.get('segmentation_type');
                var idRangeAttr = segmentation == 'gre' ? 'gre_id_range' : 'vlan_range';
                var maxId = segmentation == 'gre' ? 65535 : 4094;
                var idRange = attrs.networking_parameters.get(idRangeAttr);
                var idStart = Number(idRange[0]), idEnd = Number(idRange[1]);
                if (!utils.isNaturalNumber(idStart) || idStart < 2 || idStart > maxId) {
                    idRangeErrors[0] = $.t('cluster_page.network_tab.validation.invalid_id_start');
                } else if (!utils.isNaturalNumber(idEnd) || idEnd < 2 || idEnd > maxId) {
                    idRangeErrors[1 ] = $.t('cluster_page.network_tab.validation.invalid_id_end');
                } else if (idStart > idEnd) {
                    idRangeErrors[0] = idRangeErrors[1] = $.t('cluster_page.network_tab.validation.invalid_id_range');
                } else if (segmentation == 'vlan') {
                    _.each(_.compact(attrs.networks.pluck('vlan_start')), function(vlan) {
                        if (utils.validateVlanRange(idStart, idEnd, vlan)) {
                            idRangeErrors[0] = $.t('cluster_page.network_tab.validation.vlan_intersection');
                        }
                        return idRangeErrors[0];
                    });
                }
                if (_.compact(idRangeErrors).length) {
                    networkingParametersErrors[idRangeAttr] = idRangeErrors;
                }
                if (!attrs.networking_parameters.get('base_mac').match(utils.regexes.mac)) {
                    networkingParametersErrors.base_mac = $.t('cluster_page.network_tab.validation.invalid_mac');
                }
                var cidr = attrs.networking_parameters.get('internal_cidr');
                networkingParametersErrors = _.extend(networkingParametersErrors, utils.validateCidr(cidr, 'internal_cidr'));
                var gateway = attrs.networking_parameters.get('internal_gateway');
                if (utils.validateIP(gateway)) {
                    networkingParametersErrors.internal_gateway = $.t('cluster_page.network_tab.validation.invalid_gateway');
                } else if (!utils.validateIpCorrespondsToCIDR(cidr, gateway)) {
                    networkingParametersErrors.internal_gateway = $.t('cluster_page.network_tab.validation.gateway_is_out_of_internal_ip_range');
                }
            }
            var networkWithFloatingRange = attrs.networks.filter(function(network){ return network.get('meta').floating_range_var; })[0];
            var floatingRangesErrors = utils.validateIpRanges(attrs.networking_parameters.get('floating_ranges'), networkWithFloatingRange ? networkWithFloatingRange.get('cidr') : null);
            if (floatingRangesErrors.length) {
                networkingParametersErrors.floating_ranges = floatingRangesErrors;
            }
            var nameserverErrors = [];
            _.each(attrs.networking_parameters.get('dns_nameservers'), function(nameserver, i) {
                nameserverErrors.push(utils.validateIP(nameserver) ? $.t('cluster_page.network_tab.validation.invalid_nameserver') : null);
            });
            if (_.compact(nameserverErrors).length) {
                networkingParametersErrors.dns_nameservers = nameserverErrors;
            }
            if (!_.isEmpty(networkingParametersErrors)) {
                errors.networking_parameters = networkingParametersErrors;
            }
            return _.isEmpty(errors) ? null : errors;
        }
    });
    _.extend(models.NetworkConfiguration.prototype, cacheMixin);

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
        constructorName: 'OSTFClusterMetadata',
        urlRoot: '/api/ostf'
    });

    models.OSTFCredentials = Backbone.Model.extend({
        constructorName: 'OSTFCredentials',
        update: function(settings) {
            var accessSettings = settings.get('access');
            this.set({
                username: accessSettings.user.value,
                password: accessSettings.password.value,
                tenant: accessSettings.tenant.value
            });
        }
    });

    models.FuelKey = Backbone.Model.extend({
        constructorName: 'FuelKey',
        urlRoot: '/api/registration/key'
    });

    models.FuelVersion = Backbone.Model.extend({
        constructorName: 'FuelVersion',
        urlRoot: '/api/version',
        authExempt: true
    });

    models.User = Backbone.Model.extend({
        constructorName: 'User',
        locallyStoredAttributes: ['username', 'password'],
        initialize: function() {
            _.each(this.locallyStoredAttributes, function(attribute) {
                var locallyStoredValue = localStorage.getItem(attribute);
                if (locallyStoredValue) {
                    this.set(attribute, locallyStoredValue);
                }
                this.on('change:' + attribute, function(model, value) {
                    if (_.isUndefined(value)) {
                        localStorage.removeItem(attribute);
                    } else {
                        localStorage.setItem(attribute, value);
                    }
                });
            }, this);
        }
    });

    models.LogsPackage = Backbone.Model.extend({
        constructorName: 'LogsPackage',
        urlRoot: '/api/logs/package'
    });

    models.CapacityLog = Backbone.Model.extend({
        constructorName: 'CapacityLog',
        urlRoot: '/api/capacity'
    });

    models.WizardModel = Backbone.DeepModel.extend({
        constructorName: 'WizardModel',
        parseConfig: function(config) {
            var result = {};
            _.each(config, _.bind(function(paneConfig, paneName) {
                result[paneName] = {};
                _.each(paneConfig, function(attributeConfig, attribute) {
                    var attributeConfigValue = attributeConfig.value;
                    if (_.isUndefined(attributeConfigValue)) {
                        switch (attributeConfig.type) {
                            case 'checkbox':
                                attributeConfigValue = false;
                                break;
                            case 'radio':
                                attributeConfigValue = _.first(attributeConfig.values).data;
                                break;
                            case 'password':
                            case 'text':
                                attributeConfigValue = "";
                                break;
                        }
                    }
                    result[paneName][attribute] = attributeConfigValue;
                });
            }, this));
            return result;
        },
        processConfig: function(config) {
            this.set(this.parseConfig(config));
        },
        restoreDefaultValues: function(panesToRestore) {
            var result = {};
            _.each(this.defaults, _.bind(function(paneConfig, paneName) {
                if (_.contains(panesToRestore, paneName)) {
                    result[paneName] = this.defaults[paneName];
                }
            }, this));
            this.set(result);
        },
        validate: function(attrs, options) {
            var errors = [];
            _.each(options.config, function(attributeConfig, attribute) {
                if (!(attributeConfig.regex && attributeConfig.regex.source)) { return; }
                var hasNoSatisfiedRestrictions =  _.every(_.reject(attributeConfig.restrictions, {action: 'none'}), function(restriction) {
                    // this probably will be changed when other controls need validation
                    return !utils.evaluateExpression(restriction.condition, {default: this}).value;
                }, this);
                if (hasNoSatisfiedRestrictions) {
                    var regExp = new RegExp(attributeConfig.regex.source);
                    if (!this.get(options.paneName + '.' + attribute).match(regExp)) {
                        errors.push({
                            field: attribute,
                            message: $.t(attributeConfig.regex.error)
                        });
                    }
                }
            }, this);
            return errors.length ? errors : null;
        },
        initialize: function(config) {
            this.defaults = this.parseConfig(config);
        }
    });

    return models;
});
