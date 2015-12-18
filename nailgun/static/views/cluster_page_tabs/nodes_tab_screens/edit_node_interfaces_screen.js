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
    'views/dialogs',
    'views/controls',
    'component_mixins',
    'react-dnd',
    'views/cluster_page_tabs/nodes_tab_screens/offloading_modes_control'
],
function($, _, Backbone, React, i18n, utils, models, dispatcher, dialogs, controls, ComponentMixins, DND, OffloadingModes) {
    'use strict';

    var ns = 'cluster_page.nodes_tab.configure_interfaces.';

    var EditNodeInterfacesScreen = React.createClass({
        mixins: [
            ComponentMixins.backboneMixin('interfaces', 'change reset update'),
            ComponentMixins.backboneMixin('cluster'),
            ComponentMixins.backboneMixin('nodes', 'change reset update'),
            ComponentMixins.unsavedChangesMixin
        ],
        statics: {
            fetchData: function(options) {
                var cluster = options.cluster,
                    nodes = utils.getNodeListFromTabOptions(options);

                if (!nodes || !nodes.areInterfacesConfigurable()) {
                    return $.Deferred().reject();
                }

                var networkConfiguration = cluster.get('networkConfiguration'),
                    networksMetadata = new models.ReleaseNetworkProperties();

                return $.when(...nodes.map(function(node) {
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
        isLocked: function() {
            return !!this.props.cluster.task({group: 'deployment', active: true}) ||
                !_.all(this.props.nodes.invoke('areInterfacesConfigurable'));
        },
        interfacesPickFromJSON: function(json) {
            // Pick certain interface fields that have influence on hasChanges.
            return _.pick(json, ['assigned_networks', 'mode', 'type', 'slaves', 'bond_properties', 'interface_properties', 'offloading_modes']);
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
            return !this.isLocked() && (!_.isEqual(this.state.initialInterfaces, this.interfacesToJSON(this.props.interfaces)) ||
                this.hasChangesInRemainingNodes());
        },
        loadDefaults: function() {
            this.setState({actionInProgress: true});
            $.when(this.props.interfaces.fetch({
                url: _.result(this.props.nodes.at(0), 'url') + '/interfaces/default_assignment', reset: true
            }, this)).done(_.bind(function() {
                this.setState({actionInProgress: false});
            }, this)).fail(_.bind(function(response) {
                var errorNS = ns + 'configuration_error.';
                utils.showErrorDialog({
                    title: i18n(errorNS + 'title'),
                    message: i18n(errorNS + 'load_defaults_warning'),
                    response: response
                });
            }, this));
        },
        revertChanges: function() {
            this.props.interfaces.reset(_.cloneDeep(this.state.initialInterfaces), {parse: true});
        },
        applyChanges: function() {
            if (!this.isSavingPossible()) return $.Deferred().reject();

            var nodes = this.props.nodes,
                interfaces = this.props.interfaces,
                bonds = interfaces.filter(function(ifc) {return ifc.isBond();}),
                bondsByName = bonds.reduce(function(result, bond) {
                        result[bond.get('name')] = bond;
                        return result;
                    }, {});

            // bonding map contains indexes of slave interfaces
            // it is needed to build the same configuration for all the nodes
            // as interface names might be different, so we use indexes
            var bondingMap = _.map(bonds, function(bond) {
                return _.map(bond.get('slaves'), function(slave) {
                    return interfaces.indexOf(interfaces.findWhere(slave));
                });
            });
            this.setState({actionInProgress: true});
            return $.when(...nodes.map(function(node) {
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
                    var updatedIfc = ifc.isBond() ? bondsByName[ifc.get('name')] : interfaces.at(index);
                    ifc.set({
                        assigned_networks: new models.InterfaceNetworks(updatedIfc.get('assigned_networks').toJSON()),
                        interface_properties: updatedIfc.get('interface_properties')
                    });
                    if (ifc.isBond()) {
                        var bondProperties = ifc.get('bond_properties');
                        ifc.set({bond_properties: _.extend(bondProperties, {type__:
                            this.getBondType() == 'linux' ? 'linux' : 'ovs'})});
                    }
                    if (ifc.get('offloading_modes')) {
                        ifc.set({
                            offloading_modes: updatedIfc.get('offloading_modes')
                        });
                    }
                }, this);

                return Backbone.sync('update', node.interfaces, {url: _.result(node, 'url') + '/interfaces'});
            }, this))
                .done(_.bind(function() {
                    this.setState({initialInterfaces: _.cloneDeep(this.interfacesToJSON(this.props.interfaces))});
                    dispatcher.trigger('networkConfigurationUpdated');
                }, this))
                .fail(function(response) {
                    var errorNS = ns + 'configuration_error.';

                    utils.showErrorDialog({
                        title: i18n(errorNS + 'title'),
                        message: i18n(errorNS + 'saving_warning'),
                        response: response
                    });
                }).always(_.bind(function() {
                    this.setState({actionInProgress: false});
                }, this));
        },
        configurationTemplateExists: function() {
            return !_.isEmpty(this.props.cluster.get('networkConfiguration').get('networking_parameters').get('configuration_template'));
        },
        bondingAvailable: function() {
            var availableBondTypes = this.getBondType();
            return !!availableBondTypes && !this.configurationTemplateExists();
        },
        getBondType: function() {
            return _.compact(_.flatten(_.map(this.props.bondingConfig.availability, function(modeAvailabilityData) {
                return _.map(modeAvailabilityData, function(condition, name) {
                    var result = utils.evaluateExpression(condition, this.props.configModels).value;
                    return result && name;
                }, this);
            }, this)))[0];
        },
        findOffloadingModesIntersection: function(set1, set2) {
            return _.map(
                _.intersection(
                    _.pluck(set1, 'name'),
                    _.pluck(set2, 'name')
                ),
                function(name) {
                    return {
                        name: name,
                        state: null,
                        sub: this.findOffloadingModesIntersection(
                            _.find(set1, {name: name}).sub,
                            _.find(set2, {name: name}).sub
                        )
                    };
                },
                this);
        },
        getIntersectedOffloadingModes: function(interfaces) {
            var offloadingModes = interfaces.map(function(ifc) {
                return ifc.get('offloading_modes') || [];
            });
            if (!offloadingModes.length) return [];

            return offloadingModes.reduce(
                (function(result, modes) {
                    return this.findOffloadingModesIntersection(result, modes);
                }).bind(this)
            );
        },
        bondInterfaces: function() {
            this.setState({actionInProgress: true});
            var interfaces = this.props.interfaces.filter(function(ifc) {
                    return ifc.get('checked') && !ifc.isBond();
                }),
                bonds = this.props.interfaces.find(function(ifc) {
                    return ifc.get('checked') && ifc.isBond();
                }),
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
                    },
                    offloading_modes: this.getIntersectedOffloadingModes(interfaces)
                });
            } else {
                // adding interfaces to existing bond
                bonds.set({
                    slaves: bonds.get('slaves').concat(_.invoke(interfaces, 'pick', 'name')),
                    offloading_modes: this.getIntersectedOffloadingModes(interfaces.concat(bonds))
                });
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
                this.removeInterfaceFromBond(bond.get('name'));
            }, this);
            this.setState({actionInProgress: false});
        },
        removeInterfaceFromBond: function(bondName, slaveInterfaceName) {
            var networks = this.props.cluster.get('networkConfiguration').get('networks'),
                bond = this.props.interfaces.find({name: bondName}),
                slaves = bond.get('slaves'),
                bondHasUnmovableNetwork = bond.get('assigned_networks').any(
                    function(interfaceNetwork) {
                        return interfaceNetwork.getFullNetwork(networks).get('meta').unmovable;
                    }
                ),
                slaveInterfaceNames = _.pluck(slaves, 'name'),
                targetInterface = bond;

            // if PXE interface is being removed - place networks there
            if (bondHasUnmovableNetwork) {
                var pxeInterface = this.props.interfaces.find(function(ifc) {
                    return ifc.get('pxe') && _.contains(slaveInterfaceNames, ifc.get('name'));
                });
                if (!slaveInterfaceName || pxeInterface && pxeInterface.get('name') == slaveInterfaceName) {
                    targetInterface = pxeInterface;
                }
            }

            // if slaveInterfaceName is set - remove it from slaves, otherwise remove all
            if (slaveInterfaceName) {
                var slavesUpdated = _.reject(slaves, {name: slaveInterfaceName}),
                    names = _.pluck(slavesUpdated, 'name'),
                    bondSlaveInterfaces = this.props.interfaces.filter(function(ifc) {
                        return _.contains(names, ifc.get('name'));
                    });

                bond.set({
                    slaves: slavesUpdated,
                    offloading_modes: this.getIntersectedOffloadingModes(bondSlaveInterfaces)
                });
            } else {
                bond.set('slaves', []);
            }

            // destroy bond if all slave interfaces have been removed
            if (!slaveInterfaceName && targetInterface === bond) {
                targetInterface = this.props.interfaces.findWhere({name: slaveInterfaceNames[0]});
            }

            // move networks if needed
            if (targetInterface !== bond) {
                var interfaceNetworks = bond.get('assigned_networks').remove(
                    bond.get('assigned_networks').models
                );
                targetInterface.get('assigned_networks').add(interfaceNetworks);
            }

            // if no slaves left - remove the bond
            if (!bond.get('slaves').length) {
                this.props.interfaces.remove(bond);
            }
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
        validateSpeedsForBonding: function(interfaces) {
            var slaveInterfaces = _.flatten(_.invoke(interfaces, 'getSlaveInterfaces'), true);
            var speeds = _.invoke(slaveInterfaces, 'get', 'current_speed');
            // warn if not all speeds are the same or there are interfaces with unknown speed
            return _.uniq(speeds).length > 1 || !_.compact(speeds).length;
        },
        isSavingPossible: function() {
            return !_.chain(this.state.interfaceErrors).values().some().value() && !this.state.actionInProgress && this.hasChanges();
        },
        getIfcProperty: function(property) {
            var {interfaces, nodes} = this.props,
                bondsCount = interfaces.filter((ifc) => ifc.isBond()).length,
                getPropertyValues = function(ifcIndex) {
                    return _.uniq(nodes.map((node) => {
                        var nodeBondsCount = node.interfaces.filter((ifc) => ifc.isBond()).length,
                            nodeInterface = node.interfaces.at(ifcIndex + nodeBondsCount);
                        if (property == 'current_speed') return utils.showBandwidth(nodeInterface.get(property));
                        return nodeInterface.get(property);
                    }));
                };
            return interfaces.map((ifc, index) => {
                if (ifc.isBond()) {
                    return _.map(ifc.get('slaves'),
                        (slave) => getPropertyValues(interfaces.indexOf(interfaces.find(slave)) - bondsCount)
                    );
                }
                return [getPropertyValues(index - bondsCount)];
            });
        },
        render: function() {
            var nodes = this.props.nodes,
                nodeNames = nodes.pluck('name'),
                interfaces = this.props.interfaces,
                locked = this.isLocked(),
                bondingAvailable = this.bondingAvailable(),
                configurationTemplateExists = this.configurationTemplateExists(),
                checkedInterfaces = interfaces.filter(function(ifc) {return ifc.get('checked') && !ifc.isBond();}),
                checkedBonds = interfaces.filter(function(ifc) {return ifc.get('checked') && ifc.isBond();}),
                creatingNewBond = checkedInterfaces.length >= 2 && !checkedBonds.length,
                addingInterfacesToExistingBond = !!checkedInterfaces.length && checkedBonds.length == 1,
                bondingPossible = creatingNewBond || addingInterfacesToExistingBond,
                unbondingPossible = !checkedInterfaces.length && !!checkedBonds.length,
                hasChanges = this.hasChanges(),
                slaveInterfaceNames = _.pluck(_.flatten(_.filter(interfaces.pluck('slaves'))), 'name'),
                loadDefaultsEnabled = !this.state.actionInProgress,
                revertChangesEnabled = !this.state.actionInProgress && hasChanges,
                invalidSpeedsForBonding = bondingPossible && this.validateSpeedsForBonding(checkedBonds.concat(checkedInterfaces)) || interfaces.any(function(ifc) {
                    return ifc.isBond() && this.validateSpeedsForBonding([ifc]);
                }, this);

            var interfaceSpeeds = this.getIfcProperty('current_speed'),
                interfaceNames = this.getIfcProperty('name');

            return (
                <div className='row'>
                    <div className='title'>
                        {i18n(ns + (locked ? 'read_only_' : '') + 'title', {count: nodes.length, name: nodeNames.join(', ')})}
                    </div>
                    {configurationTemplateExists &&
                        <div className='col-xs-12'>
                            <div className='alert alert-warning'>{i18n(ns + 'configuration_template_warning')}</div>
                        </div>
                    }
                    {bondingAvailable && !locked &&
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
                            {checkedBonds.length > 1 &&
                                <div className='alert alert-warning'>{i18n(ns + 'several_bonds_warning')}</div>
                            }
                            {invalidSpeedsForBonding &&
                                <div className='alert alert-warning'>{i18n(ns + 'bond_speed_warning')}</div>
                            }
                        </div>
                    }
                    <div className='ifc-list col-xs-12'>
                        {interfaces.map(_.bind(function(ifc, index) {
                            var ifcName = ifc.get('name');
                            if (!_.contains(slaveInterfaceNames, ifcName)) return (
                                <NodeInterfaceDropTarget {...this.props}
                                    key={'interface-' + ifcName}
                                    interface={ifc}
                                    locked={locked}
                                    bondingAvailable={bondingAvailable}
                                    configurationTemplateExists={configurationTemplateExists}
                                    errors={this.state.interfaceErrors[ifcName]}
                                    validate={this.validate}
                                    removeInterfaceFromBond={this.removeInterfaceFromBond}
                                    bondingProperties={this.props.bondingConfig.properties}
                                    bondType={this.getBondType()}
                                    interfaceSpeeds={interfaceSpeeds[index]}
                                    interfaceNames={interfaceNames[index]}
                                />
                            );
                        }, this))}
                    </div>
                    <div className='col-xs-12 page-buttons content-elements'>
                        <div className='well clearfix'>
                            <div className='btn-group'>
                                <a className='btn btn-default' href={'#cluster/' + this.props.cluster.id + '/nodes'} disabled={this.state.actionInProgress}>
                                    {i18n('cluster_page.nodes_tab.back_to_nodes_button')}
                                </a>
                            </div>
                            {!locked &&
                                <div className='btn-group pull-right'>
                                    <button className='btn btn-default btn-defaults' onClick={this.loadDefaults} disabled={!loadDefaultsEnabled}>
                                        {i18n('common.load_defaults_button')}
                                    </button>
                                    <button className='btn btn-default btn-revert-changes' onClick={this.revertChanges} disabled={!revertChangesEnabled}>
                                        {i18n('common.cancel_changes_button')}
                                    </button>
                                    <button className='btn btn-success btn-apply' onClick={this.applyChanges} disabled={!this.isSavingPossible()}>
                                        {i18n('common.apply_button')}
                                    </button>
                                </div>
                            }
                        </div>
                    </div>
                </div>
            );
        }
    });

    var NodeInterface = React.createClass({
        statics: {
            target: {
                drop: function(props, monitor) {
                    var targetInterface = props.interface;
                    var sourceInterface = props.interfaces.findWhere({name: monitor.getItem().interfaceName});
                    var network = sourceInterface.get('assigned_networks').findWhere({name: monitor.getItem().networkName});
                    sourceInterface.get('assigned_networks').remove(network);
                    targetInterface.get('assigned_networks').add(network);
                    // trigger 'change' event to update screen buttons state
                    targetInterface.trigger('change', targetInterface);
                },
                canDrop: function(props, monitor) {
                    return monitor.getItem().interfaceName != props.interface.get('name');
                }
            },
            collect: function(connect, monitor) {
                return {
                    connectDropTarget: connect.dropTarget(),
                    isOver: monitor.isOver(),
                    canDrop: monitor.canDrop()
                };
            }
        },
        mixins: [
            ComponentMixins.backboneMixin('interface'),
            ComponentMixins.backboneMixin({
                modelOrCollection: function(props) {
                    return props.interface.get('assigned_networks');
                }
            })
        ],
        propTypes: {
            bondingAvailable: React.PropTypes.bool,
            locked: React.PropTypes.bool
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
        getAvailableBondingModes: function() {
            var modes = this.props.bondingProperties[this.props.bondType].mode;
            var configModels = _.clone(this.props.configModels);
            var availableModes = [];
            var interfaces = this.props.interface.isBond() ? this.props.interface.getSlaveInterfaces() : [this.props.interface];
            _.each(interfaces, function(ifc) {
                configModels.interface = ifc;
                availableModes.push(_.reduce(modes, function(result, modeSet) {
                    if (modeSet.condition && !utils.evaluateExpression(modeSet.condition, configModels).value) return result;
                    return result.concat(modeSet.values);
                }, [], this));
            }, this);
            return _.intersection(...availableModes);
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
        componentDidUpdate: function() {
            this.props.validate();
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
        getBondingOptions: function(bondingModes, attributeName) {
            return _.map(bondingModes, function(mode) {
                return (
                    <option key={'option-' + mode} value={mode}>
                        {i18n(ns + attributeName + '.' + mode.replace('.', '_'))}
                    </option>);
            }, this);
        },
        toggleOffloading: function() {
            var interfaceProperties = this.props.interface.get('interface_properties'),
                name = 'disable_offloading';
            this.onInterfacePropertiesChange(name, !interfaceProperties[name]);
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
            var ifc = this.props.interface,
                cluster = this.props.cluster,
                locked = this.props.locked,
                availableBondingModes = ifc.isBond() ? this.getAvailableBondingModes() : [],
                networkConfiguration = cluster.get('networkConfiguration'),
                networks = networkConfiguration.get('networks'),
                networkingParameters = networkConfiguration.get('networking_parameters'),
                slaveInterfaces = ifc.getSlaveInterfaces(),
                assignedNetworks = ifc.get('assigned_networks'),
                connectionStatusClasses = function(slave) {
                    var slaveDown = slave.get('state') == 'down';
                    return {
                        'ifc-connection-status': true,
                        'ifc-online': !slaveDown,
                        'ifc-offline': slaveDown
                    };
                },
                bondProperties = ifc.get('bond_properties'),
                interfaceProperties = ifc.get('interface_properties') || null,
                offloadingModes = ifc.get('offloading_modes') || [],
                bondingPossible = this.props.bondingAvailable && !locked;

            return this.props.connectDropTarget(
                <div className='ifc-container'>
                    <div className={utils.classNames({
                        'ifc-inner-container': true,
                        nodrag: this.props.errors,
                        over: this.props.isOver && this.props.canDrop
                    })}>
                        {ifc.isBond() &&
                            <div className='bond-properties clearfix forms-box'>
                                <div className={utils.classNames({
                                    'ifc-name pull-left': true,
                                    'no-checkbox': !bondingPossible
                                })}>
                                    {bondingPossible ?
                                        <controls.Input
                                            type='checkbox'
                                            label={ifc.get('name')}
                                            onChange={this.bondingChanged}
                                            checked={ifc.get('checked')}
                                            disabled={locked}
                                        />
                                        : ifc.get('name')
                                    }
                                </div>
                                <controls.Input
                                    type='select'
                                    disabled={!bondingPossible}
                                    onChange={this.bondingModeChanged}
                                    value={this.getBondMode()}
                                    label={i18n(ns + 'bonding_mode')}
                                    children={this.getBondingOptions(availableBondingModes, 'bonding_modes')}
                                    wrapperClassName='pull-right'
                                />
                                {this.isHashPolicyNeeded() &&
                                    <controls.Input
                                        type='select'
                                        value={bondProperties.xmit_hash_policy}
                                        disabled={!bondingPossible}
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
                                        disabled={!bondingPossible}
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
                                    {!ifc.isBond() && bondingPossible ?
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
                                        return (
                                            <div key={'info-' + slaveInterface.get('name')} className='ifc-info-block clearfix'>
                                                <div className='ifc-connection pull-left'>
                                                    <div className={utils.classNames(connectionStatusClasses(slaveInterface))} />
                                                </div>
                                                <div className='ifc-info pull-left'>
                                                    {this.props.interfaceNames[index].length == 1 &&
                                                        <div>{i18n(ns + 'name')}: {this.props.interfaceNames[index]}</div>
                                                    }
                                                    {this.props.nodes.length == 1 &&
                                                        <div>{i18n(ns + 'mac')}: {slaveInterface.get('mac')}</div>
                                                    }
                                                    <div>{i18n(ns + 'speed')}: {this.props.interfaceSpeeds[index].join(', ')}</div>
                                                    {(bondingPossible && slaveInterfaces.length >= 3) &&
                                                        <button className='btn btn-link' onClick={_.partial(this.props.removeInterfaceFromBond, ifc.get('name'), slaveInterface.get('name'))}>
                                                            {i18n('common.remove_button')}
                                                        </button>
                                                    }
                                                </div>
                                            </div>
                                        );
                                    }, this)}
                                </div>
                            </div>
                            <div className='col-xs-9'>
                                {!this.props.configurationTemplateExists &&
                                    <div className='ifc-networks'>
                                        {assignedNetworks.length ?
                                            assignedNetworks.map(function(interfaceNetwork) {
                                                var network = interfaceNetwork.getFullNetwork(networks);
                                                if (!network) return;
                                                return <DraggableNetwork
                                                    key={'network-' + network.id}
                                                    {... _.pick(this.props, ['locked', 'interface'])}
                                                    networkingParameters={networkingParameters}
                                                    interfaceNetwork={interfaceNetwork}
                                                    network={network}
                                                />;
                                            }, this)
                                        :
                                            i18n(ns + 'drag_and_drop_description')
                                        }
                                    </div>
                                }
                            </div>
                        </div>

                        {interfaceProperties &&
                            <div className='ifc-properties clearfix forms-box'>
                                <controls.Input
                                    type='text'
                                    label={i18n(ns + 'mtu')}
                                    value={interfaceProperties.mtu || ''}
                                    placeholder={i18n(ns + 'mtu_placeholder')}
                                    name='mtu'
                                    onChange={this.onInterfacePropertiesChange}
                                    disabled={locked}
                                    wrapperClassName='pull-right'
                                />
                                {offloadingModes.length ?
                                    <OffloadingModes interface={ifc} disabled={locked} />
                                :
                                    <button
                                        onClick={this.toggleOffloading}
                                        disabled={locked}
                                        className='btn btn-default toggle-offloading'>
                                        {i18n(ns + (interfaceProperties.disable_offloading ? 'disable_offloading' : 'default_offloading'))}
                                    </button>
                                }
                            </div>

                        }
                    </div>
                    {this.props.errors && <div className='ifc-error'>{this.props.errors}</div>}
                </div>
            );
        }
    });
    var NodeInterfaceDropTarget = DND.DropTarget('network', NodeInterface.target, NodeInterface.collect)(NodeInterface);

    var Network = React.createClass({
        statics: {
            source: {
                beginDrag: function(props) {
                    return {
                        networkName: props.network.get('name'),
                        interfaceName: props.interface.get('name')
                    };
                },
                canDrag: function(props) {
                    return !(props.locked || props.network.get('meta').unmovable);
                }
            },
            collect: function(connect, monitor) {
                return {
                    connectDragSource: connect.dragSource(),
                    isDragging: monitor.isDragging()
                };
            }
        },
        render: function() {
            var network = this.props.network,
                interfaceNetwork = this.props.interfaceNetwork,
                networkingParameters = this.props.networkingParameters,
                classes = {
                    'network-block pull-left': true,
                    disabled: !this.constructor.source.canDrag(this.props),
                    dragging: this.props.isDragging
                },
                vlanRange = network.getVlanRange(networkingParameters);

            return this.props.connectDragSource(
                <div className={utils.classNames(classes)}>
                    <div className='network-name'>
                        {i18n('network.' + interfaceNetwork.get('name'), {defaultValue: interfaceNetwork.get('name')})}
                    </div>
                    {vlanRange &&
                        <div className='vlan-id'>
                            {i18n(ns + 'vlan_id', {count: _.uniq(vlanRange).length})}:
                            {_.uniq(vlanRange).join('-')}
                        </div>
                    }
                </div>
            );
        }
    });
    var DraggableNetwork = DND.DragSource('network', Network.source, Network.collect)(Network);

    return EditNodeInterfacesScreen;
});
