/*
 * Copyright 2014 Mirantis, Inc.
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
    'utils',
    'deepModel',
    'backbone-lodash-monkeypatch'
],
function($, _, i18n, Backbone) {
    'use strict';

    function isRegularField(field) {
        return field.type == 'text' || field.type == 'password' || field.type == 'checkbox';
    }

    // Test regex using regex cache
    var regexCache = {};
    function testRegex(regexText, value) {
        if (!regexCache[regexText]) {
            regexCache[regexText] = new RegExp(regexText);
        }
        return regexCache[regexText].test(value);
    }

    var FieldSetModel = Backbone.Model.extend({
        constructorName: 'FieldSetModel',
        toJSON: function() {
            return _.omit(this.attributes, 'metadata');
        },
        validate: function() {
            var result = {};
            _.each(this.attributes.metadata, function(field) {
                if (!isRegularField(field)) {
                    return;
                }
                var value = this.get(field.name);
                if (value && field.regex) {
                    if (!testRegex(field.regex.source, value)) {
                        result[field.name] = field.regex.error;
                    }
                }
            }, this);
            return _.isEmpty(result) ? null : result;
        }
    });

    var Cinder = FieldSetModel.extend({constructorName: 'Cinder'});
    var NovaCompute = FieldSetModel.extend({constructorName: 'NovaCompute'});

    var NovaComputes = Backbone.Collection.extend({
        constructorName: 'NovaComputes',
        model: NovaCompute,
        isValid: function() {
            this.validationError = this.validate();
            return this.validationError;
        },
        validate: function() {
            var errors = _.compact(this.models.map(function(model) {
                model.isValid();
                return model.validationError;
            }));
            return _.isEmpty(errors) ?  null : errors;
        }
    });

    var AvailabilityZone = Backbone.Model.extend({
        constructorName: 'AvailabilityZone',
        constructor: function(data) {
            Backbone.Model.apply(this, {});
            if (data) {
                this.parse(data);
            }
        },
        parse: function(response) {
            var metadata = response.metadata;
            this.set('metadata', metadata);

            // regular fields
            _.each(metadata, function(field) {
                if (field.type == 'text' || field.type == 'checkbox' || field.type == 'password') {
                    this.set(field.name, response[field.name]);
                }
            }, this);

            // nova_computes
            var novaMetadata = _.find(metadata, function(field) {
                return field.name == 'nova_computes';
            });
            var novaValues = _.clone(response.nova_computes);
            novaValues = _.map(novaValues, function(value) {
                value.metadata = novaMetadata.fields;
                return new NovaCompute(value);
            });
            this.set('nova_computes', new NovaComputes(novaValues));

            // cinder
            var cinderMetadata = _.find(metadata, function(field) {
                return field.name == 'cinder';
            });
            var cinderValue = _.extend(_.clone(response.cinder), {metadata: cinderMetadata.fields});
            this.set('cinder', new Cinder(cinderValue));
        },
        toJSON: function() {
            var result = _.omit(this.attributes, 'metadata', 'nova_computes', 'cinder');
            result.nova_computes = this.get('nova_computes').toJSON();
            result.cinder = this.get('cinder').toJSON();
            return result;
        },
        validate: function() {
            var errors = _.merge({}, FieldSetModel.prototype.validate.call(this));

            var novaComputes = this.get('nova_computes');
            novaComputes.isValid();
            if (novaComputes.validationError) {
                errors.nova_computes = novaComputes.validationError;
            }

            var cinder = this.get('cinder');
            cinder.isValid();
            if (cinder.validationError) {
                errors.cinder = cinder.validationError;
            }

            return _.isEmpty(errors) ? null : errors;
        }
    });

    var AvailabilityZones = Backbone.Collection.extend({
        constructorName: 'AvailabilityZones',
        model: AvailabilityZone,
        isValid: function() {
            this.validationError = this.validate();
            return this.validationError;
        },
        validate: function() {
            var errors = _.compact(this.models.map(function(model) {
                model.isValid();
                return model.validationError;
            }));
            return _.isEmpty(errors) ?  null : errors;
        }
    });

    var Network =  FieldSetModel.extend({constructorName: 'Network'});
    var Glance = FieldSetModel.extend({constructorName: 'Glance'});

    var VCenter = Backbone.Model.extend({
        constructorName: 'VCenter',
        url: function() {
            return '/api/vmware/' + this.id + '/settings' + (this.loadDefaults ? '/defaults' : '');
        },
        parse: function(response) {
            if (!response.editable || !response.editable.metadata || !response.editable.value) {
                return;
            }
            var metadata = response.editable.metadata || [],
                value = response.editable.value || {};

            // Availability Zone(s)
            var azMetadata = _.find(metadata, function(field) {
                return field.name == 'availability_zones';
            });
            var azValues = _.clone(value.availability_zones);
            azValues = _.map(azValues, function(value) {
                value.metadata = azMetadata.fields;
                return value;
            });
            this.set('availability_zones', new AvailabilityZones(azValues));

            // Network
            var networkMetadata = _.find(metadata, function(field) {
                return field.name == 'network';
            });
            var networkValue = _.extend(_.clone(value.network), {metadata: networkMetadata.fields});
            this.set('network', new Network(networkValue));

            // Glance
            var glanceMetadata = _.find(metadata, function(field) {
                return field.name == 'glance';
            });
            var glanceValue = _.extend(_.clone(value.glance), {metadata: glanceMetadata.fields});
            this.set('glance', new Glance(glanceValue));
        },
        toJSON: function() {
            if (!this.get('availability_zones') || !this.get('network') || !this.get('glance')) {
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
        validate: function() {
            if (!this.get('availability_zones') || !this.get('network') || !this.get('glance')) {
                return null;
            }

            var errors = {};
            _.each(['availability_zones', 'network', 'glance'], function(key) {
                var model = this.get(key);
                model.isValid();
                if (model.validationError) {
                    errors[key] = model.validationError;
                }
            }, this);
            return _.isEmpty(errors) ? null : errors;
        }
    });

    return {
        VCenter: VCenter,
        AvailabilityZone: AvailabilityZone,
        Network: Network,
        Glance: Glance,
        NovaCompute: NovaCompute
    };
});
