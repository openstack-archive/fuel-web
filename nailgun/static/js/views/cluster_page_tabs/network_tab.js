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
    'text!templates/cluster/nova_nameservers.html',
    'text!templates/cluster/neutron_parameters.html',
    'text!templates/cluster/verify_network_control.html'
],
function(utils, models, commonViews, dialogViews, networkTabTemplate, networkTemplate, novaNetworkConfigurationTemplate, neutronParametersTemplate, networkTabVerificationControlTemplate) {
    'use strict';
    var NetworkTab, Network, NeutronConfiguration, NovaNetworkConfiguration, NetworkTabVerificationControl;

    NetworkTab = commonViews.Tab.extend({
        template: _.template(networkTabTemplate),
        updateInterval: 3000,
        hasChanges: false,
        events: {
            'change .net-manager input': 'changeManager',
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
            var task = !!this.model.task('deploy', 'running') || !!this.model.task('verify_networks', 'running');
            return this.model.get('status') != 'new' || task;
        },
        isVerificationLocked: function() {
            return !!this.model.task('deploy', 'running') || !!this.model.task('verify_networks', 'running');
        },
        checkForChanges: function() {
            this.hasChanges = !_.isEqual(this.model.get('networkConfiguration').toJSON(), this.networkConfiguration.toJSON());
            this.defaultButtonsState(!!this.networkConfiguration.validationError);
        },
        changeManager: function(e) {
            this.$('.net-manager input').attr('checked', function(el, oldAttr) {return !oldAttr;});
            this.networkConfiguration.set({net_manager: this.$(e.currentTarget).val()});
            this.networkConfiguration.get('networks').findWhere({name: 'fixed'}).set({amount: this.$(e.currentTarget).val() == 'VlanManager' ? this.fixedAmount : 1});
            this.renderNetworks();
            this.updateNetworkConfiguration();
        },
        updateFloatingVlanFromPublic: function() {
            if (this.model.get('net_provider') == 'nova_network') {
                var networks = this.networkConfiguration.get('networks');
                networks.findWhere({name: 'floating'}).set({vlan_start: networks.findWhere({name: 'public'}).get('vlan_start')});
            }
        },
        startVerification: function() {
            var task = new models.Task();
            var options = {
                method: 'PUT',
                url: _.result(this.model, 'url') + '/network_configuration/' + this.model.get('net_provider') + '/verify',
                data: JSON.stringify(this.networkConfiguration)
            };
            task.save({}, options)
                .fail(_.bind(function() {
                    utils.showErrorDialog({title: 'Network verification'});
                    this.$('.verify-networks-btn').prop('disabled', false);
                }, this))
                .always(_.bind(function() {
                    this.model.get('tasks').fetch({data: {cluster_id: this.model.id}}).done(_.bind(this.scheduleUpdate, this));
                }, this));
        },
        verifyNetworks: function() {
            if (!this.networkConfiguration.validationError) {
                this.$('.verify-networks-btn').prop('disabled', true);
                this.filterEmptyIpRanges();
                this.page.removeFinishedTasks().always(_.bind(this.startVerification, this));
            }
        },
        revertChanges: function() {
            this.setInitialData();
            this.page.removeFinishedTasks().always(_.bind(this.render, this));
        },
        filterEmptyIpRanges: function() {
            this.networkConfiguration.get('networks').each(function(network) {
                network.set({ip_ranges: _.filter(network.get('ip_ranges'), function(range) {return _.compact(range).length;})});
            }, this);
        },
        applyChanges: function() {
            var deferred;
            if (!this.networkConfiguration.validationError) {
                this.disableControls();
                this.filterEmptyIpRanges();
                deferred = Backbone.sync('update', this.networkConfiguration, {url: _.result(this.model, 'url') + '/network_configuration/' + this.model.get('net_provider')})
                    .done(_.bind(function(task) {
                        if (task && task.status == 'error') {
                            this.page.removeFinishedTasks().always(_.bind(function() {
                                this.defaultButtonsState(false);
                                this.model.fetch();
                                this.model.fetchRelated('tasks');
                            }, this));
                        } else {
                            this.hasChanges = false;
                            this.model.set({networkConfiguration: new models.NetworkConfiguration(this.networkConfiguration.toJSON(), {parse: true})});
                            this.model.fetch();
                            this.model.fetchRelated('tasks');
                        }
                    }, this))
                    .fail(_.bind(function() {
                        utils.showErrorDialog({title: 'Networks'});
                        this.defaultButtonsState(false);
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
            if (task.get('name') == 'verify_networks' || task.get('name') == 'deploy' || task.get('name') == 'check_networks') {
                return task.on('change:status', this.render, this);
            }
            return null;
        },
        onNewTask: function(task) {
            return this.bindTaskEvents(task) && this.render();
        },
        setInitialData: function() {
            this.hasChanges = false;
            this.networkConfiguration = new models.NetworkConfiguration(this.model.get('networkConfiguration').toJSON(), {parse: true});
            this.fixedAmount = this.model.get('net_provider') == 'nova_network' ? this.networkConfiguration.get('networks').findWhere({name: 'fixed'}).get('amount') || 1 : 1;
            this.networkConfiguration.get('networks').each(function(network) {
                if (!_.contains(['fixed', 'private'], network.get('name'))) {
                    network.set({network_size: utils.calculateNetworkSize(network.get('cidr'))});
                }
            });
        },
        updateNetworkConfiguration: function() {
            this.networkConfiguration.validate(this.networkConfiguration.attributes);
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
            this.networkConfiguration.on('invalid', function(model, errors) {
                _.each(errors.dns_nameservers, _.bind(function(error, field) {
                    this.$('.nova-nameservers input[name=' + field + ']').addClass('error').parents('.network-attribute').find('.error .help-inline').text(error);
                }, this));
                _.each(errors.neutron_parameters, _.bind(function(error, field) {
                    if (!_.contains(['id_range', 'floating'], field)) {
                        this.$('.neutron-parameters input[name=' + field + ']').addClass('error').parents('.network-attribute').find('.error .help-inline').text(error);
                    } else if (field == 'id_range') {
                        this.$('.neutron-parameters input[name=id_start], .neutron-parameters input[name=id_end]').addClass('error').parents('.network-attribute').find('.error .help-inline').text(error);
                    } else if (field == 'floating') {
                        this.$('.neutron-parameters input[name=floating_start], .neutron-parameters input[name=floating_end]').addClass('error').parents('.network-attribute').find('.error .help-inline').text(error);
                    }
                }, this));
                _.each(errors.networks, _.bind(function(networkErrors, network) {
                    _.each(networkErrors, _.bind(function(error, field) {
                        if (field != 'ip_ranges') {
                            this.$('.' + network + ' input[name=' + field + ']').addClass('error').parents('.network-attribute').find('.error .help-inline').text(error);
                        } else {
                            _.each(networkErrors.ip_ranges, _.bind(function(range) {
                                var row = this.$('.' + network + ' .ip-range-row:eq(' + range.index + ')');
                                row.find('input:first').toggleClass('error', !!range.start);
                                row.find('input:last').toggleClass('error', !!range.end);
                                row.find('.help-inline').text(range.start || range.end);
                            }, this));
                        }
                    }, this));
                }, this));
            }, this);
        },
        showVerificationErrors: function() {
            var task = this.model.task('verify_networks', 'error') || this.model.task('check_networks', 'error');
            if (task && task.get('result').length) {
                _.each(task.get('result'), function(failedNetwork) {
                    _.each(failedNetwork.errors, function(field) {
                        this.$('div[data-network-id=' + failedNetwork.id + ']').find('.' + field).children().addClass('error');
                    }, this);
                   _.each(failedNetwork.range_errors, function (idx) {
                        this.$('div[data-network-id=' + failedNetwork.id + ']').find('.ip-range-row:eq('+idx+') input').addClass('error');
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
        renderNovaNetworkConfiguration: function() {
            if (this.model.get('net_provider') == 'nova_network' && this.networkConfiguration.get('dns_nameservers')) {
                var novaNetworkConfigurationView = new NovaNetworkConfiguration({
                    novaNetworkConfiguration: this.networkConfiguration.get('dns_nameservers'),
                    tab: this
                });
                this.registerSubView(novaNetworkConfigurationView);
                this.$('.nova-nameservers').html(novaNetworkConfigurationView.render().el);
            }
        },
        renderNeutronConfiguration: function() {
            if (this.model.get('net_provider') == 'neutron' && this.networkConfiguration.get('neutron_parameters')) {
                var neutronConfigurationView = new NeutronConfiguration({
                    neutronParameters: this.networkConfiguration.get('neutron_parameters'),
                    tab: this
                });
                this.registerSubView(neutronConfigurationView);
                this.$('.neutron-parameters').html(neutronConfigurationView.render().el);
            }
        },
        render: function() {
            this.$el.html(this.template({
                loading: this.loading,
                net_provider: this.model.get('net_provider'),
                net_manager: this.networkConfiguration.get('net_manager'),
                hasChanges: this.hasChanges,
                locked: this.isLocked(),
                verificationLocked: this.isVerificationLocked(),
                segment_type: this.model.get("net_segment_type")
            })).i18n();
            this.renderNetworks();
            this.renderNovaNetworkConfiguration();
            this.renderNeutronConfiguration();
            this.renderVerificationControl();
            return this;
        }
    });

    Network = Backbone.View.extend({
        template: _.template(networkTemplate),
        events: {
            'keyup input[type=text]': 'changeNetwork',
            'change select': 'changeNetwork',
            'change .use-vlan-tagging': 'changeNetwork',
            'click .ip-ranges-add:not([disabled])': 'addIPRange',
            'click .ip-ranges-delete:not([disabled])': 'deleteIPRange'
        },
        setupVlanEnd: function() {
            var vlanEnd = '';
            var errors = this.network.validationError;
            if (!errors || !(errors.amount || errors.vlan_start)) {
                vlanEnd = (this.network.get('vlan_start') + this.network.get('amount') - 1);
                vlanEnd = vlanEnd > 4094 ? 4094 : vlanEnd;
            }
            this.$('input[name=fixed-vlan_range-end]').val(vlanEnd);
        },
        changeNetwork: function(e, ipRangeModification) {
            var target = $(e.currentTarget);
            this.$('input[type=text]').removeClass('error').parents('.network-attribute').find('.help-inline').text('');
            if (!_.isUndefined(ipRangeModification)) { // ip ranges row management
                var row = this.$(e.currentTarget).parents('.ip-range-row');
                if (ipRangeModification) {
                    var newRow = row.clone();
                    newRow.find('input').val('');
                    row.after(newRow);
                    row.parent().find('.ip-ranges-delete').parent().removeClass('hide');
                } else {
                    row.parent().find('.ip-ranges-delete').parent().toggleClass('hide', row.siblings('.ip-range-row').length == 1);
                    row.remove();
                }
            }
            if (target.hasClass('use-vlan-tagging')) { // toggle VLAN ID input field on checkbox
                target.parents('.range-row').find('.parameter-control:last').toggle(target.is(':checked'));
            }
            if (this.network.get('name') == 'public' && this.tab.model.get('net_provider') == 'nova_network') {
                this.tab.$('input[name=floating-vlan_start]').val(this.$('input[name=public-vlan_start]').val());
                if (target.hasClass('use-vlan-tagging')) {
                    this.tab.$('div.floating').find('.use-vlan-tagging').prop('checked', target.is(':checked'));
                    this.tab.$('div.floating').find('.vlan_start').toggle(target.is(':checked'));
                }
            }
            if (target.attr('name') == 'fixed-amount') {// storing fixedAmount
                this.tab.fixedAmount = parseInt(target.val(), 10) || this.tab.fixedAmount;
            }
            var fixedNetworkOnVlanManager = this.tab.networkConfiguration.get('net_manager') == 'VlanManager' && this.network.get('name') == 'fixed';
            var ip_ranges = [];
            this.$('.ip-range-row').each(function(i, row) {
                ip_ranges.push([$(row).find('input:first').val(), $(row).find('input:last').val()]);
            });
            this.network.set({
                ip_ranges: ip_ranges,
                cidr: $.trim(this.$('.cidr input').val()),
                vlan_start: fixedNetworkOnVlanManager || this.$('.use-vlan-tagging:checked').length ? Number(this.$('.vlan_start input').val()) : null,
                netmask: $.trim(this.$('.netmask input').val()),
                gateway: $.trim(this.$('.gateway input').val()) || null,
                amount: fixedNetworkOnVlanManager ? Number(this.$('input[name=fixed-amount]').val()) : 1,
                network_size: fixedNetworkOnVlanManager ? Number(this.$('.network_size select').val()) : utils.calculateNetworkSize(this.$('.cidr input').val())
            });
            if (this.network.get('name') == 'fixed' && target.hasClass('range')) {
                this.setupVlanEnd();
            }
            this.tab.updateFloatingVlanFromPublic();
            this.tab.updateNetworkConfiguration();
        },
        addIPRange: function(e) {
            this.changeNetwork(e, true);
        },
        deleteIPRange: function(e) {
            this.changeNetwork(e, false);
        },
        initialize: function(options) {
            _.defaults(this, options);
        },
        render: function() {
            this.$el.html(this.template({
                network: this.network,
                net_provider: this.tab.model.get('net_provider'),
                net_manager: this.tab.networkConfiguration.get('net_manager'),
                locked: this.tab.isLocked()
            })).i18n();
            return this;
        }
    });

    NovaNetworkConfiguration = Backbone.View.extend({
        template: _.template(novaNetworkConfigurationTemplate),
        events: {
            'keyup input[type=text]': 'onChange'
        },
        onChange: function() {
            this.$('input[type=text]').removeClass('error').parents('.network-attribute').find('.help-inline').text('');
            this.novaNetworkConfiguration.set({nameservers: [$.trim(this.$('input[name=nameserver-0]').val()), $.trim(this.$('input[name=nameserver-1]').val())]});
            this.tab.updateNetworkConfiguration();
        },
        initialize: function(options) {
            _.defaults(this, options);
        },
        render: function() {
            this.$el.html(this.template({
                nameservers: this.novaNetworkConfiguration.get('nameservers'),
                locked: this.tab.isLocked()
            })).i18n();
            return this;
        }
    });

    NeutronConfiguration = Backbone.View.extend({
        template: _.template(neutronParametersTemplate),
        events: {
            'keyup input[type=text]': 'changeConfiguration'
        },
        changeConfiguration: function(e) {
            this.$('input[type=text]').removeClass('error').parents('.network-attribute').find('.help-inline').text('');
            var l2 = _.cloneDeep(this.neutronParameters.get('L2'));
            l2.base_mac = $.trim(this.$('input[name=base_mac]').val());
            var idRange = [Number(this.$('input[name=id_start]').val()), Number(this.$('input[name=id_end]').val())];
            if (this.neutronParameters.get('segmentation_type') == 'gre') {
                l2.tunnel_id_ranges = idRange;
            } else {
                l2.phys_nets.physnet2.vlan_range = idRange;
            }
            var predefined_networks = _.cloneDeep(this.neutronParameters.get('predefined_networks'));
            predefined_networks.net04_ext.L3.floating = [$.trim(this.$('input[name=floating_start]').val()), $.trim(this.$('input[name=floating_end]').val())];
            predefined_networks.net04_ext.L3.cidr = $.trim(this.$('input[name=cidr-ext]').val());
            predefined_networks.net04.L3.cidr = $.trim(this.$('input[name=cidr-int]').val());
            predefined_networks.net04.L3.gateway = $.trim(this.$('input[name=gateway]').val());
            predefined_networks.net04.L3.nameservers = [$.trim(this.$('input[name=nameserver-0]').val()), $.trim(this.$('input[name=nameserver-1]').val())];
            this.neutronParameters.set({L2: l2, predefined_networks: predefined_networks});
            this.tab.updateNetworkConfiguration();
        },
        initialize: function(options) {
            _.defaults(this, options);
        },
        render: function() {
            this.$el.html(this.template({
                neutronParameters: this.neutronParameters,
                locked: this.tab.isLocked()
            })).i18n();
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
