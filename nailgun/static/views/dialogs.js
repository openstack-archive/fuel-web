/*
 * Copyright 2014 Mirantis, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
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
    'utils',
    'models',
    'dispatcher',
    'views/controls',
    'component_mixins'
],
function($, _, i18n, Backbone, React, utils, models, dispatcher, controls, componentMixins) {
    'use strict';

    var dialogs = {};

    function getActiveDialog() {
        return app.dialog;
    }

    function setActiveDialog(dialog) {
        if (dialog) {
            app.dialog = dialog;
        } else {
            delete app.dialog;
        }
    }

    var dialogMixin = dialogs.dialogMixin = {
        propTypes: {
            title: React.PropTypes.node,
            message: React.PropTypes.node,
            modalClass: React.PropTypes.node,
            error: React.PropTypes.bool,
            closeable: React.PropTypes.bool,
            keyboard: React.PropTypes.bool,
            background: React.PropTypes.bool,
            backdrop: React.PropTypes.oneOfType([
                React.PropTypes.string,
                React.PropTypes.bool
            ])
        },
        statics: {
            show: function(dialogOptions = {}, showOptions = {}) {
                var activeDialog = getActiveDialog();
                if (activeDialog) {
                    var result = $.Deferred();
                    if (showOptions.preventDuplicate && activeDialog.constructor === this) {
                        result.reject();
                    } else {
                        $(React.findDOMNode(activeDialog)).on('hidden.bs.modal', () => {
                            this.show(dialogOptions).then(result.resolve, result.reject);
                        });
                    }
                    return result;
                } else {
                    return React.render(React.createElement(this, dialogOptions), $('#modal-container')[0]).getResult();
                }
            }
        },
        getInitialState: function() {
            return {
                actionInProgress: false,
                result: $.Deferred()
            };
        },
        getResult: function() {
            return this.state.result;
        },
        componentDidMount: function() {
            setActiveDialog(this);
            Backbone.history.on('route', this.close, this);
            var $el = $(React.findDOMNode(this));
            $el.on('hidden.bs.modal', this.handleHidden);
            $el.on('shown.bs.modal', () => $el.find('input:enabled:first').focus());
            $el.modal(_.defaults(
                {keyboard: false},
                _.pick(this.props, ['background', 'backdrop']),
                {background: true, backdrop: true}
            ));
        },
        rejectResult: function() {
            if (this.state.result.state() == 'pending') this.state.result.reject();
        },
        componentWillUnmount: function() {
            Backbone.history.off(null, null, this);
            $(React.findDOMNode(this)).off('shown.bs.modal hidden.bs.modal');
            this.rejectResult();
            setActiveDialog(null);
        },
        handleHidden: function() {
            React.unmountComponentAtNode(React.findDOMNode(this).parentNode);
        },
        close: function() {
            $(React.findDOMNode(this)).modal('hide');
            this.rejectResult();
        },
        closeOnLinkClick: function(e) {
            // close dialogs on click of any internal link inside it
            if (e.target.tagName == 'A' && !e.target.target && e.target.href) this.close();
        },
        closeOnEscapeKey: function(e) {
            if (this.props.keyboard !== false && this.props.closeable !== false && e.key == 'Escape') this.close();
            if (_.isFunction(this.onKeyDown)) this.onKeyDown(e);
        },
        showError: function(response, message) {
            var props = {error: true};
            props.message = utils.getResponseText(response) || message;
            this.setProps(props);
        },
        renderImportantLabel: function() {
            return <span className='label label-danger'>{i18n('common.important')}</span>;
        },
        submitAction: function() {
            this.state.result.resolve();
            this.close();
        },
        render: function() {
            var classes = {'modal fade': true};
            classes[this.props.modalClass] = this.props.modalClass;
            return (
                <div className={utils.classNames(classes)} tabIndex='-1' onClick={this.closeOnLinkClick} onKeyDown={this.closeOnEscapeKey}>
                    <div className='modal-dialog'>
                        <div className='modal-content'>
                            <div className='modal-header'>
                                {this.props.closeable !== false &&
                                    <button type='button' className='close' aria-label='Close' onClick={this.close}>
                                        <span aria-hidden='true'>&times;</span>
                                    </button>
                                }
                                <h4 className='modal-title'>{this.props.title || this.state.title || (this.props.error ? i18n('dialog.error_dialog.title') : '')}</h4>
                            </div>
                            <div className='modal-body'>
                                {this.props.error ?
                                    <div className='text-error'>
                                        {this.props.message || i18n('dialog.error_dialog.server_error')}
                                    </div>
                                : this.renderBody()}
                            </div>
                            <div className='modal-footer'>
                                {this.renderFooter && !this.props.error ?
                                    this.renderFooter()
                                :
                                    <button className='btn btn-default' onClick={this.close}>{i18n('common.close_button')}</button>
                                }
                            </div>
                        </div>
                    </div>
                </div>
            );
        }
    };

    var registrationResponseErrorMixin = {
        showResponseErrors: function(response, form) {
            var jsonObj,
                error = '';
            try {
                jsonObj = JSON.parse(response.responseText);
                error = jsonObj.message;
                if (_.isObject(form)) {
                    form.validationError = {};
                    _.each(jsonObj.errors, function(value, name) {
                        form.validationError['credentials.' + name] = value;
                    });
                }
            } catch (e) {
                error = i18n('welcome_page.register.connection_error');
            }
            this.setState({error: error});
        }
    };

    dialogs.ErrorDialog = React.createClass({
        mixins: [dialogMixin],
        getDefaultProps: function() {
            return {error: true};
        }
    });

    dialogs.NailgunUnavailabilityDialog = React.createClass({
        mixins: [dialogMixin],
        getDefaultProps() {
            return {
                title: i18n('dialog.nailgun_unavailability.title'),
                modalClass: 'nailgun-unavailability-dialog',
                closeable: false,
                keyboard: false,
                backdrop: false,
                retryDelayIntervals: [5, 10, 15, 20, 30, 60]
            };
        },
        getInitialState() {
            var initialDelay = this.props.retryDelayIntervals[0];
            return {
                currentDelay: initialDelay,
                currentDelayInterval: initialDelay
            };
        },
        componentWillMount() {
            this.startCountdown();
        },
        componentDidMount() {
            $(React.findDOMNode(this)).on('shown.bs.modal', () => $(React.findDOMNode(this.refs['retry-button'])).focus());
        },
        startCountdown() {
            this.activeTimeout = _.delay(this.countdown, 1000);
        },
        stopCountdown() {
            if (this.activeTimeout) clearTimeout(this.activeTimeout);
            delete this.activeTimeout;
        },
        countdown: function() {
            var {currentDelay} = this.state;
            currentDelay--;
            if (!currentDelay) {
                this.setState({currentDelay, actionInProgress: true});
                this.reinitializeUI();
            } else {
                this.setState({currentDelay});
                this.startCountdown();
            }
        },
        reinitializeUI() {
            app.initialize().then(this.close, () => {
                var {retryDelayIntervals} = this.props;
                var nextDelay = retryDelayIntervals[retryDelayIntervals.indexOf(this.state.currentDelayInterval) + 1] || _.last(retryDelayIntervals);
                _.defer(() => this.setState({
                    actionInProgress: false,
                    currentDelay: nextDelay,
                    currentDelayInterval: nextDelay
                }, this.startCountdown));
            });
        },
        retryNow() {
            this.stopCountdown();
            this.setState({
                currentDelay: 0,
                currentDelayInterval: 0,
                actionInProgress: true
            });
            this.reinitializeUI();
        },
        renderBody() {
            return (
                <div>
                    <p>
                        {i18n('dialog.nailgun_unavailability.unavailability_message')}
                        {' '}
                        {this.state.currentDelay ?
                            i18n('dialog.nailgun_unavailability.retry_delay_message', {count: this.state.currentDelay})
                        :
                            i18n('dialog.nailgun_unavailability.retrying')
                        }
                    </p>
                    <p>
                        {i18n('dialog.nailgun_unavailability.unavailability_reasons')}
                    </p>
                </div>
            );
        },
        renderFooter() {
            return (
                <button
                    ref='retry-button'
                    className='btn btn-success'
                    onClick={this.retryNow}
                    disabled={this.state.actionInProgress}
                >
                    {i18n('dialog.nailgun_unavailability.retry_now')}
                </button>
            );
        }
    });

    dialogs.DiscardNodeChangesDialog = React.createClass({
        mixins: [dialogMixin],
        getDefaultProps() {
            return {
                title: i18n('dialog.discard_changes.title')
            };
        },
        discardNodeChanges() {
            this.setState({actionInProgress: true});
            var nodes = new models.Nodes(this.props.nodes.map(function(node) {
                if (node.get('pending_deletion')) return {
                    id: node.id,
                    pending_deletion: false
                };
                return {
                    id: node.id,
                    cluster_id: null,
                    pending_addition: false,
                    pending_roles: []
                };
            }));
            Backbone.sync('update', nodes)
                .then(() => this.props.cluster.fetchRelated('nodes'))
                .done(() => {
                    dispatcher.trigger('updateNodeStats networkConfigurationUpdated labelsConfigurationUpdated');
                    this.state.result.resolve();
                    this.close();
                })
                .fail((response) => this.showError(response, i18n('dialog.discard_changes.cant_discard')));
        },
        renderBody() {
            return (
                <div className='text-danger'>
                    {this.renderImportantLabel()}
                    {i18n('dialog.discard_changes.' + (
                        this.props.nodes[0].get('pending_deletion') ? 'discard_deletion' : 'discard_addition'
                    ))}
                </div>
            );
        },
        renderFooter() {
            return ([
                <button key='cancel' className='btn btn-default' onClick={this.close} disabled={this.state.actionInProgress}>{i18n('common.cancel_button')}</button>,
                <button key='discard' className='btn btn-danger' disabled={this.state.actionInProgress} onClick={this.discardNodeChanges}>{i18n('dialog.discard_changes.discard_button')}</button>
            ]);
        }
    });

    dialogs.DeployChangesDialog = React.createClass({
        mixins: [
            dialogMixin,
            // this is needed to somehow handle the case when verification is in progress and user pressed Deploy
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {
                    return props.cluster.get('tasks');
                },
                renderOn: 'update change:status'
            })
        ],
        getDefaultProps: function() {return {title: i18n('dialog.display_changes.title')};},
        ns: 'dialog.display_changes.',
        deployCluster: function() {
            this.setState({actionInProgress: true});
            dispatcher.trigger('deploymentTasksUpdated');
            var task = new models.Task();
            task.save({}, {url: _.result(this.props.cluster, 'url') + '/changes', type: 'PUT'})
                .done(function() {
                    this.close();
                    dispatcher.trigger('deploymentTaskStarted');
                }.bind(this))
                .fail(this.showError);
        },
        renderBody: function() {
            var cluster = this.props.cluster;
            return (
                <div className='display-changes-dialog'>
                    {!cluster.needsRedeployment() && _.contains(['new', 'stopped'], cluster.get('status')) &&
                        <div>
                            <div className='text-warning'>
                                <i className='glyphicon glyphicon-warning-sign' />
                                <div className='instruction'>
                                    {i18n('cluster_page.dashboard_tab.locked_settings_alert') + ' '}
                                </div>
                            </div>
                            <div className='text-warning'>
                                <i className='glyphicon glyphicon-warning-sign' />
                                <div className='instruction'>
                                    {i18n('cluster_page.dashboard_tab.package_information') + ' '}
                                    <a
                                        target='_blank'
                                        href={utils.composeDocumentationLink('operations.html#troubleshooting')}
                                    >
                                        {i18n('cluster_page.dashboard_tab.operations_guide')}
                                    </a>
                                    {i18n('cluster_page.dashboard_tab.for_more_information_configuration')}
                                </div>
                            </div>
                        </div>
                    }
                    <div className='confirmation-question'>
                        {i18n(this.ns + 'are_you_sure_deploy')}
                    </div>
                </div>
            );
        },
        renderFooter: function() {
            return ([
                <button key='cancel' className='btn btn-default' onClick={this.close} disabled={this.state.actionInProgress}>{i18n('common.cancel_button')}</button>,
                <button key='deploy'
                    className='btn start-deployment-btn btn-success'
                    disabled={this.state.actionInProgress || this.state.isInvalid}
                    onClick={this.deployCluster}
                >{i18n(this.ns + 'deploy')}</button>
            ]);
        }
    });

    dialogs.ProvisionVMsDialog = React.createClass({
        mixins: [dialogMixin],
        getDefaultProps: function() {return {title: i18n('dialog.provision_vms.title')};},
        startProvisioning: function() {
            this.setState({actionInProgress: true});
            var task = new models.Task();
            task.save({}, {url: _.result(this.props.cluster, 'url') + '/spawn_vms', type: 'PUT'})
                .done(function() {
                    this.close();
                    dispatcher.trigger('deploymentTaskStarted');
                }.bind(this))
                .fail(_.bind(function(response) {
                    this.showError(response, i18n('dialog.provision_vms.provision_vms_error'));
                }, this));
        },
        renderBody: function() {
            var vmsCount = this.props.cluster.get('nodes').where(function(node) {
                return node.get('pending_addition') && node.hasRole('virt');
            }).length;
            return i18n('dialog.provision_vms.text', {count: vmsCount});
        },
        renderFooter: function() {
            return ([
                <button key='cancel' className='btn btn-default' onClick={this.close} disabled={this.state.actionInProgress}>{i18n('common.cancel_button')}</button>,
                <button key='provision' className='btn btn-success' disabled={this.state.actionInProgress} onClick={this.startProvisioning}>{i18n('common.start_button')}</button>
            ]);
        }
    });

    dialogs.StopDeploymentDialog = React.createClass({
        mixins: [dialogMixin],
        getDefaultProps: function() {return {title: i18n('dialog.stop_deployment.title')};},
        stopDeployment: function() {
            this.setState({actionInProgress: true});
            var task = new models.Task();
            task.save({}, {url: _.result(this.props.cluster, 'url') + '/stop_deployment', type: 'PUT'})
                .done(function() {
                    this.close();
                    dispatcher.trigger('deploymentTaskStarted');
                }.bind(this))
                .fail(_.bind(function(response) {
                    this.showError(response, i18n('dialog.stop_deployment.stop_deployment_error.stop_deployment_warning'));
                }, this));
        },
        renderBody: function() {
            return (
                <div className='text-danger'>
                    {this.renderImportantLabel()}
                    {i18n('dialog.stop_deployment.' + (this.props.cluster.get('nodes').where({status: 'provisioning'}).length ? 'provisioning_warning' : 'text'))}
                </div>
            );
        },
        renderFooter: function() {
            return ([
                <button key='cancel' className='btn btn-default' onClick={this.close} disabled={this.state.actionInProgress}>{i18n('common.cancel_button')}</button>,
                <button key='deploy' className='btn stop-deployment-btn btn-danger' disabled={this.state.actionInProgress} onClick={this.stopDeployment}>{i18n('common.stop_button')}</button>
            ]);
        }
    });

    dialogs.RemoveClusterDialog = React.createClass({
        mixins: [dialogMixin],
        getInitialState: function() {
            return {confirmation: false};
        },
        getDefaultProps: function() {
            return {title: i18n('dialog.remove_cluster.title')};
        },
        removeCluster: function() {
            this.setState({actionInProgress: true});
            this.props.cluster
                .destroy({wait: true})
                .then(
                    () => {
                        this.close();
                        dispatcher.trigger('updateNodeStats updateNotifications');
                        app.navigate('#clusters', {trigger: true});
                    },
                    this.showError
                );
        },
        showConfirmationForm: function() {
            this.setState({confirmation: true});
        },
        getText: function() {
            var ns = 'dialog.remove_cluster.',
                runningTask = this.props.cluster.task({active: true});
            if (runningTask) {
                if (runningTask.match({name: 'stop_deployment'})) {
                    return i18n(ns + 'stop_deployment_is_running');
                }
                return i18n(ns + 'incomplete_actions_text');
            }
            if (this.props.cluster.get('nodes').length) {
                return i18n(ns + 'node_returned_text');
            }
            return i18n(ns + 'default_text');
        },
        renderBody: function() {
            var clusterName = this.props.cluster.get('name');
            return (
                <div>
                    <div className='text-danger'>
                        {this.renderImportantLabel()}
                        {this.getText()}
                    </div>
                    {this.state.confirmation &&
                        <div className='confirm-deletion-form'>
                            {i18n('dialog.remove_cluster.enter_environment_name', {name: clusterName})}
                            <controls.Input
                                type='text'
                                disabled={this.state.actionInProgress}
                                onChange={(name, value) => this.setState({confirmationError: value != clusterName})}
                                onPaste={(e) => e.preventDefault()}
                                autoFocus
                            />
                        </div>
                    }
                </div>
            );
        },
        renderFooter: function() {
            return ([
                <button key='cancel' className='btn btn-default' onClick={this.close} disabled={this.state.actionInProgress}>{i18n('common.cancel_button')}</button>,
                <button
                    key='remove'
                    className='btn btn-danger remove-cluster-btn'
                    disabled={this.state.actionInProgress || this.state.confirmation && _.isUndefined(this.state.confirmationError) || this.state.confirmationError}
                    onClick={this.props.cluster.get('status') == 'new' || this.state.confirmation ? this.removeCluster : this.showConfirmationForm}
                >
                    {i18n('common.delete_button')}
                </button>
            ]);
        }
    });

    // FIXME: the code below neeeds deduplication
    // extra confirmation logic should be moved out to dialog mixin
    dialogs.ResetEnvironmentDialog = React.createClass({
        mixins: [dialogMixin],
        getInitialState: function() {
            return {confirmation: false};
        },
        getDefaultProps: function() {
            return {title: i18n('dialog.reset_environment.title')};
        },
        resetEnvironment: function() {
            this.setState({actionInProgress: true});
            dispatcher.trigger('deploymentTasksUpdated');
            var task = new models.Task();
            task.save({}, {url: _.result(this.props.cluster, 'url') + '/reset', type: 'PUT'})
                .done(function() {
                    this.close();
                    dispatcher.trigger('deploymentTaskStarted');
                }.bind(this))
                .fail(this.showError);
        },
        renderBody: function() {
            var clusterName = this.props.cluster.get('name');
            return (
                <div>
                    <div className='text-danger'>
                        {this.renderImportantLabel()}
                        {i18n('dialog.reset_environment.text')}
                    </div>
                    {this.state.confirmation &&
                        <div className='confirm-reset-form'>
                            {i18n('dialog.reset_environment.enter_environment_name', {name: clusterName})}
                            <controls.Input
                                type='text'
                                name='name'
                                disabled={this.state.actionInProgress}
                                onChange={_.bind(function(name, value) {
                                    this.setState({confirmationError: value != clusterName});
                                }, this)}
                                onPaste={function(e) {e.preventDefault();}}
                                autoFocus
                            />
                        </div>
                    }
                </div>
            );
        },
        showConfirmationForm: function() {
            this.setState({confirmation: true});
        },
        renderFooter: function() {
            return ([
                <button key='cancel' className='btn btn-default' disabled={this.state.actionInProgress} onClick={this.close}>{i18n('common.cancel_button')}</button>,
                <button
                    key='reset'
                    className='btn btn-danger reset-environment-btn'
                    disabled={this.state.actionInProgress || this.state.confirmation && _.isUndefined(this.state.confirmationError) || this.state.confirmationError}
                    onClick={this.state.confirmation ? this.resetEnvironment : this.showConfirmationForm}
                >
                    {i18n('common.reset_button')}
                </button>
            ]);
        }
    });

    dialogs.ShowNodeInfoDialog = React.createClass({
        mixins: [
            dialogMixin,
            componentMixins.backboneMixin('node'),
            componentMixins.renamingMixin('hostname')
        ],
        getDefaultProps: function() {
            return {modalClass: 'always-show-scrollbar'};
        },
        getInitialState: function() {
            return {
                title: i18n('dialog.show_node.default_dialog_title'),
                VMsConf: null,
                VMsConfValidationError: null,
                hostnameChangingError: null
            };
        },
        goToConfigurationScreen: function(url) {
            this.close();
            app.navigate('#cluster/' + this.props.node.get('cluster') + '/nodes/' + url + '/' + utils.serializeTabOptions({nodes: this.props.node.id}), {trigger: true});
        },
        showSummary: function(meta, group) {
            var summary = '';
            try {
                switch (group) {
                    case 'system':
                        summary = (meta.system.manufacturer || '') + ' ' + (meta.system.product || '');
                        break;
                    case 'memory':
                        if (_.isArray(meta.memory.devices) && meta.memory.devices.length) {
                            var sizes = _.countBy(_.pluck(meta.memory.devices, 'size'), utils.showMemorySize);
                            summary = _.map(_.keys(sizes).sort(), function(size) {return sizes[size] + ' x ' + size;}).join(', ');
                            summary += ', ' + utils.showMemorySize(meta.memory.total) + ' ' + i18n('dialog.show_node.total');
                        } else summary = utils.showMemorySize(meta.memory.total) + ' ' + i18n('dialog.show_node.total');
                        break;
                    case 'disks':
                        summary = meta.disks.length + ' ';
                        summary += i18n('dialog.show_node.drive', {count: meta.disks.length});
                        summary += ', ' + utils.showDiskSize(_.reduce(_.pluck(meta.disks, 'size'), function(sum, n) {return sum + n;}, 0)) + ' ' + i18n('dialog.show_node.total');
                        break;
                    case 'cpu':
                        var frequencies = _.countBy(_.pluck(meta.cpu.spec, 'frequency'), utils.showFrequency);
                        summary = _.map(_.keys(frequencies).sort(), function(frequency) {return frequencies[frequency] + ' x ' + frequency;}).join(', ');
                        break;
                    case 'interfaces':
                        var bandwidths = _.countBy(_.pluck(meta.interfaces, 'current_speed'), utils.showBandwidth);
                        summary = _.map(_.keys(bandwidths).sort(), function(bandwidth) {return bandwidths[bandwidth] + ' x ' + bandwidth;}).join(', ');
                        break;
                }
            } catch (ignore) {}
            return summary;
        },
        showPropertyName: function(propertyName) {
            return String(propertyName).replace(/_/g, ' ');
        },
        showPropertyValue: function(group, name, value) {
            try {
                if (group == 'memory' && (name == 'total' || name == 'maximum_capacity' || name == 'size')) {
                    value = utils.showMemorySize(value);
                } else if (group == 'disks' && name == 'size') {
                    value = utils.showDiskSize(value);
                } else if (name == 'size') {
                    value = utils.showSize(value);
                } else if (name == 'frequency') {
                    value = utils.showFrequency(value);
                } else if (name == 'max_speed' || name == 'current_speed') {
                    value = utils.showBandwidth(value);
                } else if (_.isBoolean(value)) {
                    value = value ? i18n('common.true') : i18n('common.false');
                }
            } catch (ignore) {}
            return !_.isNumber(value) && _.isEmpty(value) ? '\u00A0' : value;
        },
        componentDidUpdate: function() {
            this.assignAccordionEvents();
        },
        componentDidMount: function() {
            this.assignAccordionEvents();
            this.setDialogTitle();
            if (this.props.node.get('pending_addition') && this.props.node.hasRole('virt')) {
                var VMsConfModel = new models.BaseModel();
                VMsConfModel.url = _.result(this.props.node, 'url') + '/vms_conf';
                this.setProps({VMsConfModel: VMsConfModel});
                this.setState({actionInProgress: true});
                VMsConfModel.fetch().always(_.bind(function() {
                    this.setState({
                        actionInProgress: false,
                        VMsConf: JSON.stringify(VMsConfModel.get('vms_conf'))
                    });
                }, this));
            }
        },
        setDialogTitle: function() {
            var name = this.props.node && this.props.node.get('name');
            if (name && name != this.state.title) this.setState({title: name});
        },
        assignAccordionEvents: function() {
            $('.panel-collapse', React.findDOMNode(this))
                .on('show.bs.collapse', function(e) {$(e.currentTarget).siblings('.panel-heading').find('i').removeClass('glyphicon-plus').addClass('glyphicon-minus');})
                .on('hide.bs.collapse', function(e) {$(e.currentTarget).siblings('.panel-heading').find('i').removeClass('glyphicon-minus').addClass('glyphicon-plus');})
                .on('hidden.bs.collapse', function(e) {e.stopPropagation();});
        },
        toggle: function(groupIndex) {
            $(React.findDOMNode(this.refs['togglable_' + groupIndex])).collapse('toggle');
        },
        onVMsConfChange: function() {
            this.setState({VMsConfValidationError: null});
        },
        saveVMsConf: function() {
            var parsedVMsConf;
            try {
                parsedVMsConf = JSON.parse(this.refs['vms-config'].getInputDOMNode().value);
            } catch (e) {
                this.setState({VMsConfValidationError: i18n('node_details.invalid_vms_conf_msg')});
            }
            if (parsedVMsConf) {
                this.setState({actionInProgress: true});
                this.props.VMsConfModel.save({vms_conf: parsedVMsConf}, {method: 'PUT'})
                    .fail(_.bind(function(response) {
                        this.setState({VMsConfValidationError: utils.getResponseText(response)});
                    }, this))
                    .always(_.bind(function() {
                        this.setState({actionInProgress: false});
                    }, this));
            }
        },
        startHostnameRenaming: function(e) {
            this.setState({hostnameChangingError: null});
            this.startRenaming(e);
        },
        onHostnameInputKeydown: function(e) {
            this.setState({hostnameChangingError: null});
            if (e.key == 'Enter') {
                this.setState({actionInProgress: true});
                var hostname = _.trim(this.refs.hostname.getInputDOMNode().value);
                (hostname != this.props.node.get('hostname') ?
                    this.props.node.save({hostname: hostname}, {patch: true, wait: true}) :
                    $.Deferred().resolve()
                )
                .fail((response) => {
                    this.setState({
                        hostnameChangingError: utils.getResponseText(response),
                        actionInProgress: false
                    });
                    this.refs.hostname.getInputDOMNode().focus();
                })
                .done(this.endRenaming);
            } else if (e.key == 'Escape') {
                this.endRenaming();
                e.stopPropagation();
                React.findDOMNode(this).focus();
            }
        },
        renderBody: function() {
            var node = this.props.node,
                meta = node.get('meta');
            if (!meta) return <controls.ProgressBar />;
            var groupOrder = ['system', 'cpu', 'memory', 'disks', 'interfaces'],
                groups = _.sortBy(_.keys(meta), (group) => _.indexOf(groupOrder, group)),
                sortOrder = {
                    disks: ['name', 'model', 'size'],
                    interfaces: ['name', 'mac', 'state', 'ip', 'netmask', 'current_speed', 'max_speed', 'driver', 'bus_info']
                };
            if (this.state.VMsConf) groups.push('config');

            return (
                <div className='node-details-popup'>
                    <div className='row'>
                        <div className='col-xs-5'><div className='node-image-outline' /></div>
                        <div className='col-xs-7 node-summary'>
                            {this.props.cluster &&
                                <div><strong>{i18n('dialog.show_node.cluster')}: </strong>{this.props.cluster.get('name')}</div>
                            }
                            <div><strong>{i18n('dialog.show_node.manufacturer_label')}: </strong>{node.get('manufacturer') || i18n('common.not_available')}</div>
                            {this.props.nodeNetworkGroup &&
                                <div>
                                    <strong>{i18n('dialog.show_node.node_network_group')}: </strong>
                                    {this.props.nodeNetworkGroup.get('name')}
                                </div>
                            }
                            <div><strong>{i18n('dialog.show_node.mac_address_label')}: </strong>{node.get('mac') || i18n('common.not_available')}</div>
                            <div><strong>{i18n('dialog.show_node.fqdn_label')}: </strong>{(node.get('meta').system || {}).fqdn || node.get('fqdn') || i18n('common.not_available')}</div>
                            <div className='change-hostname'>
                                <strong>{i18n('dialog.show_node.hostname_label')}: </strong>
                                {this.state.isRenaming ?
                                    <controls.Input
                                        ref='hostname'
                                        type='text'
                                        defaultValue={node.get('hostname')}
                                        inputClassName={'input-sm'}
                                        error={this.state.hostnameChangingError}
                                        disabled={this.state.actionInProgress}
                                        onKeyDown={this.onHostnameInputKeydown}
                                        selectOnFocus
                                        autoFocus
                                    />
                                :
                                    <span>
                                        <span className='node-hostname'>
                                            {node.get('hostname') || i18n('common.not_available')}
                                        </span>
                                        {(node.get('pending_addition') || !node.get('cluster')) &&
                                            <button
                                                className='btn-link glyphicon glyphicon-pencil'
                                                onClick={this.startHostnameRenaming}
                                            />
                                        }
                                    </span>
                                }
                            </div>
                        </div>
                    </div>
                    <div className='panel-group' id='accordion' role='tablist' aria-multiselectable='true'>
                        {_.map(groups, function(group, groupIndex) {
                            var groupEntries = meta[group],
                                subEntries = [];
                            if (group == 'interfaces' || group == 'disks') groupEntries = _.sortBy(groupEntries, 'name');
                            if (_.isPlainObject(groupEntries)) subEntries = _.find(_.values(groupEntries), _.isArray);
                            return (
                                <div className='panel panel-default' key={group}>
                                    <div className='panel-heading' role='tab' id={'heading' + group} onClick={this.toggle.bind(this, groupIndex)}>
                                        <div className='panel-title'>
                                            <div data-parent='#accordion' aria-expanded='true' aria-controls={'body' + group}>
                                                <strong>{i18n('node_details.' + group, {defaultValue: group})}</strong> {this.showSummary(meta, group)}
                                                <i className='glyphicon glyphicon-plus pull-right' />
                                            </div>
                                        </div>
                                    </div>
                                    <div className='panel-collapse collapse' role='tabpanel' aria-labelledby={'heading' + group} ref={'togglable_' + groupIndex}>
                                        <div className='panel-body enable-selection'>
                                            {_.isArray(groupEntries) &&
                                                <div>
                                                    {_.map(groupEntries, function(entry, entryIndex) {
                                                        return (
                                                            <div className='nested-object' key={'entry_' + groupIndex + entryIndex}>
                                                                {_.map(utils.sortEntryProperties(entry, sortOrder[group]), function(propertyName) {
                                                                    if (!_.isObject(entry[propertyName])) return this.renderNodeInfo(propertyName, this.showPropertyValue(group, propertyName, entry[propertyName]));
                                                                }, this)}
                                                            </div>
                                                        );
                                                    }, this)}
                                                </div>
                                            }
                                            {_.isPlainObject(groupEntries) &&
                                                <div>
                                                    {_.map(groupEntries, function(propertyValue, propertyName) {
                                                        if (!_.isArray(propertyValue) && !_.isNumber(propertyName)) return this.renderNodeInfo(propertyName, this.showPropertyValue(group, propertyName, propertyValue));
                                                    }, this)}
                                                    {!_.isEmpty(subEntries) &&
                                                        <div>
                                                            {_.map(subEntries, function(subentry, subentrysIndex) {
                                                                return (
                                                                    <div className='nested-object' key={'subentries_' + groupIndex + subentrysIndex}>
                                                                        {_.map(utils.sortEntryProperties(subentry), function(propertyName) {
                                                                            return this.renderNodeInfo(propertyName, this.showPropertyValue(group, propertyName, subentry[propertyName]));
                                                                        }, this)}
                                                                    </div>
                                                                );
                                                            }, this)}
                                                        </div>
                                                    }
                                                </div>
                                            }
                                            {(!_.isPlainObject(groupEntries) && !_.isArray(groupEntries) && !_.isUndefined(groupEntries)) &&
                                                <div>{groupEntries}</div>
                                            }
                                            {group == 'config' &&
                                                <div className='vms-config'>
                                                    <controls.Input
                                                        ref='vms-config'
                                                        type='textarea'
                                                        label={i18n('node_details.vms_config_msg')}
                                                        error={this.state.VMsConfValidationError}
                                                        onChange={this.onVMsConfChange}
                                                        defaultValue={this.state.VMsConf}
                                                    />
                                                    <button
                                                        className='btn btn-success'
                                                        onClick={this.saveVMsConf}
                                                        disabled={this.state.VMsConfValidationError || this.state.actionInProgress}
                                                    >
                                                        {i18n('common.save_settings_button')}
                                                    </button>
                                                </div>
                                            }
                                        </div>
                                    </div>
                                </div>
                            );
                        }, this)}
                    </div>
                </div>
            );
        },
        renderFooter: function() {
            return (
                <div>
                    {this.props.renderActionButtons && this.props.node.get('cluster') &&
                        <div className='btn-group' role='group'>
                            <button className='btn btn-default btn-edit-disks' onClick={_.partial(this.goToConfigurationScreen, 'disks')}>
                                {i18n('dialog.show_node.disk_configuration' + (this.props.node.areDisksConfigurable() ? '_action' : ''))}
                            </button>
                            <button className='btn btn-default btn-edit-networks' onClick={_.partial(this.goToConfigurationScreen, 'interfaces')}>
                                {i18n('dialog.show_node.network_configuration' + (this.props.node.areInterfacesConfigurable() ? '_action' : ''))}
                            </button>
                        </div>
                    }
                    <div className='btn-group' role='group'>
                        <button className='btn btn-default' onClick={this.close}>{i18n('common.close_button')}</button>
                    </div>
                </div>
            );
        },
        renderNodeInfo: function(name, value) {
            return (
                <div key={name + value} className='node-details-row'>
                    <label>{i18n('dialog.show_node.' + name, {defaultValue: this.showPropertyName(name)})}</label>
                    {value}
                </div>
            );
        }
    });

    dialogs.DiscardSettingsChangesDialog = React.createClass({
        mixins: [dialogMixin],
        getDefaultProps: function() {return {title: i18n('dialog.dismiss_settings.title')};},
        proceedWith: function(method) {
            this.setState({actionInProgress: true});
            $.when(method ? method() : $.Deferred().resolve())
                .done(this.state.result.resolve)
                .done(this.close)
                .fail(_.partial(this.showError, null, i18n('dialog.dismiss_settings.saving_failed_message')));
        },
        discard: function() {
            this.proceedWith(this.props.revertChanges);
        },
        save: function() {
            this.proceedWith(this.props.applyChanges);
        },
        getMessage: function() {
            if (this.props.isDiscardingPossible === false) return 'no_discard_message';
            if (this.props.isSavingPossible === false) return 'no_saving_message';
            return 'default_message';
        },
        renderBody: function() {
            return (
                <div className='text-danger dismiss-settings-dialog'>
                    {this.renderImportantLabel()}
                    {i18n('dialog.dismiss_settings.' + this.getMessage())}
                </div>
            );
        },
        renderFooter: function() {
            var buttons = [
                <button
                    key='stay'
                    className='btn btn-default'
                    onClick={this.close}
                >
                    {i18n('dialog.dismiss_settings.stay_button')}
                </button>,
                <button
                    key='leave'
                    className='btn btn-danger proceed-btn'
                    onClick={this.discard}
                    disabled={this.state.actionInProgress || this.props.isDiscardingPossible === false}
                >
                    {i18n('dialog.dismiss_settings.leave_button')}
                </button>,
                <button
                    key='save'
                    className='btn btn-success'
                    onClick={this.save}
                    disabled={this.state.actionInProgress || this.props.isSavingPossible === false}
                >
                    {i18n('dialog.dismiss_settings.apply_and_proceed_button')}
                </button>
            ];
            return buttons;
        }
    });

    dialogs.RemoveOfflineNodeDialog = React.createClass({
        mixins: [dialogMixin],
        getDefaultProps() {
            return {
                title: i18n('dialog.remove_node.title'),
                defaultMessage: i18n('dialog.remove_node.default_message')
            };
        },
        renderBody() {
            return (
                <div className='text-danger'>
                    {this.renderImportantLabel()}
                    {this.props.defaultMessage}
                </div>
            );
        },
        renderFooter() {
            return [
                <button key='close' className='btn btn-default' onClick={this.close}>
                    {i18n('common.cancel_button')}
                </button>,
                <button key='remove' className='btn btn-danger btn-delete' onClick={this.submitAction}>
                    {i18n('cluster_page.nodes_tab.node.remove')}
                </button>
            ];
        }
    });

    dialogs.DeleteNodesDialog = React.createClass({
        mixins: [dialogMixin],
        getDefaultProps: function() {return {title: i18n('dialog.delete_nodes.title')};},
        renderBody: function() {
            var ns = 'dialog.delete_nodes.',
                notDeployedNodesAmount = this.props.nodes.reject({status: 'ready'}).length,
                deployedNodesAmount = this.props.nodes.length - notDeployedNodesAmount;
            return (
                <div className='text-danger'>
                    {this.renderImportantLabel()}
                    {i18n(ns + 'common_message', {count: this.props.nodes.length})}
                    <br/>
                    {!!notDeployedNodesAmount && i18n(ns + 'not_deployed_nodes_message', {count: notDeployedNodesAmount})}
                    {' '}
                    {!!deployedNodesAmount && i18n(ns + 'deployed_nodes_message', {count: deployedNodesAmount})}
                </div>
            );
        },
        renderFooter: function() {
            return [
                <button key='cancel' className='btn btn-default' onClick={this.close}>{i18n('common.cancel_button')}</button>,
                <button key='delete' className='btn btn-danger btn-delete' onClick={this.deleteNodes} disabled={this.state.actionInProgress}>{i18n('common.delete_button')}</button>
            ];
        },
        deleteNodes: function() {
            this.setState({actionInProgress: true});
            var nodes = new models.Nodes(this.props.nodes.map(function(node) {
                // mark deployed node as pending deletion
                if (node.get('status') == 'ready') return {
                    id: node.id,
                    pending_deletion: true
                };
                // remove not deployed node from cluster
                return {
                    id: node.id,
                    cluster_id: null,
                    pending_addition: false,
                    pending_roles: []
                };
            }));
            Backbone.sync('update', nodes)
                .then(_.bind(function() {
                    return this.props.cluster.fetchRelated('nodes');
                }, this))
                .done(_.bind(function() {
                    dispatcher.trigger('updateNodeStats networkConfigurationUpdated labelsConfigurationUpdated');
                    this.state.result.resolve();
                    this.close();
                }, this))
                .fail(_.bind(function(response) {
                    this.showError(response, i18n('cluster_page.nodes_tab.node_deletion_error.node_deletion_warning'));
                }, this));
        }
    });

    dialogs.ChangePasswordDialog = React.createClass({
        mixins: [
            dialogMixin,
            React.addons.LinkedStateMixin
        ],
        getDefaultProps: function() {
            return {
                title: i18n('dialog.change_password.title'),
                modalClass: 'change-password'
            };
        },
        getInitialState: function() {
            return {
                currentPassword: '',
                confirmationPassword: '',
                newPassword: '',
                validationError: false
            };
        },
        getError: function(name) {
            var ns = 'dialog.change_password.';
            if (name == 'currentPassword' && this.state.validationError) return i18n(ns + 'wrong_current_password');
            if (this.state.newPassword != this.state.confirmationPassword) {
                if (name == 'confirmationPassword') return i18n(ns + 'new_password_mismatch');
                if (name == 'newPassword') return '';
            }
            return null;
        },
        renderBody: function() {
            var ns = 'dialog.change_password.',
                fields = ['currentPassword', 'newPassword', 'confirmationPassword'],
                translationKeys = ['current_password', 'new_password', 'confirm_new_password'];
            return (
                <div className='forms-box'>
                    {_.map(fields, function(name, index) {
                        return <controls.Input
                            key={name}
                            name={name}
                            ref={name}
                            type='password'
                            label={i18n(ns + translationKeys[index])}
                            maxLength='50'
                            onChange={this.handleChange.bind(this, (name == 'currentPassword'))}
                            onKeyDown={this.handleKeyDown}
                            disabled={this.state.actionInProgress}
                            toggleable={name == 'currentPassword'}
                            defaultValue={this.state[name]}
                            error={this.getError(name)}
                        />;
                    }, this)}
                </div>
            );
        },
        renderFooter: function() {
            return [
                <button key='cancel' className='btn btn-default' onClick={this.close} disabled={this.state.actionInProgress}>
                    {i18n('common.cancel_button')}
                </button>,
                <button key='apply' className='btn btn-success' onClick={this.changePassword}
                    disabled={this.state.actionInProgress || !this.isPasswordChangeAvailable()}>
                    {i18n('common.apply_button')}
                </button>
            ];
        },
        isPasswordChangeAvailable: function() {
            return this.state.newPassword.length && !this.state.validationError &&
                (this.state.newPassword == this.state.confirmationPassword);
        },
        handleKeyDown: function(e) {
            if (e.key == 'Enter') {
                e.preventDefault();
                this.changePassword();
            }
            if (e.key == ' ') {
                e.preventDefault();
                return false;
            }
        },
        handleChange: function(clearError, name, value) {
            var newState = {};
            newState[name] = value.trim();
            if (clearError) {
                newState.validationError = false;
            }
            this.setState(newState);
        },
        changePassword: function() {
            if (this.isPasswordChangeAvailable()) {
                var keystoneClient = app.keystoneClient;
                this.setState({actionInProgress: true});
                keystoneClient.changePassword(this.state.currentPassword, this.state.newPassword)
                    .done(_.bind(function() {
                        dispatcher.trigger(this.state.newPassword == keystoneClient.DEFAULT_PASSWORD ? 'showDefaultPasswordWarning' : 'hideDefaultPasswordWarning');
                        app.user.set({token: keystoneClient.token});
                        this.close();
                    }, this))
                    .fail(_.bind(function() {
                        this.setState({validationError: true, actionInProgress: false});
                        $(this.refs.currentPassword.getInputDOMNode()).focus();
                    }, this));
            }
        }
    });

    dialogs.RegistrationDialog = React.createClass({
        mixins: [
            dialogMixin,
            registrationResponseErrorMixin,
            componentMixins.backboneMixin('registrationForm', 'change invalid')
        ],
        getInitialState: function() {
            return {
                loading: true
            };
        },
        getDefaultProps: function() {
            return {
                title: i18n('dialog.registration.title'),
                modalClass: 'registration',
                backdrop: 'static'
            };
        },
        componentDidMount: function() {
            var registrationForm = this.props.registrationForm;
            registrationForm.fetch()
                .then(null, function() {
                    registrationForm.url = registrationForm.nailgunUrl;
                    return registrationForm.fetch();
                })
                .fail(_.bind(function(response) {
                    this.showResponseErrors(response);
                    this.setState({connectionError: true});
                }, this))
                .always(_.bind(function() {this.setState({loading: false});}, this));
        },
        onChange: function(inputName, value) {
            var registrationForm = this.props.registrationForm,
                name = registrationForm.makePath('credentials', inputName, 'value');
            if (registrationForm.validationError) delete registrationForm.validationError['credentials.' + inputName];
            registrationForm.set(name, value);
        },
        composeOptions: function(values) {
            return _.map(values, function(value, index) {
                return (
                    <option key={index} value={value.data}>
                        {value.label}
                    </option>
                );
            });
        },
        getAgreementLink: function(link) {
            return (<span>{i18n('dialog.registration.i_agree')} <a href={link} target='_blank'>{i18n('dialog.registration.terms_and_conditions')}</a></span>);
        },
        validateRegistrationForm: function() {
            var registrationForm = this.props.registrationForm,
                isValid = registrationForm.isValid();
            if (!registrationForm.attributes.credentials.agree.value) {
                if (!registrationForm.validationError) registrationForm.validationError = {};
                registrationForm.validationError['credentials.agree'] = i18n('dialog.registration.agree_error');
                isValid = false;
            }
            this.setState({
                error: null,
                hideRequiredFieldsNotice: isValid
            });
            if (isValid) this.createAccount();
        },
        createAccount: function() {
            var registrationForm = this.props.registrationForm;
            this.setState({actionInProgress: true});
            registrationForm.save(registrationForm.attributes, {type: 'POST'})
                .done(_.bind(function(response) {
                    var currentAttributes = _.cloneDeep(this.props.settings.attributes);

                    var collector = function(path) {
                        return function(name) {
                            this.props.settings.set(this.props.settings.makePath(path, name, 'value'), response[name]);
                        };
                    };
                    _.each(['company', 'name', 'email'], collector('statistics'), this);
                    _.each(['email', 'password'], collector('tracking'), this);

                    this.props.saveSettings(currentAttributes)
                        .done(_.bind(function() {
                            this.props.tracking.set(this.props.settings.attributes);
                            this.props.setConnected();
                            this.close();
                        }, this));
                }, this))
                .fail(_.bind(function(response) {
                    this.setState({actionInProgress: false});
                    this.showResponseErrors(response, registrationForm);
                }, this));
        },
        checkCountry: function() {
            var country = this.props.registrationForm.attributes.credentials.country.value;
            return !(country == 'Canada' || country == 'United States' || country == 'us');
        },
        renderBody: function() {
            var registrationForm = this.props.registrationForm;
            if (this.state.loading) return <controls.ProgressBar />;
            var fieldsList = registrationForm.attributes.credentials,
                actionInProgress = this.state.actionInProgress,
                error = this.state.error,
                sortedFields = _.chain(_.keys(fieldsList))
                    .without('metadata')
                    .sortBy(function(inputName) {return fieldsList[inputName].weight;})
                    .value(),
                halfWidthField = ['first_name', 'last_name', 'company', 'phone', 'country', 'region'];
            return (
                <div className='registration-form tracking'>
                    {actionInProgress && <controls.ProgressBar />}
                    {error &&
                        <div className='text-danger'>
                            <i className='glyphicon glyphicon-danger-sign' />
                            {error}
                        </div>
                    }
                    {!this.state.hideRequiredFieldsNotice && !this.state.connectionError &&
                        <div className='alert alert-warning'>
                            {i18n('welcome_page.register.required_fields')}
                        </div>
                    }
                    <form className='form-inline row'>
                        {_.map(sortedFields, function(inputName) {
                            var input = fieldsList[inputName],
                                path = 'credentials.' + inputName,
                                inputError = (registrationForm.validationError || {})[path],
                                classes = {
                                    'col-md-12': !_.contains(halfWidthField, inputName),
                                    'col-md-6': _.contains(halfWidthField, inputName),
                                    'text-center': inputName == 'agree'
                                };
                            return <controls.Input
                                ref={inputName}
                                key={inputName}
                                name={inputName}
                                label={inputName != 'agree' ? input.label : this.getAgreementLink(input.description)}
                                {... _.pick(input, 'type', 'value')}
                                children={input.type == 'select' && this.composeOptions(input.values)}
                                wrapperClassName={utils.classNames(classes)}
                                onChange={this.onChange}
                                error={inputError}
                                disabled={actionInProgress || (inputName == 'region' && this.checkCountry())}
                                description={inputName != 'agree' && input.description}
                                maxLength='50'
                            />;
                        }, this)}
                    </form>
                </div>
            );
        },
        renderFooter: function() {
            var buttons = [
                <button key='cancel' className='btn btn-default' onClick={this.close}>
                    {i18n('common.cancel_button')}
                </button>
            ];
            if (!this.state.loading) buttons.push(
                <button key='apply' className='btn btn-success' disabled={this.state.actionInProgress || this.state.connectionError} onClick={this.validateRegistrationForm}>
                    {i18n('welcome_page.register.create_account')}
                </button>
            );
            return buttons;
        }
    });

    dialogs.RetrievePasswordDialog = React.createClass({
        mixins: [
            dialogMixin,
            registrationResponseErrorMixin,
            componentMixins.backboneMixin('remoteRetrievePasswordForm', 'change invalid')
        ],
        getInitialState: function() {
            return {loading: true};
        },
        getDefaultProps: function() {
            return {
                title: i18n('dialog.retrieve_password.title'),
                modalClass: 'retrieve-password-form'
            };
        },
        componentDidMount: function() {
            var remoteRetrievePasswordForm = this.props.remoteRetrievePasswordForm;
            remoteRetrievePasswordForm.fetch()
                .then(null, function() {
                    remoteRetrievePasswordForm.url = remoteRetrievePasswordForm.nailgunUrl;
                    return remoteRetrievePasswordForm.fetch();
                })
                .fail(_.bind(function(response) {
                    this.showResponseErrors(response);
                    this.setState({connectionError: true});
                }, this))
                .always(_.bind(function() {this.setState({loading: false});}, this));
        },
        onChange: function(inputName, value) {
            var remoteRetrievePasswordForm = this.props.remoteRetrievePasswordForm;
            if (remoteRetrievePasswordForm.validationError) delete remoteRetrievePasswordForm.validationError['credentials.email'];
            remoteRetrievePasswordForm.set('credentials.email.value', value);
        },
        retrievePassword: function() {
            var remoteRetrievePasswordForm = this.props.remoteRetrievePasswordForm;
            if (remoteRetrievePasswordForm.isValid()) {
                this.setState({actionInProgress: true});
                remoteRetrievePasswordForm.save()
                    .done(this.passwordSent)
                    .fail(this.showResponseErrors)
                    .always(_.bind(function() {
                        this.setState({actionInProgress: false});
                    }, this));
            }
        },
        passwordSent: function() {
            this.setState({passwordSent: true});
        },
        renderBody: function() {
            var ns = 'dialog.retrieve_password.',
                remoteRetrievePasswordForm = this.props.remoteRetrievePasswordForm;
            if (this.state.loading) return <controls.ProgressBar />;
            var error = this.state.error,
                actionInProgress = this.state.actionInProgress,
                input = (remoteRetrievePasswordForm.get('credentials') || {}).email,
                inputError = remoteRetrievePasswordForm ? (remoteRetrievePasswordForm.validationError || {})['credentials.email'] : null;
            return (
                <div className='retrieve-password-content'>
                    {!this.state.passwordSent ?
                        <div>
                            {actionInProgress && <controls.ProgressBar />}
                            {error &&
                                <div className='text-danger'>
                                    <i className='glyphicon glyphicon-danger-sign' />
                                    {error}
                                </div>
                            }
                            {input &&
                                <div>
                                    <p>{i18n(ns + 'submit_email')}</p>
                                    <controls.Input
                                        {... _.pick(input, 'type', 'value', 'description')}
                                        onChange={this.onChange}
                                        error={inputError}
                                        disabled={actionInProgress}
                                        placeholder={input.label}
                                    />
                                </div>
                            }
                        </div>
                    :
                        <div>
                            <div>{i18n(ns + 'done')}</div>
                            <div>{i18n(ns + 'check_email')}</div>
                        </div>
                    }
                </div>
            );
        },
        renderFooter: function() {
            if (this.state.passwordSent) return [
                <button key='close' className='btn btn-default' onClick={this.close}>
                    {i18n('common.close_button')}
                </button>
            ];
            var buttons = [
                <button key='cancel' className='btn btn-default' onClick={this.close}>
                    {i18n('common.cancel_button')}
                </button>
            ];
            if (!this.state.loading) buttons.push(
                <button key='apply' className='btn btn-success' disabled={this.state.actionInProgress || this.state.connectionError} onClick={this.retrievePassword}>
                    {i18n('dialog.retrieve_password.send_new_password')}
                </button>
            );
            return buttons;
        }
    });

    dialogs.CreateNodeNetworkGroupDialog = React.createClass({
        mixins: [dialogMixin],
        getDefaultProps: function() {
            return {
                title: i18n('cluster_page.network_tab.add_node_network_group'),
                ns: 'cluster_page.network_tab.'
            };
        },
        getInitialState: function() {
            return {
                error: null
            };
        },
        renderBody: function() {
            return (
                <div className='node-network-group-creation'>
                    <controls.Input
                        name='node-network-group-name'
                        type='text'
                        label={i18n(this.props.ns + 'node_network_group_name')}
                        onChange={this.onChange}
                        error={this.state.error}
                        wrapperClassName='node-group-name'
                        inputClassName='node-group-input-name'
                        maxLength='50'
                        disabled={this.state.actionInProgress}
                        autoFocus
                    />
                </div>
            );
        },
        renderFooter: function() {
            return [
                <button key='cancel' className='btn btn-default' onClick={this.close} disabled={this.state.actionInProgress}>
                    {i18n('common.cancel_button')}
                </button>,
                <button key='apply' className='btn btn-success' onClick={this.createNodeNetworkGroup} disabled={this.state.actionInProgress || this.state.error}>
                    {i18n(this.props.ns + 'add')}
                </button>
            ];
        },
        onKeyDown: function(e) {
            if (e.key == 'Enter') {
                e.preventDefault();
                this.createNodeNetworkGroup();
            }
        },
        onChange: function(name, value) {
            this.setState({
                error: null,
                name: value
            });
        },
        createNodeNetworkGroup: function() {
            var error = (new models.NodeNetworkGroup()).validate({
                name: this.state.name,
                nodeNetworkGroups: this.props.nodeNetworkGroups
            });
            if (error) {
                this.setState({error: error});
            } else {
                this.setState({actionInProgress: true});
                (new models.NodeNetworkGroup({
                    cluster_id: this.props.clusterId,
                    name: this.state.name
                }))
                    .save(null, {validate: false})
                    .then(
                        this.submitAction,
                        (response) => {
                            this.close();
                            utils.showErrorDialog({
                                title: i18n(this.props.ns + 'node_network_group_creation_error'),
                                response: response
                            });
                        }
                    );
            }
        }
    });

    dialogs.RemoveNodeNetworkGroupDialog = React.createClass({
        mixins: [dialogMixin],
        getDefaultProps: function() {
            return {title: i18n('dialog.remove_node_network_group.title')};
        },
        renderBody: function() {
            return (
                <div>
                    <div className='text-danger'>
                        {this.renderImportantLabel()}
                        {this.props.showUnsavedChangesWarning && (i18n('dialog.remove_node_network_group.unsaved_changes_alert') + ' ')}
                        {i18n('dialog.remove_node_network_group.confirmation')}
                    </div>
                </div>
            );
        },
        renderFooter: function() {
            return ([
                <button key='cancel' className='btn btn-default' onClick={this.close}>
                    {i18n('common.cancel_button')}
                </button>,
                <button
                    key='remove'
                    className='btn btn-danger remove-cluster-btn'
                    onClick={this.submitAction}
                >
                    {i18n('common.delete_button')}
                </button>
            ]);
        }
    });

    return dialogs;
});
