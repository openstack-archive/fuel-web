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

    class Sorter {
        constructor(name, order, isLabel) {
            this.name = name;
            this.order = order;
            this.title = isLabel ? name : i18n('cluster_page.nodes_tab.sorters.' + name, {defaultValue: name});
            this.isLabel = isLabel;
            return this;
        }

        static fromObject(sorterObject, isLabel) {
            var sorterName = _.keys(sorterObject)[0];
            return new Sorter(sorterName, sorterObject[sorterName], isLabel);
        }

        static toObject(sorter) {
            return {[sorter.name]: sorter.order};
        }
    }

    class Filter {
        constructor(name, values, isLabel) {
            this.name = name;
            this.values = values;
            this.title = isLabel ? name : i18n('cluster_page.nodes_tab.filters.' + name, {defaultValue: name});
            this.isLabel = isLabel;
            this.isNumberRange = !isLabel && !_.contains(['roles', 'status', 'manufacturer', 'group_id', 'cluster'], name);
            return this;
        }

        static fromObject(filters, isLabel) {
            return _.map(filters, (values, name) => new Filter(name, values, isLabel));
        }

        static toObject(filters) {
            return _.reduce(filters, (result, filter) => {
                result[filter.name] = filter.values;
                return result;
            }, {});
        }

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
    }

    return {
        Sorter: Sorter,
        Filter: Filter
    };
});
