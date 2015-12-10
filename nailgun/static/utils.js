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
    'require',
    'jquery',
    'underscore',
    'i18n',
    'backbone',
    'classnames',
    'javascript-natural-sort',
    'expression',
    'expression/objects',
    'react',
    'ip'
], function(require, $, _, i18n, Backbone, classNames, naturalSort, Expression, expressionObjects, React, IP) {
    'use strict';

    var utils = {
        regexes: {
            url: /(?:https?:\/\/([\-\w\.]+)+(:\d+)?(\/([\w\/_\-\.]*(\?[\w\/_\-\.&%]*)?(#[\w\/_\-\.&%]*)?)?)?)/,
            ip: /^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$/,
            mac: /^([0-9a-f]{1,2}[\.:-]){5}([0-9a-f]{1,2})$/,
            cidr: /^(?:(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\/([1-9]|[1-2]\d|3[0-2])$/,
            nodeNetworkGroupName: /^[\w-.]+$/
        },
        serializeTabOptions: function(options) {
            return _.map(options, function(value, key) {
                return key + ':' + value;
            }).join(';');
        },
        deserializeTabOptions: function(serializedOptions) {
            return _.object(_.map((serializedOptions || '').split(';'), function(option) {
                return option.split(':');
            }));
        },
        getNodeListFromTabOptions: function(options) {
            var nodeIds = utils.deserializeTabOptions(options.screenOptions[0]).nodes,
                ids = nodeIds ? nodeIds.split(',').map((id) => parseInt(id, 10)) : [],
                models = require('models'),
                nodes = new models.Nodes(options.cluster.get('nodes').getByIds(ids));
            if (nodes.length == ids.length) return nodes;
        },
        renderMultilineText: function(text) {
            if (!text) return null;
            return <div>{text.split('\n').map((str, index) => <p key={index}>{str}</p>)}</div>;
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
        // FIXME(vkramskikh): moved here from healthcheck_tab to make testable
        highlightTestStep: function(text, step) {
            return text.replace(new RegExp('(^|\\s*)(' + step + '\\.[\\s\\S]*?)(\\s*\\d+\\.|$)'), '$1<b>$2</b>$3');
        },
        classNames: classNames,
        parseModelPath: function(path, models) {
            var modelPath = new expressionObjects.ModelPath(path);
            modelPath.setModel(models);
            return modelPath;
        },
        evaluateExpression: function(expression, models, options) {
            var compiledExpression = new Expression(expression, models, options),
                value = compiledExpression.evaluate();
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
        showErrorDialog: function(options) {
            var dialogs = require('views/dialogs'); // avoid circular dependencies
            options.message = options.response ? utils.getResponseText(options.response) :
                options.message || i18n('dialog.error_dialog.server_error');
            dialogs.ErrorDialog.show(options);
        },
        showBandwidth: function(bandwidth) {
            bandwidth = parseInt(bandwidth, 10);
            if (!_.isNumber(bandwidth) || _.isNaN(bandwidth)) {return i18n('common.not_available');}
            return (bandwidth / 1000).toFixed(1) + ' Gbps';
        },
        showFrequency: function(frequency) {
            frequency = parseInt(frequency, 10);
            if (!_.isNumber(frequency) || _.isNaN(frequency)) {return i18n('common.not_available');}
            var base = 1000;
            var treshold = 1000;
            return (frequency >= treshold ? (frequency / base).toFixed(2) + ' GHz' : frequency + ' MHz');
        },
        showSize: function(bytes, treshold) {
            bytes = parseInt(bytes, 10);
            if (!_.isNumber(bytes) || _.isNaN(bytes)) {return i18n('common.not_available');}
            var base = 1024;
            treshold = treshold || 256;
            var units = ['byte', 'kb', 'mb', 'gb', 'tb'];
            var i, result, unit = 'tb';
            for (i = 0; i < units.length; i += 1) {
                result = bytes / Math.pow(base, i);
                if (result < treshold) {
                    unit = units[i];
                    break;
                }
            }
            return (result ? result.toFixed(1) : result) + ' ' + i18n('common.size.' + unit, {count: result});
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
                error[field] = i18n('cluster_page.network_tab.validation.invalid_vlan');
                return error;
            }
            if (_.contains(_.compact(forbiddenVlans), vlan)) {
                error[field] = i18n('cluster_page.network_tab.validation.forbidden_vlan');
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
                        error[field] = i18n('cluster_page.network_tab.validation.large_network');
                    } else if (prefix > 30) {
                        error[field] = i18n('cluster_page.network_tab.validation.small_network');
                    }
                } else {
                    error[field] = i18n('cluster_page.network_tab.validation.invalid_cidr');
                }
            } else {
                error[field] = i18n('cluster_page.network_tab.validation.invalid_cidr');
            }
            return error[field] ? error : {};
        },
        validateIP: function(ip) {
            return _.isString(ip) && !!ip.match(utils.regexes.ip);
        },
        validateIPRanges: function(ranges, cidr, existingRanges = [], warnings = {}) {
            var ipRangesErrors = [],
                ns = 'cluster_page.network_tab.validation.';
            _.defaults(warnings, {
                INVALID_IP: i18n(ns + 'invalid_ip'),
                DOES_NOT_MATCH_CIDR: i18n(ns + 'ip_does_not_match_cidr'),
                INVALID_IP_RANGE: i18n(ns + 'invalid_ip_range'),
                EMPTY_IP_RANGE: i18n(ns + 'empty_ip_range'),
                IP_RANGES_INTERSECTION: i18n(ns + 'ip_ranges_intersection')
            });

            if (_.any(ranges, (range) => _.compact(range).length)) {
                _.each(ranges, (range, index) => {
                    if (_.any(range)) {
                        var error = {};

                        if (!utils.validateIP(range[0])) {
                            error.start = warnings.INVALID_IP;
                        } else if (cidr && !utils.validateIpCorrespondsToCIDR(cidr, range[0])) {
                            error.start = warnings.DOES_NOT_MATCH_CIDR;
                        }

                        if (!utils.validateIP(range[1])) {
                            error.end = warnings.INVALID_IP;
                        } else if (cidr && !utils.validateIpCorrespondsToCIDR(cidr, range[1])) {
                            error.end = warnings.DOES_NOT_MATCH_CIDR;
                        }

                        if (_.isEmpty(error)) {
                            if (IP.toLong(range[0]) > IP.toLong(range[1])) {
                                error.start = error.end = warnings.INVALID_IP_RANGE;
                            } else if (_.isUndefined(cidr)) {
                                error.start = error.end = warnings.IP_RANGE_IS_NOT_IN_PUBLIC_CIDR;
                            } else if (existingRanges.length) {
                                var intersection = utils.checkIPRangesIntersection(range, existingRanges);
                                if (intersection) {
                                    error.start = error.end = warnings.IP_RANGES_INTERSECTION + intersection.join(' - ');
                                }
                            }
                        }

                        if (!_.isEmpty(error)) {
                            ipRangesErrors.push(_.extend(error, {index: index}));
                        }
                    }
                });
            } else {
                ipRangesErrors.push({
                    index: 0,
                    start: warnings.EMPTY_IP_RANGE,
                    end: warnings.EMPTY_IP_RANGE
                });
            }
            return ipRangesErrors;
        },
        checkIPRangesIntersection: function([startIP, endIP], existingRanges) {
            var startIPInt = IP.toLong(startIP),
                endIPInt = IP.toLong(endIP);
            return _.find(existingRanges, ([ip1, ip2]) => IP.toLong(ip2) >= startIPInt && IP.toLong(ip1) <= endIPInt);
        },
        validateIpCorrespondsToCIDR: function(cidr, ip) {
            if (!cidr) return true;
            var networkData = IP.cidrSubnet(cidr),
                ipInt = IP.toLong(ip);
            return ipInt >= IP.toLong(networkData.firstAddress) && ipInt <= IP.toLong(networkData.lastAddress);
        },
        validateVlanRange: function(vlanStart, vlanEnd, vlan) {
            return vlan >= vlanStart && vlan <= vlanEnd;
        },
        getDefaultGatewayForCidr: function(cidr) {
            if (!_.isEmpty(utils.validateCidr(cidr))) return '';
            return IP.cidrSubnet(cidr).firstAddress;
        },
        getDefaultIPRangeForCidr: function(cidr, excludeGateway) {
            if (!_.isEmpty(utils.validateCidr(cidr))) return [['', '']];
            var networkData = IP.cidrSubnet(cidr);
            if (excludeGateway) {
                var startIPInt = IP.toLong(networkData.firstAddress);
                startIPInt++;
                return [[IP.fromLong(startIPInt), networkData.lastAddress]];
            }
            return [[networkData.firstAddress, networkData.lastAddress]];
        },
        sortEntryProperties: function(entry, sortOrder) {
            sortOrder = sortOrder || ['name'];
            var properties = _.keys(entry);
            return _.sortBy(properties, function(property) {
                var index = _.indexOf(sortOrder, property);
                return index == -1 ? properties.length : index;
            });
        },
        getResponseText: function(response, defaultText) {
            var serverErrorMessage = defaultText || i18n('dialog.error_dialog.server_error');
            var serverUnavailableMessage = i18n('dialog.error_dialog.server_unavailable');
            if (response && (!response.status || response.status >= 400)) {
                if (!response.status || response.status == 502) return serverUnavailableMessage;
                if (response.status == 500) return serverErrorMessage;
                // parsing new backend response format in responseText
                response = response.responseText || response;
                try {
                    response = JSON.parse(response);
                    return response.message || serverErrorMessage;
                } catch (exception) {
                    return serverErrorMessage;
                }
            }
            return '';
        },
        natsort: function(str1, str2, options = {}) {
            var {insensitive, desc} = options;
            naturalSort.insensitive = insensitive;
            return naturalSort(str1, str2) * (desc ? -1 : 1);
        },
        multiSort: function(model1, model2, attributes) {
            var result = utils.compare(model1, model2, attributes[0]);
            if (result === 0 && attributes.length > 1) {
                attributes.splice(0, 1);
                result = utils.multiSort(model1, model2, attributes);
            }
            return result;
        },
        compare: function(model1, model2, options) {
            var getValue = function(model) {
                var attr = options.attr;
                return _.isFunction(model[attr]) ? model[attr]() : model.get(attr);
            };
            var value1 = getValue(model1),
                value2 = getValue(model2);
            if (_.isString(value1) && _.isString(value2)) {
                return utils.natsort(value1, value2, options);
            }
            var result;
            if (_.isNumber(value1) && _.isNumber(value2)) {
                result = value1 - value2;
            } else {
                result = value1 === value2 || !value1 && !value2 ? 0 : !value1 ? 1 : -1;
            }
            return options.desc ? -result : result;
        },
        composeDocumentationLink: function(link) {
            var isMirantisIso = _.contains(app.version.get('feature_groups'), 'mirantis'),
                release = app.version.get('release'),
                linkStart = isMirantisIso ? 'https://docs.mirantis.com/openstack/fuel/fuel-' :
                    'https://docs.fuel-infra.org/openstack/fuel/fuel-';
            return linkStart + release + '/' + link;
        }
};

    return utils;
});
