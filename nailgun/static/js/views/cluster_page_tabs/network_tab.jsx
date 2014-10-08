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

        var commonNetworkMixin = {
            getModel: function() {
                return this.props.network ? this.props.cluster.get('networkConfiguration').get('networks').get(this.props.network) : this.props.parameters;
            },
            updateTab: function(model) {
                var newNetworkConfiguration = this.props.cluster.get('networkConfiguration'),
                    currentNetwork = newNetworkConfiguration.get('networks').find(this.props.network),
                    isParameter = _.isUndefined(currentNetwork);
                if (isParameter) {
                    newNetworkConfiguration.get('networking_parameters').set(model.toJSON());
                } else {
                    currentNetwork.set(model.toJSON());
                }
                newNetworkConfiguration.isValid();
                this.props.tab.forceUpdate();
            }
        };

        var NetworkMixin = {
            onInputChange: function(name, value) {
                var model = this.getModel();
                if (_.contains(name, 'vlan') || _.contains(name, 'amount')) value = _.parseInt(value);
                if (_.isNaN(value)) value = '';
                model.set(name, value);
                this.updateTab(model);
            },
            onTaggingChange: function(attribute, value) {
                var newNetworkModel = this.getModel();
                newNetworkModel.set(attribute, value ? '' : null);
                this.updateTab(newNetworkModel);
            },
            renderNetworkInput: function(config) {
                return (
                    <controls.Input
                        wrapperClassName={'network-attribute'}
                        key={config.label}
                        label={config.label}
                        type='text'
                        name={config.name}
                        value={this.getModel().get(config.name)}
                        onChange={this.onInputChange}
                        error={config.isParameter ? this.getParameterError(config.errors, config.name) : this.getNetworkError(config.errors, config.name)}
                        disabled={this.props.tab.isLocked()}
                    />
                );
            },
            getNetworkError: function(errors, attribute) {
                return (_.find(errors, attribute) || {})[attribute];
            },
            getParameterError: function(errors, attribute) {
                if (errors && _.contains(attribute, 'start')) {
                    var compactErrors = _.compact([errors[attribute]]);
                    return _.isEmpty(compactErrors) ? null : compactErrors;
                }
                return (errors || {})[attribute];
            }
        };

        var Range = React.createClass({
            getDefaultProps: function() {
                return {type: 'normal'};
            },
            propTypes: {
                wrapperClassName: React.PropTypes.renderable,
                type: React.PropTypes.oneOf(['normal', 'mini']),
                attributeName: React.PropTypes.string
            },
            autoCompleteIPRange: function(error, rangeStart, event) {
                var input = event.target;
                if (input.value) return false;
                if (_.isUndefined(error)) input.value = rangeStart;
                if (input.setSelectionRange) {
                    var startPos = _.lastIndexOf(rangeStart, '.') + 1;
                    var endPos = rangeStart.length;
                    _.defer(function() { input.setSelectionRange(startPos, endPos); });
                }
            },
            onRangeChange: function(hasManyRanges, rowIndex, attribute, name, newValue) {
                var newNetworkModel = this.props.model,
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
                this.props.component.updateTab(newNetworkModel);
            },
            addRange: function(attribute) {
                var newNetworkModel = this.props.model;
                newNetworkModel.get(attribute).push(['', '']);
                this.props.component.updateTab(newNetworkModel);
            },
            removeRange: function(attribute, rowIndex) {
                var newNetworkModel = this.props.model;
                newNetworkModel.get(attribute).splice(rowIndex, 1);
                this.props.component.updateTab(newNetworkModel);
            },
            render: function() {
                var wrapperClasses = {
                        mini: this.props.type == 'mini'
                    },
                    currentError = {},
                    errors = this.props.error || null,
                    attributeName = this.props.attributeName,
                    ranges = this.props.model.get(attributeName),
                    disableEnd = false,
                    disabled = this.props.component.props.disabled;
                if (attributeName == 'fixed_networks_vlan_start') {
                    ranges = [ranges, ranges + this.props.component.props.parameters.get('fixed_networks_amount') - 1];
                    disableEnd = true;
                }
                wrapperClasses[this.props.wrapperClassName] = this.props.wrapperClassName;
                return (
                    <div className={cx(wrapperClasses)}>
                        {this.props.showHeader &&
                            <div className={'range-row-header'}>
                                <div>{$.t('cluster_page.network_tab.range_start')}</div>
                                <div>{$.t('cluster_page.network_tab.range_end')}</div>
                            </div>
                        }
                        <div className='parameter-name'>{this.props.label}</div>
                        { (this.props.type == 'normal') ?
                            <div className={this.props.rowsClassName}>
                                {_.map(ranges, function(range, index) {
                                    currentError = _.findWhere(errors, {index: index}) || {};
                                    return (
                                        <div className='range-row autocomplete clearfix' key={index}>
                                            <controls.Input
                                                type='text'
                                                error={currentError.start && ''}
                                                name={'range0' + '_' + attributeName}
                                                placeholder='127.0.0.1'
                                                value={range[0]}
                                                inputClassName='range'
                                                onChange={_.partial(this.onRangeChange, true, index, attributeName)}
                                                disabled={disabled}
                                            />
                                            <controls.Input
                                                type='text'
                                                error={currentError.end && ''}
                                                name={'range1' + '_' + attributeName}
                                                placeholder='127.0.0.1'
                                                value={range[1]}
                                                inputClassName='range'
                                                onChange={_.partial(this.onRangeChange, true, index, attributeName)}
                                                onFocus={this.autoCompleteIPRange.bind(this, currentError && currentError.start, range[0])}
                                                disabled={disabled || disableEnd}
                                            />
                                            <div>
                                                <div className='ip-ranges-control'>
                                                    <button className='btn btn-link ip-ranges-add' disabled={disabled}
                                                        onClick={_.partial(this.addRange, attributeName)}>
                                                        <i className='icon-plus-circle'></i>
                                                    </button>
                                                </div>
                                                {(ranges.length > 1) &&
                                                    <div className='ip-ranges-control'>
                                                        <button className='btn btn-link ip-ranges-delete' disabled={disabled}
                                                            onClick={_.partial(this.removeRange, attributeName, index)}>
                                                            <i className='icon-minus-circle'></i>
                                                        </button>
                                                    </div>
                                                }
                                            </div>
                                            <div className='error validation-error'>
                                                <span className='help-inline'>{currentError.start || currentError.end}</span>
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
                                    value={ranges[0]}
                                    error={errors && errors[0] ? '' : null}
                                    onChange={_.partial(this.onRangeChange, false, 0, attributeName)}
                                    disabled={disabled}
                                />

                                <controls.Input
                                    type='text'
                                    wrapperClassName={'parameter-control'}
                                    inputClassName='range'
                                    name={'range1' + '_' + attributeName}
                                    value={ranges[1]}
                                    error={errors && errors[0] ? '' : null}
                                    onChange={_.partial(this.onRangeChange, false, 0, attributeName)}
                                    disabled={disabled || disableEnd}
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
                        {!_.isNull(this.props.value) &&
                            this.transferPropsTo(
                                <controls.Input
                                    label={false}
                                    onChange={this.props.onInputChange}
                                    type ='text'
                                    error={this.props.inputError || null}
                                />
                            )
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
                React.BackboneMixin({
                    modelOrCollection: function(props) {
                        return props.model.task({group: 'deployment', status: 'running'});
                    }
                }),
                componentMixins.pollingMixin(3)
            ],

            shouldDataBeFetched: function() {
                return !!this.props.model.task({group: 'network', status: 'running'});
            },

            fetchData: function() {
                return this.props.model.task({group: 'network', status: 'running'}).fetch();
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
                return !_.isEqual(this.initialConfiguration.toJSON(), this.props.model.get('networkConfiguration').toJSON());
            },

            onManagerChange: function(name, value) {
                var networkingParams = this.props.model.get('networkConfiguration').get('networking_parameters'),
                fixedAmount = networkingParams.get('fixed_networks_amount') || 1;
                networkingParams.set({net_manager: value});
                networkingParams.set({fixed_networks_amount: value == 'FlatDHCPManager' ? 1 : fixedAmount}, {silent: true});
                this.forceUpdate();
            },

            verifyNetworks: function() {
                if (!this.props.model.get('networkConfiguration').validationError) {
                    this.props.page.removeFinishedNetworkTasks().always(this.startVerification, this);
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
                var error  = this.props.model.get('networkConfiguration').validationError,
                    isLocked = this.isLocked();
                return (
                    <div className='row'>
                        <div className='page-control-box'>
                            <div className='page-control-button-placeholder'>
                                <button key='verify_networks' className='btn verify-networks-btn' onClick={this.verifyNetworks}
                                    disabled={error || isLocked}>
                                        {$.t('cluster_page.network_tab.verify_networks_button')}
                                </button>
                                <button key='revert_changes' className='btn btn-revert-changes' onClick={this.revertChanges}
                                    disabled={isLocked || !this.hasChanges()}>
                                        {$.t('common.cancel_changes_button')}
                                </button>
                                <button key='apply_changes' className='btn btn-success apply-btn' onClick={this.applyChanges}
                                    disabled={error || isLocked || !this.hasChanges()}>
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
                    managers = [],
                    error = this.props.model.get('networkConfiguration').validationError,
                    segmentType = false,
                    l23Provider = false,
                    networkTabClassName = {
                        'network-settings wrapper': true,
                        'changes-locked': this.isLocked()
                    };
                if (!this.state.loading) {
                    networkingParameters = networkConfiguration.get('networking_parameters');
                    var manager = networkingParameters.get('net_manager');
                    segmentType = networkingParameters ? networkingParameters.get('segmentation_type') : null;
                    l23Provider = networkingParameters ? networkingParameters.get('net_l23_provider') : null;
                    managers = [
                        {
                            label: $.t('cluster_page.network_tab.flatdhcp_manager'),
                            data: 'FlatDHCPManager',
                            checked: manager == 'FlatDHCPManager'
                        },
                        {
                            label: $.t('cluster_page.network_tab.vlan_manager'),
                            data: 'VlanManager',
                            checked: manager == 'VlanManager'
                        }
                    ];
                }
                return (
                    <div className={cx(networkTabClassName)}>
                        <h3>{$.t('cluster_page.network_tab.title')}</h3>
                        {this.state.loading ?
                            <controls.ProgressBar />
                        :
                            <div>
                                <div className='radio-checkbox-group'>
                                    {(cluster.get('net_provider') == 'nova_network') ?
                                        <controls.RadioGroup
                                            key={'net_provider'}
                                            name={'net_provider'}
                                            values={managers}
                                            onChange={this.onManagerChange}
                                        />
                                    :
                                        <div>
                                            {segmentType &&
                                                <span className='network-segment-type'>
                                                    {(l23Provider == 'nsx') ?
                                                        $.t('cluster_page.network_tab.neutron_l23_provider', {l23_provider: l23Provider.toUpperCase()})
                                                        :
                                                        $.t('cluster_page.network_tab.neutron_segmentation', {segment_type: segmentType.toUpperCase()})
                                                    }
                                                </span>
                                            }
                                        </div>
                                    }

                                </div>
                                <hr/>
                                <div className='networks-table'>
                                    {networkConfiguration.get('networks').map(function(network, index) {
                                        if (network.get('meta').configurable) {
                                            return (
                                                <Network
                                                    key={network.id}
                                                    network={network}
                                                    cluster={this.props.model}
                                                    tab={this}
                                                    errors={(error || {}).networks}
                                                    disabled={this.isLocked()}
                                                />
                                            );
                                        }
                                    }, this)}
                                </div>
                                <div className='networking-parameters'>
                                    <NetworkParameter
                                        key='network_parameter'
                                        parameters={networkingParameters}
                                        cluster={this.props.model}
                                        tab={this}
                                        errors={error ? error.networking_parameters : false}
                                        disabled={this.isLocked()}
                                    />
                                </div>

                                <div className='row verification-control'>
                                    <NetworkVerification
                                        key='network_verification'
                                        cluster={this.props.model}
                                        networks={networkConfiguration.get('networks')}
                                        tab={this}
                                    />
                                </div>
                                {this.renderControls()}
                            </div>
                        }
                    </div>
                );
            }
        });

        var Network = React.createClass({
            mixins: [
                commonNetworkMixin,
                NetworkMixin
            ],
            render: function() {
                var network = this.props.network,
                    networkConfig = network.get('meta'),
                    vlanTagging = network.get('vlan_start'),
                    ipRangesLabel = 'ip_ranges',
                    ns = 'cluster_page.network_tab.network_parameters.',
                    errors = this.props.cluster.get('networkConfiguration').validationError;
                if (errors) {
                    errors = _.has(errors.networks, network.id) ? errors.networks : false;
                }
                return (
                    <div>
                        <legend className='networks'>{$.t('network.' +  network.get('name'))}</legend>
                        <div className={this.props.network.get('name')}>
                            {(networkConfig.notation == ipRangesLabel) &&
                                <Range
                                    wrapperClassName={'network-attribute ' +  ipRangesLabel}
                                    label={$.t(ns + ipRangesLabel)}
                                    rowsClassName='ip-ranges-rows'
                                    error={this.getNetworkError(errors, ipRangesLabel)}
                                    attributeName={ipRangesLabel}
                                    model={this.props.network}
                                    component={this}
                                />
                            }

                            {this.renderNetworkInput({
                                label: $.t(ns + 'cidr'),
                                name: 'cidr',
                                errors: errors
                            })}

                            <VlanTagInput
                                label={$.t(ns + 'use_vlan_tagging')}
                                name='vlan_start'
                                value={vlanTagging}
                                onInputChange={this.onInputChange}
                                onCheckboxChange={this.onTaggingChange}
                                inputError={this.getNetworkError(errors, 'vlan_start')}
                                disabled={this.props.disabled}
                            />

                            {networkConfig.use_gateway &&
                                this.renderNetworkInput({
                                    label: $.t(ns + 'gateway'),
                                    name: 'gateway',
                                    errors: errors
                                })
                            }

                        </div>
                    </div>

                );
            }

        });

        var NetworkParameter = React.createClass({
            mixins: [
                commonNetworkMixin,
                NetworkMixin
            ],
            render: function() {
                var network = this.props.parameters,
                    netManager = network.get('net_manager'),
                    segmentation = network.get('segmentation_type'),
                    idRangePrefix = segmentation == 'gre' ? 'gre_id' : 'vlan',
                    errors = (this.props.cluster.get('networkConfiguration').validationError || {}).networking_parameters,
                    fixedVlanStart = network.get('fixed_networks_vlan_start'),
                    fixedSizeValues = _.map(_.range(3, 12), _.partial(Math.pow, 2)),
                    ns = 'cluster_page.network_tab.networking_parameters.';
                return (
                    <div>
                        {netManager ?
                            <div>
                                <legend className='networks'>
                                    {$.t(ns + 'nova_configuration')}
                                </legend>
                                <div>
                                    <div>
                                        {this.renderNetworkInput({
                                            label: $.t(ns + 'fixed_cidr'),
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
                                                    label={$.t(ns + 'fixed_size')}
                                                    name='fixed_network_size'
                                                    value={network.get('fixed_network_size')}
                                                    onChange={this.onInputChange}
                                                    children={_.map(fixedSizeValues, function(value) {
                                                        return <option key={value} value={value}>{value}</option>;
                                                    })}
                                                    disabled={this.props.disabled}
                                                />
                                            </div>
                                            {this.renderNetworkInput({
                                                label: $.t(ns + 'fixed_amount'),
                                                name: 'fixed_networks_amount',
                                                isParameter: true,
                                                errors: errors
                                            })}
                                            <Range
                                                wrapperClassName='network-attribute clearfix'
                                                label={$.t(ns + 'fixed_vlan_range')}
                                                type='mini'
                                                error={this.getParameterError(errors, 'fixed_networks_vlan_start')}
                                                attributeName='fixed_networks_vlan_start'
                                                model={this.props.parameters}
                                                component={this}
                                            />
                                        </div>
                                    :
                                        <div className='clearfix'>
                                            <VlanTagInput
                                                label={$.t(ns + 'use_vlan_tagging_fixed')}
                                                name='fixed_networks_vlan_start'
                                                value={fixedVlanStart}
                                                onInputChange={this.onInputChange}
                                                onCheckboxChange={this.onTaggingChange}
                                                inputError={this.getParameterError(errors, 'fixed_networks_vlan_start')}
                                                attributeName='fixed_networks_vlan_start'
                                                disabled={this.props.disabled}
                                            />
                                        </div>
                                    }
                                </div>
                            </div>
                        :
                            <div>
                                <legend className='networks'>{$.t(ns + 'l2_configuration')}</legend>

                                <Range
                                    wrapperClassName='network-attribute clearfix'
                                    label={$.t(ns + idRangePrefix + '_range')}
                                    type='mini'
                                    error={this.getParameterError(errors, idRangePrefix + '_range')}
                                    attributeName={idRangePrefix + '_range'}
                                    model={this.props.parameters}
                                    component={this}
                                />

                                {this.renderNetworkInput({
                                    label: $.t(ns + 'base_mac'),
                                    name: 'base_mac',
                                    isParameter: true,
                                    errors: errors
                                })}

                                <div>
                                    <legend className='networks'>{$.t(ns + 'l3_configuration')}</legend>
                                </div>
                                <div>
                                    {this.renderNetworkInput({
                                        label: $.t(ns + 'internal_cidr'),
                                        name: 'internal_cidr',
                                        isParameter: true,
                                        errors: errors
                                    })}
                                    {this.renderNetworkInput({
                                        label: $.t(ns + 'internal_gateway'),
                                        name: 'internal_gateway',
                                        isParameter: true,
                                        errors: errors
                                    })}
                                </div>
                            </div>
                        }

                        <Range
                            wrapperClassName='network-attribute floating-ranges'
                            label={$.t(ns + 'floating_ranges')}
                            rowsClassName='floating-ranges-rows'
                            error={this.getParameterError(errors, 'floating_ranges')}
                            attributeName='floating_ranges'
                            model={this.props.parameters}
                            component={this}
                        />
                        <Range
                            type='mini'
                            wrapperClassName='network-attribute dns-nameservers'
                            label={$.t(ns + 'dns_servers')}
                            rowsClassName='dns_nameservers-row'
                            showHeader={false}
                            error={this.getParameterError(errors, 'dns_nameservers')}
                            attributeName='dns_nameservers'
                            model={this.props.parameters}
                            component={this}
                        />

                    </div>
                );
            }
        });

        var NetworkVerification = React.createClass({
            getConnectionStatus: function(task, isFirstConnectionLine) {
                if (!task || (task && task.match({status: 'ready'}))) return 'stop';
                if (task && task.match({status: 'error'}) && !(isFirstConnectionLine &&
                    !(task.match({name: 'verify_networks'}) && !task.get('result').length))) return 'error';
                return 'success';
            },
            render: function() {
                var task = this.props.cluster.task({group: 'network'}),
                    threeItemsArray = ['1', '2', '3'],
                    ns = 'cluster_page.network_tab.verify_networks.';
                return (
                    <div>

                        <div className='page-control-box'>
                            <div className='verification-box'>
                                <hr/>
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
