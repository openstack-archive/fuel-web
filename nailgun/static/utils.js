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
    'expression',
    'expression/objects',
    'react'
], function(require, $, _, i18n, Backbone, classNames, Expression, expressionObjects, React) {
    'use strict';

    var utils = {
        regexes: {
            url: /(?:https?:\/\/([\-\w\.]+)+(:\d+)?(\/([\w\/_\-\.]*(\?[\w\/_\-\.&%]*)?(#[\w\/_\-\.&%]*)?)?)?)/,
            ip: /^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$/,
            mac: /^([0-9a-f]{1,2}[\.:-]){5}([0-9a-f]{1,2})$/,
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
        universalMount: function(ViewConstructor, options, el, parentView) {
            if (ViewConstructor.prototype instanceof Backbone.View) {
                var view = new ViewConstructor(options);
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
                var mountedComponent = React.render(React.createElement(ViewConstructor, options), node);
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
        showErrorDialog: function(options) {
            var dialogs = require('jsx!views/dialogs'); // avoid circular dependencies
            options.message = options.response ? utils.getResponseText(options.response) :
                options.message || i18n('dialog.error_dialog.warning');
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
            return !_.isString(ip) || !ip.match(utils.regexes.ip);
        },
        validateIPrange: function(startIP, endIP) {
            return utils.ipIntRepresentation(startIP) - utils.ipIntRepresentation(endIP) <= 0;
        },
        validateIpRanges: function(ranges, cidr, disallowSingleAddress) {
            var ipRangesErrors = [];
            if (_.filter(ranges, function(range) {return _.compact(range).length;}).length) {
                _.each(ranges, function(range, i) {
                    if (range[0] || range[1]) {
                        var error = {index: i};
                        if (utils.validateIP(range[0]) || !utils.validateIpCorrespondsToCIDR(cidr, range[0])) {
                            error.start = i18n('cluster_page.network_tab.validation.invalid_ip_start');
                        } else if (utils.validateIP(range[1]) || !utils.validateIpCorrespondsToCIDR(cidr, range[1])) {
                            error.end = i18n('cluster_page.network_tab.validation.invalid_ip_end');
                        } else if (!utils.validateIPrange(range[0], range[1])) {
                            error.start = i18n('cluster_page.network_tab.validation.invalid_ip_range');
                        } else if (disallowSingleAddress && range[0] == range[1]) {
                            error.start = i18n('cluster_page.network_tab.validation.invalid_ip_range_equal');
                        }
                        if (error.start || error.end) {
                            ipRangesErrors.push(error);
                        }
                    }
                });
            } else {
                ipRangesErrors.push({index: 0, start: i18n('cluster_page.network_tab.validation.empty_ip_range')});
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
            var defaultMessage = i18n('dialog.error_dialog.warning');
            if (response && response.status >= 400) {
                if (response.status == 500) return defaultMessage;
                // parsing new backend response format in responseText
                response = response.responseText || response;
                try {
                    response = JSON.parse(response);
                    return response.message || defaultMessage;
                } catch (exception) {
                    return defaultMessage;
                }
            }
            return '';
        },
        // Natural sorting, code taken from
        // https://github.com/javve/natural-sort
        // options:
        // insensitive (bool, default=false) -- case insensitive iff true
        // desc        (bool, default=false) -- sort in descending order iff true
        natsort: function(str1, str2, options) {
            options = options || {};
            var re = /(^-?[0-9]+(\.?[0-9]*)[df]?e?[0-9]?$|^0x[0-9a-f]+$|[0-9]+)/gi,
                // whitestring token regexp
                sre = /(^[ ]*|[ ]*$)/g,
                // date regexp
                dre = /(^([\w ]+,?[\w ]+)?[\w ]+,?[\w ]+\d+:\d+(:\d+)?[\w ]?|^\d{1,4}[\/\-]\d{1,4}[\/\-]\d{1,4}|^\w+, \w+ \d+, \d{4})/,
                // hex regexp
                hre = /^0x[0-9a-f]+$/i,
                ore = /^0/,
                caseInsensitive = function(s) {return options.insensitive && s.toLowerCase() || s;},
                // convert all to strings strip whitespace
                caseInsensitive1 = caseInsensitive(str1).replace(sre, '') || '',
                caseInsensitive2 = caseInsensitive(str2).replace(sre, '') || '',
                // chunk/tokenize
                chunks1 = caseInsensitive1.replace(re, '\0$1\0').replace(/\0$/, '').replace(/^\0/, '').split('\0'),
                chunks2 = caseInsensitive2.replace(re, '\0$1\0').replace(/\0$/, '').replace(/^\0/, '').split('\0'),
                // numeric, hex or date detection
                detect1 = parseInt(caseInsensitive1.match(hre)) || (chunks1.length != 1 && caseInsensitive1.match(dre) && Date.parse(caseInsensitive1)),
                detect2 = parseInt(caseInsensitive2.match(hre)) || detect1 && caseInsensitive2.match(dre) && Date.parse(caseInsensitive2) || null,
                numerical1, numerical2,
                mult = options.desc ? -1 : 1;
            // first try and sort Hex codes or Dates
            if (detect2)
                if (detect1 < detect2) return -1 * mult;
                if (detect1 > detect2) return 1 * mult;
            // natural sorting through split numeric strings and default strings
            for (var cLoc = 0, numS = Math.max(chunks1.length, chunks2.length); cLoc < numS; cLoc++) {
                // find floats not starting with '0', string or 0 if not defined (Clint Priest)
                numerical1 = !(chunks1[cLoc] || '').match(ore) && parseFloat(chunks1[cLoc]) || chunks1[cLoc] || 0;
                numerical2 = !(chunks2[cLoc] || '').match(ore) && parseFloat(chunks2[cLoc]) || chunks2[cLoc] || 0;
                // handle numeric vs string comparison - number < string - (Kyle Adams)
                if (isNaN(numerical1) !== isNaN(numerical2)) {
                    return (isNaN(numerical1)) ? 1 : -1;
                }
                // rely on string comparison if different types - i.e. '02' < 2 != '02' < '2'
                if (typeof numerical1 !== typeof numerical2) {
                    numerical1 += '';
                    numerical2 += '';
                }
                if (numerical1 < numerical2) return -1 * mult;
                if (numerical1 > numerical2) return 1 * mult;
            }
            return 0;
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
                result = !value1 && !value2 ? 0 : !value1 ? 1 : -1;
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
