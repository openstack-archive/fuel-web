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
    'dispatcher',
    'utils',
    'jsx!component_mixins',
    'jsx!views/controls'
],
function($, _, i18n, Backbone, React, models, dispatcher, utils, componentMixins, controls) {
    'use strict';

    var NetworkModelManipulationMixin = {
        setValue: function(attribute, value, options) {
            function convertToStringIfNaN(value) {
                var convertedValue = parseInt(value, 10);
                return _.isNaN(convertedValue) ? '' : convertedValue;
            }
            if (options && options.isInteger && !_.isNull(value)) {
                // for ranges values
                if (_.isArray(value)) {
                    value = _.map(value, convertToStringIfNaN);
                } else {
                    value = convertToStringIfNaN(value);
                }
            }
            this.getModel().set(attribute, value);
            dispatcher.trigger('hideNetworkVerificationResult');
            this.props.networkConfiguration.isValid();
        },
        getModel: function() {
            return this.props.network || this.props.networkConfiguration.get('networking_parameters');
        }
    };

    var NetworkInputsMixin = {
        composeProps: function(attribute, isRange, isInteger) {
            var network = this.props.network,
                isFloatingIPRange = attribute == 'floating_ranges',
                ns = 'cluster_page.network_tab.' + (network && !isFloatingIPRange ?
                        'network' : 'networking_parameters') + '.',
                error = this.getError(attribute) || null;

            // in case of verification error we need to pass an empty string to highlight the field only
            // but not overwriting validation error
            if (!error && _.contains(this.props.verificationErrorField, attribute)) {
                error = '';
            }
            return {
                key: attribute,
                onChange: _.partialRight(this.setValue, {isInteger: isInteger}),
                disabled: this.props.disabled,
                name: attribute,
                label: i18n(ns + attribute),
                value: this.getModel().get(attribute),
                network: isFloatingIPRange ? null : network,
                networkConfiguration: this.props.networkConfiguration,
                wrapperClassName: isRange ? 'network-attribute ' + attribute : false,
                error: error
            };
        },
        renderInput: function(attribute, isInteger) {
            return (
                <controls.Input {...this.composeProps(attribute, false, isInteger)}
                    type='text'
                    wrapperClassName='network-attribute'
                />
            );
        },
        getError: function(attribute) {
            var validationErrors = this.props.networkConfiguration.validationError;
            if (!validationErrors) return null;

            var network = this.props.network,
                errors;

            if (network && attribute != 'floating_ranges') {
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
                extendable: true,
                placeholder: '127.0.0.1',
                hiddenControls: false
            };
        },
        propTypes: {
            wrapperClassName: React.PropTypes.node,
            extendable: React.PropTypes.bool,
            name: React.PropTypes.string,
            autoIncreaseWith: React.PropTypes.number,
            integerValue: React.PropTypes.bool,
            placeholder: React.PropTypes.string,
            hiddenControls: React.PropTypes.bool,
            mini: React.PropTypes.bool
        },
        getInitialState: function() {
            return {elementToFocus: null};
        },
        componentDidUpdate: function() {
            // this glitch is needed to fix
            // when pressing '+' or '-' buttons button remains focused
            if (this.props.extendable && this.state.elementToFocus && (this.getModel().get(this.props.name).length > 1)) {
                $(this.refs[this.state.elementToFocus].getInputDOMNode()).focus();
                this.setState({elementToFocus: null});
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
        onRangeChange: function(name, newValue, attribute, rowIndex) {
            var model = this.getModel(),
                valuesToSet = _.cloneDeep(model.get(attribute)),
                valuesToModify = this.props.extendable ? valuesToSet[rowIndex] : valuesToSet;

            if (this.props.autoIncreaseWith) {
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

            this.setValue(attribute, valuesToSet, {isInteger: this.props.integerValue});
        },
        addRange: function(attribute, rowIndex) {
            var newValue = _.clone(this.getModel().get(attribute));
            newValue.push(['', '']);
            this.setValue(attribute, newValue);
            this.setState({
                elementToFocus: 'start' + (rowIndex + 1)
            });
        },
        removeRange: function(attribute, rowIndex) {
            var newValue = _.clone(this.getModel().get(attribute));
            newValue.splice(rowIndex, 1);
            this.setValue(attribute, newValue);
            this.setState({
                elementToFocus: 'start' + _.min([newValue.length - 1, rowIndex])
            });
        },
        getRangeProps: function(isRangeEnd) {
            var error = this.props.error || null,
                attributeName = this.props.name;
            return {
                type: 'text',
                placeholder: error ? '' : this.props.placeholder,
                inputClassName: 'range',
                disabled: this.props.disabled,
                onChange: _.partialRight(this.onRangeChange, attributeName),
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
                    mini: this.props.mini
                },
                verificationError = this.props.verificationError || null,
                ns = 'cluster_page.network_tab.';

            wrapperClasses[this.props.wrapperClassName] = this.props.wrapperClassName;
            return (
                <div className={utils.classNames(wrapperClasses)}>
                    {!this.props.hiddenHeader &&
                        <div className='range-row-header'>
                            <div>{i18n(ns + 'range_start')}</div>
                            <div>{i18n(ns + 'range_end')}</div>
                        </div>
                    }
                    <div className='parameter-name'>{this.props.label}</div>
                    {this.props.extendable ?
                        <div className={this.props.rowsClassName}>
                            {_.map(ranges, function(range, index) {
                                var rangeError = _.findWhere(error, {index: index}) || {};
                                return (
                                    <div className='range-row autocomplete clearfix' key={index}>
                                        <controls.Input
                                            {...this.getRangeProps()}
                                            error={(rangeError.start || verificationError) && ''}
                                            value={range[0]}
                                            onChange={_.partialRight(this.onRangeChange,  attributeName, index)}
                                            ref={'start' + index}
                                            inputClassName='start'
                                            placeholder={rangeError.start ? '' : this.props.placeholder}
                                        />
                                        <controls.Input
                                            {...this.getRangeProps(true)}
                                            error={rangeError.end && ''}
                                            value={range[1]}
                                            onChange={_.partialRight(this.onRangeChange, attributeName, index)}
                                            onFocus={this.autoCompleteIPRange.bind(this, rangeError && rangeError.start, range[0])}
                                            disabled={this.props.disabled || !!this.props.autoIncreaseWith}
                                            placeholder={rangeError.end ? '' : this.props.placeholder}
                                        />
                                        {!this.props.hiddenControls &&
                                            <div>
                                                <div className='ip-ranges-control'>
                                                    <button
                                                        className='btn btn-link ip-ranges-add'
                                                        disabled={this.props.disabled}
                                                        onClick={this.addRange.bind(this, attributeName, index)}>
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
                                        }
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
                                inputClassName='start'
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
        onInputChange: function(attribute, value) {
            this.setValue(attribute, value, {isInteger: true});
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
                            onChange={this.onInputChange}
                            type='text'
                        />
                    }
                </div>
            );
        }
    });

    var NetworkTab = React.createClass({
        mixins: [
            componentMixins.backboneMixin('cluster', 'change:status'),
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {
                    return props.cluster.get('tasks');
                },
                renderOn: 'add remove change:status'
            }),
            componentMixins.dispatcherMixin('hideNetworkVerificationResult', function() {
                this.setState({hideVerificationResult: true});
            }),
            componentMixins.dispatcherMixin('networkConfigurationUpdated', function() {
                this.setState({hideVerificationResult: false});
            })
        ],
        getInitialState: function() {
            return {
                loading: true,
                initialConfiguration: false,
                hideVerificationResult: false
            };
        },
        componentDidMount: function() {
            var networkConfiguration = this.props.cluster.get('networkConfiguration');
            $.when(this.props.cluster.get('settings').fetch({cache: true}), networkConfiguration.fetch({cache: true})).done(_.bind(function() {
                this.updateInitialConfiguration();
                this.setState({loading: false});
            }, this));
            this.props.cluster.get('tasks').on('change:status change:unsaved', this.removeUnsavedNetworkVerificationTasks, this);
        },
        componentWillUnmount: function() {
            this.loadInitialConfiguration();
            this.props.cluster.get('tasks').off(null, this.removeUnsavedNetworkVerificationTasks, this);
        },
        removeUnsavedNetworkVerificationTasks: function(task) {
            // FIXME(vkramskikh): remove tasks which we marked as "unsaved" hacky flag
            // immediately after completion, so they won't be taken into account when
            // we determine cluster verification status. They need to be removed silently
            // and kept in the collection to show verification result to the user
            if (task.match({group: 'network', status: ['ready', 'error']}) && task.get('unsaved')) {
                task.destroy({silent: true});
                task.unset('id'); // hack to prevent issuing another DELETE requests after actual removal
                this.props.cluster.get('tasks').add(task, {silent: true});
            }
        },
        hasChanges: function() {
            return !_.isEqual(this.state.initialConfiguration, this.props.cluster.get('networkConfiguration').toJSON());
        },
        revertChanges: function() {
            this.loadInitialConfiguration();
            this.props.cluster.get('networkConfiguration').isValid();
            this.setState({hideVerificationResult: false});
        },
        loadInitialConfiguration: function() {
            var networkConfiguration = this.props.cluster.get('networkConfiguration');
            networkConfiguration.get('networks').reset(_.cloneDeep(this.state.initialConfiguration.networks));
            networkConfiguration.get('networking_parameters').set(_.cloneDeep(this.state.initialConfiguration.networking_parameters));
        },
        updateInitialConfiguration: function() {
            this.setState({initialConfiguration: _.cloneDeep(this.props.cluster.get('networkConfiguration').toJSON())});
        },
        isLocked: function() {
            return !!this.props.cluster.task({group: ['deployment', 'network'], status: 'running'}) ||
                !this.props.cluster.isAvailableForSettingsChanges();
        },
        render: function() {
            var isLocked = this.isLocked(),
                classes = {
                    'network-settings wrapper': true,
                    'changes-locked': isLocked
                },
                ns = 'cluster_page.network_tab.';
            return (
                <div className={utils.classNames(classes)}>
                    <h3>{i18n(ns + 'title')}</h3>
                    {this.state.loading ?
                        <controls.ProgressBar />
                    :
                        <div>
                            <NetworkTabContent
                                networkConfiguration={this.props.cluster.get('networkConfiguration')}
                                initialConfiguration={this.state.initialConfiguration}
                                tasks={this.props.cluster.get('tasks')}
                                cluster={this.props.cluster}
                                isLocked={isLocked}
                                updateInitialConfiguration={this.updateInitialConfiguration}
                                revertChanges={this.revertChanges}
                                hasChanges={this.hasChanges}
                                hideVerificationResult={this.state.hideVerificationResult}
                            />
                        </div>
                    }
                </div>
            );
        }
    });

    var NetworkTabContent = React.createClass({
        mixins: [
            componentMixins.backboneMixin('networkConfiguration', 'change'),
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {
                    return props.networkConfiguration.get('networking_parameters');
                },
                renderOn: 'change'
            }),
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {
                    return props.networkConfiguration.get('networks');
                },
                renderOn: 'change reset'
            }),
            componentMixins.pollingMixin(3)
        ],
        shouldDataBeFetched: function() {
            return !!this.props.cluster.task({group: 'network', status: 'running'});
        },
        fetchData: function() {
            return this.props.cluster.task({group: 'network', status: 'running'}).fetch();
        },
        getInitialState: function() {
            return {
                actionInProgress: false
            };
        },
        isLocked: function() {
            return this.props.isLocked || this.state.actionInProgress;
        },
        prepareIpRanges: function() {
            var removeEmptyRanges = function(ranges) {
                return _.filter(ranges, function(range) {return _.compact(range).length;});
            };
            this.props.networkConfiguration.get('networks').each(function(network) {
                if (network.get('meta').notation == 'ip_ranges') {
                    network.set({ip_ranges: removeEmptyRanges(network.get('ip_ranges'))});
                }
            });
            var floatingRanges = this.props.networkConfiguration.get('networking_parameters').get('floating_ranges');
            if (floatingRanges) {
                this.props.networkConfiguration.get('networking_parameters').set({floating_ranges: removeEmptyRanges(floatingRanges)});
            }
        },
        onManagerChange: function(name, value) {
            var networkingParams = this.props.networkConfiguration.get('networking_parameters'),
                fixedAmount = this.props.networkConfiguration.get('networking_parameters').get('fixed_networks_amount') || 1;
            networkingParams.set({
                net_manager: value,
                fixed_networks_amount: value == 'FlatDHCPManager' ? 1 : fixedAmount
            });
            this.props.networkConfiguration.isValid();
            dispatcher.trigger('hideNetworkVerificationResult');
        },
        verifyNetworks: function() {
            this.setState({actionInProgress: true});
            this.prepareIpRanges();
            dispatcher.trigger('networkConfigurationUpdated', this.startVerification);
        },
        startVerification: function() {
            var task = new models.Task(),
                options = {
                    method: 'PUT',
                    url: _.result(this.props.networkConfiguration, 'url') + '/verify',
                    data: JSON.stringify(this.props.networkConfiguration)
                },
                ns = 'cluster_page.network_tab.verify_networks.verification_error.';

            task.save({}, options)
                .fail(function(response) {
                    utils.showErrorDialog({
                        title: i18n(ns + 'title'),
                        message: i18n(ns + 'start_verification_warning'),
                        response: response
                    });
                })
                .then(_.bind(function() {
                    return this.props.cluster.fetchRelated('tasks');
                }, this))
                .then(_.bind(function() {
                    // FIXME(vkramskikh): this ugly hack is needed to distinguish
                    // verification tasks for saved config from verification tasks
                    // for unsaved config (which appear after clicking "Verify"
                    // button without clicking "Save Changes" button first).
                    // For proper implementation, this should be managed by backend
                    this.props.cluster.get('tasks').get(task.id).set('unsaved', this.props.hasChanges());
                    return this.startPolling();
                }, this))
                .always(_.bind(function() {
                    this.setState({actionInProgress: false});
                }, this));
        },
        applyChanges: function() {
            this.setState({actionInProgress: true});
            this.prepareIpRanges();
            dispatcher.trigger('networkConfigurationUpdated', _.bind(function() {
                return Backbone.sync('update', this.props.networkConfiguration)
                    .then(_.bind(function(response) {
                        if (response.status != 'error') {
                            this.props.updateInitialConfiguration();
                        } else {
                            // FIXME(vkramskikh): the same hack for check_networks task:
                            // remove failed tasks immediately, so they won't be taken into account
                            return this.props.cluster.fetchRelated('tasks').done(_.bind(function() {
                                this.props.cluster.get('tasks').get(response.id).set('unsaved', true);
                            }, this));
                        }
                    }, this))
                    .always(_.bind(function() {
                        this.setState({actionInProgress: false});
                    }, this));
            }, this));
        },
        renderButtons: function() {
            var error = this.props.networkConfiguration.validationError,
                isLocked = this.isLocked(),
                hasChanges = this.props.hasChanges(),
                isVerificationDisabled = error || this.state.actionInProgress || !!this.props.cluster.task({group: ['deployment', 'network'], status: 'running'}),
                isCancelChangesDisabled = isLocked || !hasChanges,
                isSaveChangesDisabled = error || isLocked || !hasChanges;
            return (
                <div className='row'>
                    <div className='page-control-box'>
                        <div className='page-control-button-placeholder'>
                            <button key='verify_networks' className='btn verify-networks-btn' onClick={this.verifyNetworks}
                                disabled={isVerificationDisabled}>
                                    {i18n('cluster_page.network_tab.verify_networks_button')}
                            </button>
                            <button key='revert_changes' className='btn btn-revert-changes' onClick={this.props.revertChanges}
                                disabled={isCancelChangesDisabled}>
                                    {i18n('common.cancel_changes_button')}
                            </button>
                            <button key='apply_changes' className='btn btn-success apply-btn' onClick={this.applyChanges}
                                disabled={isSaveChangesDisabled}>
                                    {i18n('common.save_settings_button')}
                            </button>
                        </div>
                    </div>
                </div>
            );
        },
        getVerificationErrors: function() {
            var task = this.props.hideVerificationResult ? null : this.props.cluster.task({group: 'network', status: 'error'}),
                fieldsWithVerificationErrors = [];
            // @TODO(morale): soon response format will be changed and this part should be rewritten
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
        renderNetworks: function() {
            var verificationErrors = this.getVerificationErrors();
            return this.props.networkConfiguration.get('networks').map(function(network) {
                return (
                    <Network
                        key={network.id}
                        network={network}
                        networkConfiguration={this.props.networkConfiguration}
                        validationErrors={(this.props.networkConfiguration.validationError || {}).networks}
                        disabled={this.isLocked()}
                        verificationErrorField={_.pluck(_.where(verificationErrors, {network: network.id}), 'field')}
                        netProvider={network.get('name') == 'public' && this.props.cluster.get('net_provider')}
                    />
                );
            }, this);
        },
        render: function() {
            var ns = 'cluster_page.network_tab.',
                isLocked = this.isLocked(),
                cluster = this.props.cluster,
                networkingParameters = this.props.networkConfiguration.get('networking_parameters'),
                l23Provider = networkingParameters.get('net_l23_provider'),
                manager = networkingParameters.get('net_manager'),
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

            return (
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
                        {this.renderNetworks()}
                    </div>
                    <div className='networking-parameters'>
                        <NetworkingParameters
                            networkConfiguration={this.props.networkConfiguration}
                            validationError={(this.props.networkConfiguration.validationError || {}).networking_parameters}
                            disabled={this.isLocked()}

                        />
                    </div>
                    <div className='verification-control'>
                        <NetworkVerificationResult
                            key='network_verification'
                            task={cluster.task({group: 'network'})}
                            networks={this.props.networkConfiguration.get('networks')}
                            hideVerificationResult={this.props.hideVerificationResult}
                        />
                    </div>
                    {this.renderButtons()}
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
                        />
                        {networkConfig.use_gateway &&
                            this.renderInput('gateway')
                        }
                        {network.get('name') == 'public' &&
                            <Range
                                {...this.composeProps('floating_ranges', true)}
                                rowsClassName='floating-ranges-rows'
                                hiddenControls={this.props.netProvider == 'neutron'}
                            />
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
                                            extendable={false}
                                            autoIncreaseWith={parseInt(networkParameters.get('fixed_networks_amount')) || 0}
                                            integerValue={true}
                                            placeholder=''
                                            mini={true}
                                        />
                                    </div>
                                :
                                    <div className='clearfix'>
                                        <VlanTagInput
                                            {...this.composeProps('fixed_networks_vlan_start')}
                                            label={i18n(ns + 'use_vlan_tagging_fixed')}
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
                                extendable={false}
                                placeholder=''
                                integerValue={true}
                                mini={true}
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
                        {...this.composeProps('dns_nameservers', true)}
                        extendable={false}
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

            if (this.props.hideVerificationResult) task = null;
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
                                    {task.get('message')}
                                </div>
                            }
                            {(task && task.match({name: 'verify_networks'}) && !!task.get('result').length) &&
                                <div className='verification-result-table'>
                                    <controls.Table
                                        tableClassName='table table-condensed enable-selection'
                                        noStripes={true}
                                        head={_.map(['node_name', 'node_mac_address', 'node_interface', 'expected_vlan'], function(attr) {
                                            return {label: i18n(ns + attr)};
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
