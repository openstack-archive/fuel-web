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
    function(React, models, utils, componentMixins, controls) {
        'use strict';

        var NetworkRangeMixin = {
            onRangeChange: function(attribute, hasManyRanges, event) {
                var name = event.target.name,
                    newNetworkModel = this.props.network,
                    valuesToSet = [],
                    target = $(event.target),
                    rowSelector = '.range-row',
                    rowIndex = target.parents('.network-attribute').find(rowSelector).index(target.parents(rowSelector));

                if (hasManyRanges) {
                    valuesToSet =  this.props.network.get(attribute);

                    if (name == 'range0') {
                        valuesToSet[rowIndex][0] = event.currentTarget.value;
                    } else if (name == 'range1') {
                        valuesToSet[rowIndex][1] = event.currentTarget.value;
                    }
                } else {
                    if (name == 'range0') {
                        valuesToSet = [event.currentTarget.value, this.props.network.get(attribute)[1]];
                    } else if (name == 'range1') {
                        valuesToSet = [this.props.network.get(attribute)[0], event.currentTarget.value];
                    }
                }
                newNetworkModel.set(attribute, valuesToSet);
                this.updateTabState(newNetworkModel);
            },

            addRange: function(attribute, event) {
                var updatedRange = (this.props.network.get(attribute)).push(['', '']),
                    newNetworkModel = this.props.network;
                this.updateTabState(newNetworkModel);
            },

            removeRange: function(attribute, event) {
                var target = $(event.target),
                    rowSelector = '.range-row',
                    newNetworkModel = this.props.network,
                    newNetworkConfiguration = this.props.tab.state.networkConfiguration,
                    rowIndex = target.parents('.network-attribute').find(rowSelector).index(target.parents(rowSelector));

                newNetworkModel.get(attribute).splice(rowIndex, 1);
                this.updateTabState(newNetworkModel);
            }
        };

        var NetworkMixin = {

            updateTabState: function(model) {
                var newNetworkConfiguration = this.props.tab.state.networkConfiguration,
                    currentNetwork = newNetworkConfiguration.get('networks').find(this.props.network),
                    isParameter = _.isUndefined(currentNetwork);
                _.extend(isParameter ? newNetworkConfiguration.get('networking_parameters').toJSON() : currentNetwork.toJSON(), model.toJSON());
                this.props.tab.setState({networkConfiguration: newNetworkConfiguration});
                this.props.tab.state.networkConfiguration.trigger('change');
            },

            onInputChange: function(name, value) {
                var newNetworkModel = this.props.network;
                if (_.contains(name, 'vlan') || _.contains(name, 'amount')) {
                    var numberValue = _.parseInt(value);
                    newNetworkModel.set(name, _.isNaN(numberValue) ? '' : numberValue);
                } else {
                    newNetworkModel.set(name, value);
                }
                this.updateTabState(newNetworkModel);
            },

            onTaggingChange: function(attribute, value) {
                var newNetworkModel = this.props.network;
                newNetworkModel.set(attribute, value ? '' : null);
                this.updateTabState(newNetworkModel);
            },

            renderNetworkInput: function(config) {
                return (
                    <div className='network-attribute'>
                        <controls.Input
                            title={config.title}
                            type='text'
                            name={config.name}
                            value={this.props.network.get(config.name)}
                            onChange={this.onInputChange}
                            error={config.isParameter ? this.getParameterError(config.name) : this.getNetworkError(config.name)}
                            disabled={this.props.tab.isLocked()}
                        />
                    </div>
                );
            },

            getNetworkError: function(attribute) {
                return (this.props.errors && _.find(this.props.errors, attribute)) ?
                    _.find(this.props.errors, attribute)[attribute] : undefined;
            },

            getParameterError: function(attribute) {
                return (this.props.errors && this.props.errors[attribute]) ? this.props.errors[attribute] : undefined;
            }
        };

        var NetworkTab = React.createClass({
            mixins: [
                React.BackboneMixin('model'),
                React.BackboneMixin({modelOrCollection: function(props) {
                    return props.model.get('tasks');
                }}),
                React.BackboneMixin({modelOrCollection: function(props) {
                    return props.model.task({group: 'network', status: 'running'});
                }}),
                componentMixins.pollingMixin(3)
            ],

            shouldDataBeFetched: function() {
                return !!this.props.model.task('verify_networks', 'running');
            },

            fetchData: function() {
                var task = this.props.model.task('verify_networks', 'running');
                this.setState({disabled: false});
                return task.fetch();
            },

            getInitialState: function() {
                return {
                    loading: true,
                    disabled: false,
                    networkConfiguration: {},
                    errors: false
                };
            },

            loadInitialConfiguration: function() {
                this.replaceState({networkConfiguration:
                    new models.NetworkConfiguration(this.initialConfiguration.toJSON(), {parse: true})});
                this.state.networkConfiguration.trigger('change');
            },

            updateInitialConfiguration: function() {
                this.initialConfiguration = new models.NetworkConfiguration(_.cloneDeep(this.state.networkConfiguration.toJSON()), {parse: true});
            },

            networkConfigChanged: function() {
                this.setState({errors: false});
                if (this.state.networkConfiguration) {
                    this.state.networkConfiguration.isValid();
                }
            },

            onInvalid: function(networkConfiguration, errors) {
                this.setState({errors: errors});
            },

            componentDidMount: function() {
                var cluster = this.props.model,
                    settings = cluster.get('settings');

                this.initialConfiguration = new models.NetworkConfiguration();
                this.setState({networkConfiguration: cluster.get('networkConfiguration')});

                this.state.networkConfiguration.on('change', _.bind(this.networkConfigChanged, this));
                this.state.networkConfiguration.on('invalid', _.bind(this.onInvalid, this));

                $.when(settings.fetch({cache: true}), this.state.networkConfiguration.fetch({cache: true})).done(_.bind(function() {
                    this.updateInitialConfiguration();
                    this.setState({loading: false});
                }, this));
            },

            isLocked: function() {
                return !!this.props.model.task({group: ['deployment', 'network'], status: 'running'}) ||
                    !this.props.model.isAvailableForSettingsChanges() ||
                    this.state.disabled;
            },

            hasChanges: function() {
                if (_.isUndefined(this.initialConfiguration) || _.isEmpty(this.initialConfiguration.attributes)) {return false;}
                return !_.isEqual(this.initialConfiguration.toJSON(), this.state.networkConfiguration.toJSON());
            },

            managerChange: function(name, value) {
                this.networkingParameters.set({net_manager: value});
                this.forceUpdate();
            },

            verifyNetworks: function() {
                if (!this.state.networkConfiguration.validationError) {
                    this.setState({disabled: true});
                    this.props.page.removeFinishedNetworkTasks().always(_.bind(this.startVerification, this));
                }
            },

            startVerification: function() {
                var task = new models.Task();
                var options = {
                    method: 'PUT',
                    url: _.result(this.state.networkConfiguration, 'url') + '/verify',
                    data: JSON.stringify(this.state.networkConfiguration)
                };
                task.save({}, options)
                    .fail(_.bind(function() {
                        utils.showErrorDialog({
                            title: $.t('cluster_page.network_tab.verify_networks.verification_error.title'),
                            message: $.t('cluster_page.network_tab.verify_networks.verification_error.start_verification_warning')
                        });
                        this.setState({disabled: true});
                    }, this))
                    .always(_.bind(function() {
                        this.props.model.fetchRelated('tasks').done(_.bind(function() {
                            this.startPolling();
                        }, this));
                    }, this));
            },

            revertChanges: function() {
                this.loadInitialConfiguration();
                this.props.page.removeFinishedNetworkTasks().always(_.bind(this.forceUpdate, this));
            },

            applyChanges: function() {
                var deferred;
                this.verifyNetworks();
                if (!this.state.networkConfiguration.validationError) {
                    this.setState({disabled: true});
                    deferred = Backbone.sync('update', this.state.networkConfiguration)
                        .done(_.bind(function(task) {
                            if (task && task.status == 'error') {
                                this.props.page.removeFinishedNetworkTasks().always(_.bind(function() {
                                    this.props.model.fetch();
                                    this.props.model.fetchRelated('tasks').done(_.bind(function() {
                                        this.props.page.removeFinishedNetworkTasks(true);
                                    }, this));
                                }, this));
                            } else {
                                this.updateInitialConfiguration();
                                this.props.model.fetch();
                                this.props.model.fetchRelated('tasks');
                            }
                            this.setState({disabled: false});
                        }, this))
                        .fail(_.bind(function() {
                            utils.showErrorDialog({title: $.t('cluster_page.network_tab.verify_networks.verification_error.title')});
                            this.setState({disabled: false});
                            this.props.model.fetch();
                            this.props.model.fetchRelated('tasks');
                        }, this));
                } else {
                    deferred = new $.Deferred();
                    deferred.reject();
                }
                return deferred;
            },

            render: function() {
                var cluster = this.props.model,
                    managers = {
                        FlatDHCPManager: $.t('cluster_page.network_tab.flatdhcp_manager'),
                        VlanManager: $.t('cluster_page.network_tab.vlan_manager')
                    };
                if (!this.state.loading) {
                    this.networkingParameters = this.state.networkConfiguration.get('networking_parameters');
                    this.segment_type = this.networkingParameters ? this.networkingParameters.get('segmentation_type') : null;
                    this.l23_provider = this.networkingParameters ? this.networkingParameters.get('net_l23_provider') : null;
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
                                        {_.map(managers, function(label, value) {
                                            return (
                                                <div className='item-box' key={label}>
                                                    <controls.Input
                                                        type='radio'
                                                        title={label}
                                                        labelWrapperClassName='parameter-name'
                                                        name='net-manager'
                                                        value={value}
                                                        onChange={this.managerChange}
                                                        checked={this.networkingParameters.get('net_manager') == value}
                                                        disabled={this.isLocked()}
                                                    />
                                                </div>
                                            );
                                        }, this)}
                                    </div>
                                :
                                    <div>
                                        {this.segment_type &&
                                            <div>
                                                <span className='network-segment-type'>
                                                    {(this.l23_provider == 'nsx') ?
                                                        $.t('cluster_page.network_tab.neutron_l23_provider', {l23_provider: this.l23_provider.toUpperCase()})
                                                    :
                                                        $.t('cluster_page.network_tab.neutron_segmentation', {segment_type: this.segment_type.toUpperCase()})
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
                                                    errors={this.state.errors ? this.state.errors.networks : false}
                                                />
                                            );
                                        }
                                    }, this)}

                                </div>
                                <div className='networking-parameters'>
                                    <NetworkParameter
                                        network={this.state.networkConfiguration.get('networking_parameters')}
                                        tab={this}
                                        errors={this.state.errors ? this.state.errors.networking_parameters : false}
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
                                    tab={this}
                                />
                            </div>
                        }
                        <div className='row'>
                            <div className='page-control-box'>
                                <div className='page-control-button-placeholder'>
                                    <button className='btn verify-networks-btn' onClick={this.verifyNetworks}
                                        disabled={this.state.errors || this.isLocked()}>
                                        {$.t('cluster_page.network_tab.verify_networks_button')}
                                    </button>
                                    <button className='btn btn-revert-changes' onClick={this.revertChanges}
                                        disabled={this.isLocked() || !this.hasChanges()}>
                                        {$.t('common.cancel_changes_button')}
                                    </button>
                                    <button className='btn btn-success apply-btn' onClick={this.applyChanges}
                                        disabled={this.state.errors || this.isLocked() || !this.hasChanges()}>
                                        {$.t('common.save_settings_button')}
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                );
            }
    });

    var Network = React.createClass({
        mixins: [
            NetworkRangeMixin,
            NetworkMixin
        ],
        getInitialState: function() {
            return {
                network: this.props.network
            };
        },
        render: function() {
            var disabled = this.props.tab.isLocked() ? 'disabled' : '',
                networkConfig = this.props.network.get('meta'),
                vlanTagging = this.props.network.get('vlan_start');
            this.props.errors = (_.keys(this.props.errors)[0] == this.props.network.id) ? this.props.errors : false;
            return (
                <div>
                    <legend className='networks'>{$.t('network.' +  this.props.network.get('name'))}</legend>
                    <div className={this.props.network.get('name')}>
                        {(networkConfig.notation == 'ip_ranges') &&
                            <controls.Range
                                wrapperClassName='network-attribute ip-ranges'
                                nameLabel={$.t('cluster_page.network_tab.network_parameters.ip_range')}
                                rowsClassName={'ip-ranges-rows'}
                                type='normal'
                                networkAttribute={this.props.network.get('ip_ranges')}
                                attribute='ip_ranges'
                                onChange={this.onRangeChange.bind(this, 'ip_ranges', true)}
                                addRange={this.addRange.bind(this, 'ip_ranges')}
                                removeRange={this.removeRange.bind(this, 'ip_ranges')}
                                error={this.getNetworkError('ip_ranges')}
                                disabled={this.props.tab.isLocked()}
                            />
                        }

                        {this.renderNetworkInput({
                            title: $.t('cluster_page.network_tab.network_parameters.cidr'),
                            name: 'cidr'
                        })}

                        <controls.checkboxAndInput
                            title={$.t('cluster_page.network_tab.network_parameters.use_vlan_tagging')}
                            name='vlan_start'
                            value={vlanTagging}
                            enabled={!_.isNull(vlanTagging)}
                            onInputChange={this.onInputChange}
                            onCheckboxChange={this.onTaggingChange}
                            inputError={this.getNetworkError('vlan_start')}
                            disabled={this.props.tab.isLocked()}
                        />

                        {networkConfig.use_gateway &&
                            <div>
                                {this.renderNetworkInput({
                                    title: $.t('cluster_page.network_tab.network_parameters.gateway'),
                                    name: 'gateway'
                                })}
                            </div>
                        }

                    </div>
                </div>

            );
        }

    });

    var NetworkParameter = React.createClass({
        mixins: [
            NetworkRangeMixin,
            NetworkMixin
        ],
        getInitialState: function() {
            return {
                network: this.props.parameters,
                fixedAmount: this.props.network.get('fixed_networks_amount') || 1
            };
        },
        componentDidMount: function() {
            this.props.network.on('change:net_manager', function(parameters, manager) {
                parameters.set({fixed_networks_amount: manager == 'FlatDHCPManager' ? 1 : this.state.fixedAmount}, {silent: true});
                this.forceUpdate();
            }, this);
            this.props.network.on('change:fixed_networks_amount', this.updateFixedAmount, this);
        },
        updateFixedAmount: function() {
            this.state.fixedAmount = this.props.network.get('fixed_networks_amount') || 1;
        },
        render: function() {
            var network = this.props.network,
                netManager = network.get('net_manager'),
                segmentation = network.get('segmentation_type'),
                disabled = this.props.tab.isLocked() ? 'disabled' : '',
                idRangePrefix = segmentation == 'gre' ? 'gre_id' : 'vlan',
                errors = this.props.errors,
                fixedVlanStart = network.get('fixed_networks_vlan_start'),
                fixedSizeValues = _.map(_.range(3, 12), _.partial(Math.pow, 2));
            return (
                <div>
                    {netManager ?
                        <div>
                            <legend className='networks'>
                                {$.t('cluster_page.network_tab.networking_parameters.nova_configuration')}
                            </legend>
                            <div>
                                <div>
                                    {this.renderNetworkInput({
                                        title: $.t('cluster_page.network_tab.networking_parameters.fixed_cidr'),
                                        name: 'fixed_networks_cidr',
                                        isParameter: true
                                    })}
                                </div>
                                {(netManager == 'VlanManager') ?
                                        <div>
                                            <div className='network-attribute'>
                                                <controls.Input
                                                    type='select'
                                                    title={$.t('cluster_page.network_tab.networking_parameters.fixed_size')}
                                                    name='fixed_network_size'
                                                    value={network.get('fixed_network_size')}
                                                    onChange={this.onInputChange}
                                                    children={_.map(fixedSizeValues, function(value) {
                                                        return <option value={value}>{value}</option>;
                                                    })}
                                                    disabled={this.props.tab.isLocked()}
                                                />
                                            </div>
                                            {this.renderNetworkInput({
                                                title: $.t('cluster_page.network_tab.networking_parameters.fixed_amount'),
                                                name: 'fixed_networks_amount',
                                                isParameter: true
                                            })}
                                            <controls.Range
                                                wrapperClassName={'network-attribute clearfix'}
                                                nameLabel={$.t('cluster_page.network_tab.networking_parameters.fixed_vlan_range')}
                                                type='mini'
                                                name='fixed_networks'
                                                networkAttribute={[fixedVlanStart, (fixedVlanStart + (this.state.fixedAmount - 1))]}
                                                attribute='fixed_networks_vlan_start'
                                                onChange={this.onRangeChange.bind(this, 'fixed_networks_vlan_start', false)}
                                                error={this.getParameterError('fixed_networks_vlan_start')}
                                                disableEnd={true}
                                                disabled={this.props.tab.isLocked()}
                                            />
                                        </div>
                                        :
                                        <div>

                                            <controls.checkboxAndInput
                                                title={$.t('cluster_page.network_tab.networking_parameters.use_vlan_tagging_fixed')}
                                                name='fixed_networks_vlan_start'
                                                value={fixedVlanStart}
                                                enabled={!_.isNull(fixedVlanStart)}
                                                onInputChange={this.onInputChange}
                                                onCheckboxChange={this.onTaggingChange}
                                                inputError={this.getParameterError('fixed_networks_vlan_start')}
                                                disabled={this.props.tab.isLocked()}
                                            />

                                        </div>
                                }
                            </div>
                        </div>
                    :
                        <div>
                            <legend className='networks'>{$.t('cluster_page.network_tab.networking_parameters.l2_configuration')}</legend>

                            <controls.Range
                                wrapperClassName='network-attribute clearfix'
                                nameLabel={$.t('cluster_page.network_tab.networking_parameters.' + idRangePrefix + '_range')}
                                type='mini'
                                networkAttribute={network.get(idRangePrefix + '_range')}
                                attribute={idRangePrefix + '_range'}
                                onChange={this.onRangeChange.bind(this, idRangePrefix + '_range', false)}
                                error={this.getParameterError(idRangePrefix + '_range')}
                                disabled={this.props.tab.isLocked()}
                            />

                            {this.renderNetworkInput({
                                title: $.t('cluster_page.network_tab.networking_parameters.base_mac'),
                                name: 'base_mac',
                                isParameter: true
                            })}

                            <div>
                                <legend className='networks'>{$.t('cluster_page.network_tab.networking_parameters.l3_configuration')}</legend>
                            </div>
                            <div>
                                {this.renderNetworkInput({
                                    title: $.t('cluster_page.network_tab.networking_parameters.internal_cidr'),
                                    name: 'internal_cidr',
                                    isParameter: true
                                })}
                                {this.renderNetworkInput({
                                    title: $.t('cluster_page.network_tab.networking_parameters.internal_gateway'),
                                    name: 'internal_gateway',
                                    isParameter: true
                                })}
                            </div>
                        </div>
                    }

                    <controls.Range
                        type='normal'
                        wrapperClassName='network-attribute floating'
                        nameLabel={$.t('cluster_page.network_tab.networking_parameters.floating_ranges')}
                        rowsClassName='floating-ranges-rows'
                        networkAttribute={network.get('floating_ranges')}
                        attribute='floating_ranges'
                        onChange={this.onRangeChange.bind(this, 'floating_ranges', true)}
                        addRange={this.addRange.bind(this, 'floating_ranges')}
                        removeRange={this.removeRange.bind(this, 'floating_ranges')}
                        error={this.getParameterError('floating_ranges')}
                        disabled={this.props.tab.isLocked()}
                    />

                    <controls.Range
                        type='normal'
                        wrapperClassName='network-attribute'
                        nameLabel={$.t('cluster_page.network_tab.networking_parameters.dns_servers')}
                        rowsClassName='dns_nameservers-row'
                        networkAttribute={[network.get('dns_nameservers')]}
                        attribute={'dns_nameservers'}
                        onChange={this.onRangeChange.bind(this, 'dns_nameservers', false)}
                        noLabel={true}
                        noControls={true}
                        error={this.getParameterError('dns_nameservers')}
                        disabled={this.props.tab.isLocked()}
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
                                }
                                {task && (task.match({name: 'verify_networks'}) && task.get('result').length) ?
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
                                    :
                                        <div></div>
                                    }
                                </div>
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
