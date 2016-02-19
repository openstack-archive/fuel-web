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

import $ from 'jquery';
import _ from 'underscore';
import i18n from 'i18n';
import Backbone from 'backbone';
import Expression from 'expression';
import {ModelPath} from 'expression/objects';
import utils from 'utils';
import customControls from 'views/custom_controls';
import 'deep-model';

var models = {};

var makePathMixin = {
  makePath(...args) {
    return args.join('.');
  }
};

var superMixin = models.superMixin = {
  _super(method, args) {
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
  getByIds(ids) {
    return this.filter((model) => _.contains(ids, model.id));
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

_.each(collectionMethods, (method) => {
  collectionMixin[method] = function() {
    var args = _.toArray(arguments);
    var source = args[0];

    if (_.isPlainObject(source)) {
      args[0] = (model) => _.isMatch(model.attributes, source);
    }

    args.unshift(this.models);

    return _[method](...args);
  };
});

var BaseModel = models.BaseModel = Backbone.Model.extend(superMixin);
var BaseCollection = models.BaseCollection =
  Backbone.Collection.extend(collectionMixin).extend(superMixin);

var cacheMixin = {
  fetch(options) {
    if (this.cacheFor && options && options.cache && this.lastSyncTime &&
      (this.cacheFor > (new Date() - this.lastSyncTime))) {
      return $.Deferred().resolve();
    }
    return this._super('fetch', arguments);
  },
  sync() {
    var deferred = this._super('sync', arguments);
    if (this.cacheFor) {
      deferred.done(() => {
        this.lastSyncTime = new Date();
      });
    }
    return deferred;
  },
  cancelThrottling() {
    delete this.lastSyncTime;
  }
};
models.cacheMixin = cacheMixin;

var restrictionMixin = models.restrictionMixin = {
  checkRestrictions(models, action, setting) {
    var restrictions = _.map(setting ? setting.restrictions : this.get('restrictions'),
      utils.expandRestriction);
    if (action) {
      restrictions = _.where(restrictions, {action: action});
    }
    var satisfiedRestrictions = _.filter(restrictions,
        (restriction) => new Expression(restriction.condition, models, restriction).evaluate()
      );
    return {
      result: !!satisfiedRestrictions.length,
      message: _.compact(_.pluck(satisfiedRestrictions, 'message')).join(' ')
    };
  },
  expandLimits(limits) {
    this.expandedLimits = this.expandedLimits || {};
    this.expandedLimits[this.get('name')] = limits;
  },
  checkLimits(models, nodes, checkLimitIsReached = true, limitTypes = ['min', 'max']) {
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
     *        - there can be no more nodes added (return false) -- case for
     *          checkLimitIsReached = false
     *  limitType -- array of limit types to check. Possible choices are 'min', 'max', 'recommended'
    **/

    var evaluateExpressionHelper = (expression, models, options) => {
      var ret;

      if (_.isUndefined(expression)) {
        return {value: undefined, modelPaths: {}};
      } else if (_.isNumber(expression)) {
        return {value: expression, modelPaths: {}};
      }

      ret = utils.evaluateExpression(expression, models, options);

      if (ret.value instanceof ModelPath) {
        ret.value = ret.value.model.get(ret.value.attribute);
      }

      return ret;
    };

    var checkedLimitTypes = {};
    var name = this.get('name');
    var limits = this.expandedLimits[name] || {};
    var overrides = limits.overrides || [];
    var limitValues = {
      max: evaluateExpressionHelper(limits.max, models).value,
      min: evaluateExpressionHelper(limits.min, models).value,
      recommended: evaluateExpressionHelper(limits.recommended, models).value
    };
    var count = nodes.nodesAfterDeploymentWithRole(name).length;
    var messages;
    var label = this.get('label');

    var checkOneLimit = (obj, limitType) => {
      var limitValue, comparator;

      if (_.isUndefined(obj[limitType])) {
        return null;
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
      limitValue = parseInt(evaluateExpressionHelper(obj[limitType], models).value, 10);
      // Update limitValue with overrides, this way at the end we have a flattened
      // limitValues with overrides having priority
      limitValues[limitType] = limitValue;
      checkedLimitTypes[limitType] = true;
      if (comparator(count, limitValue)) {
        return {
          type: limitType,
          value: limitValue,
          message: obj.message || i18n('common.role_limits.' + limitType,
            {limitValue: limitValue, count: count, roleName: label})
        };
      }
    };

    // Check the overridden limit types
    messages = _.chain(overrides)
      .map((override) => {
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
      .map((limitType) => {
        if (checkedLimitTypes[limitType]) {
          return null;
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
    messages = _.map(limitTypes, (limitType) => {
      var message = _.chain(messages)
        .filter({type: limitType})
        .sortBy('value')
        .value();
      if (limitType !== 'max') {
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
  parse(response) {
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
  groups: ['base', 'compute', 'storage', 'other'],
  initialize() {
    this.processConflictsAndRestrictions();
    this.on('update', this.processConflictsAndRestrictions, this);
  },
  processConflictsAndRestrictions() {
    this.each((role) => {
      role.expandLimits(role.get('limits'));

      var roleConflicts = role.get('conflicts');
      var roleName = role.get('name');

      if (roleConflicts === '*') {
        role.conflicts = _.map(this.reject({name: roleName}), (role) => role.get('name'));
      } else {
        role.conflicts = _.chain(role.conflicts)
          .union(roleConflicts)
          .uniq()
          .compact()
          .value();
      }

      _.each(role.conflicts, (conflictRoleName) => {
        var conflictingRole = this.findWhere({name: conflictRoleName});
        if (conflictingRole) {
          conflictingRole.conflicts = _.uniq(_.union(conflictingRole.conflicts || [], [roleName]));
        }
      });
    });
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
  defaults() {
    var defaults = {
      nodes: new models.Nodes(),
      tasks: new models.Tasks(),
      nodeNetworkGroups: new models.NodeNetworkGroups()
    };
    defaults.nodes.cluster = defaults.tasks.cluster = defaults.nodeNetworkGroups.cluster = this;
    return defaults;
  },
  validate(attrs) {
    var errors = {};
    if (!_.trim(attrs.name) || !_.trim(attrs.name).length) {
      errors.name = 'Environment name cannot be empty';
    }
    if (!attrs.release) {
      errors.release = 'Please choose OpenStack release';
    }
    return _.isEmpty(errors) ? null : errors;
  },
  task(filter1, filter2) {
    var filters = _.isPlainObject(filter1) ? filter1 : {name: filter1, status: filter2};
    return this.get('tasks') && this.get('tasks').findTask(filters);
  },
  tasks(filter1, filter2) {
    var filters = _.isPlainObject(filter1) ? filter1 : {name: filter1, status: filter2};
    return this.get('tasks') && this.get('tasks').filterTasks(filters);
  },
  needsRedeployment() {
    return this.get('nodes').any({pending_addition: false, status: 'error'}) &&
      this.get('status') !== 'update_error';
  },
  fetchRelated(related, options) {
    return this.get(related).fetch(_.extend({data: {cluster_id: this.id}}, options));
  },
  isAvailableForSettingsChanges() {
    return !this.get('is_locked');
  },
  isDeploymentPossible() {
    return this.get('release').get('state') !== 'unavailable' &&
      !this.task({group: 'deployment', active: true}) &&
      (this.get('status') !== 'operational' || this.get('nodes').hasChanges());
  },
  getCapacity() {
    var result = {
      cores: 0,
      ht_cores: 0,
      ram: 0,
      hdd: 0
    };
    if (!this.get('nodes').length) return result;
    var resourceToRoleGroupMap = {
      cores: 'compute',
      ht_cores: 'compute',
      ram: 'compute',
      hdd: 'storage'
    };
    var groupedRoles = {};
    _.each(['compute', 'storage'], (group) => {
      groupedRoles[group] = this.get('roles')
        .where({group: group})
        .map((role) => role.get('name'));
    });
    this.get('nodes').each((node) => {
      _.each(resourceToRoleGroupMap, (group, resourceName) => {
        if (node.hasRole(groupedRoles[group])) result[resourceName] += node.resource(resourceName);
      });
    });
    return result;
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
  resource(resourceName) {
    var resource = 0;
    try {
      if (resourceName === 'cores') {
        resource = this.get('meta').cpu.real;
      } else if (resourceName === 'ht_cores') {
        resource = this.get('meta').cpu.total;
      } else if (resourceName === 'hdd') {
        resource = _.reduce(this.get('meta').disks, (hdd, disk) => {
          return _.isNumber(disk.size) ? hdd + disk.size : hdd;
        }, 0);
      } else if (resourceName === 'ram') {
        resource = this.get('meta').memory.total;
      } else if (resourceName === 'disks') {
        resource = _.pluck(this.get('meta').disks, 'size').sort((a, b) => a - b);
      } else if (resourceName === 'disks_amount') {
        resource = this.get('meta').disks.length;
      } else if (resourceName === 'interfaces') {
        resource = this.get('meta').interfaces.length;
      }
    } catch (ignore) {}
    return _.isNaN(resource) ? 0 : resource;
  },
  sortedRoles(preferredOrder) {
    return _.union(this.get('roles'), this.get('pending_roles')).sort((a, b) => {
      return _.indexOf(preferredOrder, a) - _.indexOf(preferredOrder, b);
    });
  },
  isSelectable() {
    // forbid removing node from adding to environments
    // and useless management of roles, disks, interfaces, etc.
    return this.get('status') !== 'removing';
  },
  hasRole(roles = [], onlyDeployedRoles = false) {
    if (_.isString(roles)) roles = [roles];
    var nodeRoles = this.get('roles');
    if (!onlyDeployedRoles) nodeRoles = nodeRoles.concat(this.get('pending_roles'));
    return !!_.intersection(nodeRoles, roles).length;
  },
  isProvisioningPossible() {
    var status = this.get('status');
    return status === 'discover' || status === 'error' && this.get('error_type') === 'provisioning';
  },
  isDeploymentPossible() {
    var status = this.get('status');
    return status === 'provisioned' || status === 'error' && this.get('error_type') === 'deploy';
  },
  hasChanges() {
    return this.get('pending_addition') ||
      this.get('pending_deletion') ||
      !!this.get('cluster') && !!this.get('pending_roles').length;
  },
  areDisksConfigurable() {
    var status = this.get('status');
    return status === 'discover' || status === 'error';
  },
  areInterfacesConfigurable() {
    var status = this.get('status');
    return status === 'discover' || status === 'error';
  },
  getRolesSummary(releaseRoles) {
    return _.map(this.sortedRoles(releaseRoles.pluck('name')), (role) => {
      return releaseRoles.findWhere({name: role}).get('label');
    }).join(', ');
  },
  getStatusSummary() {
    // 'offline' status has higher priority
    if (!this.get('online')) return 'offline';
    var status = this.get('status');
    // 'removing' end 'error' statuses have higher priority
    if (_.contains(['removing', 'error'], status)) return status;
    if (this.get('pending_addition')) return 'pending_addition';
    if (this.get('pending_deletion')) return 'pending_deletion';
    return status;
  },
  getLabel(label) {
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
  nodesAfterDeployment() {
    return this.filter((node) => !node.get('pending_deletion'));
  },
  nodesAfterDeploymentWithRole(role) {
    return _.filter(this.nodesAfterDeployment(), (node) => node.hasRole(role));
  },
  resources(resourceName) {
    var resources = this.map((node) => node.resource(resourceName));
    return _.reduce(resources, (sum, n) => sum + n, 0);
  },
  getLabelValues(label) {
    return this.invoke('getLabel', label);
  },
  areDisksConfigurable() {
    if (!this.length) return false;
    var roles = _.union(this.at(0).get('roles'), this.at(0).get('pending_roles'));
    var disks = this.at(0).resource('disks');
    return !this.any((node) => {
      var roleConflict = _.difference(roles, _.union(node.get('roles'),
        node.get('pending_roles'))).length;
      return roleConflict || !_.isEqual(disks, node.resource('disks'));
    });
  },
  areInterfacesConfigurable() {
    if (!this.length) return false;
    return _.uniq(this.invoke('resource', 'interfaces')).length === 1;
  }
});

models.NodesStatistics = BaseModel.extend({
  constructorName: 'NodesStatistics',
  urlRoot: '/api/nodes/allocation/stats'
});

models.NodeAttributes = Backbone.DeepModel
  .extend(restrictionMixin)
  .extend(makePathMixin)
  .extend({
    constructorName: 'NodeAttributes',
    isNew() {
      return false;
    },
    validate(attrs) {
      var errors = {};
      var listOfFields = ['dpdk', 'nova'];
      _.each(attrs, (group, groupName) => {
        _.each(listOfFields, (field) => {
          var groupSetting = group[field];
          if (!(groupSetting.regex || {}).source) return;
          if (!new RegExp(groupSetting.regex.source).test(groupSetting.value)) {
            errors[this.makePath(groupName, field)] = groupSetting.regex.error;
          }
        });
      });
      return _.isEmpty(errors) ? null : errors;
    }
  });

models.Task = BaseModel.extend({
  constructorName: 'Task',
  urlRoot: '/api/tasks',
  releaseId() {
    var id;
    try {
      id = this.get('result').release_info.release_id;
    } catch (ignore) {}
    return id;
  },
  groups: {
    network: [
      'verify_networks',
      'check_networks'
    ],
    deployment: [
      'stop_deployment',
      'deploy',
      'provision',
      'deployment',
      'reset_environment',
      'spawn_vms'
    ]
  },
  extendGroups(filters) {
    var names = utils.composeList(filters.name);
    if (_.isEmpty(names)) names = _.flatten(_.values(this.groups));
    var groups = utils.composeList(filters.group);
    if (_.isEmpty(groups)) return names;
    return _.intersection(names, _.flatten(_.values(_.pick(this.groups, groups))));
  },
  extendStatuses(filters) {
    var activeTaskStatuses = ['running', 'pending'];
    var completedTaskStatuses = ['ready', 'error'];
    var statuses = utils.composeList(filters.status);
    if (_.isEmpty(statuses)) {
      statuses = _.union(activeTaskStatuses, completedTaskStatuses);
    }
    if (_.isBoolean(filters.active)) {
      return _.intersection(statuses, filters.active ? activeTaskStatuses : completedTaskStatuses);
    }
    return statuses;
  },
  match(filters) {
    filters = filters || {};
    if (!_.isEmpty(filters)) {
      if ((filters.group || filters.name) &&
        !_.contains(this.extendGroups(filters), this.get('name'))) {
        return false;
      }
      if ((filters.status || _.isBoolean(filters.active)) &&
        !_.contains(this.extendStatuses(filters), this.get('status'))) {
        return false;
      }
    }
    return true;
  },
  isInfinite() {
    return this.match({name: ['stop_deployment', 'reset_environment']});
  },
  isStoppable() {
    return this.match({name: 'deploy', status: 'running'});
  }
});

models.Tasks = BaseCollection.extend({
  constructorName: 'Tasks',
  model: models.Task,
  url: '/api/tasks',
  toJSON() {
    return this.pluck('id');
  },
  comparator: 'id',
  filterTasks(filters) {
    return _.chain(this.model.prototype.extendGroups(filters))
      .map((name) => {
        return this.filter((task) => task.match(_.extend(_.omit(filters, 'group'), {name: name})));
      })
      .flatten()
      .compact()
      .value();
  },
  findTask(filters) {
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
  comparator(notification) {
    return -notification.id;
  }
});

models.Settings = Backbone.DeepModel
  .extend(superMixin)
  .extend(cacheMixin)
  .extend(restrictionMixin)
  .extend(makePathMixin)
  .extend({
    constructorName: 'Settings',
    urlRoot: '/api/clusters/',
    root: 'editable',
    cacheFor: 60 * 1000,
    groupList: ['general', 'security', 'compute', 'network', 'storage',
      'logging', 'openstack_services', 'other'],
    isNew() {
      return false;
    },
    isPlugin(section) {
      return (section.metadata || {}).class === 'plugin';
    },
    parse(response) {
      return response[this.root];
    },
    mergePluginSettings() {
      _.each(this.attributes, (section, sectionName) => {
        if (this.isPlugin(section)) {
          var chosenVersionData = section.metadata.versions.find(
              (version) => version.metadata.plugin_id === section.metadata.chosen_id
            );
          // merge metadata of a chosen plugin version
          _.extend(section.metadata,
            _.omit(chosenVersionData.metadata, 'plugin_id', 'plugin_version'));
          // merge settings of a chosen plugin version
          this.attributes[sectionName] = _.extend(_.pick(section, 'metadata'),
            _.omit(chosenVersionData, 'metadata'));
        }
      }, this);
    },
    toJSON() {
      var settings = this._super('toJSON', arguments);
      if (!this.root) return settings;

      // update plugin settings
      _.each(settings, (section, sectionName) => {
        if (this.isPlugin(section)) {
          var chosenVersionData = section.metadata.versions.find(
              (version) => version.metadata.plugin_id === section.metadata.chosen_id
            );
          section.metadata = _.omit(section.metadata,
            _.without(_.keys(chosenVersionData.metadata), 'plugin_id', 'plugin_version'));
          _.each(section, (setting, settingName) => {
            if (settingName !== 'metadata') chosenVersionData[settingName].value = setting.value;
          });
          settings[sectionName] = _.pick(section, 'metadata');
        }
      });
      return {[this.root]: settings};
    },
    initialize() {
      this.once('change', this.mergePluginSettings, this);
    },
    validate(attrs, options) {
      var errors = {};
      var models = options ? options.models : {};
      var checkRestrictions = (setting) => this.checkRestrictions(models, null, setting);
      _.each(attrs, (group, groupName) => {
        if ((group.metadata || {}).enabled === false ||
          checkRestrictions(group.metadata).result) return;
        _.each(group, (setting, settingName) => {
          if (checkRestrictions(setting).result) return;
          var path = this.makePath(groupName, settingName);
          // support of custom controls
          var CustomControl = customControls[setting.type];
          if (CustomControl) {
            var error = CustomControl.validate(setting, models);
            if (error) errors[path] = error;
            return;
          }

          if (!(setting.regex || {}).source) return;
          if (!setting.value.match(new RegExp(setting.regex.source))) {
            errors[path] = setting.regex.error;
          }
        });
      });
      return _.isEmpty(errors) ? null : errors;
    },
    getValueAttribute(settingName) {
      return settingName === 'metadata' ? 'enabled' : 'value';
    },
    hasChanges(initialAttributes, models) {
      return _.any(this.attributes, (section, sectionName) => {
        var metadata = section.metadata;
        var result = false;
        if (metadata) {
          if (this.checkRestrictions(models, null, metadata).result) return result;
          if (!_.isUndefined(metadata.enabled)) {
            result = metadata.enabled !== initialAttributes[sectionName].metadata.enabled;
          }
          if (!result && this.isPlugin(section)) {
            result = metadata.chosen_id !== initialAttributes[sectionName].metadata.chosen_id;
          }
        }
        return result || (metadata || {}).enabled !== false &&
          _.any(section, (setting, settingName) => {
            if (this.checkRestrictions(models, null, setting).result) return false;
            return !_.isEqual(setting.value,
              (initialAttributes[sectionName][settingName] || {}).value);
          });
      });
    },
    sanitizeGroup(group) {
      return _.contains(this.groupList, group) ? group : 'other';
    },
    getGroupList() {
      var groups = [];
      _.each(this.attributes, (section) => {
        if (section.metadata.group) {
          groups.push(this.sanitizeGroup(section.metadata.group));
        } else {
          _.each(section, (setting, settingName) => {
            if (settingName !== 'metadata') groups.push(this.sanitizeGroup(setting.group));
          });
        }
      });
      return _.intersection(this.groupList, groups);
    }
  });

models.FuelSettings = models.Settings.extend({
  constructorName: 'FuelSettings',
  url: '/api/settings',
  root: 'settings',
  parse(response) {
    return _.extend(this._super('parse', arguments), {master_node_uid: response.master_node_uid});
  }
});

models.Disk = BaseModel.extend({
  constructorName: 'Disk',
  urlRoot: '/api/nodes/',
  parse(response) {
    response.volumes = new models.Volumes(response.volumes);
    response.volumes.disk = this;
    return response;
  },
  toJSON(options) {
    return _.extend(this.constructor.__super__.toJSON.call(this, options),
      {volumes: this.get('volumes').toJSON()});
  },
  getUnallocatedSpace(options) {
    options = options || {};
    var volumes = options.volumes || this.get('volumes');
    var allocatedSpace = volumes.reduce((sum, volume) => {
      return volume.get('name') === options.skip ? sum : sum + volume.get('size');
    }, 0);
    return this.get('size') - allocatedSpace;
  },
  validate(attrs) {
    var error;
    var unallocatedSpace = this.getUnallocatedSpace({volumes: attrs.volumes});
    if (unallocatedSpace < 0) {
      error = i18n('cluster_page.nodes_tab.configure_disks.validation_error',
        {size: utils.formatNumber(unallocatedSpace * -1)});
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
  getMinimalSize(minimum) {
    var currentDisk = this.collection.disk;
    var groupAllocatedSpace = 0;
    if (currentDisk && currentDisk.collection) {
      groupAllocatedSpace = currentDisk.collection.reduce((sum, disk) => {
        return disk.id === currentDisk.id ? sum : sum +
          disk.get('volumes').findWhere({name: this.get('name')}).get('size');
      }, 0);
    }
    return minimum - groupAllocatedSpace;
  },
  getMaxSize() {
    var volumes = this.collection.disk.get('volumes');
    var diskAllocatedSpace = volumes.reduce((total, volume) => {
      return this.get('name') === volume.get('name') ? total : total + volume.get('size');
    }, 0);
    return this.collection.disk.get('size') - diskAllocatedSpace;
  },
  validate(attrs, options) {
    var min = this.getMinimalSize(options.minimum);
    if (attrs.size < min) {
      return i18n('cluster_page.nodes_tab.configure_disks.volume_error',
        {size: utils.formatNumber(min)});
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
  parse(response) {
    response.assigned_networks = new models.InterfaceNetworks(response.assigned_networks);
    response.assigned_networks.interface = this;
    return response;
  },
  toJSON(options) {
    return _.omit(_.extend(this.constructor.__super__.toJSON.call(this, options), {
      assigned_networks: this.get('assigned_networks').toJSON()
    }), 'checked');
  },
  isBond() {
    return this.get('type') === 'bond';
  },
  getSlaveInterfaces() {
    if (!this.isBond()) return [this];
    var slaveInterfaceNames = _.pluck(this.get('slaves'), 'name');
    return this.collection.filter((slaveInterface) => {
      return _.contains(slaveInterfaceNames, slaveInterface.get('name'));
    });
  },
  validate(attrs) {
    var errors = [];
    var networks = new models.Networks(this.get('assigned_networks')
      .invoke('getFullNetwork', attrs.networks));
    var untaggedNetworks = networks.filter((network) => {
      return _.isNull(network.getVlanRange(attrs.networkingParameters));
    });
    var ns = 'cluster_page.nodes_tab.configure_interfaces.validation.';
    // public and floating networks are allowed to be assigned to the same interface
    var maxUntaggedNetworksCount = networks.any({name: 'public'}) &&
      networks.any({name: 'floating'}) ? 2 : 1;
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

    // check interface networks have the same vlan id
    var vlans = _.reject(networks.pluck('vlan_start'), _.isNull);
    if (_.uniq(vlans).length < vlans.length) errors.push(i18n(ns + 'networks_with_the_same_vlan'));

    // check interface network vlan ids included in Neutron L2 vlan range
    var vlanRanges = _.reject(networks.map(
        (network) => network.getVlanRange(attrs.networkingParameters)
      ), _.isNull);
    if (
      _.any(vlanRanges,
        (currentRange) => _.any(vlanRanges,
          (range) => !_.isEqual(currentRange, range) &&
            range[1] >= currentRange[0] && range[0] <= currentRange[1]
        )
      )
    ) errors.push(i18n(ns + 'vlan_range_intersection'));

    return errors;
  }
});

models.Interfaces = BaseCollection.extend({
  constructorName: 'Interfaces',
  model: models.Interface,
  generateBondName(base) {
    var index, proposedName;
    for (index = 0; ; index += 1) {
      proposedName = base + index;
      if (!this.any({name: proposedName})) return proposedName;
    }
  },
  comparator(ifc1, ifc2) {
    return utils.multiSort(ifc1, ifc2, [{attr: 'isBond'}, {attr: 'name'}]);
  }
});

var networkPreferredOrder = ['public', 'floating', 'storage', 'management',
  'private', 'fixed', 'baremetal'];

models.InterfaceNetwork = BaseModel.extend({
  constructorName: 'InterfaceNetwork',
  getFullNetwork(networks) {
    return networks.findWhere({name: this.get('name')});
  }
});

models.InterfaceNetworks = BaseCollection.extend({
  constructorName: 'InterfaceNetworks',
  model: models.InterfaceNetwork,
  comparator(network) {
    return _.indexOf(networkPreferredOrder, network.get('name'));
  }
});

models.Network = BaseModel.extend({
  constructorName: 'Network',
  getVlanRange(networkingParameters) {
    if (!this.get('meta').neutron_vlan_range) {
      var externalNetworkData = this.get('meta').ext_net_data;
      var vlanStart = externalNetworkData ?
        networkingParameters.get(externalNetworkData[0]) : this.get('vlan_start');
      return _.isNull(vlanStart) ? vlanStart :
        [vlanStart, externalNetworkData ?
          vlanStart + networkingParameters.get(externalNetworkData[1]) - 1 : vlanStart];
    }
    return networkingParameters.get('vlan_range');
  }
});

models.Networks = BaseCollection.extend({
  constructorName: 'Networks',
  model: models.Network,
  comparator(network) {
    return _.indexOf(networkPreferredOrder, network.get('name'));
  }
});

models.NetworkingParameters = BaseModel.extend({
  constructorName: 'NetworkingParameters'
});

models.NetworkConfiguration = BaseModel.extend(cacheMixin).extend({
  constructorName: 'NetworkConfiguration',
  cacheFor: 60 * 1000,
  parse(response) {
    response.networks = new models.Networks(response.networks);
    response.networking_parameters = new models.NetworkingParameters(
      response.networking_parameters
    );
    return response;
  },
  toJSON() {
    return {
      networks: this.get('networks').toJSON(),
      networking_parameters: this.get('networking_parameters').toJSON()
    };
  },
  isNew() {
    return false;
  },
  validateNetworkIpRanges(network, cidr) {
    if (network.get('meta').notation === 'ip_ranges') {
      var errors = utils.validateIPRanges(network.get('ip_ranges'), cidr);
      return errors.length ? {ip_ranges: errors} : null;
    }
    return null;
  },
  validateFixedNetworksAmount(fixedNetworksAmount, fixedNetworkVlan) {
    if (!utils.isNaturalNumber(parseInt(fixedNetworksAmount, 10))) {
      return {fixed_networks_amount: i18n('cluster_page.network_tab.validation.invalid_amount')};
    }
    if (fixedNetworkVlan && fixedNetworksAmount > 4095 - fixedNetworkVlan) {
      return {fixed_networks_amount: i18n('cluster_page.network_tab.validation.need_more_vlan')};
    }
    return null;
  },
  validateNeutronSegmentationIdRange([idStart, idEnd], isVlanSegmentation, vlans = []) {
    var ns = 'cluster_page.network_tab.validation.';
    var maxId = isVlanSegmentation ? 4094 : 65535;
    var errors = _.map([idStart, idEnd], (id, index) => {
      return !utils.isNaturalNumber(id) || id < 2 || id > maxId ?
        i18n(ns + (index === 0 ? 'invalid_id_start' : 'invalid_id_end')) : '';
    });
    if (errors[0] || errors[1]) return errors;

    errors[0] = errors[1] = idStart === idEnd ?
        i18n(ns + 'not_enough_id')
      :
        idStart > idEnd ? i18n(ns + 'invalid_id_range') : '';
    if (errors[0] || errors[1]) return errors;

    if (isVlanSegmentation) {
      if (_.any(vlans, (vlan) => utils.validateVlanRange(idStart, idEnd, vlan))) {
        errors[0] = errors[1] = i18n(ns + 'vlan_intersection');
      }
    }
    return errors;
  },
  validateNeutronFloatingRange(floatingRanges, networks, networkErrors, nodeNetworkGroups) {
    var error = utils.validateIPRanges(floatingRanges, null);
    if (!_.isEmpty(error)) return error;

    var networksToCheck = networks.filter((network) => {
      var cidrError;
      try {
        cidrError = !!networkErrors[network.get('group_id')][network.id].cidr;
      } catch (ignore) {}
      if (cidrError || !network.get('meta').floating_range_var) return false;
      var [floatingRangeStart, floatingRangeEnd] = floatingRanges[0];
      var cidr = network.get('cidr');
      return utils.validateIpCorrespondsToCIDR(cidr, floatingRangeStart) &&
        utils.validateIpCorrespondsToCIDR(cidr, floatingRangeEnd);
    });

    if (networksToCheck.length) {
      _.each(networksToCheck, (network) => {
        error = utils.validateIPRanges(
          floatingRanges,
          network.get('cidr'),
          _.filter(network.get('ip_ranges'), (range, index) => {
            var ipRangeError = false;
            try {
              ipRangeError = !_.all(range) || _.any(
                  networkErrors[network.get('group_id')][network.id].ip_ranges,
                  {index: index}
                );
            } catch (ignore) {}
            return !ipRangeError;
          }),
          {
            IP_RANGES_INTERSECTION: i18n(
              'cluster_page.network_tab.validation.floating_and_public_ip_ranges_intersection',
              {
                cidr: network.get('cidr'),
                network: _.capitalize(network.get('name')),
                nodeNetworkGroup: nodeNetworkGroups.get(network.get('group_id')).get('name')
              }
            )
          }
        );
        return _.isEmpty(error);
      });
    } else {
      error = [{index: 0}];
      error[0].start = error[0].end =
        i18n('cluster_page.network_tab.validation.floating_range_is_not_in_public_cidr');
    }

    return error;
  },
  validateNetwork(network, networksToCheck, novaNetworking = false) {
    var cidr = network.get('cidr');
    var errors = {};

    _.extend(errors, utils.validateCidr(cidr));
    var cidrError = _.has(errors, 'cidr');

    _.extend(errors, this.validateNetworkIpRanges(network, cidrError ? null : cidr));

    if (network.get('meta').use_gateway) {
      _.extend(
        errors,
        utils.validateGateway(network.get('gateway'), cidrError ? null : cidr)
      );
    }

    // same VLAN IDs are not permitted for nova-network
    var forbiddenVlans = novaNetworking ? networksToCheck.map((net) => {
      return net.id !== network.id ? net.get('vlan_start') : null;
    }) : [];
    _.extend(
      errors,
      utils.validateVlan(network.get('vlan_start'), forbiddenVlans, 'vlan_start')
    );

    return errors;
  },
  validateNovaNetworkParameters(parameters, networks, manager) {
    var errors = {};

    _.extend(
      errors,
      utils.validateCidr(parameters.get('fixed_networks_cidr'), 'fixed_networks_cidr')
    );

    var fixedNetworkVlan = parameters.get('fixed_networks_vlan_start');
    var fixedNetworkVlanError = utils.validateVlan(
      fixedNetworkVlan,
      networks.pluck('vlan_start'),
      'fixed_networks_vlan_start',
      manager === 'VlanManager'
    );
    _.extend(errors, fixedNetworkVlanError);

    var fixedNetworksAmount = parameters.get('fixed_networks_amount');
    _.extend(
      errors,
      this.validateFixedNetworksAmount(
        fixedNetworksAmount,
        _.isEmpty(fixedNetworkVlanError) ? null : fixedNetworkVlan
      )
    );

    if (_.isEmpty(fixedNetworkVlanError)) {
      var vlanIntersection = _.any(_.compact(networks.pluck('vlan_start')),
        (vlan) => utils.validateVlanRange(
          fixedNetworkVlan,
          fixedNetworkVlan + fixedNetworksAmount - 1, vlan
        )
      );
      if (vlanIntersection) {
        errors.fixed_networks_vlan_start =
          i18n('cluster_page.network_tab.validation.vlan_intersection');
      }
    }

    var floatingRangeErrors = utils.validateIPRanges(parameters.get('floating_ranges'));
    if (floatingRangeErrors.length) {
      errors.floating_ranges = floatingRangeErrors;
    }

    return errors;
  },
  validateNeutronParameters(parameters, networks, networkErrors, nodeNetworkGroups) {
    var errors = {};

    var isVlanSegmentation = parameters.get('segmentation_type') === 'vlan';
    var idRangeAttributeName = isVlanSegmentation ? 'vlan_range' : 'gre_id_range';
    var idRangeErrors = this.validateNeutronSegmentationIdRange(
      _.map(parameters.get(idRangeAttributeName), Number),
      isVlanSegmentation,
      _.compact(networks.pluck('vlan_start'))
    );
    if (idRangeErrors[0] || idRangeErrors[1]) errors[idRangeAttributeName] = idRangeErrors;

    if (!parameters.get('base_mac').match(utils.regexes.mac)) {
      errors.base_mac = i18n('cluster_page.network_tab.validation.invalid_mac');
    }

    _.extend(errors, utils.validateCidr(parameters.get('internal_cidr'), 'internal_cidr'));

    _.extend(
      errors,
      utils.validateGateway(
        parameters.get('internal_gateway'),
        parameters.get('internal_cidr'),
        'internal_gateway'
      )
    );

    _.each(['internal_name', 'floating_name'], (attribute) => {
      if (!parameters.get(attribute).match(/^[a-z][\w\-]*$/i)) {
        errors[attribute] = i18n('cluster_page.network_tab.validation.invalid_name');
      }
    });

    var floatingRangeErrors = this.validateNeutronFloatingRange(
      parameters.get('floating_ranges'),
      networks,
      networkErrors,
      nodeNetworkGroups
    );
    if (floatingRangeErrors.length) errors.floating_ranges = floatingRangeErrors;

    return errors;
  },
  validateBaremetalParameters(cidr, networkingParameters) {
    var errors = {};

    _.extend(
      errors,
      utils.validateGateway(
        networkingParameters.get('baremetal_gateway'),
        cidr,
        'baremetal_gateway'
      )
    );

    var baremetalRangeErrors = utils.validateIPRanges(
      [networkingParameters.get('baremetal_range')],
      cidr
    );
    if (baremetalRangeErrors.length) {
      var [{start, end}] = baremetalRangeErrors;
      errors.baremetal_range = [start, end];
    }

    return errors;
  },
  validateNameServers(nameservers) {
    var errors = _.map(nameservers,
      (nameserver) => !utils.validateIP(nameserver) ?
        i18n('cluster_page.network_tab.validation.invalid_nameserver') : null
    );
    if (_.compact(errors).length) return {dns_nameservers: errors};
  },
  validate(attrs, options = {}) {
    var networkingParameters = attrs.networking_parameters;
    var novaNetworkManager = networkingParameters.get('net_manager');

    var errors = {};

    // validate networks
    var nodeNetworkGroupsErrors = {};
    options.nodeNetworkGroups.map((nodeNetworkGroup) => {
      var nodeNetworkGroupErrors = {};
      var networksToCheck = new models.Networks(attrs.networks.filter((network) => {
        return network.get('group_id') === nodeNetworkGroup.id && network.get('meta').configurable;
      }));
      networksToCheck.each((network) => {
        var networkErrors = this.validateNetwork(network, networksToCheck, !!novaNetworkManager);
        if (!_.isEmpty(networkErrors)) nodeNetworkGroupErrors[network.id] = networkErrors;
      });
      if (!_.isEmpty(nodeNetworkGroupErrors)) {
        nodeNetworkGroupsErrors[nodeNetworkGroup.id] = nodeNetworkGroupErrors;
      }
    });
    if (!_.isEmpty(nodeNetworkGroupsErrors)) errors.networks = nodeNetworkGroupsErrors;

    // validate networking parameters
    var networkingParametersErrors = novaNetworkManager ?
        this.validateNovaNetworkParameters(networkingParameters, attrs.networks, novaNetworkManager)
      :
        this.validateNeutronParameters(
          networkingParameters,
          attrs.networks,
          errors.networks,
          options.nodeNetworkGroups
        );

    // it is only one baremetal network in environment
    // so node network group filter is not needed here
    var baremetalNetwork = attrs.networks.find({name: 'baremetal'});
    if (baremetalNetwork) {
      var baremetalCidrError = false;
      try {
        baremetalCidrError = errors
          .networks[baremetalNetwork.get('group_id')][baremetalNetwork.id].cidr;
      } catch (error) {}
      _.extend(
        networkingParametersErrors,
        this.validateBaremetalParameters(
          baremetalCidrError ? null : baremetalNetwork.get('cidr'),
          networkingParameters
        )
      );
    }

    _.extend(
      networkingParametersErrors,
      this.validateNameServers(networkingParameters.get('dns_nameservers'))
    );

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
  initialize() {
    _.each(this.locallyStoredAttributes, (attribute) => {
      var locallyStoredValue = localStorage.getItem(attribute);
      if (locallyStoredValue) {
        this.set(attribute, locallyStoredValue);
      }
      this.on('change:' + attribute, (model, value) => {
        if (_.isUndefined(value)) {
          localStorage.removeItem(attribute);
        } else {
          localStorage.setItem(attribute, value);
        }
      });
    });
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
  parseConfig(config) {
    var result = {};
    _.each(config, (paneConfig, paneName) => {
      result[paneName] = {};
      _.each(paneConfig, (attributeConfig, attribute) => {
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
    });
    return result;
  },
  processConfig(config) {
    this.set(this.parseConfig(config));
  },
  restoreDefaultValues(panesToRestore) {
    var result = {};
    _.each(this.defaults, (paneConfig, paneName) => {
      if (_.contains(panesToRestore, paneName)) {
        result[paneName] = this.defaults[paneName];
      }
    });
    this.set(result);
  },
  validate(attrs, options) {
    var errors = [];
    _.each(options.config, (attributeConfig, attribute) => {
      if (!(attributeConfig.regex && attributeConfig.regex.source)) return;
      var hasNoSatisfiedRestrictions = _.every(_.reject(attributeConfig.restrictions,
        {action: 'none'}), (restriction) => {
        // this probably will be changed when other controls need validation
        return !utils.evaluateExpression(restriction.condition, {default: this}).value;
      });
      if (hasNoSatisfiedRestrictions) {
        var regExp = new RegExp(attributeConfig.regex.source);
        if (!this.get(options.paneName + '.' + attribute).match(regExp)) {
          errors.push({
            field: attribute,
            message: i18n(attributeConfig.regex.error)
          });
        }
      }
    });
    return errors.length ? errors : null;
  },
  initialize(config) {
    this.defaults = this.parseConfig(config);
  }
});

models.MirantisCredentials = Backbone.DeepModel.extend(superMixin).extend(makePathMixin).extend({
  constructorName: 'MirantisCredentials',
  baseUrl: 'https://software.mirantis.com/wp-content/themes/' +
  'mirantis_responsive_v_1_0/scripts/fuel_forms_api/',
  validate(attrs) {
    var errors = {};
    _.each(attrs, (group, groupName) => {
      _.each(group, (setting, settingName) => {
        var path = this.makePath(groupName, settingName);
        if (!setting.regex || !setting.regex.source) return;
        if (!setting.value.match(new RegExp(setting.regex.source))) {
          errors[path] = setting.regex.error;
        }
      });
    });
    return _.isEmpty(errors) ? null : errors;
  }
});

models.NodeNetworkGroup = BaseModel.extend({
  constructorName: 'NodeNetworkGroup',
  urlRoot: '/api/nodegroups',
  validate(options = {}) {
    var newName = _.trim(options.name) || '';
    if (!newName) {
      return i18n('cluster_page.network_tab.node_network_group_empty_name');
    }
    if ((this.collection || options.nodeNetworkGroups).any({name: newName})) {
      return i18n('cluster_page.network_tab.node_network_group_duplicate_error');
    }
    return null;
  }
});

models.NodeNetworkGroups = BaseCollection.extend({
  constructorName: 'NodeNetworkGroups',
  model: models.NodeNetworkGroup,
  url: '/api/nodegroups',
  comparator: (nodeNetworkGroup) => -nodeNetworkGroup.get('is_default')
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
      return this.pattern === componentName;
    }

    var componentParts = componentName.split(':');
    if (componentParts.length < this.parts.length) {
      return false;
    }
    var matched = true;
    _.each(this.parts, (part, index) => {
      if (part !== '*') {
        if (part !== componentParts[index]) {
          matched = false;
          return matched;
        }
      }
    });
    return matched;
  }
}

models.ComponentModel = BaseModel.extend({
  initialize(component) {
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
  expandWildcards(components) {
    var expandProperty = (propertyName, components) => {
      var expandedComponents = [];
      _.each(this.get(propertyName), (patternDescription) => {
        var patternName = _.isString(patternDescription) ? patternDescription :
          patternDescription.name;
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
      incompatible: expandProperty('incompatible', components)
    });
  },
  predicates: {
    one_of: (processedComponents = [], forthcomingComponents = []) => {
      var enabledLength =
          _.filter(processedComponents, (component) => component.get('enabled')).length;
      var processedLength = processedComponents.length;
      var comingLength = forthcomingComponents.length;
      return {
        matched: (enabledLength === 0 && comingLength > 0) || enabledLength === 1,
        invalid: processedLength === 0 && comingLength === 0
      };
    },
    none_of: (processedComponents = []) => {
      var enabledLength =
          _.filter(processedComponents, (component) => component.get('enabled')).length;
      return {
        matched: enabledLength === 0,
        invalid: false
      };
    },
    any_of: (processedComponents = [], forthcomingComponents = []) => {
      var enabledLength =
          _.filter(processedComponents, (component) => component.get('enabled')).length;
      var processedLength = processedComponents.length;
      var comingLength = forthcomingComponents.length;
      return {
        matched: (enabledLength === 0 && comingLength > 0) || enabledLength >= 1,
        invalid: processedLength === 0 && comingLength === 0
      };
    },
    all_of: (processedComponents = [], forthcomingComponents = []) => {
      var processedLength = processedComponents.length;
      var comingLength = forthcomingComponents.length;
      return {
        matched: _.all(processedComponents, (component) => component.get('enabled')),
        invalid: processedLength === 0 && comingLength === 0
      };
    }
  },
  preprocessRequires(components) {
    var componentIndex = {};
    components.each((component) => {
      componentIndex[component.id] = component;
    });

    var requires = _.map(this.get('requires'), (require) => {
      var condition = {};
      _.any(['one_of', 'none_of', 'any_of', 'all_of'], (predicate) => {
        if (!_.isObject(require[predicate])) {
          return false;
        }
        condition = _.extend(require[predicate], {predicate: predicate});
        condition.items = _.map(condition.items, (name) => componentIndex[name]);
        return true;
      });
      return condition;
    });
    this.set({requires: requires});
  },
  processRequires(currentPaneIndex, paneMap) {
    var result = [];
    _.each(this.get('requires'), (require) => {
      var groupedComponents = _.groupBy(require.items, (item) => {
        if (!item) {
          return 'null';
        }
        var index = paneMap[item.get('type')];
        return index <= currentPaneIndex ? 'processed' : 'forthcoming';
      });
      var predicate = this.predicates[require.predicate];
      var predicateResult = predicate(groupedComponents.processed, groupedComponents.forthcoming);
      var message = predicateResult.invalid ? require.message_invalid : require.message;
      result.push(_.merge(predicateResult, {message: predicateResult.matched ? null : message}));
    });
    this.set({
      requireFail: _.any(result, (item) => !item.matched),
      invalid: _.any(result, (item) => item.invalid)
    });
    return {
      matched: _.all(result, (item) => item.matched),
      warnings: _.compact(_.map(result, (item) => i18n(item.message))).join(' ')
    };
  },
  restoreDefaultValue() {
    this.set({enabled: this.get('default')});
  },
  toJSON() {
    return this.get('enabled') ? this.id : null;
  },
  isML2Driver() {
    return /:ml2:\w+$/.test(this.id);
  }
});

models.ComponentsCollection = BaseCollection.extend({
  model: models.ComponentModel,
  allTypes: ['hypervisor', 'network', 'storage', 'additional_service'],
  initialize(models, options) {
    this.releaseId = options.releaseId;
    this.paneMap = {};
    _.each(this.allTypes, (type, index) => {
      this.paneMap[type] = index;
    });
  },
  url() {
    return '/api/v1/releases/' + this.releaseId + '/components';
  },
  parse(response) {
    return _.isArray(response) ? response : [];
  },
  getComponentsByType(type, options = {sorted: true}) {
    var components = this.where({type: type});
    if (options.sorted) {
      components.sort((component1, component2) => {
        return component1.get('weight') - component2.get('weight');
      });
    }
    return components;
  },
  restoreDefaultValues(types) {
    types = types || this.allTypes;
    var components = _.filter(this.models, (model) => _.contains(types, model.get('type')));
    _.invoke(components, 'restoreDefaultValue');
  },
  toJSON() {
    return _.compact(_.map(this.models, (model) => model.toJSON()));
  },
  processPaneRequires(paneType) {
    var currentPaneIndex = this.paneMap[paneType];
    this.each((component) => {
      var componentPaneIndex = this.paneMap[component.get('type')];
      if (component.get('disabled') || componentPaneIndex > currentPaneIndex) {
        return;
      }
      var result = component.processRequires(currentPaneIndex, this.paneMap);
      var isDisabled = !result.matched;
      if (componentPaneIndex === currentPaneIndex) {
        // current pane handling
        component.set({
          disabled: isDisabled,
          warnings: isDisabled ? result.warnings : null,
          enabled: isDisabled ? false : component.get('enabled'),
          availability: 'incompatible'
        });
      } else if (!result.matched) {
        // previous pane handling
        component.set({
          warnings: result.warnings
        });
      }
    });
  },
  validate(paneType) {
    // all the past panes should have all restrictions matched
    // when not, errors dictionary is set
    this.validationError = null;
    var errors = [];
    var currentPaneIndex = this.paneMap[paneType];
    this.each((component) => {
      var componentPaneIndex = this.paneMap[component.get('type')];
      if (componentPaneIndex >= currentPaneIndex) {
        return;
      }
      if (component.get('enabled') && component.get('requireFail')) {
        errors.push(component.get('warnings'));
      }
    });
    if (errors.length > 0 ) {
      this.validationError = errors;
    }
  }
});

export default models;
