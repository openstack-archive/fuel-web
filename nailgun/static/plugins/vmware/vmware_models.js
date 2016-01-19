/*
 * Copyright 2015 Mirantis, Inc.
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
import _ from 'underscore';
import i18n from 'i18n';
import Backbone from 'backbone';
import models from 'models';

var VmWareModels = {};

VmWareModels.isRegularField = (field) => {
  return _.contains(['text', 'password', 'checkbox', 'select'], field.type);
};

// models for testing restrictions
var restrictionModels = {};

// Test regex using regex cache
var regexCache = {};
function testRegex(regexText, value) {
  if (!regexCache[regexText]) {
    regexCache[regexText] = new RegExp(regexText);
  }
  return regexCache[regexText].test(value);
}

var BaseModel = Backbone.Model.extend(models.superMixin).extend(models.cacheMixin).extend(models.restrictionMixin).extend({
  constructorName: 'BaseModel',
  cacheFor: 60 * 1000,
  toJSON() {
    return _.omit(this.attributes, 'metadata');
  },
  validate() {
    var result = {};
    _.each(this.attributes.metadata, (field) => {
      if (!VmWareModels.isRegularField(field) || field.type == 'checkbox') {
        return;
      }
      var isDisabled = this.checkRestrictions(restrictionModels, undefined, field);
      if (isDisabled.result) {
        return;
      }
      var value = this.get(field.name);
      if (field.regex) {
        if (!testRegex(field.regex.source, value)) {
          result[field.name] = field.regex.error;
        }
      }
    });
    return _.isEmpty(result) ? null : result;
  },
  testRestrictions() {
    var results = {
      hide: {},
      disable: {}
    };
    var metadata = this.get('metadata');
    _.each(metadata, (field) => {
      var disableResult = this.checkRestrictions(restrictionModels, undefined, field);
      results.disable[field.name] = disableResult;

      var hideResult = this.checkRestrictions(restrictionModels, 'hide', field);
      results.hide[field.name] = hideResult;
    });
    return results;
  }
});

var BaseCollection = Backbone.Collection.extend(models.superMixin).extend(models.cacheMixin).extend({
  constructorName: 'BaseCollection',
  model: BaseModel,
  cacheFor: 60 * 1000,
  isValid() {
    this.validationError = this.validate();
    return this.validationError;
  },
  validate() {
    var errors = _.compact(this.models.map((model) => {
      model.isValid();
      return model.validationError;
    }));
    return _.isEmpty(errors) ? null : errors;
  },
  testRestrictions() {
    _.invoke(this.models, 'testRestrictions', restrictionModels);
  }
});

VmWareModels.NovaCompute = BaseModel.extend({
  constructorName: 'NovaCompute',
  checkEmptyTargetNode() {
    var targetNode = this.get('target_node');
    if (targetNode.current && targetNode.current.id == 'invalid') {
      this.validationError = this.validationError || {};
      this.validationError.target_node = i18n('vmware.invalid_target_node');
    }
  },
  checkDuplicateField(keys, fieldName) {
    /*jshint validthis:true */
    var fieldValue = this.get(fieldName);
    if (fieldValue.length > 0 && keys[fieldName] && keys[fieldName][fieldValue]) {
      this.validationError = this.validationError || {};
      this.validationError[fieldName] = i18n('vmware.duplicate_value');
    }
    keys[fieldName] = keys[fieldName] || {};
    keys[fieldName][fieldValue] = true;
  },
  checkDuplicates(keys) {
    this.checkDuplicateField(keys, 'vsphere_cluster');
    this.checkDuplicateField(keys, 'service_name');

    var targetNode = this.get('target_node') || {};
    if (targetNode.current) {
      if (targetNode.current.id && targetNode.current.id != 'controllers' &&
        keys.target_node && keys.target_node[targetNode.current.id]) {
        this.validationError = this.validationError || {};
        this.validationError.target_node = i18n('vmware.duplicate_value');
      }
      keys.target_node = keys.target_node || {};
      keys.target_node[targetNode.current.id] = true;
    }
  }
});

var NovaComputes = BaseCollection.extend({
  constructorName: 'NovaComputes',
  model: VmWareModels.NovaCompute,
  validate() {
    this._super('validate', arguments);

    var keys = {vsphere_clusters: {}, service_names: {}};
    this.invoke('checkDuplicates', keys);
    this.invoke('checkEmptyTargetNode');

    var errors = _.compact(_.pluck(this.models, 'validationError'));
    return _.isEmpty(errors) ? null : errors;
  }
});

var AvailabilityZone = BaseModel.extend({
  constructorName: 'AvailabilityZone',
  constructor(data) {
    Backbone.Model.apply(this, arguments);
    if (data) {
      this.set(this.parse(data));
    }
  },
  parse(response) {
    var result = {};
    var metadata = response.metadata;
    result.metadata = metadata;

    // regular fields
    _.each(metadata, (field) => {
      if (VmWareModels.isRegularField(field)) {
        result[field.name] = response[field.name];
      }
    }, this);

    // nova_computes
    var novaMetadata = _.find(metadata, {name: 'nova_computes'});
    var novaValues = _.clone(response.nova_computes);
    novaValues = _.map(novaValues, (value) => {
      value.metadata = novaMetadata.fields;
      return new VmWareModels.NovaCompute(value);
    });
    result.nova_computes = new NovaComputes(novaValues);

    return result;
  },
  toJSON() {
    var result = _.omit(this.attributes, 'metadata', 'nova_computes');
    result.nova_computes = this.get('nova_computes').toJSON();
    return result;
  },
  validate() {
    var errors = _.merge({}, BaseModel.prototype.validate.call(this));

    var novaComputes = this.get('nova_computes');
    novaComputes.isValid();
    if (novaComputes.validationError) {
      errors.nova_computes = novaComputes.validationError;
    }

    return _.isEmpty(errors) ? null : errors;
  }
});

var AvailabilityZones = BaseCollection.extend({
  constructorName: 'AvailabilityZones',
  model: AvailabilityZone
});

VmWareModels.Network = BaseModel.extend({constructorName: 'Network'});
VmWareModels.Glance = BaseModel.extend({constructorName: 'Glance'});

VmWareModels.VCenter = BaseModel.extend({
  constructorName: 'VCenter',
  url() {
    return '/api/v1/clusters/' + this.id + '/vmware_attributes' + (this.loadDefaults ? '/defaults' : '');
  },
  parse(response) {
    if (!response.editable || !response.editable.metadata || !response.editable.value) {
      return;
    }
    var metadata = response.editable.metadata || [];
    var value = response.editable.value || {};

    // Availability Zone(s)
    var azMetadata = _.find(metadata, {name: 'availability_zones'});
    var azValues = _.clone(value.availability_zones);
    azValues = _.map(azValues, (value) => {
      value.metadata = azMetadata.fields;
      return value;
    });

    // Network
    var networkMetadata = _.find(metadata, {name: 'network'});
    var networkValue = _.extend(_.clone(value.network), {metadata: networkMetadata.fields});

    // Glance
    var glanceMetadata = _.find(metadata, {name: 'glance'});
    var glanceValue = _.extend(_.clone(value.glance), {metadata: glanceMetadata.fields});

    return {
      metadata: metadata,
      availability_zones: new AvailabilityZones(azValues),
      network: new VmWareModels.Network(networkValue),
      glance: new VmWareModels.Glance(glanceValue)
    };
  },
  isFilled() {
    var result = this.get('availability_zones') && this.get('network') && this.get('glance');
    return !!result;
  },
  toJSON() {
    if (!this.isFilled()) {
      return {};
    }
    return {
      editable: {
        value: {
          availability_zones: this.get('availability_zones').toJSON(),
          network: this.get('network').toJSON(),
          glance: this.get('glance').toJSON()
        }
      }
    };
  },
  validate() {
    if (!this.isFilled()) {
      return null;
    }

    var errors = {};
    _.each(this.get('metadata'), (field) => {
      var model = this.get(field.name);
      // do not validate disabled restrictions
      var isDisabled = this.checkRestrictions(restrictionModels, undefined, field);
      if (isDisabled.result) {
        return;
      }
      model.isValid();
      if (model.validationError) {
        errors[field.name] = model.validationError;
      }
    });

    // check unassigned nodes exist
    var assignedNodes = {};
    var availabilityZones = this.get('availability_zones') || [];
    availabilityZones.each((zone) => {
      var novaComputes = zone.get('nova_computes') || [];
      novaComputes.each((compute) => {
        var targetNode = compute.get('target_node');
        assignedNodes[targetNode.current.id] = targetNode.current.label;
      });
    });
    var unassignedNodes = restrictionModels.cluster.get('nodes').filter((node) => {
      return _.contains(node.get('pending_roles'), 'compute-vmware') && !assignedNodes[node.get('hostname')];
    });
    if (unassignedNodes.length > 0) {
      errors.unassigned_nodes = unassignedNodes;
    }

    return _.isEmpty(errors) ? null : errors;
  },
  setModels(models) {
    restrictionModels = models;
    return this;
  }
});

export default VmWareModels;
