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
    'views/cluster_page_tabs/nodes_tab_screens/edit_node_screen',
    'text!templates/cluster/edit_node_interfaces.html',
    'text!templates/cluster/node_interface.html'
],
function(utils, models, EditNodeScreen, editNodeInterfacesScreenTemplate, nodeInterfaceTemplate) {
    'use strict';
    var EditNodeInterfacesScreen, NodeInterface;

    EditNodeInterfacesScreen = EditNodeScreen.extend({
        className: 'edit-node-networks-screen',
        constructorName: 'EditNodeInterfacesScreen',
        template: _.template(editNodeInterfacesScreenTemplate),
        events: {
            'click .btn-bond:not(:disabled)': 'bondInterfaces',
            'click .btn-unbond:not(:disabled)': 'unbondInterfaces',
            'click .btn-defaults': 'loadDefaults',
            'click .btn-revert-changes:not(:disabled)': 'revertChanges',
            'click .btn-apply:not(:disabled)': 'applyChanges',
            'click .btn-return:not(:disabled)': 'returnToNodeList'
        },
        initButtons: function() {
            this.constructor.__super__.initButtons.apply(this);
            this.bondInterfacesButton = new Backbone.Model({disabled: true});
            this.unbondInterfacesButton = new Backbone.Model({disabled: true});
        },
        updateButtonsState: function(state) {
            this.constructor.__super__.updateButtonsState.apply(this, arguments);
            this.bondInterfacesButton.set('disabled', state);
            this.unbondInterfacesButton.set('disabled', state);
        },
        setupButtonsBindings: function() {
            this.constructor.__super__.setupButtonsBindings.apply(this);
            var bindings = {attributes: [{name: 'disabled', observe: 'disabled'}]};
            this.stickit(this.bondInterfacesButton, {'.btn-bond': bindings});
            this.stickit(this.unbondInterfacesButton, {'.btn-unbond': bindings});
        },
        isLocked: function() {
            var nodesAvailableForChanges = this.nodes.filter(function(node) {
                return node.get('pending_addition') || node.get('status') == 'error';
            });
            return !nodesAvailableForChanges.length || this.constructor.__super__.isLocked.apply(this);
        },
        hasChanges: function() {
            function getInterfaceConfiguration(interfaces) {
                return _.map(interfaces.toJSON(), function(ifc) {
                    return _.pick(ifc, ['assigned_networks', 'type', 'mode', 'slaves']);
                });
            }
            var currentConfiguration = getInterfaceConfiguration(this.interfaces);
            return !this.nodes.reduce(function(result, node) {
                return result && _.isEqual(currentConfiguration, getInterfaceConfiguration(node.interfaces));
            }, true);
        },
        checkForChanges: function() {
            this.updateButtonsState(this.isLocked() || !this.hasChanges());
            this.loadDefaultsButton.set('disabled', this.isLocked());
            this.updateBondingControlsState();
        },
        validateInterfacesSpeedsForBonding: function(interfaces) {
            var slaveInterfaces = _.flatten(_.invoke(interfaces, 'getSlaveInterfaces'), true);
            var speeds = _.invoke(slaveInterfaces, 'get', 'current_speed');
            // warn if not all speeds are the same or there are interfaces with unknown speed
            return _.uniq(speeds).length > 1 || !_.compact(speeds).length;
        },
        bondingAvailable: function() {
            var iserDisabled =  this.model.get('settings').get('storage.iser.value') != true;
            var mellanoxSriovDisabled = this.model.get('settings').get('neutron_mellanox.plugin.value') != "ethernet";
            return !this.isLocked() && this.model.get('net_provider') == 'neutron' && iserDisabled && mellanoxSriovDisabled;
        },
        updateBondingControlsState: function() {
            var checkedInterfaces = this.interfaces.filter(function(ifc) {return ifc.get('checked') && !ifc.isBond();});
            var checkedBonds = this.interfaces.filter(function(ifc) {return ifc.get('checked') && ifc.isBond();});
            var creatingNewBond = checkedInterfaces.length >= 2 && !checkedBonds.length;
            var addingInterfacesToExistingBond = !!checkedInterfaces.length && checkedBonds.length == 1;
            var bondingPossible = creatingNewBond || addingInterfacesToExistingBond;
            var newBondWillHaveInvalidSpeeds = bondingPossible && this.validateInterfacesSpeedsForBonding(checkedBonds.concat(checkedInterfaces));
            var existingBondHasInvalidSpeeds = !!this.interfaces.find(function(ifc) {
                return ifc.isBond() && this.validateInterfacesSpeedsForBonding(ifc.getSlaveInterfaces());
            }, this);
            this.bondInterfacesButton.set('disabled', !bondingPossible);
            this.unbondInterfacesButton.set('disabled', checkedInterfaces.length || !checkedBonds.length);
            this.$('.bond-speed-warning').toggle(newBondWillHaveInvalidSpeeds || existingBondHasInvalidSpeeds);
        },
        bondInterfaces: function() {
            var interfaces = this.interfaces.filter(function(ifc) {return ifc.get('checked') && !ifc.isBond();});
            var bond = this.interfaces.find(function(ifc) {return ifc.get('checked') && ifc.isBond();});
            if (!bond) {
                // if no bond selected - create new one
                bond = new models.Interface({
                    type: 'bond',
                    name: this.interfaces.generateBondName(),
                    mode: models.Interface.prototype.bondingModes[0],
                    assigned_networks: new models.InterfaceNetworks(),
                    slaves: _.invoke(interfaces, 'pick', 'name')
                });
            } else {
                // adding interfaces to existing bond
                bond.set({slaves: bond.get('slaves').concat(_.invoke(interfaces, 'pick', 'name'))});
                // remove the bond to add it later and trigger re-rendering
                this.interfaces.remove(bond, {silent: true});
            }
            _.each(interfaces, function(ifc) {
                bond.get('assigned_networks').add(ifc.get('assigned_networks').models);
                ifc.get('assigned_networks').reset();
                ifc.set({checked: false});
            });
            this.interfaces.add(bond);
        },
        unbondInterfaces: function() {
            _.each(this.interfaces.where({checked: true}), function(bond) {
                // assign all networks from the bond to the first slave interface
                var ifc = this.interfaces.findWhere({name: bond.get('slaves')[0].name});
                ifc.get('assigned_networks').add(bond.get('assigned_networks').models);
                bond.get('assigned_networks').reset();
                bond.set({checked: false});
                this.interfaces.remove(bond);
            }, this);
        },
        loadDefaults: function() {
            this.disableControls(true);
            this.interfaces.fetch({url: _.result(this.nodes.at(0), 'url') + '/interfaces/default_assignment', reset: true})
                .fail(_.bind(function() {
                    utils.showErrorDialog({
                        title: $.t('cluster_page.nodes_tab.configure_interfaces.configuration_error.title'),
                        message: $.t('cluster_page.nodes_tab.configure_interfaces.configuration_error.load_defaults_warning')
                    });
                }, this));
        },
        revertChanges: function() {
            this.interfaces.reset(_.cloneDeep(this.nodes.at(0).interfaces.toJSON()), {parse: true});
        },
        applyChanges: function() {
            this.disableControls(true);
            var bonds = this.interfaces.filter(function(ifc) {return ifc.isBond();});
            // bonding map contains indexes of slave interfaces
            // it is needed to build the same configuration for all the nodes
            // as interface names might be different, so we use indexes
            var bondingMap = _.map(bonds, function(bond) {
                return _.map(bond.get('slaves'), function(slave) {
                    return this.interfaces.indexOf(this.interfaces.findWhere(slave));
                }, this);
            }, this);
            return $.when.apply($, this.nodes.map(function(node) {
                // removing previously configured bonds
                var oldNodeBonds = node.interfaces.filter(function(ifc) {return ifc.isBond();});
                node.interfaces.remove(oldNodeBonds);
                // creating node-specific bonds without slaves
                var nodeBonds = _.map(bonds, function(bond) {
                    return new models.Interface(_.omit(bond.toJSON(), 'slaves'), {parse: true});
                }, this);
                node.interfaces.add(nodeBonds);
                // determining slaves using bonding map
                _.each(nodeBonds, function(bond, bondIndex) {
                    var slaveIndexes = bondingMap[bondIndex];
                    var slaveInterfaces = _.map(slaveIndexes, node.interfaces.at, node.interfaces);
                    bond.set({slaves: _.invoke(slaveInterfaces, 'pick', 'name')});
                });
                // assigning networks according to user choice
                node.interfaces.each(function(ifc, index) {
                    ifc.set({assigned_networks: new models.InterfaceNetworks(this.interfaces.at(index).get('assigned_networks').toJSON())});
                }, this);
                return Backbone.sync('update', node.interfaces, {url: _.result(node, 'url') + '/interfaces'});
            }, this))
            .done(function() {
                app.page.removeFinishedNetworkTasks();
            })
            .always(_.bind(this.checkForChanges, this))
            .fail(function() {
                utils.showErrorDialog({
                    title: $.t('cluster_page.nodes_tab.configure_interfaces.configuration_error.title'),
                    message: $.t('cluster_page.nodes_tab.configure_interfaces.configuration_error.saving_warning')
                });
            });
        },
        initialize: function(options) {
            this.constructor.__super__.initialize.apply(this, arguments);
            if (this.nodes.length) {
                this.model.on('change:status', function() {
                    this.revertChanges();
                    this.render();
                    this.checkForChanges();
                }, this);
                this.networkConfiguration = this.model.get('networkConfiguration');
                this.loading = $.when.apply($, this.nodes.map(function(node) {
                    node.interfaces = new models.Interfaces();
                    node.interfaces.url = _.result(node, 'url') + '/interfaces';
                    return node.interfaces.fetch();
                }, this).concat(this.networkConfiguration.fetch({cache: true})))
                    .done(_.bind(function() {
                        this.interfaces = new models.Interfaces(this.nodes.at(0).interfaces.toJSON(), {parse: true});
                        this.interfaces.on('reset add remove change:slaves', this.render, this);
                        this.interfaces.on('sync change:mode', this.checkForChanges, this);
                        this.interfaces.on('change:checked reset', this.updateBondingControlsState, this);
                        // FIXME: modifying prototype to easily access NetworkConfiguration model
                        // should be reimplemented in a less hacky way
                        var networks = this.networkConfiguration.get('networks');
                        models.InterfaceNetwork.prototype.getFullNetwork = function() {
                            return networks.findWhere({name: this.get('name')});
                        };
                        var networkingParameters = this.networkConfiguration.get('networking_parameters');
                        models.Network.prototype.getVlanRange = function() {
                            if (!this.get('meta').neutron_vlan_range) {
                                var externalNetworkData = this.get('meta').ext_net_data;
                                var vlanStart = externalNetworkData ? networkingParameters.get(externalNetworkData[0]) : this.get('vlan_start');
                                return _.isNull(vlanStart) ? vlanStart : [vlanStart, externalNetworkData ? vlanStart + networkingParameters.get(externalNetworkData[1]) - 1 : vlanStart];
                            }
                            return networkingParameters.get('vlan_range');
                        };
                        this.render();
                    }, this))
                    .fail(_.bind(this.goToNodeList, this));
            } else {
                this.goToNodeList();
            }
            this.initButtons();
        },
        beforeTearDown: function() {
            delete models.InterfaceNetwork.prototype.getFullNetwork;
            delete models.Network.prototype.getVlanRange;
        },
        renderInterfaces: function() {
            this.tearDownRegisteredSubViews();
            this.$('.node-networks').html('');
            var slaveInterfaceNames = _.pluck(_.flatten(_.filter(this.interfaces.pluck('slaves'))), 'name');
            this.interfaces.each(_.bind(function(ifc) {
                if (!_.contains(slaveInterfaceNames, ifc.get('name'))) {
                    var nodeInterface = new NodeInterface({model: ifc, screen: this});
                    this.registerSubView(nodeInterface);
                    this.$('.node-networks').append(nodeInterface.render().el);
                }
            }, this));
            // if any errors found disable apply button
            _.each(this.interfaces.invoke('validate'), _.bind(function(interfaceValidationResult) {
                if (!_.isEmpty(interfaceValidationResult)) {
                    this.applyChangesButton.set('disabled', true);
                }
            }, this));
        },
        render: function() {
            this.$el.html(this.template({
                nodes: this.nodes,
                locked: this.isLocked(),
                bondingAvailable: this.bondingAvailable()
            })).i18n();
            if (this.loading && this.loading.state() != 'pending') {
                this.renderInterfaces();
                this.checkForChanges();
            }
            this.setupButtonsBindings();
            return this;
        }
    });

    NodeInterface = Backbone.View.extend({
        template: _.template(nodeInterfaceTemplate),
        templateHelpers: _.pick(utils, 'showBandwidth'),
        events: {
            'sortremove .logical-network-box': 'dragStart',
            'sortstart .logical-network-box': 'dragStart',
            'sortreceive .logical-network-box': 'dragStop',
            'sortstop .logical-network-box': 'dragStop',
            'sortactivate .logical-network-box': 'dragActivate',
            'sortdeactivate .logical-network-box': 'dragDeactivate',
            'sortover .logical-network-box': 'updateDropTarget',
            'click .btn-remove-interface': 'removeInterface'
        },
        bindings: {
            'input[type=checkbox]': {
                observe: 'checked'
            },
            'select[name=mode]': {
                observe: 'mode',
                selectOptions: {
                    collection: function() {
                        return _.map(models.Interface.prototype.bondingModes, function(mode) {
                            return {value: mode, label: $.t('cluster_page.nodes_tab.configure_interfaces.bonding_modes.' + mode, {defaultValue: mode})};
                        });
                    }
                }
            }
        },
        removeInterface: function(e) {
            var slaveInterfaceId = parseInt($(e.currentTarget).data('interface-id'), 10);
            var slaveInterface = this.screen.interfaces.get(slaveInterfaceId);
            this.model.set('slaves', _.reject(this.model.get('slaves'), {name: slaveInterface.get('name')}));
        },
        dragStart: function(event, ui) {
            var networkNames = $(ui.item).find('.logical-network-item').map(function(index, el) {
                return $(el).data('name');
            }).get();
            this.screen.draggedNetworks = this.model.get('assigned_networks').filter(function(network) {
                return _.contains(networkNames, network.get('name'));
            });
            if (event.type == 'sortstart') {
                this.updateDropTarget();
            } else if (event.type == 'sortremove') {
                this.model.get('assigned_networks').remove(this.screen.draggedNetworks);
            }
        },
        dragStop: function(event, ui) {
            if (event.type == 'sortreceive') {
                this.model.get('assigned_networks').add(this.screen.draggedNetworks);
            }
            this.render();
            this.screen.draggedNetworks = null;
        },
        updateDropTarget: function(event) {
            this.screen.dropTarget = this;
        },
        checkIfEmpty: function() {
            this.$('.network-help-message').toggle(!this.model.get('assigned_networks').length && !this.screen.isLocked());
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.model.get('assigned_networks').on('add remove', this.checkIfEmpty, this);
            this.model.get('assigned_networks').on('add remove', this.screen.checkForChanges, this.screen);
        },
        handleValidationErrors: function() {
            var validationResult = this.model.validate();
            if (validationResult.length) {
                this.screen.applyChangesButton.set('disabled', true);
                _.each(validationResult, _.bind(function(error) {
                    this.$('.physical-network-box[data-name=' + this.model.get('name') + ']')
                        .addClass('nodrag')
                        .next('.network-box-error-message').text(error);
                }, this));
            }
        },
        render: function() {
            this.$el.html(this.template(_.extend({
                ifc: this.model,
                locked: this.screen.isLocked(),
                bondingAvailable: this.screen.bondingAvailable()
            }, this.templateHelpers))).i18n();
            this.checkIfEmpty();
            this.$('.logical-network-box').sortable({
                connectWith: '.logical-network-box',
                items: '.logical-network-group:not(.disabled)',
                containment: this.screen.$('.node-networks'),
                disabled: this.screen.isLocked()
            }).disableSelection();
            this.handleValidationErrors();
            this.stickit(this.model);
            return this;
        }
    });

    return EditNodeInterfacesScreen;
});
