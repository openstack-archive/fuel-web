/*
 * Copyright 2014 Mirantis, Inc.
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
    'jquery',
    'underscore',
    'react',
    'utils',
    'models',
    'jsx!views/dialogs',
    'jsx!views/controls'
],
function($, _, React, utils, models, dialogs, controls) {
    'use strict';

    var cx = React.addons.classSet;

    var ScreenMixin = {
        goToNodeList: function() {
            app.navigate('#cluster/' + this.props.model.get('id') + '/nodes', {trigger: true});
        },
        isLockedScreen: function() {
            return this.model && !!this.model.tasks({group: 'deployment', status: 'running'}).length;
        }
    };

    var NodeInterfaces = React.createClass({
        mixins: [
            React.BackboneMixin('model', 'change:status'),
            React.BackboneMixin('interface', 'change:status'),
            React.BackboneMixin({
                modelOrCollection: function(props) {
                    return props.interface.get('assigned_networks');
                },
                renderOn: 'add change remove'
            })
        ],
        propTypes: {
            bondingAvailable: React.PropTypes.bool,
            locked: React.PropTypes.bool,
            refresh: React.PropTypes.func
        },
        onModelChange: function() {
            this.props.refresh();
        },
        componentDidMount: function() {
            $(this.refs.logicalNetworkBox.getDOMNode()).sortable({
                connectWith: '.logical-network-box',
                items: '.logical-network-group:not(.disabled)',
                containment: $('.node-networks'),
                disabled: this.props.locked,
                receive: this.dragStop,
                remove: this.dragStart,
                start: this.dragStart,
                stop: this.dragStop
            }).disableSelection();
        },
        componentDidUpdate: function() {
            this.props.validate();
        },
        dragStart: function(e, ui) {
            var networkNames = $(ui.item).find('.logical-network-item').map(function(index, el) {
                // NOTE: .data('name') returns an incorrect result here.
                //       This is probably caused by jQuery .data cache (attr reads directly from DOM).
                //       http://api.jquery.com/data/#data-html5
                return $(el).attr('data-name');
            });
            if (e.type == 'sortremove') {
                $(this.refs.logicalNetworkBox.getDOMNode()).sortable('cancel');
                this.props.interface.get('assigned_networks').remove(this.props.getDraggedNetworks());
            } else {
                this.props.setDraggedNetworks(this.props.interface.get('assigned_networks').filter(function(network) {
                        return _.contains(networkNames, network.get('name'));
                    })
                );
            }
        },
        dragStop: function(e) {
            if (e.type == 'sortreceive') {
                this.props.interface.get('assigned_networks').add(this.props.getDraggedNetworks());
            }
            this.props.setDraggedNetworks(null);
        },
        bondingChanged: function() {
            var checked = this.props.interface.get('checked');
            this.props.interface.set({checked: !checked});
            this.props.refresh();
        },
        bondingModeChanged: function(e) {
            this.props.interface.set({mode: e.target.value});
            this.props.refresh();
        },
        bondingRemoveInterface: function(e) {
            console.log('TODO');
        },
        render: function() {
            var ifc = this.props.interface,
                cluster = this.props.model,
                locked = this.props.locked,
                networkConfiguration = cluster.get('networkConfiguration'),
                networks = networkConfiguration.get('networks'),
                networkingParameters = networkConfiguration.get('networking_parameters'),
                selectOptions = _.map(models.Interface.prototype.bondingModes, function(mode) {
                    return {value: mode, label: $.t('cluster_page.nodes_tab.configure_interfaces.bonding_modes.' + mode)};
                }),
                slaveInterfaces = ifc.getSlaveInterfaces(),
                assignedNetworks = ifc.get('assigned_networks'),
                bondable = this.props.bondingAvailable && assignedNetworks && !assignedNetworks.find(function(interfaceNetwork) {
                    return interfaceNetwork.getFullNetwork(networks).get('meta').unmovable;
                }),
                slaveOnlineClass = function(slave) {
                    var slaveDown = slave.get('state') == 'down';

                    return {
                        'interface-online': !slaveDown,
                        'interface-offline': slaveDown
                    };
                },
                assignedNetworksGrouped = [],
                networkToAdd = [],
                showHelpMessage = !locked && !assignedNetworks.length;
            assignedNetworks.each(function(interfaceNetwork) {
                if (interfaceNetwork.getFullNetwork(networks) != 'floating') {
                    if (networkToAdd.length) {
                        assignedNetworksGrouped.push(networkToAdd);
                    }
                    networkToAdd = [];
                }
                networkToAdd.push(interfaceNetwork);
            });
            if (networkToAdd.length) {
                assignedNetworksGrouped.push(networkToAdd);
            }

            return (
                <div className={cx({'physical-network-box': true, nodrag: this.props.errors})} data-name="{ifc.get('name')}">
                    <div className="network-box-item">
                        { ifc.isBond() ?
                            <div className="network-box-name">
                                { this.props.bondingAvailable ?
                                    (
                                        <controls.Input
                                            type="checkbox"
                                            label={ifc.get('name')}
                                            labelClassName="pull-left"
                                            onChange={this.bondingChanged} />
                                    )
                                    :
                                    <div className="network-bond-name pull-left disabled">{ifc.get('name')}</div>
                                }
                                <div className="network-bond-mode pull-right">
                                    <b>{$.t('cluster_page.nodes_tab.configure_interfaces.bonding_mode')}:</b>
                                    <span>
                                        <select name="mode" value={ifc.get('mode')} disabled={this.props.bondingAvailable ? '' : 'disabled'} onChange={this.bondingModeChanged}>
                                            {_.map(selectOptions, function(option) {
                                                    return (
                                                        <option value={option.value}>{option.label}</option>
                                                    );
                                                })
                                            }
                                        </select>
                                    </span>
                                </div>
                                <div className="clearfix"></div>
                            </div>
                        : null
                        }

                        <div className="physical-network-checkbox">
                            { !ifc.isBond() && bondable ?
                                <controls.Input
                                    type="checkbox"
                                    onChange={this.bondingChanged} />
                            : null
                            }
                        </div>

                        <div className="network-connections-block">
                            { _.map(slaveInterfaces, function(slaveInterface) {
                                return (
                                    <div className="network-interfaces-status">
                                        <div className={cx(slaveOnlineClass(slaveInterface))}></div>
                                        <div className="network-interfaces-name">{slaveInterface.get('name')}</div>
                                    </div>
                                    );
                                })
                            }
                        </div>

                        <div className="network-connections-info-block">
                            { _.map(slaveInterfaces, function(slaveInterface) {
                                return (
                                    <div className="network-connections-info-block-item">
                                        <div className="network-connections-info-position"></div>
                                        <div className="network-connections-info-description">
                                            <div>MAC: {slaveInterface.get('mac')}</div>
                                            <div>{$.t('cluster_page.nodes_tab.configure_interfaces.speed')}:
                                                {utils.showBandwidth(slaveInterface.get('current_speed'))}</div>
                                            { (this.props.bondingAvailable && slaveInterfaces.length >= 3) ?
                                                <button className="btn btn-link btn-remove-interface"
                                                        type="button" data-interface-id="{slaveInterface.id}" onClick={this.bondingRemoveInterface}>Remove</button>
                                                : null
                                            }
                                        </div>
                                    </div>
                                );
                            }, this)
                            }
                        </div>

                        <div className="logical-network-box" ref="logicalNetworkBox">
                            { !showHelpMessage ? _.map(assignedNetworksGrouped, function(networkGroup) {
                                var network = networkGroup[0].getFullNetwork(networks);

                                if (!network) {
                                    return;
                                }

                                var classes = {
                                        'logical-network-group': true,
                                        disabled: locked || network.get('meta').unmovable
                                    },
                                    vlanRange = network.getVlanRange(networkingParameters);

                                return (
                                    <div className={cx(classes)}>
                                        { _.map(networkGroup, function(interfaceNetwork) {
                                            return (
                                                <div className="logical-network-item" data-name={interfaceNetwork.get('name')}>
                                                    <div className="name">{$.t('network.' + interfaceNetwork.get('name'), {defaultValue: interfaceNetwork.get('name')})}</div>
                                                    { !_.isNull(vlanRange) ?
                                                        <div className="id">
                                                            {$.t('cluster_page.nodes_tab.configure_interfaces.vlan_id', {count: _.uniq(vlanRange).length})}:
                                                            {_.uniq(vlanRange).join('-')}
                                                        </div>
                                                    : null
                                                    }
                                                </div>
                                            );
                                        })
                                        }
                                    </div>
                                );
                            }, this)
                            : <div className="network-help-message">{$.t("cluster_page.nodes_tab.configure_interfaces.drag_and_drop_description")}</div>
                            }
                        </div>
                    </div>
                    <div className="network-box-error-message common enable-selection">
                        { this.props.errors || '' }
                    </div>
                </div>
            );
        }
    });

    var EditNodeInterfacesScreen = React.createClass({
        mixins: [
            ScreenMixin,
            React.BackboneMixin('model', 'change:status'),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.model.get('assigned_networks');
            }}),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.model.get('networkConfiguration');
            }}),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.model.get('nodes');
            }})
        ],
        getInitialState: function() {
            return {
                actionInProgress: false,
                loading: true,
                interfaceErrors: {}
            };
        },
        getDraggedNetworks: function() {
            return this.draggedNetworks || null;
        },
        setDraggedNetworks: function(networks) {
            this.draggedNetworks = networks;
        },
        nodeToJSON: function(node) {
            return _.omit(node.toJSON(), 'checked', 'state');
        },
        setInitialData: function() {
            this.initialNode = this.node.toJSON();
            this.initialInterfaces = this.node.interfaces.map(this.nodeToJSON);
        },
        hasChanges: function() {
            return !_.isEqual(this.initialNode, this.node.toJSON()) ||
                !_.isEqual(this.initialInterfaces, this.node.interfaces.map(this.nodeToJSON));
        },
        loadDefaults: function() {
            this.setState({loading: true});
            $.when(this.node.interfaces.fetch({
                    url: _.result(this.node, 'url') + '/interfaces/default_assignment', reset: true
                }, this),
            this).done(_.bind(function() {
                this.setState({loading: false});
            }, this));
        },
        revertChanges: function() {
            this.node.interfaces.reset(_.cloneDeep(this.initialInterfaces), {parse: true});
            this.forceUpdate();
        },
        applyChanges: function() {
            var node = this.node,
                nodes = this.nodes;
            var bonds = node.interfaces.filter(function(ifc) {return ifc.isBond();});
            // bonding map contains indexes of slave interfaces
            // it is needed to build the same configuration for all the nodes
            // as interface names might be different, so we use indexes
            var bondingMap = _.map(bonds, function(bond) {
                return _.map(bond.get('slaves'), function(slave) {
                    return node.interfaces.indexOf(node.interfaces.findWhere(slave));
                });
            });
            // removing previously configured bonds
            var oldNodeBonds = node.interfaces.filter(function(ifc) {return ifc.isBond();});
            node.interfaces.remove(oldNodeBonds);
            // creating node-specific bonds without slaves
            var nodeBonds = _.map(bonds, function(bond) {
                return new models.Interface(_.omit(bond.toJSON(), 'slaves'), {parse: true});
            });
            node.interfaces.add(nodeBonds);
            // determining slaves using bonding map
            _.each(nodeBonds, function(bond, bondIndex) {
                var slaveIndexes = bondingMap[bondIndex];
                var slaveInterfaces = _.map(slaveIndexes, node.interfaces.at, node.interfaces);
                bond.set({slaves: _.invoke(slaveInterfaces, 'pick', 'name')});
            });
            this.setState({loading: true});
            return $.when.apply($, nodes.map(function(n, idx) {
                // removing previously configured bonds
                var oldNodeBonds = n.interfaces.filter(function(ifc) {return ifc.isBond();});
                n.interfaces.remove(oldNodeBonds);
                // creating node-specific bonds without slaves
                var nodeBonds = _.map(bonds, function(bond) {
                    return new models.Interface(_.omit(bond.toJSON(), 'slaves'), {parse: true});
                }, this);
                n.interfaces.add(nodeBonds);
                // determining slaves using bonding map
                _.each(nodeBonds, function(bond, bondIndex) {
                    var slaveIndexes = bondingMap[bondIndex];
                    var slaveInterfaces = _.map(slaveIndexes, n.interfaces.at, n.interfaces);
                    bond.set({slaves: _.invoke(slaveInterfaces, 'pick', 'name')});
                });

                if (idx > 0) {
                    // Assigning networks according to user choice to the remaining nodes -- reference node
                    // has index 0
                    n.interfaces.each(function(ifc, index) {
                        ifc.set({assigned_networks: new models.InterfaceNetworks(node.interfaces.at(index).get('assigned_networks').toJSON())});
                    }, this);
                }

                return Backbone.sync('update', n.interfaces, {url: _.result(n, 'url') + '/interfaces'});
            }, this))
                .done(_.bind(function() {
                    this.setInitialData();
                    app.page.removeFinishedNetworkTasks();
                }, this))
                //.always(_.bind(this.checkForChanges, this))
                .fail(function() {
                    utils.showErrorDialog({
                        title: $.t('cluster_page.nodes_tab.configure_interfaces.configuration_error.title'),
                        message: $.t('cluster_page.nodes_tab.configure_interfaces.configuration_error.saving_warning')
                    });
                }).always(_.bind(function() {
                    this.setState({loading: false});
                }, this));
        },
        componentWillMount: function() {
            var cluster = this.props.model,
                nodeIds = utils.deserializeTabOptions(this.props.screenOptions[0]).nodes.split(',').map(function(id) {return parseInt(id, 10);});
            this.networkConfiguration = cluster.get('networkConfiguration');
            this.nodes = new models.Nodes(cluster.get('nodes').getByIds(nodeIds));
            this.node = this.nodes.at(0);
            if (!this.node) {
                // TODO: just set nonexisting node id to get here
                utils.showErrorDialog({
                    title: $.t('cluster_page.nodes_tab.configure_interfaces.configuration_error.title'),
                    message: $.t('cluster_page.nodes_tab.configure_interfaces.configuration_error.load_defaults_warning')
                });
            }

            $.when.apply($, this.nodes.map(_.bind(function(n) {
                    n.interfaces = new models.Interfaces();
                    return n.interfaces.fetch({
                        url: _.result(n, 'url') + '/interfaces',
                        reset: true
                    }, this);
                }, this)).concat([this.networkConfiguration.fetch({cache: true})]),  this)
                .done(_.bind(function() {
                    this.setInitialData();
                    this.setState({loading: false});
                }, this));
        },
        isLocked: function() {
            return !(this.node.get('pending_addition') || this.node.get('status') == 'error' || this.isLockedScreen());

            /*
            // TODO: nodeIds?
            var nodesAvailableForChanges = this.nodes.filter(function(node) {
                return node.get('pending_addition') || node.get('status') == 'error';
            });
            // TODO: change .length to any
            return !nodesAvailableForChanges.length && this.isLockedScreen();
            */
        },
        returnToNodeList: function() {
            // TODO
            this.goToNodeList();
        },
        bondingAvailable: function() {
            var cluster = this.props.model;
            var iserDisabled =  cluster.get('settings').get('storage.iser.value') != true;
            var mellanoxSriovDisabled = cluster.get('settings').get('neutron_mellanox.plugin.value') != "ethernet";
            return !this.isLocked() && cluster.get('net_provider') == 'neutron' && iserDisabled && mellanoxSriovDisabled;
        },
        bondInterfaces: function() {
            this.setState({loading: true});
            var interfaces = this.node.interfaces.filter(function(ifc) {return ifc.get('checked') && !ifc.isBond();});
            var bond = this.node.interfaces.find(function(ifc) {return ifc.get('checked') && ifc.isBond();});
            if (!bond) {
                // if no bond selected - create new one
                bond = new models.Interface({
                    type: 'bond',
                    name: this.node.interfaces.generateBondName(),
                    mode: models.Interface.prototype.bondingModes[0],
                    assigned_networks: new models.InterfaceNetworks(),
                    slaves: _.invoke(interfaces, 'pick', 'name')
                });
            } else {
                // adding interfaces to existing bond
                bond.set({slaves: bond.get('slaves').concat(_.invoke(interfaces, 'pick', 'name'))});
                // remove the bond to add it later and trigger re-rendering
                this.node.interfaces.remove(bond, {silent: true});
            }
            _.each(interfaces, function(ifc) {
                bond.get('assigned_networks').add(ifc.get('assigned_networks').models);
                ifc.get('assigned_networks').reset();
                ifc.set({checked: false});
            });
            this.node.interfaces.add(bond);
            this.setState({loading: false});
        },
        unbondInterfaces: function() {
            this.setState({loading: true});
            _.each(this.node.interfaces.where({checked: true}), function(bond) {
                // assign all networks from the bond to the first slave interface
                var ifc = this.node.interfaces.findWhere({name: bond.get('slaves')[0].name});
                ifc.get('assigned_networks').add(bond.get('assigned_networks').models);
                bond.get('assigned_networks').reset();
                bond.set({checked: false});
                this.node.interfaces.remove(bond);
            }, this);
            this.setState({loading: false});
        },
        validate: function() {
            if (!this.node.interfaces) {
                return;
            }
            var interfaceErrors = {},
                validationResult,
                networkConfiguration = this.props.model.get('networkConfiguration'),
                networkingParameters = networkConfiguration.get('networking_parameters'),
                networks = networkConfiguration.get('networks');
            this.node.interfaces.each(_.bind(function(ifc) {
                validationResult = ifc.validate({
                    networkingParameters: networkingParameters,
                    networks: networks
                });
                if (validationResult.length) {
                    interfaceErrors[ifc.get('name')] = validationResult.join(' ');
                }
            }), this);
            if (!_.isEqual(this.state.interfaceErrors, interfaceErrors)) {
                this.setState({interfaceErrors: interfaceErrors});
            }
        },
        refresh: function() {
            this.forceUpdate();
        },
        render: function() {
            var locked = this.isLocked(),
                bondingAvailable = this.bondingAvailable(),
                checkedInterfaces = this.node.interfaces.filter(function(ifc) { return ifc.get('checked') && !ifc.isBond(); }),
                checkedBonds = this.node.interfaces.filter(function(ifc) { return ifc.get('checked') && ifc.isBond(); }),
                creatingNewBond = checkedInterfaces.length >= 2 && !checkedBonds.length,
                addingInterfacesToExistingBond = !!checkedInterfaces.length && checkedBonds.length == 1,
                bondingPossible = creatingNewBond || addingInterfacesToExistingBond,
                unbondingPossible = !checkedInterfaces.length && !!checkedBonds.length,
                hasChanges = this.hasChanges(),
                hasErrors = _.chain(this.state.interfaceErrors).values().some(_.identity).value(),
                node = this.node,
                interfaces = this.node.interfaces,
                slaveInterfaceNames = _.pluck(_.flatten(_.filter(interfaces.pluck('slaves'))), 'name'),
                returnEnabled = !this.state.loading,
                loadDefaultsEnabled = !this.state.loading,
                revertChangesEnabled = !this.state.loading && hasChanges,
                applyEnabled = !hasErrors && !this.state.loading && hasChanges;

            return (
                <div className="edit-node-networks-screen" style={{display: 'block'}}>
                    <div className={cx({'edit-node-interfaces': true, 'changes-locked': locked})}>
                        <h3>
                            {$.t('cluster_page.nodes_tab.configure_interfaces.title', {count: 1, name: node && node.get('name')})}
                        </h3>
                    </div>

                    <div className="row">
                        <div className="page-control-box">
                            <div className="page-control-button-placeholder">
                                <button className="btn btn-bond" disabled={!bondingAvailable || !bondingPossible} onClick={this.bondInterfaces}>{$.t("cluster_page.nodes_tab.configure_interfaces.bond_button")}</button>
                                <button className="btn btn-unbond" disabled={!bondingAvailable || !unbondingPossible} onClick={this.unbondInterfaces}>{$.t("cluster_page.nodes_tab.configure_interfaces.unbond_button")}</button>
                            </div>
                        </div>
                        {bondingAvailable ?
                            <div className="bond-speed-warning alert hide">{$.t("cluster_page.nodes_tab.configure_interfaces.bond_speed_warning")}</div>
                            : null
                        }

                        { this.state.loading ? <controls.ProgressBar /> : null }

                        <div className="node-networks">
                            {
                                interfaces.map(_.bind(function(ifc) {
                                    if (!_.contains(slaveInterfaceNames, ifc.get('name'))) {
                                        return <NodeInterfaces {...this.props}
                                                    interface={ifc}
                                                    locked={locked}
                                                    bondingAvailable={bondingAvailable}
                                                    getDraggedNetworks={this.getDraggedNetworks}
                                                    setDraggedNetworks={this.setDraggedNetworks}
                                                    errors={this.state.interfaceErrors[ifc.get('name')]}
                                                    validate={this.validate}
                                                    refresh={this.refresh}
                                                />
                                    };
                                }, this))
                            }
                        </div>

                        <div className="page-control-box">
                            <div className="back-button pull-left">
                                <button className="btn btn-return" onClick={this.returnToNodeList}>{$.t("cluster_page.nodes_tab.back_to_nodes_button")}</button>
                            </div>
                            <div className="page-control-button-placeholder">
                                <button className="btn btn-defaults" onClick={this.loadDefaults} disabled={!loadDefaultsEnabled}>{$.t("common.load_defaults_button")}</button>
                                <button className="btn btn-revert-changes" onClick={this.revertChanges} disabled={!revertChangesEnabled}>{$.t("common.cancel_changes_button")}</button>
                                <button className="btn btn-success btn-apply" onClick={this.applyChanges} disabled={!applyEnabled}>{$.t("common.apply_button")}</button>
                            </div>
                        </div>
                    </div>
                </div>
            );
        }
    });

    return EditNodeInterfacesScreen;
});
