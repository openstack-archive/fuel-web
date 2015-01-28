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
function($, _, i18n, Backbone, utils) {
    'use strict';

    var Cinder = Backbone.Model.extend({
        constructorName: 'Cinder'
    });

    var NovaCompute = Backbone.Model.extend({
        constructorName: 'NovaCompute'
    });

    var NovaComputes = Backbone.Collection.extend({
        constructorName: 'NovaComputes'
    });

    var AvailabilityZone = Backbone.Model.extend({
        constructorName: 'AvailabilityZone',
        constructor: function(data) {
            Backbone.Model.apply(this, {});
            if(data) {
                this.parse(data);
            }
        },
        parse: function(response) {
            var metadata = response.metadata;

            // regular fields
            _.each(metadata, function(field) {
                if(field.type=='text' || field.type=='checkbox') {
                    this.set(field.name, response[field.name]);
                }
            }, this);

            // nova_computes
            this.set('nova_computes', response.nova_computes);

            // cinder
            this.set('cinder', response.cinder);
        }
    });

    var AvailabilityZones = Backbone.Collection.extend({
        constructorName: 'AvailabilityZones',
        model: AvailabilityZone
    });

    var Network = Backbone.Model.extend({
        constructorName: 'Network'
    });

    var Glance = Backbone.Model.extend({
        constructorName: 'Glance'
    });

    var VCenter = Backbone.Model.extend({
        constructorName: 'VCenter',
        url: function() {
            return '/api/vmware/' + this.id + '/settings';
        },
        parse: function (response) {
            if(!response.editable || !response.editable.metadata || !response.editable.value){
                return;
            }
            var metadata = response.editable.metadata || [];
            var value = response.editable.value || {};

            // Availability Zone(s)
            var azMetadata = _.find(metadata, function (field) {
                return field.name == 'availability_zones';
            });
            var azValues = _.clone(value.availability_zones);
            azValues = _.map(azValues, function(value) {
                value.metadata = azMetadata.fields;
                return value;
            });
            this.set('availability_zones', new AvailabilityZones(azValues));

            // Network
            var networkMetadata = _.find(metadata, function (field) {
                return field.name == 'network';
            });
            var networkValue = _.extend(_.clone(value.network), {metadata: networkMetadata.fields});
            this.set('network', new Network(networkValue));

            // Glance
            var glanceMetadata = _.find(metadata, function (field) {
                return field.name == 'glance';
            });
            var glanceValue = _.extend(_.clone(value.glance), {metadata: glanceMetadata.fields});
            this.set('glance', new Glance(glanceValue));

            console.log('VCenter model =', this);
        }
    });

    return {
        VCenter: VCenter,
        AvailabilityZone: AvailabilityZone,
        Network: Network,
        Glance: Glance
    };
});
