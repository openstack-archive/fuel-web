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

define(['require', 'expression', 'expression/objects', 'react'], function(require, Expression, expressionObjects, React) {
    'use strict';

    var utils = {
        regexes: {
            url: /(?:https?:\/\/([\-\w\.]+)+(:\d+)?(\/([\w\/_\-\.]*(\?\S+)?)?)?)/,
            ip: /^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$/,
            mac: /^([0-9a-fA-F]{2}:){5}([0-9a-fA-F]{2})$/,
            cidr: /^(?:(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\/([1-9]|[1-2]\d|3[0-2])$/
        },
        serializeTabOptions: function(options) {
            return _.map(options, function(value, key) {
                return key + ':' + value;
            }).join(';');
        },
        deserializeTabOptions: function(serializedOptions) {
            return _.object(_.map(serializedOptions.split(';'), function(option) {
                return option.split(':');
            }));
        },
        linebreaks: function(text) {
            return text.replace(/\n/g, '<br/>');
        },
        composeLink: function(url) {
            return '<a target="_blank" href="' + url + '">' + url + '</a>';
        },
        urlify: function(text) {
            return utils.linebreaks(text).replace(new RegExp(utils.regexes.url.source, 'g'), utils.composeLink);
        },
        composeList: function(value) {
            return _.isUndefined(value) ? [] : _.isArray(value) ? value : [value];
        },
        parseModelPath: function(path, models) {
            var modelPath = new expressionObjects.ModelPath(path);
            modelPath.setModel(models);
            return modelPath;
        },
        evaluateExpression: function(expression, models, options) {
            var compiledExpression = new Expression(expression, models, options);
            var value = compiledExpression.evaluate();
            return {
                value: value,
                modelPaths: compiledExpression.modelPaths
            };
        },
        expandRestriction: function(restriction) {
            var result = {
                action: 'disable',
                message: null
            };
            if (_.isString(restriction)) {
                result.condition = restriction;
            } else if (_.isPlainObject(restriction)) {
                if (_.has(restriction, 'condition')) {
                    _.extend(result, restriction);
                } else {
                    result.condition = _.keys(restriction)[0];
                    result.message = _.values(restriction)[0];
                }
            } else {
                throw new Error('Invalid restriction format');
            }
            return result;
        },
        universalMount: function(view, el, parentView) {
            if (view instanceof Backbone.View) {
                view.render();
                if (el) {
                    $(el).html(view.el);
                }
                if (parentView) {
                    parentView.registerSubView(view);
                }
                return view;
            } else {
                var node = $(el)[0];
                var mountedComponent = React.renderComponent(view, node);
                // FIXME(vkramskikh): we need to store node to which
                // we mounted the component since it is not always
                // possible to determine the node: if render() returns
                // null, getDOMNode() also returns null
                mountedComponent._mountNode = node;
                return mountedComponent;
            }
        },
        universalUnmount: function(view) {
            if (view instanceof Backbone.View) {
                view.tearDown();
            } else {
                React.unmountComponentAtNode(view._mountNode || view.getDOMNode().parentNode);
            }
        },
        showDialog: function(dialog) {
            return React.renderComponent(dialog, $('#modal-container')[0]);
        },
        showErrorDialog: function(options, parentView) {
            parentView = parentView || app.page;
            var dialogViews = require('jsx!views/dialogs'); // avoid circular dependencies
            var dialog = new dialogViews.Dialog();
            parentView.registerSubView(dialog);
            dialog.render(_.extend({error: true}, options));
        },
        showBandwidth: function(bandwidth) {
            bandwidth = parseInt(bandwidth, 10);
            if (!_.isNumber(bandwidth) || _.isNaN(bandwidth)) {return $.t('common.not_available');}
            return (bandwidth / 1000).toFixed(1) + ' Gbps';
        },
        showFrequency: function(frequency) {
            frequency = parseInt(frequency, 10);
            if (!_.isNumber(frequency) || _.isNaN(frequency)) {return $.t('common.not_available');}
            var base = 1000;
            var treshold = 1000;
            return (frequency >= treshold ? (frequency / base).toFixed(2) + ' GHz' : frequency + ' MHz');
        },
        showSize: function(bytes, treshold) {
            bytes = parseInt(bytes, 10);
            if (!_.isNumber(bytes) || _.isNaN(bytes)) {return $.t('common.not_available');}
            var base = 1024;
            treshold = treshold || 256;
            var units = ['byte', 'kb', 'mb', 'gb', 'tb'];
            var i, result;
            for (i = 0; i < units.length; i += 1) {
                result = bytes / Math.pow(base, i);
                if (result < treshold) {
                    return (result ? result.toFixed(1) : result) + ' ' + $.t('common.size.' + units[i], {count: result});
                }
            }
            return result;
        },
        showMemorySize: function(bytes) {
            return utils.showSize(bytes, 1024);
        },
        showDiskSize: function(value, power) {
            power = power || 0;
            return utils.showSize(value * Math.pow(1024, power));
        },
        calculateNetworkSize: function(cidr) {
            return Math.pow(2, 32 - parseInt(_.last(cidr.split('/')), 10));
        },
        formatNumber: function(n) {
            return String(n).replace(/\d/g, function(c, i, a) {
                return i > 0 && c !== '.' && (a.length - i) % 3 === 0 ? ',' + c : c;
            });
        },
        floor: function(n, decimals) {
            return Math.floor(n * Math.pow(10, decimals)) / Math.pow(10, decimals);
        },
        isNaturalNumber: function(n) {
            return _.isNumber(n) && n > 0 && n % 1 === 0;
        },
        validateVlan: function(vlan, forbiddenVlans, field, disallowNullValue) {
            var error = {};
            if ((_.isNull(vlan) && disallowNullValue) || (!_.isNull(vlan) && (!utils.isNaturalNumber(vlan) || vlan < 1 || vlan > 4094))) {
                error[field] = $.t('cluster_page.network_tab.validation.invalid_vlan');
                return error;
            }
            if (_.contains(_.compact(forbiddenVlans), vlan)) {
                error[field] = $.t('cluster_page.network_tab.validation.forbidden_vlan');
            }
            return error[field] ? error : {};
        },
        validateCidr: function(cidr, field) {
            field = field || 'cidr';
            var error = {}, match;
            if (_.isString(cidr)) {
                match = cidr.match(utils.regexes.cidr);
                if (match) {
                    var prefix = parseInt(match[1], 10);
                    if (prefix < 2) {
                        error[field] = $.t('cluster_page.network_tab.validation.large_network');
                    } else if (prefix > 30) {
                        error[field] = $.t('cluster_page.network_tab.validation.small_network');
                    }
                } else {
                    error[field] = $.t('cluster_page.network_tab.validation.invalid_cidr');
                }
            } else {
                error[field] = $.t('cluster_page.network_tab.validation.invalid_cidr');
            }
            return error[field] ? error : {};
        },
        validateIP: function(ip) {
            return !_.isString(ip) || !ip.match(utils.regexes.ip);
        },
        validateIPrange: function(startIP, endIP) {
            return utils.ipIntRepresentation(startIP) - utils.ipIntRepresentation(endIP) <= 0;
        },
        validateIpRanges: function(ranges, cidr) {
            var ipRangesErrors = [];
            if (_.filter(ranges, function(range) {return _.compact(range).length;}).length) {
                _.each(ranges, function(range, i) {
                    if (range[0] || range[1]) {
                        var error = {index: i};
                        if (utils.validateIP(range[0]) || !utils.validateIpCorrespondsToCIDR(cidr, range[0])) {
                            error.start = $.t('cluster_page.network_tab.validation.invalid_ip_start');
                        } else if (utils.validateIP(range[1]) || !utils.validateIpCorrespondsToCIDR(cidr, range[1])) {
                            error.end = $.t('cluster_page.network_tab.validation.invalid_ip_end');
                        } else if (!utils.validateIPrange(range[0], range[1])) {
                            error.start = $.t('cluster_page.network_tab.validation.invalid_ip_range');
                        }
                        if (error.start || error.end) {
                            ipRangesErrors.push(error);
                        }
                    }
                });
            } else {
                ipRangesErrors.push({index: 0, start: $.t('cluster_page.network_tab.validation.empty_ip_range')});
            }
            return ipRangesErrors;
        },
        ipIntRepresentation: function(ip) {
            return _.reduce(ip.split('.'), function(sum, octet, index) {return sum + octet * Math.pow(256, 3 - index);}, 0);
        },
        validateIpCorrespondsToCIDR: function(cidr, ip) {
            var result = true;
            if (cidr) {
                /* jshint bitwise: false */
                var networkAddressToInt = utils.ipIntRepresentation(cidr.split('/')[0]);
                var netmask = ~((Math.pow(2, 32) - 1) >>> cidr.split('/')[1]);
                var ipToInt = utils.ipIntRepresentation(ip);
                result = (networkAddressToInt & netmask).toString(16) == (ipToInt & netmask).toString(16);
                /* jshint bitwise: true */
            }
            return result;
        },
        validateVlanRange: function(vlanStart, vlanEnd, vlan) {
            return vlan >= vlanStart && vlan <= vlanEnd;
        },
        sortEntryProperties: function(entry, sortOrder) {
            sortOrder = sortOrder || ['name'];
            var properties = _.keys(entry);
            return _.sortBy(properties, function(property) {
                var index = _.indexOf(sortOrder, property);
                return index == -1 ? properties.length : index;
            });
        },
        getResponseText: function(response) {
            return _.contains([400, 409], response.status) ? response.responseText : '';
        }
    };

    return utils;
});
