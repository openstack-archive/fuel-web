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

define(
[
    'jquery',
    'underscore',
    'i18n',
    'backbone',
    'models'
],
($, _, i18n, Backbone, models) => {
    'use strict';

    function isRegularField(field) {
        return _.contains(['text', 'password', 'checkbox', 'select'], field.type);
    }

    // models for testing restrictions
    let restrictionModels = {};

    // Test regex using regex cache
    let regexCache = {};
    function testRegex(regexText, value) {
        if (!regexCache[regexText]) {
            regexCache[regexText] = new RegExp(regexText);
        }
        return regexCache[regexText].test(value);
    }

    let BaseModel = Backbone.Model.extend(models.superMixin).extend(models.cacheMixin).extend(models.restrictionMixin).extend({
        constructorName: 'BaseModel',
        cacheFor: 60 * 1000,
        toJSON() {
            return _.omit(this.attributes, 'metadata');
        },
        validate() {
            this.expandedRestrictions = this.expandedRestrictions || {};
            let result = {};
            _.each(this.attributes.metadata, function(field) {
                if (!isRegularField(field) || field.type == 'checkbox') {
                    return;
                }
                let isDisabled = this.checkRestrictions(restrictionModels, undefined, field.name);
                if (isDisabled.result) {
                    return;
                }
                let value = this.get(field.name);
                if (field.regex) {
                    if (!testRegex(field.regex.source, value)) {
                        result[field.name] = field.regex.error;
                    }
                }
            }, this);
            return _.isEmpty(result) ? null : result;
        },
        parseRestrictions() {
            let metadata = this.get('metadata');
            _.each(metadata, function(field) {
                let key = field.name,
                    restrictions = field.restrictions || [],
                    childModel = this.get(key);
                this.expandRestrictions(restrictions, key);

                if (_.isFunction(childModel.parseRestrictions)) {
                    childModel.parseRestrictions();
                }
            }, this);
        },
        testRestrictions() {
            let results = {
                hide: {},
                disable: {}
            };
            let metadata = this.get('metadata');
            _.each(metadata, function(field) {
                let key = field.name;
                let disableResult = this.checkRestrictions(restrictionModels, undefined, key);
                results.disable[key] = disableResult;

                let hideResult = this.checkRestrictions(restrictionModels, 'hide', key);
                results.hide[key] = hideResult;
            }, this);
            return results;
        }
    });

    let BaseCollection = Backbone.Collection.extend(models.superMixin).extend(models.cacheMixin).extend({
        constructorName: 'BaseCollection',
        model: BaseModel,
        cacheFor: 60 * 1000,
        isValid() {
            this.validationError = this.validate();
            return this.validationError;
        },
        validate() {
            let errors = _.compact(this.models.map((model) => {
                model.isValid();
                return model.validationError;
            }));
            return _.isEmpty(errors) ? null : errors;
        },
        parseRestrictions() {
            _.invoke(this.models, 'parseRestrictions');
        },
        testRestrictions() {
            _.invoke(this.models, 'testRestrictions', restrictionModels);
        }
    });

    let NovaCompute = BaseModel.extend({
        constructorName: 'NovaCompute',
        checkEmptyTargetNode() {
            let targetNode = this.get('target_node');
            if (targetNode.current && targetNode.current.id == 'invalid') {
                this.validationError = this.validationError || {};
                this.validationError.target_node = i18n('vmware.invalid_target_node');
            }
        },
        checkDuplicateField(keys, fieldName) {
            /*jshint validthis:true */
            let fieldValue = this.get(fieldName);
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

            let targetNode = this.get('target_node') || {};
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

    let NovaComputes = BaseCollection.extend({
        constructorName: 'NovaComputes',
        model: NovaCompute,
        validate() {
            this._super('validate', arguments);

            let keys = {vsphere_clusters: {}, service_names: {}};
            this.invoke('checkDuplicates', keys);
            this.invoke('checkEmptyTargetNode');

            let errors = _.compact(_.pluck(this.models, 'validationError'));
            return _.isEmpty(errors) ? null : errors;
        }
    });

    let AvailabilityZone = BaseModel.extend({
        constructorName: 'AvailabilityZone',
        constructor(data) {
            Backbone.Model.apply(this, arguments);
            if (data) {
                this.set(this.parse(data));
            }
        },
        parse(response) {
            let result = {};
            let metadata = response.metadata;
            result.metadata = metadata;

            // regular fields
            _.each(metadata, (field) => {
                if (isRegularField(field)) {
                    result[field.name] = response[field.name];
                }
            }, this);

            // nova_computes
            let novaMetadata = _.find(metadata, {name: 'nova_computes'});
            let novaValues = _.clone(response.nova_computes);
            novaValues = _.map(novaValues, (value) => {
                value.metadata = novaMetadata.fields;
                return new NovaCompute(value);
            });
            result.nova_computes = new NovaComputes(novaValues);

            return result;
        },
        toJSON() {
            let result = _.omit(this.attributes, 'metadata', 'nova_computes');
            result.nova_computes = this.get('nova_computes').toJSON();
            return result;
        },
        validate() {
            let errors = _.merge({}, BaseModel.prototype.validate.call(this));

            let novaComputes = this.get('nova_computes');
            novaComputes.isValid();
            if (novaComputes.validationError) {
                errors.nova_computes = novaComputes.validationError;
            }

            return _.isEmpty(errors) ? null : errors;
        }
    });

    let AvailabilityZones = BaseCollection.extend({
        constructorName: 'AvailabilityZones',
        model: AvailabilityZone
    });

    let Network = BaseModel.extend({constructorName: 'Network'});
    let Glance = BaseModel.extend({constructorName: 'Glance'});

    let VCenter = BaseModel.extend({
        constructorName: 'VCenter',
        url() {
            return '/api/v1/clusters/' + this.id + '/vmware_attributes' + (this.loadDefaults ? '/defaults' : '');
        },
        parse(response) {
            if (!response.editable || !response.editable.metadata || !response.editable.value) {
                return;
            }
            let metadata = response.editable.metadata || [],
                value = response.editable.value || {};

            // Availability Zone(s)
            let azMetadata = _.find(metadata, {name: 'availability_zones'});
            let azValues = _.clone(value.availability_zones);
            azValues = _.map(azValues, (value) => {
                value.metadata = azMetadata.fields;
                return value;
            });

            // Network
            let networkMetadata = _.find(metadata, {name: 'network'});
            let networkValue = _.extend(_.clone(value.network), {metadata: networkMetadata.fields});

            // Glance
            let glanceMetadata = _.find(metadata, {name: 'glance'});
            let glanceValue = _.extend(_.clone(value.glance), {metadata: glanceMetadata.fields});

            return {
                metadata: metadata,
                availability_zones: new AvailabilityZones(azValues),
                network: new Network(networkValue),
                glance: new Glance(glanceValue)
            };
        },
        isFilled() {
            let result = this.get('availability_zones') && this.get('network') && this.get('glance');
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

            let errors = {};
            _.each(this.get('metadata'), function(field) {
                let key = field.name;
                let model = this.get(key);
                // do not validate disabled restrictions
                let isDisabled = this.checkRestrictions(restrictionModels, undefined, key);
                if (isDisabled.result) {
                    return;
                }
                model.isValid();
                if (model.validationError) {
                    errors[key] = model.validationError;
                }
            }, this);

            // check unassigned nodes exist
            let assignedNodes = {};
            let availabilityZones = this.get('availability_zones') || [];
            availabilityZones.each(function(zone) {
                let novaComputes = zone.get('nova_computes') || [];
                novaComputes.each((compute) => {
                    let targetNode = compute.get('target_node');
                    assignedNodes[targetNode.current.id] = targetNode.current.label;
                }, this);
            }, this);
            let unassignedNodes = restrictionModels.cluster.get('nodes').filter((node) => {
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

    return {
        VCenter: VCenter,
        AvailabilityZone: AvailabilityZone,
        Network: Network,
        Glance: Glance,
        NovaCompute: NovaCompute,
        isRegularField: isRegularField
    };
});
