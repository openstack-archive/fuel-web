/*
 * Copyright 2014 Mirantis, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the 'License'); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an 'AS IS' BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
 **/
define(
    [
        'react',
        'models',
        'utils',
        'jsx!component_mixins',
        'jsx!views/controls'
    ],
    function (React, models, utils, componentMixins, controls) {
        'use strict';

        var NetworkRangeMixin = {
            onRangeChange: function(attribute, hasManyRanges, event) {
                var name = event.target.name,
                    newNetworkModel = this.state.network,
                    valuesToSet = [],
                    target = $(event.target),
                    rowSelector = '.range-row',
                    rowIndex = target.parents('.network-attribute').find(rowSelector).index(target.parents(rowSelector));

                if (hasManyRanges) {
                    valuesToSet =  this.state.network.get(attribute);
                    if (name == 'range0') {
                        valuesToSet[rowIndex][0] = event.currentTarget.value;
                    }
                    else if (name == 'range1') {
                         valuesToSet[rowIndex][1] = event.currentTarget.value;
                    }
                }
                else {
                    if (name == 'range0') {
                        valuesToSet = [event.currentTarget.value, this.state.network.get(attribute)[1]];
                    }
                    else if (name == 'range1') {
                        valuesToSet = [this.state.network.get(attribute)[0], event.currentTarget.value];
                    }
                }

                newNetworkModel.set(attribute, valuesToSet);
                this.setState({network: newNetworkModel});
                this.props.tab.state.networkConfiguration.trigger('change');
            },
            addRange: function(attribute, event) {
                var updatedRange = (this.state.network.get(attribute)).push(['', '']),
                    newNetworkModel = this.state.network;
                this.setState({network: newNetworkModel});
            },
            removeRange: function(attribute, event) {
                var target = $(event.target),
                    rowSelector = '.range-row',
                    newNetworkModel = this.state.network,
                    rowIndex = target.parents('.network-attribute').find(rowSelector).index(target.parents(rowSelector));

                newNetworkModel.get(attribute).splice(rowIndex, 1);

                this.setState({network: newNetworkModel});

            }
        };

        var NetworkTab = React.createClass({
            getInitialState: function () {
                var cluster = this.props.model;
                return {
                    loading: true,
                    disabled: false,
                    networkConfiguration: {},
                    errors: false
                };
            },
            loadInitialConfiguration: function() {
                this.state.networkConfiguration.clear().set(new models.NetworkConfiguration(this.initialConfiguration.toJSON(), {parse: true}).attributes);
            },
            updateInitialConfiguration: function() {
                this.initialConfiguration = new models.NetworkConfiguration(this.state.networkConfiguration.toJSON(), {parse: true});
            },
            networkConfigChanged: function() {

                this.setState({'errors': false});
                if (this.state.networkConfiguration) {
                    this.state.networkConfiguration.isValid();
                }
            },
            onInvalid: function(networkConfiguration, errors) {
                this.setState({'errors': errors});
            },
            componentDidMount: function() {
                var cluster = this.props.model,
                    settings = cluster.get('settings');

                this.initialConfiguration = new models.NetworkConfiguration();
                this.setState({networkConfiguration: cluster.get('networkConfiguration')});

                this.state.networkConfiguration.on('change', _.bind(this.networkConfigChanged, this));
                this.state.networkConfiguration.on('invalid', _.bind(this.onInvalid, this));

                $.when(settings.fetch({cache: true}), this.state.networkConfiguration.fetch({cache: true})).done(_.bind(function () {
                    this.updateInitialConfiguration();
                    this.setState({loading: false});
//                    this.configModels = {
//                        cluster: this.props.model,
//                        settings: settings,
//                        networking_parameters: this.props.model.get('networkConfiguration').get('network
//                        ing_parameters'),
//                        version: app.version,
//                        default: settings
//                    };
//                    if (_.isEmpty(parsedRestrictions)) {
//                        this.parseSettingsRestrictions();
//                    }
//                    if (_.isEmpty(roleRestrictions)) {
//                        this.parseRolesRestrictions();
//                    }
//                    this.setState({loading: false});
                }, this));

            },
            isLocked: function () {
                return this.props.model.task({group: ['deployment', 'network'], status: 'running'})
                    || !this.props.model.isAvailableForSettingsChanges()
                    || this.state.disabled;
            },
            hasChanges: function() {
                return !_.isEqual(this.initialConfiguration.toJSON(), this.state.networkConfiguration.toJSON());
            },
            managerChange: function(name, value) {
                this.networkingParameters.set({'net_manager': value});
                this.forceUpdate();
            },
            render: function () {
                var cluster = this.props.model,
                    managers = {
                        FlatDHCPManager: $.t('cluster_page.network_tab.flatdhcp_manager'),
                        VlanManager: $.t('cluster_page.network_tab.vlan_manager')
                    };
                if (!this.state.loading) {
                    this.networkingParameters = this.state.networkConfiguration.get('networking_parameters');
                    var segment_type = this.networkingParameters ? this.networkingParameters.get('segmentation_type') : null,
                        l23_provider = this.networkingParameters ? this.networkingParameters.get('net_l23_provider') : null;
                }
                return (
                    <div className={'network-settings wrapper' + (this.isLocked() ? ' changes-locked' : '')}>
                        <h3>{$.t('cluster_page.network_tab.title')}</h3>
                        {this.state.loading ?
                              <controls.ProgressBar />
                        :
                            <div>

                                {(cluster.get('net_provider') == 'nova_network') ?
                                    <div className='radio-checkbox-group'>
                                        {_.map(managers, function (label, value) {
                                            return (
                                                <div className='item-box' key={label}>
                                                    <controls.Input
                                                        type='radio'
                                                        title={label}
                                                        labelWrapperClassName='parameter-name'
                                                        disabled={this.isLocked()}
                                                        name='net-manager'
                                                        value={value}
                                                        onChange={this.managerChange}
                                                        checked={this.networkingParameters.get('net_manager') == value}
                                                    />
                                                </div>
                                            );
                                        }, this)}
                                    </div>
                                :
                                    <div>
                                        {segment_type &&
                                            <div>
                                                <span className='network-segment-type'>
                                                    {(l23_provider == 'nsx' ) ?
                                                        $.t('cluster_page.network_tab.neutron_l23_provider', {l23_provider: l23_provider.toUpperCase()})
                                                    :
                                                        $.t('cluster_page.network_tab.neutron_segmentation', {segment_type: segment_type.toUpperCase()})
                                                    }
                                                </span>
                                            </div>
                                        }

                                    </div>
                                }
                                <hr/>
                                <div className='networks-table'>
                                    {this.state.networkConfiguration.get('networks').map(function(network, index) {
                                        if (network.get('meta').configurable) {
                                            return (
                                                <Network
                                                    key={index}
                                                    network={network}
                                                    tab={this}
                                                    errors={this.state.errors.networks}
                                                 />
                                            );
                                        }
                                    }, this)}

                                </div>
                                <div className='networking-parameters'>
                                    <NetworkParameter
                                        parameters={this.state.networkConfiguration.get('networking_parameters')}
                                        tab={this}
                                        errors={this.state.errors.networking_parameters}
                                    />
                                </div>
                            </div>
                        }

                        <hr/>
                        {!this.state.loading &&
                            <div className='row verification-control'>
                                <NetworkVerification
                                    cluster={this.props.model}
                                    networks={this.state.networkConfiguration.get('networks')}
                                />
                            </div>
                        }
                        <div className='row'>
                            <div className='page-control-box'>
                                <div className='page-control-button-placeholder'>
                                    <button className='btn verify-networks-btn'>{$.t('cluster_page.network_tab.verify_networks_button')}</button>
                                    <button className='btn btn-revert-changes'>{$.t('common.cancel_changes_button')}</button>
                                    <button className='btn btn-success apply-btn'>{$.t('common.save_settings_button')}</button>
                                </div>
                            </div>
                        </div>
                    </div>
                );

            }

    });

    var Network = React.createClass({
         mixins: [
            NetworkRangeMixin
        ],
        getInitialState: function() {
            return {
                network: this.props.network
            };
        },
//        onRangeChange: function(attribute, event) {
//            var name = event.target.name,
//                newNetworkModel = this.state.network;
//            if (name == 'range0') {
//                newNetworkModel.set(attribute, [[event.currentTarget.value, this.state.network.get(attribute)[0][1]]]);
//            }
//            else if (name == 'range1') {
//                newNetworkModel.set(attribute, [[this.state.network.get(attribute)[0][0], event.currentTarget.value]]);
//            }
//            this.setState({network: newNetworkModel});
//        },
        render: function() {
            var disabled = this.props.tab.isLocked() ? 'disabled' : '',
                networkConfig = this.state.network.get('meta');
//            debugger;
            return (
                <div>
                    <legend className='networks'>{$.t('network.'+  this.props.network.get('name'))}</legend>
                    <div className={this.props.network.get('name')}>
                        {(networkConfig.notation == 'ip_ranges') &&
                            <controls.Range
                                wrapperClassName='network-attribute ip-ranges'
                                nameLabel={$.t('cluster_page.network_tab.network_parameters.ip_range')}
                                rowsClassName={'ip-ranges-rows'}
                                type='normal'
                                networkAttribute={this.state.network.get('ip_ranges')}
                                attribute='ip_ranges'
                                onChange={this.onRangeChange.bind(this, 'ip_ranges', true)}
                                addRange={this.addRange.bind(this, 'ip_ranges')}
                                removeRange={this.removeRange.bind(this, 'ip_ranges')}
                                error={this.props.errors ? _.find(this.props.errors, 'ip_ranges').ip_ranges : false}
                            />
                        }

                        <div className='network-attribute'>
                            <controls.Input
                                title={$.t('cluster_page.network_tab.network_parameters.cidr')}
                                type='text'
                                name='cidr'
                            />
                        </div>

                        <div className='network-attribute'>
                            <controls.Input
                                title={$.t('cluster_page.network_tab.network_parameters.use_vlan_tagging')}
                                type='checkbox'
                            />
                            <controls.Input
                                type='text'
                                name='vlan_start'
                            />
                        </div>

                        {networkConfig.use_gateway &&
                            <div className='network-attribute'>
                                <controls.Input
                                    title={$.t('cluster_page.network_tab.network_parameters.gateway')}
                                    type='text'
                                    name='gateway'
                                />
                            </div>
                       }

                    </div>
                </div>

            );
        }

    });

    var NetworkParameter = React.createClass({
        mixins: [
            NetworkRangeMixin
        ],
        getInitialState: function() {
            return {
                network: this.props.parameters
            };
        },
//        onRangeChange: function(attribute, event) {
//            debugger;
//            var name = event.target.name,
//                newParameterModel = this.state.network;
//            if (name == 'range0') {
//                newParameterModel.set(attribute, [event.currentTarget.value, this.state.network.get(attribute)[1]]);
//            }
//            else if (name == 'range1') {
//                newParameterModel.set(attribute, [this.state.network.get(attribute)[0], event.currentTarget.value]);
//            }
//            this.setState({parameters: newParameterModel});
//        },
        render: function() {
            var netManager = this.state.network.get('net_manager'),
                segmentation = this.state.network.get('segmentation_type'),
                disabled = this.props.tab.isLocked() ? 'disabled' : '',
                idRangePrefix = segmentation == 'gre' ? 'gre_id' : 'vlan',
                errors = this.props.errors;
            return (
                <div>
                    {netManager ?
                        <div>
                            <legend className='networks'>
                                {$.t('cluster_page.network_tab.networking_parameters.nova_configuration')}
                            </legend>
                            <div>
                                <div className='network-attribute'>
                                    <controls.Input
                                        type='text'
                                        title={$.t('cluster_page.network_tab.networking_parameters.fixed_cidr')}
                                        name='fixed_networks_cidr'
                                    />
                                </div>
                                {(netManager == 'VlanManager') ?
                                    <div>
                                        <div className='network-attribute'>
                                            <controls.Input
                                                type='select'
                                                title={$.t('cluster_page.network_tab.networking_parameters.fixed_size')}
                                                name='fixed_network_size'
                                            />
                                        </div>
                                        <div className='network-attribute'>
                                            <controls.Input
                                                type='text'
                                                title={$.t('cluster_page.network_tab.networking_parameters.fixed_amount')}
                                                name='fixed_networks_amount'
                                            />
                                        </div>
                                        <controls.Range
                                            wrapperClassName={'network-attribute'}
                                            nameLabel={$.t('cluster_page.network_tab.networking_parameters.fixed_vlan_range')}
                                            type='mini'
                                            name='fixed_networks'
                                            networkAttribute={this.state.network.get('vlan_range')}
                                            attribute='vlan_range'
                                            onChange={this.onRangeChange.bind(this, 'vlan_range', false)}
                                            error={errors ? errors.vlan_range : false}
                                        />
                                    </div>
                                :
                                    <div>
                                        <div className='network-attribute'>
                                            <div className='parameter-name'>{$.t('cluster_page.network_tab.networking_parameters.use_vlan_tagging_fixed')}</div>
                                            <div className='vlan-tagging clearfix'>
                                                <controls.Input
                                                    type='checkbox'
                                                />
                                                <controls.Input
                                                    type='text'
                                                    name='fixed_networks_vlan_start'
                                                />
                                            </div>
                                        </div>
                                    </div>
                                }
                            </div>
                        </div>
                    :
                        <div>
                            <legend className='networks'>{$.t('cluster_page.network_tab.networking_parameters.l2_configuration')}</legend>

                            <controls.Range
                                wrapperClassName='network-attribute clearfix'
                                nameLabel={$.t('cluster_page.network_tab.networking_parameters.' + idRangePrefix +'_range')}
                                type='mini'
                                networkAttribute={this.state.network.get(idRangePrefix +'_range')}
                                attribute={idRangePrefix +'_range'}
                                onChange={this.onRangeChange.bind(this, idRangePrefix +'_range', false)}
                                error={errors ? errors[idRangePrefix +'_range'] : false}
                            />

                            <div className='network-attribute'>
                                <controls.Input
                                    type='text'
                                    title={$.t('cluster_page.network_tab.networking_parameters.base_mac')}
                                    name='base_mac'
                                />
                            </div>

                            <div>
                                <legend className='networks'>{$.t('cluster_page.network_tab.networking_parameters.l3_configuration')}</legend>
                            </div>
                            <div>
                                <div className='network-attribute'>
                                    <controls.Input
                                        type='text'
                                        title={$.t('cluster_page.network_tab.networking_parameters.internal_cidr')}
                                    />
                                </div>
                                <div className='network-attribute'>
                                    <controls.Input
                                        type='text'
                                        title={$.t('cluster_page.network_tab.networking_parameters.internal_gateway')}
                                    />
                                </div>
                            </div>
                        </div>
                    }

                    <controls.Range
                        type='normal'
                        wrapperClassName='network-attribute floating'
                        nameLabel={$.t('cluster_page.network_tab.networking_parameters.floating_ranges')}
                        rowsClassName='floating-ranges-rows'
                        networkAttribute={this.state.network.get('floating_ranges')}
                        attribute='floating_ranges'
                        onChange={this.onRangeChange.bind(this, 'floating_ranges', true)}
                        addRange={this.addRange.bind(this, 'floating_ranges')}
                        removeRange={this.removeRange.bind(this, 'floating_ranges')}
                        error={errors ? errors.floating_ranges : false}
                    />

                    <controls.Range
                        type='normal'
                        wrapperClassName='network-attribute'
                        nameLabel={$.t('cluster_page.network_tab.networking_parameters.dns_servers')}
                        rowsClassName='dns_nameservers-row'
                        networkAttribute={[this.state.network.get('dns_nameservers')]}
                        attribute={'dns_nameservers'}
                        onChange={this.onRangeChange.bind(this, 'dns_nameservers', false)}
                        noLabel={true}
                        noControls={true}
                        error={errors ? errors.dns_nameservers : false}
                    />

                </div>
            );
        }
    });

    var NetworkVerification = React.createClass({
        render: function() {
            var task = this.props.cluster.task({group: 'network'}),
                connectStatus = 'success',
                connectStatusLast = 'success';
            if (!task || (task && task.match({status: 'ready'}))) {
                connectStatus = connectStatusLast = 'stop'
            } else if (task && task.match({status: 'error'})) {
                connectStatus = connectStatusLast = 'error';
                connectStatus = task.match({name: 'verify_networks'}) && !task.get('result').length ? 'error' : 'success';
            }
            return (
                <div>
                    { this.props.networks ?
                        <div className='page-control-box'>

                            <div className='verification-box'>
                                <div className='verification-network-placeholder'>
                                    <div className='router-box'>
                                        <div className='verification-router'></div>
                                    </div>
                                    <div className='animation-box'>
                                        <div className={'connect-1-' + connectStatus}></div>
                                        <div className={'connect-2-' + connectStatusLast}></div>
                                        <div className={'connect-3-' + connectStatusLast}></div>
                                    </div>
                                    <div className='nodex-box'>
                                        <div className='verification-node-1'></div>
                                        <div className='verification-node-2'></div>
                                        <div className='verification-node-3'></div>
                                    </div>
                                </div>
                            </div>

                            <div className='verification-text-placeholder'>
                                <li>
                                    <strong>{$.t('cluster_page.network_tab.verify_networks.step_0')}</strong>
                                </li>
                                <li>{$.t('cluster_page.network_tab.verify_networks.step_1')}</li>
                                <li>{$.t('cluster_page.network_tab.verify_networks.step_2')}</li>
                                <li>{$.t('cluster_page.network_tab.verify_networks.step_3')}</li>
                                <li>{$.t('cluster_page.network_tab.verify_networks.step_4')}</li>
                            </div>

                            {(task && task.match({name: 'verify_networks', status: 'ready'})) ?
                                <div className='alert alert-success enable-selection'>
                                    {$.t('cluster_page.network_tab.verify_networks.success_alert')}
                                </div>
                            : (task && task.match({status: 'error'})) &&
                                <div className='alert alert-error enable-selection'>
                                    <span>
                                        {$.t('cluster_page.network_tab.verify_networks.fail_alert')}
                                    </span>
                                    <br/>
                                    { task.escape('message').replace(/\n/g, '<br/>') }
                                </div>
                                (task.match({name: 'verify_networks'}) && task.get('result').length) &&
                                    <div className='verification-result-table'>
                                        <table className='table table-condensed enable-selection'>
                                            <thead>
                                                <tr>
                                                    <th>
                                                        {$.t('cluster_page.network_tab.verify_networks.node_name')}
                                                    </th>
                                                    <th>
                                                        {$.t('cluster_page.network_tab.verify_networks.node_mac_address')}
                                                    </th>
                                                    <th>
                                                        {$.t('cluster_page.network_tab.verify_networks.node_interface')}
                                                    </th>
                                                    <th>
                                                        {$.t('cluster_page.network_tab.verify_networks.expected_vlan')}
                                                    </th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {_.map(task.get('result'), function(node, index) {
                                                    var absentVlans = _.map(node.absent_vlans, function(vlan) {
                                                        return vlan || $.t('cluster_page.network_tab.untagged');
                                                    });
                                                    return (
                                                        <tr key={index}>
                                                            <td>
                                                                {node.name ? node.name : 'N/A'}
                                                            </td>
                                                            <td>
                                                                {node.mac ? node.mac : 'N/A' }
                                                            </td>
                                                            <td>
                                                                {node.interface}
                                                            </td>
                                                            <td>
                                                                {absentVlans}
                                                            </td>
                                                            </tr>
                                                    );
                                                })}
                                            </tbody>
                                        </table>
                                    </div>

                            }
                        </div>
                    :
                        <div>&nbsp;</div>
                    }
                </div>
            );
        }
    });


    return NetworkTab;
});
