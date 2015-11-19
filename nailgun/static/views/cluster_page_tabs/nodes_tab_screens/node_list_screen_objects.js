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
define(['underscore', 'i18n'], function(_, i18n) {
    'use strict';

    var objects = {
        Sorter(name, order, isLabel) {
            if (!this) return new objects.Sorter(name, order, isLabel);
            this.name = name;
            this.order = order;
            this.title = isLabel ? this.name : i18n('cluster_page.nodes_tab.sorters.' + this.name, {defaultValue: this.name});
            this.isLabel = isLabel;
            return this;
        },
        Filter(name, values, isLabel) {
            if (!this) return new objects.Filter(name, values, isLabel);
            this.name = name;
            this.values = values;
            this.title = isLabel ? this.name : i18n('cluster_page.nodes_tab.filters.' + this.name, {defaultValue: this.name});
            this.isLabel = isLabel;
            this.isNumberRange = !isLabel && !_.contains(['roles', 'status', 'manufacturer', 'group_id', 'cluster'], this.name);
            return this;
        }
    };

    _.extend(objects.Sorter, {
        fromObject(sorterObject, isLabel) {
            var sorterName = _.keys(sorterObject)[0];
            return new objects.Sorter(sorterName, sorterObject[sorterName], isLabel);
        },
        toObject(sorter) {
            var data = {};
            data[sorter.name] = sorter.order;
            return data;
        }
    });

    _.extend(objects.Filter, {
        fromObject(filters, isLabel) {
            return _.map(filters, function(values, name) {
                return new objects.Filter(name, values, isLabel);
            });
        },
        toObject(filters) {
            return _.reduce(filters, function(result, filter) {
                result[filter.name] = filter.values;
                return result;
            }, {});
        }
    });

    _.extend(objects.Filter.prototype, {
        updateLimits(nodes, updateValues) {
            if (this.isNumberRange) {
                var limits = [0, 0];
                if (nodes.length) {
                    var resources = nodes.invoke('resource', this.name);
                    limits = [_.min(resources), _.max(resources)];
                    if (this.name == 'hdd' || this.name == 'ram') {
                        limits = [Math.floor(limits[0] / Math.pow(1024, 3)), Math.ceil(limits[1] / Math.pow(1024, 3))];
                    }
                }
                this.limits = limits;
                if (updateValues) this.values = _.clone(limits);
            }
        }
    });

    return objects;
});
