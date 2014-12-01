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

        var NetworkMixin = {
            onInputChange: function(name, value) {
                if (_.contains(name, 'vlan') || _.contains(name, 'amount')) value = _.parseInt(value);
                if (_.isNaN(value)) value = '';
                this.props.model.set(name, value);
                this.props.networkConfiguration.isValid();
                $('input[type=text]').removeClass('error');
            },

            onTaggingChange: function(attribute, value) {
                this.props.model.set(attribute, value ? '' : null);
                this.props.networkConfiguration.isValid();
            },

            renderNetworkInput: function(config) {
                return (
                    <controls.Input
                        key={config.name}
                        type='text'
                        name={config.name}
                        label={config.label}
                        value={this.props.model.get(config.name)}
                        wrapperClassName='network-attribute'
                        onChange={this.onInputChange}
                        error={config.errors}
                        disabled={this.props.disabled}
                    />
                );
            },

            getNetworkError: function(errors, attribute) {
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
                React.BackboneMixin({
                    modelOrCollection: function(props) {
                        return props.model;
                    },
                    renderOn: 'change'
                })
            ],

            getDefaultProps: function() {
                return {
                    type: 'normal',
                    hiddenHeader: false
                };
            },

            propTypes: {
                wrapperClassName: React.PropTypes.renderable,
                type: React.PropTypes.oneOf(['normal', 'mini']),
                attributeName: React.PropTypes.string
            },

            forcingNetworkConfigUpdate: function() {
                $('input[type=text]').removeClass('error');
                this.props.networkConfiguration.isValid();
                this.props.networkConfiguration.trigger('change');
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
                var valuesToSet = this.props.model.get(attribute),
                    valuesToModify = hasManyRanges ? valuesToSet[rowIndex] : valuesToSet;
                if (!_.contains(attribute, 'start')) {
                    if (_.contains(name,  'range-start')) {
                        valuesToModify[0] = newValue;
                    } else if (_.contains(name, 'range-end')) {
                        valuesToModify[1] = newValue;
                    }
                } else {
                    valuesToSet = parseInt(newValue) || newValue;
                }
                this.props.model.set(attribute, valuesToSet);
                this.forcingNetworkConfigUpdate();
            },

            addRange: function(attribute, event) {
                event.preventDefault();
                this.props.model.get(attribute).push(['', '']);
                this.props.networkConfiguration.trigger('change');
            },

            removeRange: function(attribute, rowIndex) {
                this.props.model.get(attribute).splice(rowIndex, 1);
                this.forcingNetworkConfigUpdate();
            },

            render: function() {
                var currentError = {},
                    errors = this.props.error || null,
                    attributeName = this.props.attributeName,
                    attribute =  this.props.model.get(attributeName),
                    ranges = this.props.autoIncreaseWith ? [attribute,
                        (_.isString(attribute) && _.isEmpty(attribute)) ? '' : attribute + this.props.autoIncreaseWith - 1]
                        : attribute,
                    wrapperClasses = {
                        mini: this.props.type == 'mini'
                    };
                wrapperClasses[this.props.wrapperClassName] = this.props.wrapperClassName;
                return (
                    <div className={cx(wrapperClasses)}>
                        {!this.props.hiddenHeader &&
                            <div className='range-row-header'>
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
                                                name={'range-start' + '_' + attributeName}
                                                placeholder='127.0.0.1'
                                                value={range[0]}
                                                inputClassName='range'
                                                onChange={this.onRangeChange.bind(this, true, index, attributeName)}
                                                disabled={this.props.disabled}
                                            />
                                            <controls.Input
                                                type='text'
                                                error={currentError.end && ''}
                                                name={'range-end' + '_' + attributeName}
                                                placeholder='127.0.0.1'
                                                value={range[1]}
                                                inputClassName='range'
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
                                <controls.Input
                                    type='text'
                                    wrapperClassName={'parameter-control'}
                                    inputClassName='range'
                                    name={'range-start' + '_' + attributeName}
                                    value={ranges[0]}
                                    error={errors && errors[0] ? '' : null}
                                    onChange={this.onRangeChange.bind(this, false, 0, attributeName)}
                                    disabled={this.props.disabled}
                                />
                                <controls.Input
                                    type='text'
                                    wrapperClassName={'parameter-control'}
                                    inputClassName='range'
                                    name={'range-end' + '_' + attributeName}
                                    value={ranges[1]}
                                    error={errors && errors[0] ? '' : null}
                                    onChange={this.onRangeChange.bind(this, false, 0, attributeName)}
                                    disabled={this.props.disabled || !!this.props.autoIncreaseWith}
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
                    <div className='network-attribute vlan-tagging'>
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
                                    error={this.props.inputError}
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
                    },
                    renderOn: 'change'
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
                    renderOn: 'change'
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

            showVerificationErrors: function(task) {
                task = task || this.props.model.task({group: 'network', status: 'error'});
                if (task && task.get('result').length) {
                    _.each(task.get('result'), function(verificationError) {
                        _.each(verificationError.ids, function(networkId) {
                            _.each(verificationError.errors, function(field) {
                                $('.networks-table [name=' + networkId + '] input[name="' + field + '"]').addClass('error');
                            }, this);
                        }, this);
                    }, this);
                }
            },

            componentDidMount: function() {
                $.when(this.props.model.get('settings').fetch({cache: true}), this.props.model.get('networkConfiguration').fetch({cache: true})).done(_.bind(function() {
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
                networkingParams.set({fixed_networks_amount: value == 'FlatDHCPManager' ? 1 : fixedAmount});
                this.props.model.get('networkConfiguration').isValid();
            },

            verifyNetworks: function(event) {
                event.preventDefault();
                if (!this.props.model.get('networkConfiguration').validationError) {
                    this.props.page.removeFinishedNetworkTasks().always(this.startVerification);
                }
            },

            startVerification: function() {
                var task = new models.Task(),
                    networkConfiguration = this.props.model.get('networkConfiguration'),
                    options = {
                        method: 'PUT',
                        url: _.result(networkConfiguration, 'url') + '/verify',
                        data: JSON.stringify(networkConfiguration)
                    };
                task.save({}, options)
                    .fail(_.bind(function() {
                        utils.showErrorDialog({
                            title: $.t('cluster_page.network_tab.verify_networks.verification_error.title'),
                            message: $.t('cluster_page.network_tab.verify_networks.verification_error.start_verification_warning')
                        });
                    }, this))
                    .always(_.bind(function() {
                        this.props.model.fetchRelated('tasks').done(_.bind(function() {
                            this.startPolling();
                            this.showVerificationErrors();
                        }, this));
                    }, this));
            },

            revertChanges: function(event) {
                event.preventDefault();
                this.loadInitialConfiguration();
                this.props.page.removeFinishedNetworkTasks();
            },

            applyChanges: function(event) {
                event.preventDefault();
                var networkConfiguration = this.props.model.get('networkConfiguration');
                if (!networkConfiguration.validationError) {
                    return Backbone.sync('update', networkConfiguration)
                        .done(_.bind(function(task) {
                            if (task && task.status == 'error') {
                                this.forceUpdate();
                                this.showVerificationErrors(new Backbone.Model(task));
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
                        }, this))
                        .fail(_.bind(function() {
                            utils.showErrorDialog({title: $.t('cluster_page.network_tab.verify_networks.verification_error.title')});
                            this.props.model.fetch();
                            this.props.model.fetchRelated('tasks');
                        }, this));
                }
                return $.Deferred.deferred.resolve();
            },

            renderNetwork: function(network) {
                var networkConfiguration = this.props.model.get('networkConfiguration');
                return <Network
                    key={network.id}
                    model={network}
                    networkConfiguration={networkConfiguration}
                    errors={(networkConfiguration.validationError || {}).networks}
                    disabled={this.isLocked()}
                />;
            },

            renderButtons: function() {
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
                var cluster, networkConfiguration, networkingParameters, l23Provider, managers,
                    classes = {
                        'network-settings wrapper': true,
                        'changes-locked': this.isLocked()
                    };
                if (!this.state.loading) {
                    cluster = this.props.model;
                    networkConfiguration = cluster.get('networkConfiguration');
                    networkingParameters = networkConfiguration.get('networking_parameters');
                    l23Provider = networkingParameters.get('net_l23_provider');
                    var manager = networkingParameters.get('net_manager');
                    managers = [
                        {
                            label: $.t('cluster_page.network_tab.flatdhcp_manager'),
                            data: 'FlatDHCPManager',
                            checked: manager == 'FlatDHCPManager',
                            disabled: this.isLocked()
                        },
                        {
                            label: $.t('cluster_page.network_tab.vlan_manager'),
                            data: 'VlanManager',
                            checked: manager == 'VlanManager',
                            disabled: this.isLocked()
                        }
                    ];
                }
                return (
                    <div className={cx(classes)}>
                        <h3>{$.t('cluster_page.network_tab.title')}</h3>
                        {this.state.loading ?
                            <controls.ProgressBar />
                        :
                            <div>
                                <form id="network-form">
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
                                                $.t('cluster_page.network_tab.neutron_l23_provider', {l23_provider: l23Provider.toUpperCase()})
                                                :
                                                $.t('cluster_page.network_tab.neutron_segmentation', {segment_type: networkingParameters.get('segmentation_type').toUpperCase()})
                                            }
                                        </span>
                                    }

                                </div>
                                <div className='networks-table'>
                                    {networkConfiguration.get('networks').map(this.renderNetwork, this)}
                                </div>
                                <div className='networking-parameters'>
                                    <NetworkingParameters
                                        key='network_parameter'
                                        model={networkingParameters}
                                        networkConfiguration={networkConfiguration}
                                        errors={(networkConfiguration.validationError || {}).networking_parameters}
                                        disabled={this.isLocked()}
                                    />
                                </div>
                                <div className='verification-control'>
                                    <NetworkVerification
                                        key='network_verification'
                                        task={cluster.task({group: 'network'})}
                                        networks={networkConfiguration.get('networks')}
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
            mixins: [NetworkMixin],
            render: function() {
                var network = this.props.model,
                    networkConfig = network.get('meta');
                if (!networkConfig.configurable) return null;
                var vlanTagging = network.get('vlan_start'),
                    ipRangesLabel = 'ip_ranges',
                    ns = 'cluster_page.network_tab.network_parameters.',
                    errors = this.props.networkConfiguration.validationError;
                if (errors) {
                    errors = _.has(errors.networks, network.id) ? errors.networks : false;
                }
                return (
                    <div name={network.id}>
                        <legend className='networks'>{$.t('network.' +  network.get('name'))}</legend>
                        <div className={network.get('name')}>
                            {(networkConfig.notation == ipRangesLabel) &&
                                <Range
                                    wrapperClassName={'network-attribute ip_ranges'}
                                    label={$.t(ns + ipRangesLabel)}
                                    rowsClassName='ip-ranges-rows'
                                    error={this.getNetworkError(errors, ipRangesLabel)}
                                    attributeName={ipRangesLabel}
                                    model={network}
                                    disabled={this.props.disabled}
                                    networkConfiguration={this.props.networkConfiguration}
                                />
                            }
                            {this.renderNetworkInput({
                                label: $.t(ns + 'cidr'),
                                name: 'cidr',
                                errors: this.getNetworkError(errors, 'cidr')
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
                                    errors: this.getNetworkError(errors, 'gateway')
                                })
                            }
                        </div>
                    </div>
                );
            }
        });

        var NetworkingParameters = React.createClass({
            mixins: [NetworkMixin],
            render: function() {
                var manager = this.props.model.get('net_manager'),
                    idRangePrefix = this.props.model.get('segmentation_type') == 'gre' ? 'gre_id' : 'vlan',
                    errors = (this.props.networkConfiguration.validationError || {}).networking_parameters,
                    fixedNetworkSizeValues = _.map(_.range(3, 12), _.partial(Math.pow, 2)),
                    ns = 'cluster_page.network_tab.networking_parameters.';
                return (
                    <div>
                        {manager ?
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
                                            errors: this.getParameterError(errors, 'fixed_networks_cidr')
                                        })}
                                    </div>
                                    {(manager == 'VlanManager') ?
                                        <div>
                                            <div className='network-attribute'>
                                                <controls.Input
                                                    type='select'
                                                    label={$.t(ns + 'fixed_size')}
                                                    name='fixed_network_size'
                                                    value={this.props.model.get('fixed_network_size')}
                                                    onChange={this.onInputChange}
                                                    children={_.map(fixedNetworkSizeValues, function(value) {
                                                        return <option key={value} value={value}>{value}</option>;
                                                    })}
                                                    disabled={this.props.disabled}
                                                />
                                            </div>
                                            {this.renderNetworkInput({
                                                label: $.t(ns + 'fixed_amount'),
                                                name: 'fixed_networks_amount',
                                                isParameter: true,
                                                errors: this.getParameterError(errors, 'fixed_networks_amount')
                                            })}
                                            <Range
                                                wrapperClassName='network-attribute clearfix'
                                                label={$.t(ns + 'fixed_vlan_range')}
                                                type='mini'
                                                error={this.getParameterError(errors, 'fixed_networks_vlan_start')}
                                                attributeName='fixed_networks_vlan_start'
                                                model={this.props.model}
                                                disabled={this.props.disabled}
                                                autoIncreaseWith={this.props.model.get('fixed_networks_amount')}
                                                networkConfiguration={this.props.networkConfiguration}
                                            />
                                        </div>
                                    :
                                        <div className='clearfix'>
                                            <VlanTagInput
                                                label={$.t(ns + 'use_vlan_tagging_fixed')}
                                                name='fixed_networks_vlan_start'
                                                value={this.props.model.get('fixed_networks_vlan_start')}
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
                                    model={this.props.model}
                                    disabled={this.props.disabled}
                                    networkConfiguration={this.props.networkConfiguration}
                                />
                                {this.renderNetworkInput({
                                    label: $.t(ns + 'base_mac'),
                                    name: 'base_mac',
                                    isParameter: true,
                                    errors: this.getParameterError(errors, 'base_mac')
                                })}
                                <div>
                                    <legend className='networks'>{$.t(ns + 'l3_configuration')}</legend>
                                </div>
                                <div>
                                    {this.renderNetworkInput({
                                        label: $.t(ns + 'internal_cidr'),
                                        name: 'internal_cidr',
                                        isParameter: true,
                                        errors: this.getParameterError(errors, 'internal_cidr')
                                    })}
                                    {this.renderNetworkInput({
                                        label: $.t(ns + 'internal_gateway'),
                                        name: 'internal_gateway',
                                        isParameter: true,
                                        errors: this.getParameterError(errors, 'internal_gateway')
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
                            model={this.props.model}
                            disabled={this.props.disabled}
                            networkConfiguration={this.props.networkConfiguration}
                        />
                        <Range
                            type='mini'
                            wrapperClassName='network-attribute dns-nameservers'
                            label={$.t(ns + 'dns_servers')}
                            rowsClassName='dns_nameservers-row'
                            hiddenHeader={true}
                            error={this.getParameterError(errors, 'dns_nameservers')}
                            attributeName='dns_nameservers'
                            model={this.props.model}
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
