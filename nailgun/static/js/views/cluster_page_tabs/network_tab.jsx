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
        'jquery',
        'underscore',
        'i18n',
        'backbone',
        'react',
        'models',
        'utils',
        'jsx!component_mixins',
        'jsx!views/controls'
    ],
    function($, _, i18n, Backbone, React, models, utils, componentMixins, controls) {
        'use strict';

        var cx = React.addons.classSet;

        var CommonNetworkMixin = {
            setToProperNetworkModel: function(attribute, value) {
                if (this.props.network) {
                    this.props.networkConfiguration.get('networks').find(this.props.network).set(attribute, value);
                }
                this.props.networkConfiguration.get('networking_parameters').set(attribute, value);
                this.props.networkConfiguration.isValid();
            },
            getProperNetworkModel: function() {
                if (this.props.network) {
                    return this.props.networkConfiguration.get('networks').find(this.props.network);
                }
                return this.props.networkConfiguration.get('networking_parameters');
            }
        };

        var NetworkMixin = {
            getProps: function(attribute, network, networkId) {
                var ns = 'cluster_page.network_tab.network_parameters.',
                    config = {
                        key: attribute,
                        onChange: this.onInputChange,
                        disabled: this.props.disabled,
                        name: attribute,
                        error: this.getNetworkError(networkId, attribute),
                        value: network.get(attribute),
                        label: i18n(ns + attribute)
                    };
                return config;
            },

            onInputChange: function(name, value) {
                if (_.contains(name, 'vlan') || _.contains(name, 'amount')) value = _.parseInt(value);
                if (_.isNaN(value)) value = '';
                this.setToProperNetworkModel(name, value);
            },

            renderNetworkInput: function(config) {
                return (
                    <controls.Input {...config}
                        type='text'
                        wrapperClassName='network-attribute'
                    />
                );
            },

            getNetworkError: function(networkId, attribute) {
                var validationErrors = this.props.networkConfiguration.validationError,
                    errors;
                if (validationErrors) errors = _.has(validationErrors.networks, networkId) ? validationErrors.networks : false;
                return (_.find(errors, attribute) || {})[attribute];
            },

            getParameterError: function(errors, attribute) {
                if (errors && _.contains(attribute, 'start')) {
                    return errors[attribute] ? [errors[attribute]] : undefined;
                }
                return (errors || {})[attribute];
            }
        };

        var Range = React.createClass({
            mixins: [
                CommonNetworkMixin
            ],

            getDefaultProps: function() {
                return {
                    type: 'normal'
                };
            },

            propTypes: {
                wrapperClassName: React.PropTypes.node,
                type: React.PropTypes.oneOf(['normal', 'mini']),
                attributeName: React.PropTypes.string,
                autoIncreaseWith: React.PropTypes.number
            },

            autoCompleteIPRange: function(error, rangeStart, event) {
                var input = event.target;
                if (input.value) return;
                if (_.isUndefined(error)) input.value = rangeStart;
                if (input.setSelectionRange) {
                    var startPos = _.lastIndexOf(rangeStart, '.') + 1;
                    var endPos = rangeStart.length;
                    _.defer(function() { input.setSelectionRange(startPos, endPos); });
                }
            },

            onRangeChange: function(hasManyRanges, rowIndex, attribute, name, newValue) {
                var model = this.getProperNetworkModel(),
                    valuesToSet = _.cloneDeep(model.get(attribute)),
                    valuesToModify = hasManyRanges ? valuesToSet[rowIndex] : valuesToSet;

                // if not only start value can be changed
                if (!_.contains(attribute, 'start')) {
                    // if first range field
                    if (_.contains(name, 'range-start')) {
                        valuesToModify[0] = newValue;
                    // if end field
                    } else if (_.contains(name, 'range-end')) {
                        valuesToModify[1] = newValue;
                    }
                // if any other
                } else {
                    valuesToSet = parseInt(newValue) || newValue;
                }
                if (this.props.verificationError) {
                    this.props.page.removeFinishedNetworkTasks();
                }
                this.setToProperNetworkModel(attribute, valuesToSet);
            },

            addRange: function(attribute, event) {
                event.preventDefault();
                var newValue = _.clone(this.getProperNetworkModel().get(attribute));
                newValue.push(['', '']);
                this.setToProperNetworkModel(attribute, newValue);
            },

            removeRange: function(attribute, rowIndex, event) {
                event.preventDefault();
                var newValue = _.clone(this.getProperNetworkModel().get(attribute));
                newValue.splice(rowIndex, 1);
                this.setToProperNetworkModel(attribute, newValue);
            },

            render: function() {
                var currentError = {},
                    errors = this.props.error || null,
                    attributeName = this.props.attributeName,
                    attribute = this.getProperNetworkModel().get(attributeName),
                    ranges = !_.isUndefined(this.props.autoIncreaseWith) ?
                        [attribute, this.props.autoIncreaseWith ? attribute + this.props.autoIncreaseWith - 1 : ''] :
                        attribute,
                    wrapperClasses = {
                        mini: this.props.type == 'mini'
                    },
                    commonInputRangeConfig = {
                        type: 'text',
                        placeholder: '127.0.0.1',
                        inputClassName: 'range',
                        disabled: this.props.disabled,
                        error: errors && errors[0] ? '' : null,
                        onChange: this.onRangeChange.bind(this, false, 0, attributeName),
                        name: 'range-start_' + attributeName
                    },
                    secondInRangeInputConfig = {
                        name: 'range-end_' + attributeName
                    },
                    verificationError = this.props.verificationError ? this.props.verificationError : null;
                wrapperClasses[this.props.wrapperClassName] = this.props.wrapperClassName;
                return (
                    <div className={cx(wrapperClasses)}>
                        {!this.props.hiddenHeader &&
                            <div className='range-row-header'>
                                <div>{i18n('cluster_page.network_tab.range_start')}</div>
                                <div>{i18n('cluster_page.network_tab.range_end')}</div>
                            </div>
                        }
                        <div className='parameter-name'>{this.props.label}</div>
                        { (this.props.type == 'normal') ?
                            <div className={this.props.rowsClassName}>
                                {_.map(ranges, function(range, index) {
                                    currentError = _.findWhere(errors, {index: index}) || {};
                                    return (
                                        <div className='range-row autocomplete clearfix' key={index}>
                                            <controls.Input {...commonInputRangeConfig}
                                                error={(currentError.start || verificationError) && ''}
                                                value={range[0]}
                                                onChange={this.onRangeChange.bind(this, true, index, attributeName)}
                                            />
                                            <controls.Input {..._.extend(commonInputRangeConfig, secondInRangeInputConfig)}
                                                error={currentError.end && ''}
                                                value={range[1] || verificationError}
                                                onChange={this.onRangeChange.bind(this, true, index, attributeName)}
                                                onFocus={this.autoCompleteIPRange.bind(this, currentError && currentError.start, range[0])}
                                                disabled={this.props.disabled || !!this.props.autoIncreaseWith}
                                            />
                                            <div>
                                                <div className='ip-ranges-control'>
                                                    <button className='btn btn-link ip-ranges-add' disabled={this.props.disabled}
                                                        onClick={this.addRange.bind(this, attributeName)}>
                                                        <i className='icon-plus-circle'></i>
                                                    </button>
                                                </div>
                                                {(ranges.length > 1) &&
                                                    <div className='ip-ranges-control'>
                                                        <button className='btn btn-link ip-ranges-delete' disabled={this.props.disabled}
                                                            onClick={this.removeRange.bind(this, attributeName, index)}>
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
                                <controls.Input {...commonInputRangeConfig}
                                    wrapperClassName={'parameter-control'}
                                    value={ranges[0]}
                                />
                                <controls.Input {..._.extend(commonInputRangeConfig, secondInRangeInputConfig)}
                                    wrapperClassName={'parameter-control'}
                                    disabled={this.props.disabled || _.isNumber(this.props.autoIncreaseWith)}
                                    value={ranges[1]}
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
            mixins: [CommonNetworkMixin],

            onTaggingChange: function(attribute, value) {
                this.props.model.set(attribute, value ? '' : null);
            },

            render: function() {
                return (
                    <div className='network-attribute vlan-tagging'>
                        <controls.Input {...this.props}
                            labelBeforeControl={true}
                            onChange={this.onTaggingChange}
                            type='checkbox'
                            checked={!_.isNull(this.props.value)}
                            error={null}
                        />
                        {!_.isNull(this.props.value) &&
                            <controls.Input {...this.props}
                                label={false}
                                onChange={this.props.onInputChange}
                                type ='text'
                            />
                        }
                    </div>
                );
            }
        });

        var NetworkTab = React.createClass({
            mixins: [
                React.BackboneMixin('model', 'change:status'),
                React.BackboneMixin({
                    modelOrCollection: function(props) {
                        return props.model.get('networkConfiguration');
                    },
                    renderOn: 'change invalid'
                }),
                React.BackboneMixin({
                    modelOrCollection: function(props) {
                        return props.model.get('networkConfiguration').get('networking_parameters');
                    },
                    renderOn: 'change'
                }),
                React.BackboneMixin({
                    modelOrCollection: function(props) {
                        return props.model.get('networkConfiguration').get('networks');
                    },
                    renderOn: 'change reset'
                }),
                React.BackboneMixin({
                    modelOrCollection: function(props) {
                        return props.model.get('tasks');
                    },
                    renderOn: 'add remove change:status'
                }),
                React.BackboneMixin({
                    modelOrCollection: function(props) {
                        return props.model.task({group: ['network', 'deployment'], status: 'running'});
                    }
                }),
                componentMixins.pollingMixin(3)
            ],

            componentWillMount: function() {
                this.networkConfiguration = this.props.model.get('networkConfiguration');
            },

            shouldDataBeFetched: function() {
                return !!this.props.model.task({group: 'network', status: 'running'});
            },

            fetchData: function() {
                return this.props.model.task({group: 'network', status: 'running'}).fetch();
            },

            getInitialState: function() {
                return {
                    loading: true,
                    actionInProgress: false
                };
            },

            loadInitialConfiguration: function() {
                // FIXME(morale): it's a bad practice to have mutable props, that's why we
                // should think about other solution here
                this.networkConfiguration.get('networks').reset(_.cloneDeep(this.initialConfiguration.networks));
                this.networkConfiguration.get('networking_parameters').set(_.cloneDeep(this.initialConfiguration.networking_parameters));
            },

            updateInitialConfiguration: function() {
                this.initialConfiguration = _.cloneDeep(this.networkConfiguration.toJSON());
            },

            prepareIpRanges: function() {
                var removeEmptyRanges = function(ranges) {
                    return _.filter(ranges, function(range) {return _.compact(range).length;});
                };
                this.networkConfiguration.get('networks').each(function(network) {
                    if (network.get('meta').notation == 'ip_ranges') {
                        network.set({ip_ranges: removeEmptyRanges(network.get('ip_ranges'))});
                    }
                });
                var floatingRanges = this.networkConfiguration.get('networking_parameters').get('floating_ranges');
                if (floatingRanges) {
                    this.networkConfiguration.get('networking_parameters').set({floating_ranges: removeEmptyRanges(floatingRanges)});
                }
            },

            componentDidMount: function() {
                $.when(this.props.model.get('settings').fetch({cache: true}), this.networkConfiguration.fetch({cache: true})).done(_.bind(function() {
                    this.updateInitialConfiguration();
                    this.setState({loading: false});
                }, this));
            },

            isLocked: function() {
                return !!this.props.model.task({group: ['deployment', 'network'], status: 'running'}) ||
                    !this.props.model.isAvailableForSettingsChanges() || this.state.actionInProgress;
            },

            hasChanges: function() {
                return !_.isEqual(this.initialConfiguration, this.networkConfiguration.toJSON());
            },

            onManagerChange: function(name, value) {
                var networkingParams = this.networkConfiguration.get('networking_parameters'),
                    fixedAmount = this.networkConfiguration.get('networking_parameters').get('fixed_networks_amount') || 1;
                networkingParams.set({
                    net_manager: value,
                    fixed_networks_amount: value == 'FlatDHCPManager' ? 1 : fixedAmount
                });
            },

            verifyNetworks: function(event) {
                event.preventDefault();
                this.setState({actionInProgress: true});
                this.prepareIpRanges();
                this.props.page.removeFinishedNetworkTasks().always(_.bind(this.startVerification, this));
            },

            startVerification: function() {
                var task = new models.Task(),
                    options = {
                        method: 'PUT',
                        url: _.result(this.networkConfiguration, 'url') + '/verify',
                        data: JSON.stringify(this.networkConfiguration)
                    };
                task.save({}, options)
                    .fail(function() {
                        utils.showErrorDialog({
                            title: i18n('cluster_page.network_tab.verify_networks.verification_error.title'),
                            message: i18n('cluster_page.network_tab.verify_networks.verification_error.start_verification_warning')
                        });
                    })
                    .always(_.bind(function() {
                        this.props.model.fetchRelated('tasks').done(_.bind(function() {
                            this.startPolling();
                            this.setState({actionInProgress: false});
                        }, this));
                    }, this));
            },

            revertChanges: function(event) {
                event.preventDefault();
                this.loadInitialConfiguration();
                this.props.page.removeFinishedNetworkTasks();
                this.networkConfiguration.isValid();
            },

            applyChanges: function(event) {
                event.preventDefault();
                this.setState({actionInProgress: true});
                this.prepareIpRanges();
                if (!this.networkConfiguration.validationError) {
                    return Backbone.sync('update', this.networkConfiguration)
                        .done(_.bind(function(task) {
                            if (task && task.status == 'error') {
                                this.props.page.removeFinishedNetworkTasks().always(_.bind(function() {
                                    this.props.model.fetch();
                                }, this));
                            } else {
                                this.updateInitialConfiguration();
                                this.props.model.fetch();
                                this.props.model.fetchRelated('tasks');
                            }
                        }, this))
                        .fail(_.bind(function() {
                            utils.showErrorDialog({title: i18n('cluster_page.network_tab.verify_networks.verification_error.title')});
                            this.props.model.fetch();
                            this.props.model.fetchRelated('tasks');
                        }, this))
                        .always(_.bind(function() {
                            this.setState({actionInProgress: false});
                        }, this));
                }
                return $.Deferred.deferred.resolve();
            },

            renderNetwork: function(network) {
                var errorFields = this.getVerificationErrors();
                return <Network
                    key={network.id}
                    network={network}
                    networkConfiguration={this.networkConfiguration}
                    errors={(this.networkConfiguration.validationError || {}).networks}
                    disabled={this.isLocked()}
                    verificationErrorField={_.pluck(_.where(errorFields, {network: network.id}), 'field')}
                    page={this.props.page}
                    removeTasks={this.props.page.removeFinishedNetworkTasks.bind(this)}
                />;
            },

            renderButtons: function() {
                var error = this.networkConfiguration.validationError,
                    isLocked = this.isLocked(),
                    hasChanges = this.hasChanges();
                return (
                    <div className='row'>
                        <div className='page-control-box'>
                            <div className='page-control-button-placeholder'>
                                <button key='verify_networks' className='btn verify-networks-btn' onClick={this.verifyNetworks}
                                    disabled={error || isLocked}>
                                        {i18n('cluster_page.network_tab.verify_networks_button')}
                                </button>
                                <button key='revert_changes' className='btn btn-revert-changes' onClick={this.revertChanges}
                                    disabled={isLocked || !hasChanges}>
                                        {i18n('common.cancel_changes_button')}
                                </button>
                                <button key='apply_changes' className='btn btn-success apply-btn' onClick={this.applyChanges}
                                    disabled={error || isLocked || !hasChanges}>
                                        {i18n('common.save_settings_button')}
                                </button>
                            </div>
                        </div>
                    </div>
                );
            },

            getVerificationErrors: function() {
                var task = this.props.model.task({group: 'network', status: 'error'}),
                    fieldsWithVerificationErrors = [];
                if (task && task.get('result').length) {
                    _.each(task.get('result'), function(verificationError) {
                        _.each(verificationError.ids, function(networkId) {
                            _.each(verificationError.errors, function(field) {
                                fieldsWithVerificationErrors.push({network: networkId, field: field});
                            }, this);
                        }, this);
                    }, this);
                }
                return fieldsWithVerificationErrors;
            },

            render: function() {
                var cluster, networkingParameters, l23Provider, managers,
                    isLocked = this.isLocked(),
                    classes = {
                        'network-settings wrapper': true,
                        'changes-locked': isLocked
                    };
                if (!this.state.loading) {
                    cluster = this.props.model;
                    networkingParameters = this.networkConfiguration.get('networking_parameters');
                    l23Provider = networkingParameters.get('net_l23_provider');
                    var manager = networkingParameters.get('net_manager');
                    managers = [
                        {
                            label: i18n('cluster_page.network_tab.flatdhcp_manager'),
                            data: 'FlatDHCPManager',
                            checked: manager == 'FlatDHCPManager',
                            disabled: isLocked
                        },
                        {
                            label: i18n('cluster_page.network_tab.vlan_manager'),
                            data: 'VlanManager',
                            checked: manager == 'VlanManager',
                            disabled: isLocked
                        }
                    ];
                }

                if (!this.hasChanges()) {
                    this.props.page.removeFinishedNetworkTasks();
                }

                return (
                    <div className={cx(classes)}>
                        <h3>{i18n('cluster_page.network_tab.title')}</h3>
                        {this.state.loading ?
                            <controls.ProgressBar />
                        :
                            <div>
                                <form id='network-form'>
                                    <div className='radio-checkbox-group'>
                                        {(cluster.get('net_provider') == 'nova_network') ?
                                            <controls.RadioGroup
                                                key='net_provider'
                                                name='net_provider'
                                                values={managers}
                                                onChange={this.onManagerChange}
                                            />
                                        :
                                            <span className='network-segment-type'>
                                                {(l23Provider == 'nsx') ?
                                                    i18n('cluster_page.network_tab.neutron_l23_provider', {l23_provider: l23Provider.toUpperCase()})
                                                    :
                                                    i18n('cluster_page.network_tab.neutron_segmentation', {segment_type: networkingParameters.get('segmentation_type').toUpperCase()})
                                                }
                                            </span>
                                        }

                                    </div>
                                    <div className='networks-table'>
                                        {this.networkConfiguration.get('networks').map(this.renderNetwork, this)}
                                    </div>
                                    <div className='networking-parameters'>
                                        <NetworkingParameters
                                            key='network_parameter'
                                            networkConfiguration={this.networkConfiguration}
                                            errors={(this.networkConfiguration.validationError || {}).networking_parameters}
                                            disabled={this.isLocked()}
                                        />
                                    </div>
                                    <div className='verification-control'>
                                        <NetworkVerification
                                            key='network_verification'
                                            task={cluster.task({group: 'network'})}
                                            networks={this.networkConfiguration.get('networks')}
                                        />
                                    </div>
                                    {this.renderButtons()}
                                </form>
                            </div>
                        }
                    </div>
                );
            }
        });

        var Network = React.createClass({
            mixins: [
                NetworkMixin,
                CommonNetworkMixin
            ],

            render: function() {
                var network = this.props.network,
                    networkConfig = network.get('meta'),
                    networkId = network.id;
                if (!networkConfig.configurable) return null;
                var vlanTagging = network.get('vlan_start'),
                    ipRangesLabel = 'ip_ranges',
                    ns = 'cluster_page.network_tab.network_parameters.';
                return (
                    <div name={networkId}>
                        <legend className='networks'>{i18n('network.' + network.get('name'))}</legend>
                        <div className={network.get('name')}>
                            {(networkConfig.notation == ipRangesLabel) &&
                                <Range
                                    {...this.getProps(ipRangesLabel, network, networkId)}
                                        wrapperClassName='network-attribute ip_ranges'
                                        rowsClassName='ip-ranges-rows'
                                        verificationError={_.contains(this.props.verificationErrorField, 'ip_ranges')}
                                        attributeName={ipRangesLabel}
                                        network={this.props.network}
                                        networkConfiguration={this.props.networkConfiguration}
                                        page={this.props.page}
                                />
                            }
                            {this.renderNetworkInput(this.getProps('cidr', network, networkId))}
                            <VlanTagInput
                                {...this.getProps('vlan_start', network, networkId)}
                                    label={i18n(ns + 'use_vlan_tagging')}
                                    value={vlanTagging}
                                    model={this.props.network}
                                    onInputChange={this.onInputChange}
                            />
                            {networkConfig.use_gateway &&
                                this.renderNetworkInput(this.getProps('gateway', network, networkId))
                            }
                        </div>
                    </div>
                );
            }
        });

        var NetworkingParameters = React.createClass({
            mixins: [
                NetworkMixin,
                CommonNetworkMixin
            ],
            render: function() {
                var networkParameters = this.props.networkConfiguration.get('networking_parameters'),
                    manager = networkParameters.get('net_manager'),
                    idRangePrefix = networkParameters.get('segmentation_type') == 'gre' ? 'gre_id' : 'vlan',
                    errors = (this.props.networkConfiguration.validationError || {}).networking_parameters,
                    fixedNetworkSizeValues = _.map(_.range(3, 12), _.partial(Math.pow, 2)),
                    ns = 'cluster_page.network_tab.networking_parameters.';
                return (
                    <div>
                        {manager ?
                            <div>
                                <legend className='networks'>
                                    {i18n(ns + 'nova_configuration')}
                                </legend>
                                <div>
                                    <div>
                                        {this.renderNetworkInput({
                                            label: i18n(ns + 'fixed_cidr'),
                                            name: 'fixed_networks_cidr',
                                            error: this.getParameterError(errors, 'fixed_networks_cidr'),
                                            value: networkParameters.get('fixed_networks_cidr')
                                        })}
                                    </div>
                                    {(manager == 'VlanManager') ?
                                        <div>
                                            <div className='network-attribute'>
                                                <controls.Input
                                                    type='select'
                                                    label={i18n(ns + 'fixed_size')}
                                                    name='fixed_network_size'
                                                    value={networkParameters.get('fixed_network_size')}
                                                    onChange={this.onInputChange}
                                                    children={_.map(fixedNetworkSizeValues, function(value) {
                                                        return <option key={value} value={value}>{value}</option>;
                                                    })}
                                                    disabled={this.props.disabled}
                                                />
                                            </div>
                                            {this.renderNetworkInput({
                                                label: i18n(ns + 'fixed_amount'),
                                                name: 'fixed_networks_amount',
                                                error: this.getParameterError(errors, 'fixed_networks_amount'),
                                                value: networkParameters.get('fixed_networks_amount')
                                            })}
                                            <Range
                                                wrapperClassName='network-attribute clearfix'
                                                label={i18n(ns + 'fixed_vlan_range')}
                                                type='mini'
                                                error={this.getParameterError(errors, 'fixed_networks_vlan_start')}
                                                attributeName='fixed_networks_vlan_start'
                                                disabled={this.props.disabled}
                                                autoIncreaseWith={parseInt(networkParameters.get('fixed_networks_amount')) || 0}
                                                networkConfiguration={this.props.networkConfiguration}
                                            />
                                        </div>
                                    :
                                        <div className='clearfix'>
                                            <VlanTagInput
                                                label={i18n(ns + 'use_vlan_tagging_fixed')}
                                                name='fixed_networks_vlan_start'
                                                value={networkParameters.get('fixed_networks_vlan_start')}
                                                onInputChange={this.onInputChange}
                                                inputError={this.getParameterError(errors, 'fixed_networks_vlan_start')}
                                                disabled={this.props.disabled}
                                                model={networkParameters}
                                            />
                                        </div>
                                    }
                                </div>
                            </div>
                        :
                            <div>
                                <legend className='networks'>{i18n(ns + 'l2_configuration')}</legend>
                                <Range
                                    wrapperClassName='network-attribute clearfix'
                                    label={i18n(ns + idRangePrefix + '_range')}
                                    type='mini'
                                    error={this.getParameterError(errors, idRangePrefix + '_range')}
                                    attributeName={idRangePrefix + '_range'}
                                    disabled={this.props.disabled}
                                    networkConfiguration={this.props.networkConfiguration}
                                />
                                {this.renderNetworkInput({
                                    label: i18n(ns + 'base_mac'),
                                    name: 'base_mac',
                                    error: this.getParameterError(errors, 'base_mac')
                                })}
                                <div>
                                    <legend className='networks'>{i18n(ns + 'l3_configuration')}</legend>
                                </div>
                                <div>
                                    {this.renderNetworkInput({
                                        label: i18n(ns + 'internal_cidr'),
                                        name: 'internal_cidr',
                                        error: this.getParameterError(errors, 'internal_cidr')
                                    })}
                                    {this.renderNetworkInput({
                                        label: i18n(ns + 'internal_gateway'),
                                        name: 'internal_gateway',
                                        error: this.getParameterError(errors, 'internal_gateway')
                                    })}
                                </div>
                            </div>
                        }

                        <Range
                            wrapperClassName='network-attribute floating-ranges'
                            label={i18n(ns + 'floating_ranges')}
                            rowsClassName='floating-ranges-rows'
                            error={this.getParameterError(errors, 'floating_ranges')}
                            attributeName='floating_ranges'
                            disabled={this.props.disabled}
                            networkConfiguration={this.props.networkConfiguration}
                        />
                        <Range
                            type='mini'
                            wrapperClassName='network-attribute dns-nameservers'
                            label={i18n(ns + 'dns_servers')}
                            rowsClassName='dns_nameservers-row'
                            hiddenHeader={true}
                            error={this.getParameterError(errors, 'dns_nameservers')}
                            attributeName='dns_nameservers'
                            disabled={this.props.disabled}
                            networkConfiguration={this.props.networkConfiguration}
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
                var task = this.props.task,
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
                                        return <li key={index}>{i18n(ns + 'step_' + index)}</li>;
                                    }, this)}
                                </div>

                                {(task && task.match({name: 'verify_networks', status: 'ready'})) ?
                                    <div className='alert alert-success enable-selection'>
                                        {i18n(ns + 'success_alert')}
                                    </div>
                                : (task && task.match({status: 'error'})) &&
                                    <div className='alert alert-error enable-selection'>
                                        <span>
                                            {i18n(ns + 'fail_alert')}
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
                                                return i18n(ns + attr);
                                            })}
                                            body={
                                                _.map(task.get('result'), function(node) {
                                                    var absentVlans = _.map(node.absent_vlans, function(vlan) {
                                                        return vlan || i18n('cluster_page.network_tab.untagged');
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
