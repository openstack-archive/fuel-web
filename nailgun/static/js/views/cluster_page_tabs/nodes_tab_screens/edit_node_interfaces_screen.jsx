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
            return !!this.model.tasks({group: 'deployment', status: 'running'}).length;
        }
    };

    var NodeInterfaces = React.createClass({
        mixins: [
            React.BackboneMixin('model', 'change:status'),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.model.get('networkConfiguration');
            }})
        ],
        propTypes: {
            bondingAvailable: React.PropTypes.bool,
            locked: React.PropTypes.bool
        },
        getInitialState: function() {
            return {
                showHelpMessage: false
            };
        },
        componentDidMount: function() {
            this.props.interface.get('assigned_networks').on('add remove', this.toggleHelpMessage, this);
            this.toggleHelpMessage();

            $('.logical-network-box', this.getDOMNode()).sortable({
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
        dragStart: function(e, ui) {
            var networkNames = $(ui.item).find('.logical-network-item').map(function(index, el) {
                return $(el).attr('data-name');  // TODO: for some reason, data('name') is incorrect here
            });
            if(e.type == 'sortremove') {
                $('.logical-network-box', this.getDOMNode()).sortable('cancel');
            }
            this.props.dragStart(e, ui, networkNames, this.props.interface);
            this.forceUpdate();
        },
        dragStop: function(e, ui) {
            this.props.dragStop(e, ui, this.props.interface);
            this.forceUpdate();
        },
        toggleHelpMessage: function() {
            var ifc = this.props.interface,
                locked = this.props.locked,
                showHelpMessage = !locked && !ifc.get('assigned_networks').length;
            this.setState({showHelpMessage: showHelpMessage});
        },
        render: function() {
            var cluster = this.props.model;
            var locked = this.props.locked;
            var networkConfiguration = cluster.get('networkConfiguration');
            var networks = networkConfiguration.get('networks');
            var getFullNetwork = function(ifcNetwork) {
                return networks && networks.findWhere({name: ifcNetwork.get('name')});
            };
            var getVlanRange = function(network) {
                var networkingParameters = networkConfiguration.get('networking_parameters');
                if (!network.get('meta').neutron_vlan_range) {
                    var externalNetworkData = network.get('meta').ext_net_data;
                    var vlanStart = externalNetworkData ? networkingParameters.get(externalNetworkData[0]) : network.get('vlan_start');
                    return _.isNull(vlanStart) ? vlanStart : [vlanStart, externalNetworkData ? vlanStart + networkingParameters.get(externalNetworkData[1]) - 1 : vlanStart];
                }
                return networkingParameters.get('vlan_range');
            };

            var slaveInterfaces = this.props.interface.getSlaveInterfaces();
            var movable = this.props.bondingAvailable && !cluster.get('assigned_networks').find(function(interfaceNetwork) {return getFullNetwork(interfaceNetwork).get('meta').unmovable;});
            var slaveOnlineClass = function(slave) {
                var slaveNotDown = slave.get('state') != 'down';

                return {
                    'interface-online': slaveNotDown,
                    'interface-offline': !slaveNotDown
                };
            };
            var assignedNetworksGrouped = [],
                networkToAdd = [];
            this.props.interface.get('assigned_networks').each(function(interfaceNetwork) {
                if (getFullNetwork(interfaceNetwork) != 'floating') {
                    if(networkToAdd.length) {
                        assignedNetworksGrouped.push(networkToAdd);
                    }
                    networkToAdd = [];
                }
                networkToAdd.push(interfaceNetwork);
            });
            if(networkToAdd.length) {
                assignedNetworksGrouped.push(networkToAdd);
            }

            return (
                <div className="physical-network-box" data-name="{this.props.interface.get('name')}">
                    <div className="network-box-item">
                        { this.props.interface.isBond() ?
                            <div className="network-box-name">
                                { this.props.bondingAvailable ?
                                    (
                                        <label>
                                            <div className="pull-left">
                                                <div className="custom-tumbler network-bond-name-checkbox">
                                                    <input type="checkbox" />
                                                    {/* TODO: <!-- [if !IE |(gte IE 9)]> --><span>&nbsp;</span><!-- <![endif] --> */}
                                                </div>
                                            </div>
                                            <div className="network-bond-name pull-left">{this.props.interface.get('name')}</div>
                                        </label>
                                    )
                                    :
                                    <div className="network-bond-name pull-left disabled">{this.props.interface.get('name')}</div>
                                }
                                <div className="network-bond-mode pull-right">
                                    <b>{$.t('cluster_page.nodes_tab.configure_interfaces.bonding_mode')}:</b>
                                    <span>
                                        <select name="mode" disabled={bondingAvailable ? '' : 'disabled'}></select>
                                    </span>
                                </div>
                                <div className="clearfix"></div>
                            </div>
                        : null
                        }

                        <div className="physical-network-checkbox">
                            { !this.props.interface.isBond() && movable ?
                                <label>
                                    <div className="custom-tumbler">
                                        <input type="checkbox" />
                                        {/* TODO: <!-- [if !IE |(gte IE 9)]> --><span>&nbsp;</span><!-- <![endif] -->*/}
                                    </div>
                                </label>
                            : null
                            }
                        </div>

                        <div className="network-connections-block">
                            { _.map(slaveInterfaces, function (slaveInterface) {
                                return (
                                    <div className="network-interfaces-status">
                                        <div className={cx(slaveOnlineClass(slaveInterface))}></div>
                                        <div className="network-interfaces-name">{slaveInterface.get('name')}</div>
                                    </div>
                                    )
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
                                                        type="button" data-interface-id="{slaveInterface.id}">Remove</button>
                                                : null
                                            }
                                        </div>
                                    </div>
                                )
                            }, this)
                            }
                        </div>

                        <div className="logical-network-box">
                            { !this.state.showHelpMessage ? _.map(assignedNetworksGrouped, function(networkGroup) {
                                var network = getFullNetwork(networkGroup[0]);

                                if(!network) {
                                    return;
                                }

                                var classes = {
                                        'logical-network-group': true,
                                        'disabled': locked || network.get('meta').unmovable
                                    },
                                    vlanRange = getVlanRange(network);

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
                                            )
                                        })
                                        }
                                    </div>
                                )
                            }, this)
                            : <div className="network-help-message">{$.t("cluster_page.nodes_tab.configure_interfaces.drag_and_drop_description")}</div>
                            }
                        </div>

                        <div className="network-box-error-message common enable-selection">&nbsp;</div>
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
                return props.model.get('networkConfiguration');
            }})
        ],
        getInitialState: function() {
            return {
                actionInProgress: false,
                loading: true
            };
        },
        dragStart: function(e, ui, networkNames, ifc) {
            if (e.type == 'sortremove') {
                ifc.get('assigned_networks').remove(this.draggedNetworks);
            } else {
                this.draggedNetworks = ifc.get('assigned_networks').filter(function (network) {
                    return _.contains(networkNames, network.get('name'));
                });
            }
        },
        dragStop: function(e, ui, ifc) {
            if(e.type == 'sortreceive') {
                ifc.get('assigned_networks').add(this.draggedNetworks);
            }
            this.draggedNetworks = null;
        },
        componentWillMount: function() {
            var cluster = this.props.model,
                nodeIds = utils.deserializeTabOptions(this.props.screenOptions[0]).nodes.split(',').map(function(id) {return parseInt(id, 10);});
            this.networkConfiguration = cluster.get('networkConfiguration');
            this.nodes = new models.Nodes(cluster.get('nodes').getByIds(nodeIds));

            $.when.apply($, this.nodes.map(function(node) {
                node.interfaces = new models.Interfaces();
                return node.interfaces.fetch({
                    url: _.result(node, 'url') + '/interfaces/default_assignment',
                    reset: true
                });
            }, this).concat(this.networkConfiguration.fetch({cache: true})))
                .done(_.bind(function() {
                    if(this.nodes.length) {
                        this.interfaces = new models.Interfaces(this.nodes.at(0).interfaces.toJSON(), {parse: true});
                        this.setState({loading: false});
                    } else {
                        // TODO: just set nonexisting node id to get here
                        utils.showErrorDialog({
                            title: $.t('cluster_page.nodes_tab.configure_interfaces.configuration_error.title'),
                            message: $.t('cluster_page.nodes_tab.configure_interfaces.configuration_error.load_defaults_warning')
                        });
                    }
                }, this));
        },
        isLocked: function() {
            var nodesAvailableForChanges = this.nodes.filter(function(node) {
                return node.get('pending_addition') || node.get('status') == 'error';
            });
            // TODO: change .length to any
            return !nodesAvailableForChanges.length && this.isLockedScreen();
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
        render: function() {
            var locked = this.isLocked(),
                bondingAvailable = true,
                nodes = [],
                interfaces = [],
                slaveInterfaceNames = [],
                returnEnabled = true;  // TODO
            if(!this.state.loading) {
                nodes = this.nodes;
                interfaces = this.interfaces;
                slaveInterfaceNames = _.pluck(_.flatten(_.filter(interfaces.pluck('slaves'))), 'name');
            }

            return (
                <div className="edit-node-networks-screen" style={{display: 'block'}}>
                    <div className={cx({'edit-node-interfaces': true, 'changes-locked': locked})}>
                        <h3>
                            {$.t('cluster_page.nodes_tab.configure_interfaces.title', {count: nodes.length, name: nodes.length && nodes.at(0).get('name')})}
                        </h3>
                    </div>

                    <div className="row">
                        {bondingAvailable ?
                            <div className="page-control-box">
                                <div className="page-control-button-placeholder">
                                    <button className="btn btn-bond">{$.t("cluster_page.nodes_tab.configure_interfaces.bond_button")}</button>
                                    <button className="btn btn-unbond">{$.t("cluster_page.nodes_tab.configure_interfaces.unbond_button")}</button>
                                </div>
                            </div>
                            : null
                        }
                        {bondingAvailable ?
                            <div className="bond-speed-warning alert hide">{$.t("cluster_page.nodes_tab.configure_interfaces.bond_speed_warning")}</div>
                            : null
                        }

                        { this.state.loading ? <controls.ProgressBar /> : null }

                        <div className="node-networks">
                            {
                                interfaces.map(_.bind(function (ifc) {
                                    if (!_.contains(slaveInterfaceNames, ifc.get('name'))) {
                                        return this.transferPropsTo(
                                                <NodeInterfaces
                                                    interface={ifc}
                                                    locked={locked}
                                                    bondingAvailable={this.bondingAvailable()}
                                                    dragStart={this.dragStart}
                                                    dragStop={this.dragStop}
                                                />
                                        );
                                    }
                                }, this))
                            }
                        </div>

                        <div className="page-control-box">
                            <div className="back-button pull-left">
                                <button className="btn btn-return" onClick={this.returnToNodeList}>{$.t("cluster_page.nodes_tab.back_to_nodes_button")}</button>
                            </div>
                            <div className="page-control-button-placeholder">
                                <button className="btn btn-defaults">{$.t("common.load_defaults_button")}</button>
                                <button className="btn btn-revert-changes">{$.t("common.cancel_changes_button")}</button>
                                <button className="btn btn-success btn-apply">{$.t("common.apply_button")}</button>
                            </div>
                        </div>
                    </div>
                </div>
            );
        }
    });

    return EditNodeInterfacesScreen;
});
