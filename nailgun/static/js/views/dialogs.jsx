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
    'jsx!views/controls',
    'jsx!views/statistics_mixin',
    'jsx!component_mixins'
],
function($, _, i18n, Backbone, React, utils, models, dispatcher, controls, statisticsMixin, componentMixins) {
    'use strict';

    var dialogs = {};

    var dialogMixin = {
        propTypes: {
            title: React.PropTypes.node,
            message: React.PropTypes.node,
            modalClass: React.PropTypes.node,
            error: React.PropTypes.bool
        },
        statics: {
            show: function(options) {
                return utils.universalMount(this, options, $('#modal-container'));
            }
        },
        getInitialState: function() {
            return {actionInProgress: false};
        },
        componentDidMount: function() {
            Backbone.history.on('route', this.close, this);
            var $el = $(this.getDOMNode());
            $el.on('hidden', this.handleHidden);
            $el.on('shown', function() {$el.find('[autofocus]:first').focus();});
            $el.modal({background: true, keyboard: true});
        },
        componentWillUnmount: function() {
            Backbone.history.off(null, null, this);
            $(this.getDOMNode()).off('shown hidden');
        },
        handleHidden: function() {
            React.unmountComponentAtNode(this.getDOMNode().parentNode);
        },
        close: function() {
            $(this.getDOMNode()).modal('hide');
        },
        showError: function(response, message) {
            var props = {error: true};
            props.message = utils.getResponseText(response) || message;
            this.setProps(props);
        },
        renderImportantLabel: function() {
            return <span className='label label-important'>{i18n('common.important')}</span>;
        },
        render: function() {
            var classes = {'modal fade': true};
            classes[this.props.modalClass] = this.props.modalClass;
            return (
                <div className={utils.classNames(classes)} tabIndex="-1">
                    <div className='modal-header'>
                        <button type='button' className='close' onClick={this.close}>&times;</button>
                        <h3>{this.props.title || this.state.title || (this.props.error ? i18n('dialog.error_dialog.title') : '')}</h3>
                    </div>
                    <div className='modal-body'>
                        {this.props.error ?
                            <div className='text-error'>
                                {this.props.message || i18n('dialog.error_dialog.warning')}
                            </div>
                        : this.renderBody()}
                    </div>
                    <div className='modal-footer'>
                        {this.renderFooter && !this.props.error ? this.renderFooter() : <button className='btn' onClick={this.close}>{i18n('common.close_button')}</button>}
                    </div>
                </div>
            );
        }
    };

    dialogs.ErrorDialog = React.createClass({
        mixins: [dialogMixin],
        getDefaultProps: function() {
            return {error: true};
        }
    });

    dialogs.DiscardNodeChangesDialog = React.createClass({
        mixins: [dialogMixin],
        getDefaultProps: function() {return {title: i18n('dialog.discard_changes.title')};},
        discardNodeChanges: function() {
            this.setState({actionInProgress: true});
            var nodes = new models.Nodes(_.compact(this.props.cluster.get('nodes').map(function(node) {
                if (node.get('pending_addition') || node.get('pending_deletion') || node.get('pending_roles').length) {
                    var data = {id: node.id, pending_roles: [], pending_addition: false, pending_deletion: false};
                    if (node.get('pending_addition')) data.cluster_id = null;
                    return data;
                }
            })));
            Backbone.sync('update', nodes)
                .then(_.bind(function() {
                    return $.when(this.props.cluster.fetch(), this.props.cluster.fetchRelated('nodes'));
                }, this))
                .done(_.bind(function() {
                    dispatcher.trigger('updateNodeStats');
                    this.close();
                }, this))
                .fail(this.showError);
        },
        renderChangedNodeAmount: function(nodes, dictKey) {
            return nodes.length ? <div key={dictKey} className='deploy-task-name'>
                {i18n('dialog.display_changes.' + dictKey, {count: nodes.length})}
            </div> : null;
        },
        renderBody: function() {
            var nodes = this.props.cluster.get('nodes');
            return (
                <div>
                    <div className='msg-error'>
                        {this.renderImportantLabel()}
                        {i18n('dialog.discard_changes.alert_text')}
                    </div>
                    <br/>
                    {this.renderChangedNodeAmount(nodes.where({pending_addition: true}), 'added_node')}
                    {this.renderChangedNodeAmount(nodes.where({pending_deletion: true}), 'deleted_node')}
                    {this.renderChangedNodeAmount(nodes.filter(function(node) {
                        return !node.get('pending_addition') && !node.get('pending_deletion') && node.get('pending_roles').length;
                    }), 'reconfigured_node')}
                </div>
            );
        },
        renderFooter: function() {
            return ([
                <button key='cancel' className='btn' disabled={this.state.actionInProgress} onClick={this.close}>{i18n('common.cancel_button')}</button>,
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
                renderOn: 'add remove change:status'
            })
        ],
        getDefaultProps: function() {return {title: i18n('dialog.display_changes.title')};},
        getConfigModels: function() {
            var cluster = this.props.cluster,
                settings = cluster.get('settings');
            return {
                cluster: cluster,
                settings: settings,
                version: app.version,
                release: cluster.get('release'),
                default: settings,
                networking_parameters: cluster.get('networkConfiguration').get('networking_parameters')
            };
        },
        getInitialState: function() {
            var ns = 'dialog.display_changes.',
                cluster = this.props.cluster,
                configModels = this.getConfigModels(),
                validRoleModels = cluster.get('release').get('role_models').filter(function(role) {
                    return !role.checkRestrictions(configModels).result;
                }),
                limitValidations = _.zipObject(validRoleModels.map(function(role) {
                    return [role.get('name'), role.checkLimits(configModels)];
                })),
                limitRecommendations = _.zipObject(validRoleModels.map(function(role) {
                    return [role.get('name'), role.checkLimits(configModels, true, ['recommended'])];
                })),
                areSettingsInvalid = !cluster.get('settings').isValid({models: configModels});

            var networkVerificationTask = cluster.task({group: 'network'}),
                networksVerificationResult;
            if (_.isUndefined(networkVerificationTask)) {
                networksVerificationResult = {warning: i18n(ns + 'verification_not_performed')};
            } else if (networkVerificationTask.match({status: 'error'})) {
                networksVerificationResult = {error: i18n(ns + 'verification_failed')};
            } else if (networkVerificationTask.match({status: 'running'})) {
                networksVerificationResult = {warning: i18n(ns + 'verification_in_progress')};
            }

            var state = {
                ns: ns,
                amountRestrictions: limitValidations,
                amountRestrictionsRecommendations: limitRecommendations,
                isInvalid: _.any(limitValidations, {valid: false}) || areSettingsInvalid,
                networksVerificationResult: networksVerificationResult,
                areSettingsInvalid: areSettingsInvalid,
                vcenterError: null
            };

            // vcenter
            var useVcenter = cluster.get('settings').get('common.use_vcenter.value');
            if (useVcenter) {
                var vcenter = cluster.get('vcenter');
                vcenter.setModels(configModels).parseRestrictions();
                if (!vcenter.isValid()) {
                    state.isInvalid = true;
                    state.vcenterError = {
                        text: i18n('vmware.has_errors'),
                        linkUrl: '/#cluster/' + cluster.id + '/vmware',
                        linkText: i18n('vmware.tab_name')
                    };
                }
            }
            return state;
        },
        deployCluster: function() {
            this.setState({actionInProgress: true});
            dispatcher.trigger('deploymentTasksUpdated');
            var task = new models.Task();
            task.save({}, {url: _.result(this.props.cluster, 'url') + '/changes', type: 'PUT'})
                .always(this.close)
                .done(_.bind(dispatcher.trigger, dispatcher, 'deploymentTaskStarted'))
                .fail(this.showError);
        },
        renderChangedNodesAmount: function(nodes, dictKey) {
            return !!nodes.length && <div key={dictKey} className='deploy-task-name'>
                {i18n(this.state.ns + dictKey, {count: nodes.length})}
            </div>;
        },
        renderBody: function() {
            var cluster = this.props.cluster,
                nodes = cluster.get('nodes'),
                roleModels = cluster.get('release').get('role_models'),
                settingsLocked = _.contains(['new', 'stopped'], cluster.get('status')),
                needsRedeployment = cluster.needsRedeployment(),
                warningClasses = {
                    'deploy-task-notice': true,
                    'text-error': needsRedeployment || this.state.isInvalid,
                    'text-warning': settingsLocked
                };
            return (
                <div className='display-changes-dialog'>
                    {(settingsLocked || needsRedeployment || this.state.isInvalid) &&
                        <div>
                            <div className={utils.classNames(warningClasses)}>
                                <i className='icon-attention' />
                                <span>{i18n(this.state.ns + (this.state.isInvalid ? 'warnings.no_deployment' :
                                    settingsLocked ? 'locked_settings_alert' : 'redeployment_needed'))}</span>
                            </div>
                            <hr className='slim' />
                        </div>
                    }
                    {this.renderChangedNodesAmount(nodes.where({pending_addition: true}), 'added_node')}
                    {this.renderChangedNodesAmount(nodes.where({pending_deletion: true}), 'deleted_node')}
                    {!_.isNull(this.state.vcenterError) &&
                        <div className='alert alert-error'>
                            {' ' + this.state.vcenterError.text + ' '}
                            <a href={this.state.vcenterError.linkUrl}>
                                {this.state.vcenterError.linkText}
                            </a>
                        </div>
                    }
                    {this.state.areSettingsInvalid &&
                        this.showInvalidSettingsMessage()
                    }
                    <div className='amount-restrictions'>
                        {roleModels.map(_.bind(function(role) {
                            var name = role.get('name'),
                                limits = this.state.amountRestrictions[name];

                            if (limits && !limits.valid) {
                                return (<div key={'limit-error-' + name} className='alert alert-error'>{limits.message}</div>);
                            }
                        }, this))}
                        {roleModels.map(_.bind(function(role) {
                            var name = role.get('name'),
                                recommendation = this.state.amountRestrictionsRecommendations[name];

                            if (recommendation && !recommendation.valid) {
                                return (<div key={'limit-warning-' + name} className='alert alert-warning'>{recommendation.message}</div>);
                            }
                        }, this))}
                        {this.state.networksVerificationResult &&
                            this.showNetworkVerificationMessage(this.state.networksVerificationResult)
                        }
                    </div>
                </div>
            );
        },
        showInvalidSettingsMessage: function() {
            return (
                <div className={'alert alert-error'}>
                    {i18n(this.state.ns + 'invalid_settings')}
                    {' ' + i18n(this.state.ns + 'get_more_info') + ' '}
                    <a href={'#cluster/' + this.props.cluster.id + '/settings'}>
                        {i18n(this.state.ns + 'settings_link')}
                    </a>.
                </div>
            );
        },
        showNetworkVerificationMessage: function(verificationResult) {
            if (_.isEmpty(verificationResult)) return null;
            var verificationWarning = verificationResult.warning,
                verificationError = verificationResult.error,
                classes = {
                    alert: true,
                    'alert-error': !!verificationError,
                    'alert-warning': !!verificationWarning
                };
            return (
                <div className={utils.classNames(classes)}>
                    {verificationWarning || verificationError}
                    {' ' + i18n(this.state.ns + 'get_more_info') + ' '}
                    <a href={'#cluster/' + this.props.cluster.id + '/network'}>
                        {i18n(this.state.ns + 'networks_link')}
                    </a>.
                </div>
            );
        },
        renderFooter: function() {
            var classes = {
                'btn start-deployment-btn': true,
                'btn-danger': this.state.isInvalid || (this.state.networksVerificationResult || {}).error,
                'btn-success': !this.state.isInvalid
            };
            return ([
                <button key='cancel' className='btn' disabled={this.state.actionInProgress} onClick={this.close}>{i18n('common.cancel_button')}</button>,
                <button key='deploy'
                    className={utils.classNames(classes)}
                    disabled={this.state.actionInProgress || this.state.isInvalid}
                    onClick={this.deployCluster}
                >{i18n(this.state.ns + 'deploy')}</button>
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
                .always(this.close)
                .done(_.bind(dispatcher.trigger, dispatcher, 'deploymentTaskStarted'))
                .fail(_.bind(function(response) {
                    this.showError(response, i18n('dialog.stop_deployment.stop_deployment_error.stop_deployment_warning'));
                }, this));
        },
        renderBody: function() {
            return (
                <div className='msg-error'>
                    {this.renderImportantLabel()}
                    {i18n('dialog.stop_deployment.' + (this.props.cluster.get('nodes').where({status: 'provisioning'}).length ? 'provisioning_warning' : 'text'))}
                </div>
            );
        },
        renderFooter: function() {
            return ([
                <button key='cancel' className='btn' disabled={this.state.actionInProgress} onClick={this.close}>{i18n('common.cancel_button')}</button>,
                <button key='deploy' className='btn stop-deployment-btn btn-danger' disabled={this.state.actionInProgress} onClick={this.stopDeployment}>{i18n('common.stop_button')}</button>
            ]);
        }
    });

    dialogs.RemoveClusterDialog = React.createClass({
        mixins: [dialogMixin],
        getDefaultProps: function() {return {title: i18n('dialog.remove_cluster.title')};},
        removeCluster: function() {
            this.setState({actionInProgress: true});
            this.props.cluster.destroy({wait: true})
                .always(this.close)
                .done(function() {
                    dispatcher.trigger('updateNodeStats updateNotifications');
                    app.navigate('#clusters', {trigger: true});
                })
                .fail(this.showError);
        },
        renderBody: function() {
            return (
                <div className='msg-error'>
                    {this.renderImportantLabel()}
                    {i18n('dialog.remove_cluster.' + (this.props.cluster.tasks({status: 'running'}).length ? 'incomplete_actions_text' : 'node_returned_text'))}
                </div>
            );
        },
        renderFooter: function() {
            return ([
                <button key='cancel' className='btn' disabled={this.state.actionInProgress} onClick={this.close}>{i18n('common.cancel_button')}</button>,
                <button key='deploy' className='btn remove-cluster-btn btn-danger' disabled={this.state.actionInProgress} onClick={this.removeCluster}>{i18n('common.delete_button')}</button>
            ]);
        }
    });

    dialogs.ResetEnvironmentDialog = React.createClass({
        mixins: [dialogMixin],
        getDefaultProps: function() {return {title: i18n('dialog.reset_environment.title')};},
        resetEnvironment: function() {
            this.setState({actionInProgress: true});
            dispatcher.trigger('deploymentTasksUpdated');
            var task = new models.Task();
            task.save({}, {url: _.result(this.props.cluster, 'url') + '/reset', type: 'PUT'})
                .always(this.close)
                .done(_.bind(dispatcher.trigger, dispatcher, 'deploymentTaskStarted'))
                .fail(this.showError);
        },
        renderBody: function() {
            return (
                <div className='msg-error'>
                    {this.renderImportantLabel()}
                    {i18n('dialog.reset_environment.text')}
                </div>
            );
        },
        renderFooter: function() {
            return ([
                <button key='cancel' className='btn' onClick={this.close}>{i18n('common.cancel_button')}</button>,
                <button key='reset' className='btn btn-danger reset-environment-btn' onClick={this.resetEnvironment} disabled={this.state.actionInProgress}>{i18n('common.reset_button')}</button>
            ]);
        }
    });

    dialogs.UpdateEnvironmentDialog = React.createClass({
        mixins: [dialogMixin],
        getDefaultProps: function() {return {title: i18n('dialog.update_environment.title')};},
        updateEnvironment: function() {
            this.setState({actionInProgress: true});
            var cluster = this.props.cluster;
            cluster.save({pending_release_id: this.props.pendingReleaseId || cluster.get('release_id')}, {patch: true, wait: true})
                .always(this.close)
                .fail(this.showError)
                .done(_.bind(function() {
                    dispatcher.trigger('deploymentTasksUpdated');
                    (new models.Task()).save({}, {url: _.result(cluster, 'url') + '/update', type: 'PUT'})
                        .done(_.bind(dispatcher.trigger, dispatcher, 'deploymentTaskStarted'));
                }, this));
        },
        renderBody: function() {
            var action = this.props.action;
            return (
                <div>
                    {action == 'update' && this.props.isDowngrade ?
                        <div className='msg-error'>
                            {this.renderImportantLabel()}
                            {i18n('dialog.' + action + '_environment.downgrade_warning')}
                        </div>
                    :
                        <div>{i18n('dialog.' + action + '_environment.text')}</div>
                    }
                </div>
            );
        },
        renderFooter: function() {
            var action = this.props.action,
                classes = utils.classNames({
                    'btn update-environment-btn': true,
                    'btn-success': action == 'update',
                    'btn-danger': action != 'update'
                });
            return ([
                <button key='cancel' className='btn' onClick={this.close}>{i18n('common.cancel_button')}</button>,
                <button key='reset' className={classes} onClick={this.updateEnvironment} disabled={this.state.actionInProgress}>{i18n('common.' + action + '_button')}</button>
            ]);
        }
    });

    dialogs.ShowNodeInfoDialog = React.createClass({
        mixins: [
            dialogMixin,
            componentMixins.backboneMixin('node')
        ],
        getInitialState: function() {
            return {title: i18n('dialog.show_node.default_dialog_title')};
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
                }
            } catch (ignore) {}
            return !_.isNumber(value) && _.isEmpty(value) ? '\u00A0' : value;
        },
        componentDidUpdate: function() {
            this.assignAccordionEvents();
            this.setDialogTitle();
        },
        componentDidMount: function() {
            this.assignAccordionEvents();
            this.setDialogTitle();
        },
        setDialogTitle: function() {
            var name = this.props.node && this.props.node.get('name');
            if (name && name != this.state.title) this.setState({title: name});
        },
        assignAccordionEvents: function() {
            $('.accordion-body', this.getDOMNode())
                .on('show', function(e) {$(e.currentTarget).siblings('.accordion-heading').find('i').removeClass('icon-expand').addClass('icon-collapse');})
                .on('hide', function(e) {$(e.currentTarget).siblings('.accordion-heading').find('i').removeClass('icon-collapse').addClass('icon-expand');})
                .on('hidden', function(e) {e.stopPropagation();});
        },
        toggle: function(groupIndex) {
            $(this.refs['togglable_' + groupIndex].getDOMNode()).collapse('toggle');
        },
        renderBody: function() {
            var node = this.props.node,
                meta = node.get('meta');
            if (!meta) return <controls.ProgressBar />;
            var groupOrder = ['system', 'cpu', 'memory', 'disks', 'interfaces'],
                groups = _.sortBy(_.keys(meta), function(group) {return _.indexOf(groupOrder, group)}),
                sortOrder = {
                    disks: ['name', 'model', 'size'],
                    interfaces: ['name', 'mac', 'state', 'ip', 'netmask', 'current_speed', 'max_speed', 'driver', 'bus_info']
                };
            return (
                <div>
                    <div className='row-fluid'>
                        <div className='span5'><div className='node-image-outline'></div></div>
                        <div className='span7'>
                            <div><strong>{i18n('dialog.show_node.manufacturer_label')}: </strong>{node.get('manufacturer') || i18n('common.not_available')}</div>
                            <div><strong>{i18n('dialog.show_node.mac_address_label')}: </strong>{node.get('mac') || i18n('common.not_available')}</div>
                            <div><strong>{i18n('dialog.show_node.fqdn_label')}: </strong>{(node.get('meta').system || {}).fqdn || node.get('fqdn') || i18n('common.not_available')}</div>
                        </div>
                    </div>
                    <div className='accordion' id='nodeDetailsAccordion'>
                        {_.map(groups, function(group, groupIndex) {
                            var groupEntries = meta[group],
                                subEntries = [];
                            if (group == 'interfaces' || group == 'disks') groupEntries = _.sortBy(groupEntries, 'name');
                            if (_.isPlainObject(groupEntries)) subEntries = _.find(_.values(groupEntries), _.isArray);
                            return (
                                <div className='accordion-group' key={group}>
                                    <div className='accordion-heading' onClick={this.toggle.bind(this, groupIndex)}>
                                        <div className='accordion-toggle' data-group={group}>
                                            <b>{i18n('node_details.' + group, {defaultValue: group})}</b>
                                            <span>{this.showSummary(meta, group)}</span>
                                            <i className='icon-expand pull-right'></i>
                                        </div>
                                    </div>
                                    <div className='accordion-body collapse' ref={'togglable_' + groupIndex}>
                                        <div className='accordion-inner'>
                                            {_.isArray(groupEntries) &&
                                                <div>
                                                    {_.map(groupEntries, function(entry, entryIndex) {
                                                        return (
                                                            <div className='nested-object' key={'entry_' + groupIndex + entryIndex}>
                                                                {_.map(utils.sortEntryProperties(entry, sortOrder[group]), function(propertyName) {
                                                                    return this.renderNodeInfo(propertyName, this.showPropertyValue(group, propertyName, entry[propertyName]));
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
                                            {(!_.isPlainObject(groupEntries) && !_.isArray(groupEntries)) &&
                                                <div>{groupEntries}</div>
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
            var node = this.props.node;
            return (
                <div>
                    {node.get('cluster') &&
                        <span>
                            <button className='btn btn-edit-networks' onClick={this.goToConfigurationScreen.bind(this, 'interfaces')}>{i18n('dialog.show_node.network_configuration_button')}</button>
                            <button className='btn btn-edit-disks' onClick={this.goToConfigurationScreen.bind(this, 'disks')}>{i18n('dialog.show_node.disk_configuration_button')}</button>
                        </span>
                    }
                    <button className='btn' onClick={this.close}>{i18n('common.cancel_button')}</button>
                </div>
            );
        },
        renderNodeInfo: function(name, value) {
            return (
                <div key={name + value}>
                    <label>{i18n('dialog.show_node.' + name, {defaultValue: this.showPropertyName(name)})}</label>
                    <span>{value}</span>
                </div>
            );
        }
    });

    dialogs.DiscardSettingsChangesDialog = React.createClass({
        mixins: [dialogMixin],
        getDefaultProps: function() {return {title: i18n('dialog.dismiss_settings.title'), defaultMessage: i18n('dialog.dismiss_settings.default_message')};},
        proceed: function() {
            this.close();
            dispatcher.trigger('networkConfigurationUpdated', _.bind(this.props.cb, this.props));
        },
        renderBody: function() {
            var message = this.props.verification ? i18n('dialog.dismiss_settings.verify_message') : this.props.defaultMessage;
            return (
                <div className='msg-error dismiss-settings-dialog'>
                    {this.renderImportantLabel()}
                    {message}
                </div>
            );
        },
        renderFooter: function() {
            var verification = !!this.props.verification,
                buttons = [<button key='stay' className='btn btn-return' onClick={this.close}>{i18n('dialog.dismiss_settings.stay_button')}</button>],
                buttonToAdd = <button key='leave' className='btn btn-danger proceed-btn' onClick={this.proceed}>
                    {i18n('dialog.dismiss_settings.leave_button')}
                </button>;
            if (!verification) buttons.push(buttonToAdd);
            return buttons;
        }
    });

    dialogs.RemoveNodeConfirmDialog = React.createClass({
        mixins: [dialogMixin],
        getDefaultProps: function() {return {title: i18n('dialog.remove_node.title'), defaultMessage: i18n('dialog.remove_node.default_message')};},
        proceed: function() {
            this.close();
            dispatcher.trigger('networkConfigurationUpdated', this.props.cb);
        },
        renderBody: function() {
            var message = this.props.defaultMessage;
            return (
                <div className='msg-error'>
                    {this.renderImportantLabel()}
                    {message}
                </div>
            );
        },
        renderFooter: function() {
            return [
                <button key='stay' className='btn btn-return' onClick={this.close}>{i18n('common.cancel_button')}</button>,
                <button key='delete' className='btn btn-danger btn-delete' onClick={this.proceed}>
                    {i18n('cluster_page.nodes_tab.node.remove')}
                </button>
            ];
        }
    });

    dialogs.DeleteNodesDialog = React.createClass({
        mixins: [dialogMixin],
        getDefaultProps: function() {return {title: i18n('dialog.delete_nodes.title')};},
        renderBody: function() {
            return (<div className='deploy-task-notice'>{this.renderImportantLabel()} {i18n('dialog.delete_nodes.message')}</div>);
        },
        renderFooter: function() {
            return [
                <button key='cancel' className='btn' onClick={this.close}>{i18n('common.cancel_button')}</button>,
                <button key='delete' className='btn btn-danger btn-delete' onClick={this.deleteNodes} disabled={this.state.actionInProgress}>{i18n('common.delete_button')}</button>
            ];
        },
        deleteNodes: function() {
            this.setState({actionInProgress: true});
            var nodes = new models.Nodes(this.props.nodes.map(function(node) {
                if (node.get('pending_addition')) return {id: node.id, cluster_id: null, pending_addition: false, pending_roles: []};
                return {id: node.id, pending_deletion: true};
            }));
            Backbone.sync('update', nodes)
                .then(_.bind(function() {
                    return this.props.cluster.fetchRelated('nodes');
                }, this))
                .done(_.bind(function() {
                    dispatcher.trigger('updateNodeStats networkConfigurationUpdated');
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
                <form className='change-password-form'>
                    {_.map(fields, function(name, index) {
                        return (<controls.Input
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
                        />);
                    }, this)}
                </form>
            );
        },
        renderFooter: function() {
            return [
                <button key='cancel' className='btn' onClick={this.close} disabled={this.state.actionInProgress}>
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
                this.setState({actionInProgress: true});
                app.keystoneClient.changePassword(this.state.currentPassword, this.state.newPassword)
                    .done(_.bind(function() {
                        app.user.set({token: app.keystoneClient.token});
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
            componentMixins.backboneMixin('registrationForm', 'change invalid')
        ],
        getInitialState: function() {
            return {
                disabled: true,
                loading: true
            };
        },
        getDefaultProps: function() {
            return {
                title: i18n('dialog.registration.title'),
                modalClass: 'registration'
            };
        },
        componentDidMount: function() {
            var registrationForm = this.props.registrationForm;
            registrationForm.fetch()
                .done(_.bind(function() {this.setState({loading: false});}, this))
                .fail(_.bind(function() {
                    registrationForm.url = registrationForm.nailgunUrl;
                    registrationForm.fetch()
                        .fail(_.bind(function(response) {
                            var error = !response.responseText || _.isString(response.responseText) ? i18n('welcome_page.register.connection_error') : JSON.parse(response.responseText).message;
                            this.setState({error: error});
                        }, this))
                        .always(_.bind(function() {this.setState({loading: false});}, this));
                }, this));
        },
        onChange: function(inputName, value) {
            var registrationForm = this.props.registrationForm,
                name = registrationForm.makePath('credentials', inputName, 'value');
            if (registrationForm.validationError) delete registrationForm.validationError['credentials.' + inputName];
            registrationForm.set(name, value);
            this.setState({disabled: !registrationForm.attributes.credentials.agree.value});
        },
        composeOptions: function(values) {
            return _.map(values, function(value, index) {
                return (
                    <option key={index} value={value.data} disabled={value.disabled}>
                        {value.label}
                    </option>
                );
            });
        },
        getAgreementLink: function(link) {
            return (<span>{i18n('dialog.registration.i_agree')} <a href={link} target='_blank'>{i18n('dialog.registration.terms_and_conditions')}</a></span>);
        },
        goToWelcomeScreen: function() {
            if (this.props.setConnected) this.props.setConnected();
            this.close();
        },
        createAccount: function() {
            var registrationForm = this.props.registrationForm;
            if (registrationForm.isValid()) {
                this.setState({actionInProgress: true});
                registrationForm.save(registrationForm.attributes, {type: 'POST'})
                    .done(_.bind(function(response) {
                        var settings = this.props.settings,
                            registrationData = settings.get('statistics'),
                            connectionInfo = settings.get('tracking');
                        _.each(response, function(value, name) {
                            registrationData[name].value = value;
                        });
                        //FIXME: Change this part when backend will be ready
                        connectionInfo.email.value = response.email;
                        connectionInfo.password.value = 'temp';
                        settings.save(null, {patch: true, wait: true, validate: false})
                            .done(this.goToWelcomeScreen)
                            .fail(_.bind(function() {
                                this.setState({error: i18n('common.error')});
                            }, this));
                    }, this))
                    .always(_.bind(function() {
                        this.setState({actionInProgress: false});
                    }, this))
                    .fail(_.bind(function(response) {
                        var error = !response.responseText || _.isString(response.responseText) ? i18n('welcome_page.register.connection_error') : JSON.parse(response.responseText).message;
                        this.setState({error: error});
                    }, this));
            }
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
                    .value();
            return (
                <div className='registration-form'>
                    {actionInProgress && <controls.ProgressBar />}
                    {error &&
                        <div className='error'>
                            <i className='icon-attention'></i>
                            {error}
                        </div>
                    }
                    <form className='form-horizontal'>
                        {_.map(sortedFields, function(inputName) {
                            var input = fieldsList[inputName],
                                path = 'credentials.' + inputName,
                                inputError = (registrationForm.validationError || {})[path];
                            return <controls.Input
                                ref={inputName}
                                key={inputName}
                                name={inputName}
                                label={inputName != 'agree' ? input.label : this.getAgreementLink(input.description)}
                                {... _.pick(input, 'type', 'value')}
                                children={input.type == 'select' && this.composeOptions(input.values)}
                                wrapperClassName={inputName}
                                onChange={this.onChange}
                                error={inputError}
                                disabled={actionInProgress}
                                description={inputName != 'agree' && input.description}
                            />;
                        }, this)}
                    </form>
                </div>
            );
        },
        renderFooter: function() {
            return [
                <button key='cancel' className='btn' onClick={this.close}>
                    {i18n('common.cancel_button')}
                </button>,
                <button key='apply' className='btn btn-success' disabled={this.state.disabled || this.state.actionInProgress} onClick={this.createAccount}>
                    {i18n('welcome_page.register.create_account')}
                </button>
            ];
        }
    });

    dialogs.RetrievePasswordDialog = React.createClass({
        mixins: [
            dialogMixin,
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
                .done(_.bind(function() {
                    this.setState({
                        remoteRetrievePasswordForm: remoteRetrievePasswordForm,
                        loading: false
                    });
                }, this))
                .fail(_.bind(function() {
                    remoteRetrievePasswordForm.url = remoteRetrievePasswordForm.nailgunUrl;
                    remoteRetrievePasswordForm.fetch()
                        .done(_.bind(function() {
                            this.setState({remoteRetrievePasswordForm: remoteRetrievePasswordForm});
                        }, this))
                        .fail(_.bind(function(response) {
                            var error = !response.responseText || _.isString(response.responseText) ? i18n('welcome_page.register.connection_error') : JSON.parse(response.responseText).message;
                            this.setState({error: error});
                        }, this))
                        .always(_.bind(function() {this.setState({loading: false});}, this));
                }, this));
        },
        onChange: function(inputName, value) {
            var remoteRetrievePasswordForm = this.props.remoteRetrievePasswordForm;
            if (remoteRetrievePasswordForm.validationError) delete remoteRetrievePasswordForm.validationError['credentials.email'];
            remoteRetrievePasswordForm.set('credentials.email.value', value);
        },
        retrievePassword: function() {
            var remoteRetrievePasswordForm = this.props.remoteRetrievePasswordForm;
            if (remoteRetrievePasswordForm.isValid() && !this.state.error) {
                this.setState({actionInProgress: true});
                remoteRetrievePasswordForm.save()
                    .done(_.bind(this.passwordSent, this))
                    .fail(_.bind(function(response) {
                        var error = !response.responseText || _.isString(response.responseText) ? i18n('welcome_page.register.connection_error') : JSON.parse(response.responseText).message;
                        this.setState({error: error});
                    }, this))
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
                remoteRetrievePasswordForm = this.state.remoteRetrievePasswordForm;
            if (this.state.loading) return <controls.ProgressBar />;
            var error = this.state.error,
                actionInProgress = this.state.actionInProgress,
                input = remoteRetrievePasswordForm ? remoteRetrievePasswordForm.attributes.credentials.email : null,
                inputError = remoteRetrievePasswordForm ? (remoteRetrievePasswordForm.validationError || {})['credentials.email'] : null;
            return (
                <div className='retrieve-password-content'>
                    {!this.state.passwordSent ?
                        <div>
                            {actionInProgress && <controls.ProgressBar />}
                            {error &&
                                <div className='error'>
                                    <i className='icon-attention'></i>
                                    {error}
                                </div>
                            }
                            {input &&
                                <div>
                                    <div>{i18n(ns + 'submit_email')}</div>
                                    <controls.Input
                                        ref='retrieve_password'
                                        key='retrieve_password'
                                        name='retrieve_password'
                                        {... _.pick(input, 'type', 'value', 'label')}
                                        onChange={this.onChange}
                                        error={inputError}
                                        disabled={actionInProgress}
                                        description={input.description}
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
            return (
                <div>
                    {!this.state.passwordSent ?
                        <div>
                            <button key='cancel' className='btn' onClick={this.close}>
                                {i18n('common.cancel_button')}
                            </button>
                            <button key='apply' className='btn btn-success' disabled={this.state.actionInProgress || this.state.error} onClick={this.retrievePassword}>
                                {i18n('dialog.retrieve_password.send_new_password')}
                            </button>
                        </div>
                    :
                        <div>
                            <button key='close' className='btn' onClick={this.close}>
                                {i18n('common.close_button')}
                            </button>
                        </div>
                    }
                </div>
            );
        }
    });

    return dialogs;
});
