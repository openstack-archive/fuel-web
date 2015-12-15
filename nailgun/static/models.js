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
    'views/custom_controls',
    'deep-model'
], function($, _, i18n, Backbone, utils, Expression, expressionObjects, customControls) {
    'use strict';

    var models = {};

    var superMixin = models.superMixin = {
        _super: function(method, args) {
            var object = this;
            while (object[method] === this[method]) object = object.constructor.__super__;
            return object[method].apply(this, args || []);
        }
    };

    // Mixin for adjusting some collection functions to work properly with model.get.
    // Lodash supports some methods with predicate objects, not functions.
    // Underscore has only pure predicate functions.
    // We need to convert predicate objects to functions that use model's
    // get functionality -- otherwise model.property always returns undefined.

    var collectionMixin = {
        getByIds: function(ids) {
            return this.filter(function(model) {return _.contains(ids, model.id);});
        }
    };

    var collectionMethods = [
        'dropRightWhile', 'dropWhile', 'takeRightWhile', 'takeWhile',
        'findIndex', 'findLastIndex',
        'findKey', 'findLastKey',
        'find', 'detect', 'findLast',
        'filter', 'select', 'reject',
        'every', 'all', 'some', 'any',
        'partition'
    ];

    _.each(collectionMethods, function(method) {
        collectionMixin[method] = function() {
            var args = _.toArray(arguments),
                source = args[0];

            if (_.isPlainObject(source)) {
                args[0] = function(model) {
                    return _.isMatch(model.attributes, source);
                };
            }

            args.unshift(this.models);

            return _[method](...args);
        };
    });

    var BaseModel = models.BaseModel = Backbone.Model.extend(superMixin);
    var BaseCollection = models.BaseCollection = Backbone.Collection.extend(collectionMixin).extend(superMixin);

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
        },
        cancelThrottling: function() {
            delete this.lastSyncTime;
        }
    };
    models.cacheMixin = cacheMixin;

    var restrictionMixin = models.restrictionMixin = {
        expandRestrictions: function(restrictions, path) {
            path = path || 'restrictions';
            this.expandedRestrictions = this.expandedRestrictions || {};
            this.expandedRestrictions[path] = _.map(restrictions, utils.expandRestriction, this);
        },
        checkRestrictions: function(models, action, path) {
            path = path || 'restrictions';
            var restrictions = (this.expandedRestrictions || {})[path];
            if (action) restrictions = _.where(restrictions, {action: action});
            var satisfiedRestrictions = _.filter(restrictions, function(restriction) {
                return new Expression(restriction.condition, models, restriction).evaluate();
            });
            return {result: !!satisfiedRestrictions.length, message: _.compact(_.pluck(satisfiedRestrictions, 'message')).join(' ')};
        },
        expandLimits: function(limits) {
            this.expandedLimits = this.expandedLimits || {};
            this.expandedLimits[this.get('name')] = limits;
        },
        checkLimits: function(models, nodes, checkLimitIsReached = true, limitTypes = ['min', 'max']) {
            /*
             *  Check the 'limits' section of configuration.
             *  models -- current models to check the limits
             *  nodes -- node collection to check the limits
             *  checkLimitIsReached -- boolean (default: true), if true then for min = 1, 1 node is allowed
             *      if false, then for min = 1, 1 node is not allowed anymore
             *      This is because validation runs in 2 modes: validate current model as is
             *      and validate current model checking the possibility of adding/removing node
             *      So if max = 1 and we have 1 node then:
             *        - the model is valid as is (return true) -- case for checkLimitIsReached = true
             *        - there can be no more nodes added (return false) -- case for checkLimitIsReached = false
             *  limitType -- array of limit types to check. Possible choices are 'min', 'max', 'recommended'
            **/

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
                limits = this.expandedLimits[name] || {},
                overrides = limits.overrides || [],
                limitValues = {
                    max: evaluateExpressionHelper(limits.max, models).value,
                    min: evaluateExpressionHelper(limits.min, models).value,
                    recommended: evaluateExpressionHelper(limits.recommended, models).value
                },
                count = nodes.nodesAfterDeploymentWithRole(name).length,
                messages,
                label = this.get('label');

            var checkOneLimit = function(obj, limitType) {
                var limitValue,
                    comparator;

                if (_.isUndefined(obj[limitType])) {
                    return;
                }
                switch (limitType) {
                    case 'min':
                        comparator = checkLimitIsReached ? (a, b) => a < b : (a, b) => a <= b;
                        break;
                    case 'max':
                        comparator = checkLimitIsReached ? (a, b) => a > b : (a, b) => a >= b;
                        break;
                    default:
                        comparator = (a, b) => a < b;
                }
                limitValue = parseInt(evaluateExpressionHelper(obj[limitType], models).value);
                // Update limitValue with overrides, this way at the end we have a flattened limitValues with overrides having priority
                limitValues[limitType] = limitValue;
                checkedLimitTypes[limitType] = true;
                if (comparator(count, limitValue)) {
                    return {
                        type: limitType,
                        value: limitValue,
                        message: obj.message || i18n('common.role_limits.' + limitType, {limitValue: limitValue, count: count, roleName: label})
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

    models.Plugin = BaseModel.extend({
        constructorName: 'Plugin',
        urlRoot: '/api/plugins'
    });

    models.Plugins = BaseCollection.extend({
        constructorName: 'Plugins',
        model: models.Plugin,
        url: '/api/plugins'
    });

    models.Role = BaseModel.extend(restrictionMixin).extend({
        idAttribute: 'name',
        constructorName: 'Role',
        parse: function(response) {
            _.extend(response, _.omit(response.meta, 'name'));
            response.label = response.meta.name;
            delete response.meta;
            return response;
        }
    });

    models.Roles = BaseCollection.extend(restrictionMixin).extend({
        constructorName: 'Roles',
        comparator: 'weight',
        model: models.Role,
        initialize: function() {
            this.processConflictsAndRestrictions();
            this.on('update', this.processConflictsAndRestrictions, this);
        },
        processConflictsAndRestrictions: function() {
            this.each(function(role) {
                role.expandRestrictions(role.get('restrictions'));
                role.expandLimits(role.get('limits'));

                var roleConflicts = role.get('conflicts'),
                    roleName = role.get('name');

                if (roleConflicts == '*') {
                    role.conflicts = _.map(this.reject({name: roleName}), function(role) {
                        return role.get('name');
                    });
                } else {
                    role.conflicts = _.chain(role.conflicts)
                        .union(roleConflicts)
                        .uniq()
                        .compact()
                        .value();
                }

                _.each(role.conflicts, function(conflictRoleName) {
                    var conflictingRole = this.findWhere({name: conflictRoleName});
                    if (conflictingRole) conflictingRole.conflicts = _.uniq(_.union(conflictingRole.conflicts || [], [roleName]));
                }, this);
            }, this);
        }
    });

    models.Release = BaseModel.extend({
        constructorName: 'Release',
        urlRoot: '/api/releases'
    });

    models.ReleaseNetworkProperties = BaseModel.extend({
        constructorName: 'ReleaseNetworkProperties'
    });

    models.Releases = BaseCollection.extend(cacheMixin).extend({
        constructorName: 'Releases',
        cacheFor: 60 * 1000,
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
            if (!_.trim(attrs.name) || _.trim(attrs.name).length == 0) {
                errors.name = 'Environment name cannot be empty';
            }
            if (!attrs.release) {
                errors.release = 'Please choose OpenStack release';
            }
            return _.isEmpty(errors) ? null : errors;
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
        fetchRelated: function(related, options) {
            return this.get(related).fetch(_.extend({data: {cluster_id: this.id}}, options));
        },
        isAvailableForSettingsChanges: function() {
            return !this.get('is_locked');
        },
        isDeploymentPossible: function() {
            var nodes = this.get('nodes');
            return this.get('release').get('state') != 'unavailable' && !!nodes.length &&
                (nodes.hasChanges() || this.needsRedeployment()) && !this.task({group: 'deployment', active: true});
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
        statuses: [
            'ready',
            'pending_addition',
            'pending_deletion',
            'provisioned',
            'provisioning',
            'deploying',
            'discover',
            'error',
            'offline',
            'removing'
        ],
        resource: function(resourceName) {
            var resource = 0;
            try {
                if (resourceName == 'cores') {
                    resource = this.get('meta').cpu.real;
                } else if (resourceName == 'ht_cores') {
                    resource = this.get('meta').cpu.total;
                } else if (resourceName == 'hdd') {
                    resource = _.reduce(this.get('meta').disks, function(hdd, disk) {return _.isNumber(disk.size) ? hdd + disk.size : hdd;}, 0);
                } else if (resourceName == 'ram') {
                    resource = this.get('meta').memory.total;
                } else if (resourceName == 'disks') {
                    resource = _.pluck(this.get('meta').disks, 'size').sort(function(a, b) {return a - b;});
                } else if (resourceName == 'disks_amount') {
                    resource = this.get('meta').disks.length;
                } else if (resourceName == 'interfaces') {
                    resource = this.get('meta').interfaces.length;
                }
            } catch (ignore) {}
            return _.isNaN(resource) ? 0 : resource;
        },
        sortedRoles: function(preferredOrder) {
            return _.union(this.get('roles'), this.get('pending_roles')).sort(function(a, b) {
                return _.indexOf(preferredOrder, a) - _.indexOf(preferredOrder, b);
            });
        },
        isSelectable: function() {
            // forbid removing node from adding to environments
            // and useless management of roles, disks, interfaces, etc.
            return this.get('status') != 'removing';
        },
        hasRole: function(role, onlyDeployedRoles) {
            var roles = onlyDeployedRoles ? this.get('roles') : _.union(this.get('roles'), this.get('pending_roles'));
            return _.contains(roles, role);
        },
        hasChanges() {
            return this.get('pending_addition') ||
                this.get('pending_deletion') ||
                this.get('cluster') && !!this.get('pending_roles').length;
        },
        areDisksConfigurable: function() {
            var status = this.get('status');
            return status == 'discover' || status == 'error';
        },
        areInterfacesConfigurable: function() {
            var status = this.get('status');
            return status == 'discover' || status == 'error' || status == 'provisioned';
        },
        getRolesSummary: function(releaseRoles) {
            return _.map(this.sortedRoles(releaseRoles.pluck('name')), function(role) {
                return releaseRoles.findWhere({name: role}).get('label');
            }).join(', ');
        },
        getStatusSummary: function() {
            // 'offline' status has higher priority
            if (!this.get('online')) return 'offline';
            var status = this.get('status');
            // 'removing' end 'error' statuses have higher priority
            if (_.contains(['removing', 'error'], status)) return status;
            if (this.get('pending_addition')) return 'pending_addition';
            if (this.get('pending_deletion')) return 'pending_deletion';
            return status;
        },
        getLabel: function(label) {
            var labelValue = this.get('labels')[label];
            return _.isUndefined(labelValue) ? false : labelValue;
        }
    });

    models.Nodes = BaseCollection.extend({
        constructorName: 'Nodes',
        model: models.Node,
        url: '/api/nodes',
        comparator: 'id',
        sorters: [
            'cluster',
            'roles',
            'status',
            'name',
            'mac',
            'ip',
            'manufacturer',
            'cores',
            'ht_cores',
            'hdd',
            'disks',
            'ram',
            'interfaces',
            'group_id'
        ],
        filters: [
            'cluster',
            'roles',
            'status',
            'manufacturer',
            'cores',
            'ht_cores',
            'hdd',
            'disks_amount',
            'ram',
            'interfaces',
            'group_id'
        ],
        viewModes: ['standard', 'compact'],
        hasChanges() {
            return _.any(this.invoke('hasChanges'));
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
        },
        getLabelValues: function(label) {
            return this.invoke('getLabel', label);
        },
        areDisksConfigurable: function() {
            if (!this.length) return false;
            var roles = _.union(this.at(0).get('roles'), this.at(0).get('pending_roles')),
                disks = this.at(0).resource('disks');
            return !this.any(function(node) {
                var roleConflict = _.difference(roles, _.union(node.get('roles'), node.get('pending_roles'))).length;
                return roleConflict || !_.isEqual(disks, node.resource('disks'));
            });
        },
        areInterfacesConfigurable: function() {
            if (!this.length) return false;
            return _.uniq(this.invoke('resource', 'interfaces')).length == 1;
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
            deployment: ['update', 'stop_deployment', 'deploy', 'reset_environment', 'spawn_vms']
        },
        extendGroups: function(filters) {
            var names = utils.composeList(filters.name);
            if (_.isEmpty(names)) names = _.flatten(_.values(this.groups));
            var groups = utils.composeList(filters.group);
            if (_.isEmpty(groups)) return names;
            return _.intersection(names, _.flatten(_.values(_.pick(this.groups, groups))));
        },
        extendStatuses: function(filters) {
            var activeTaskStatuses = ['running', 'pending'],
                completedTaskStatuses = ['ready', 'error'],
                statuses = utils.composeList(filters.status);
            if (_.isEmpty(statuses)) {
                statuses = _.union(activeTaskStatuses, completedTaskStatuses);
            }
            if (_.isBoolean(filters.active)) {
                return _.intersection(statuses, filters.active ? activeTaskStatuses : completedTaskStatuses);
            }
            return statuses;
        },
        match: function(filters) {
            filters = filters || {};
            if (!_.isEmpty(filters)) {
                if ((filters.group || filters.name) && !_.contains(this.extendGroups(filters), this.get('name'))) {
                    return false;
                }
                if ((filters.status || _.isBoolean(filters.active)) && !_.contains(this.extendStatuses(filters), this.get('status'))) {
                    return false;
                }
            }
            return true;
        },
        isInfinite: function() {
            return this.match({name: ['stop_deployment', 'reset_environment']});
        },
        isStoppable: function() {
            return this.match({name: 'deploy', status: 'running'});
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
        groupList: ['general', 'security', 'compute', 'network', 'storage', 'logging', 'openstack_services', 'other'],
        isNew: function() {
            return false;
        },
        parse: function(response) {
            return response[this.root];
        },
        toJSON: function() {
            if (!this.root) return this._super('toJSON', arguments);
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
                if ((group.metadata || {}).enabled === false || checkRestrictions(this.makePath(groupName, 'metadata')).result) return;
                _.each(group, function(setting, settingName) {
                    var path = this.makePath(groupName, settingName);
                    if (checkRestrictions(path).result) return;

                    // support of custom controls
                    var CustomControl = customControls[setting.type];
                    if (CustomControl) {
                        var error = CustomControl.validate(setting, models);
                        if (error) errors[path] = error;
                        return;
                    }

                    if (!(setting.regex || {}).source) return;
                    if (!setting.value.match(new RegExp(setting.regex.source))) errors[path] = setting.regex.error;
                }, this);
            }, this);
            return _.isEmpty(errors) ? null : errors;
        },
        makePath: function(...args) {
            return args.join('.');
        },
        getValueAttribute: function(settingName) {
            return settingName == 'metadata' ? 'enabled' : 'value';
        },
        hasChanges: function(initialAttributes, models) {
            return _.any(this.attributes, function(group, groupName) {
                var metadata = group.metadata,
                    result = false;
                if (metadata) {
                    if (this.checkRestrictions(models, null, this.makePath(groupName, 'metadata')).result) return result;
                    if (!_.isUndefined(metadata.enabled)) result = metadata.enabled != initialAttributes[groupName].metadata.enabled;
                }
                return result || _.any(group, function(setting, settingName) {
                    if (this.checkRestrictions(models, null, this.makePath(groupName, settingName)).result) return false;
                    return !_.isEqual(setting.value, initialAttributes[groupName][settingName].value);
                }, this);
            }, this);
        },
        sanitizeGroup: function(group) {
            return _.contains(this.groupList, group) ? group : 'other';
        },
        getGroupList: function() {
            var groups = [];
            _.each(this.attributes, function(section) {
                if (section.metadata.group) {
                    groups.push(this.sanitizeGroup(section.metadata.group));
                } else {
                    _.each(section, function(setting, settingName) {
                        if (settingName != 'metadata') groups.push(this.sanitizeGroup(setting.group));
                    }, this);
                }
            }, this);
            return _.intersection(this.groupList, groups);
        }
    });

    models.FuelSettings = models.Settings.extend({
        constructorName: 'FuelSettings',
        url: '/api/settings',
        root: 'settings',
        parse: function(response) {
            return _.extend(this._super('parse', arguments), {master_node_uid: response.master_node_uid});
        }
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
                error = i18n('cluster_page.nodes_tab.configure_disks.validation_error', {size: utils.formatNumber(unallocatedSpace * -1)});
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
            var currentDisk = this.collection.disk,
                groupAllocatedSpace = 0;
            if (currentDisk && currentDisk.collection)
                groupAllocatedSpace = currentDisk.collection.reduce(function(sum, disk) {return disk.id == currentDisk.id ? sum : sum + disk.get('volumes').findWhere({name: this.get('name')}).get('size');}, 0, this);
            return minimum - groupAllocatedSpace;
        },
        getMaxSize: function() {
            var volumes = this.collection.disk.get('volumes'),
                diskAllocatedSpace = volumes.reduce(function(total, volume) {return this.get('name') == volume.get('name') ? total : total + volume.get('size');}, 0, this);
            return this.collection.disk.get('size') - diskAllocatedSpace;
        },
        validate: function(attrs, options) {
            var min = this.getMinimalSize(options.minimum);
            if (attrs.size < min) {
                return i18n('cluster_page.nodes_tab.configure_disks.volume_error', {size: utils.formatNumber(min)});
            }
            return null;
        }
    });

    models.Volumes = BaseCollection.extend({
        constructorName: 'Volumes',
        model: models.Volume,
        url: '/api/volumes/'
    });

    models.Interface = BaseModel.extend({
        constructorName: 'Interface',
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
        validate: function(attrs) {
            var errors = [];
            var networks = new models.Networks(this.get('assigned_networks').invoke('getFullNetwork', attrs.networks));
            var untaggedNetworks = networks.filter(function(network) { return _.isNull(network.getVlanRange(attrs.networkingParameters)); });
            var ns = 'cluster_page.nodes_tab.configure_interfaces.validation.';
            // public and floating networks are allowed to be assigned to the same interface
            var maxUntaggedNetworksCount = networks.any({name: 'public'}) && networks.any({name: 'floating'}) ? 2 : 1;
            if (untaggedNetworks.length > maxUntaggedNetworksCount) {
                errors.push(i18n(ns + 'too_many_untagged_networks'));
            }
            var interfaceProperties = this.get('interface_properties');
            if (interfaceProperties && interfaceProperties.mtu) {
                var mtuValue = interfaceProperties.mtu;
                if (mtuValue && (mtuValue < 42 || mtuValue > 65536)) {
                    errors.push(i18n(ns + 'invalid_mtu'));
                }
            }
            return errors;
        }
    });

    models.Interfaces = BaseCollection.extend({
        constructorName: 'Interfaces',
        model: models.Interface,
        generateBondName: function(base) {
            var index, proposedName;
            for (index = 0; ; index += 1) {
                proposedName = base + index;
                if (!this.any({name: proposedName})) return proposedName;
            }
        },
        comparator: function(ifc1, ifc2) {
            return utils.multiSort(ifc1, ifc2, [{attr: 'isBond'}, {attr: 'name'}]);
        }
    });

    var networkPreferredOrder = ['public', 'floating', 'storage', 'management', 'private', 'fixed', 'baremetal'];

    models.InterfaceNetwork = BaseModel.extend({
        constructorName: 'InterfaceNetwork',
        getFullNetwork: function(networks) {
            return networks.findWhere({name: this.get('name')});
        }
    });

    models.InterfaceNetworks = BaseCollection.extend({
        constructorName: 'InterfaceNetworks',
        model: models.InterfaceNetwork,
        comparator: function(network) {
            return _.indexOf(networkPreferredOrder, network.get('name'));
        }
    });

    models.Network = BaseModel.extend({
        constructorName: 'Network',
        getVlanRange: function(networkingParameters) {
            if (!this.get('meta').neutron_vlan_range) {
                var externalNetworkData = this.get('meta').ext_net_data;
                var vlanStart = externalNetworkData ? networkingParameters.get(externalNetworkData[0]) : this.get('vlan_start');
                return _.isNull(vlanStart) ? vlanStart : [vlanStart, externalNetworkData ? vlanStart + networkingParameters.get(externalNetworkData[1]) - 1 : vlanStart];
            }
            return networkingParameters.get('vlan_range');
        }
    });

    models.Networks = BaseCollection.extend({
        constructorName: 'Networks',
        model: models.Network,
        comparator: function(network) {
            return _.indexOf(networkPreferredOrder, network.get('name'));
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
        validate: function(attrs) {
            var errors = {},
                networkingParametersErrors = {},
                ns = 'cluster_page.network_tab.validation.',
                networks = attrs.networks,
                networkParameters = attrs.networking_parameters,
                nodeNetworkGroupsErrors = {},
                nodeNetworkGroups = app.nodeNetworkGroups,
                novaNetManager = networkParameters.get('net_manager'),
                floatingRangesErrors;

            nodeNetworkGroups.map(function(nodeNetworkGroup) {
                var currentNetworks = new models.Networks(networks.where({group_id: nodeNetworkGroup.id}));
                var nodeNetworkGroupErrors = {};
                // validate networks
                currentNetworks.each(function(network) {
                    var networkErrors = {};
                    if (network.get('meta').configurable) {
                        var cidr = network.get('cidr');
                        _.extend(networkErrors, utils.validateCidr(cidr));
                        var cidrError = _.has(networkErrors, 'cidr');
                        if (network.get('meta').notation == 'ip_ranges') {
                            var ipRangesErrors = utils.validateIPRanges(network.get('ip_ranges'), cidrError ? null : cidr);
                            if (ipRangesErrors.length) {
                                networkErrors.ip_ranges = ipRangesErrors;
                            }
                        }
                        if (network.get('meta').use_gateway) {
                            if (!utils.validateIP(network.get('gateway'))) {
                                networkErrors.gateway = i18n(ns + 'invalid_gateway');
                            } else if (!cidrError && !utils.validateIpCorrespondsToCIDR(cidr, network.get('gateway'))) {
                                networkErrors.gateway = i18n(ns + 'gateway_is_out_of_ip_range');
                            }
                        }
                        //FIXME (morale): same VLAN IDs are not permitted for nova-network for now
                        var forbiddenVlans = [];
                        if (novaNetManager) {
                            forbiddenVlans = currentNetworks.map(function(net) {
                                return net.id != network.id ? net.get('vlan_start') : null;
                            });
                        }
                        _.extend(networkErrors, utils.validateVlan(network.get('vlan_start'), forbiddenVlans, 'vlan_start'));
                        if (!_.isEmpty(networkErrors)) {
                            nodeNetworkGroupErrors[network.id] = networkErrors;
                        }
                        if (network.get('name') == 'baremetal') {
                            var baremetalCidrError = _.has(nodeNetworkGroupErrors[network.id], 'cidr'),
                                baremetalGateway = networkParameters.get('baremetal_gateway');
                            if (!utils.validateIP(baremetalGateway)) {
                                networkingParametersErrors.baremetal_gateway = i18n(ns + 'invalid_gateway');
                            } else if (!baremetalCidrError && !utils.validateIpCorrespondsToCIDR(cidr, baremetalGateway)) {
                                networkingParametersErrors.baremetal_gateway = i18n(ns + 'gateway_is_out_of_baremetal_network');
                            }
                            var baremetalRangeErrors = utils.validateIPRanges([networkParameters.get('baremetal_range')], baremetalCidrError ? null : cidr);
                            if (baremetalRangeErrors.length) {
                                var [{start, end}] = baremetalRangeErrors;
                                networkingParametersErrors.baremetal_range = [start, end];
                            }
                        }
                    }
                }, this);
                if (!_.isEmpty(nodeNetworkGroupErrors)) {
                    nodeNetworkGroupsErrors[nodeNetworkGroup.id] = nodeNetworkGroupErrors;
                }
            }, this);

            if (!_.isEmpty(nodeNetworkGroupsErrors)) {
                errors.networks = nodeNetworkGroupsErrors;
            }

            // validate networking parameters
            if (novaNetManager) {
                networkingParametersErrors = _.extend(networkingParametersErrors, utils.validateCidr(networkParameters.get('fixed_networks_cidr'), 'fixed_networks_cidr'));
                var fixedAmount = networkParameters.get('fixed_networks_amount');
                var fixedVlan = networkParameters.get('fixed_networks_vlan_start');
                if (!utils.isNaturalNumber(parseInt(fixedAmount))) {
                    networkingParametersErrors.fixed_networks_amount = i18n(ns + 'invalid_amount');
                }
                var vlanErrors = utils.validateVlan(fixedVlan, networks.pluck('vlan_start'), 'fixed_networks_vlan_start', novaNetManager == 'VlanManager');
                _.extend(networkingParametersErrors, vlanErrors);
                if (_.isEmpty(vlanErrors)) {
                    if (!networkingParametersErrors.fixed_networks_amount && fixedAmount > 4095 - fixedVlan) {
                        networkingParametersErrors.fixed_networks_amount = i18n(ns + 'need_more_vlan');
                    }
                    var vlanIntersection = false;
                    _.each(_.compact(networks.pluck('vlan_start')), function(vlan) {
                        if (utils.validateVlanRange(fixedVlan, fixedVlan + fixedAmount - 1, vlan)) {
                            vlanIntersection = true;
                        }
                    });
                    if (vlanIntersection) {
                        networkingParametersErrors.fixed_networks_vlan_start = i18n(ns + 'vlan_intersection');
                    }
                }
                floatingRangesErrors = utils.validateIPRanges(networkParameters.get('floating_ranges'), null);
                if (floatingRangesErrors.length) {
                    networkingParametersErrors.floating_ranges = floatingRangesErrors;
                }
            } else {
                var idRangeErrors = ['', ''];
                var segmentation = networkParameters.get('segmentation_type');
                var idRangeAttr = segmentation == 'vlan' ? 'vlan_range' : 'gre_id_range';
                var maxId = segmentation == 'vlan' ? 4094 : 65535;
                var idRange = networkParameters.get(idRangeAttr);
                var idStart = Number(idRange[0]), idEnd = Number(idRange[1]);
                if (!utils.isNaturalNumber(idStart) || idStart < 2 || idStart > maxId) {
                    idRangeErrors[0] = i18n(ns + 'invalid_id_start');
                } else if (!utils.isNaturalNumber(idEnd) || idEnd < 2 || idEnd > maxId) {
                    idRangeErrors[1] = i18n(ns + 'invalid_id_end');
                } else if (idStart > idEnd) {
                    idRangeErrors[0] = idRangeErrors[1] = i18n(ns + 'invalid_id_range');
                } else if (segmentation == 'vlan') {
                    _.each(_.compact(networks.pluck('vlan_start')), function(vlan) {
                        if (utils.validateVlanRange(idStart, idEnd, vlan)) {
                            idRangeErrors[0] = i18n(ns + 'vlan_intersection');
                        }
                        return idRangeErrors[0];
                    });
                }
                if (_.compact(idRangeErrors).length) {
                    networkingParametersErrors[idRangeAttr] = idRangeErrors;
                }
                if (!networkParameters.get('base_mac').match(utils.regexes.mac)) {
                    networkingParametersErrors.base_mac = i18n(ns + 'invalid_mac');
                }
                var cidr = networkParameters.get('internal_cidr');
                networkingParametersErrors = _.extend(networkingParametersErrors, utils.validateCidr(cidr, 'internal_cidr'));
                var gateway = networkParameters.get('internal_gateway');
                if (!utils.validateIP(gateway)) {
                    networkingParametersErrors.internal_gateway = i18n(ns + 'invalid_gateway');
                } else if (!utils.validateIpCorrespondsToCIDR(cidr, gateway)) {
                    networkingParametersErrors.internal_gateway = i18n(ns + 'gateway_is_out_of_internal_network');
                }
                var networkNamesRegExp = /^[a-z][\w\-]*$/i;
                _.each(['internal_name', 'floating_name'], (paramName) => {
                    if (!networkParameters.get(paramName).match(networkNamesRegExp)) {
                        networkingParametersErrors[paramName] = i18n(ns + 'invalid_name');
                    }
                });

                var floatingRanges = networkParameters.get('floating_ranges'),
                    networkToCheckFloatingRange = networks.find((network) => {
                        if (!network.get('meta').floating_range_var) return false;
                        var cidrError = false;
                        try {
                            cidrError = !!errors.networks[network.get('group_id')][network.id].cidr;
                        } catch (error) {}
                        if (cidrError) return false;
                        return utils.validateIpCorrespondsToCIDR(network.get('cidr'), floatingRanges[0][0]) &&
                            utils.validateIpCorrespondsToCIDR(network.get('cidr'), floatingRanges[0][1]);
                    });

                var networkToCheckFloatingRangeData = networkToCheckFloatingRange ? {
                        cidr: networkToCheckFloatingRange.get('cidr'),
                        network: _.capitalize(networkToCheckFloatingRange.get('name')),
                        nodeNetworkGroup: nodeNetworkGroups.get(networkToCheckFloatingRange.get('group_id')).get('name')
                    } : {},
                    networkToCheckFloatingRangeIPRanges = networkToCheckFloatingRange ? _.filter(networkToCheckFloatingRange.get('ip_ranges'), (range, index) => {
                        var ipRangeError = false;
                        try {
                            ipRangeError = !_.all(range) || !!_.find(errors.networks[networkToCheckFloatingRange.get('group_id')][networkToCheckFloatingRange.id].ip_ranges, {index: index});
                        } catch (error) {}
                        return !ipRangeError;
                    }) : [];

                floatingRangesErrors = utils.validateIPRanges(
                    floatingRanges,
                    networkToCheckFloatingRangeData.cidr,
                    networkToCheckFloatingRangeIPRanges,
                    {
                        IP_RANGES_INTERSECTION: i18n(ns + 'floating_and_public_ip_ranges_intersection', networkToCheckFloatingRangeData),
                        IP_RANGE_IS_NOT_IN_PUBLIC_CIDR: i18n(ns + 'floating_range_is_not_in_public_cidr')
                    }
                );

                if (floatingRangesErrors.length) {
                    networkingParametersErrors.floating_ranges = floatingRangesErrors;
                }
            }
            var nameserverErrors = [];
            _.each(networkParameters.get('dns_nameservers'), function(nameserver) {
                nameserverErrors.push(!utils.validateIP(nameserver) ? i18n(ns + 'invalid_nameserver') : null);
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
                var hasNoSatisfiedRestrictions = _.every(_.reject(attributeConfig.restrictions, {action: 'none'}), function(restriction) {
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

    models.MirantisCredentials = Backbone.DeepModel.extend(superMixin).extend({
        constructorName: 'MirantisCredentials',
        baseUrl: 'https://software.mirantis.com/wp-content/themes/mirantis_responsive_v_1_0/scripts/fuel_forms_api/',
        validate: function(attrs) {
            var errors = {};
            _.each(attrs, function(group, groupName) {
                _.each(group, function(setting, settingName) {
                    var path = this.makePath(groupName, settingName);
                    if (!setting.regex || !setting.regex.source) return;
                    if (!setting.value.match(new RegExp(setting.regex.source))) errors[path] = setting.regex.error;
                }, this);
            }, this);
            return _.isEmpty(errors) ? null : errors;
        },
        makePath: function(...args) {
            return args.join('.');
        }
    });

    models.MirantisLoginForm = models.MirantisCredentials.extend({
        constructorName: 'MirantisLoginForm',
        url: function() {
            return this.baseUrl + 'login';
        },
        nailgunUrl: 'api/tracking/login'
    });

    models.MirantisRegistrationForm = models.MirantisCredentials.extend({
        constructorName: 'MirantisRegistrationForm',
        url: function() {
            return this.baseUrl + 'registration';
        },
        nailgunUrl: 'api/tracking/registration'
    });

    models.MirantisRetrievePasswordForm = models.MirantisCredentials.extend({
        constructorName: 'MirantisRetrievePasswordForm',
        url: function() {
            return this.baseUrl + 'restore_password';
        },
        nailgunUrl: 'api/tracking/restore_password'
    });

    models.NodeNetworkGroup = BaseModel.extend({
        constructorName: 'NodeNetworkGroup',
        urlRoot: '/api/nodegroups',
        isDefault: function() {
            return _.min(_.pluck(this.collection.where({cluster_id: this.get('cluster_id')}), 'id')) == this.id;
        },
        validate: function(options) {
            var newName = options.name,
                networkTabNS = 'cluster_page.network_tab.',
                nodeNetworkGroups = this.collection || options.nodeNetworkGroups;
            if (!nodeNetworkGroups) return null;
            if (newName.toLowerCase() == 'default') {
                return i18n(networkTabNS + 'node_network_group_default_name');
            }
            if (_.contains(nodeNetworkGroups.pluck('name'), newName)) {
                return i18n(networkTabNS + 'node_network_group_duplicate_error');
            }
            if (!newName.match(utils.regexes.nodeNetworkGroupName)) {
                return i18n(networkTabNS + 'validation.invalid_node_network_group_name');
            }
            return null;
        }
    });

    models.NodeNetworkGroups = BaseCollection.extend(cacheMixin).extend({
        constructorName: 'NodeNetworkGroups',
        cacheFor: 60 * 1000,
        model: models.NodeNetworkGroup,
        url: '/api/nodegroups',
        comparator: 'id'
    });

    models.PluginLink = BaseModel.extend({
        constructorName: 'PluginLink'
    });

    models.PluginLinks = BaseCollection.extend(cacheMixin).extend({
        constructorName: 'PluginLinks',
        cacheFor: 60 * 1000,
        model: models.PluginLink,
        comparator: 'id'
    });

    class ComponentPattern {
        constructor(pattern) {
            this.pattern = pattern;
            this.parts = pattern.split(':');
            this.hasWildcard = _.contains(this.parts, '*');
        }
        match(componentName) {
            if (!this.hasWildcard) {
                return this.pattern == componentName;
            }

            var componentParts = componentName.split(':');
            if (componentParts.length < this.parts.length) {
                return false;
            }
            var matched = true;
            _.each(this.parts, (part, index) => {
                if (part == '*') {
                    return;
                }
                if (part != componentParts[index]) {
                    matched = false;
                    return matched;
                }
            });
            return matched;
        }
    }

    models.ComponentModel = BaseModel.extend({
        initialize: function(component) {
            var parts = component.name.split(':');
            this.set({
                id: component.name,
                enabled: component.enabled,
                type: parts[0],
                subtype: parts[1],
                name: component.name,
                label: i18n(component.label),
                description: component.description && i18n(component.description),
                compatible: component.compatible,
                incompatible: component.incompatible,
                weight: component.weight || 100
            });
        },
        expandWildcards: function(components) {
            var expandProperty = (propertyName, components) => {
                var expandedComponents = [];
                _.each(this.get(propertyName), (patternDescription) => {
                    var patternName = _.isString(patternDescription) ? patternDescription : patternDescription.name;
                    var pattern = new ComponentPattern(patternName);
                    components.each((component) => {
                        if (pattern.match(component.id)) {
                            expandedComponents.push({
                                component: component,
                                message: i18n(patternDescription.message || '')
                            });
                        }
                    });
                });
                return expandedComponents;
            };

            this.set({
                compatible: expandProperty('compatible', components),
                incompatible: expandProperty('incompatible', components),
                requires: expandProperty('requires', components)
            });
        },
        restoreDefaultValue: function() {
            this.set({enabled: this.get('default')});
        },
        toJSON: function() {
            return this.get('enabled') ? this.id : null;
        },
        isML2Driver: function() {
            return /:ml2:\w+$/.test(this.id);
        }
    });

    models.ComponentsCollection = BaseCollection.extend({
        model: models.ComponentModel,
        allTypes: ['hypervisor', 'network', 'storage', 'additional_service'],
        initialize: function(models, options) {
            this.releaseId = options.releaseId;
        },
        url: function() {
            return '/api/v1/releases/' + this.releaseId + '/components';
        },
        parse: function(response) {
            return _.isArray(response) ? response : [];
        },
        getComponentsByType: function(type, options = {sorted: true}) {
            var components = this.where({type: type});
            if (options.sorted) {
                components.sort((component1, component2) => {
                    return component1.get('weight') - component2.get('weight');
                });
            }
            return components;
        },
        restoreDefaultValues: function(types) {
            types = types || this.allTypes;
            var components = _.filter(this.models, (model) => _.contains(types, model.get('type')));
            _.invoke(components, 'restoreDefaultValue');
        },
        toJSON: function() {
            return _.compact(_.map(this.models, (model) => model.toJSON()));
        }
    });

    return models;
});
