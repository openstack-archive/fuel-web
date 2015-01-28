/*
 * Copyright 2015 Mirantis, Inc.
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

    var NetworkModelManipulationMixin = {
        setValue: function(attribute, value, props) {
            if (props && props.integerValue && !_.isNull(value)) {
                var convertedToNumberValue = parseInt(value);
                value = _.isNaN(convertedToNumberValue) ? '' : convertedToNumberValue;
            }
            this.getModel().set(attribute, value);
            app.page.removeFinishedNetworkTasks();
        },
        getModel: function() {
            if (this.props.network) {
                return this.props.networkConfiguration.get('networks').find(this.props.network);
            }
            return this.props.networkConfiguration.get('networking_parameters');
        }
    };

    var NetworkInputsMixin = {
        composeProps: function(attribute, isRange) {
            var network = this.props.network,
                ns = 'cluster_page.network_tab.' + (network ? 'network' : 'networking_parameters') + '.',
                error = this.getError(attribute) || null;

            // in case of verification error we need to pass an empty string to highlight the field only
            // but not overwriting validation error
            if (!error && _.contains(this.props.verificationErrorField, attribute)) {
                error = '';
            }
            return {
                key: attribute,
                onChange: this.setValue,
                disabled: this.props.disabled,
                name: attribute,
                label: i18n(ns + attribute),
                value: this.getModel().get(attribute),
                network: network,
                networkConfiguration: this.props.networkConfiguration,
                wrapperClassName: isRange ? 'network-attribute ' + attribute : false,
                error: error
            };
        },
        renderInput: function(attribute, isInteger) {
            return (
                <controls.Input {...this.composeProps(attribute)}
                    type='text'
                    wrapperClassName='network-attribute'
                    integerValue={isInteger}
                />
            );
        },
        getError: function(attribute) {
            var validationErrors = this.props.networkConfiguration.validationError;
            if (!validationErrors) return null;

            var network = this.props.network,
                errors;

            if (network) {
                errors = validationErrors.networks && validationErrors.networks[network.id];
                return errors && errors[attribute] || null;
            }

            errors = (validationErrors.networking_parameters || {})[attribute];
            if (!errors) {
                return null;
            }

            // specific format needed for vlan_start errors
            if (attribute == 'fixed_networks_vlan_start') {
                return [errors];
            }
            return errors;
        }
    };

    var Range = React.createClass({
        mixins: [
            NetworkModelManipulationMixin
        ],
        getDefaultProps: function() {
            return {
                type: 'extendable'
            };
        },
        propTypes: {
            wrapperClassName: React.PropTypes.node,
            type: React.PropTypes.oneOf(['normal', 'extendable']),
            name: React.PropTypes.string,
            autoIncreaseWith: React.PropTypes.number,
            integerValue: React.PropTypes.bool,
            directSetValue: React.PropTypes.bool
        },
        getInitialState: function() {
            return {pendingFocus: false};
        },
        componentDidUpdate: function() {
            // this glitch is needed to fix
            // when pressing '+' or '-' buttons button remains focused
            if (this.props.type == 'extendable') {
                if ((this.getModel().get(this.props.name).length > 1) && this.state.pendingFocus) {
                    $(_.findLast(this.refs).getInputDOMNode()).focus();
                    this.setState({pendingFocus: false});
                }
            }
        },
        autoCompleteIPRange: function(error, rangeStart, event) {
            var input = event.target;
            if (input.value) return;
            if (_.isUndefined(error)) input.value = rangeStart;
            if (input.setSelectionRange) {
                var startPos = _.lastIndexOf(rangeStart, '.') + 1,
                    endPos = rangeStart.length;
                input.setSelectionRange(startPos, endPos);
            }
        },
        onRangeChange: function(hasManyRanges, rowIndex, attribute, name, newValue) {
            var model = this.getModel(),
                valuesToSet = _.cloneDeep(model.get(attribute)),
                valuesToModify = hasManyRanges ? valuesToSet[rowIndex] : valuesToSet;

            newValue = this.props.integerValue ? parseInt(newValue) : newValue;
            if (this.props.directSetValue) {
                valuesToSet = newValue;
            } else {
                // if first range field
                if (_.contains(name, 'range-start')) {
                    valuesToModify[0] = newValue;
                    // if end field
                } else if (_.contains(name, 'range-end')) {
                    valuesToModify[1] = newValue;
                }
            }

            this.setValue(attribute, valuesToSet, this.props);
        },
        addRange: function(attribute, event) {
            event.preventDefault();
            var newValue = _.clone(this.getModel().get(attribute));
            newValue.push(['', '']);
            this.setValue(attribute, newValue);
            this.setState({pendingFocus: true});
        },
        removeRange: function(attribute, rowIndex, event) {
            event.preventDefault();
            var newValue = _.clone(this.getModel().get(attribute));
            newValue.splice(rowIndex, 1);
            this.setValue(attribute, newValue);
            this.setState({pendingFocus: true});
        },
        getRangeProps: function(isRangeEnd) {
            var error = this.props.error || null,
                attributeName = this.props.name;
            return {
                type: 'text',
                placeholder: error || !_.isUndefined(this.props.autoIncreaseWith) ? '' : '127.0.0.1',
                inputClassName: 'range',
                disabled: this.props.disabled,
                onChange: this.onRangeChange.bind(this, false, 0, attributeName),
                name: (isRangeEnd ? 'range-end_' : 'range-start_') + attributeName
            };
        },
        render: function() {
            var error = this.props.error || null,
                attributeName = this.props.name,
                attribute = this.getModel().get(attributeName),
                ranges = !_.isUndefined(this.props.autoIncreaseWith) ?
                    [attribute || '', this.props.autoIncreaseWith ? (attribute + this.props.autoIncreaseWith - 1 || '') : ''] :
                    attribute,
                wrapperClasses = {
                    mini: this.props.type == 'normal'
                },
                verificationError = this.props.verificationError || null,
                ns = 'cluster_page.network_tab.';

            wrapperClasses[this.props.wrapperClassName] = this.props.wrapperClassName;
            return (
                <div className={cx(wrapperClasses)}>
                    {!this.props.hiddenHeader &&
                        <div className='range-row-header'>
                            <div>{i18n(ns + 'range_start')}</div>
                            <div>{i18n(ns + 'range_end')}</div>
                        </div>
                    }
                    <div className='parameter-name'>{this.props.label}</div>
                    { (this.props.type == 'extendable') ?
                        <div className={this.props.rowsClassName}>
                            {_.map(ranges, function(range, index) {
                                var rangeError = _.findWhere(error, {index: index}) || {};
                                return (
                                    <div className='range-row autocomplete clearfix' key={index}>
                                        <controls.Input
                                            {...this.getRangeProps()}
                                            error={(rangeError.start || verificationError) && ''}
                                            value={range[0]}
                                            onChange={this.onRangeChange.bind(this, true, index, attributeName)}
                                            ref={'start' + index}
                                        />
                                        <controls.Input
                                            {...this.getRangeProps(true)}
                                            error={rangeError.end && ''}
                                            value={range[1]}
                                            onChange={this.onRangeChange.bind(this, true, index, attributeName)}
                                            onFocus={this.autoCompleteIPRange.bind(this, rangeError && rangeError.start, range[0])}
                                            disabled={this.props.disabled || !!this.props.autoIncreaseWith}
                                        />
                                        <div>
                                            <div className='ip-ranges-control'>
                                                <button
                                                    className='btn btn-link ip-ranges-add'
                                                    disabled={this.props.disabled}
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
                                            <span className='help-inline'>
                                                {rangeError.start || rangeError.end}
                                            </span>
                                        </div>
                                    </div>
                                );
                            }, this)}
                        </div>
                    :
                        <div className='range-row'>
                            <controls.Input
                                {...this.getRangeProps()}
                                wrapperClassName='parameter-control'
                                value={ranges[0]}
                                error={error && error[0] ? '' : null}
                            />
                            <controls.Input
                                {...this.getRangeProps(true)}
                                wrapperClassName='parameter-control'
                                disabled={this.props.disabled || _.isNumber(this.props.autoIncreaseWith)}
                                value={ranges[1]}
                                error={error && error[1] ? '' : null}
                            />
                            {error && (error[0] || error[1]) &&
                                <div className='error validation-error'>
                                    <span className='help-inline'>{error ? error[0] || error[1] : ''}</span>
                                </div>
                            }
                        </div>
                    }
                </div>
            );
        }
    });

    var VlanTagInput = React.createClass({
        mixins: [NetworkModelManipulationMixin],
        getInitialState: function() {
            return {pendingFocus: false};
        },
        componentDidUpdate: function() {
            var value = this.props.value;
            if (!_.isNull(value) && this.state.pendingFocus) {
                $(this.refs[this.props.name].getInputDOMNode()).focus();
                this.setState({pendingFocus: false});
            }
        },
        onTaggingChange: function(attribute, value) {
            this.setValue(attribute, value ? '' : null);
            this.setState({pendingFocus: true});
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
                            ref={this.props.name}
                            label={false}
                            onChange={this.props.onInputChange}
                            type='text'
                            integerValue={true}
                        />
                    }
                </div>
            );
        }
    });

    var NetworkTab = React.createClass({
        mixins: [
            componentMixins.backboneMixin('model', 'change:status', 'change:networkConfiguration'),
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {
                    return props.cluster.get('networkConfiguration').get('networking_parameters');
                },
                renderOn: 'change'
            }),
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {
                    return props.cluster.get('networkConfiguration').get('networks');
                },
                renderOn: 'change reset'
            }),
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {
                    return props.cluster.get('tasks');
                },
                renderOn: 'add remove change:status'
            }),
            componentMixins.pollingMixin(3)
        ],
        componentWillUnmount: function() {
            this.loadInitialConfiguration();
        },
        componentWillUpdate: function() {
            this.networkConfiguration.isValid();
        },
        componentWillReceiveProps: function(options) {
            this.networkConfiguration = options.cluster.get('networkConfiguration');
        },
        shouldDataBeFetched: function() {
            return !!this.props.cluster.task({group: 'network', status: 'running'});
        },
        fetchData: function() {
            return this.props.cluster.task({group: 'network', status: 'running'}).fetch();
        },
        getInitialState: function() {
            return {
                loading: true,
                actionInProgress: false
            };
        },
        loadInitialConfiguration: function() {
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
            this.networkConfiguration = this.props.cluster.get('networkConfiguration');
            $.when(this.props.cluster.get('settings').fetch({cache: true}), this.networkConfiguration.fetch({cache: true})).done(_.bind(function() {
                this.updateInitialConfiguration();
                this.setState({loading: false});
            }, this));
        },
        isLocked: function() {
            return !!this.props.cluster.task({group: ['deployment', 'network'], status: 'running'}) ||
                !this.props.cluster.isAvailableForSettingsChanges() || this.state.actionInProgress;
        },
        hasChanges: function() {
            return this.state.loading ? false : !_.isEqual(this.initialConfiguration, this.networkConfiguration.toJSON());
        },
        onManagerChange: function(name, value) {
            var networkingParams = this.networkConfiguration.get('networking_parameters'),
                fixedAmount = this.networkConfiguration.get('networking_parameters').get('fixed_networks_amount') || 1;
            networkingParams.set({
                net_manager: value,
                fixed_networks_amount: value == 'FlatDHCPManager' ? 1 : fixedAmount
            });
        },
        verifyNetworks: function() {
            this.setState({actionInProgress: true});
            this.prepareIpRanges();
            app.page.removeFinishedNetworkTasks().always(_.bind(this.startVerification, this));
        },
        startVerification: function() {
            var task = new models.Task(),
                options = {
                    method: 'PUT',
                    url: _.result(this.networkConfiguration, 'url') + '/verify',
                    data: JSON.stringify(this.networkConfiguration)
                },
                ns = 'cluster_page.network_tab.verify_networks.verification_error.';

            task.save({}, options)
                .fail(function() {
                    utils.showErrorDialog({
                        title: i18n(ns + 'title'),
                        message: i18n(ns + 'start_verification_warning')
                    });
                })
                .always(_.bind(function() {
                    this.props.cluster.fetchRelated('tasks').done(_.bind(function() {
                        this.startPolling();
                        this.setState({actionInProgress: false});
                    }, this));
                }, this));
        },
        revertChanges: function() {
            this.loadInitialConfiguration();
            app.page.removeFinishedNetworkTasks();
        },
        applyChanges: function() {
            this.setState({actionInProgress: true});
            this.prepareIpRanges();
            return Backbone.sync('update', this.networkConfiguration)
                .done(_.bind(function(task) {
                    if (task && task.status != 'error') {
                        this.updateInitialConfiguration();
                    }
                }, this))
                .fail(_.bind(function() {
                    this.props.cluster.fetch();
                    this.props.cluster.fetchRelated('tasks');
                }, this))
                .always(_.bind(function() {
                    this.setState({actionInProgress: false});
                }, this));
        },
        renderNetwork: function(network) {
            return <Network
                key={network.id}
                network={network}
                networkConfiguration={this.networkConfiguration}
                validationErrors={(this.networkConfiguration.validationError || {}).networks}
                disabled={this.isLocked()}
                verificationErrorField={_.pluck(_.where(this.verificationErrors, {network: network.id}), 'field')}
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
            var task = this.props.cluster.task({group: 'network', status: 'error'}),
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
            var cluster, networkingParameters, l23Provider, managers, manager,
                isLocked = this.isLocked(),
                classes = {
                    'network-settings wrapper': true,
                    'changes-locked': isLocked
                },
                ns = 'cluster_page.network_tab.';

            if (!this.state.loading) {
                cluster = this.props.cluster;
                networkingParameters = this.networkConfiguration.get('networking_parameters');
                l23Provider = networkingParameters.get('net_l23_provider');
                manager = networkingParameters.get('net_manager');
                managers = [
                    {
                        label: i18n(ns + 'flatdhcp_manager'),
                        data: 'FlatDHCPManager',
                        checked: manager == 'FlatDHCPManager',
                        disabled: isLocked
                    },
                    {
                        label: i18n(ns + 'vlan_manager'),
                        data: 'VlanManager',
                        checked: manager == 'VlanManager',
                        disabled: isLocked
                    }
                ];
                this.verificationErrors = this.getVerificationErrors();
            }
            return (
                <div className={cx(classes)}>
                    <h3>{i18n(ns + 'title')}</h3>
                    {this.state.loading ?
                        <controls.ProgressBar />
                    :
                        <div>
                            <div id='network-form'>
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
                                                i18n(ns + 'neutron_l23_provider', {l23_provider: l23Provider.toUpperCase()})
                                                :
                                                i18n(ns + 'neutron_segmentation', {segment_type: networkingParameters.get('segmentation_type').toUpperCase()})
                                            }
                                        </span>
                                    }
                                </div>
                                <div className='networks-table'>
                                    {this.networkConfiguration.get('networks').map(this.renderNetwork, this)}
                                </div>
                                <div className='networking-parameters'>
                                    <NetworkingParameters
                                        networkConfiguration={this.networkConfiguration}
                                        validationError={(this.networkConfiguration.validationError || {}).networking_parameters}
                                        disabled={this.isLocked()}
                                    />
                                </div>
                                <div className='verification-control'>
                                    <NetworkVerificationResult
                                        key='network_verification'
                                        task={cluster.task({group: 'network'})}
                                        networks={this.networkConfiguration.get('networks')}
                                    />
                                </div>
                                {this.renderButtons()}
                            </div>
                        </div>
                    }
                </div>
            );
        }
    });

    var Network = React.createClass({
        mixins: [
            NetworkInputsMixin,
            NetworkModelManipulationMixin
        ],
        render: function() {
            var network = this.props.network,
                networkConfig = network.get('meta');
            if (!networkConfig.configurable) return null;
            var vlanTagging = network.get('vlan_start'),
                ipRangesLabel = 'ip_ranges',
                ns = 'cluster_page.network_tab.network.';

            return (
                <div>
                    <legend className='networks'>{i18n('network.' + network.get('name'))}</legend>
                    <div className={network.get('name')}>
                        {(networkConfig.notation == ipRangesLabel) &&
                            <Range
                                {...this.composeProps(ipRangesLabel, true)}
                                rowsClassName='ip-ranges-rows'
                                verificationError={_.contains(this.props.verificationErrorField, 'ip_ranges')}
                            />
                        }
                        {this.renderInput('cidr')}
                        <VlanTagInput
                            {...this.composeProps('vlan_start')}
                            label={i18n(ns + 'use_vlan_tagging')}
                            value={vlanTagging}
                            onInputChange={this.setValue}
                        />
                        {networkConfig.use_gateway &&
                            this.renderInput('gateway')
                        }
                    </div>
                </div>
            );
        }
    });

    var NetworkingParameters = React.createClass({
        mixins: [
            NetworkInputsMixin,
            NetworkModelManipulationMixin
        ],
        getDefaultProps: function() {
            return {fixedNetworkSizeValues: _.map(_.range(3, 12), _.partial(Math.pow, 2))};
        },
        render: function() {
            var networkParameters = this.props.networkConfiguration.get('networking_parameters'),
                manager = networkParameters.get('net_manager'),
                idRangePrefix = networkParameters.get('segmentation_type') == 'gre' ? 'gre_id' : 'vlan',
                ns = 'cluster_page.network_tab.networking_parameters.';

            return (
                <div>
                    {manager ?
                        <div>
                            <legend className='networks'>
                                {i18n(ns + 'nova_configuration')}
                            </legend>
                            <div>
                                {this.renderInput('fixed_networks_cidr')}
                                {(manager == 'VlanManager') ?
                                    <div>
                                        <div className='network-attribute'>
                                            <controls.Input
                                                {...this.composeProps('fixed_network_size')}
                                                type='select'
                                                children={_.map(this.props.fixedNetworkSizeValues, function(value) {
                                                    return <option key={value} value={value}>{value}</option>;
                                                })}
                                            />
                                        </div>
                                        {this.renderInput('fixed_networks_amount', true)}
                                        <Range
                                            {...this.composeProps('fixed_networks_vlan_start', true)}
                                            wrapperClassName='network-attribute clearfix'
                                            label={i18n(ns + 'fixed_vlan_range')}
                                            type='normal'
                                            autoIncreaseWith={parseInt(networkParameters.get('fixed_networks_amount')) || 0}
                                            integerValue={true}
                                            directSetValue={true}
                                        />
                                    </div>
                                :
                                    <div className='clearfix'>
                                        <VlanTagInput
                                            {...this.composeProps('fixed_networks_vlan_start')}
                                            label={i18n(ns + 'use_vlan_tagging_fixed')}
                                            onInputChange={this.setValue}
                                        />
                                    </div>
                                }
                            </div>
                        </div>
                    :
                        <div>
                            <legend className='networks'>{i18n(ns + 'l2_configuration')}</legend>
                            <Range
                                {...this.composeProps(idRangePrefix + '_range', true)}
                                wrapperClassName='network-attribute clearfix'
                                type='normal'
                            />
                            {this.renderInput('base_mac')}
                            <div>
                                <legend className='networks'>{i18n(ns + 'l3_configuration')}</legend>
                            </div>
                            <div>
                                {this.renderInput('internal_cidr')}
                                {this.renderInput('internal_gateway')}
                            </div>
                        </div>
                    }
                    <Range
                        {...this.composeProps('floating_ranges', true)}
                        rowsClassName='floating-ranges-rows'
                    />
                    <Range
                        {...this.composeProps('dns_nameservers', true)}
                        type='normal'
                        rowsClassName='dns_nameservers-row'
                        hiddenHeader={true}
                    />
                </div>
            );
        }
    });

    var NetworkVerificationResult = React.createClass({
        getConnectionStatus: function(task, isFirstConnectionLine) {
            if (!task || (task && task.match({status: 'ready'}))) return 'stop';
            if (task && task.match({status: 'error'}) && !(isFirstConnectionLine &&
                !(task.match({name: 'verify_networks'}) && !task.get('result').length))) return 'error';
            return 'success';
        },
        render: function() {
            var task = this.props.task,
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
                                    {_.times(3, function(index) {
                                        ++index;
                                        return <div key={index} className={'connect-' + index + '-' + this.getConnectionStatus(task, index == 1)}></div>;
                                    }, this)}
                                </div>
                                <div className='nodes-box'>
                                    {_.times(3, function(index) {
                                        ++index;
                                        return <div key={index} className={'verification-node-' + index}></div>;
                                    })}
                                </div>
                            </div>
                            <div className='verification-text-placeholder'>
                                {_.times(5, function(index) {
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
                                        {task.escape('message')}
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
