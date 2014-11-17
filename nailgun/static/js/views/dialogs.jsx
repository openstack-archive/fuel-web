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
    'require',
    'react',
    'utils',
    'models',
    'jsx!component_mixins',
    'jsx!views/controls'
],
function(require, React, utils, models, componentMixins, controls) {
    'use strict';

    var cx = React.addons.classSet;

    var dialogs = {};

    dialogs.ErrorDialog = React.createClass({
        mixins: [componentMixins.dialogMixin]
    });

    dialogs.DiscardNodeChangesDialog = React.createClass({
        mixins: [componentMixins.dialogMixin],
        getDefaultProps: function() {return {title: $.t('dialog.discard_changes.title')};},
        discardNodeChanges: function() {
            this.setState({actionInProgress: true});
            var cluster = this.props.cluster,
                nodes = new models.Nodes(cluster.get('nodes').filter(function(node) {
                    return node.get('pending_addition') || node.get('pending_deletion') || node.get('pending_roles').length;
                }));
            nodes.each(function(node) {
                var data = {pending_roles: [], pending_addition: false, pending_deletion: false};
                if (node.get('pending_addition')) data.cluster_id = null;
                node.set(data, {silent: true});
            });
            nodes.toJSON = function() {
                return this.map(function(node) {
                    return _.pick(node.attributes, 'id', 'cluster_id', 'pending_addition', 'pending_deletion', 'pending_roles');
                });
            };
            Backbone.sync('update', nodes)
                .always(_.bind(this.close, this))
                .done(_.bind(function() {
                    $.when(cluster.fetch(), cluster.get('nodes').fetch({data: {cluster_id: cluster.id}}))
                        .always(function() {
                            // we set node flags silently, so trigger resize event to redraw node list
                            cluster.get('nodes').trigger('resize');
                            app.navbar.refresh();
                        });
                }, this))
                .fail(function() {utils.showErrorDialog();});
        },
        renderChangedNodeAmount: function(nodes, dictKey) {
            return nodes.length ? <div key={dictKey} className='deploy-task-name'>
                {$.t('dialog.display_changes.' + dictKey, {count: nodes.length})}
            </div> : null;
        },
        renderBody: function() {
            var nodes = this.props.cluster.get('nodes');
            return (
                <div>
                    {this.renderChangedNodeAmount(nodes.where({pending_addition: true}), 'added_node')}
                    {this.renderChangedNodeAmount(nodes.where({pending_deletion: true}), 'deleted_node')}
                    {this.renderChangedNodeAmount(nodes.filter(function(node) {
                        return !node.get('pending_addition') && !node.get('pending_deletion') && node.get('pending_roles').length;
                    }), 'reconfigured_node')}
                    <hr className='slim' />
                    <div className='text-error deploy-task-notice'><i className='icon-attention' /> {$.t('dialog.discard_changes.alert_text')}</div>
                </div>
            );
        },
        renderFooter: function() {
            return ([
                <button key='cancel' className='btn' disabled={this.state.actionInProgress} onClick={this.close}>{$.t('common.cancel_button')}</button>,
                <button key='discard' className='btn btn-danger' disabled={this.state.actionInProgress} onClick={this.discardNodeChanges}>{$.t('dialog.discard_changes.discard_button')}</button>
            ]);
        }
    });

    dialogs.DeployChangesDialog = React.createClass({
        mixins: [componentMixins.dialogMixin],
        getDefaultProps: function() {return {title: $.t('dialog.display_changes.title')};},
        getInitialState: function() {
            // FIXME: the following amount restrictions shoud be described declaratively in configuration file
            var cluster = this.props.cluster,
                nodes = cluster.get('nodes'),
                requiredNodeAmount = this.getRequiredNodeAmount(),
                settings = cluster.get('settings');
            return {
                amountRestrictions: {
                    controller: nodes.nodesAfterDeploymentWithRole('controller') < requiredNodeAmount,
                    compute: !nodes.nodesAfterDeploymentWithRole('compute') && cluster.get('settings').get('common.libvirt_type.value') != 'vcenter',
                    mongo: !this.props.cluster.get('settings').get('additional_components.mongo.value') && this.props.cluster.get('settings').get('additional_components.ceilometer.value') && nodes.nodesAfterDeploymentWithRole('mongo') < requiredNodeAmount
                },
                areSettingsValid: settings.isValid({models: {
                    cluster: cluster,
                    version: app.version,
                    settings: settings,
                    networking_parameters: cluster.get('networkConfiguration').get('networking_parameters'),
                    default: settings
                }})
            };
        },
        getRequiredNodeAmount: function() {
            return this.props.cluster.get('mode') == 'ha_compact' ? 3 : 1;
        },
        deployCluster: function() {
            this.setState({actionInProgress: true});
            app.page.removeFinishedDeploymentTasks();
            var task = new models.Task();
            task.save({}, {url: _.result(this.props.cluster, 'url') + '/changes', type: 'PUT'})
                .always(_.bind(this.close, this))
                .done(function() {app.page.deploymentTaskStarted();})
                .fail(function() {utils.showErrorDialog();});
        },
        renderChangedNodeAmount: function(nodes, dictKey) {
            return nodes.length ? <div key={dictKey} className='deploy-task-name'>
                {$.t('dialog.display_changes.' + dictKey, {count: nodes.length})}
            </div> : null;
        },
        renderChange: function(change, nodeIds) {
            var nodes = this.props.cluster.get('nodes');
            return (
                <div key={change}>
                    <div className='deploy-task-name'>{$.t('dialog.display_changes.settings_changes.' + change)}</div>
                    <ul>
                        {_.map(nodeIds, function(id) {
                            var node = nodes.get(id);
                            return node ? <li key={change + id}>{node.get('name')}</li> : null;
                        })}
                    </ul>
                </div>
            );
        },
        renderBody: function() {
            var ns = 'dialog.display_changes.',
                cluster = this.props.cluster,
                nodes = cluster.get('nodes'),
                requiredNodeAmount = this.getRequiredNodeAmount(),
                isNew = cluster.get('status') == 'new',
                isNewOrNeedsRedeployment = isNew || cluster.needsRedeployment(),
                warningMessageClasses = cx({
                    'deploy-task-notice': true,
                    'text-error': !this.state.areSettingsValid,
                    'text-warning': isNewOrNeedsRedeployment
                });
            return (
                <div className='display-changes-dialog'>
                    {(isNewOrNeedsRedeployment || !this.state.areSettingsValid) &&
                        <div>
                            <div className={warningMessageClasses}>
                                <i className='icon-attention' />
                                <span>{$.t(ns + (!this.state.areSettingsValid ? 'warnings.settings_invalid' :
                                    isNew ? 'locked_settings_alert' : 'redeployment_needed'))}</span>
                            </div>
                            <hr className='slim' />
                        </div>
                    }
                    {this.renderChangedNodeAmount(nodes.where({pending_addition: true}), 'added_node')}
                    {this.renderChangedNodeAmount(nodes.where({pending_deletion: true}), 'deleted_node')}
                    {this.renderChangedNodeAmount(nodes.filter(function(node) {
                        return !node.get('pending_addition') && !node.get('pending_deletion') && node.get('pending_roles').length;
                    }), 'reconfigured_node')}
                    {_.map(_.groupBy(cluster.get('changes'), function(change) {return change.name;}), function(nodes, change) {
                        return this.renderChange(change, _.compact(_.pluck(nodes, 'node_id')));
                    }, this)}
                    <div className='amount-restrictions'>
                        {this.state.amountRestrictions.controller &&
                            <div className='alert alert-error'>{$.t(ns + 'warnings.controller', {count: requiredNodeAmount})}</div>
                        }
                        {this.state.amountRestrictions.compute &&
                            <div className='alert alert-error'>{$.t(ns + 'warnings.compute')}</div>
                        }
                        {this.state.amountRestrictions.mongo &&
                            <div className='alert alert-error'>{$.t(ns + 'warnings.mongo', {count: requiredNodeAmount})}</div>
                        }
                    </div>
                </div>
            );
        },
        renderFooter: function() {
            return ([
                <button key='cancel' className='btn' disabled={this.state.actionInProgress} onClick={this.close}>{$.t('common.cancel_button')}</button>,
                <button key='deploy'
                    className={'btn start-deployment-btn btn-' + (_.compact(_.values(this.state.amountRestrictions)).length ? 'danger' : 'success')}
                    disabled={this.state.actionInProgress || !this.state.areSettingsValid}
                    onClick={this.deployCluster}
                >{$.t('dialog.display_changes.deploy')}</button>
            ]);
        }
    });

    dialogs.StopDeploymentDialog = React.createClass({
        mixins: [componentMixins.dialogMixin],
        getDefaultProps: function() {return {title: $.t('dialog.stop_deployment.title')};},
        stopDeployment: function() {
            this.setState({actionInProgress: true});
            var task = new models.Task();
            task.save({}, {url: _.result(this.props.cluster, 'url') + '/stop_deployment', type: 'PUT'})
                .always(_.bind(this.close, this))
                .done(function() {app.page.deploymentTaskStarted();})
                .fail(function(response) {
                    utils.showErrorDialog({
                        title: $.t('dialog.stop_deployment.stop_deployment_error.title'),
                        message: utils.getResponseText(response) || $.t('dialog.stop_deployment.stop_deployment_error.stop_deployment_warning')
                    });
                });
        },
        renderBody: function() {
            return (
                <div className='msg-error'>
                    {this.renderImportantLabel()}
                    {$.t('dialog.stop_deployment.' + (this.props.cluster.get('nodes').where({status: 'provisioning'}).length ? 'provisioning_warning' : 'text'))}
                </div>
            );
        },
        renderFooter: function() {
            return ([
                <button key='cancel' className='btn' disabled={this.state.actionInProgress} onClick={this.close}>{$.t('common.cancel_button')}</button>,
                <button key='deploy' className='btn stop-deployment-btn btn-danger' disabled={this.state.actionInProgress} onClick={this.stopDeployment}>{$.t('common.stop_button')}</button>
            ]);
        }
    });

    dialogs.RemoveClusterDialog = React.createClass({
        mixins: [componentMixins.dialogMixin],
        getDefaultProps: function() {return {title: $.t('dialog.remove_cluster.title')};},
        removeCluster: function() {
            this.setState({actionInProgress: true});
            this.props.cluster.destroy({wait: true})
                .always(_.bind(this.close, this))
                .done(function() {
                    app.navbar.refresh();
                    app.navigate('#clusters', {trigger: true});
                })
                .fail(function() {utils.showErrorDialog();});
        },
        renderBody: function() {
            return (
                <div className='msg-error'>
                    {this.renderImportantLabel()}
                    {$.t('dialog.remove_cluster.' + (this.props.cluster.tasks({status: 'running'}).length ? 'incomplete_actions_text' : 'node_returned_text'))}
                </div>
            );
        },
        renderFooter: function() {
            return ([
                <button key='cancel' className='btn' disabled={this.state.actionInProgress} onClick={this.close}>{$.t('common.cancel_button')}</button>,
                <button key='deploy' className='btn remove-cluster-btn btn-danger' disabled={this.state.actionInProgress} onClick={this.removeCluster}>{$.t('common.delete_button')}</button>
            ]);
        }
    });

    dialogs.ResetEnvironmentDialog = React.createClass({
        mixins: [componentMixins.dialogMixin],
        getDefaultProps: function() {return {title: $.t('dialog.reset_environment.title')};},
        resetEnvironment: function() {
            this.setState({actionInProgress: true});
            app.page.removeFinishedDeploymentTasks();
            var task = new models.Task();
            task.save({}, {url: _.result(this.props.cluster, 'url') + '/reset', type: 'PUT'})
                .always(_.bind(this.close, this))
                .done(function() {app.page.deploymentTaskStarted();})
                .fail(function() {utils.showErrorDialog();});
        },
        renderBody: function() {
            return (
                <div className='msg-error'>
                    {this.renderImportantLabel()}
                    {$.t('dialog.reset_environment.text')}
                </div>
            );
        },
        renderFooter: function() {
            return ([
                <button key='cancel' className='btn' onClick={this.close}>{$.t('common.cancel_button')}</button>,
                <button key='reset' className='btn btn-danger reset-environment-btn' onClick={this.resetEnvironment} disabled={this.state.actionInProgress}>{$.t('common.reset_button')}</button>
            ]);
        }
    });

    dialogs.UpdateEnvironmentDialog = React.createClass({
        mixins: [componentMixins.dialogMixin],
        getDefaultProps: function() {return {title: $.t('dialog.update_environment.title')};},
        updateEnvironment: function() {
            this.setState({actionInProgress: true});
            var cluster = this.props.cluster;
            cluster.save({pending_release_id: this.props.pendingReleaseId || cluster.get('release_id')}, {patch: true, wait: true})
                .always(_.bind(this.close, this))
                .fail(function() {utils.showErrorDialog();})
                .done(_.bind(function() {
                    var task = new models.Task();
                    task.save({}, {url: _.result(cluster, 'url') + '/update', type: 'PUT'})
                        .done(function() {app.page.deploymentTaskStarted();});
                }, this));
        },
        renderBody: function() {
            var action = this.props.action;
            return (
                <div>
                    {action == 'update' && this.props.isDowngrade ?
                        <div className='msg-error'>
                            {this.renderImportantLabel()}
                            {$.t('dialog.' + action + '_environment.downgrade_warning')}
                        </div>
                    :
                        <div>{$.t('dialog.' + action + '_environment.text')}</div>
                    }
                </div>
            );
        },
        renderFooter: function() {
            var action = this.props.action,
                classes = React.addons.classSet({
                    'btn update-environment-btn': true,
                    'btn-success': action == 'update',
                    'btn-danger': action != 'update'
                });
            return ([
                <button key='cancel' className='btn' onClick={this.close}>{$.t('common.cancel_button')}</button>,
                <button key='reset' className={classes} onClick={this.updateEnvironment} disabled={this.state.actionInProgress}>{$.t('common.' + action + '_button')}</button>
            ]);
        }
    });

    dialogs.ShowNodeInfoDialog = React.createClass({
        mixins: [componentMixins.dialogMixin],
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
                            summary += ', ' + utils.showMemorySize(meta.memory.total) + ' ' + $.t('dialog.show_node.total');
                        } else summary = utils.showMemorySize(meta.memory.total) + ' ' + $.t('dialog.show_node.total');
                        break;
                    case 'disks':
                        summary = meta.disks.length + ' ';
                        summary += $.t('dialog.show_node.drive', {count: meta.disks.length});
                        summary += ', ' + utils.showDiskSize(_.reduce(_.pluck(meta.disks, 'size'), function(sum, n) {return sum + n;}, 0)) + ' ' + $.t('dialog.show_node.total');
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
            return _.isEmpty(value) ? '\u00A0' : value;
        },
        componentDidMount: function() {
            $('.accordion-body')
                .on('show', function(e) {$(e.currentTarget).siblings('.accordion-heading').find('i').removeClass('icon-expand').addClass('icon-collapse');})
                .on('hide', function(e) {$(e.currentTarget).siblings('.accordion-heading').find('i').removeClass('icon-collapse').addClass('icon-expand');})
                .on('hidden', function(e) {e.stopPropagation();});
        },
        toggle: function(groupIndex) {
            $(this.refs['togglable_' + groupIndex].getDOMNode()).collapse('toggle');
        },
        renderBody: function() {
            var node = this.props.node,
                meta = node.get('meta'),
                groupOrder = ['system', 'cpu', 'memory', 'disks', 'interfaces'],
                groups = _.sortBy(_.keys(meta), function(group) {return _.indexOf(groupOrder, group)}),
                sortOrder = {
                    disks: ['name', 'model', 'size'],
                    interfaces: ['name', 'mac', 'state', 'ip', 'netmask', 'current_speed', 'max_speed']
                };
            return (
                <div>
                    {(node.deferred && node.deferred.state() == 'pending') ?
                        <controls.ProgressBar />
                        :
                        <div>
                            <div className='row-fluid'>
                                <div className='span5'><div className='node-image-outline'></div></div>
                                <div className='span7'>
                                    <div><strong>{$.t('dialog.show_node.manufacturer_label')}: </strong>{node.get('manufacturer') || $.t('common.not_available')}</div>
                                    <div><strong>{$.t('dialog.show_node.mac_address_label')}: </strong>{node.get('mac') || $.t('common.not_available')}</div>
                                    <div><strong>{$.t('dialog.show_node.fqdn_label')}: </strong>{(node.get('meta').system || {}).fqdn || node.get('fqdn') || $.t('common.not_available')}</div>
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
                                                    <b>{$.t('node_details.' + group, {defaultValue: group})}</b>
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
                                                                        {_.map(utils.sortEntryProperties(entry, sortOrder[group]), function(propertyName, propertyArrIndex) {
                                                                            return this.renderNodeInfo($.t('dialog.show_node.' + propertyName, {defaultValue: this.showPropertyName(propertyName)}), this.showPropertyValue(group, propertyName, entry[propertyName]), 'entry_' + groupIndex + entryIndex + propertyArrIndex);
                                                                        }, this)}
                                                                    </div>
                                                                );
                                                            }, this)}
                                                        </div>
                                                    }
                                                    {_.isPlainObject(groupEntries) &&
                                                        <div>
                                                            {_.map(groupEntries, function(propertyValue, propertyName) {
                                                                if (!_.isArray(propertyValue) && !_.isNumber(propertyName))
                                                                    return this.renderNodeInfo($.t('dialog.show_node.' + propertyName, {defaultValue: this.showPropertyName(propertyName)}), this.showPropertyValue(group, propertyName, propertyValue), 'entry_' + groupIndex + propertyName);
                                                            }, this)}
                                                            {!_.isEmpty(subEntries) &&
                                                                <div>
                                                                    {_.map(subEntries, function(subentry, subentrysIndex) {
                                                                        return (
                                                                            <div className='nested-object' key={'subentries_' + groupIndex + subentrysIndex}>
                                                                                {_.map(utils.sortEntryProperties(subentry), function(propertyName, subentryIndex) {
                                                                                    return this.renderNodeInfo($.t('dialog.show_node.' + propertyName, {defaultValue: this.showPropertyName(propertyName)}), this.showPropertyValue(group, propertyName, subentry[propertyName]), 'subentry_' + groupIndex + subentryIndex);
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
                    }
                </div>
            );
        },
        renderFooter: function() {
            var node = this.props.node;
            return (
                <div>
                    {node.get('cluster') &&
                        <span>
                            <button className='btn btn-edit-networks' onClick={this.goToConfigurationScreen.bind(this, 'interfaces')}>{$.t('dialog.show_node.network_configuration_button')}</button>
                            <button className='btn btn-edit-disks' onClick={this.goToConfigurationScreen.bind(this, 'disks')}>{$.t('dialog.show_node.disk_configuration_button')}</button>
                        </span>
                    }
                    <button className='btn' onClick={this.close}>{$.t('common.cancel_button')}</button>
                </div>
            );
        },
        renderNodeInfo: function(label, span, key) {
            return (
                <div key={key}>
                    <label>{label}</label>
                    <span>{span}</span>
                </div>
            );
        }
    });

    dialogs.DiscardSettingsChangesDialog = React.createClass({
        mixins: [componentMixins.dialogMixin],
        getDefaultProps: function() {return {title: $.t('dialog.dismiss_settings.title'), defaultMessage: $.t('dialog.dismiss_settings.default_message')};},
        proceed: function() {
            this.close();
            app.page.removeFinishedNetworkTasks().always(_.bind(this.props.cb, this.props));
        },
        renderBody: function() {
            var message = this.props.verification ? $.t('dialog.dismiss_settings.verify_message') : this.props.defaultMessage;
            return (
                <div className='msg-error dismiss-settings-dialog'>
                    {this.renderImportantLabel()}
                    {message}
                </div>
            );
        },
        renderFooter: function() {
            var verification = !!this.props.verification,
                buttons = [<button key='stay' className='btn btn-return' onClick={this.close}>{$.t('dialog.dismiss_settings.stay_button')}</button>];
            if (!verification) buttons.push(<button key='leave' className='btn btn-danger proceed-btn' onClick={this.proceed}>{$.t('dialog.dismiss_settings.leave_button')}</button>);
            return buttons;
        }
    });

    dialogs.DeleteNodesDialog = React.createClass({
        mixins: [componentMixins.dialogMixin],
        getDefaultProps: function() {return {title: $.t('dialog.delete_nodes.title')};},
        renderBody: function() {
            return (<div className='deploy-task-notice'>{this.renderImportantLabel()} {$.t('dialog.delete_nodes.message')}</div>);
        },
        renderFooter: function() {
            return [
                <button key='cancel' className='btn' onClick={this.close}>{$.t('common.cancel_button')}</button>,
                <button key='delete' className='btn btn-danger btn-delete' onClick={this.deleteNodes} disabled={this.state.actionInProgress}>{$.t('common.delete_button')}</button>
            ];
        },
        deleteNodes: function() {
            var nodes = this.props.nodes;
            this.setState({actionInProgress: true});
            nodes.each(function(node) {
                if (!node.get('pending_deletion')) {
                    if (node.get('pending_addition')) {
                        node.set({
                            cluster_id: null,
                            pending_addition: false,
                            pending_roles: []
                        });
                    } else {
                        node.set({pending_deletion: true});
                    }
                }
            }, this);
            nodes.toJSON = function() {
                return this.map(function(node) {
                    return _.pick(node.attributes, 'id', 'cluster_id', 'pending_roles', 'pending_addition', 'pending_deletion');
                });
            };
            nodes.sync('update', nodes)
                .always(_.bind(this.close, this))
                .done(_.bind(function() {
                    var cluster = this.props.cluster;
                    cluster.fetch();
                    cluster.fetchRelated('nodes');
                    _.invoke(app.page.tab.screen.nodes.where({checked: true}), 'set', {checked: false});
                    app.page.tab.screen.updateBatchActionsButtons();
                    app.navbar.refresh();
                    app.page.removeFinishedNetworkTasks();
                }, this))
                .fail(function() {
                    utils.showErrorDialog({
                        title: $.t('cluster_page.nodes_tab.node_deletion_error.title'),
                        message: $.t('cluster_page.nodes_tab.node_deletion_error.node_deletion_warning')
                    });
                });
        }
    });

    dialogs.ChangePasswordDialog = React.createClass({
        mixins: [
            componentMixins.dialogMixin,
            React.addons.LinkedStateMixin
        ],
        getDefaultProps: function() {
            return {
                title: $.t('dialog.change_password.title'),
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
            if (name == 'currentPassword' && this.state.validationError) return $.t(ns + 'wrong_current_password');
            if (this.state.newPassword != this.state.confirmationPassword) {
                if (name == 'confirmationPassword') return $.t(ns + 'new_password_mismatch');
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
                            label={$.t(ns + translationKeys[index])}
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
                    {$.t('common.cancel_button')}
                </button>,
                <button key='apply' className='btn btn-success' onClick={this.changePassword}
                    disabled={this.state.actionInProgress || !this.isPasswordChangeAvailable()}>
                    {$.t('common.apply_button')}
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
                        $(this.refs.currentPassword.refs.input.getDOMNode()).focus();
                    }, this));
            }
        }
    });

    return dialogs;
});
