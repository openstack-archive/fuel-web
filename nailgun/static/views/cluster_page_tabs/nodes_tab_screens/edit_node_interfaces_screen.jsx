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
    'dispatcher',
    'jsx!views/dialogs',
    'jsx!views/controls',
    'jsx!component_mixins',
    'jquery-ui/sortable'
],
function($, _, Backbone, React, i18n, utils, models, dispatcher, dialogs, controls, ComponentMixins) {
    'use strict';

    var ScreenMixin, EditNodeInterfacesScreen, NodeInterface;

    ScreenMixin = {
        goToNodeList: function() {
            app.navigate('#cluster/' + this.props.cluster.get('id') + '/nodes', {trigger: true});
        },
        isLockedScreen: function() {
            var nodesAvailableForChanges = this.props.nodes.filter(function(node) {
                return node.get('pending_addition') || node.get('status') == 'error';
            });
            return !nodesAvailableForChanges.length ||
                this.props.cluster && !!this.props.cluster.tasks({group: 'deployment', status: 'running'}).length;
        },
        returnToNodeList: function() {
            if (this.hasChanges()) {
                dialogs.DiscardSettingsChangesDialog.show({cb: _.bind(this.goToNodeList, this)});
            } else {
                this.goToNodeList();
            }
        }
    };

    EditNodeInterfacesScreen = React.createClass({
        mixins: [
            ScreenMixin,
            ComponentMixins.backboneMixin('interfaces', 'change:checked change:slaves change:bond_properties change:interface_properties reset sync'),
            ComponentMixins.backboneMixin('cluster', 'change:status change:networkConfiguration change:nodes sync'),
            ComponentMixins.backboneMixin('nodes', 'change sync')
        ],
        statics: {
            fetchData: function(options) {
                var cluster = options.cluster,
                    nodeIds = utils.deserializeTabOptions(options.screenOptions[0]).nodes.split(',').map(function(id) {return parseInt(id, 10);}),
                    nodeLoadingErrorNS = 'cluster_page.nodes_tab.configure_interfaces.node_loading_error.',
                    nodes,
                    networkConfiguration,
                    networksMetadata = new models.ReleaseNetworkProperties();

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
                }, this).concat([
                    networkConfiguration.fetch({cache: true}),
                    networksMetadata.fetch({
                        url: '/api/releases/' + cluster.get('release_id') + '/networks'
                    })]))
                    .then(_.bind(function() {
                        var interfaces = new models.Interfaces();
                        interfaces.set(_.cloneDeep(nodes.at(0).interfaces.toJSON()), {parse: true});
                        return {
                            interfaces: interfaces,
                            nodes: nodes,
                            bondingConfig: networksMetadata.get('bonding'),
                            configModels: {
                                version: app.version,
                                cluster: cluster,
                                settings: cluster.get('settings')
                            }
                        };
                    }, this));
            }
        },
        getInitialState: function() {
            return {
                actionInProgress: false,
                interfaceErrors: {}
            };
        },
        componentWillMount: function() {
            this.setState({initialInterfaces: _.cloneDeep(this.interfacesToJSON(this.props.interfaces))});
        },
        componentDidMount: function() {
            this.validate();
        },
        getDraggedNetworks: function() {
            return this.draggedNetworks || null;
        },
        setDraggedNetworks: function(networks) {
            this.draggedNetworks = networks;
        },
        interfacesPickFromJSON: function(json) {
            // Pick certain interface fields that have influence on hasChanges.
            return _.pick(json, ['assigned_networks', 'mode', 'type', 'slaves', 'bond_properties', 'interface_properties']);
        },
        interfacesToJSON: function(interfaces, remainingNodesMode) {
            // Sometimes 'state' is sent from the API and sometimes not
            // It's better to just unify all inputs to the one without state.
            var picker = remainingNodesMode ? this.interfacesPickFromJSON : function(json) { return _.omit(json, 'state'); };

            return interfaces.map(function(ifc) {
                return picker(ifc.toJSON());
            });
        },
        hasChangesInRemainingNodes: function() {
            var initialInterfacesOmitted = _.map(this.state.initialInterfaces, this.interfacesPickFromJSON);

            return _.any(this.props.nodes.slice(1), _.bind(function(node) {
                return !_.isEqual(initialInterfacesOmitted, this.interfacesToJSON(node.interfaces, true));
            }, this));
        },
        hasChanges: function() {
            return !_.isEqual(this.state.initialInterfaces, this.interfacesToJSON(this.props.interfaces)) ||
                this.hasChangesInRemainingNodes();
        },
        loadDefaults: function() {
            this.setState({actionInProgress: true});
            $.when(this.props.interfaces.fetch({
                url: _.result(this.props.nodes.at(0), 'url') + '/interfaces/default_assignment', reset: true
            }, this)).done(_.bind(function() {
                this.setState({actionInProgress: false});
            }, this)).fail(_.bind(function(response) {
                var errorNS = 'cluster_page.nodes_tab.configure_interfaces.configuration_error.';

                utils.showErrorDialog({
                    title: i18n(errorNS + 'title'),
                    message: i18n(errorNS + 'load_defaults_warning'),
                    response: response
                });
                this.goToNodeList();
            }, this));
        },
        revertChanges: function() {
            this.props.interfaces.reset(_.cloneDeep(this.state.initialInterfaces), {parse: true});
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

                // Assigning networks according to user choice and interface properties
                node.interfaces.each(function(ifc, index) {
                    ifc.set({
                        assigned_networks: new models.InterfaceNetworks(interfaces.at(index).get('assigned_networks').toJSON()),
                        interface_properties: interfaces.at(index).get('interface_properties')
                    });
                    if (ifc.isBond()) {
                        var bondProperties = ifc.get('bond_properties');
                        ifc.set({bond_properties: _.extend(bondProperties, {type__:
                            this.getBondType() == 'linux' ? 'linux' : 'ovs'})});
                    }
                }, this);

                return Backbone.sync('update', node.interfaces, {url: _.result(node, 'url') + '/interfaces'});
            }, this))
                .done(_.bind(function() {
                    this.setState({initialInterfaces: _.cloneDeep(this.interfacesToJSON(this.props.interfaces))});
                    dispatcher.trigger('networkConfigurationUpdated');
                }, this))
                .fail(function(response) {
                    var errorNS = 'cluster_page.nodes_tab.configure_interfaces.configuration_error.';

                    utils.showErrorDialog({
                        title: i18n(errorNS + 'title'),
                        message: i18n(errorNS + 'saving_warning'),
                        response: response
                    });
                }).always(_.bind(function() {
                    this.setState({actionInProgress: false});
                }, this));
        },
        isLocked: function() {
            var hasLockedNodes = this.props.nodes.any(function(node) {
                return !node.get('pending_addition') || _.contains(['ready', 'error'], node.get('status'));
            });
            return hasLockedNodes || this.isLockedScreen();
        },
        bondingAvailable: function() {
            var availableBondTypes = this.getBondType();
            return !this.isLocked() && !!availableBondTypes;
        },
        getBondType: function() {
            return _.compact(_.flatten(_.map(this.props.bondingConfig.availability, function(modeAvailabilityData) {
                return _.map(modeAvailabilityData, function(condition, name) {
                    var result = utils.evaluateExpression(condition, this.props.configModels).value;
                    return result && name;
                }, this);
            }, this)))[0];
        },
        bondInterfaces: function() {
            this.setState({actionInProgress: true});
            var interfaces = this.props.interfaces.filter(function(ifc) {return ifc.get('checked') && !ifc.isBond();}),
                bonds = this.props.interfaces.find(function(ifc) {return ifc.get('checked') && ifc.isBond();}),
                bondingProperties = this.props.bondingConfig.properties;

            if (!bonds) {
                // if no bond selected - create new one
                var bondMode = _.flatten(_.pluck(bondingProperties[this.getBondType()].mode, 'values'))[0];
                bonds = new models.Interface({
                    type: 'bond',
                    name: this.props.interfaces.generateBondName(this.getBondType() == 'linux' ? 'bond' : 'ovs-bond'),
                    mode: bondMode,
                    assigned_networks: new models.InterfaceNetworks(),
                    slaves: _.invoke(interfaces, 'pick', 'name'),
                    bond_properties: {
                        mode: bondMode
                    },
                    interface_properties: {
                        mtu: null,
                        disable_offloading: true
                    }
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
        validateSpeedsForBonding: function(interfaces) {
            var slaveInterfaces = _.flatten(_.invoke(interfaces, 'getSlaveInterfaces'), true);
            var speeds = _.invoke(slaveInterfaces, 'get', 'current_speed');
            // warn if not all speeds are the same or there are interfaces with unknown speed
            return _.uniq(speeds).length > 1 || !_.compact(speeds).length;
        },
        render: function() {
            var ns = 'cluster_page.nodes_tab.configure_interfaces.',
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
                loadDefaultsEnabled = !this.state.actionInProgress && !locked,
                revertChangesEnabled = !this.state.actionInProgress && hasChanges,
                applyEnabled = !hasErrors && !this.state.actionInProgress && hasChanges,
                invalidSpeedsForBonding = bondingPossible && this.validateSpeedsForBonding(checkedBonds.concat(checkedInterfaces)) || interfaces.any(function(ifc) {
                    return ifc.isBond() && this.validateSpeedsForBonding([ifc]);
                }, this);

            // calculate interfaces speed
            var getIfcSpeed = function(index) {
                    return _.unique(nodes.map(function(node) {
                        return utils.showBandwidth(node.interfaces.at(index).get('current_speed'));
                    }));
                },
                interfaceSpeeds = interfaces.map(function(ifc, index) {
                    if (!ifc.isBond()) return [getIfcSpeed(index)];
                    return _.map(ifc.get('slaves'), function(slave) {
                        return getIfcSpeed(interfaces.indexOf(interfaces.findWhere(slave)));
                    });
                });

            return (
                <div className='row'>
                    <div className='title'>
                        {i18n(ns + 'title', {count: nodes.length, name: nodeNames.join(', ')})}
                    </div>
                    {bondingAvailable &&
                        <div className='col-xs-12'>
                            <div className='page-buttons'>
                                <div className='well clearfix'>
                                    <div className='btn-group pull-right'>
                                        <button className='btn btn-default btn-bond' onClick={this.bondInterfaces} disabled={!bondingPossible}>
                                            {i18n(ns + 'bond_button')}
                                        </button>
                                        <button className='btn btn-default btn-unbond' onClick={this.unbondInterfaces} disabled={!unbondingPossible}>
                                            {i18n(ns + 'unbond_button')}
                                        </button>
                                    </div>
                                </div>
                            </div>
                            {invalidSpeedsForBonding &&
                                <div className='alert alert-warning'>{i18n(ns + 'bond_speed_warning')}</div>
                            }
                        </div>
                    }
                    <div className='ifc-list col-xs-12'>
                        {interfaces.map(_.bind(function(ifc, index) {
                            var ifcName = ifc.get('name');
                            if (!_.contains(slaveInterfaceNames, ifcName)) return (
                                <NodeInterface {...this.props}
                                    key={'interface-' + ifcName}
                                    interface={ifc}
                                    locked={locked}
                                    bondingAvailable={bondingAvailable}
                                    getDraggedNetworks={this.getDraggedNetworks}
                                    setDraggedNetworks={this.setDraggedNetworks}
                                    errors={this.state.interfaceErrors[ifcName]}
                                    validate={this.validate}
                                    refresh={this.refresh}
                                    bondingProperties={this.props.bondingConfig.properties}
                                    bondType={this.getBondType()}
                                    interfaceSpeeds={interfaceSpeeds[index]}
                                />
                            );
                        }, this))}
                    </div>
                    <div className='col-xs-12 page-buttons'>
                        <div className='well clearfix'>
                            <div className='btn-group'>
                                <button className='btn btn-default btn-return' onClick={this.returnToNodeList} disabled={!returnEnabled}>
                                    {i18n('cluster_page.nodes_tab.back_to_nodes_button')}
                                </button>
                            </div>
                            <div className='btn-group pull-right'>
                                <button className='btn btn-default btn-defaults' onClick={this.loadDefaults} disabled={!loadDefaultsEnabled}>
                                    {i18n('common.load_defaults_button')}
                                </button>
                                <button className='btn btn-default btn-revert-changes' onClick={this.revertChanges} disabled={!revertChangesEnabled}>
                                    {i18n('common.cancel_changes_button')}
                                </button>
                                <button className='btn btn-success btn-apply' onClick={this.applyChanges} disabled={!applyEnabled}>
                                    {i18n('common.apply_button')}
                                </button>
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
            ComponentMixins.backboneMixin('interface', 'change:checked change:mode change:bond_properties change:interface_properties'),
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
        isLacpRateAvailable: function() {
            return _.contains(this.getBondPropertyValues('lacp_rate', 'for_modes'), this.getBondMode());
        },
        isHashPolicyNeeded: function() {
            return _.contains(this.getBondPropertyValues('xmit_hash_policy', 'for_modes'), this.getBondMode());
        },
        getBondMode: function() {
            var ifc = this.props.interface;
            return ifc.get('mode') || (ifc.get('bond_properties') || {}).mode;
        },
        getAvailableModes: function() {
            var modes = this.props.bondingProperties[this.props.bondType].mode;
            return _.reduce(modes, function(result, modeSet) {
                if (modeSet.condition && !utils.evaluateExpression(modeSet.condition, this.props.configModels).value) return result;
                return result.concat(modeSet.values);
            }, [], this);
        },
        getBondPropertyValues: function(propertyName, value) {
            var bondType = this.props.bondType;
            return _.flatten(_.pluck(this.props.bondingProperties[bondType][propertyName], value));
        },
        updateBondProperties: function(options) {
            var bondProperties = _.cloneDeep(this.props.interface.get('bond_properties')) || {};
            bondProperties = _.extend(bondProperties, options);
            if (!this.isHashPolicyNeeded()) bondProperties = _.omit(bondProperties, 'xmit_hash_policy');
            if (!this.isLacpRateAvailable()) bondProperties = _.omit(bondProperties, 'lacp_rate');
            this.props.interface.set('bond_properties', bondProperties);
        },
        onModelChange: function() {
            this.props.refresh();
        },
        componentDidMount: function() {
            $(this.refs.networks.getDOMNode()).sortable({
                connectWith: '.ifc-networks',
                items: '.network-group-block:not(.disabled)',
                containment: $('.ifc-list'),
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
            var networkNames = $(ui.item).find('.network-block').map(function(index, el) {
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
                $(this.refs.networks.getDOMNode()).sortable('cancel');
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
                    $(this.refs.networks.getDOMNode()).sortable('cancel');
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
            this.updateBondProperties({mode: value});
            if (this.isHashPolicyNeeded()) {
                this.updateBondProperties({xmit_hash_policy: this.getBondPropertyValues('xmit_hash_policy', 'values')[0]});
            }
            if (this.isLacpRateAvailable()) {
                this.updateBondProperties({lacp_rate: this.getBondPropertyValues('lacp_rate', 'values')[0]});
            }
        },
        onPolicyChange: function(name, value) {
            this.updateBondProperties({xmit_hash_policy: value});
        },
        onLacpChange: function(name, value) {
            this.updateBondProperties({lacp_rate: value});
        },
        bondingRemoveInterface: function(slaveName) {
            var slaves = _.reject(this.props.interface.get('slaves'), {name: slaveName});
            this.props.interface.set('slaves', slaves);
        },
        getBondingOptions: function(bondingModes, attributeName) {
            return _.map(bondingModes, function(mode) {
                return (
                    <option key={'option-' + mode} value={mode}>
                        {i18n('cluster_page.nodes_tab.configure_interfaces.' + attributeName + '.' + mode.replace('.', '_'))}
                    </option>);
            }, this);
        },
        onInterfacePropertiesChange: function(name, value) {
            function convertToNullIfNaN(value) {
                var convertedValue = parseInt(value, 10);
                return _.isNaN(convertedValue) ? null : convertedValue;
            }
            if (name == 'mtu') {
                value = convertToNullIfNaN(value);
            }
            var interfaceProperties = _.cloneDeep(this.props.interface.get('interface_properties') || {});
            interfaceProperties[name] = value;
            this.props.interface.set('interface_properties', interfaceProperties);
        },
        render: function() {
            var ns = 'cluster_page.nodes_tab.configure_interfaces.',
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
                connectionStatusClasses = function(slave) {
                    var slaveDown = slave.get('state') == 'down';
                    return {
                        'ifc-connection-status': true,
                        'ifc-online': !slaveDown,
                        'ifc-offline': slaveDown
                    };
                },
                assignedNetworksGrouped = [],
                networksToAdd = [],
                bondProperties = ifc.get('bond_properties'),
                interfaceProperties = ifc.get('interface_properties') || null;

            assignedNetworks.each(function(interfaceNetwork) {
                if (interfaceNetwork.getFullNetwork(networks).get('name') != 'floating') {
                    if (networksToAdd.length) assignedNetworksGrouped.push(networksToAdd);
                    networksToAdd = [];
                }
                networksToAdd.push(interfaceNetwork);
            });
            if (networksToAdd.length) assignedNetworksGrouped.push(networksToAdd);

            return (
                <div className='ifc-container'>
                    <div className={utils.classNames({'ifc-inner-container': true, nodrag: this.props.errors})}>
                        {ifc.isBond() &&
                            <div className='bond-properties clearfix forms-box'>
                                <div className='ifc-name pull-left'>
                                    {this.props.bondingAvailable ?
                                        <controls.Input
                                            type='checkbox'
                                            label={ifc.get('name')}
                                            onChange={this.bondingChanged}
                                            checked={ifc.get('checked')} />
                                        : ifc.get('name')
                                    }
                                </div>
                                <controls.Input
                                    type='select'
                                    disabled={!this.props.bondingAvailable}
                                    onChange={this.bondingModeChanged}
                                    value={this.getBondMode()}
                                    label={i18n(ns + 'bonding_mode')}
                                    children={this.getBondingOptions(this.getAvailableModes(), 'bonding_modes')}
                                    wrapperClassName='pull-right'
                                />
                                {this.isHashPolicyNeeded() &&
                                    <controls.Input
                                        type='select'
                                        value={bondProperties.xmit_hash_policy}
                                        disabled={!this.props.bondingAvailable}
                                        onChange={this.onPolicyChange}
                                        label={i18n(ns + 'bonding_policy')}
                                        children={this.getBondingOptions(this.getBondPropertyValues('xmit_hash_policy', 'values'), 'hash_policy')}
                                        wrapperClassName='pull-right'
                                    />
                                }
                                {this.isLacpRateAvailable() &&
                                    <controls.Input
                                        type='select'
                                        value={bondProperties.lacp_rate}
                                        disabled={!this.props.bondingAvailable}
                                        onChange={this.onLacpChange}
                                        label={i18n(ns + 'lacp_rate')}
                                        children={this.getBondingOptions(this.getBondPropertyValues('lacp_rate', 'values'), 'lacp_rates')}
                                        wrapperClassName='pull-right'
                                    />
                                }
                            </div>
                        }

                        <div className='networks-block row'>
                            <div className='col-xs-3'>
                                <div className='ifc-checkbox pull-left'>
                                    {!ifc.isBond() && bondable ?
                                        <controls.Input
                                            type='checkbox'
                                            onChange={this.bondingChanged}
                                            checked={ifc.get('checked')}
                                        />
                                    :
                                        <span>&nbsp;</span>
                                    }
                                </div>
                                <div className='pull-left'>
                                    {_.map(slaveInterfaces, function(slaveInterface, index) {
                                        var ifcName = slaveInterface.get('name');
                                        return (
                                            <div key={'info-' + ifcName} className='ifc-info-block clearfix'>
                                                <div className='ifc-connection pull-left'>
                                                    <div className={utils.classNames(connectionStatusClasses(slaveInterface))} />
                                                    <div className='ifc-name'>{ifcName}</div>
                                                </div>
                                                <div className='ifc-info pull-left'>
                                                    {this.props.nodes.length == 1 &&
                                                        <div>{i18n(ns + 'mac')}: {slaveInterface.get('mac')}</div>
                                                    }
                                                    <div>
                                                        {i18n(ns + 'speed')}: {this.props.interfaceSpeeds[index].join(', ')}
                                                    </div>
                                                    {(this.props.bondingAvailable && slaveInterfaces.length >= 3) &&
                                                        <button className='btn btn-link' onClick={_.partial(this.bondingRemoveInterface, ifcName)}>
                                                            {i18n('common.remove_button')}
                                                        </button>
                                                    }
                                                </div>
                                            </div>
                                        );
                                    }, this)}
                                </div>
                            </div>
                            <div className='ifc-networks col-xs-9' ref='networks'>
                                {assignedNetworks.length ?
                                    _.map(assignedNetworksGrouped, function(networkGroup) {
                                        var network = networkGroup[0].getFullNetwork(networks);
                                        if (!network) return;

                                        var classes = {
                                                'network-group-block pull-left': true,
                                                disabled: locked || network.get('meta').unmovable
                                            },
                                            vlanRange = network.getVlanRange(networkingParameters);
                                        return (
                                            <div key={'network-group-' + network.id} className={utils.classNames(classes)}>
                                                {_.map(networkGroup, function(interfaceNetwork) {
                                                    var networkName = interfaceNetwork.get('name');
                                                    return (
                                                        <div key={'network-' + networkName} className='network-block pull-left' data-name={networkName}>
                                                            <div className='network-name'>
                                                                {i18n('network.' + networkName, {defaultValue: networkName})}
                                                            </div>
                                                            {vlanRange &&
                                                                <div className='vlan-id'>
                                                                    {i18n(ns + 'vlan_id', {count: _.uniq(vlanRange).length})}:
                                                                    {_.uniq(vlanRange).join('-')}
                                                                </div>
                                                            }
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        );
                                    }, this)
                                :
                                    <div className='no-networks-message'>{i18n(ns + 'drag_and_drop_description')}</div>
                                }
                            </div>
                        </div>

                        {interfaceProperties &&
                            <div className='ifc-properties clearfix forms-box'>
                                <controls.Input
                                    type='checkbox'
                                    label={i18n(ns + 'disable_offloading')}
                                    checked={interfaceProperties.disable_offloading}
                                    name='disable_offloading'
                                    onChange={this.onInterfacePropertiesChange}
                                    disabled={locked}
                                    wrapperClassName='pull-right'
                                />
                                <controls.Input
                                    type='text'
                                    label={i18n(ns + 'mtu')}
                                    value={interfaceProperties.mtu || ''}
                                    name='mtu'
                                    onChange={this.onInterfacePropertiesChange}
                                    disabled={locked}
                                    wrapperClassName='pull-right'
                                />
                            </div>
                        }

                    </div>
                    {this.props.errors && <div className='ifc-error'>{this.props.errors}</div>}
                </div>
            );
        }
    });

    return EditNodeInterfacesScreen;
});
