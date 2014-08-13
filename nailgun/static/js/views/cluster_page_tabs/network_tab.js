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
define(
[
    'utils',
    'models',
    'views/common',
    'views/dialogs',
    'text!templates/cluster/network_tab.html',
    'text!templates/cluster/network.html',
    'text!templates/cluster/range_field.html',
    'text!templates/cluster/networking_parameters.html',
    'text!templates/cluster/verify_network_control.html'
],
function(utils, models, commonViews, dialogViews, networkTabTemplate, networkTemplate, rangeTemplate, networkingParametersTemplate, networkTabVerificationControlTemplate) {
    'use strict';
    var NetworkTab, NetworkTabSubview, Network, NetworkingParameters, NetworkTabVerificationControl;

    NetworkTab = commonViews.Tab.extend({
        template: _.template(networkTabTemplate),
        updateInterval: 3000,
        events: {
            'click .verify-networks-btn:not([disabled])': 'verifyNetworks',
            'click .btn-revert-changes:not([disabled])': 'revertChanges',
            'click .apply-btn:not([disabled])': 'applyChanges'
        },
        calculateButtonsState: function() {
            var hasChanges = this.hasChanges();
            var locked = this.isLocked();
            var errors = !!this.networkConfiguration.validationError;
            this.$('.btn.verify-networks-btn').attr('disabled', errors || !!this.model.task({group: ['deployment', 'network'], status: 'running'}));
            this.$('.btn.btn-revert-changes').attr('disabled', !(hasChanges || errors) || locked);
            this.$('.btn.apply-btn').attr('disabled', !hasChanges || errors || locked);
        },
        disableControls: function() {
            this.$('.btn, input, select').attr('disabled', true);
        },
        isLocked: function() {
            return this.model.task({group: ['deployment', 'network'], status: 'running'}) || !this.model.isAvailableForSettingsChanges();
        },
        hasChanges: function() {
            return !_.isEqual(this.initialConfiguration.toJSON(), this.networkConfiguration.toJSON());
        },
        verifyNetworks: function() {
            if (!this.networkConfiguration.validationError) {
                this.disableControls();
                this.prepareIpRanges();
                this.page.removeFinishedNetworkTasks().always(_.bind(this.startVerification, this));
            }
        },
        prepareIpRanges: function() {
            var removeEmptyRanges = function(ranges) {
                return _.filter(ranges, function(range) {return _.compact(range).length;});
            };
            this.networkConfiguration.get('networks').each(function(network) {
                if (network.get('meta').notation == 'ip_ranges') {
                    network.set({ip_ranges: removeEmptyRanges(network.get('ip_ranges'))});
                }
            });
            var floatingRanges = this.networkConfiguration.get('networking_parameters').get('floating_ranges');
            if (floatingRanges) {
                this.networkConfiguration.get('networking_parameters').set({floating_ranges: removeEmptyRanges(floatingRanges)});
            }
        },
        startVerification: function() {
            var task = new models.Task();
            var options = {
                method: 'PUT',
                url: _.result(this.networkConfiguration, 'url') + '/verify',
                data: JSON.stringify(this.networkConfiguration)
            };
            task.save({}, options)
                .fail(_.bind(function() {
                    utils.showErrorDialog({
                        title: $.t('cluster_page.network_tab.verify_networks.verification_error.title'),
                        message: $.t('cluster_page.network_tab.verify_networks.verification_error.start_verification_warning')
                    });
                    this.calculateButtonsState();
                }, this))
                .always(_.bind(function() {
                    this.model.fetchRelated('tasks').done(_.bind(this.scheduleUpdate, this));
                }, this));
        },
        revertChanges: function() {
            this.loadInitialConfiguration();
            this.page.removeFinishedNetworkTasks().always(_.bind(this.render, this));
        },
        beforeTearDown: function() {
            this.loadInitialConfiguration();
        },
        loadInitialConfiguration: function() {
            this.networkConfiguration.clear().set(new models.NetworkConfiguration(this.initialConfiguration.toJSON(), {parse: true}).attributes);
        },
        updateInitialConfiguration: function() {
            this.initialConfiguration = new models.NetworkConfiguration(this.networkConfiguration.toJSON(), {parse: true});
        },
        applyChanges: function() {
            var deferred;
            if (!this.networkConfiguration.validationError) {
                this.disableControls();
                this.prepareIpRanges();
                deferred = Backbone.sync('update', this.networkConfiguration)
                    .done(_.bind(function(task) {
                        if (task && task.status == 'error') {
                            this.page.removeFinishedNetworkTasks().always(_.bind(function() {
                                this.calculateButtonsState();
                                this.model.fetch();
                                this.model.fetchRelated('tasks').done(_.bind(function() {
                                    this.page.removeFinishedNetworkTasks(true);
                                }, this));
                            }, this));
                        } else {
                            this.updateInitialConfiguration();
                            this.model.fetch();
                            this.model.fetchRelated('tasks');
                        }
                    }, this))
                    .fail(_.bind(function() {
                        utils.showErrorDialog({title: $.t('cluster_page.network_tab.verify_networks.verification_error.title')});
                        this.calculateButtonsState();
                        this.model.fetch();
                        this.model.fetchRelated('tasks');
                    }, this));
            } else {
                deferred = new $.Deferred();
                deferred.reject();
            }
            return deferred;
        },
        scheduleUpdate: function() {
            if (this.model.task('verify_networks', 'running')) {
                this.registerDeferred($.timeout(this.updateInterval).done(_.bind(this.update, this)));
            }
        },
        update: function() {
            var task = this.model.task('verify_networks', 'running');
            if (task) {
                this.registerDeferred(task.fetch().always(_.bind(this.scheduleUpdate, this)));
            }
        },
        displayValidationError: function($el, error) {
            $el.addClass('error').parents('.network-attribute').find('.error .help-inline').text(error);
        },
        updateNetworkConfiguration: function() {
            this.$('input[type=text]').removeClass('error').parents('.network-attribute').find('.help-inline').text('');
            this.networkConfiguration.isValid();
            this.calculateButtonsState();
            this.page.removeFinishedNetworkTasks();
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.model.on('change:status', this.render, this);
            this.model.get('tasks').bindToView(this, [{group: ['deployment', 'network']}], function(task) {
                task.on('change:status', this.render, this);
            }, this.render, this.renderVerificationControl);
            this.initialConfiguration = new models.NetworkConfiguration();
            this.networkConfiguration = this.model.get('networkConfiguration');
            this.networkConfiguration.on('invalid', function(model, errors) {
                _.each(errors.networking_parameters, _.bind(function(error, field) {
                    if (field != 'floating_ranges') {
                        if (_.isArray(error)) {
                            _.each(error, _.bind(function(msg, index) {
                                if (msg) {
                                    this.displayValidationError(this.$('.' + field + '-row input[name=range' + index + ']'), msg);
                                }
                            }, this));
                        } else {
                            this.displayValidationError(this.$('.networking-parameters input[name=' + field + ']'), error);
                        }
                    } else {
                        _.each(errors.networking_parameters[field], _.bind(function(range) {
                            var row = this.$('.floating-ranges-rows .range-row:eq(' + range.index + ')');
                            row.find('input:first').toggleClass('error', !!range.start);
                            row.find('input:last').toggleClass('error', !!range.end);
                            row.find('.help-inline').text(range.start || range.end);
                        }, this));
                    }
                }, this));
                _.each(errors.networks, _.bind(function(networkErrors, networkId) {
                    _.each(networkErrors, _.bind(function(error, field) {
                        if (field != 'ip_ranges') {
                            this.displayValidationError(this.$('div[data-network-id="' + networkId + '"] input[name=' + field + ']'), error);
                        } else {
                            _.each(networkErrors.ip_ranges, _.bind(function(range) {
                                var row = this.$('div[data-network-id="' + networkId + '"] .ip-ranges-rows .range-row:eq(' + range.index + ')');
                                row.find('input:first').toggleClass('error', !!range.start);
                                row.find('input:last').toggleClass('error', !!range.end);
                                row.find('.help-inline').text(range.start || range.end);
                            }, this));
                        }
                    }, this));
                }, this));
            }, this);
            (this.loading = $.when(this.model.get('settings').fetch({cache: true}), this.networkConfiguration.fetch({cache: true}))).done(_.bind(this.updateInitialConfiguration, this));
            if (this.loading.state() == 'pending') {
                this.loading.done(_.bind(this.render, this));
            }
        },
        renderVerificationControl: function() {
            var verificationView = new NetworkTabVerificationControl({
                cluster: this.model,
                networks: this.networkConfiguration.get('networks')
            });
            this.registerSubView(verificationView);
            this.$('.verification-control').html(verificationView.render().el);
            this.showVerificationErrors();
            if (this.hasChanges()) {
                this.page.removeFinishedNetworkTasks(true);
            }
        },
        showVerificationErrors: function() {
            var task = this.model.task({group: 'network', status: 'error'});
            if (task && task.get('result').length) {
                _.each(task.get('result'), function(verificationError) {
                    _.each(verificationError.ids, function(networkId) {
                        _.each(verificationError.errors, function(field) {
                            this.$('div[data-network-id=' + networkId + '] input[name="' + field + '"]').addClass('error');
                        }, this);
                    }, this);
                }, this);
            }
        },
        renderNetworks: function() {
            this.$('.networks-table').html('');
            this.networkConfiguration.get('networks').each(function(network) {
                if (network.get('meta').configurable) {
                    var networkView = new Network({network: network, tab: this});
                    this.registerSubView(networkView);
                    this.$('.networks-table').append(networkView.render().el);
                }
            }, this);
        },
        renderNetworkingParameters: function() {
            var networkingParametersView = new NetworkingParameters({parameters: this.networkConfiguration.get('networking_parameters'), tab: this});
            this.registerSubView(networkingParametersView);
            this.$('.networking-parameters').html(networkingParametersView.render().el);
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            var networkingParameters = this.networkConfiguration.get('networking_parameters');
            this.$el.html(this.template({
                loading: this.loading,
                provider: this.model.get('net_provider'),
                locked: this.isLocked(),
                segment_type: networkingParameters ? networkingParameters.get('segmentation_type') : null,
                l23_provider: networkingParameters ? networkingParameters.get('net_l23_provider') : null
            })).i18n();
            if (this.loading.state() != 'pending') {
                this.stickit(networkingParameters, {'input[name=net-manager]': 'net_manager'});
                // FIXME: quick hack for vCenter feature support.
                // Reverse dependensies on OpenStack settings should be implemented.
                this.$('input[name=net-manager]').attr('disabled', this.model.get('settings').get('common.libvirt_type.value') == 'vcenter' || this.isLocked());
                this.renderNetworks();
                this.renderNetworkingParameters();
                this.calculateButtonsState();
                this.renderVerificationControl();
            }
            return this;
        }
    });

    NetworkTabSubview = Backbone.View.extend({
        rangeTemplate: _.template(rangeTemplate),
        events: {
            'click .ip-ranges-control button:not([disabled])': 'changeIPRanges',
            'focus .autocomplete input:last': 'autoCompleteIPRanges'
        },
        changeIPRanges: function(e) {
            var config = this.ipRangesConfig;
            var rowIndex = this.$('.' + config.domSelector + '-ranges-rows').find('.range-row').index($(e.currentTarget).parents('.range-row'));
            var ipRanges = _.cloneDeep(config.model.get(config.attribute));
            if (this.$(e.currentTarget).hasClass('ip-ranges-add')) {
                ipRanges.splice(rowIndex + 1, 0, ['','']);
            } else {
                ipRanges.splice(rowIndex, 1);
            }
            config.model.set(config.attribute, ipRanges);
        },
        autoCompleteIPRanges: function(e) {
            var config = this.ipRangesConfig;
            var rowIndex = this.$('.' + config.domSelector + '-ranges-rows').find('.range-row').index(this.$(e.currentTarget).parents('.range-row'));
            var ipRanges = _.cloneDeep(config.model.get(config.attribute));
            var startIP = ipRanges[rowIndex][0];
            if (!ipRanges[rowIndex][1] && !utils.validateIP(startIP)) {
                ipRanges[rowIndex][1] = startIP;
                config.model.set(config.attribute, ipRanges);
                var input = this.$(e.currentTarget)[0];
                if (input.setSelectionRange) {
                    var startPos = _.lastIndexOf(startIP, '.') + 1;
                    var endPos = startIP.length;
                    _.defer(function() { input.setSelectionRange(startPos, endPos); });
                }
            }
        },
        composeIpRangesBindings: function() {
            var config = this.ipRangesConfig;
            _.each(config.model.get(config.attribute), function(range, rangeIndex) {
                _.each(range, function(ip, index) {
                    this.bindings['.' + config.domSelector + '-ranges-rows input[name=range' + index + '][data-range=' + rangeIndex + ']'] = {
                        observe: config.attribute,
                        onGet: function(value, options) {
                            return value[rangeIndex] ? value[rangeIndex][index] : null;
                        },
                        getVal: function($el) {
                            var ipRanges = _.cloneDeep(config.model.get(config.attribute));
                            ipRanges[$el.data('range')][index] = $el.val();
                            return ipRanges;
                        }
                    };
                }, this);
            }, this);
        },
        renderIpRanges: function() {
            var config = this.ipRangesConfig;
            var $el = this.$('.' + config.domSelector + '-ranges-rows');
            $el.html('');
            var ip_ranges = config.model.get(config.attribute);
            _.each(ip_ranges, function(range, rangeIndex) {
                $el.append(this.rangeTemplate({
                    index: rangeIndex,
                    removalPossible: ip_ranges.length > 1,
                    locked: this.tab.isLocked()
                }));
            }, this);
            this.composeIpRangesBindings();
            this.stickit(config.model);
        },
        composeVlanBindings: function(observe) {
            observe = observe || 'vlan_start';
            var vlanInput = this.$('input[name=' + observe + ']');
            var bindings = {};
            bindings['.vlan-tagging input[type=checkbox]'] = {
                observe: observe,
                onGet: function(value) {
                    vlanInput.toggle(!_.isNull(value));
                    return !_.isNull(value);
                },
                onSet: function(value) {
                    vlanInput.toggle(!!value);
                    if (value) {
                        vlanInput.focus();
                    }
                    return value ? '' : null;
                }
            };
            bindings['input[name=' + observe + ']'] = {
                stickitChange: this.network,
                observe: observe,
                onSet: function(value) {
                    return Number(value) || '';
                }
            };
            return bindings;
        },
        composeRangeFieldBindings: function(observe, index, convertToNumber) {
            var bindings = {};
            bindings['.' + observe + '-row input[name=range' + index + ']'] = {
                observe: observe,
                onGet: function(value) { return value[index]; },
                getVal: _.bind(function($el) {
                    var range = _.clone(this.parameters.get(observe));
                    range[this.$('.' + observe + '-row .range').index($el)] = convertToNumber ? Number($el.val()) : $el.val();
                    return range;
                }, this)
            };
            return bindings;
        }
    });

    Network = NetworkTabSubview.extend({
        template: _.template(networkTemplate),
        bindings: {
            'input[name=gateway]': 'gateway',
            'input[name=cidr]': 'cidr'
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.ipRangesConfig = {model: this.network, attribute: 'ip_ranges', domSelector: 'ip'};
            this.network.on('change:ip_ranges', function(network, ip_ranges) {
                if (ip_ranges.length != network.previous('ip_ranges').length) {
                    this.renderIpRanges();
                }
            }, this);
            this.network.on('change', this.tab.updateNetworkConfiguration, this.tab);
        },
        render: function() {
            this.$el.html(this.template({network: this.network, locked: this.tab.isLocked()})).i18n();
            if (this.network.get('meta').notation == 'ip_ranges') {
                this.renderIpRanges();
            }
            this.stickit(this.network, _.merge(this.bindings, this.composeVlanBindings()));
            return this;
        }
    });

    NetworkingParameters = NetworkTabSubview.extend({
        template: _.template(networkingParametersTemplate),
        bindings: {
            'input[name=fixed_networks_cidr]': 'fixed_networks_cidr',
            'input[name=base_mac]': 'base_mac',
            'input[name=internal_cidr]': 'internal_cidr',
            'input[name=internal_gateway]': 'internal_gateway',
            'select[name=fixed_network_size]': {
                observe: 'fixed_network_size',
                selectOptions: {collection: _.map(_.range(3, 12), _.partial(Math.pow, 2))}
            },
            'input[name=fixed_networks_amount]': {
                observe: 'fixed_networks_amount',
                onSet:function(value) {
                    return Number(value) || '';
                }
            },
            'input[name=vlan_end]': {
                observe: ['fixed_networks_vlan_start', 'fixed_networks_amount'],
                onGet: function(value) {
                    if (!value[0] || !value[1]) {
                        return '';
                    }
                    var vlanEnd = value[0] + value[1] - 1;
                    return vlanEnd > 4094 ? 4094 : vlanEnd;
                }
            }
        },
        updateFixedAmount: function() {
            this.fixedAmount = this.parameters.get('fixed_networks_amount') || 1;
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.ipRangesConfig = {model: this.parameters, attribute: 'floating_ranges', domSelector: 'floating'};
            this.parameters.on('change:net_manager', function(parameters, manager) {
                parameters.set({fixed_networks_amount: manager == 'FlatDHCPManager' ? 1 : this.fixedAmount}, {silent: true});
                this.render();
            }, this);
            this.parameters.on('change:fixed_networks_amount', this.updateFixedAmount, this);
            this.parameters.on('change:floating_ranges', function(parameters, floating_ranges) {
                if (floating_ranges.length != parameters.previous('floating_ranges').length) {
                    this.renderIpRanges();
                }
            }, this);
            this.parameters.on('change', this.tab.updateNetworkConfiguration, this.tab);
        },
        composeBindings: function() {
            var segmentation = this.parameters.get('segmentation_type');
            if (segmentation) {
                var idRangeAttr = segmentation == 'gre' ? 'gre_id_range' : 'vlan_range';
                _.each(this.parameters.get(idRangeAttr), function(id, index) {
                    _.merge(this.bindings, this.composeRangeFieldBindings(idRangeAttr, index, true));
                }, this);
            }
            _.each(this.parameters.get('dns_nameservers'), function(nameserver, index) {
                _.merge(this.bindings, this.composeRangeFieldBindings('dns_nameservers', index));
            }, this);
           _.merge(this.bindings, this.composeVlanBindings('fixed_networks_vlan_start'));
        },
        render: function() {
            this.$el.html(this.template({
                netManager: this.parameters.get('net_manager'),
                segmentation: this.parameters.get('segmentation_type'),
                locked: this.tab.isLocked()
            })).i18n();
            this.composeBindings();
            this.renderIpRanges();
            this.stickit(this.parameters);
            this.updateFixedAmount();
            return this;
        }
    });

    NetworkTabVerificationControl = Backbone.View.extend({
        template: _.template(networkTabVerificationControlTemplate),
        initialize: function(options) {
            _.defaults(this, options);
        },
        render: function() {
            this.$el.html(this.template({cluster: this.cluster, networks: this.networks})).i18n();
            return this;
        }
    });

    return NetworkTab;
});
