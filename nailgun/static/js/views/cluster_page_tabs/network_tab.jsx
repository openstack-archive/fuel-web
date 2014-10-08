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

        var NetworkMixin = {

        };



        var NetworkTab = React.createClass({
//            mixins: [
//                 componentMixins.pollingMixin(3)
//            ],
//            shouldDataBeFetched: function () {
//                debugger;
//                return false;
//            },
//            fetchData: function () {
//                debugger;
//            },
            getInitialState: function () {
                var cluster = this.props.model;
                return {
                    loading: true

                };
            },
            loadInitialConfiguration: function() {
                this.networkConfiguration.clear().set(new models.NetworkConfiguration(this.initialConfiguration.toJSON(), {parse: true}).attributes);
            },
            updateInitialConfiguration: function() {
                this.initialConfiguration = new models.NetworkConfiguration(this.networkConfiguration.toJSON(), {parse: true});
            },
            componentDidMount: function () {
                var cluster = this.props.model,
                    settings = cluster.get('settings');

                this.initialConfiguration = new models.NetworkConfiguration();
                this.networkConfiguration = cluster.get('networkConfiguration');

                this.networkConfiguration.on('invalid', _.bind(this.forceUpdate, this));

                $.when(settings.fetch({cache: true}), this.networkConfiguration.fetch({cache: true})).done(_.bind(function () {
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
                return this.props.model.task({group: ['deployment', 'network'], status: 'running'}) || !this.props.model.isAvailableForSettingsChanges();
            },
            render: function () {
                var cluster = this.props.model,
                    managers = {
                        FlatDHCPManager: $.t('cluster_page.network_tab.flatdhcp_manager'),
                        VlanManager: $.t('cluster_page.network_tab.vlan_manager')
                    };
                if (!this.state.loading) {
                    var networkingParameters = this.networkConfiguration.get('networking_parameters'),
                        segment_type = networkingParameters ? networkingParameters.get('segmentation_type') : null,
                        l23_provider = networkingParameters ? networkingParameters.get('net_l23_provider') : null;
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
                                                <div className='item-box'>
                                                    <controls.Input
                                                        type='radio'
                                                        label={label}
                                                        labelWrapperClassName='parameter-name'
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
                                    {this.networkConfiguration.get('networks').map(function(network) {
                                        if (network.get('meta').configurable) {
                                            return (
                                                <Network
                                                    network={network}
                                                    tab={this}
                                                 />
                                            );
                                        }
                                    }, this)}

                                </div>
                                <div className='networking-parameters'>
                                    <NetworkParameter
                                        parameters={this.networkConfiguration.get('networking_parameters')}
                                        tab={this}
                                    />
                                </div>
                            </div>
                        }

                        <hr/>
                        {!this.state.loading &&
                            <div className='row verification-control'>
                                <NetworkVerification
                                    cluster={this.props.model}
                                    networks={this.networkConfiguration.get('networks')}
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
        render: function() {
            var disabled = this.props.tab.isLocked() ? 'disabled' : '',
                networkConfig = this.props.network.get('meta');
            return (
                <div>
                    <legend className='networks'>{$.t('network.'+  this.props.network.get('name'))}</legend>
                    <div className={this.props.network.get('name')}>
                        {(networkConfig.notation == 'ip_ranges') &&
                            <div className='network-attribute ip-ranges'>
                                <div className='range-row-header'>
                                    <div>{$.t('cluster_page.network_tab.range_start')}</div>
                                    <div>{$.t('cluster_page.network_tab.range_end')}</div>
                                </div>
                                <div className='parameter-name'>{$.t('cluster_page.network_tab.network_parameters.ip_range')}</div>
                                <div className='ip-ranges-rows'></div>
                            </div>
                        }

                        <div className='network-attribute'>
                            <controls.Input
                                label={$.t('cluster_page.network_tab.network_parameters.cidr')}
                                type='text'
                                name='cidr'
                            />
                        </div>

                        <div className='network-attribute'>
                            <controls.Input
                                label={$.t('cluster_page.network_tab.network_parameters.use_vlan_tagging')}
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
                                    label={$.t('cluster_page.network_tab.network_parameters.gateway')}
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
        render: function() {
            var netManager = this.props.parameters.get('net_manager'),
                segmentation = this.props.parameters.get('segmentation_type');
            var disabled = this.props.tab.isLocked() ? 'disabled' : '';
            var idRangePrefix = segmentation == 'gre' ? 'gre_id' : 'vlan';
            return (
                <div>
                    {netManager ?
                        <div>
                            <legend className='networks'>{$.t('cluster_page.network_tab.networking_parameters.nova_configuration')}</legend>
                            <div>
                                <div className='network-attribute'>
                                    <controls.Input
                                        type='text'
                                        label={$.t('cluster_page.network_tab.networking_parameters.fixed_cidr')}
                                        name='fixed_networks_cidr'
                                    />
                                </div>
                                {(netManager == 'VlanManager') ?
                                    <div>
                                        <div className='network-attribute'>
                                            <controls.Input
                                                type='select'
                                                label={$.t('cluster_page.network_tab.networking_parameters.fixed_size')}
                                                name='fixed_network_size'
                                            />
                                        </div>
                                        <div className='network-attribute'>
                                            <controls.Input
                                                type='text'
                                                label={$.t('cluster_page.network_tab.networking_parameters.fixed_amount')}
                                                name='fixed_networks_amount'
                                            />
                                        </div>
                                        <div className='network-attribute'>
                                            <div className='range-row-header mini'>
                                                <div>{$.t('cluster_page.network_tab.range_start')}</div>
                                                <div>{$.t('cluster_page.network_tab.range_end')}</div>
                                            </div>
                                            <label className='parameter-box clearfix'>
                                                <div className='networks-sub-title parameter-name'>{$.t('cluster_page.network_tab.networking_parameters.fixed_vlan_range')}</div>
                                                <div className='range-row'>
                                                    <div className='parameter-control'>
                                                        <input type='text' className='mini range' name='fixed_networks_vlan_start' value='' />
                                                    </div>
                                                    <div className='parameter-control'>
                                                        <input type='text' className='mini' name='vlan_end' value='' disabled />
                                                    </div>
                                                    <div className='error validation-error'><span className='help-inline'></span></div>
                                                </div>
                                            </label>
                                        </div>
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
                            <div>
                                <div className='network-attribute'>
                                    <div className='range-row-header mini'>
                                        <div>{$.t('cluster_page.network_tab.range_start')}</div>
                                        <div>{$.t('cluster_page.network_tab.range_end')}</div>
                                    </div>
                                </div>

                                <div className='parameter-name'>
                                    <span>
                                        {$.t('cluster_page.network_tab.networking_parameters.' + idRangePrefix +'_range')}
                                    </span>
                                </div>
                                <div className={'range-row ' + idRangePrefix +' _range-row clearfix'}>
                                    <controls.Input
                                        type='text'
                                        name='range0'
                                        className='mini range'
                                    />
                                    <controls.Input
                                        type='text'
                                        name='range1'
                                        className='mini range'
                                    />
                                </div>
                            </div>

                            <div className='network-attribute'>
                                <controls.Input
                                    type='text'
                                    label={$.t('cluster_page.network_tab.networking_parameters.base_mac')}
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
                                        label={$.t('cluster_page.network_tab.networking_parameters.internal_cidr')}
                                    />
                                </div>
                                <div className='network-attribute'>
                                    <controls.Input
                                        type='text'
                                        label={$.t('cluster_page.network_tab.networking_parameters.internal_gateway')}
                                    />
                                </div>
                            </div>
                        </div>
                    }
                    <div>
                        <div className='network-attribute floating'>
                            <div className='range-row-header'>
                                <div>{$.t('cluster_page.network_tab.range_start')}</div>
                                <div>{$.t('cluster_page.network_tab.range_end')}</div>
                            </div>
                            <div className='parameter-name'>{$.t('cluster_page.network_tab.networking_parameters.floating_ranges')}</div>
                            <div className='floating-ranges-rows'></div>
                        </div>

                        <div className='network-attribute'>
                            <div className='parameter-name'>{$.t('cluster_page.network_tab.networking_parameters.dns_servers')}</div>
                            <div className='dns_nameservers-row range-row clearfix'>
                                <controls.Input
                                    type='text'
                                    name='range0'
                                    placeholder='127.0.0.1'
                                />
                                <controls.Input
                                    type='text'
                                    name='range1'
                                    placeholder='127.0.0.1'
                                />
                            </div>
                        </div>
                    </div>
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
              connectStatus = connectStatusLast = 'stop';
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
                                                {_.map(task.get('result'), function(node) {
                                                    var absentVlans = _.map(node.absent_vlans, function(vlan) {
                                                        return vlan || $.t('cluster_page.network_tab.untagged');
                                                    });
                                                    return (
                                                        <tr>
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