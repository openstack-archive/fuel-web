/*
 * Copyright 2013 Mirantis, Inc.
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
    'view_mixins',
    'jsx!component_mixins',
    'text!templates/dialogs/base_dialog.html',
    'text!templates/dialogs/reset_environment.html',
    'text!templates/dialogs/update_environment.html',
    'text!templates/dialogs/show_node.html',
    'text!templates/dialogs/dismiss_settings.html',
    'text!templates/dialogs/delete_nodes.html',
    'jsx!views/controls'
],
function(require, React, utils, models, viewMixins, componentMixins, baseDialogTemplate, resetEnvironmentDialogTemplate, updateEnvironmentDialogTemplate, showNodeInfoTemplate, discardSettingsChangesTemplate, deleteNodesTemplate, controls) {
    'use strict';

    var cx = React.addons.classSet;

    var views = {};

    views.Dialog = Backbone.View.extend({
        className: 'modal fade',
        template: _.template(baseDialogTemplate),
        modalBound: false,
        beforeTearDown: function() {
            this.unstickit();
            this.$el.modal('hide');
        },
        displayError: function(options) {
            var logsLink;
            var cluster = app.page.model;
            if (!options.hideLogsLink && cluster && cluster.constructor == models.Cluster) {
                var logOptions = {type: 'local', source: 'api', level: 'error'};
                logsLink = '#cluster/' + cluster.id + '/logs/' + utils.serializeTabOptions(logOptions);
            }
            var dialogOptions = _.defaults(options, {
                error: true,
                title: $.t('dialog.error_dialog.title'),
                message: $.t('dialog.error_dialog.warning'),
                logsLink: logsLink
            });
            this.$el.removeClass().addClass('modal').html(views.Dialog.prototype.template(dialogOptions)).i18n();
        },
        initialize: function(options) {
            _.defaults(this, options);
        },
        render: function(options) {
            this.$el.attr('tabindex', -1);
            if (options && options.error) {
                this.displayError(options);
            } else {
                var templateOptions = _.extend({title: '', message: '', error: false, logsLink: ''}, options);
                this.$el.html(this.template(templateOptions)).i18n();
            }
            if (!this.modalBound) {
                this.$el.on('hidden', _.bind(this.tearDown, this));
                this.$el.on('shown', _.bind(function() {
                    this.$('[autofocus]:first').focus();
                }, this));
                this.$el.modal(_.extend({}, this.modalOptions));
                this.modalBound = true;
            }
            return this;
        }
    });

    views.DiscardNodeChangesDialog = React.createClass({
        mixins: [componentMixins.dialogMixin],
        getDefaultProps: function() {
            return {title: $.t('dialog.discard_changes.title')};
        },
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
                .done(_.bind(function() {
                    $.when(cluster.fetch(), cluster.get('nodes').fetch({data: {cluster_id: cluster.id}}))
                        .always(_.bind(function() {
                            // we set node flags silently, so trigger resize event to redraw node list
                            cluster.get('nodes').trigger('resize');
                            app.navbar.refresh();
                            this.close();
                        }, this));
                }, this))
                .fail(_.bind(function() {
                    this.displayError();
                    this.setState({actionInProgress: false});
                }, this));
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

    views.DeployChangesDialog = React.createClass({
        mixins: [componentMixins.dialogMixin],
        getDefaultProps: function() {
            return {title: $.t('dialog.display_changes.title')};
        },
        getInitialState: function() {
            // FIXME: the following amount restrictions shoud be described declaratively in configuration file
            var nodes = this.props.cluster.get('nodes'),
                requiredNodeAmount = this.getRequiredNodeAmount();
            return {
                amountRestrictions: {
                    controller: nodes.nodesAfterDeploymentWithRole('controller') < requiredNodeAmount,
                    compute: !nodes.nodesAfterDeploymentWithRole('compute'),
                    mongo: this.props.cluster.get('settings').get('additional_components.ceilometer.value') && nodes.nodesAfterDeploymentWithRole('mongo') < requiredNodeAmount
                }
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
                .done(_.bind(function() {
                    app.page.deploymentTaskStarted();
                    this.close();
                }, this))
                .fail(_.bind(function() {
                    this.displayError();
                    this.setState({actionInProgress: false});
                }, this));
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
                requiredNodeAmount = this.getRequiredNodeAmount();
            return (
                <div className='display-changes-dialog'>
                    {(cluster.get('status') == 'new' || cluster.needsRedeployment()) &&
                        <div>
                            <div className='deploy-task-notice text-warning'>
                                <i className='icon-attention' />
                                <span>{$.t(ns + (cluster.get('status') == 'new' ? 'locked_settings_alert' : 'redeployment_needed'))}</span>
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
                    disabled={this.state.actionInProgress}
                    onClick={this.deployCluster}
                >{$.t('dialog.display_changes.deploy')}</button>
            ]);
        }
    });

    views.StopDeploymentDialog = React.createClass({
        mixins: [componentMixins.dialogMixin],
        getDefaultProps: function() {
            return {title: $.t('dialog.stop_deployment.title')};
        },
        stopDeployment: function() {
            this.setState({actionInProgress: true});
            var task = new models.Task();
            task.save({}, {url: _.result(this.props.cluster, 'url') + '/stop_deployment', type: 'PUT'})
                .done(_.bind(function() {
                    this.close();
                    app.page.deploymentTaskStarted();
                }, this))
                .fail(_.bind(function(response) {
                    this.displayError({
                        title: $.t('dialog.stop_deployment.stop_deployment_error.title'),
                        message: utils.getResponseText(response) || $.t('dialog.stop_deployment.stop_deployment_error.stop_deployment_warning')
                    });
                    this.setState({actionInProgress: false});
                }, this));
        },
        renderBody: function() {
            return (
                <div className='msg-error'>
                    <span className='label label-important'>{$.t('common.important')}</span>
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

    views.RemoveClusterDialog = React.createClass({
        mixins: [componentMixins.dialogMixin],
        getDefaultProps: function() {
            return {title: $.t('dialog.remove_cluster.title')};
        },
        removeCluster: function() {
            this.setState({actionInProgress: true});
            this.props.cluster.destroy({wait: true})
                .done(_.bind(function() {
                    this.close();
                    app.navbar.refresh();
                    app.navigate('#clusters', {trigger: true});
                }, this))
                .fail(_.bind(function() {
                    this.displayError();
                    this.setState({actionInProgress: false});
                }, this));
        },
        renderBody: function() {
            return (
                <div className='msg-error'>
                    <span className='label label-important'>{$.t('common.important')}</span>
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

    views.ResetEnvironmentDialog = views.Dialog.extend({
        template: _.template(resetEnvironmentDialogTemplate),
        events: {
            'click .reset-environment-btn:not(:disabled)': 'resetEnvironment'
        },
        resetEnvironment: function() {
            this.$('.reset-environment-btn').attr('disabled', true);
            app.page.removeFinishedDeploymentTasks();
            var task = new models.Task();
            task.save({}, {url: _.result(this.model, 'url') + '/reset', type: 'PUT'})
                .done(_.bind(function() {
                    this.$el.modal('hide');
                    app.page.deploymentTaskStarted();
                }, this))
                .fail(_.bind(this.displayError, this));
        }
    });

    views.UpdateEnvironmentDialog = views.Dialog.extend({
        template: _.template(updateEnvironmentDialogTemplate),
        events: {
            'click .update-environment-btn:not(:disabled)': 'updateEnvironment'
        },
        updateEnvironment: function() {
            this.$('.update-environment-btn').attr('disabled', true);
            var deferred = this.cluster.save({
                pending_release_id: this.pendingReleaseId || this.cluster.get('release_id')
            }, {patch: true, wait: true});
            if (deferred) {
                deferred.done(_.bind(function() {
                    app.page.removeFinishedDeploymentTasks();
                    var task = new models.Task();
                    task.save({}, {url: _.result(this.cluster, 'url') + '/update', type: 'PUT'})
                        .done(_.bind(function() {
                            this.$el.modal('hide');
                            app.page.deploymentTaskStarted();
                        }, this))
                        .fail(_.bind(this.displayError, this));
                }, this))
                .fail(_.bind(this.displayError, this));
            }
        },
        render: function() {
            this.constructor.__super__.render.call(this, {cluster: this.cluster, action: this.action, isDowngrade: this.isDowngrade});
            return this;
        }
    });

    views.ShowNodeInfoDialog = views.Dialog.extend({
        template: _.template(showNodeInfoTemplate),
        templateHelpers: {
            showPropertyName: function(propertyName) {
                return propertyName.replace(/_/g, ' ');
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
                return (_.isUndefined(value) || _.isNull(value) || !$.trim(value.toString()).length) ? '\u00A0' : value;
            },
            showSummary: function(meta, group) {
                var summary = '';
                try {
                    if (group == 'system') {
                        summary = (meta.system.manufacturer || '') + ' ' + (meta.system.product || '');
                    } else if (group == 'memory') {
                        if (_.isArray(meta.memory.devices) && meta.memory.devices.length) {
                            var sizes = _.groupBy(_.pluck(meta.memory.devices, 'size'), utils.showMemorySize);
                            summary = _.map(_.keys(sizes).sort(), function(size) {return sizes[size].length + ' x ' + size;}).join(', ');
                            summary += ', ' + utils.showMemorySize(meta.memory.total) + ' ' + $.t('dialog.show_node.total');
                        } else {
                            summary = utils.showMemorySize(meta.memory.total) + ' ' + $.t('dialog.show_node.total');
                        }
                    } else if (group == 'disks') {
                        summary = meta.disks.length + ' ';
                        summary += $.t('dialog.show_node.drive', {count: meta.disks.length});
                        summary += ', ' + utils.showDiskSize(_.reduce(_.pluck(meta.disks, 'size'), function(sum, n) {return sum + n;}, 0)) + ' ' + $.t('dialog.show_node.total');
                    } else if (group == 'cpu') {
                        var frequencies = _.groupBy(_.pluck(meta.cpu.spec, 'frequency'), utils.showFrequency);
                        summary = _.map(_.keys(frequencies).sort(), function(frequency) {return frequencies[frequency].length + ' x ' + frequency;}).join(', ');
                    } else if (group == 'interfaces') {
                        var bandwidths = _.groupBy(_.pluck(meta.interfaces, 'current_speed'), utils.showBandwidth);
                        summary = _.map(_.keys(bandwidths).sort(), function(bandwidth) {return bandwidths[bandwidth].length + ' x ' + bandwidth;}).join(', ');
                    }
                } catch (ignore) {}
                return summary;
            },
            sortEntryProperties: utils.sortEntryProperties
        },
        events: {
            'click .accordion-heading': 'toggle',
            'click .btn-edit-disks': 'goToDisksConfiguration',
            'click .btn-edit-networks': 'goToInterfacesConfiguration',
            'click .btn-node-console': 'goToSSHConsole'
        },
        toggle: function(e) {
            $(e.currentTarget).siblings('.accordion-body').collapse('toggle');
        },
        goToDisksConfiguration: function() {
            app.navigate('#cluster/' + this.node.get('cluster') + '/nodes/disks/' + utils.serializeTabOptions({nodes: this.node.id}), {trigger: true});
        },
        goToInterfacesConfiguration: function() {
            app.navigate('#cluster/' + this.node.get('cluster') + '/nodes/interfaces/' + utils.serializeTabOptions({nodes: this.node.id}), {trigger: true});
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.node.on('sync', this.render, this);
        },
        goToSSHConsole: function() {
            window.open('http://' + window.location.hostname + ':2443/?' + $.param({
                ssh: 'ssh://root@' + this.node.get('ip'),
                location: this.node.get('ip').replace(/\./g, '')
            }), '_blank');
        },
        render: function() {
            this.constructor.__super__.render.call(this, _.extend({node: this.node}, this.templateHelpers));
            this.$('.accordion-body').collapse({
                parent: this.$('.accordion'),
                toggle: false
            }).on('show', function(e) {
                $(e.currentTarget).siblings('.accordion-heading').find('i').removeClass('icon-expand').addClass('icon-collapse');
            }).on('hide', function(e) {
                $(e.currentTarget).siblings('.accordion-heading').find('i').removeClass('icon-collapse').addClass('icon-expand');
            }).on('hidden', function(e) {
                e.stopPropagation();
            });
            return this;
        }
    });

    views.DiscardSettingsChangesDialog = views.Dialog.extend({
        template: _.template(discardSettingsChangesTemplate),
        events: {
            'click .proceed-btn': 'proceed'
        },
        proceed: function() {
            this.$el.modal('hide');
            app.page.removeFinishedNetworkTasks().always(_.bind(this.cb, this));
        },
        render: function() {
            if (this.verification) {
                this.message = $.t('dialog.dismiss_settings.verify_message');
            }
            this.constructor.__super__.render.call(this, {
                message: this.message || $.t('dialog.dismiss_settings.default_message'),
                verification: this.verification || false
            });
            return this;
        }
    });

    views.DeleteNodesDialog = views.Dialog.extend({
        template: _.template(deleteNodesTemplate),
        events: {
            'click .btn-delete': 'deleteNodes'
        },
        deleteNodes: function() {
            if (this.nodes.cluster) {
                this.$('.btn-delete').prop('disabled', true);
                this.nodes.each(function(node) {
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
                this.nodes.toJSON = function(options) {
                    return this.map(function(node) {
                        return _.pick(node.attributes, 'id', 'cluster_id', 'pending_roles', 'pending_addition', 'pending_deletion');
                    });
                };
                this.nodes.sync('update', this.nodes)
                    .done(_.bind(function() {
                        this.$el.modal('hide');
                        app.page.tab.model.fetch();
                        app.page.tab.screen.nodes.fetch();
                        _.invoke(app.page.tab.screen.nodes.where({checked: true}), 'set', {checked: false});
                        app.page.tab.screen.updateBatchActionsButtons();
                        app.navbar.refresh();
                        app.page.removeFinishedNetworkTasks();
                    }, this))
                    .fail(_.bind(function() {
                        utils.showErrorDialog({
                            title: $.t('cluster_page.nodes_tab.node_deletion_error.title'),
                            message: $.t('cluster_page.nodes_tab.node_deletion_error.node_deletion_warning')
                        });
                    }, this));
            }
        },
        render: function() {
            this.constructor.__super__.render.call(this, {nodes: this.nodes});
            return this;
        }
    });

    views.ChangePasswordDialog = React.createClass({
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

    return views;
});
