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
    var NetworkTab, Network, NetworkingParameters, NetworkTabVerificationControl;

    NetworkTab = commonViews.Tab.extend({
        template: _.template(networkTabTemplate),
        updateInterval: 3000,
        hasChanges: false,
        events: {
            'click .verify-networks-btn:not([disabled])': 'verifyNetworks',
            'click .btn-revert-changes:not([disabled])': 'revertChanges',
            'click .apply-btn:not([disabled])': 'applyChanges'
        },
        defaultButtonsState: function() {
            var locked = this.isLocked();
            var errors = !!this.networkConfiguration.validationError;
            this.$('.btn.verify-networks-btn').attr('disabled', errors || locked);
            this.$('.btn.btn-revert-changes').attr('disabled', !(this.hasChanges || errors) || locked);
            this.$('.btn.apply-btn').attr('disabled', !this.hasChanges || errors || locked);
        },
        disableControls: function() {
            this.$('.btn, input, select').attr('disabled', true);
        },
        isLocked: function() {
            return this.model.task({group: ['deployment', 'network'], status: 'running'}) || !this.model.isAvailableForSettingsChanges();
        },
        checkForChanges: function() {
            this.hasChanges = !_.isEqual(this.model.get('networkConfiguration').toJSON(), this.networkConfiguration.toJSON());
            this.defaultButtonsState();
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
        verifyNetworks: function() {
            if (!this.networkConfiguration.validationError) {
                this.disableControls();
                this.removeEmptyRanges();
                this.page.removeFinishedTasks().always(_.bind(this.startVerification, this));
            }
        },
        removeEmptyRanges: function() {
            this.networkConfiguration.get('networks').each(function(network) {
                if (network.get('meta').notation == 'ip_ranges') {
                    network.set({ip_ranges: _.filter(network.get('ip_ranges'), function(range) {return _.compact(range).length;})}, {silent: true});
                }
            });
        },
        startVerification: function() {
            var task = new models.Task();
            var options = {
                method: 'PUT',
                url: _.result(this.model, 'url') + '/network_configuration/' + this.provider + '/verify',
                data: JSON.stringify(this.networkConfiguration)
            };
            task.save({}, options)
                .fail(_.bind(function() {
                    utils.showErrorDialog({title: $.t('cluster_page.network_tab.network_verification')});
                    this.defaultButtonsState();
                }, this))
                .always(_.bind(function() {
                    this.model.get('tasks').fetch({data: {cluster_id: this.model.id}}).done(_.bind(this.scheduleUpdate, this));
                }, this));
        },
        revertChanges: function() {
            this.setInitialData();
            this.page.removeFinishedTasks().always(_.bind(this.render, this));
        },
        applyChanges: function() {
            var deferred;
            if (!this.networkConfiguration.validationError) {
                this.disableControls();
                this.removeEmptyRanges();
                deferred = Backbone.sync('update', this.networkConfiguration, {url: _.result(this.model, 'url') + '/network_configuration/' + this.provider})
                    .done(_.bind(function(task) {
                        if (task && task.status == 'error') {
                            this.page.removeFinishedTasks().always(_.bind(function() {
                                this.defaultButtonsState();
                                this.model.fetch();
                                this.model.fetchRelated('tasks').done(_.bind(function() {
                                    this.page.removeFinishedTasks(null, true);
                                }, this));
                            }, this));
                        } else {
                            this.hasChanges = false;
                            this.model.set({networkConfiguration: new models.NetworkConfiguration(this.networkConfiguration.toJSON(), {parse: true})});
                            this.model.fetch();
                            this.model.fetchRelated('tasks');
                        }
                    }, this))
                    .fail(_.bind(function() {
                        utils.showErrorDialog({title: $.t('cluster_page.network_tab.title')});
                        this.defaultButtonsState();
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
        bindTaskEvents: function(task) {
            return task.match({group: ['deployment', 'network']}) ? task.on('change:status', this.render, this) : null;
        },
        onNewTask: function(task) {
            return this.bindTaskEvents(task) && this.render();
        },
        displayValidationError: function($el, error) {
            $el.addClass('error').parents('.network-attribute').find('.error .help-inline').text(error);
        },
        setInitialData: function() {
            this.hasChanges = false;
            this.networkConfiguration = new models.NetworkConfiguration(this.model.get('networkConfiguration').toJSON(), {parse: true});
            this.provider = this.model.get('net_provider');
            this.networkingParameters = this.networkConfiguration.get('networking_parameters');
            this.fixedAmount = this.networkingParameters.get('fixed_networks_amount') || 1;
            this.networkingParameters.on('change:net_manager', function(parameters, manager) {
                this.networkingParameters.set({fixed_networks_amount: manager == 'FlatDHCPManager' ? 1 : this.fixedAmount}, {silent: true});
                this.renderNetworks();
                this.renderNetworkingParameters();
                this.updateNetworkConfiguration();
            }, this);
            this.networkConfiguration.on('invalid', function(model, errors) {
                _.each(errors.networking_parameters, _.bind(function(error, field) {
                    if (!_.contains(field, 'floating')) {
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
                            var row = this.$('.floating .floating-ranges-rows .range-row:eq(' + range.index + ')');
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
        },
        updateNetworkConfiguration: function() {
            this.$('input[type=text]').removeClass('error').parents('.network-attribute').find('.help-inline').text('');
            this.networkConfiguration.isValid();
            this.checkForChanges();
            this.page.removeFinishedTasks();
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.networkConfiguration = new models.NetworkConfiguration();
            this.model.on('change:status', this.render, this);
            this.model.get('tasks').each(this.bindTaskEvents, this);
            this.model.get('tasks').on('add', this.onNewTask, this);
            this.model.get('tasks').on('remove', this.renderVerificationControl, this);
            if (!this.model.get('networkConfiguration')) {
                this.model.set({networkConfiguration: new models.NetworkConfiguration()});
                this.loading = this.model.get('networkConfiguration').fetch({url: _.result(this.model, 'url') + '/network_configuration/' + this.model.get('net_provider')})
                    .done(_.bind(function() {
                        this.setInitialData();
                        this.render();
                    }, this));
            } else {
                this.setInitialData();
            }
        },
        showVerificationErrors: function() {
            var task = this.model.task({group: 'network', status: 'error'});
            if (task && task.get('result').length) {
                _.each(task.get('result'), function(verificationError) {
                    _.each(verificationError.ids, function(networkId) {
                        _.each(verificationError.errors, function(field) {
                            this.$('div[data-network-id=' + networkId + ']').find('.' + field).children().addClass('error');
                        }, this);
                    }, this);
                }, this);
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
            var networkingParametersView = new NetworkingParameters({parameters: this.networkingParameters, tab: this});
            this.registerSubView(networkingParametersView);
            this.$('.networking-parameters').html(networkingParametersView.render().el);
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html(this.template({
                loading: this.loading,
                provider: this.provider,
                locked: this.isLocked(),
                segment_type: this.networkingParameters ? this.networkingParameters.get('segmentation_type') : null
            })).i18n();
            if (this.networkingParameters) {
                this.stickit(this.networkingParameters, {'input[name=net-manager]': 'net_manager'});
                this.renderNetworks();
                this.renderNetworkingParameters();
            }
            this.renderVerificationControl();
            this.defaultButtonsState();
            return this;
        }
    });

    Network = Backbone.View.extend({
        template: _.template(networkTemplate),
        rangeTemplate: _.template(rangeTemplate),
        events: {
            'click .ip-ranges-add:not([disabled])': 'addIPRange',
            'click .ip-ranges-delete:not([disabled])': 'deleteIPRange'
        },
        bindings: {
            'input[name=gateway]': 'gateway',
            'input[name=cidr]': 'cidr'
        },
        floatingRangeBindings: {},
        changeIpRanges: function(e, addRange) {
            var floating = !!$(e.currentTarget).parents('.floating').length;
            var netBlock = floating ? this.$('.floating') : this.$('div[data-network-id=' + this.network.id + ']');
            var index = netBlock.find('.range-row').index($(e.currentTarget).parents('.range-row'));
            var model = floating ? this.tab.networkingParameters : this.network;
            var field = floating ? this.floatingRange : 'ip_ranges';
            var ipRanges = _.cloneDeep(model.get(field));
            if (addRange) {
                ipRanges.splice(index + 1, 0, ['','']);
            } else {
                ipRanges.splice(index, 1);
            }
            model.set(field, ipRanges, {silent: true});
            this.render();
            this.tab.networkConfiguration.isValid();
        },
        addIPRange: function(e) {
            this.changeIpRanges(e, true);
        },
        deleteIPRange: function(e) {
            this.changeIpRanges(e, false);
        },
        stickitNetwork: function () {
            this.stickit(this.network, _.merge(this.bindings, this.tab.composeVlanBindings.call(this)));
            this.stickit(this.tab.networkingParameters, this.floatingRangeBindings);
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.network.on('change', this.tab.updateNetworkConfiguration, this.tab);
            this.floatingRange = this.network.get('meta').floating_range_var;
        },
        renderIpRanges: function(config) {
            config = config || {
                domClass: 'ip',
                observe: 'ip_ranges',
                model: this.network,
                bindings: this.bindings
            };
            var rangesBlockSelector = '.' + config.domClass + '-ranges-rows';
            this.$(rangesBlockSelector).empty();
            var ranges = config.model.get(config.observe);
            _.each(ranges, function(range, rangeIndex) {
                this.$(rangesBlockSelector).append(this.rangeTemplate({
                    index: rangeIndex,
                    removalPossible: ranges.length > 1,
                    locked: this.tab.isLocked()
                }));
                _.each(range, function(ip, index) {
                    config.bindings[rangesBlockSelector + ' input[name=range' + index + '][data-range=' + rangeIndex + ']'] = {
                        observe: config.observe,
                        onGet: function(value, options) { return value[rangeIndex][index]; },
                        getVal: function($el) {
                            var ipRanges = _.cloneDeep(config.model.get(config.observe));
                            ipRanges[$el.data('range')][index] = $el.val();
                            return ipRanges;
                        }
                    };
                }, this);
            }, this);
        },
        render: function() {
            this.$el.html(this.template({
                network: this.network,
                networkConfig: this.network.get('meta'),
                netManager: this.tab.networkingParameters.get('net_manager'),
                locked: this.tab.isLocked()
            })).i18n();
            if (this.network.get('meta').notation == 'ip_ranges') {
                this.renderIpRanges();
            }
            if (this.floatingRange) {
                this.renderIpRanges({
                    domClass: 'floating',
                    observe: this.floatingRange,
                    model: this.tab.networkingParameters,
                    bindings: this.floatingRangeBindings
                });
            }
            this.stickitNetwork();
            return this;
        }
    });

    NetworkingParameters = Backbone.View.extend({
        template: _.template(networkingParametersTemplate),
        initialize: function(options) {
            _.defaults(this, options);
            this.parameters.on('change:fixed_networks_amount', function(parameters, amount) { this.tab.fixedAmount = amount; }, this);
            this.parameters.on('change', this.tab.updateNetworkConfiguration, this.tab);
        },
        composeRangeFieldBindings: function(observe, index) {
            var bindings = {};
            bindings['.' + observe + '-row input[name=range' + index + ']'] = {
                observe: observe,
                onGet: function(value) { return value[index]; },
                getVal: _.bind(function($el) {
                    var range = _.clone(this.parameters.get(observe));
                    range[this.$('.' + observe + '-row .range').index($el)] = $el.val();
                    return range;
                }, this)
            };
            return bindings;
        },
        stickitParameters: function() {
            var bindings = {
                'input[name=fixed_networks_cidr]': 'fixed_networks_cidr',
                'input[name=base_mac]': 'base_mac',
                'input[name=internal_cidr]': 'internal_cidr',
                'input[name=internal_gateway]': 'internal_gateway',
                'select[name=fixed_network_size]': {
                    observe: 'fixed_network_size',
                    selectOptions: {
                        collection: function() {
                            return _.map([8, 16, 32, 64, 128, 256, 512, 1024, 2048], function(size) {
                                return {value: size, label: size};
                            });
                        }
                    }
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
            };
            var segmentation = this.parameters.get('segmentation_type');
            if (segmentation) {
                var idRangeAttr = segmentation == 'gre' ? 'gre_id_range' : 'vlan_range';
                _.each(this.parameters.get(idRangeAttr), function(id, index) {
                    _.merge(bindings, this.composeRangeFieldBindings(idRangeAttr, index));
                }, this);
            }
            _.each(this.parameters.get('dns_nameservers'), function(nameserver, index) {
                _.merge(bindings, this.composeRangeFieldBindings('dns_nameservers', index));
            }, this);
            this.stickit(this.parameters, _.merge(bindings, this.tab.composeVlanBindings.call(this, 'fixed_networks_vlan_start')));
        },
        render: function() {
            this.$el.html(this.template({
                netManager: this.parameters.get('net_manager'),
                segmentation: this.parameters.get('segmentation_type'),
                locked: this.tab.isLocked()
            })).i18n();
            this.stickitParameters();
            return this;
        }
    });

    NetworkTabVerificationControl = Backbone.View.extend({
        template: _.template(networkTabVerificationControlTemplate),
        initialize: function(options) {
            _.defaults(this, options);
        },
        render: function() {
            this.$el.html(this.template({
                cluster: this.cluster,
                networks: this.networks
            })).i18n();
            return this;
        }
    });

    return NetworkTab;
});
