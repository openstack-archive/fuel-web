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
    'jsx!views/dialogs',
    'jsx!component_mixins',
    'jsx!views/controls'
],
function($, _, i18n, Backbone, React, models, dispatcher, utils, dialogs, componentMixins, controls) {
    'use strict';

    var CSSTransitionGroup = React.addons.CSSTransitionGroup,
        networkingParametersNamespace = 'cluster_page.network_tab.networking_parameters.',
        networkTabNamespace = 'cluster_page.network_tab.';

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
            var errors = this.props.networkConfiguration.validate(this.props.networkConfiguration, this.props.nodeNetworkGroups);
            if (this.state && this.state.validationErrors) {
                this.setState({
                    validationErrors: errors
                });
            } else {
                this.props.setValidationErrors(errors);
            }
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
                wrapperClassName: isRange ? attribute : false,
                error: error,
                setValidationErrors: this.props.setValidationErrors,
                nodeNetworkGroups: this.props.nodeNetworkGroups
            };
        },
        renderInput: function(attribute, isInteger) {
            return (
                <controls.Input {...this.composeProps(attribute, false, isInteger)}
                    type='text'
                />
            );
        },
        getError: function(attribute) {
            var validationErrors = this.state && this.state.validationErrors || this.props.validationErrors;
            if (!validationErrors) return null;

            var network = this.props.network,
                errors;

            if (network && attribute != 'floating_ranges') {
                errors = validationErrors.networks[this.props.currentNodeNetworkGroup.id] &&
                    validationErrors.networks[this.props.currentNodeNetworkGroup.id][network.id];
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
                ranges = !_.isUndefined(this.props.autoIncreaseWith) ?
                    [attribute || '', this.props.autoIncreaseWith ? (attribute + this.props.autoIncreaseWith - 1 || '') : ''] :
                    attribute,
                wrapperClasses = {
                    'form-group range row': true,
                    mini: this.props.mini
                },
                verificationError = this.props.verificationError || null,
                startInputError = error && error[0],
                endInputError = error && error[1];
            wrapperClasses[this.props.wrapperClassName] = this.props.wrapperClassName;
            return (
                <div className={utils.classNames(wrapperClasses)}>
                    {!this.props.hiddenHeader &&
                        <div className='range-row-header col-xs-12'>
                            <div>{i18n(networkTabNamespace + 'range_start')}</div>
                            <div>{i18n(networkTabNamespace + 'range_end')}</div>
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
                                    error={error && error[0] ? '' : null}
                                    inputClassName='start'
                                />
                                <controls.Input
                                    {...this.getRangeProps(true)}
                                    disabled={this.props.disabled || _.isNumber(this.props.autoIncreaseWith)}
                                    value={ranges[1]}
                                    error={error && error[1] ? '' : null}
                                />
                                {error && (error[0] || error[1]) &&
                                    <div className='validation-error text-danger pull-left'>
                                        <span className='help-inline'>{error ? startInputError || endInputError : ''}</span>
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
            componentMixins.backboneMixin('cluster', 'change:networkConfiguration'),
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
            componentMixins.backboneMixin('nodeNetworkGroups', 'change update'),
            componentMixins.dispatcherMixin('hideNetworkVerificationResult', function() {
                this.setState({hideVerificationResult: true});
            }),
            componentMixins.dispatcherMixin('networkConfigurationUpdated', function() {
                this.setState({hideVerificationResult: false});
            }),
            componentMixins.pollingMixin(3),
            componentMixins.unsavedChangesMixin,
            componentMixins.renamingMixin('node-network-group-name')
        ],
        statics: {
            fetchData: function(options) {
                var nodeNetworkGroups = new models.NodeNetworkGroups(),
                    cluster = options.cluster;
                return $.when(
                    cluster.get('settings').fetch({cache: true}),
                    cluster.get('networkConfiguration').fetch({cache: true}),
                    nodeNetworkGroups.fetch({cache: true})
                ).then(function() {
                    return {nodeNetworkGroups: new models.NodeNetworkGroups(nodeNetworkGroups.where({cluster_id: cluster.id}))};
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
                hideVerificationResult: false,
                validationErrors: null
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
                hideVerificationResult: true,
                validationErrors: this.props.cluster.get('networkConfiguration').validate(this.props.cluster.get('networkConfiguration'), this.props.nodeNetworkGroups)
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
                !this.props.cluster.isAvailableForSettingsChanges();
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
                networkingParams = networkConfiguration.get('networking_parameters'),
                fixedAmount = networkConfiguration.get('networking_parameters').get('fixed_networks_amount') || 1;
            networkingParams.set({
                net_manager: value,
                fixed_networks_amount: value == 'FlatDHCPManager' ? 1 : fixedAmount
            });
            this.setState({validationErrors: networkConfiguration.validate(this.props.cluster.get('networkConfiguration'), this.props.nodeNetworkGroups)});
            dispatcher.trigger('hideNetworkVerificationResult');
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
                    this.props.cluster.get('tasks').get(task.id).set('unsaved', this.hasChanges());
                    return this.startPolling();
                }, this))
                .always(_.bind(function() {
                    this.setState({actionInProgress: false});
                }, this));
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
            return _.isNull(this.state.validationErrors) &&
                !this.isLocked() &&
                this.hasChanges();
        },
        renderButtons: function() {
            var error = this.state.validationErrors,
                isLocked = this.isLocked(),
                isVerificationDisabled = error || this.state.actionInProgress ||
                    !!this.props.cluster.task({group: ['deployment', 'network'], active: true}) ||
                    this.props.nodeNetworkGroups.length > 1,
                isCancelChangesDisabled = isLocked || !this.hasChanges();
            return (
                <div className='well clearfix'>
                    <div className='btn-group pull-right'>
                        <button key='verify_networks' className='btn btn-default verify-networks-btn' onClick={this.verifyNetworks}
                                disabled={isVerificationDisabled}>
                            {i18n('cluster_page.network_tab.verify_networks_button')}
                        </button>
                        <button key='revert_changes' className='btn btn-default btn-revert-changes' onClick={this.revertChanges}
                                disabled={isCancelChangesDisabled}>
                            {i18n('common.cancel_changes_button')}
                        </button>
                        <button key='apply_changes' className='btn btn-success apply-btn' onClick={this.applyChanges}
                                disabled={!this.isSavingPossible()}>
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
            dialogs.RemoveNodeNetworkGroupDialog.show({})
                .done(_.bind(function() {
                    var currentNodeNetworkGroup = this.props.nodeNetworkGroups.findWhere({name: this.props. activeNetworkGroupName});
                    this.props.nodeNetworkGroups.remove(currentNodeNetworkGroup);
                    currentNodeNetworkGroup.destroy()
                        .done(_.bind(function() {
                            this.setState({
                                initialConfiguration: _.cloneDeep(this.props.cluster.get('networkConfiguration').toJSON())
                            });
                        }, this));
                }, this));
        },
        onNodeNetworkGroupNameKeyDown: function(e) {
            this.setState({nodeNetworkGroupNameChangingError: null});
            if (e.key == 'Enter') {
                this.setState({actionInProgress: true});
                var nodeNetworkGroupName = _.trim(this.refs['node-network-group-name'].getInputDOMNode().value);
                var currentNodeNetworkGroup = this.props.nodeNetworkGroups.findWhere({name: this.props.activeNetworkGroupName});
                (nodeNetworkGroupName != this.props.activeNetworkGroupName ?
                        currentNodeNetworkGroup.save({
                            name: nodeNetworkGroupName
                        })
                    :
                        $.Deferred().resolve()
                )
                    .fail(_.bind(function(response) {
                        this.setState({
                            nodeNetworkGroupNameChangingError: utils.getResponseText(response),
                            actionInProgress: false
                        });
                        this.refs['node-network-group-name'].getInputDOMNode().focus();
                    }, this))
                    .done(this.endRenaming);
            } else if (e.key == 'Escape') {
                this.endRenaming();
                e.stopPropagation();
                this.getDOMNode().focus();
            }
        },
        setValidationErrors: function(errors) {
            this.setState({
                validationErrors: errors
            });
        },
        renderNetworks: function(networks, isMultiRack, nodeNetworkGroups, currentNodeNetworkGroup) {
            var verificationErrors = this.getVerificationErrors(),
                networkConfiguration = this.props.cluster.get('networkConfiguration');
            return ([
                isMultiRack &&
                    (<div className='network-group-name' key={currentNodeNetworkGroup.id}>
                        {this.state.isRenaming ?
                            <controls.Input
                                ref='node-network-group-name'
                                type='text'
                                defaultValue={currentNodeNetworkGroup.get('name')}
                                error={this.state.nodeNetworkGroupNameChangingError}
                                disabled={this.state.actionInProgress}
                                onKeyDown={this.onNodeNetworkGroupNameKeyDown}
                                selectOnFocus
                                autoFocus
                            />
                        :
                            <div className='name' onClick={this.startRenaming}>
                                <button className='btn-link'>
                                    {currentNodeNetworkGroup.get('name')}
                                </button>
                                <i className='glyphicon glyphicon-pencil'></i>
                            </div>
                        }
                        {isMultiRack && (_.min(nodeNetworkGroups.pluck('id')) != currentNodeNetworkGroup.id) &&
                            <i className='glyphicon glyphicon-remove' onClick={this.removeNodeNetworkGroup}></i>
                        }
                    </div>),
                networks.map(function(network) {
                    return (
                        <Network
                            key={network.id}
                            network={network}
                            networkConfiguration={networkConfiguration}
                            validationErrors={this.state.validationErrors}
                            disabled={this.isLocked()}
                            verificationErrorField={_.pluck(_.where(verificationErrors, {network: network.id}), 'field')}
                            setValidationErrors={this.setValidationErrors}
                            currentNodeNetworkGroup={currentNodeNetworkGroup}
                            nodeNetworkGroups={nodeNetworkGroups}
                        />
                    );
                }, this)
            ])
        },
        addNodeGroup: function(hasChanges) {
            if (hasChanges) {
                utils.showErrorDialog({
                    title: i18n(networkTabNamespace + 'node_network_group_creation_error'),
                    message: <div><i className='glyphicon glyphicon-danger-sign' /> {i18n(networkTabNamespace + 'save_changes_warning')}</div>
                });
                return;
            }
            dialogs.CreateNodeNetworkGroup.show({
                cluster: this.props.cluster,
                nodeNetworkGroups: this.props.nodeNetworkGroups,
                setActiveNetworkSectionName: this.props.setActiveNetworkSectionName,
                networkConfiguration: this.props.cluster.get('networkConfiguration')
            })
                .done(_.bind(function() {
                    this.props.cluster.get('networkConfiguration').fetch()
                        .done(_.bind(function() {
                            this.setState({
                                initialConfiguration: _.cloneDeep(this.props.cluster.get('networkConfiguration').toJSON())
                            });
                        }, this));
                }, this));
        },
        render: function() {
            var isLocked = this.isLocked(),
                hasChanges = this.hasChanges(),
                cluster = this.props.cluster,
                networkConfiguration = this.props.cluster.get('networkConfiguration'),
                networkingParameters = networkConfiguration.get('networking_parameters'),
                manager = networkingParameters.get('net_manager'),
                managers = [
                    {
                        label: i18n(networkTabNamespace + 'flatdhcp_manager'),
                        data: 'FlatDHCPManager',
                        checked: manager == 'FlatDHCPManager',
                        disabled: isLocked
                    },
                    {
                        label: i18n(networkTabNamespace + 'vlan_manager'),
                        data: 'VlanManager',
                        checked: manager == 'VlanManager',
                        disabled: isLocked
                    }
                ],
                classes = {
                    row: true,
                    'changes-locked': isLocked
                },
                activeNetworkGroupName = this.props.activeNetworkGroupName,
                nodeNetworkGroups = this.props.nodeNetworkGroups,
                isNovaEnvironment = cluster.get('net_provider') == 'nova_network',
                networks = networkConfiguration.get('networks'),
                isMultiRack = nodeNetworkGroups.length > 1;

            if (!activeNetworkGroupName || (
                activeNetworkGroupName && !nodeNetworkGroups.findWhere({name: activeNetworkGroupName}) &&
                !_.contains(['neutron_l2', 'neutron_l3', 'network_verification'], activeNetworkGroupName))) {
                activeNetworkGroupName = _.first(nodeNetworkGroups.pluck('name'));
            }

            var currentNodeNetworkGroup = nodeNetworkGroups.findWhere({name: activeNetworkGroupName}),
                nodeNetworkGroupId = currentNodeNetworkGroup && currentNodeNetworkGroup.id;

            var validationErrors = networkConfiguration.validate(networkConfiguration, nodeNetworkGroups);

            return (
                <div className={utils.classNames(classes)}>
                    <div className='col-xs-12'>
                        <div className='row'>
                            <div className='title col-xs-7'>
                                {i18n(networkTabNamespace + 'title')}
                                {!isNovaEnvironment &&
                                    <div className='forms-box segmentation-type'>
                                        {'(' + i18n('common.network.neutron_' +
                                            networkingParameters.get('segmentation_type')) + ')'}
                                    </div>
                                }
                            </div>
                            <div className='col-xs-5'>
                                {isMultiRack &&
                                    <controls.Input
                                        key='show_all'
                                        type='checkbox'
                                        name='show_all'
                                        label={i18n(networkTabNamespace + 'show_all_networks')}
                                        wrapperClassName='show-all-networks pull-left'
                                        onChange={this.props.setActiveNetworkSectionName}
                                    />
                                }
                                {!isNovaEnvironment &&
                                    <button
                                        key='add_node_group'
                                        className='btn btn-default add-nodegroup-btn pull-right'
                                        onClick={_.partial(this.addNodeGroup, hasChanges)}
                                    >
                                        {hasChanges && <i className='glyphicon glyphicon-danger-sign' />}
                                        {i18n(networkTabNamespace + 'add_node_network_group')}
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
                    <NetworkSubtabs
                        cluster={this.props.cluster}
                        setActiveNetworkSectionName={this.props.setActiveNetworkSectionName}
                        nodeNetworkGroups={nodeNetworkGroups}
                        activeGroupName={activeNetworkGroupName}
                        showAllNodeNetworkGroups={this.props.showAllNodeNetworkGroups}
                        isMultiRack={isMultiRack}
                    />
                    <div className='col-xs-10'>
                        {!_.contains(['neutron_l2', 'neutron_l3', 'network_verification'], activeNetworkGroupName) &&
                            (this.props.showAllNodeNetworkGroups ?
                                nodeNetworkGroups.map(function(networkGroup) {
                                    return this.renderNetworks(networks.where({group_id: networkGroup.id}), isMultiRack, nodeNetworkGroups, networkGroup);
                                }, this)
                            :
                                this.renderNetworks(networks.where({group_id: nodeNetworkGroupId}), isMultiRack, nodeNetworkGroups, currentNodeNetworkGroup)
                            )
                        }
                        {activeNetworkGroupName == 'network_verification' &&
                            <div className='verification-control'>
                                <NetworkVerificationResult
                                    key='network_verification'
                                    task={cluster.task({group: 'network'})}
                                    networks={networkConfiguration.get('networks')}
                                    hideVerificationResult={this.state.hideVerificationResult}
                                    isMultirack={isMultiRack}
                                />
                            </div>
                        }
                        {!manager ?
                            [
                                activeNetworkGroupName == 'neutron_l2' &&
                                    <NetworkingL2Parameters
                                        networkConfiguration={networkConfiguration}
                                        validationErrors={validationErrors}
                                        disabled={this.isLocked()}
                                        setValidationErrors={this.setValidationErrors}
                                    />,
                                activeNetworkGroupName == 'neutron_l3' &&
                                    <NetworkingL3Parameters
                                        networkConfiguration={networkConfiguration}
                                        validationErrors={validationErrors}
                                        disabled={this.isLocked()}
                                        setValidationErrors={this.setValidationErrors}
                                    />
                            ]
                        :
                            [activeNetworkGroupName == 'nova_configuration' &&
                                <NovaParameters
                                    networkConfiguration={networkConfiguration}
                                    validationErrors={validationErrors}
                                    setValidationErrors={this.setValidationErrors}
                                />
                            ]
                        }
                    </div>
                    <div className='col-xs-12 page-buttons content-elements'>
                        {this.renderButtons()}
                    </div>
                </div>
            );
        }
    });

    var NetworkSubtabs = React.createClass({
        renderClickablePills: function(sections, isNetworkGroupPill) {
            var cluster = this.props.cluster,
                networkConfiguration = cluster.get('networkConfiguration'),
                errors,
                nodeNetworkGroups = this.props.nodeNetworkGroups,
                invalidSections = {},
                isNovaEnvironment = cluster.get('net_provider') == 'nova_network';

                errors = networkConfiguration.validate(networkConfiguration, nodeNetworkGroups);

            if (isNovaEnvironment) {
                invalidSections.nova_configuration = errors && errors.networking_parameters;
                invalidSections.default = errors && errors.networks
            } else if (isNetworkGroupPill) {
                nodeNetworkGroups.map(function(nodeNetworkGroup) {
                    invalidSections[nodeNetworkGroup.get('name')] = errors &&
                        errors.networks && !!errors.networks[nodeNetworkGroup.id];
                }, this);
            } else {
                _.forEach(errors && errors.networking_parameters, function(error, name) {
                    if (_.contains(['vlan_range', 'base_mac'], name)) {
                        invalidSections.neutron_l2 = true;
                    } else {
                        invalidSections.neutron_l3 = true;
                    }
                }, this);
            }

            invalidSections.network_verification = cluster.task({group: 'network', status: 'error'});

            return (sections.map(function(groupName) {
                var tabLabel = i18n(networkTabNamespace + 'tabs.networks'),
                    showAll = this.props.showAllNodeNetworkGroups,
                    isActive = groupName == this.props.activeGroupName ||
                        showAll && isNetworkGroupPill && (sections.length == 1) &&
                        !_.contains(['neutron_l2', 'neutron_l3', 'network_verification'],
                            this.props.activeGroupName);

                if (!isNetworkGroupPill) {
                    tabLabel = i18n(networkTabNamespace + 'tabs.' + groupName);
                } else if (this.props.isMultiRack && !showAll) {
                    tabLabel = groupName;
                }

                return (
                    <li
                        key={groupName}
                        role='presentation'
                        className={utils.classNames({active: isActive})}
                        onClick={_.partial(this.props.setActiveNetworkSectionName, groupName)}
                    >
                        <a className={'subtab-link-' + groupName}>
                            {invalidSections[groupName] && <i className='subtab-icon glyphicon-danger-sign' />}
                            {tabLabel}
                            {!isNovaEnvironment && this.props.nodeNetworkGroups.min('id').get('name') == groupName &&
                                <controls.Tooltip
                                    key='default-nodegroup-tooltip'
                                    placement='right'
                                    text={i18n(networkTabNamespace + 'default_node_network_group_info')}
                                >
                                    <i className='glyphicon glyphicon-info-sign' />
                                </controls.Tooltip>
                            }
                        </a>
                    </li>
                );
            }, this));
        },
        render: function() {
            var nodeNetworkGroups = this.props.nodeNetworkGroups,
                settingsSections = [],
                nodeGroupSections = [],
                showAll = this.props.showAllNodeNetworkGroups,
                isMultiRack = this.props.isMultiRack;
                if (isMultiRack && !showAll) {
                    nodeGroupSections = nodeGroupSections.concat(nodeNetworkGroups.pluck('name'));
                } else {
                    nodeGroupSections.push(nodeNetworkGroups.pluck('name')[0]);
                }

                if (this.props.cluster.get('net_provider') == 'nova_network') {
                    settingsSections.push('nova_configuration');
                } else {
                    settingsSections = settingsSections.concat(['neutron_l2', 'neutron_l3']);
                }
                settingsSections.push('network_verification');

            return (
                <div className='col-xs-2'>
                    <CSSTransitionGroup
                        component='ul'
                        transitionName='subtab-item'
                        className='nav nav-pills nav-stacked node-network-groups-list'
                        transitionEnter={false}
                    >
                        {isMultiRack && !showAll &&
                            <li className='group-title' key='group1'>
                                {i18n(networkTabNamespace + 'tabs.node_network_groups')}
                            </li>
                        }
                        {this.renderClickablePills(nodeGroupSections, true)}
                        <li className='group-title' key='group2'>
                            {i18n(networkTabNamespace + 'tabs.settings')}
                        </li>
                        {this.renderClickablePills(settingsSections)}
                    </CSSTransitionGroup>
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
                networkName = network.get('name'),
                networkConfig = network.get('meta');
            if (!networkConfig.configurable) return null;
            var vlanTagging = network.get('vlan_start'),
                ipRangesLabel = 'ip_ranges';

            return (
                <div className={'forms-box ' + networkName}>
                    <h3 className='networks'>{i18n('network.' + networkName)}</h3>
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
                        label={i18n(networkTabNamespace + 'network.use_vlan_tagging')}
                        value={vlanTagging}
                    />
                    {networkConfig.use_gateway &&
                        this.renderInput('gateway')
                    }
                </div>
            );
        }
    });

    var NovaParameters = React.createClass({
        mixins: [
            NetworkInputsMixin,
            NetworkModelManipulationMixin
        ],
        render: function() {
            var networkConfiguration = this.props.networkConfiguration,
                networkingParameters = networkConfiguration.get('networking_parameters'),
                manager = networkingParameters.get('net_manager'),
                fixedNetworkSizeValues = _.map(_.range(3, 12), _.partial(Math.pow, 2));
            return (
                <div className='forms-box' key='nova-config'>
                    <h3 className='networks'>{i18n(networkingParametersNamespace + 'nova_configuration')}</h3>
                    <Range
                        {...this.composeProps('floating_ranges', true)}
                        rowsClassName='floating-ranges-rows'
                        hiddenControls={false}
                    />
                    <div>
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
                                    label={i18n(networkingParametersNamespace + 'fixed_vlan_range')}
                                    extendable={false}
                                    autoIncreaseWith={parseInt(networkingParameters.get('fixed_networks_amount')) || 0}
                                    integerValue={true}
                                    placeholder=''
                                    mini={true}
                                />
                            </div>
                        :
                            <VlanTagInput
                                {...this.composeProps('fixed_networks_vlan_start')}
                                label={i18n(networkingParametersNamespace + 'use_vlan_tagging_fixed')}
                            />
                        }
                    </div>
                </div>);
        }
    });

    var NetworkingL2Parameters = React.createClass({
        mixins: [
            NetworkInputsMixin,
            NetworkModelManipulationMixin
        ],
        render: function() {
            var networkParameters = this.props.networkConfiguration.get('networking_parameters'),
                idRangePrefix = networkParameters.get('segmentation_type') == 'vlan' ? 'vlan' : 'gre_id';

            return (
                <div className='forms-box' key='neutron-l2'>
                    <h3 className='networks'>{i18n(networkingParametersNamespace + 'l2_configuration')}</h3>
                    <div>
                        <Range
                            {...this.composeProps(idRangePrefix + '_range', true)}
                            extendable={false}
                            placeholder=''
                            integerValue={true}
                            mini={true}
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
        render: function() {
            return (
                <div className='forms-box' key='neutron-l3'>
                    <h3 className='networks'>{i18n(networkingParametersNamespace + 'l3_configuration')}</h3>
                    <Range
                        {...this.composeProps('floating_ranges', true)}
                        rowsClassName='floating-ranges-rows'
                        hiddenControls={true}
                    />
                    <div>
                        {this.renderInput('internal_cidr')}
                        {this.renderInput('internal_gateway')}
                    </div>
                    <MultipleValuesInput {...this.composeProps('dns_nameservers', true)} />
                </div>);
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
                <div>
                    {this.props.isMultirack &&
                        <div className='alert alert-warning'>
                            <p>{i18n(networkTabNamespace + 'verification_multirack_warning')}</p>
                        </div>
                    }
                    <div className='page-control-box'>
                        <div className='verification-box row'>
                            <hr/>
                            <div className='verification-network-placeholder col-xs-7'>
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
                            <div className='verification-text-placeholder col-xs-5'>
                                <ol>
                                    {_.times(5, function(index) {
                                        return <li key={index}>{i18n(ns + 'step_' + index)}</li>;
                                    }, this)}
                                </ol>
                            </div>
                            {(task && task.match({name: 'verify_networks', status: 'ready'})) ?
                                <div>
                                    <div className='alert alert-success enable-selection'>
                                        {i18n(ns + 'success_alert')}
                                    </div>
                                    {task.get('message') &&
                                        <div className='alert alert-warning enable-selection'>
                                            {task.get('message')}
                                        </div>
                                    }
                                </div>
                            : (task && task.match({status: 'error'})) &&
                                <div className='alert alert-danger enable-selection'>
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
