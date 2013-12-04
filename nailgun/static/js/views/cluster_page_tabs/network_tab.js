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
    'text!templates/cluster/ip_ranges.html',
    'text!templates/cluster/nova_nameservers.html',
    'text!templates/cluster/neutron_parameters.html',
    'text!templates/cluster/verify_network_control.html'
],
function(utils, models, commonViews, dialogViews, networkTabTemplate, networkTemplate, ipRangesTemplate, novaNetworkConfigurationTemplate, neutronParametersTemplate, networkTabVerificationControlTemplate) {
    'use strict';
    var NetworkTab, Network, NeutronConfiguration, NovaNetworkConfiguration, NetworkTabVerificationControl;

    NetworkTab = commonViews.Tab.extend({
        template: _.template(networkTabTemplate),
        updateInterval: 3000,
        hasChanges: false,
        events: {
            'click .verify-networks-btn:not([disabled])': 'verifyNetworks',
            'click .btn-revert-changes:not([disabled])': 'revertChanges',
            'click .apply-btn:not([disabled])': 'applyChanges'
        },
        bindings: {
            'input[name=net-manager]': {
                observe: 'net_manager',
                onSet: 'changeManager'
            }
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
        changeManager: function(value) {
            this.networkConfiguration.get('networks').findWhere({name: 'fixed'}).set({amount: value == 'VlanManager' ? this.fixedAmount : 1});
            this.renderNetworks();
            this.updateNetworkConfiguration();
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
            this.networkConfiguration.get('networks').each(function(network) {
                if (!_.contains(['fixed', 'private'], network.get('name'))) {
                    network.set({network_size: utils.calculateNetworkSize(network.get('cidr'))});
                }
            });
            this.fixedAmount = this.model.get('net_provider') == 'nova_network' ? this.networkConfiguration.get('networks').findWhere({name: 'fixed'}).get('amount') : 1;
            this.networkConfiguration.on('invalid', function(model, errors) {
                _.each(errors.dns_nameservers, _.bind(function(error, field) {
                    this.$('.nova-nameservers input[name=' + field + ']').addClass('error').parents('.network-attribute').find('.error .help-inline').text(error);
                }, this));
                _.each(errors.neutron_parameters, _.bind(function(error, field) {
                    this.$('.neutron-parameters input[name=' + field + ']').addClass('error').parents('.network-attribute').find('.error .help-inline').text(error);
                }, this));
                _.each(errors.networks, _.bind(function(networkErrors, network) {
                    _.each(networkErrors, _.bind(function(error, field) {
                        if (field != 'ip_ranges') {
                            this.$('input[name=' + network + '-' + field + ']').addClass('error').parents('.network-attribute').find('.error .help-inline').text(error);
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
                    configuration: this.networkConfiguration.get('dns_nameservers'),
                    tab: this
                });
                this.registerSubView(novaNetworkConfigurationView);
                this.$('.nova-nameservers').html(novaNetworkConfigurationView.render().el);
            }
        },
        renderNeutronConfiguration: function() {
            if (this.model.get('net_provider') == 'neutron' && this.networkConfiguration.get('neutron_parameters')) {
                var neutronConfigurationView = new NeutronConfiguration({
                    configuration: this.networkConfiguration.get('neutron_parameters'),
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
                hasChanges: this.hasChanges,
                locked: this.isLocked(),
                verificationLocked: this.isVerificationLocked(),
                segment_type: this.model.get("net_segment_type")
            })).i18n();
            this.stickit(this.networkConfiguration);
            this.renderNetworks();
            this.renderNovaNetworkConfiguration();
            this.renderNeutronConfiguration();
            this.renderVerificationControl();
            return this;
        }
    });

    Network = Backbone.View.extend({
        template: _.template(networkTemplate),
        ipRangesTemplate: _.template(ipRangesTemplate),
        events: {
            'click .ip-ranges-add:not([disabled])': 'addIPRange',
            'click .ip-ranges-delete:not([disabled])': 'deleteIPRange'
        },
        bindings: {
            '.cidr input': {
                observe: 'cidr'
            },
            '.netmask input': {
                observe: 'netmask'
            },
            '.gateway input': {
                observe: 'gateway'
            },
            '.amount input': {
                observe: 'amount',
                onGet: function(value) {
                    if (this.network.get('name') == 'fixed') {
                        this.tab.fixedAmount = value;
                    }
                    return value;
                }
            },
            '.network_size select': {
                observe: 'network_size',
                onGet: function(value) {
                    return this.tab.networkConfiguration.get('net_manager') == 'VlanManager' && this.network.get('name') == 'fixed' ? value : utils.calculateNetworkSize(this.network.get('cidr'));
                }
            },
            '.use-vlan-tagging': {
                observe: 'vlan_start',
                onGet: function(value) {
                    return !_.isNull(value);
                },
                getVal: function($el) {
                    $el.parents('.range-row').find('.parameter-control:last').toggle($el.is(':checked'));
                }
            },
            '.vlan_start input': {
                observe: 'vlan_start',
                visible: function(value) {
                    return !_.isNull(value);
                },
                onGet: function(value) {
                    return this.tab.networkConfiguration.get('net_manager') == 'VlanManager' && this.network.get('name') == 'fixed' || this.$('.use-vlan-tagging:checked').length ? value : null;
                },
                getVal: function($el) {
                    if (this.network.get('name') == 'public' && this.tab.model.get('net_provider') == 'nova_network') {
                        this.tab.networkConfiguration.get('networks').findWhere({name: 'floating'}).set({vlan_start: $el.val()});
                    }
                }
            },
            'input[name=fixed-vlan_range-end]': {
                observe: ['vlan_start', 'amount'],
                onGet: _.bind(function() {
                    var vlanEnd = this.network.get('vlan_start') + this.network.get('amount') - 1;
                    return vlanEnd > 4094 ? 4094 : vlanEnd;
                }, this)
            },
            '.network-attribute.ip_ranges': {
                observe: 'ip_ranges',
                update: function($el, ipRanges, network) {
                    $el.html(this.ipRangesTemplate({
                        hidden: !_.contains(network.getAttributes(this.tab.model.get('net_provider')), 'ip_ranges'),
                        locked: this.tab.isLocked(),
                        ipRanges: ipRanges
                    })).i18n();
                },
                onSet: 'composeIpRanges'
            }
        },
        composeIpRanges: function() {
            var ipRanges = [];
            this.$('.ip-range-row').each(function(i, row) {
                ipRanges.push([$(row).find('input:first').val(), $(row).find('input:last').val()]);
            });
            return ipRanges;
        },
        composeIpRangesRows: function(e, addRange) {
            var target = $(e.currentTarget);
            if (!_.isUndefined(addRange)) {
                var row = target.parents('.ip-range-row');
                if (addRange) {
                    var newRow = row.clone();
                    newRow.find('input').val('');
                    row.after(newRow);
                    row.parent().find('.ip-ranges-delete').parent().removeClass('hide');
                } else {
                    row.parent().find('.ip-ranges-delete').parent().toggleClass('hide', row.siblings('.ip-range-row').length == 1);
                    row.remove();
                }
            }
        },
        addIPRange: function(e) {
            this.composeIpRangesRows(e, addRange);
        },
        deleteIPRange: function(e) {
            this.composeIpRangesRows(e, addRange);
            this.network.set({ip_ranges: this.composeIpRanges()});
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.network.on('change', this.tab.updateNetworkConfiguration, this.tab);
        },
        render: function() {
            this.$el.html(this.template({
                network: this.network,
                net_provider: this.tab.model.get('net_provider'),
                net_manager: this.tab.networkConfiguration.get('net_manager'),
                locked: this.tab.isLocked()
            })).i18n();
            this.stickit(this.network);
            return this;
        }
    });

    NovaNetworkConfiguration = Backbone.View.extend({
        template: _.template(novaNetworkConfigurationTemplate),
        initialize: function(options) {
            _.defaults(this, options);
            this.configuration.on('change', this.tab.updateNetworkConfiguration, this.tab);
        },
        bindings: {
            'input[name=nameserver-0]': {
                observe: 'nameservers',
                stickitChange: 0,
                onGet: function(value) {
                    return value[0];
                },
                onSet: 'updateNameserver'
            },
            'input[name=nameserver-1]': {
                observe: 'nameservers',
                stickitChange: 1,
                onGet: function(value) {
                    return value[1];
                },
                onSet: 'updateNameserver'
            }
        },
        updateNameserver: function(value, options) {
            var nameservers = this.configuration.get('nameservers');
            nameservers[options.stickitChange] = value;
            return nameservers;
        },
        render: function() {
            this.$el.html(this.template({locked: this.tab.isLocked()})).i18n();
            this.stickit(this.configuration);
            return this;
        }
    });

    NeutronConfiguration = Backbone.View.extend({
        template: _.template(neutronParametersTemplate),
        initialize: function(options) {
            _.defaults(this, options);
            this.configuration.on('change', this.tab.updateNetworkConfiguration, this.tab);
        },
        bindings: {
            'input[name=base_mac]': {
                observe: 'L2.base_mac'
            },
            'input[name=id_start]': {
                observe: ['L2.tunnel_id_ranges', 'L2.phys_nets.physnet2.vlan_range'],
                stickitChange: 0,
                onGet: function(value) {
                    var range = _.filter(value, function(range) {return range.length;})[0];
                    return range[0];
                },
                onSet: 'updateIdRange'
            },
            'input[name=id_end]': {
                observe: ['L2.tunnel_id_ranges', 'L2.phys_nets.physnet2.vlan_range'],
                stickitChange: 1,
                onGet: function(value) {
                    var range = _.filter(value, function(range) {return range.length;})[0];
                    return range[1];
                },
                onSet: 'updateIdRange'
            },
            'input[name=floating_start]': {
                observe: 'predefined_networks.net04_ext.L3.floating',
                stickitChange: 0,
                onGet: function(value) {
                    return value[0];
                },
                onSet: 'updateFloatingRange'
            },
            'input[name=floating_end]': {
                observe: 'predefined_networks.net04_ext.L3.floating',
                stickitChange: 1,
                onGet: function(value) {
                    return value[1];
                },
                onSet: 'updateFloatingRange'
            },
            'input[name=cidr-int]': {
                observe: 'predefined_networks.net04.L3.cidr'
            },
            'input[name=gateway]': {
                observe: 'predefined_networks.net04.L3.gateway'
            },
            'input[name=nameserver-0]': {
                observe: 'predefined_networks.net04.L3.nameservers',
                stickitChange: 0,
                onGet: function(value) {
                    return value[0];
                },
                onSet: 'updateNameserver'
            },
            'input[name=nameserver-1]': {
                observe: 'predefined_networks.net04.L3.nameservers',
                stickitChange: 1,
                onGet: function(value) {
                    return value[1];
                },
                onSet: 'updateNameserver'
            }
        },
        updateAttribute: function(attr, value, options) {
            attr[options.stickitChange] = value;
            return attr;
        },
        updateIdRange: function(value, options) {
            var range = this.configuration.get('segmentation_type') == 'gre' ? this.configuration.get('L2').tunnel_id_ranges : this.configuration.get('L2').phys_nets.physnet2.vlan_range;
            this.updateAttribute(range, value, options);
        },
        updateFloatingRange: function(value, options) {
            this.updateAttribute(this.configuration.get('predefined_networks').net04_ext.L3.floating, value, options);
        },
        updateNameserver: function(value, options) {
            this.updateAttribute(this.configuration.get('predefined_networks').net04.L3.nameservers, value, options);
        },
        render: function() {
            this.$el.html(this.template({
                segmentation: this.configuration.get('segmentation_type'),
                locked: this.tab.isLocked()
            })).i18n();
            this.stickit(this.configuration);
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
