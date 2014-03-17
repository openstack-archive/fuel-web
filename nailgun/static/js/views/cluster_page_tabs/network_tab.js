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
        defaultButtonsState: function(errors) {
            this.$('.btn.verify-networks-btn').attr('disabled', errors);
            this.$('.btn.btn-revert-changes').attr('disabled', !this.hasChanges && !errors);
            this.$('.btn.apply-btn').attr('disabled', !this.hasChanges || errors);
        },
        disableControls: function() {
            this.$('.btn, input, select').attr('disabled', true);
        },
        isLocked: function() {
            return this.model.task({group: ['deployment', 'network'], status: 'running'}) || !this.model.isAvailableForSettingsChanges();
        },
        checkForChanges: function() {
            this.hasChanges = !_.isEqual(this.model.get('networkConfiguration').toJSON(), this.networkConfiguration.toJSON());
            this.defaultButtonsState(!!this.networkConfiguration.validationError);
        },
        verifyNetworks: function() {
            if (!this.networkConfiguration.validationError) {
                this.disableControls();
                this.prepareNetworks();
                this.page.removeFinishedTasks().always(_.bind(this.startVerification, this));
            }
        },
        prepareNetworks: function() {
            this.networkConfiguration.get('networks').each(function(network) {
                if (network.get('meta').notation == 'ip_ranges') {
                    // remove empty IP ranges
                    network.set({ip_ranges: _.filter(network.get('ip_ranges'), function(range) {return _.compact(range).length;})}, {silent: true});
                }
            });
            var netManager = this.networkingParameters.get('net_manager');
            this.networkingParameters.set({fixed_networks_amount: netManager == 'VlanManager' ? this.fixedAmount : 1}, {silent: true});
        },
        startVerification: function() {
            var task = new models.Task();
            var options = {
                method: 'PUT',
                url: _.result(this.model, 'url') + '/network_configuration/' + this.provider + '/verify',
                data: JSON.stringify(this.networkConfiguration)
            };
            task.save({}, options)
                .done(_.bind(function() {
                    this.defaultButtonsState();
                }, this))
                .fail(_.bind(function() {
                    utils.showErrorDialog({title: $.t('cluster_page.network_tab.network_verification')});
                    this.$('.verify-networks-btn').prop('disabled', false);
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
                this.prepareNetworks();
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
        setInitialData: function() {
            this.hasChanges = false;
            this.networkConfiguration = new models.NetworkConfiguration(this.model.get('networkConfiguration').toJSON(), {parse: true});
            this.provider = this.model.get('net_provider');
            this.networkingParameters = this.networkConfiguration.get('networking_parameters');
            this.fixedAmount = this.provider == 'nova_network' ? this.networkingParameters.get('fixed_networks_amount') : 1;
            this.networkConfiguration.on('invalid', function(model, errors) {
                /*_.each(errors.dns_nameservers, _.bind(function(error, field) {
                    var fieldData = field.split('-');
                    this.$('.nova-nameservers .' + fieldData[0] + '-row input[name=range' + fieldData[1] + ']').addClass('error').parents('.network-attribute').find('.error .help-inline').text(error);
                }, this));
                _.each(errors.neutron_parameters, _.bind(function(error, field) {
                    var $el, fieldData = field.split('-');
                    if (_.contains(['floating', 'nameservers'], fieldData[0])) {
                        $el = this.$('.neutron-parameters .' + fieldData[0] + '-row input[name=range' + fieldData[1] + ']');
                    } else {
                        $el = this.$('.neutron-parameters input[name=' + field + ']');
                    }
                    $el.addClass('error').parents('.network-attribute').find('.error .help-inline').text(error);
                }, this));
                _.each(errors.networks, _.bind(function(networkErrors, network) {
                    _.each(networkErrors, _.bind(function(error, field) {
                        if (field != 'ip_ranges') {
                            this.$('.' + network + ' input[name=' + field + ']').addClass('error').parents('.network-attribute').find('.error .help-inline').text(error);
                        } else {
                            _.each(networkErrors.ip_ranges, _.bind(function(range) {
                                var row = this.$('.' + network + ' .ip-ranges-rows .range-row:eq(' + range.index + ')');
                                row.find('input:first').toggleClass('error', !!range.start);
                                row.find('input:last').toggleClass('error', !!range.end);
                                row.find('.help-inline').text(range.start || range.end);
                            }, this));
                        }
                    }, this));
                }, this));*/
            }, this);
            this.networkConfiguration.on('change:net_manager', function() {
                this.renderNetworks();
                this.updateNetworkConfiguration();
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
            if (this.networkConfiguration.get('networks')) {
                this.tearDownRegisteredSubViews();
                this.$('.networks-table').html('');
                this.networkConfiguration.get('networks').each(function(network) {
                    var networkView = new Network({network: network, tab: this});
                    this.registerSubView(networkView);
                    this.$('.networks-table').append(networkView.render().el);
                }, this);
            }
        },
        renderNetworkingParameters: function() {
            var networkingParameters = new NetworkingParameters({parameters: this.networkingParameters, tab: this});
            this.registerSubView(networkingParameters);
            this.$('.networking-parameters').html(networkingParameters.render().el);
        },
        render: function() {
            this.$el.html(this.template({
                loading: this.loading,
                provider: this.provider,
                locked: this.isLocked(),
                segment_type: this.networkingParameters.get('segmentation_type')
            })).i18n();
            this.stickit(this.networkingParameters, {'input[name=net-manager]': 'net_manager'});
            this.renderNetworks();
            this.renderNetworkingParameters();
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
        stickitNetwork: function() {
            var bindings = {
                'input[name=gateway]': 'gateway',
                'input[name=cidr]': 'cidr',
                '.vlan-tagging input[type=checkbox]': {
                    observe: 'vlan_start',
                    onGet: function(value) {
                        this.$('input[name=vlan_start]').toggle(!_.isNull(value));
                        return !_.isNull(value);
                    },
                    onSet: _.bind(function(value) {
                        this.$('input[name=vlan_start]').toggle(!!value);
                        if (value) {
                            this.$('input[name=vlan_start]').focus();
                        }
                        return value ? '' : null;
                    }, this)
                },
                'input[name=vlan_start]': {
                    observe: 'vlan_start',
                    onSet: function(value) {
                        return Number(value) || '';
                    }
                }
            };
            this.stickit(this.network, _.merge(bindings, this.ipRangeBindings));
        },
        changeIpRanges: function(e, addRange) {
            var index = this.$('.range-row').index($(e.currentTarget).parents('.range-row'));
            var ipRanges = _.cloneDeep(this.network.get('ip_ranges'));
            if (addRange) {
                ipRanges.splice(index + 1, 0, ['','']);
            } else {
                ipRanges.splice(index, 1);
            }
            this.network.set({ip_ranges: ipRanges}, {silent: true});
            this.render();
            this.tab.networkConfiguration.isValid();
        },
        addIPRange: function(e) {
            this.changeIpRanges(e, true);
        },
        deleteIPRange: function(e) {
            this.changeIpRanges(e, false);
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.network.on('change', this.tab.updateNetworkConfiguration, this.tab);
        },
        renderIpRanges: function() {
            this.$('.ip-ranges-rows').empty();
            this.ipRangeBindings = {};
            _.each(this.network.get('ip_ranges'), function(range, rangeIndex) {
                this.$('.ip-ranges-rows').append(this.rangeTemplate({
                    index: rangeIndex,
                    rangeControls: true,
                    removalPossible: this.network.get('ip_ranges').length > 1,
                    locked: this.tab.isLocked()
                }));
                _.each(range, function(ip, index) {
                    this.ipRangeBindings['.' + this.network.get('name') + ' .ip-ranges-rows input[name=range' + index + '][data-range=' + rangeIndex + ']'] = {
                        observe: 'ip_ranges',
                        onGet: function(value) {
                            return value[rangeIndex][index];
                        },
                        getVal: _.bind(function($el) {
                            var ipRanges = _.cloneDeep(this.network.get('ip_ranges'));
                            ipRanges[$el.data('range')][index] = $el.val();
                            return ipRanges;
                        }, this)
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
            this.renderIpRanges();
            this.stickitNetwork();
            return this;
        }
    });

    NetworkingParameters = Backbone.View.extend({
        template: _.template(networkingParametersTemplate),
        rangeTemplate: _.template(rangeTemplate),
        initialize: function(options) {
            _.defaults(this, options);
            this.parameters.on('change:amount', function(parameters, amount) {
                if (this.parameters.get('net_manager') == 'VlanManager') {
                    this.tab.fixedAmount = amount;
                }
            }, this);
            this.parameters.on('change', this.tab.updateNetworkConfiguration, this.tab);
        },
        stickitParameters: function() {        
            var bindings = {
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
                    onSet: function(value) {
                        return Number(value) || '';
                    }
                },
                'input[name=vlan_end]': {
                    observe: ['vlan_start', 'amount'],
                    onGet: function(value) {
                        if (!value[0] || !value[1]) {
                            return '';
                        }
                        var vlanEnd = value[0] + value[1] - 1;
                        return vlanEnd > 4094 ? 4094 : vlanEnd;
                    }
                },
                'input[name=fixed_networks_vlan_start]': 'fixed_networks_vlan_start',
                'input[name=fixed_networks_cidr]': 'fixed_networks_cidr',
                'input[name=base_mac]': 'base_mac',
                'input[name=internal_cidr]': 'internal_cidr',
                'input[name=internal_gateway]': 'internal_gateway'
            };
            var idRangeAttr = this.parameters.get('segmentation_type') == 'gre' ? 'gre_id_range' : 'vlan_range';
            _.each(this.parameters.get(idRangeAttr), function(id, idIndex) {
                bindings['input[name=id' + idIndex + ']'] = {
                    observe: idRangeAttr,
                    onGet: function(value) {return value[idIndex];},
                    getVal: _.bind(function($el) {
                        var range = _.clone(this.parameters.get(idRangeAttr));
                        range[this.$('.neutronId').index($el)] = Number($el.val()) || '';
                        return range;
                    }, this)
                };
            }, this);
            this.composeRangeBindings('floating_ranges', bindings);
            this.composeRangeBindings('dns_nameservers', bindings);
            this.stickit(this.configuration, bindings);
        },
        composeRangeBindings: function(attr, bindings) {
            var range = this.parameters.get(attr);
            _.each(range, function(el, elIndex) {
                bindings['.' + attr + '-row input[name=range' + elIndex + ']'] = {
                    observe: attr,
                    onGet: function(value) {return value[elIndex];},
                    getVal: _.bind(function($el) {
                        var newRange = _.clone(this.parameters.get(attr));
                        newRange[this.$('.' + attr + '-row .range').index($el)] = $el.val();
                        return newRange;
                    }, this)
                };
            }, this);
        },
        render: function() {
            this.$el.html(this.template({
                provider: this.tab.provider,
                netManager: this.parameters.get('net_manager'),
                segmentation: this.parameters.get('segmentation_type'),
                locked: this.tab.isLocked()
            })).i18n();
            this.$('.floating_ranges-row').html(this.rangeTemplate({locked: this.tab.isLocked()}));
            this.$('.dns_nameservers-row').html(this.rangeTemplate({locked: this.tab.isLocked()}));
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
