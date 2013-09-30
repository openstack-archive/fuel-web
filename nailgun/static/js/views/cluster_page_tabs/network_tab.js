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
    'text!templates/cluster/neutron_parameters.html',
    'text!templates/cluster/verify_network_control.html'
],
function(utils, models, commonViews, dialogViews, networkTabTemplate, networkTemplate, neutronParametersTemplate, networkTabVerificationControlTemplate) {
    'use strict';
    var NetworkTab, Network, NeutronConfiguration, NetworkTabVerificationControl;

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
        defaultButtonsState: function(validationErrors) {
            this.$('.btn.verify-networks-btn').attr('disabled', validationErrors);
            this.$('.btn.btn-revert-changes').attr('disabled', !this.hasChanges);
            this.$('.btn.apply-btn').attr('disabled', !this.hasChanges || validationErrors);
        },
        disableControls: function() {
            this.$('.btn, input, select').attr('disabled', true);
        },
        isLocked: function() {
            var task = !!this.model.task('deploy', 'running') || !!this.model.task('verify_networks', 'running');
            var allowedClusterStatus = this.model.get('status') == 'new' || this.model.get('status') == 'error';
            return !allowedClusterStatus || task;
        },
        isVerificationLocked: function() {
            return !!this.model.task('deploy', 'running') || !!this.model.task('verify_networks', 'running');
        },
        checkForChanges: function() {
            this.hasChanges = !_.isEqual(this.model.get('networkConfiguration').toJSON(), this.networkConfiguration.toJSON());
            this.defaultButtonsState(_.some(this.networkConfiguration.get('networks').models, 'validationError') || !!(this.networkConfiguration.get('neutron_parameters') && this.networkConfiguration.get('neutron_parameters').validationError));
        },
        changeManager: function(e) {
            this.$('.net-manager input').attr('checked', function(el, oldAttr) {return !oldAttr;});
            this.networkConfiguration.set({net_manager: this.$(e.currentTarget).val()});
            this.networkConfiguration.get('networks').findWhere({name: 'fixed'}).set({amount: this.$(e.currentTarget).val() == 'VlanManager' ? this.fixedAmount : 1});
            this.renderNetworks();
            this.checkForChanges();
            this.networkConfiguration.get('networks').invoke('set', {}, { // trigger validation check
                validate: true,
                net_manager: this.networkConfiguration.get('net_manager'),
                net_provider: this.model.get('net_provider')
            });
            this.page.removeFinishedTasks();
        },
        updateFloatingVlanFromPublic: function() {
            if (this.model.get('net_provider') == 'nova_network') {
                var networks = this.networkConfiguration.get('networks');
                networks.findWhere({name: 'floating'}).set({vlan_start: networks.findWhere({name: 'public'}).get('vlan_start')});
            }
        },
        updateExternalCidrFromPublic: function() {
            if (this.model.get('net_provider') == 'neutron') {
                var cidr = this.networkConfiguration.get('networks').findWhere({name: 'public'}).get('cidr');
                this.networkConfiguration.get('neutron_parameters').get('predefined_networks').net04_ext.L3.cidr = cidr;
                this.$('input[name=cidr-ext]').val(cidr).trigger('change');
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
            if (!_.some(this.networkConfiguration.get('networks').models, 'validationError') && (!this.networkConfiguration.get('neutron_parameters') || !this.networkConfiguration.get('neutron_parameters').validationError)) {
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
                network.set({ip_ranges: _.filter(network.get('ip_ranges'), function(range) {return !_.isEqual(range, ['', '']);})});
            }, this);
        },
        applyChanges: function() {
            var deferred;
            if (!_.some(this.networkConfiguration.get('networks').models, 'validationError') && (!this.networkConfiguration.get('neutron_parameters') || !this.networkConfiguration.get('neutron_parameters').validationError)) {
                this.disableControls();
                this.filterEmptyIpRanges();
                deferred = Backbone.sync('update', this.networkConfiguration, {url: _.result(this.model, 'url') + '/network_configuration/' + this.model.get('net_provider')})
                    .always(_.bind(function() {
                        this.model.fetch();
                        this.model.fetchRelated('tasks');
                    }, this))
                    .done(_.bind(function(task) {
                        if (task && task.status == 'error') {
                            this.defaultButtonsState(false);
                        } else {
                            this.hasChanges = false;
                            this.model.set({networkConfiguration: new models.NetworkConfiguration(this.networkConfiguration.toJSON(), {parse: true})});
                        }
                    }, this))
                    .fail(_.bind(function() {
                        this.defaultButtonsState(false);
                        utils.showErrorDialog({title: 'Networks'});
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
            _.each(this.networkConfiguration.get('networks').reject({name: 'fixed'}), function(network) {
                network.set({network_size: utils.calculateNetworkSize(network.get('cidr'))});
            });
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
                verificationLocked: this.isVerificationLocked()
            }));
            this.renderNetworks();
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
            'click .range-name': 'setIPRangeFocus',
            'click .ip-ranges-add:not(:disabled)': 'addIPRange',
            'click .ip-ranges-delete:not(:disabled)': 'deleteIPRange'
        },
        setupVlanEnd: function() {
            var vlanEnd = '';
            // calculate vlan end if there are no amount or vlan start validation errors
            var errors = this.network.validationError;
            if (!errors || !(errors.amount || errors.vlan_start)) {
                vlanEnd = (this.network.get('vlan_start') + this.network.get('amount') - 1);
                vlanEnd = vlanEnd > 4094 ? 4094 : vlanEnd;
            }
            this.$('input[name=fixed-vlan_range-end]').val(vlanEnd);
        },
        changeNetwork: function(e) {
            // FIXME(vk): very complex and confusing logic, needs to be rewritten
            var target = $(e.currentTarget);
            this.$('input[type=text]').removeClass('error');
            this.$('.help-inline').text('');

            if (target.hasClass('use-vlan-tagging')) {
                // toggle VLAN ID input field on checkbox
                target.parents('.range-row').find('.parameter-control:last').toggle(target.is(':checked'));
            }
            if (this.network.get('name') == 'public' && this.tab.model.get('net_provider') == 'nova_network') {
                this.tab.$('input[name=floating-vlan_start]').val(this.$('input[name=public-vlan_start]').val());
                if (target.hasClass('use-vlan-tagging')) {
                    this.tab.$('div.floating').find('.use-vlan-tagging').prop('checked', target.is(':checked'));
                    this.tab.$('div.floating').find('.vlan_start').toggle(target.is(':checked'));
                }
            }
            if (target.attr('name') == 'fixed-amount') {
                // storing fixedAmount
                this.tab.fixedAmount = parseInt(target.val(), 10) || this.tab.fixedAmount;
            }
            this.updateNetworkFromForm();
            if (this.network.get('name') == 'fixed' && target.hasClass('range')) {
                this.setupVlanEnd();
            }
            this.tab.updateFloatingVlanFromPublic();
            this.tab.updateExternalCidrFromPublic();
            this.tab.checkForChanges();
            this.tab.page.removeFinishedTasks();
        },
        updateNetworkFromForm: function() {
            var ip_ranges = [];
            this.$('.ip-range-row').each(function(index, rangeRow) {
                var range = [$(rangeRow).find('input:first').val(), $(rangeRow).find('input:last').val()];
                ip_ranges.push(range);
            });
            var fixedNetworkOnVlanManager = this.tab.networkConfiguration.get('net_manager') == 'VlanManager' && this.network.get('name') == 'fixed';
            this.network.set({
                ip_ranges: ip_ranges,
                cidr: this.$('.cidr input').val(),
                vlan_start: fixedNetworkOnVlanManager || this.$('.use-vlan-tagging:checked').length ? Number(this.$('.vlan_start input').val()) : null,
                netmask: this.$('.netmask input').val(),
                gateway: this.$('.gateway input').val(),
                amount: fixedNetworkOnVlanManager ? Number(this.$('input[name=fixed-amount]').val()) : 1,
                network_size: fixedNetworkOnVlanManager ? Number(this.$('.network_size select').val()) : utils.calculateNetworkSize(this.$('.cidr input').val())
            }, {
                validate: true,
                net_provider: this.tab.model.get('net_provider'),
                net_manager: this.tab.networkConfiguration.get('net_manager')
            });
        },
        setIPRangeFocus: function(e) {
            this.$(e.currentTarget).next().find('input:first').focus();
        },
        editIPRange: function(e, add) {
            var row = this.$(e.currentTarget).parents('.ip-range-row');
            if (add) {
                var newRow = row.clone();
                newRow.find('input').removeClass('error').val('');
                newRow.find('.help-inline').text('');
                row.after(newRow);
                row.parent().find('.ip-ranges-delete').parent().removeClass('hide');
            } else {
                row.parent().find('.ip-ranges-delete').parent().toggleClass('hide', row.siblings('.ip-range-row').length == 1);
                row.remove();
            }
            this.updateNetworkFromForm();
            this.tab.checkForChanges();
            this.tab.page.removeFinishedTasks();
        },
        addIPRange: function(e) {
            this.editIPRange(e, true);
        },
        deleteIPRange: function(e) {
            this.editIPRange(e, false);
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.network.on('invalid', function(model, errors) {
                this.$('input.error').removeClass('error').find('.help-inline').text('');
                _.each(_.without(_.keys(errors), 'ip_ranges'), _.bind(function(field) {
                    this.$('.' + field).children().addClass('error');
                    this.$('.' + field).parents('.network-attribute').find('.error .help-inline').text(errors[field]);
                }, this));
                if (errors.ip_ranges) {
                    _.each(errors.ip_ranges, _.bind(function(range) {
                        var row = this.$('.ip-range-row:eq(' + range.index + ')');
                        row.find('input:first').toggleClass('error', !!range.start);
                        row.find('input:last').toggleClass('error', !!range.end);
                        row.find('.help-inline').text(range.start || range.end);
                    }, this));
                }
            }, this);
        },
        render: function() {
            this.$el.html(this.template({
                network: this.network,
                net_provider: this.tab.model.get('net_provider'),
                net_manager: this.tab.networkConfiguration.get('net_manager'),
                locked: this.tab.isLocked()
            }));
            return this;
        }
    });

    NeutronConfiguration = Backbone.View.extend({
        template: _.template(neutronParametersTemplate),
        events: {
            'keyup input[type=text]': 'changeConfiguration'
        },
        changeConfiguration: function(e) {
            this.$('input[type=text]').removeClass('error');
            this.$('.help-inline').text('');

            var l2 = _.cloneDeep(this.neutronParameters.get('L2'));
            l2.base_mac = this.$('input[name=base_mac]').val();
            var idRange = [Number(this.$('input[name=id_start]').val()), Number(this.$('input[name=id_end]').val())];
            if (this.neutronParameters.get('segmentation_type') == 'gre') {
                l2.tunnel_id_ranges = idRange;
            } else {
                l2.phys_nets.physnet2.vlan_range = idRange;
            }

            var predefined_networks = _.cloneDeep(this.neutronParameters.get('predefined_networks'));
            predefined_networks.net04_ext.L3.floating = [this.$('input[name=floating_start]').val(), this.$('input[name=floating_end]').val()];
            predefined_networks.net04_ext.L3.cidr = this.$('input[name=cidr-ext]').val();
            predefined_networks.net04.L3.cidr = this.$('input[name=cidr-int]').val();
            predefined_networks.net04.L3.nameservers = [this.$('input[name=nameserver-0]').val(), this.$('input[name=nameserver-1]').val()];

            this.neutronParameters.set({L2: l2, predefined_networks: predefined_networks}, {validate: true});
            this.tab.checkForChanges();
            this.tab.page.removeFinishedTasks();
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.neutronParameters.on('invalid', function(model, errors) {
                this.$('input.error').removeClass('error').find('.help-inline').text('');
                _.each(_.without(_.keys(errors), 'id_range', 'floating'), _.bind(function(field) {
                    this.$('input[name=' + field + ']')
                        .addClass('error')
                        .parents('.network-attribute').find('.error .help-inline').text(errors[field]);
                }, this));
                if (errors.id_range) {
                    this.$('input[name=id_start], input[name=id_end]')
                        .addClass('error')
                        .parents('.network-attribute').find('.error .help-inline').text(errors.id_range);
                }
                if (errors.floating) {
                    this.$('input[name=floating_start], input[name=floating_end]')
                        .addClass('error')
                        .parents('.network-attribute').find('.error .help-inline').text(errors.floating);
                }
            }, this);
        },
        render: function() {
            this.$el.html(this.template({
                neutronParameters: this.neutronParameters,
                externalCidr: this.tab.networkConfiguration.get('networks').findWhere({name: 'public'}).get('cidr'),
                locked: this.tab.isLocked()
            }));
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
            }));
            return this;
        }
    });

    return NetworkTab;
});
