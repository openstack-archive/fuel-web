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
define(['require'], function(require) {
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
        urlify: function (text) {
            return utils.linebreaks(text).replace(new RegExp(utils.regexes.url.source, 'g'), utils.composeLink);
        },
        composeList: function(value) {
            return _.isUndefined(value) ? [] : _.isArray(value) ? value : [value];
        },
        showErrorDialog: function(options, parentView) {
            parentView = parentView || app.page;
            var dialogViews = require('views/dialogs'); // avoid circular dependencies
            var dialog = new dialogViews.Dialog();
            parentView.registerSubView(dialog);
            dialog.render(_.extend({title: '', message: ''}, options));
            dialog.displayErrorMessage(options);
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
            return(frequency >= treshold ? (frequency / base).toFixed(2) + ' GHz' : frequency + ' MHz');
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
        validateCidr: function(cidr, field) {
            field = field || 'cidr';
            var errors = {};
            var match;
            if (_.isString(cidr)) {
                match = cidr.match(utils.regexes.cidr);
                if (match) {
                    var prefix = parseInt(match[1], 10);
                    if (prefix < 2) {
                        errors[field] = 'Network is too large';
                    }
                    if (prefix > 30) {
                        errors[field] = 'Network is too small';
                    }
                } else {
                    errors[field] = 'Invalid CIDR';
                }
            } else {
                errors[field] = 'Invalid CIDR';
            }
            return errors;
        },
        validateIP: function(ip) {
            return !_.isString(ip) || !ip.match(utils.regexes.ip);
        },
        validateIPrange: function(startIP, endIP) {
            return this.ipIntRepresentation(startIP) - this.ipIntRepresentation(endIP) <= 0;
        },
        validateNetmask: function(netmask) {
            return utils.validateIP(netmask) || !this.ipIntRepresentation(netmask).toString(2).match(/^1+00+$/);
        },
        ipIntRepresentation: function(ip) {
            return _.reduce(ip.split('.'), function(sum, octet, index) {return sum + octet * Math.pow(256, 3 - index);}, 0);
        },
        validateIpCorrespondsToCIDR: function(cidr, ip) {
            /*jslint bitwise: true*/
            var networkAddressToInt = utils.ipIntRepresentation(cidr.split('/')[0]);
            var netmask = ~((Math.pow(2, 32) - 1) >>> cidr.split('/')[1]);
            var ipToInt = utils.ipIntRepresentation(ip);
            var result = (networkAddressToInt & netmask).toString(16) == (ipToInt & netmask).toString(16);
            /*jslint bitwise: false*/
            return result;
        },
        composeCidr: function(ip, netmask) {
            var netmaskInt = this.ipIntRepresentation(netmask);
            var ipInt = this.ipIntRepresentation(ip);
            var networkSize = netmaskInt.toString(2).match(/1/g).length;
            /*jslint bitwise: true*/
            var networkAddressInt = netmaskInt & ipInt;
            var networkAddress = [networkAddressInt >>> 24, networkAddressInt >>> 16 & 0xFF, networkAddressInt >>> 8 & 0xFF, networkAddressInt & 0xFF].join('.');
            /*jslint bitwise: false*/
            return networkAddress + '/' + networkSize;
        },
        validateVlanRange: function(vlanStart, vlanEnd, vlan) {
            return vlan >= vlanStart && vlan <= vlanEnd;
        }
    };

    return utils;
});
