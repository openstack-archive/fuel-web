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

    console.log('VmWare models loaded'); //TODO

    var AvailabilityZone = Backbone.Model.extend({
    });

    var AvailabilityZones = Backbone.Collection.extend({
        model: AvailabilityZone
    });

    var Network = Backbone.Model.extend({
    });

    var Glance = Backbone.Model.extend({
    });

    var VCenter = Backbone.Model.extend({
        constructorName: 'VCenter',
        url: function() {
            return '/api/vmware/' + this.id + '/settings';
        },
        parse: function (response) {
            var data = response.editable.value || {};
            var metadata = response.editable.metadata || [];

            // Availability Zone(s)
            // TODO

            // Network
            var networkMetadata = _.find(metadata, function (field) {
                return field.name == 'network'
            });
            var network = _.extend(_.clone(data.network || {}), {metadata: networkMetadata.fields});
            this.set('network', new Network(network));
            console.log('@@@', network, this.get('network'));

            // Glance
            var glanceMetadata = _.find(metadata, function (field) {
                return field.name == 'glance'
            });
            var glance = _.extend(_.clone(data.glance || {}), {metadata: glanceMetadata.fields});
            this.set('glance', new Glance(glance));
            console.log('@@@', glance, this.get('glance'));
        }
    });

    return {
        VCenter: VCenter,
        AvailabilityZone: AvailabilityZone,
        Network: Network,
        Glance: Glance
    };
});
