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
define([
    'jquery',
    'underscore',
    'i18n',
    'backbone',
    'utils',
    'expression',
    'expression/objects',
    'deepModel'
], function($, _, i18n, Backbone, utils, Expression, expressionObjects) {
    'use strict';

    var models = {};

    var superMixin = {
        _super: function(method, args) {
            var object = this;
            while (object[method] === this[method]) object = object.constructor.__super__;
            return object[method].apply(this, args || []);
        }
    };

    var BaseModel = models.BaseModel = Backbone.Model.extend(superMixin);
    var BaseCollection = models.BaseCollection = Backbone.Collection.extend({
        getByIds: function(ids) {
            return this.filter(function(model) {return _.contains(ids, model.id);});
        }
    }).extend(superMixin);

    var cacheMixin = {
        fetch: function(options) {
            if (this.cacheFor && options && options.cache && this.lastSyncTime && (this.cacheFor > (new Date() - this.lastSyncTime))) {
                return $.Deferred().resolve();
            }
            return this._super('fetch', arguments);
        },
        sync: function() {
            var deferred = this._super('sync', arguments);
            if (this.cacheFor) {
                deferred.done(_.bind(function() {
                    this.lastSyncTime = new Date();
                }, this));
            }
            return deferred;
        }
    };

    var restrictionMixin = {
        expandRestrictions: function(restrictions, path) {
            path = path || 'restrictions';
            this.expandedRestrictions = this.expandedRestrictions || {};
            this.expandedRestrictions[path] = _.map(restrictions, utils.expandRestriction, this);
        },
        checkRestrictions: function(models, action, path) {
            path = path || 'restrictions';
            var restrictions = this.expandedRestrictions[path];
            if (action) restrictions = _.where(restrictions, {action: action});
            var satisfiedRestrictions = _.filter(restrictions, function(restriction) {
                return new Expression(restriction.condition, models).evaluate();
            });
            return {result: !!satisfiedRestrictions.length, message: _.compact(_.pluck(satisfiedRestrictions, 'message')).join(' ')};
        },
        expandLimits: function(limits) {
            this.expandedLimits = this.expandedLimits || {};
            this.expandedLimits[this.get('name')] = limits;
        },
        checkLimits: function(models, checkLimitIsReached, limitTypes) {
            /*
             *  Check the 'limits' section of configuration.
             *  models -- current model to check the limits
             *  checkLimitIsReached -- boolean (default: true), if true then for min = 1, 1 node is allowed
             *      if false, then for min = 1, 1 node is not allowed anymore
             *      This is because validation runs in 2 modes: validate current model as is
             *      and validate current model checking the possibility of adding/removing node
             *      So if max = 1 and we have 1 node then:
             *        - the model is valid as is (return true) -- case for checkLimitIsReached = true
             *        - there can be no more nodes added (return false) -- case for checkLimitIsReached = false
             *  limitType -- array of limit types to check. Possible choices are 'min', 'max', 'recommended'
            **/

            // Default values
            if (_.isUndefined(checkLimitIsReached)) checkLimitIsReached = true;
            if (_.isUndefined(limitTypes)) limitTypes = ['min', 'max'];

            var evaluateExpressionHelper = function(expression, models, options) {
                var ret;

                if (_.isUndefined(expression)) {
                    return {value: undefined, modelPaths: {}};
                } else if (_.isNumber(expression)) {
                    return {value: expression, modelPaths: {}};
                }

                ret = utils.evaluateExpression(expression, models, options);

                if (ret.value instanceof expressionObjects.ModelPath) {
                    ret.value = ret.value.model.get(ret.value.attribute);
                }

                return ret;
            };

            var checkedLimitTypes = {},
                name = this.get('name'),
                nodes = models.cluster.get('nodes'),
                limits = this.expandedLimits[name] || {},
                overrides = limits.overrides || [],
                limitValues = {
                    max: evaluateExpressionHelper(limits.max, models).value,
                    min: evaluateExpressionHelper(limits.min, models).value,
                    recommended: evaluateExpressionHelper(limits.recommended, models).value
                },
                count = nodes.nodesAfterDeploymentWithRole(name).length,
                messages;

            var checkOneLimit = function(obj, limitType) {
                var limitValue,
                    comparator;

                if (_.isUndefined(obj[limitType])) {
                    return;
                }
                switch (limitType) {
                    case 'min':
                        comparator = checkLimitIsReached ? function(a, b) {return a < b;} : function(a, b) {return a <= b;};
                        break;
                    case 'max':
                        comparator = checkLimitIsReached ? function(a, b) {return a > b;} : function(a, b) {return a >= b;};
                        break;
                    default:
                        comparator = function(a, b) {return a < b;};
                }
                limitValue = parseInt(evaluateExpressionHelper(obj[limitType], models).value);
                // Update limitValue with overrides, this way at the end we have a flattened limitValues with overrides having priority
                limitValues[limitType] = limitValue;
                checkedLimitTypes[limitType] = true;
                if (comparator(count, limitValue)) {
                    return {
                        type: limitType,
                        value: limitValue,
                        message: obj.message || i18n('common.role_limits.' + limitType, {limitValue: limitValue, count: count, roleName: name})
                    };
                }
            };

            // Check the overridden limit types
            messages = _.chain(overrides)
                .map(function(override) {
                    var exp = evaluateExpressionHelper(override.condition, models).value;

                    if (exp) {
                        return _.map(limitTypes, _.partial(checkOneLimit, override));
                    }
                })
                .flatten()
                .compact()
                .value();
            // Now check the global, not-overridden limit types
            messages = messages.concat(_.chain(limitTypes)
                .map(function(limitType) {
                    if (checkedLimitTypes[limitType]) {
                        return;
                    }

                    return checkOneLimit(limitValues, limitType);
                })
                .flatten()
                .compact()
                .value()
            );
            // There can be multiple messages for same limit type
            // (for example, multiple 'min' messages) coming from
            // multiple override methods. We pick a single, worst
            // message, i.e. for 'min' and 'recommended' types we
            // pick one with maximal value, for 'max' type we pick
            // the minimal one.
            messages = _.map(limitTypes, function(limitType) {
                    var message = _.chain(messages)
                        .filter({type: limitType})
                        .sortBy('value')
                        .value();
                    if (limitType != 'max') {
                        message = message.reverse();
                    }
                    if (message[0]) {
                        return message[0].message;
                    }
            });
            messages = _.compact(messages).join(' ');

            return {
                count: count,
                limits: limitValues,
                message: messages,
                valid: !messages
            };
        }
    };

    models.Role = BaseModel.extend(restrictionMixin).extend({
        constructorName: 'Role'
    });

    models.Roles = BaseCollection.extend(restrictionMixin).extend({
        constructorName: 'Roles',
        model: models.Role,
        processConflicts: function() {
            this.each(function(role) {
                role.conflicts = _.chain(role.conflicts)
                    .union(role.get('conflicts'))
                    .uniq()
                    .compact()
                    .value();
                _.each(role.get('conflicts'), function(conflict) {
                    var conflictingRole = this.findWhere({name: conflict});
                    conflictingRole.conflicts = conflictingRole.conflicts || [];
                    conflictingRole.conflicts.push(role.get('name'));
                }, this);
            }, this);
        }
    });

    models.Release = BaseModel.extend({
        constructorName: 'Release',
        urlRoot: '/api/releases',
        parse: function(response) {
            response.role_models = new models.Roles(_.map(response.roles, function(roleName) {
                var roleData = response.roles_metadata[roleName];
                roleData.label = roleData.name;
                return _.extend(roleData, {name: roleName});
            }));
            response.role_models.each(function(role) {
                role.expandRestrictions(role.get('restrictions'));
                role.expandLimits(role.get('limits'));
            });
            response.role_models.processConflicts();
            delete response.roles_metadata;
            return response;
        }
    });

    models.Releases = BaseCollection.extend({
        constructorName: 'Releases',
        model: models.Release,
        url: '/api/releases'
    });

    models.Cluster = BaseModel.extend({
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
            return {roles: i18n('cluster_page.nodes_tab.roles'), hardware: i18n('cluster_page.nodes_tab.hardware_info'), both: i18n('cluster_page.nodes_tab.roles_and_hardware_info')};
        },
        task: function(filter1, filter2) {
            var filters = _.isPlainObject(filter1) ? filter1 : {name: filter1, status: filter2};
            return this.get('tasks') && this.get('tasks').findTask(filters);
        },
        tasks: function(filter1, filter2) {
            var filters = _.isPlainObject(filter1) ? filter1 : {name: filter1, status: filter2};
            return this.get('tasks') && this.get('tasks').filterTasks(filters);
        },
        needsRedeployment: function() {
            return this.get('nodes').any({pending_addition: false, status: 'error'}) && this.get('status') != 'update_error';
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

    models.Clusters = BaseCollection.extend({
        constructorName: 'Clusters',
        model: models.Cluster,
        url: '/api/clusters',
        comparator: 'id'
    });

    models.Node = BaseModel.extend({
        constructorName: 'Node',
        urlRoot: '/api/nodes',
        resource: function(resourceName) {
            var resource = 0;
            try {
                if (resourceName == 'cores') {
                    resource = this.get('meta').cpu.real;
                } else if (resourceName == 'ht_cores') {
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
        sortedRoles: function(preferredOrder) {
            return _.union(this.get('roles'), this.get('pending_roles')).sort(function(a, b) {
                return _.indexOf(preferredOrder, a) - _.indexOf(preferredOrder, b);
            });
        },
        isSelectable: function() {
            return this.get('status') != 'error' || this.get('cluster');
        },
        hasRole: function(role, onlyDeployedRoles) {
            var roles = onlyDeployedRoles ? this.get('roles') : _.union(this.get('roles'), this.get('pending_roles'));
            return _.contains(roles, role);
        },
        hasChanges: function() {
            return this.get('pending_addition') || this.get('pending_deletion');
        },
        getRolesSummary: function(releaseRoles) {
            return _.map(this.sortedRoles(releaseRoles.pluck('name')), function(role) {
                return releaseRoles.findWhere({name: role}).get('label');
            }).join(', ');
        },
        getHardwareSummary: function() {
            return i18n('node_details.hdd') + ': ' + utils.showDiskSize(this.resource('hdd')) + ' \u00A0 ' + i18n('node_details.ram') + ': ' + utils.showMemorySize(this.resource('ram'));
        }
    });

    models.Nodes = BaseCollection.extend({
        constructorName: 'Nodes',
        model: models.Node,
        url: '/api/nodes',
        comparator: function(node1, node2) {
            return utils.multiSort(node1, node2, [{attr: 'online', desc: true}, {attr: 'id'}]);
        },
        hasChanges: function() {
            return !!this.filter(function(node) {
                return node.get('pending_addition') || node.get('pending_deletion') || node.get('pending_roles').length;
            }).length;
        },
        nodesAfterDeployment: function() {
            return this.filter(function(node) {return !node.get('pending_deletion');});
        },
        nodesAfterDeploymentWithRole: function(role) {
            return _.filter(this.nodesAfterDeployment(), function(node) {return node.hasRole(role);});
        },
        resources: function(resourceName) {
            var resources = this.map(function(node) {return node.resource(resourceName);});
            return _.reduce(resources, function(sum, n) {return sum + n;}, 0);
        }
    });

    models.NodesStatistics = BaseModel.extend({
        constructorName: 'NodesStatistics',
        urlRoot: '/api/nodes/allocation/stats'
    });

    models.Task = BaseModel.extend({
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

    models.Tasks = BaseCollection.extend({
        constructorName: 'Tasks',
        model: models.Task,
        url: '/api/tasks',
        toJSON: function() {
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

    models.Notification = BaseModel.extend({
        constructorName: 'Notification',
        urlRoot: '/api/notifications'
    });

    models.Notifications = BaseCollection.extend({
        constructorName: 'Notifications',
        model: models.Notification,
        url: '/api/notifications',
        comparator: function(notification) {
            return -notification.id;
        }
    });

    models.Settings = Backbone.DeepModel.extend(superMixin).extend(cacheMixin).extend(restrictionMixin).extend({
        constructorName: 'Settings',
        urlRoot: '/api/clusters/',
        root: 'editable',
        cacheFor: 60 * 1000,
        isNew: function() {
            return false;
        },
        parse: function(response) {
            return response[this.root];
        },
        toJSON: function() {
            var data = {};
            data[this.root] = this._super('toJSON', arguments);
            return data;
        },
        processRestrictions: function() {
            _.each(this.attributes, function(group, groupName) {
                if (group.metadata) {
                    this.expandRestrictions(group.metadata.restrictions, groupName + '.metadata');
                }
                _.each(group, function(setting, settingName) {
                    this.expandRestrictions(setting.restrictions, this.makePath(groupName, settingName));
                    _.each(setting.values, function(value) {
                        this.expandRestrictions(value.restrictions, this.makePath(groupName, settingName, value.data));
                    }, this);
                }, this);
            }, this);
        },
        initialize: function() {
            // FIXME(vkramskikh): this will work only if there won't be
            // any restrictions added later in the same model
            this.once('change', this.processRestrictions, this);
        },
        validate: function(attrs, options) {
            var errors = {},
                models = options ? options.models : {},
                checkRestrictions = _.bind(function(path) {
                    return this.checkRestrictions(models, null, path);
                }, this);
            _.each(attrs, function(group, groupName) {
                if (checkRestrictions(this.makePath(groupName, 'metadata')).result) return;
                _.each(group, function(setting, settingName) {
                    var path = this.makePath(groupName, settingName);
                    if (!setting.regex || !setting.regex.source || checkRestrictions(path).result) return;
                    if (!setting.value.match(new RegExp(setting.regex.source))) errors[path] = setting.regex.error;
                }, this);
            }, this);
            return _.isEmpty(errors) ? null : errors;
        },
        makePath: function() {
            return _.toArray(arguments).join('.');
        },
        hasChanges: function(initialAttributes, models) {
            return _.any(this.attributes, function(group, groupName) {
                if (group.metadata && this.checkRestrictions(models, null, this.makePath(groupName, 'metadata')).result) return false;
                return _.any(group, function(setting, settingName) {
                    if (this.checkRestrictions(models, null, this.makePath(groupName, settingName)).result) return false;
                    return setting.value != initialAttributes[groupName][settingName].value;
                }, this);
            }, this);
        }
    });

    models.FuelSettings = models.Settings.extend({
        constructorName: 'FuelSettings',
        url: '/api/settings',
        root: 'settings'
    });

    models.Disk = BaseModel.extend({
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

    models.Disks = BaseCollection.extend({
        constructorName: 'Disks',
        model: models.Disk,
        url: '/api/nodes/',
        comparator: 'name'
    });

    models.Volume = BaseModel.extend({
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

    models.Volumes = BaseCollection.extend({
        constructorName: 'Volumes',
        model: models.Volume,
        url: '/api/volumes/'
    });

    models.Interface = BaseModel.extend({
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
            var untaggedNetworks = networks.filter(function(network) {return _.isNull(network.getVlanRange());});
            // public and floating networks are allowed to be assigned to the same interface
            var maxUntaggedNetworksCount = networks.where({name: 'public'}).length && networks.where({name: 'floating'}).length ? 2 : 1;
            if (untaggedNetworks.length > maxUntaggedNetworksCount) {
                errors.push(i18n('cluster_page.nodes_tab.configure_interfaces.validation.too_many_untagged_networks'));
            }
            return errors;
        }
    });

    models.Interfaces = BaseCollection.extend({
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
        comparator: function(ifc1, ifc2) {
            return utils.multiSort(ifc1, ifc2, [{attr: 'isBond'}, {attr: 'name'}]);
        }
    });

    models.InterfaceNetwork = BaseModel.extend({
        constructorName: 'InterfaceNetwork'
    });

    models.InterfaceNetworks = BaseCollection.extend({
        constructorName: 'InterfaceNetworks',
        model: models.InterfaceNetwork,
        preferredOrder: ['public', 'floating', 'storage', 'management', 'fixed'],
        comparator: function(network) {
            return _.indexOf(this.preferredOrder, network.get('name'));
        }
    });

    models.Network = BaseModel.extend({
        constructorName: 'Network'
    });

    models.Networks = BaseCollection.extend({
        constructorName: 'Networks',
        model: models.Network,
        preferredOrder: ['public', 'floating', 'storage', 'management', 'fixed'],
        comparator: function(network) {
            return _.indexOf(this.preferredOrder, network.get('name'));
        }
    });

    models.NetworkingParameters = BaseModel.extend({
        constructorName: 'NetworkingParameters'
    });

    models.NetworkConfiguration = BaseModel.extend(cacheMixin).extend({
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
            } else if (utils.ipIntRepresentation(range[0]) - utils.ipIntRepresentation(range[1]) > 0) {
                errors[errorKeys[2]] = {text: 'invalid_range', params: {opt1: 'ip_start', opt2: 'ip_end'}};
            }
            return errors;
        },
        validate: function(attrs) {
            debugger;
            var errors = {},
                networksErrors = {},
                networkingParametersErrors = {},
                fixedNetwork = attrs.networks.findWhere({name: 'fixed'}),
                publicNetwork = attrs.networks.findWhere({name: 'public'}),
                publicIp = _.compact(_.flatten(publicNetwork.get('ip_ranges')))[0],
                publicCidr = !utils.validateIP(publicIp) ? publicNetwork.get('cidr') : null,
                floatingIpRanges = _.compact(_.flatten(attrs.networking_parameters.get('floating_ranges')))[0];

            // validate networks
            var netProvider = attrs.net_manager ? 'nova_network' : 'neutron';
            attrs.networks.each(function(network) {
                if (network.get('meta').configurable) {
                    var networkErrors = {};
                    if (network.has('cidr')) {
                        networkErrors = _.extend(networkErrors, utils.validateCidr(network.get('cidr')));
                    }
                    if (network.has('amount') && network.get('vlan_start')) {
                        if (!utils.isNaturalNumber(network.get('amount'))) {
                            networkErrors.amount = {text: 'invalid', params: {opt1: 'number_of_networks'}};
                        } else if (network.get('amount') > 4095 - network.get('vlan_start')) {
                            networkErrors.amount = {text: 'need_more_vlan'};
                        }
                    }
                    if (network.has('vlan_start') && network.get('name') != 'floating' &&
                        (!_.isNull(network.get('vlan_start')) || (network.get('name') == 'fixed' && attrs.net_manager == 'VlanManager'))) {
                        var vlan = network.get('vlan_start');
                        var forbiddenVlans = _.compact(attrs.networks.map(function (net) {
                            return net.id != network.id && net.get('name') != 'floating' ? net.get('vlan_start') : null;
                        }));
                        if (!utils.isNaturalNumber(vlan) || vlan < 1 || vlan > 4094) {
                            networkErrors.vlan_start = {text: 'invalid', params: {opt1: 'vlan_id'}};
                        } else if (_.contains(forbiddenVlans, vlan) || (netProvider == 'nova_network' && network.get('name') != 'fixed' &&
                            utils.validateVlanRange(fixedNetwork.get('vlan_start'), fixedNetwork.get('vlan_start') + fixedNetwork.get('amount') - 1, vlan))) {
                            networkErrors.vlan_start = {
                                text: 'conflicts_with_other_networks',
                                params: {opt1: 'vlan_id'}
                            };
                        }
                    }
                    var validRanges;
                    if (network.has('ip_ranges')) {
                        var networkRanges = network.get('ip_ranges');
                        var ipRangesErrors = [];
                        var notEmptyRanges = _.filter(networkRanges, function (range) {
                            return range[0] || range[1];
                        });
                        if (notEmptyRanges.length) {
                            _.each(notEmptyRanges, function (range) {
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
                                    //// check IP is not equal to broadcast or subnet addresses
                                    //var netmask = network.get('netmask');
                                    //if (_.isEmpty(error) && !networkErrors.netmask) {
                                    //    var subnetAddress = utils.composeSubnetAddress(range[0], netmask);
                                    //    if (range[0] == subnetAddress) {
                                    //        error.start = {
                                    //            text: 'conflicts',
                                    //            params: {opt1: 'ip_start', opt2: 'subnet'}
                                    //        };
                                    //    } else if (range[0] == utils.composeBroadcastAddress(subnetAddress, netmask)) {
                                    //        error.start = {
                                    //            text: 'conflicts',
                                    //            params: {opt1: 'ip_start', opt2: 'broadcast'}
                                    //        };
                                    //    } else if (range[1] == subnetAddress) {
                                    //        error.end = {text: 'conflicts', params: {opt1: 'ip_end', opt2: 'subnet'}};
                                    //    } else if (range[1] == utils.composeBroadcastAddress(subnetAddress, netmask)) {
                                    //        error.end = {
                                    //            text: 'conflicts',
                                    //            params: {opt1: 'ip_end', opt2: 'broadcast'}
                                    //        };
                                    //    }
                                    //}
                                }
                                if (!_.isEmpty(error)) {
                                    ipRangesErrors.push(_.extend(error, {index: $.inArray(range, networkRanges)}));
                                }
                            }, this);
                            // network IP ranges must not intersect each other
                            validRanges = this.getValidIPRanges(network, ipRangesErrors);
                            _.each(validRanges, function (range1, index1) {
                                _.each(validRanges, function (range2, index2) {
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
                            } else if (gateway == utils.composeBroadcastAddress(subnetAddress, netmask)) {
                                networkErrors.gateway = {
                                    text: 'conflicts',
                                    params: {opt1: 'gateway', opt2: 'broadcast'}
                                };
                            }
                        }
                        if (!networkErrors.netmask && network.get('name') == 'public') {
                            if (publicCidr && !utils.validateIpCorrespondsToCIDR(publicCidr, gateway)) {
                                networkErrors.gateway = {
                                    text: 'out_of_public',
                                    params: {opt1: 'gateway', opt2: 'ip_range'}
                                };
                            } else { // Public network gateway field must not be in any of Public or Floating IP ranges.
                                var gatewayInt = utils.ipIntRepresentation(gateway);
                                _.each(validRanges, function (range) {
                                    if (gatewayInt >= utils.ipIntRepresentation(range[0]) && gatewayInt <= utils.ipIntRepresentation(range[1])) {
                                        networkErrors.gateway = {
                                            text: 'conflicts_with_public',
                                            params: {opt1: 'gateway', opt2: 'ip_range'}
                                        };
                                    }
                                }, this);
                            }
                        }
                    }
                    if (!_.isEmpty(networkErrors)) {
                        networksErrors[network.get('name')] = networkErrors;
                    }
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
            //if (netProvider == 'nova_network') {
            //    var floatingErrors = networksErrors.floating ? networksErrors.floating.ip_ranges : [];
            //    var floatingRanges = this.getValidIPRanges(floatingNetwork, floatingErrors);
            //    _.each(floatingRanges, function(floatingRange, index) {
            //        _.each(publicRanges, function(publicRange) {
            //            if (utils.validateIPRangesIntersection(publicRange, floatingRange)) {
            //                if (!floatingErrors) {
            //                    floatingErrors = {ip_ranges: []};
            //                } else if (!floatingErrors.ip_ranges) {
            //                    floatingErrors.ip_ranges = [];
            //                }
            //                floatingErrors.ip_ranges.push({index: index, both: {text: 'conflicts_with_public', params: {opt1: 'ip_range', opt2: 'ip_range'}}});
            //            }
            //        }, this);
            //    }, this);
            //    if (_.isEmpty(floatingErrors) && (!networksErrors.floating || !networksErrors.floating.ip_ranges)) {
            //        _.each(floatingRanges, function(range, index) {
            //            if (range[0] == publicNetwork.get('gateway')) {
            //                if (!floatingErrors) {
            //                    floatingErrors = {ip_ranges: []};
            //                } else if (!floatingErrors.ip_ranges) {
            //                    floatingErrors.ip_ranges = [];
            //                }
            //                floatingErrors.ip_ranges.push({index: index, start: {text: 'conflicts_with_public', params: {opt1: 'ip_start', opt2: 'gateway'}}});
            //            } else if (range[1] == publicNetwork.get('gateway')) {
            //                if (!floatingErrors) {
            //                    floatingErrors = {ip_ranges: []};
            //                } else if (!floatingErrors.ip_ranges) {
            //                    floatingErrors.ip_ranges = [];
            //                }
            //                floatingErrors.ip_ranges.push({index: index, end: {text: 'conflicts_with_public', params: {opt1: 'ip_end', opt2: 'gateway'}}});
            //            }
            //        }, this);
            //    }
            //    if (!_.isEmpty(floatingErrors)) {
            //        networksErrors.floating = networksErrors.floating || {};
            //        networksErrors.floating.ip_ranges = floatingErrors;
            //    }
            //}
            if (!_.isEmpty(networksErrors)) {
                errors.networks = networksErrors;
            }

            // validate Nova Network configuration
            //if (netProvider == 'nova_network') {
            //    var novaNetworkErrors = {};
            //    _.each(attrs.dns_nameservers.get('nameservers'), function(nameserver, i) {
            //        if (utils.validateIP(nameserver)) {
            //            novaNetworkErrors['nameservers-' + i] =  {text: 'invalid', params: {opt1: 'nameserver'}};
            //        }
            //    }, this);
            //    if (!_.isEmpty(novaNetworkErrors)) {
            //        errors.dns_nameservers = novaNetworkErrors;
            //    }
            //}

            // validate Neutron configuration
            if (netProvider == 'neutron') {
                var neutronErrors = {};
                var parameters = attrs.networking_parameters;
                var segmentation = parameters.get('segmentation_type');
                var idRange = segmentation == 'gre' ? parameters.get('gre_id_range') : parameters;
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
                if (parameters.base_mac == '' || !(_.isString(parameters.base_mac) && parameters.base_mac.match(utils.regexes.mac))) {
                    neutronErrors.base_mac = {text: 'invalid', params: {opt1: 'base_mac'}};
                }

                var gateway = parameters.internal_gateway,
                    cidr = parameters.internal_cidr;


                if (utils.validateIP(gateway)) {
                    neutronErrors.gateway = {text: 'invalid', params: {opt1: 'gateway'}};
                } else if (!utils.validateIpCorrespondsToCIDR(cidr, gateway)) {
                    neutronErrors.gateway = {text: 'gateway_is_out_of_internal_ip_range'};
                } else if (!neutronErrors['cidr-int'] && !neutronErrors['floating-0'] && utils.validateIpCorrespondsToCIDR(cidr, floatingIpRanges[0])) {
                    neutronErrors.gateway = {text: 'conflicts_with', params: {opt1: 'gateway', opt2: 'external_floating'}};
                } else if (gateway == cidr.split('/')[0]) {
                    neutronErrors.gateway = {text: 'conflicts_with', params: {opt1: 'gateway', opt2: 'subnet'}};
                }/* else if (gateway == utils.composeBroadcastAddress(cidr.split('/')[0], netmask)) {
                    neutronErrors.gateway = {text: 'conflicts_with', params: {opt1: 'gateway', opt2: 'broadcast'}};
                }*/

                if (!_.isEmpty(neutronErrors)) {
                    errors.networking_parameters = neutronErrors;
                }
            }
            return _.isEmpty(errors) ? null : errors;
        }
    });

    models.LogSource = BaseModel.extend({
        constructorName: 'LogSource',
        urlRoot: '/api/logs/sources'
    });

    models.LogSources = BaseCollection.extend({
        constructorName: 'LogSources',
        model: models.LogSource,
        url: '/api/logs/sources'
    });

    models.TestSet = BaseModel.extend({
        constructorName: 'TestSet',
        urlRoot: '/ostf/testsets'
    });

    models.TestSets = BaseCollection.extend({
        constructorName: 'TestSets',
        model: models.TestSet,
        url: '/ostf/testsets'
    });

    models.Test = BaseModel.extend({
        constructorName: 'Test',
        urlRoot: '/ostf/tests'
    });

    models.Tests = BaseCollection.extend({
        constructorName: 'Tests',
        model: models.Test,
        url: '/ostf/tests'
    });

    models.TestRun = BaseModel.extend({
        constructorName: 'TestRun',
        urlRoot: '/ostf/testruns'
    });

    models.TestRuns = BaseCollection.extend({
        constructorName: 'TestRuns',
        model: models.TestRun,
        url: '/ostf/testruns'
    });

    models.OSTFClusterMetadata = BaseModel.extend({
        constructorName: 'OSTFClusterMetadata',
        urlRoot: '/api/ostf'
    });

    models.FuelKey = BaseModel.extend({
        constructorName: 'FuelKey',
        urlRoot: '/api/registration/key'
    });

    models.FuelVersion = BaseModel.extend({
        constructorName: 'FuelVersion',
        urlRoot: '/api/version',
        authExempt: true
    });

    models.User = BaseModel.extend({
        constructorName: 'User',
        locallyStoredAttributes: ['username', 'token'],
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

    models.LogsPackage = BaseModel.extend({
        constructorName: 'LogsPackage',
        urlRoot: '/api/logs/package'
    });

    models.CapacityLog = BaseModel.extend({
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
                                attributeConfigValue = '';
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
                if (!(attributeConfig.regex && attributeConfig.regex.source)) {return;}
                var hasNoSatisfiedRestrictions =  _.every(_.reject(attributeConfig.restrictions, {action: 'none'}), function(restriction) {
                    // this probably will be changed when other controls need validation
                    return !utils.evaluateExpression(restriction.condition, {default: this}).value;
                }, this);
                if (hasNoSatisfiedRestrictions) {
                    var regExp = new RegExp(attributeConfig.regex.source);
                    if (!this.get(options.paneName + '.' + attribute).match(regExp)) {
                        errors.push({
                            field: attribute,
                            message: i18n(attributeConfig.regex.error)
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
