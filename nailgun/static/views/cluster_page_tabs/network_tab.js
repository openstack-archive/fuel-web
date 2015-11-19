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
    'views/dialogs',
    'component_mixins',
    'views/controls'
],
function($, _, i18n, Backbone, React, models, dispatcher, utils, dialogs, componentMixins, controls) {
    'use strict';

    var CSSTransitionGroup = React.addons.CSSTransitionGroup,
        parametersNS = 'cluster_page.network_tab.networking_parameters.',
        networkTabNS = 'cluster_page.network_tab.',
        defaultNetworkSubtabs = ['neutron_l2', 'neutron_l3', 'network_verification', 'nova_configuration'];

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
            var networkConfiguration = this.props.cluster.get('networkConfiguration');
            this.getModel().set(attribute, value);
            dispatcher.trigger('hideNetworkVerificationResult');
            networkConfiguration.isValid();
        },
        getModel: function() {
            return this.props.network ||
                this.props.cluster.get('networkConfiguration').get('networking_parameters');
        }
    };

    var NetworkInputsMixin = {
        composeProps: function(attribute, isRange, isInteger) {
            var network = this.props.network,
                ns = network ? networkTabNS + 'network.' : parametersNS,
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
                network: network,
                cluster: this.props.cluster,
                wrapperClassName: isRange ? attribute : false,
                error: error
            };
        },
        renderInput: function(attribute, isInteger) {
            return (
                <controls.Input {...this.composeProps(attribute, false, isInteger)}
                    type='text'
                    wrapperClassName={attribute + ' simple-input'}
                />
            );
        },
        getError: function(attribute) {
            var validationErrors = this.props.cluster.get('networkConfiguration').validationError;
            if (!validationErrors) return null;

            var network = this.props.network,
                errors;

            if (network) {
                errors = (validationErrors.networks &&
                    validationErrors.networks[this.props.currentNodeNetworkGroup.id] ||
                    {})[network.id];
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
            if (this.props.extendable && this.state.elementToFocus && this.getModel().get(this.props.name).length) {
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
            } else if (_.contains(name, 'range-start')) {
                // if first range field
                valuesToModify[0] = newValue;
            } else if (_.contains(name, 'range-end')) {
                // if end field
                valuesToModify[1] = newValue;
            }

            this.setValue(attribute, valuesToSet, {isInteger: this.props.integerValue});
        },
        addRange: function(attribute, rowIndex) {
            var newValue = _.clone(this.getModel().get(attribute));
            newValue.splice(rowIndex + 1, 0, ['', '']);
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
                className: 'form-control',
                disabled: this.props.disabled,
                onChange: _.partialRight(this.onRangeChange, attributeName),
                name: (isRangeEnd ? 'range-end_' : 'range-start_') + attributeName
            };
        },
        renderRangeControls: function(attributeName, index, length) {
            return (
                <div className='ip-ranges-control'>
                    <button
                        className='btn btn-link ip-ranges-add'
                        disabled={this.props.disabled}
                        onClick={_.partial(this.addRange, attributeName, index)}
                    >
                        <i className='glyphicon glyphicon-plus-sign'></i>
                    </button>
                    {(length > 1) &&
                        <button
                            className='btn btn-link ip-ranges-delete'
                            disabled={this.props.disabled}
                            onClick={_.partial(this.removeRange, attributeName, index)}
                        >
                            <i className='glyphicon glyphicon-minus-sign'></i>
                        </button>
                    }
                </div>
            );
        },
        render: function() {
            var error = this.props.error || null,
                attributeName = this.props.name,
                attribute = this.getModel().get(attributeName),
                ranges = this.props.autoIncreaseWith ?
                    [attribute || 0, (attribute + this.props.autoIncreaseWith - 1 || 0)] :
                    attribute,
                wrapperClasses = {
                    'form-group range row': true,
                    mini: this.props.mini,
                    [this.props.wrapperClassName]: this.props.wrapperClassName
                },
                verificationError = this.props.verificationError || null,
                [startInputError, endInputError] = error || [];

            wrapperClasses[this.props.wrapperClassName] = this.props.wrapperClassName;
            return (
                <div className={utils.classNames(wrapperClasses)}>
                    {!this.props.hiddenHeader &&
                        <div className='range-row-header col-xs-12'>
                            <div>{i18n(networkTabNS + 'range_start')}</div>
                            <div>{i18n(networkTabNS + 'range_end')}</div>
                        </div>
                    }
                    <div className='col-xs-12'>
                        <label>{this.props.label}</label>
                        {this.props.extendable ?
                            _.map(ranges, function(range, index) {
                                var rangeError = _.findWhere(error, {index: index}) || {};
                                return (
                                    <div className='range-row clearfix' key={index}>
                                        <controls.Input
                                            {...this.getRangeProps()}
                                            error={(rangeError.start || verificationError) ? '' : null}
                                            value={range[0]}
                                            onChange={_.partialRight(this.onRangeChange, attributeName, index)}
                                            ref={'start' + index}
                                            inputClassName='start'
                                            placeholder={rangeError.start ? '' : this.props.placeholder}
                                        />
                                        <controls.Input
                                            {...this.getRangeProps(true)}
                                            error={rangeError.end ? '' : null}
                                            value={range[1]}
                                            onChange={_.partialRight(this.onRangeChange, attributeName, index)}
                                            onFocus={_.partial(this.autoCompleteIPRange, rangeError && rangeError.start, range[0])}
                                            disabled={this.props.disabled || !!this.props.autoIncreaseWith}
                                            placeholder={rangeError.end ? '' : this.props.placeholder}
                                            extraContent={!this.props.hiddenControls && this.renderRangeControls(attributeName, index, ranges.length)}
                                        />
                                        <div className='validation-error text-danger pull-left'>
                                            <span className='help-inline'>
                                                {rangeError.start || rangeError.end}
                                            </span>
                                        </div>
                                    </div>
                                );
                            }, this)
                        :
                            <div className='range-row clearfix'>
                                <controls.Input
                                    {...this.getRangeProps()}
                                    value={ranges[0]}
                                    error={startInputError ? '' : null}
                                    inputClassName='start'
                                />
                                <controls.Input
                                    {...this.getRangeProps(true)}
                                    disabled={this.props.disabled || !!this.props.autoIncreaseWith}
                                    value={ranges[1]}
                                    error={endInputError ? '' : null}
                                />
                                {error && (startInputError || endInputError) &&
                                    <div className='validation-error text-danger pull-left'>
                                        <span className='help-inline'>{startInputError || endInputError}</span>
                                    </div>
                                }
                            </div>
                        }
                    </div>
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
                <div className={'vlan-tagging form-group ' + this.props.name}>
                    <label className='vlan-tag-label'>{this.props.label}</label>
                    <controls.Input {...this.props}
                        onChange={this.onTaggingChange}
                        type='checkbox'
                        checked={!_.isNull(this.props.value)}
                        error={null}
                        label={null}
                    />
                    {!_.isNull(this.props.value) &&
                        <controls.Input {...this.props}
                            ref={this.props.name}
                            onChange={this.onInputChange}
                            type='text'
                            label={null}
                        />
                    }
                </div>
            );
        }
    });

    var CidrControl = React.createClass({
        mixins: [NetworkModelManipulationMixin],
        onCidrChange: function(name, cidr) {
            this.props.onChange(name, cidr);
            if (this.props.network.get('meta').notation == 'cidr') {
                this.props.autoUpdateParameters(cidr);
            }
        },
        render: function() {
            return (
                <div className='form-group cidr'>
                    <label>{i18n('cluster_page.network_tab.network.cidr')}</label>
                    <controls.Input
                        {...this.props}
                        type='text'
                        label={null}
                        onChange={this.onCidrChange}
                        wrapperClassName='pull-left'
                    />
                    <controls.Input
                        type='checkbox'
                        checked={this.props.network.get('meta').notation == 'cidr'}
                        label={i18n('cluster_page.network_tab.network.use_whole_cidr')}
                        disabled={this.props.disabled}
                        onChange={this.props.changeNetworkNotation}
                        wrapperClassName='pull-left'
                    />
                </div>
            );
        }
    });

    // FIXME(morale): this component is a lot of copy-paste from Range component
    // and should be rewritten either as a mixin or as separate component for
    // multiplying other components (eg accepting Range, Input etc)
    var MultipleValuesInput = React.createClass({
        mixins: [
            NetworkModelManipulationMixin
        ],
        propTypes: {
            name: React.PropTypes.string,
            placeholder: React.PropTypes.string,
            label: React.PropTypes.string,
            value: React.PropTypes.array
        },
        getInitialState: function() {
            return {elementToFocus: null};
        },
        componentDidUpdate: function() {
            // this glitch is needed to fix
            // when pressing '+' or '-' buttons button remains focused
            if (this.state.elementToFocus && this.getModel().get(this.props.name).length) {
                $(this.refs[this.state.elementToFocus].getInputDOMNode()).focus();
                this.setState({elementToFocus: null});
            }
        },
        onChange: function(attribute, value, index) {
            var model = this.getModel(),
                valueToSet = _.cloneDeep(model.get(attribute));
            valueToSet[index] = value;
            this.setValue(attribute, valueToSet);
        },
        addValue: function(attribute, index) {
            var newValue = _.clone(this.getModel().get(attribute));
            newValue.splice(index + 1, 0, '');
            this.setValue(attribute, newValue);
            this.setState({
                elementToFocus: 'row' + (index + 1)
            });
        },
        removeValue: function(attribute, index) {
            var newValue = _.clone(this.getModel().get(attribute));
            newValue.splice(index, 1);
            this.setValue(attribute, newValue);
            this.setState({
                elementToFocus: 'row' + _.min([newValue.length - 1, index])
            });
        },
        renderControls: function(attributeName, index, length) {
            return (
                <div className='ip-ranges-control'>
                    <button
                        className='btn btn-link ip-ranges-add'
                        disabled={this.props.disabled}
                        onClick={_.partial(this.addValue, attributeName, index)}
                    >
                        <i className='glyphicon glyphicon-plus-sign' />
                    </button>
                    {length > 1 &&
                        <button
                            className='btn btn-link ip-ranges-delete'
                            disabled={this.props.disabled}
                            onClick={_.partial(this.removeValue, attributeName, index)}
                        >
                            <i className='glyphicon glyphicon-minus-sign' />
                        </button>
                    }
                </div>
            );
        },
        render: function() {
            var attributeName = this.props.name,
                values = this.props.value;
            return (
                <div className={'form-group row multiple-values ' + attributeName}>
                    <div className='col-xs-12'>
                        <label>{this.props.label}</label>
                        {_.map(values, function(value, index) {
                            var inputError = (this.props.error || {})[index];
                            return (
                                <div className='range-row clearfix' key={attributeName + index}>
                                    <controls.Input
                                        type='text'
                                        disabled={this.props.disabled}
                                        name={attributeName}
                                        error={(inputError || this.props.verificationError) && ''}
                                        value={value}
                                        onChange={_.partialRight(this.onChange, index)}
                                        ref={'row' + index}
                                        placeholder={inputError ? '' : this.props.placeholder}
                                        extraContent={this.renderControls(attributeName, index, values.length)}
                                    />
                                    <div className='validation-error text-danger pull-left'>{inputError}</div>
                                </div>
                            );
                        }, this)}
                    </div>
                </div>
            );
        }
    });

    var NetworkTab = React.createClass({
        mixins: [
            NetworkInputsMixin,
            NetworkModelManipulationMixin,
            componentMixins.backboneMixin('cluster', 'change:status'),
            componentMixins.backboneMixin('nodeNetworkGroups', 'change update'),
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
                renderOn: 'change reset update'
            }),
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {
                    return props.cluster.get('tasks');
                },
                renderOn: 'update change:status'
            }),
            componentMixins.dispatcherMixin('hideNetworkVerificationResult', function() {
                this.setState({hideVerificationResult: true});
            }),
            componentMixins.dispatcherMixin('networkConfigurationUpdated', function() {
                this.setState({hideVerificationResult: false});
            }),
            componentMixins.pollingMixin(3),
            componentMixins.unsavedChangesMixin
        ],
        statics: {
            fetchData: function(options) {
                var cluster = options.cluster;
                return $.when(
                    cluster.get('settings').fetch({cache: true}),
                    cluster.get('networkConfiguration').fetch({cache: true})
                ).then(function() {
                    return {};
                });
            }
        },
        shouldDataBeFetched: function() {
            return !!this.props.cluster.task({group: 'network', active: true});
        },
        fetchData: function() {
            return this.props.cluster.task({group: 'network', active: true}).fetch();
        },
        getInitialState: function() {
            return {
                initialConfiguration: _.cloneDeep(this.props.cluster.get('networkConfiguration').toJSON()),
                hideVerificationResult: false
            };
        },
        componentDidMount: function() {
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
            if (task.match({group: 'network', active: false}) && task.get('unsaved')) {
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
            this.setState({
                hideVerificationResult: true
            });
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
            return !!this.props.cluster.task({group: ['deployment', 'network'], active: true}) ||
                !this.props.cluster.isAvailableForSettingsChanges() || this.state.actionInProgress;
        },
        prepareIpRanges: function() {
            var removeEmptyRanges = function(ranges) {
                    return _.filter(ranges, function(range) {return _.compact(range).length;});
                },
                networkConfiguration = this.props.cluster.get('networkConfiguration');
            networkConfiguration.get('networks').each(function(network) {
                if (network.get('meta').notation == 'ip_ranges') {
                    network.set({ip_ranges: removeEmptyRanges(network.get('ip_ranges'))});
                }
            });
            var floatingRanges = networkConfiguration.get('networking_parameters').get('floating_ranges');
            if (floatingRanges) {
                networkConfiguration.get('networking_parameters').set({floating_ranges: removeEmptyRanges(floatingRanges)});
            }
        },
        onManagerChange: function(name, value) {
            var networkConfiguration = this.props.cluster.get('networkConfiguration'),
                networkingParameters = networkConfiguration.get('networking_parameters'),
                fixedAmount = networkConfiguration.get('networking_parameters').get('fixed_networks_amount') || 1;
            networkingParameters.set({
                net_manager: value,
                fixed_networks_amount: value == 'FlatDHCPManager' ? 1 : fixedAmount
            });
            networkConfiguration.isValid();
            this.setState({hideVerificationResult: true});
        },
        verifyNetworks: function() {
            this.setState({actionInProgress: true});
            this.prepareIpRanges();
            dispatcher.trigger('networkConfigurationUpdated', this.startVerification);
        },
        startVerification: function() {
            var networkConfiguration = this.props.cluster.get('networkConfiguration'),
                task = new models.Task(),
                options = {
                    method: 'PUT',
                    url: _.result(networkConfiguration, 'url') + '/verify',
                    data: JSON.stringify(networkConfiguration)
                },
                ns = 'cluster_page.network_tab.verify_networks.verification_error.';

            task.save({}, options)
                .fail((response) => {
                    utils.showErrorDialog({
                        title: i18n(ns + 'title'),
                        message: i18n(ns + 'start_verification_warning'),
                        response: response
                    });
                })
                .then(() => {
                    return this.props.cluster.fetchRelated('tasks');
                })
                .then(() => {
                    // FIXME(vkramskikh): this ugly hack is needed to distinguish
                    // verification tasks for saved config from verification tasks
                    // for unsaved config (which appear after clicking "Verify"
                    // button without clicking "Save Changes" button first).
                    // For proper implementation, this should be managed by backend
                    this.props.cluster.get('tasks').get(task.id).set('unsaved', this.hasChanges());
                    return this.startPolling();
                })
                .always(() => {
                    this.setState({actionInProgress: false});
                });
        },
        getStayMessage: function() {
            return this.props.cluster.task({group: 'network', active: true}) && i18n('dialog.dismiss_settings.verify_message');
        },
        applyChanges: function() {
            if (!this.isSavingPossible()) return $.Deferred().reject();
            this.setState({actionInProgress: true});
            this.prepareIpRanges();

            var result = $.Deferred();
            dispatcher.trigger('networkConfigurationUpdated', _.bind(function() {
                return Backbone.sync('update', this.props.cluster.get('networkConfiguration'))
                    .then(_.bind(function(response) {
                        this.updateInitialConfiguration();
                        result.resolve(response);
                    }, this), _.bind(function() {
                        result.reject();
                        // FIXME(vkramskikh): the same hack for check_networks task:
                        // remove failed tasks immediately, so they won't be taken into account
                        return this.props.cluster.fetchRelated('tasks')
                            .done(_.bind(function() {
                                this.props.cluster.task('check_networks').set('unsaved', true);
                            }, this));
                    }, this))
                    .always(_.bind(function() {
                        this.setState({actionInProgress: false});
                    }, this));
                }, this)
            );
            return result;
        },
        isSavingPossible: function() {
            return _.isNull(this.props.cluster.get('networkConfiguration').validationError) &&
                !this.isLocked() &&
                this.hasChanges();
        },
        renderButtons: function() {
            var error = this.props.cluster.get('networkConfiguration').validationError,
                isLocked = this.isLocked(),
                isVerificationDisabled = error || this.state.actionInProgress ||
                    !!this.props.cluster.task({group: ['deployment', 'network'], active: true}) ||
                    this.nodeNetworkGroups.length > 1,
                isCancelChangesDisabled = isLocked || !this.hasChanges();
            return (
                <div className='well clearfix'>
                    <div className='btn-group pull-right'>
                        <button
                            key='verify_networks'
                            className='btn btn-default verify-networks-btn'
                            onClick={this.verifyNetworks}
                            disabled={isVerificationDisabled}
                        >
                            {i18n('cluster_page.network_tab.verify_networks_button')}
                        </button>
                        <button
                            key='revert_changes'
                            className='btn btn-default btn-revert-changes'
                            onClick={this.revertChanges}
                            disabled={isCancelChangesDisabled}
                        >
                            {i18n('common.cancel_changes_button')}
                        </button>
                        <button
                            key='apply_changes'
                            className='btn btn-success apply-btn'
                            onClick={this.applyChanges}
                            disabled={!this.isSavingPossible()}
                        >
                            {i18n('common.save_settings_button')}
                        </button>
                    </div>
                </div>
            );
        },
        getVerificationErrors: function() {
            var task = this.state.hideVerificationResult ? null : this.props.cluster.task({group: 'network', status: 'error'}),
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
        removeNodeNetworkGroup: function() {
            dialogs.RemoveNodeNetworkGroupDialog.show()
                .done(_.bind(function() {
                    var currentNodeNetworkGroup = this.nodeNetworkGroups.findWhere({name: this.props.activeNetworkSectionName});
                    this.props.nodeNetworkGroups.remove(currentNodeNetworkGroup);
                    currentNodeNetworkGroup.destroy().done(this.updateInitialConfiguration);
                }, this));
        },
        addNodeGroup: function(hasChanges) {
            if (hasChanges) {
                utils.showErrorDialog({
                    title: i18n(networkTabNS + 'node_network_group_creation_error'),
                    message: <div><i className='glyphicon glyphicon-danger-sign' /> {i18n(networkTabNS + 'save_changes_warning')}</div>
                });
                return;
            }
            dialogs.CreateNodeNetworkGroupDialog.show({
                clusterId: this.props.cluster.id,
                nodeNetworkGroups: this.nodeNetworkGroups
            })
                .done(_.bind(function() {
                    this.setState({hideVerificationResult: true});
                    this.nodeNetworkGroups.fetch().done(_.bind(function() {
                        var newNodeNetworkGroup = this.nodeNetworkGroups.last();
                        this.props.nodeNetworkGroups.add(newNodeNetworkGroup);
                        this.props.setActiveNetworkSectionName(newNodeNetworkGroup.get('name'));
                        this.props.cluster.get('networkConfiguration').fetch()
                            .done(this.updateInitialConfiguration);
                    }, this));
                }, this));
        },
        render: function() {
            var isLocked = this.isLocked(),
                hasChanges = this.hasChanges(),
                {activeNetworkSectionName, cluster} = this.props,
                networkConfiguration = this.props.cluster.get('networkConfiguration'),
                networkingParameters = networkConfiguration.get('networking_parameters'),
                manager = networkingParameters.get('net_manager'),
                managers = [
                    {
                        label: i18n(networkTabNS + 'flatdhcp_manager'),
                        data: 'FlatDHCPManager',
                        checked: manager == 'FlatDHCPManager',
                        disabled: isLocked
                    },
                    {
                        label: i18n(networkTabNS + 'vlan_manager'),
                        data: 'VlanManager',
                        checked: manager == 'VlanManager',
                        disabled: isLocked
                    }
                ],
                classes = {
                    row: true,
                    'changes-locked': isLocked
                },
                nodeNetworkGroups = this.nodeNetworkGroups = new models.NodeNetworkGroups(this.props.nodeNetworkGroups.where({cluster_id: cluster.id})),
                isNovaEnvironment = cluster.get('net_provider') == 'nova_network',
                networks = networkConfiguration.get('networks'),
                isMultiRack = nodeNetworkGroups.length > 1,
                networkTask = cluster.task({group: 'network'}),
                isNodeNetworkGroupSectionSelected = !_.contains(defaultNetworkSubtabs, activeNetworkSectionName);

            if (!activeNetworkSectionName ||
                    (activeNetworkSectionName && !nodeNetworkGroups.findWhere({name: activeNetworkSectionName}) &&
                    isNodeNetworkGroupSectionSelected)) {
                activeNetworkSectionName = _.first(nodeNetworkGroups.pluck('name'));
            }

            networkConfiguration.isValid();
            var currentNodeNetworkGroup = nodeNetworkGroups.findWhere({name: activeNetworkSectionName}),
                validationErrors = networkConfiguration.validationError,
                nodeNetworkGroupProps = {
                    cluster: cluster,
                    locked: isLocked,
                    actionInProgress: this.state.actionInProgress,
                    getVerificationErrors: this.getVerificationErrors
                };
            return (
                <div className={utils.classNames(classes)}>
                    <div className='col-xs-12'>
                        <div className='row'>
                            <div className='title col-xs-7'>
                                {i18n(networkTabNS + 'title')}
                                {!isNovaEnvironment &&
                                    <div className='forms-box segmentation-type'>
                                        {'(' + i18n('common.network.neutron_' +
                                            networkingParameters.get('segmentation_type')) + ')'}
                                    </div>
                                }
                            </div>
                            <div className='col-xs-5 node-netwrok-groups-controls'>
                                {isNodeNetworkGroupSectionSelected && isMultiRack &&
                                    <controls.Input
                                        key='show_all'
                                        type='checkbox'
                                        name='show_all'
                                        label={i18n(networkTabNS + 'show_all_networks')}
                                        wrapperClassName='show-all-networks pull-left'
                                        onChange={this.props.setActiveNetworkSectionName}
                                        checked={this.props.showAllNetworks}
                                    />
                                }
                                {!isNovaEnvironment &&
                                    <button
                                        key='add_node_group'
                                        className='btn btn-default add-nodegroup-btn pull-right'
                                        onClick={_.partial(this.addNodeGroup, hasChanges)}
                                        disabled={isLocked}
                                    >
                                        {hasChanges && <i className='glyphicon glyphicon-danger-sign'/>}
                                        {i18n(networkTabNS + 'add_node_network_group')}
                                    </button>
                                }
                            </div>
                        </div>
                    </div>
                    {isNovaEnvironment &&
                        <div className='col-xs-12 forms-box nova-managers'>
                            <controls.RadioGroup
                                key='net_provider'
                                name='net_provider'
                                values={managers}
                                onChange={this.onManagerChange}
                                wrapperClassName='pull-left'
                            />
                        </div>
                    }
                    <div className='network-tab-content col-xs-12'>
                        <div className='row'>
                            <NetworkSubtabs
                                cluster={cluster}
                                setActiveNetworkSectionName={this.props.setActiveNetworkSectionName}
                                nodeNetworkGroups={nodeNetworkGroups}
                                activeGroupName={activeNetworkSectionName}
                                showAllNetworks={this.props.showAllNetworks}
                                isMultiRack={isMultiRack}
                                hasChanges={hasChanges}
                            />
                            <div className='col-xs-10'>
                                {isNodeNetworkGroupSectionSelected &&
                                    (this.props.showAllNetworks ?
                                        nodeNetworkGroups.map(function(networkGroup) {
                                            return (
                                                <NodeNetworkGroup
                                                    {...nodeNetworkGroupProps}
                                                    nodeNetworkGroups={nodeNetworkGroups}
                                                    nodeNetworkGroup={networkGroup}
                                                    networks={networks.where({group_id: networkGroup.id})}
                                                    removeNodeNetworkGroup={this.removeNodeNetworkGroup}
                                                    setActiveNetworkSectionName={this.props.setActiveNetworkSectionName}
                                                />
                                            );
                                        }, this)
                                    :
                                        <NodeNetworkGroup
                                            {...nodeNetworkGroupProps}
                                            nodeNetworkGroups={nodeNetworkGroups}
                                            nodeNetworkGroup={currentNodeNetworkGroup}
                                            networks={networks.where({group_id: currentNodeNetworkGroup.id})}
                                            removeNodeNetworkGroup={this.removeNodeNetworkGroup}
                                            setActiveNetworkSectionName={this.props.setActiveNetworkSectionName}
                                        />
                                    )
                                }
                                {activeNetworkSectionName == 'network_verification' &&
                                    <div className='verification-control'>
                                        <NetworkVerificationResult
                                            key='network_verification'
                                            task={networkTask}
                                            networks={networkConfiguration.get('networks')}
                                            hideVerificationResult={this.state.hideVerificationResult}
                                            isMultirack={isMultiRack}
                                        />
                                    </div>
                                }
                                {activeNetworkSectionName == 'nova_configuration' &&
                                    <NovaParameters
                                        cluster={cluster}
                                        validationErrors={validationErrors}
                                    />
                                }
                                {activeNetworkSectionName == 'neutron_l2' &&
                                    <NetworkingL2Parameters
                                        cluster={cluster}
                                        validationErrors={validationErrors}
                                        disabled={this.isLocked()}
                                    />
                                }
                                {activeNetworkSectionName == 'neutron_l3' &&
                                    <NetworkingL3Parameters
                                        cluster={cluster}
                                        validationErrors={validationErrors}
                                        disabled={this.isLocked()}
                                    />
                                }
                            </div>
                        </div>
                    </div>
                    {!this.state.hideVerificationResult && networkTask && networkTask.match({status: 'error'}) &&
                        <div className='col-xs-12'>
                            <div className='alert alert-danger enable-selection col-xs-12 network-alert'>
                                <span>
                                    {i18n('cluster_page.network_tab.verify_networks.fail_alert')}
                                </span>
                                <br/>
                                {networkTask.get('message')}
                            </div>
                        </div>
                    }
                    <div className='col-xs-12 page-buttons content-elements'>
                        {this.renderButtons()}
                    </div>
                </div>
            );
        }
    });

    var NodeNetworkGroup = React.createClass({
        render: function() {
            var {cluster, networks, nodeNetworkGroup, nodeNetworkGroups} = this.props,
                verificationErrors = this.props.getVerificationErrors(),
                networkConfiguration = cluster.get('networkConfiguration'),
                isMultiRack = nodeNetworkGroups.length > 1;
            return (
                <div>
                    {isMultiRack &&
                        <NodeNetworkGroupTitle
                            nodeNetworkGroups={nodeNetworkGroups}
                            currentNodeNetworkGroup={nodeNetworkGroup}
                            locked={this.props.locked}
                            removeNodeNetworkGroup={this.props.removeNodeNetworkGroup}
                            setActiveNetworkSectionName={this.props.setActiveNetworkSectionName}
                        />
                    }
                    {networks.map(function(network) {
                        return (
                            <Network
                                key={network.id}
                                network={network}
                                cluster={cluster}
                                validationErrors={(networkConfiguration.validationError || {}).networks}
                                disabled={this.props.locked}
                                verificationErrorField={_.pluck(_.where(verificationErrors, {network: network.id}), 'field')}
                                currentNodeNetworkGroup={nodeNetworkGroup}
                            />
                        );
                    }, this)}
                </div>
            );
        }
    });

    var NetworkSubtabs = React.createClass({
        renderClickablePills: function(sections, isNetworkGroupPill) {
            var {cluster, nodeNetworkGroups} = this.props,
                networkConfiguration = cluster.get('networkConfiguration'),
                errors,
                isNovaEnvironment = cluster.get('net_provider') == 'nova_network',
                activeNodeNetworkGroup = nodeNetworkGroups.findWhere({name: this.props.activeGroupName});

            networkConfiguration.isValid();

            errors = networkConfiguration.validationError;

            var networkParametersErrors = errors && errors.networking_parameters,
                networksErrors = errors && errors.networks;

            return (sections.map(function(groupName) {
                var tabLabel = groupName,
                    showAll = this.props.showAllNetworks,
                    isActive = groupName == this.props.activeGroupName ||
                        showAll && isNetworkGroupPill,
                    isInvalid;

                // is one of predefined sections selected (networking_parameters)
                if (groupName == 'neutron_l2') {
                    isInvalid = !!_.intersection(NetworkingL2Parameters.renderedParameters, _.keys(networkParametersErrors)).length;
                } else if (groupName == 'neutron_l3') {
                    isInvalid = !!_.intersection(NetworkingL3Parameters.renderedParameters, _.keys(networkParametersErrors)).length;
                } else if (groupName == 'nova_configuration') {
                    isInvalid = !!_.intersection(NovaParameters.renderedParameters, _.keys(networkParametersErrors)).length;
                }

                // is node network group section selected
                if (this.props.isMultiRack && !showAll) {
                    isInvalid = networksErrors && !!networksErrors[activeNodeNetworkGroup.id]
                } else if (isNovaEnvironment) {
                    isInvalid = networksErrors;
                }

                if (!isNetworkGroupPill) {
                    tabLabel = i18n(networkTabNS + 'tabs.' + groupName);
                //FIXME(morale): this is a hack until default node network group
                // name is capitalized on backend
                } else if (groupName == 'default' && !this.props.isMultiRack) {
                    tabLabel = 'Default';
                }

                if (groupName == 'network_verification') {
                    tabLabel = i18n(networkTabNS + 'tabs.connectivity_check');
                    isInvalid = this.props.hasChanges && cluster.task({
                            group: 'network',
                            status: 'error'
                        });
                }

                return (
                    <li
                        key={groupName}
                        role='presentation'
                        className={utils.classNames({active: isActive, warning: this.props.isMultiRack && groupName == 'network_verification'})}
                        onClick={_.partial(this.props.setActiveNetworkSectionName, groupName)}
                    >
                        <a className={'subtab-link-' + groupName}>
                            {isInvalid && <i className='subtab-icon glyphicon-danger-sign' />}
                            {tabLabel}
                        </a>
                    </li>
                );
            }, this));
        },
        render: function() {
            var {nodeNetworkGroups} = this.props,
                settingsSections = [],
                nodeGroupSections = [];

                if (this.props.isMultiRack && !this.props.showAllNetworks) {
                    nodeGroupSections = nodeGroupSections.concat(nodeNetworkGroups.pluck('name'));
                } else {
                    nodeGroupSections.push(nodeNetworkGroups.pluck('name')[0]);
                }

                if (this.props.cluster.get('net_provider') == 'nova_network') {
                    settingsSections.push('nova_configuration');
                } else {
                    settingsSections = settingsSections.concat(['neutron_l2', 'neutron_l3']);
                }

            return (
                <div className='col-xs-2'>
                    <CSSTransitionGroup
                        component='ul'
                        transitionName='subtab-item'
                        className='nav nav-pills nav-stacked node-network-groups-list'
                        transitionEnter={false}
                        transitionLeave={false}
                        key='node-group-list'
                        id='node-group-list'
                    >
                        <li className='group-title' key='group1'>
                            {i18n(networkTabNS + 'tabs.node_network_groups')}
                        </li>
                        {this.renderClickablePills(nodeGroupSections, true)}
                        <li className='group-title' key='group2'>
                            {i18n(networkTabNS + 'tabs.settings')}
                        </li>
                        {this.renderClickablePills(settingsSections)}
                        <li className='group-title' key='group3'>
                            {i18n(networkTabNS + 'tabs.network_verification')}
                        </li>
                        {this.renderClickablePills(['network_verification'])}
                    </CSSTransitionGroup>
                </div>
            );
        }
    });

    var NodeNetworkGroupTitle = React.createClass({
        mixins: [
            componentMixins.renamingMixin('node-group-title-input')
        ],
        onNodeNetworkGroupNameKeyDown: function(e) {
            this.setState({nodeNetworkGroupNameChangingError: null});
            if (e.key == 'Enter') {
                var element = this.refs['node-group-title-input'].getInputDOMNode();
                this.setState({actionInProgress: true});
                var nodeNetworkGroupNewName = _.trim(element.value),
                    currentNodeNetworkGroup = this.props.currentNodeNetworkGroup,
                    nodeNetworkGroups = this.props.nodeNetworkGroups,
                    validationError;

                if (nodeNetworkGroupNewName != currentNodeNetworkGroup.get('name')) {
                    if (_.contains(nodeNetworkGroups.pluck('name'), nodeNetworkGroupNewName)) {
                        validationError = i18n(networkTabNS + 'node_network_group_duplicate_error');
                        if (nodeNetworkGroupNewName == nodeNetworkGroups.min('id').get('name')) {
                            validationError = i18n(networkTabNS + 'node_network_group_default_name');
                        }
                    }
                    if (validationError) {
                        this.setState({
                            nodeNetworkGroupNameChangingError: validationError
                        });
                        element.focus();
                    } else {
                        currentNodeNetworkGroup.save({
                            name: nodeNetworkGroupNewName
                        })
                            .fail((response) => {
                                this.setState({
                                    nodeNetworkGroupNameChangingError: utils.getResponseText(response)
                                });
                                element.focus();
                            })
                            .done(() => {
                                this.endRenaming();
                                this.props.setActiveNetworkSectionName(nodeNetworkGroupNewName, true);
                            });
                    }
                } else {
                    this.endRenaming();
                }
            } else if (e.key == 'Escape') {
                this.endRenaming();
                e.stopPropagation();
                this.getDOMNode().focus();
            }
        },
        startNodeNetworkGroupRenaming: function(e) {
            this.setState({nodeNetworkGroupNameChangingError: null});
            this.startRenaming(e);
        },
        render: function() {
            var currentNodeNetworkGroup = this.props.currentNodeNetworkGroup,
                nodeNetworkGroups = this.props.nodeNetworkGroups,
                isDefaultNodeNetworkGroup = _.min(nodeNetworkGroups.pluck('id')) == currentNodeNetworkGroup.id,
                classes = {
                    'network-group-name': true,
                    default: isDefaultNodeNetworkGroup
                };
            return (
                <div className={utils.classNames(classes)} key={currentNodeNetworkGroup.id}>
                    {this.state.isRenaming ?
                        <controls.Input
                            type='text'
                            ref='node-group-title-input'
                            name='new-name'
                            defaultValue={currentNodeNetworkGroup.get('name')}
                            error={this.state.nodeNetworkGroupNameChangingError}
                            disabled={this.props.locked}
                            onKeyDown={this.onNodeNetworkGroupNameKeyDown}
                            wrapperClassName='node-group-renaming'
                            maxLength='50'
                            selectOnFocus
                            autoFocus
                        />
                    :
                        <div className='name' onClick={this.startNodeNetworkGroupRenaming}>
                            <button className='btn-link'>
                                {currentNodeNetworkGroup.get('name')}
                            </button>
                            <i className='glyphicon glyphicon-pencil'></i>
                        </div>
                    }
                    {isDefaultNodeNetworkGroup &&
                        <span className='explanation'>{i18n(networkTabNS + 'default_node_network_group_info')}</span>
                    }
                    {!isDefaultNodeNetworkGroup && !this.state.isRenaming &&
                        <i className='glyphicon glyphicon-remove' onClick={this.props.removeNodeNetworkGroup}></i>
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
        autoUpdateParameters: function(cidr) {
            var useGateway = this.props.network.get('meta').use_gateway;
            if (useGateway) this.setValue('gateway', utils.getDefaultGatewayForCidr(cidr));
            this.setValue('ip_ranges', utils.getDefaultIPRangeForCidr(cidr, useGateway));
        },
        changeNetworkNotation: function(name, value) {
            var meta = _.clone(this.props.network.get('meta'));
            meta.notation = value ? 'cidr' : 'ip_ranges';
            this.setValue('meta', meta);
            if (value) this.autoUpdateParameters(this.props.network.get('cidr'));
        },
        render: function() {
            var meta = this.props.network.get('meta');
            if (!meta.configurable) return null;

            var networkName = this.props.network.get('name');

            var ipRangeProps = this.composeProps('ip_ranges', true),
                gatewayProps = this.composeProps('gateway');
            return (
                <div className={'forms-box ' + networkName}>
                    <h3 className='networks'>{i18n('network.' + networkName)}</h3>
                    <CidrControl
                        {... this.composeProps('cidr')}
                        changeNetworkNotation={this.changeNetworkNotation}
                        autoUpdateParameters={this.autoUpdateParameters}
                    />
                    <Range
                        {...ipRangeProps}
                        disabled={ipRangeProps.disabled || meta.notation == 'cidr'}
                        rowsClassName='ip-ranges-rows'
                        verificationError={_.contains(this.props.verificationErrorField, 'ip_ranges')}
                    />
                    {meta.use_gateway &&
                        <controls.Input
                            {...gatewayProps}
                            type='text'
                            disabled={gatewayProps.disabled || meta.notation == 'cidr'}
                        />
                    }
                    <VlanTagInput
                        {...this.composeProps('vlan_start')}
                        label={i18n(networkTabNS + 'network.use_vlan_tagging')}
                        value={this.props.network.get('vlan_start')}
                    />
                </div>
            );
        }
    });

    var NovaParameters = React.createClass({
        mixins: [
            NetworkInputsMixin,
            NetworkModelManipulationMixin
        ],
        statics: {
            renderedParameters: [
                'floating_ranges', 'fixed_networks_cidr', 'fixed_network_size',
                'fixed_networks_amount', 'fixed_networks_vlan_start', 'dns_nameservers'
            ]
        },
        render: function() {
            var networkConfiguration = this.props.cluster.get('networkConfiguration'),
                networkingParameters = networkConfiguration.get('networking_parameters'),
                manager = networkingParameters.get('net_manager'),
                fixedNetworkSizeValues = _.map(_.range(3, 12), _.partial(Math.pow, 2));
            return (
                <div className='forms-box nova-config' key='nova-config'>
                    <h3 className='networks'>{i18n(parametersNS + 'nova_configuration')}</h3>
                    <Range
                        {...this.composeProps('floating_ranges', true)}
                        rowsClassName='floating-ranges-rows'
                    />
                    {this.renderInput('fixed_networks_cidr')}
                    {(manager == 'VlanManager') ?
                        <div>
                            <controls.Input
                                {...this.composeProps('fixed_network_size', false, true)}
                                type='select'
                                children={_.map(fixedNetworkSizeValues, function(value) {
                                            return <option key={value} value={value}>{value}</option>;
                                        })}
                                inputClassName='pull-left'
                            />
                            {this.renderInput('fixed_networks_amount', true)}
                            <Range
                                {...this.composeProps('fixed_networks_vlan_start', true)}
                                wrapperClassName='clearfix vlan-id-range'
                                label={i18n(parametersNS + 'fixed_vlan_range')}
                                extendable={false}
                                autoIncreaseWith={parseInt(networkingParameters.get('fixed_networks_amount')) || 0}
                                integerValue
                                placeholder=''
                                mini
                            />
                        </div>
                    :
                        <VlanTagInput
                            {...this.composeProps('fixed_networks_vlan_start')}
                            label={i18n(parametersNS + 'use_vlan_tagging_fixed')}
                        />
                    }
                    <MultipleValuesInput {...this.composeProps('dns_nameservers', true)} />
                </div>
            );
        }
    });

    var NetworkingL2Parameters = React.createClass({
        mixins: [
            NetworkInputsMixin,
            NetworkModelManipulationMixin
        ],
        statics: {
            renderedParameters: [
                'vlan_range', 'gre_id_range', 'base_mac'
            ]
        },
        render: function() {
            var networkParameters = this.props.cluster.get('networkConfiguration').get('networking_parameters'),
                idRangePrefix = networkParameters.get('segmentation_type') == 'vlan' ? 'vlan' : 'gre_id';
            return (
                <div className='forms-box' key='neutron-l2'>
                    <h3 className='networks'>{i18n(parametersNS + 'l2_configuration')}</h3>
                    <div>
                        <Range
                            {...this.composeProps(idRangePrefix + '_range', true)}
                            extendable={false}
                            placeholder=''
                            integerValue
                            mini
                        />
                        {this.renderInput('base_mac')}
                    </div>
                </div>
            );
        }
    });

    var NetworkingL3Parameters = React.createClass({
        mixins: [
            NetworkInputsMixin,
            NetworkModelManipulationMixin
        ],
        statics: {
            renderedParameters: [
                'floating_ranges', 'internal_cidr', 'internal_gateway', 'baremetal_range',
                'baremetal_gateway', 'dns_nameservers'
            ]
        },
        render: function() {
            var networks = this.props.cluster.get('networkConfiguration').get('networks');
            return (
                <div className='forms-box' key='neutron-l3'>
                    <h3 className='networks'>{i18n(parametersNS + 'l3_configuration')}</h3>
                    <Range
                        {...this.composeProps('floating_ranges', true)}
                        rowsClassName='floating-ranges-rows'
                        hiddenControls
                    />
                    <div>
                        {this.renderInput('internal_cidr')}
                        {this.renderInput('internal_gateway')}
                    </div>
                    {networks.findWhere({name: 'baremetal'}) &&
                        [
                            <Range
                                key='baremetal_range'
                                {...this.composeProps('baremetal_range', true)}
                                extendable={false}
                                hiddenControls
                            />,
                            this.renderInput('baremetal_gateway')
                        ]
                    }
                    <MultipleValuesInput {...this.composeProps('dns_nameservers', true)} />
                </div>
            );
        }
    });

    var NetworkVerificationResult = React.createClass({
        getConnectionStatus: function(task, isFirstConnectionLine) {
            if (!task || task.match({status: 'ready'})) return 'stop';
            if (task && task.match({status: 'error'}) && !(isFirstConnectionLine &&
                !(task.match({name: 'verify_networks'}) && !task.get('result').length))) return 'error';
            return 'success';
        },
        render: function() {
            var task = this.props.task,
                ns = 'cluster_page.network_tab.verify_networks.';

            if (this.props.hideVerificationResult) task = null;
            return (
                <div className='forms-box'>
                    <h3>{i18n(networkTabNS + 'tabs.network_verification')}</h3>
                    {this.props.isMultirack &&
                        <div className='alert alert-warning'>
                            <p>{i18n(networkTabNS + 'verification_multirack_warning')}</p>
                        </div>
                    }
                    <div className='page-control-box'>
                        <div className='verification-box row'>
                            <div className='verification-network-placeholder col-xs-8 col-xs-offset-2'>
                                <div className='router-box'>
                                    <div className='verification-router'></div>
                                </div>
                                <div className='animation-box'>
                                    {_.times(3, function(index) {
                                        ++index;
                                        return <div key={index} className={this.getConnectionStatus(task, index == 1) + ' connect-' + index}></div>;
                                    }, this)}
                                </div>
                                <div className='nodes-box'>
                                    {_.times(3, function(index) {
                                        ++index;
                                        return <div key={index} className={'verification-node-' + index}></div>;
                                    })}
                                </div>
                            </div>
                        </div>
                        <div className='row'>
                            <div className='verification-text-placeholder col-xs-12'>
                                <ol>
                                    {_.times(5, function(index) {
                                        return <li key={index}>{i18n(ns + 'step_' + index)}</li>;
                                    }, this)}
                                </ol>
                            </div>
                            {(task && task.match({name: 'verify_networks', status: 'ready'})) &&
                                <div className='col-xs-12'>
                                    <div className='alert alert-success enable-selection'>
                                        {i18n(ns + 'success_alert')}
                                    </div>
                                    {task.get('message') &&
                                        <div className='alert alert-warning enable-selection'>
                                            {task.get('message')}
                                        </div>
                                    }
                                </div>
                            }
                            {(task && task.match({name: 'verify_networks'}) && !!task.get('result').length) &&
                                <div className='verification-result-table col-xs-12'>
                                    <controls.Table
                                        tableClassName='table table-condensed enable-selection'
                                        noStripes
                                        head={_.map(['node_name', 'node_mac_address', 'node_interface', 'expected_vlan'], function(attr) {
                                            return {label: i18n(ns + attr)};
                                        })}
                                        body={
                                            _.map(task.get('result'), function(node) {
                                                var absentVlans = _.map(node.absent_vlans, function(vlan) {
                                                    return vlan || i18n('cluster_page.network_tab.untagged');
                                                });
                                                return [node.name || 'N/A', node.mac || 'N/A', node.interface, absentVlans.join(', ')];
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
