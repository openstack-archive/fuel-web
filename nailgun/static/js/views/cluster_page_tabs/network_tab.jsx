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

        var cx = React.addons.classSet;

        var NetworkRangeMixin = {
            onRangeChange: function(attribute, hasManyRanges, rowIndex, name, newValue) {
                var newNetworkModel = this.props.network,
                    valuesToSet = newNetworkModel.get(attribute),
                    valuesToModify = hasManyRanges ? valuesToSet[rowIndex] : valuesToSet;

                if (!_.contains(attribute, 'start')) {
                    if (_.contains(name,  'range0')) {
                        valuesToModify[0] = newValue;
                    } else if (_.contains(name, 'range1')) {
                        valuesToModify[1] = newValue;
                    }
                } else {
                    valuesToSet = parseInt(newValue) || newValue;
                }
                newNetworkModel.set(attribute, valuesToSet);
                this.updateTab(newNetworkModel);
            },

            addRange: function(attribute) {
                var updatedRange = (this.props.network.get(attribute)).push(['', '']),
                    newNetworkModel = this.props.network;
                this.updateTab(newNetworkModel);
            },

            removeRange: function(attribute, rowIndex) {
                var newNetworkModel = this.props.network;
                newNetworkModel.get(attribute).splice(rowIndex, 1);
                this.updateTab(newNetworkModel);
            }
        };

        var NetworkMixin = {

            updateTab: function(model) {
                var newNetworkConfiguration = this.props.tab.props.model.get('networkConfiguration'),
                    currentNetwork = newNetworkConfiguration.get('networks').find(this.props.network),
                    isParameter = _.isUndefined(currentNetwork);
                _.extend(isParameter ? newNetworkConfiguration.get('networking_parameters').toJSON() : currentNetwork.toJSON(), model.toJSON());
                newNetworkConfiguration.isValid();
                this.props.tab.forceUpdate();
            },

            onInputChange: function(name, value) {
                var newNetworkModel = this.props.network;
                if (_.contains(name, 'vlan') || _.contains(name, 'amount')) {
                    var numberValue = _.parseInt(value);
                    newNetworkModel.set(name, _.isNaN(numberValue) ? '' : numberValue);
                } else {
                    newNetworkModel.set(name, value);
                }
                this.updateTab(newNetworkModel);
            },

            onTaggingChange: function(attribute, value) {
                var newNetworkModel = this.props.network;
                newNetworkModel.set(attribute, value ? '' : null);
                this.updateTab(newNetworkModel);
            },

            renderNetworkInput: function(config) {
                return (
                    <div className='network-attribute' key={config.label}>
                        <controls.Input
                            label={config.label}
                            type='text'
                            name={config.name}
                            value={this.props.network.get(config.name)}
                            onChange={this.onInputChange}
                            error={config.isParameter ? this.getParameterError(config.errors, config.name) : this.getNetworkError(config.errors, config.name)}
                            disabled={this.props.tab.isLocked()}
                        />
                    </div>
                );
            },

            getNetworkError: function(errors, attribute) {
                return (_.find(errors, attribute) || {})[attribute];
            },

            getParameterError: function(errors, attribute) {
                if (errors && _.contains(attribute, 'start')) {
                    return _.compact([errors[attribute]]);
                }
                return errors ? errors[attribute] : undefined;
            }
        };

        var Range = React.createClass({
            getDefaultProps: function() {
                return {type: 'normal'};
            },
            propTypes: {
                wrapperClassName: React.PropTypes.renderable,
                type: React.PropTypes.oneOf(['normal', 'mini']),
                attribute: React.PropTypes.array,
                attributeName: React.PropTypes.string
            },
            autoCompleteIpRange: function(error, rangeStart, event) {
                var input = event.target;
                if (_.isUndefined(error)) {
                    input.value = rangeStart;
                }
                if (input.setSelectionRange) {
                    var startPos = _.lastIndexOf(rangeStart, '.') + 1;
                    var endPos = rangeStart.length;
                    _.defer(function() { input.setSelectionRange(startPos, endPos); });
                }
            },
            render: function() {
                var wrapperClasses = {
                        mini: this.props.type == 'mini'
                    },
                    rowHeaderClasses = {
                        'range-row-header': true
                    },
                    currentError = null,
                    errors = this.props.error || false,
                    attributeName = this.props.attributeName || '';
                wrapperClasses[this.props.wrapperClassName] = this.props.wrapperClassName;
                return (
                    <div className={cx(wrapperClasses)}>
                        {this.props.showHeader &&
                            <div className={cx(rowHeaderClasses)}>
                                <div>{$.t('cluster_page.network_tab.range_start')}</div>
                                <div>{$.t('cluster_page.network_tab.range_end')}</div>
                            </div>
                        }
                        <div className='parameter-name'>{this.props.label}</div>
                        { (this.props.type == 'normal') ?
                            <div className={this.props.rowsClassName}>
                                {_.map(this.props.attribute, function(range, index) {
                                    if (errors) {
                                        currentError = _.compact(_.map(errors, function(error) {
                                            return (error.index == index) ? error : null;
                                        }, this))[0] || null;
                                    }
                                    return (

                                        <div className='range-row autocomplete clearfix' key={index}>
                                            <controls.Input
                                                type='text'
                                                error={currentError && currentError.start ? '' : null}
                                                name={'range0' + '_' + attributeName}
                                                placeholder='127.0.0.1'
                                                value={range[0]}
                                                inputClassName='range'
                                                onChange={_.partial(this.props.onChange, index)}
                                                disabled={this.props.disabled}
                                            />
                                            <controls.Input
                                                type='text'
                                                error={currentError && currentError.end ? '' : null}
                                                name={'range1' + '_' + attributeName}
                                                placeholder='127.0.0.1'
                                                value={range[1]}
                                                inputClassName='range'
                                                onChange={_.partial(this.props.onChange, index)}
                                                onFocus={this.autoCompleteIpRange.bind(this, currentError && currentError.start, range[0])}
                                                disabled={this.props.disabled || this.props.disableEnd}
                                            />

                                            <div>
                                                <div className='ip-ranges-control'>
                                                    <button className='btn btn-link ip-ranges-add' disabled={this.props.disabled} onClick={this.props.addRange}>
                                                        <i className='icon-plus-circle'></i>
                                                    </button>
                                                </div>
                                                {(this.props.attribute.length > 1) &&
                                                    <div className='ip-ranges-control'>
                                                        <button className='btn btn-link ip-ranges-delete' disabled={this.props.disabled} onClick={_.partial(this.props.removeRange, index)}>
                                                            <i className='icon-minus-circle'></i>
                                                        </button>
                                                    </div>
                                                }
                                            </div>
                                            <div className='error validation-error'>
                                                <span className='help-inline'>{currentError ? currentError.start || currentError.end : ''}</span>
                                            </div>
                                        </div>
                                    );
                                }, this)}
                            </div>
                        :
                            <div className='range-row'>

                                <controls.Input
                                    type='text'
                                    wrapperClassName={'parameter-control'}
                                    inputClassName='range'
                                    name={'range0' + '_' + attributeName}
                                    value={this.props.attribute[0]}
                                    error={errors && errors[0] ? '' : null}
                                    onChange={_.partial(this.props.onChange, 0)}
                                    disabled={this.props.disabled}
                                />

                                <controls.Input
                                    type='text'
                                    wrapperClassName={'parameter-control'}
                                    inputClassName='range'
                                    name={'range1' + '_' + attributeName}
                                    value={this.props.attribute[1]}
                                    error={errors && errors[0] ? '' : null}
                                    onChange={_.partial(this.props.onChange, 0)}
                                    disabled={this.props.disabled || this.props.disableEnd}
                                />

                                <div className='error validation-error'>
                                    <span className='help-inline'>{errors ? errors[0] || errors[1] : ''}</span>
                                </div>
                            </div>
                        }
                    </div>
                );
            }
        });

        var VlanTagInput = React.createClass({
            render: function() {
                return (
                    <div className='network-attribute complex-control vlan-tagging'>
                        {this.transferPropsTo(
                            <controls.Input
                                labelBeforeControl={true}
                                onChange={this.props.onCheckboxChange}
                                type='checkbox'
                                checked={!_.isNull(this.props.value)}
                            />
                        )}
                        {this.props.enabled &&
                            <div>
                                {this.transferPropsTo(
                                    <controls.Input
                                        label={false}
                                        onChange={this.props.onInputChange}
                                        type ='text'
                                        error={this.props.inputError}
                                    />
                                )}
                            </div>
                        }

                    </div>
                );
            }
        });

        var NetworkTab = React.createClass({
            mixins: [
                React.BackboneMixin('model', 'change'),
                React.BackboneMixin({
                    modelOrCollection: function(props) {
                        return props.model.get('networkConfiguration');
                    }
                }),
                React.BackboneMixin({
                    modelOrCollection: function(props) {
                        return props.model.get('networkConfiguration').get('networking_parameters');
                    }
                }),
                React.BackboneMixin({
                    modelOrCollection: function(props) {
                        return props.model.get('networkConfiguration').get('networks');
                    }
                }),
                React.BackboneMixin({
                    modelOrCollection: function(props) {
                        return props.model.get('tasks');
                    },
                    renderOn: 'add remove change:status'
                }),
                React.BackboneMixin({
                    modelOrCollection: function(props) {
                        return props.model.task({group: 'network', status: 'running'});
                    }
                }),
                componentMixins.pollingMixin(3)
            ],

            shouldDataBeFetched: function() {
                return !!this.props.model.task({group: 'network', status: 'running'});
            },

            fetchData: function() {
                var task = this.props.model.task({group: 'network', status: 'running'});
                return task.fetch();
            },

            getInitialState: function() {
                return {
                    loading: true
                };
            },

            loadInitialConfiguration: function() {
                this.props.model.get('networkConfiguration').set(
                    new models.NetworkConfiguration(_.cloneDeep(this.initialConfiguration.toJSON()), {parse: true}).attributes
                );
            },

            updateInitialConfiguration: function() {
                this.initialConfiguration = new models.NetworkConfiguration(_.cloneDeep(this.props.model.get('networkConfiguration').toJSON()), {parse: true});
            },

            componentDidMount: function() {
                var cluster = this.props.model,
                    settings = cluster.get('settings');
                this.initialConfiguration = new models.NetworkConfiguration();
                $.when(settings.fetch({cache: true}), cluster.get('networkConfiguration').fetch({cache: true})).done(_.bind(function() {
                    this.updateInitialConfiguration();
                    this.setState({loading: false});
                }, this));
            },

            isLocked: function() {
                return !!this.props.model.task({group: ['deployment', 'network'], status: 'running'}) ||
                    !this.props.model.isAvailableForSettingsChanges();
            },

            hasChanges: function() {
                if (_.isUndefined(this.initialConfiguration) || _.isEmpty(this.initialConfiguration.attributes)) {return false;}
                return !_.isEqual(this.initialConfiguration.toJSON(), this.props.model.get('networkConfiguration').toJSON());
            },

            managerChange: function(name, value) {
                this.props.model.get('networkConfiguration').get('networking_parameters').set({net_manager: value});
                this.forceUpdate();
            },

            verifyNetworks: function() {
                if (!this.props.model.get('networkConfiguration').validationError) {
                    this.props.page.removeFinishedNetworkTasks().always(_.bind(this.startVerification, this));
                }
            },

            startVerification: function() {
                var task = new models.Task(),
                    cluster = this.props.model,
                    networkConfig = cluster.get('networkConfiguration');
                var options = {
                    method: 'PUT',
                    url: _.result(networkConfig, 'url') + '/verify',
                    data: JSON.stringify(networkConfig)
                };
                task.save({}, options)
                    .fail(_.bind(function() {
                        utils.showErrorDialog({
                            title: $.t('cluster_page.network_tab.verify_networks.verification_error.title'),
                            message: $.t('cluster_page.network_tab.verify_networks.verification_error.start_verification_warning')
                        });
                    }, this))
                    .always(_.bind(function() {
                        cluster.fetchRelated('tasks').done(_.bind(function() {
                            this.startPolling();
                        }, this));
                    }, this));
            },

            revertChanges: function() {
                this.loadInitialConfiguration();
                this.props.page.removeFinishedNetworkTasks();
                this.forceUpdate();
            },

            applyChanges: function() {
                var deferred,
                    networkConfiguration = this.props.model.get('networkConfiguration');
                if (!networkConfiguration.validationError) {
                    deferred = Backbone.sync('update', networkConfiguration)
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
                            this.forceUpdate();
                        }, this))
                        .fail(_.bind(function() {
                            utils.showErrorDialog({title: $.t('cluster_page.network_tab.verify_networks.verification_error.title')});
                            this.props.model.fetch();
                            this.props.model.fetchRelated('tasks');
                            this.forceUpdate();
                        }, this));
                } else {
                    deferred = new $.Deferred();
                    deferred.reject();
                }
                return deferred;
            },

            renderControls: function() {
                var error  = this.props.model.get('networkConfiguration').validationError;
                return (
                    <div className='row'>
                        <div className='page-control-box'>
                            <div className='page-control-button-placeholder'>
                                <button key='verify_networks' className='btn verify-networks-btn' onClick={this.verifyNetworks}
                                    disabled={error || this.isLocked()}>
                                        {$.t('cluster_page.network_tab.verify_networks_button')}
                                </button>
                                <button key='revert_changes' className='btn btn-revert-changes' onClick={this.revertChanges}
                                    disabled={this.isLocked() || !this.hasChanges()}>
                                        {$.t('common.cancel_changes_button')}
                                </button>
                                <button key='apply_changes' className='btn btn-success apply-btn' onClick={this.applyChanges}
                                    disabled={error || this.isLocked() || !this.hasChanges()}>
                                        {$.t('common.save_settings_button')}
                                </button>
                            </div>
                        </div>
                    </div>
                );
            },

            render: function() {
                var cluster = this.props.model,
                    networkConfiguration = cluster.get('networkConfiguration'),
                    networkingParameters,
                    managers = {
                        FlatDHCPManager: $.t('cluster_page.network_tab.flatdhcp_manager'),
                        VlanManager: $.t('cluster_page.network_tab.vlan_manager')
                    },
                    error = this.props.model.get('networkConfiguration').validationError;
                if (!this.state.loading) {
                    networkingParameters = networkConfiguration.get('networking_parameters');
                    this.segment_type = networkingParameters ? networkingParameters.get('segmentation_type') : null;
                    this.l23_provider = networkingParameters ? networkingParameters.get('net_l23_provider') : null;
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
                                                <div className='item-box'
                                                    key={label}>
                                                    <controls.Input
                                                        type='radio'
                                                        label={label}
                                                        key={label}
                                                        labelWrapperClassName='parameter-name'
                                                        name='net-manager'
                                                        value={value}
                                                        onChange={this.managerChange}
                                                        checked={networkingParameters.get('net_manager') == value}
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
                                    {networkConfiguration.get('networks').map(function(network, index) {
                                        if (network.get('meta').configurable) {
                                            return (
                                                <Network
                                                    key={network.id}
                                                    network={network}
                                                    tab={this}
                                                    errors={error ? error.networks : false}
                                                />
                                            );
                                        }
                                    }, this)}
                                </div>
                                <div className='networking-parameters'>
                                    <NetworkParameter
                                        key='network_parameter'
                                        network={networkingParameters}
                                        tab={this}
                                        errors={error ? error.networking_parameters : false}
                                    />
                                </div>
                            </div>
                        }

                        {!this.state.loading &&
                            <div className='row verification-control'>
                                <NetworkVerification
                                    key='network_verification'
                                    cluster={this.props.model}
                                    networks={networkConfiguration.get('networks')}
                                    tab={this}
                                />
                            </div>
                        }
                        {this.renderControls()}
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
                    vlanTagging = this.props.network.get('vlan_start'),
                    errors = this.props.tab.props.model.get('networkConfiguration').validationError;
                if (errors) {
                    errors = _.has(errors.networks, this.props.network.id) ? errors.networks : false;
                }
                return (
                    <div>
                        <legend className='networks'>{$.t('network.' +  this.props.network.get('name'))}</legend>
                        <div className={this.props.network.get('name')}>
                            {(networkConfig.notation == 'ip_ranges') &&
                                <Range
                                    wrapperClassName='network-attribute ip-ranges'
                                    label={$.t('cluster_page.network_tab.network_parameters.ip_range')}
                                    rowsClassName={'ip-ranges-rows'}
                                    type='normal'
                                    attribute={this.props.network.get('ip_ranges')}
                                    onChange={this.onRangeChange.bind(this, 'ip_ranges', true)}
                                    addRange={this.addRange.bind(this, 'ip_ranges')}
                                    removeRange={this.removeRange.bind(this, 'ip_ranges')}
                                    error={this.getNetworkError(errors, 'ip_ranges')}
                                    disabled={this.props.tab.isLocked()}
                                    attributeName={'ip_ranges'}
                                />
                            }

                            {this.renderNetworkInput({
                                label: $.t('cluster_page.network_tab.network_parameters.cidr'),
                                name: 'cidr',
                                errors: errors
                            })}

                            <VlanTagInput
                                label={$.t('cluster_page.network_tab.network_parameters.use_vlan_tagging')}
                                name='vlan_start'
                                value={vlanTagging}
                                enabled={!_.isNull(vlanTagging)}
                                onInputChange={this.onInputChange}
                                onCheckboxChange={this.onTaggingChange}
                                inputError={this.getNetworkError(errors, 'vlan_start')}
                                disabled={this.props.tab.isLocked()}
                            />

                            {networkConfig.use_gateway &&
                                <div>
                                    {this.renderNetworkInput({
                                        label: $.t('cluster_page.network_tab.network_parameters.gateway'),
                                        name: 'gateway',
                                        errors: errors
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
                    errors = this.props.tab.props.model.get('networkConfiguration').validationError,
                    fixedVlanStart = network.get('fixed_networks_vlan_start'),
                    fixedSizeValues = _.map(_.range(3, 12), _.partial(Math.pow, 2));
                errors = errors ? errors.networking_parameters : undefined;
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
                                            label: $.t('cluster_page.network_tab.networking_parameters.fixed_cidr'),
                                            name: 'fixed_networks_cidr',
                                            isParameter: true,
                                            errors: errors
                                        })}
                                    </div>
                                    {(netManager == 'VlanManager') ?
                                            <div>
                                                <div className='network-attribute'>
                                                    <controls.Input
                                                        type='select'
                                                        key='fixedNetworkSize'
                                                        label={$.t('cluster_page.network_tab.networking_parameters.fixed_size')}
                                                        name='fixed_network_size'
                                                        value={network.get('fixed_network_size')}
                                                        onChange={this.onInputChange}
                                                        children={_.map(fixedSizeValues, function(value) {
                                                            return <option key={value} value={value}>{value}</option>;
                                                        })}
                                                        disabled={this.props.tab.isLocked()}
                                                    />
                                                </div>
                                                {this.renderNetworkInput({
                                                    label: $.t('cluster_page.network_tab.networking_parameters.fixed_amount'),
                                                    name: 'fixed_networks_amount',
                                                    isParameter: true,
                                                    errors: errors
                                                })}
                                                <Range
                                                    wrapperClassName={'network-attribute clearfix'}
                                                    label={$.t('cluster_page.network_tab.networking_parameters.fixed_vlan_range')}
                                                    type='mini'
                                                    attribute={[fixedVlanStart, (fixedVlanStart + (this.state.fixedAmount - 1))]}
                                                    onChange={this.onRangeChange.bind(this, 'fixed_networks_vlan_start', false)}
                                                    error={this.getParameterError(errors, 'fixed_networks_vlan_start')}
                                                    disableEnd={true}
                                                    disabled={this.props.tab.isLocked()}
                                                    attributeName={'fixed_networks_vlan_start'}
                                                />
                                            </div>
                                            :
                                            <div className='clearfix'>

                                                <VlanTagInput
                                                    label={$.t('cluster_page.network_tab.networking_parameters.use_vlan_tagging_fixed')}
                                                    name='fixed_networks_vlan_start'
                                                    value={fixedVlanStart}
                                                    enabled={!_.isNull(fixedVlanStart)}
                                                    onInputChange={this.onInputChange}
                                                    onCheckboxChange={this.onTaggingChange}
                                                    inputError={this.getParameterError(errors, 'fixed_networks_vlan_start')}
                                                    disabled={this.props.tab.isLocked()}
                                                    attributeName={'fixed_networks_vlan_start'}
                                                />

                                            </div>
                                    }
                                </div>
                            </div>
                        :
                            <div>
                                <legend className='networks'>{$.t('cluster_page.network_tab.networking_parameters.l2_configuration')}</legend>

                                <Range
                                    wrapperClassName='network-attribute clearfix'
                                    label={$.t('cluster_page.network_tab.networking_parameters.' + idRangePrefix + '_range')}
                                    type='mini'
                                    attribute={network.get(idRangePrefix + '_range')}
                                    onChange={this.onRangeChange.bind(this, idRangePrefix + '_range', false)}
                                    error={this.getParameterError(errors, idRangePrefix + '_range')}
                                    disabled={this.props.tab.isLocked()}
                                    attributeName={idRangePrefix + '_range'}
                                />

                                {this.renderNetworkInput({
                                    label: $.t('cluster_page.network_tab.networking_parameters.base_mac'),
                                    name: 'base_mac',
                                    isParameter: true,
                                    errors: errors
                                })}

                                <div>
                                    <legend className='networks'>{$.t('cluster_page.network_tab.networking_parameters.l3_configuration')}</legend>
                                </div>
                                <div>
                                    {this.renderNetworkInput({
                                        label: $.t('cluster_page.network_tab.networking_parameters.internal_cidr'),
                                        name: 'internal_cidr',
                                        isParameter: true,
                                        errors: errors
                                    })}
                                    {this.renderNetworkInput({
                                        label: $.t('cluster_page.network_tab.networking_parameters.internal_gateway'),
                                        name: 'internal_gateway',
                                        isParameter: true,
                                        errors: errors
                                    })}
                                </div>
                            </div>
                        }

                        <Range
                            type='normal'
                            wrapperClassName='network-attribute floating-ranges'
                            label={$.t('cluster_page.network_tab.networking_parameters.floating_ranges')}
                            rowsClassName='floating-ranges-rows'
                            attribute={network.get('floating_ranges')}
                            onChange={this.onRangeChange.bind(this, 'floating_ranges', true)}
                            addRange={this.addRange.bind(this, 'floating_ranges')}
                            removeRange={this.removeRange.bind(this, 'floating_ranges')}
                            error={this.getParameterError(errors, 'floating_ranges')}
                            disabled={this.props.tab.isLocked()}
                            attributeName={'floating_ranges'}
                        />
                        <Range
                            type='mini'
                            wrapperClassName='network-attribute dns-nameservers'
                            label={$.t('cluster_page.network_tab.networking_parameters.dns_servers')}
                            rowsClassName='dns_nameservers-row'
                            attribute={network.get('dns_nameservers')}
                            onChange={this.onRangeChange.bind(this, 'dns_nameservers', false)}
                            showHeader={false}
                            error={this.getParameterError(errors, 'dns_nameservers')}
                            disabled={this.props.tab.isLocked()}
                            attributeName={'dns_nameservers'}
                        />

                    </div>
                );
            }
        });

        var NetworkVerification = React.createClass({
            getConnectionStatus: function(task, isFirstConnectionLine) {
                if (!task || (task && task.match({status: 'ready'}))) return 'stop';
                if (task && task.match({status: 'error'}) && !(isFirstConnectionLine && !(task.match({name: 'verify_networks'}) && !task.get('result').length))) return 'error';
                return 'success';
            },
            render: function() {
                var task = this.props.cluster.task({group: 'network'}),
                    threeItemsArray = ['1', '2', '3'],
                    ns = 'cluster_page.network_tab.verify_networks.';
                return (
                    <div>
                        <hr/>
                        <div className='page-control-box'>
                            <div className='verification-box'>
                                <div className='verification-network-placeholder'>
                                    <div className='router-box'>
                                        <div className='verification-router'></div>
                                    </div>
                                    <div className='animation-box'>
                                        {_.map(threeItemsArray, function(index) {
                                            return <div key={index} className={'connect-' + index + '-' + this.getConnectionStatus(task, index == '1')}></div>;
                                        }, this)}
                                    </div>
                                    <div className='nodex-box'>
                                        {_.map(threeItemsArray, function(index) {
                                            return <div key={index} className={'verification-node-' + index}></div>;
                                        })}
                                    </div>
                                </div>

                                <div className='verification-text-placeholder'>
                                    {_.map(['0', '1', '2', '3', '4'], function(index) {
                                        return <li key={index}>{$.t(ns + 'step_' + index)}</li>;
                                    }, this)}
                                </div>

                                {(task && task.match({name: 'verify_networks', status: 'ready'})) ?
                                    <div className='alert alert-success enable-selection'>
                                        {$.t(ns + 'success_alert')}
                                    </div>
                                : (task && task.match({status: 'error'})) &&
                                    <div className='alert alert-error enable-selection'>
                                        <span>
                                            {$.t(ns + 'fail_alert')}
                                        </span>
                                        <br/>
                                        {utils.linebreaks(task.escape('message'))}
                                    </div>
                                }
                                {(task && task.match({name: 'verify_networks'}) && !!task.get('result').length) &&
                                    <div className='verification-result-table'>
                                        <controls.Table
                                            tableClassName='table table-condensed enable-selection'
                                            noStripes={true}
                                            head={_.map(['node_name', 'node_mac_address', 'node_interface', 'expected_vlan'], function(attr) {
                                                return $.t(ns + attr);
                                            })}
                                            body={
                                                _.map(task.get('result'), function(node, index) {
                                                    var absentVlans = _.map(node.absent_vlans, function(vlan) {
                                                        return vlan || $.t('cluster_page.network_tab.untagged');
                                                    });
                                                    return [node.name || 'N/A', node.mac || 'N/A', node.interface, absentVlans];
                                                })
                                            }
                                        />
                                    </div>
                                }
                            </div>
                        </div>
                    </div>
                );
            }
        });

    return NetworkTab;
});
