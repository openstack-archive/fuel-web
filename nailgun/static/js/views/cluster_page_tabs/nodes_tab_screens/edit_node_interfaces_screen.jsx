/*
 * Copyright 2015 Mirantis, Inc.
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
    'backbone',
    'react',
    'i18n',
    'utils',
    'models',
    'jsx!views/controls',
    'jsx!component_mixins',
    'jquery-ui'
],
function($, _, Backbone, React, i18n, utils, models, controls, ComponentMixins) {
    'use strict';

    var cx = React.addons.classSet,
        ScreenMixin, EditNodeInterfacesScreen, NodeInterface;

    ScreenMixin = {
        goToNodeList: function() {
            app.navigate('#cluster/' + this.props.cluster.get('id') + '/nodes', {trigger: true});
        },
        isLockedScreen: function() {
            return this.props.cluster && !!this.props.cluster.tasks({group: 'deployment', status: 'running'}).length;
        },
        returnToNodeList: function() {
            if (this.hasChanges()) {
                app.page.discardSettingsChanges({cb: _.bind(this.goToNodeList, this)});
            } else {
                this.goToNodeList();
            }
        }
    };

    EditNodeInterfacesScreen = React.createClass({
        mixins: [
            ScreenMixin,
            ComponentMixins.backboneMixin('interfaces', 'change:checked change:slaves reset sync'),
            ComponentMixins.backboneMixin('cluster', 'change:status change:networkConfiguration change:nodes sync'),
            ComponentMixins.backboneMixin('nodes', 'change sync')
        ],
        getInitialState: function() {
            return {
                actionInProgress: false,
                interfaceErrors: {}
            };
        },
        setInitialData: function() {
            this.initialInterfaces = this.interfacesToJSON();
        },
        componentWillMount: function() {
            this.setInitialData();
        },
        getDraggedNetworks: function() {
            return this.draggedNetworks || null;
        },
        setDraggedNetworks: function(networks) {
            this.draggedNetworks = networks;
        },
        interfacesToJSON: function() {
            // This needs to be done -- sometimes 'state' is sent from the API and sometimes not
            // It's better to just unify all inputs to the one without state.
            return this.props.interfaces.map(function(ifc) { return _.omit(ifc.toJSON(), 'state'); });
        },
        hasChanges: function() {
            return !_.isEqual(this.initialInterfaces, this.interfacesToJSON());
        },
        loadDefaults: function() {
            this.setState({actionInProgress: true});
            $.when(this.props.interfaces.fetch({
                url: _.result(this.props.nodes.at(0), 'url') + '/interfaces/default_assignment', reset: true
            }, this)).done(_.bind(function() {
                this.setState({actionInProgress: false});
            }, this)).fail(_.bind(function() {
                var errorNS = 'cluster_page.nodes_tab.configure_interfaces.configuration_error.';

                utils.showErrorDialog({
                    title: i18n(errorNS + 'title'),
                    message: i18n(errorNS + 'load_defaults_warning')
                });
                this.goToNodeList();
            }, this));
        },
        revertChanges: function() {
            this.props.interfaces.reset(_.cloneDeep(this.initialInterfaces), {parse: true});
        },
        applyChanges: function() {
            var nodes = this.props.nodes,
                interfaces = this.props.interfaces,
                bonds = interfaces.filter(function(ifc) {return ifc.isBond();});
            // bonding map contains indexes of slave interfaces
            // it is needed to build the same configuration for all the nodes
            // as interface names might be different, so we use indexes
            var bondingMap = _.map(bonds, function(bond) {
                return _.map(bond.get('slaves'), function(slave) {
                    return interfaces.indexOf(interfaces.findWhere(slave));
                });
            });
            this.setState({actionInProgress: true});
            return $.when.apply($, nodes.map(function(node) {
                var oldNodeBonds, nodeBonds;
                // removing previously configured bonds
                oldNodeBonds = node.interfaces.filter(function(ifc) {return ifc.isBond();});
                node.interfaces.remove(oldNodeBonds);
                // creating node-specific bonds without slaves
                nodeBonds = _.map(bonds, function(bond) {
                    return new models.Interface(_.omit(bond.toJSON(), 'slaves'), {parse: true});
                }, this);
                node.interfaces.add(nodeBonds);
                // determining slaves using bonding map
                _.each(nodeBonds, function(bond, bondIndex) {
                    var slaveIndexes = bondingMap[bondIndex],
                        slaveInterfaces = _.map(slaveIndexes, node.interfaces.at, node.interfaces);
                    bond.set({slaves: _.invoke(slaveInterfaces, 'pick', 'name')});
                });

                // Assigning networks according to user choice
                node.interfaces.each(function(ifc, index) {
                    ifc.set({assigned_networks: new models.InterfaceNetworks(interfaces.at(index).get('assigned_networks').toJSON())});
                }, this);

                return Backbone.sync('update', node.interfaces, {url: _.result(node, 'url') + '/interfaces'});
            }, this))
                .done(_.bind(function() {
                    this.setInitialData();
                    app.page.removeFinishedNetworkTasks();
                }, this))
                .fail(function() {
                    var errorNS = 'cluster_page.nodes_tab.configure_interfaces.configuration_error.';

                    utils.showErrorDialog({
                        title: i18n(errorNS + 'title'),
                        message: i18n(errorNS + 'saving_warning')
                    });
                }).always(_.bind(function() {
                    this.setState({actionInProgress: false});
                }, this));
        },
        isLocked: function() {
            var hasLockedNodes = this.props.nodes.any(function(node) {
                return !(node.get('pending_addition') || node.get('status') == 'error');
            });
            return hasLockedNodes || this.isLockedScreen();
        },
        bondingAvailable: function() {
            var cluster = this.props.cluster,
                isExperimental = _.contains(app.version.get('feature_groups'), 'experimental'),
                iserDisabled = !cluster.get('settings').get('storage.iser.value'),
                mellanoxSriovDisabled = cluster.get('settings').get('neutron_mellanox.plugin.value') != 'ethernet';
            return !this.isLocked() && isExperimental && cluster.get('net_provider') == 'neutron' && iserDisabled && mellanoxSriovDisabled;
        },
        bondInterfaces: function() {
            this.setState({actionInProgress: true});
            var interfaces = this.props.interfaces.filter(function(ifc) {return ifc.get('checked') && !ifc.isBond();}),
                bonds = this.props.interfaces.find(function(ifc) {return ifc.get('checked') && ifc.isBond();});
            if (!bonds) {
                // if no bond selected - create new one
                bonds = new models.Interface({
                    type: 'bond',
                    name: this.props.interfaces.generateBondName(),
                    mode: models.Interface.prototype.bondingModes[0],
                    assigned_networks: new models.InterfaceNetworks(),
                    slaves: _.invoke(interfaces, 'pick', 'name')
                });
            } else {
                // adding interfaces to existing bond
                bonds.set({slaves: bonds.get('slaves').concat(_.invoke(interfaces, 'pick', 'name'))});
                // remove the bond to add it later and trigger re-rendering
                this.props.interfaces.remove(bonds, {silent: true});
            }
            _.each(interfaces, function(ifc) {
                bonds.get('assigned_networks').add(ifc.get('assigned_networks').models);
                ifc.get('assigned_networks').reset();
                ifc.set({checked: false});
            });
            this.props.interfaces.add(bonds);
            this.setState({actionInProgress: false});
        },
        unbondInterfaces: function() {
            this.setState({actionInProgress: true});
            _.each(this.props.interfaces.where({checked: true}), function(bond) {
                // assign all networks from the bond to the first slave interface
                var ifc = this.props.interfaces.findWhere({name: bond.get('slaves')[0].name});
                ifc.get('assigned_networks').add(bond.get('assigned_networks').models);
                bond.get('assigned_networks').reset();
                bond.set({checked: false});
                this.props.interfaces.remove(bond);
            }, this);
            this.setState({actionInProgress: false});
        },
        validate: function() {
            var interfaceErrors = {},
                validationResult,
                networkConfiguration = this.props.cluster.get('networkConfiguration'),
                networkingParameters = networkConfiguration.get('networking_parameters'),
                networks = networkConfiguration.get('networks');

            if (!this.props.interfaces) {
                return;
            }

            this.props.interfaces.each(_.bind(function(ifc) {
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
            var configureInterfacesTransNS = 'cluster_page.nodes_tab.configure_interfaces.',
                nodes = this.props.nodes,
                nodeNames = nodes.pluck('name'),
                interfaces = this.props.interfaces,
                locked = this.isLocked(),
                bondingAvailable = this.bondingAvailable(),
                checkedInterfaces = interfaces.filter(function(ifc) {return ifc.get('checked') && !ifc.isBond();}),
                checkedBonds = interfaces.filter(function(ifc) {return ifc.get('checked') && ifc.isBond();}),
                creatingNewBond = checkedInterfaces.length >= 2 && !checkedBonds.length,
                addingInterfacesToExistingBond = !!checkedInterfaces.length && checkedBonds.length == 1,
                bondingPossible = creatingNewBond || addingInterfacesToExistingBond,
                unbondingPossible = !checkedInterfaces.length && !!checkedBonds.length,
                hasChanges = this.hasChanges(),
                hasErrors = _.chain(this.state.interfaceErrors).values().some().value(),
                slaveInterfaceNames = _.pluck(_.flatten(_.filter(interfaces.pluck('slaves'))), 'name'),
                returnEnabled = !this.state.actionInProgress,
                loadDefaultsEnabled = !this.state.actionInProgress,
                revertChangesEnabled = !this.state.actionInProgress && hasChanges,
                applyEnabled = !hasErrors && !this.state.actionInProgress && hasChanges;

            return (
                <div className='edit-node-networks-screen' style={{display: 'block'}} ref='nodeNetworksScreen'>
                    <div className={cx({'edit-node-interfaces': true, 'changes-locked': locked})}>
                        <h3>
                            {i18n(configureInterfacesTransNS + 'title', {count: nodes.length, name: nodeNames.join(', ')})}
                        </h3>
                    </div>

                    <div className='row'>
                        <div className='page-control-box'>
                            <div className='page-control-button-placeholder'>
                                <button className='btn btn-bond' disabled={!bondingAvailable || !bondingPossible} onClick={this.bondInterfaces}>{i18n(configureInterfacesTransNS + 'bond_button')}</button>
                                <button className='btn btn-unbond' disabled={!bondingAvailable || !unbondingPossible} onClick={this.unbondInterfaces}>{i18n(configureInterfacesTransNS + 'unbond_button')}</button>
                            </div>
                        </div>
                        {bondingAvailable &&
                            <div className='bond-speed-warning alert hide'>{i18n(configureInterfacesTransNS + 'bond_speed_warning')}</div>
                        }

                        <div className='node-networks'>
                            {
                                interfaces.map(_.bind(function(ifc) {
                                    if (!_.contains(slaveInterfaceNames, ifc.get('name'))) {
                                        return <NodeInterface {...this.props}
                                            key={'interface-' + ifc.get('name')}
                                            interface={ifc}
                                            locked={locked}
                                            bondingAvailable={bondingAvailable}
                                            getDraggedNetworks={this.getDraggedNetworks}
                                            setDraggedNetworks={this.setDraggedNetworks}
                                            errors={this.state.interfaceErrors[ifc.get('name')]}
                                            validate={this.validate}
                                            refresh={this.refresh}
                                        />;
                                    }
                                }, this))
                            }
                        </div>

                        <div className='page-control-box'>
                            <div className='back-button pull-left'>
                                <button className='btn btn-return' onClick={this.returnToNodeList} disabled={!returnEnabled}>{i18n('cluster_page.nodes_tab.back_to_nodes_button')}</button>
                            </div>
                            <div className='page-control-button-placeholder'>
                                <button className='btn btn-defaults' onClick={this.loadDefaults} disabled={!loadDefaultsEnabled}>{i18n('common.load_defaults_button')}</button>
                                <button className='btn btn-revert-changes' onClick={this.revertChanges} disabled={!revertChangesEnabled}>{i18n('common.cancel_changes_button')}</button>
                                <button className='btn btn-success btn-apply' onClick={this.applyChanges} disabled={!applyEnabled}>{i18n('common.apply_button')}</button>
                            </div>
                        </div>
                    </div>
                </div>
            );
        }
    });

    NodeInterface = React.createClass({
        mixins: [
            ComponentMixins.backboneMixin('cluster', 'change:status'),
            ComponentMixins.backboneMixin('interface', 'change:checked change:mode'),
            ComponentMixins.backboneMixin({
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
                // NOTE(pkaminski): .data('name') returns an incorrect result here.
                // This is probably caused by jQuery .data cache (attr reads directly from DOM).
                // http://api.jquery.com/data/#data-html5
                return $(el).attr('data-name');
            });
            if (e.type == 'sortstart') {
                // NOTE(pkaminski): Save initial networks state -- this is used for blocking
                // of dragging within one interface -- see also this.dragStop
                this.initialNetworks = this.props.interface.get('assigned_networks').pluck('name');
            }
            if (e.type == 'sortremove') {
                $(this.refs.logicalNetworkBox.getDOMNode()).sortable('cancel');
                this.props.interface.get('assigned_networks').remove(this.props.getDraggedNetworks());
            } else {
                this.props.setDraggedNetworks(this.props.interface.get('assigned_networks').filter(function(network) {
                        return _.contains(networkNames, network.get('name'));
                    })[0]
                );
            }
        },
        dragStop: function(e) {
            var networks;

            if (e.type == 'sortreceive') {
                this.props.interface.get('assigned_networks').add(this.props.getDraggedNetworks());
            } else if (e.type == 'sortstop') {
                // Block dragging within an interface
                networks = this.props.interface.get('assigned_networks').pluck('name');
                if (!_.xor(networks, this.initialNetworks).length) {
                    $(this.refs.logicalNetworkBox.getDOMNode()).sortable('cancel');
                }
                this.initialNetworks = [];
            }
            this.props.setDraggedNetworks(null);
        },
        bondingChanged: function(name, value) {
            this.props.interface.set({checked: value});
        },
        bondingModeChanged: function(name, value) {
            this.props.interface.set({mode: value});
        },
        bondingRemoveInterface: function(slaveName) {
            var slaves = _.reject(this.props.interface.get('slaves'), {name: slaveName});
            this.props.interface.set('slaves', slaves);
        },
        render: function() {
            var configureInterfacesTransNS = 'cluster_page.nodes_tab.configure_interfaces.',
                ifc = this.props.interface,
                cluster = this.props.cluster,
                locked = this.props.locked,
                networkConfiguration = cluster.get('networkConfiguration'),
                networks = networkConfiguration.get('networks'),
                networkingParameters = networkConfiguration.get('networking_parameters'),
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
                networksToAdd = [],
                showHelpMessage = !locked && !assignedNetworks.length;
            assignedNetworks.each(function(interfaceNetwork) {
                if (interfaceNetwork.getFullNetwork(networks).get('name') != 'floating') {
                    if (networksToAdd.length) {
                        assignedNetworksGrouped.push(networksToAdd);
                    }
                    networksToAdd = [];
                }
                networksToAdd.push(interfaceNetwork);
            });
            if (networksToAdd.length) {
                assignedNetworksGrouped.push(networksToAdd);
            }
            return (
                <div className={cx({'physical-network-box': true, nodrag: this.props.errors})}>
                    <div className='network-box-item'>
                        {ifc.isBond() &&
                            <div className='network-box-name'>
                                {this.props.bondingAvailable ?
                                    <controls.Input
                                        type='checkbox'
                                        label={ifc.get('name')}
                                        labelClassName='pull-left'
                                        onChange={this.bondingChanged}
                                        checked={ifc.get('checked')} />
                                    :
                                    <div className='network-bond-name pull-left disabled'>{ifc.get('name')}</div>
                                }
                                <div className='network-bond-mode pull-right'>
                                    <controls.Input
                                        type='select'
                                        disabled={!this.props.bondingAvailable}
                                        onChange={this.bondingModeChanged}
                                        value={ifc.get('mode')}
                                        label={i18n(configureInterfacesTransNS + 'bonding_mode') + ':'}
                                        children={_.map(models.Interface.prototype.bondingModes, function(mode) {
                                            return <option key={'option-' + mode} value={mode}>{i18n(configureInterfacesTransNS + 'bonding_modes.' + mode)}</option>;
                                        })} />
                                </div>
                                <div className='clearfix'></div>
                            </div>
                        }

                        <div className='physical-network-checkbox'>
                            {!ifc.isBond() && bondable && <controls.Input type='checkbox' onChange={this.bondingChanged} checked={ifc.get('checked')} />}
                        </div>

                        <div className='network-connections-block'>
                            {_.map(slaveInterfaces, function(slaveInterface) {
                                return <div key={'network-connections-slave-' + slaveInterface.get('name')} className='network-interfaces-status'>
                                        <div className={cx(slaveOnlineClass(slaveInterface))}></div>
                                        <div className='network-interfaces-name'>{slaveInterface.get('name')}</div>
                                    </div>;
                                })
                            }
                        </div>

                        <div className='network-connections-info-block'>
                            {_.map(slaveInterfaces, function(slaveInterface) {
                                return <div key={'network-connections-info-' + slaveInterface.get('name')} className='network-connections-info-block-item'>
                                        <div className='network-connections-info-position'></div>
                                        <div className='network-connections-info-description'>
                                            <div>{i18n(configureInterfacesTransNS + 'mac')}: {slaveInterface.get('mac')}</div>
                                            <div>{i18n(configureInterfacesTransNS + 'speed')}:
                                                {utils.showBandwidth(slaveInterface.get('current_speed'))}</div>
                                            {(this.props.bondingAvailable && slaveInterfaces.length >= 3) &&
                                                <button className='btn btn-link btn-remove-interface'
                                                        type='button'
                                                        onClick={this.bondingRemoveInterface.bind(this, slaveInterface.get('name'))}>{i18n('common.remove_button')}</button>
                                            }
                                        </div>
                                    </div>;
                            }, this)
                            }
                        </div>

                        <div className='logical-network-box' ref='logicalNetworkBox'>
                            {!showHelpMessage ? _.map(assignedNetworksGrouped, function(networkGroup) {
                                var network = networkGroup[0].getFullNetwork(networks);

                                if (!network) {
                                    return;
                                }

                                var classes = {
                                        'logical-network-group': true,
                                        disabled: locked || network.get('meta').unmovable
                                    },
                                    vlanRange = network.getVlanRange(networkingParameters);

                                return <div key={'network-box-' + network.get('id')} className={cx(classes)}>
                                        {_.map(networkGroup, function(interfaceNetwork) {
                                            return (
                                                <div key={'interface-network-' + interfaceNetwork.get('name')}
                                                    className='logical-network-item' data-name={interfaceNetwork.get('name')}>
                                                    <div className='name'>{i18n('network.' + interfaceNetwork.get('name'), {defaultValue: interfaceNetwork.get('name')})}</div>
                                                    {vlanRange &&
                                                        <div className='id'>
                                                            {i18n(configureInterfacesTransNS + 'vlan_id', {count: _.uniq(vlanRange).length})}:
                                                            {_.uniq(vlanRange).join('-')}
                                                        </div>
                                                    }
                                                </div>
                                            );
                                        })
                                        }
                                    </div>;
                            }, this)
                            : <div className='network-help-message'>{i18n(configureInterfacesTransNS + 'drag_and_drop_description')}</div>
                            }
                        </div>
                    </div>
                    <div className='network-box-error-message common enable-selection'>
                        {this.props.errors || ''}
                    </div>
                </div>
            );
        }
    });

    EditNodeInterfacesScreen.fetchData = function(options) {
        var cluster = options.cluster,
            nodeIds = utils.deserializeTabOptions(options.screenOptions[0]).nodes.split(',').map(function(id) {return parseInt(id, 10);}),
            nodeLoadingErrorNS = 'cluster_page.nodes_tab.configure_interfaces.node_loading_error.',
            nodes,
            networkConfiguration;

        networkConfiguration = cluster.get('networkConfiguration');
        nodes = new models.Nodes(cluster.get('nodes').getByIds(nodeIds));
        if (nodes.length != nodeIds.length) {
            utils.showErrorDialog({
                title: i18n(nodeLoadingErrorNS + 'title'),
                message: i18n(nodeLoadingErrorNS + 'load_error')
            });
            ScreenMixin.goToNodeList();
            return;
        }

        return $.when.apply($, nodes.map(function(node) {
            node.interfaces = new models.Interfaces();
            return node.interfaces.fetch({
                url: _.result(node, 'url') + '/interfaces',
                reset: true
            }, this);
        }, this).concat([networkConfiguration.fetch({cache: true})]))
            .then(_.bind(function() {
                var interfaces = new models.Interfaces();
                interfaces.set(_.cloneDeep(nodes.at(0).interfaces.toJSON()), {parse: true});

                return {
                    interfaces: interfaces,
                    nodes: nodes
                };
            }, this));
    };

    return EditNodeInterfacesScreen;
});
