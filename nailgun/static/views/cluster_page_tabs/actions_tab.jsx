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
    'react',
    'utils',
    'models',
    'dispatcher',
    'jsx!views/dialogs',
    'jsx!component_mixins'
],
function($, _, i18n, React, utils, models, dispatcher, dialogs, componentMixins) {
    'use strict';

    var ActionsTab = React.createClass({
        mixins: [
            componentMixins.backboneMixin('cluster'),
            componentMixins.backboneMixin({modelOrCollection: function(props) {
                return props.cluster.get('tasks');
            }}),
            componentMixins.backboneMixin({modelOrCollection: function(props) {
                return props.cluster.task({group: 'deployment', status: 'running'});
            }})
        ],
        statics: {
            fetchData: function() {
                if (_.contains(app.version.get('feature_groups'), 'experimental')) {
                    var releases = new models.Releases();
                    return releases.fetch().then(function() {
                        return {releases: releases};
                    });
                }
                return $.Deferred().resolve();
            }
        },
        render: function() {
            var cluster = this.props.cluster,
                task = cluster.task({group: 'deployment', status: 'running'});
            return (
                <div className='row content-elements'>
                    <div className='title'>{i18n('cluster_page.actions_tab.title')}</div>
                    <RenameEnvironmentAction cluster={cluster}/>
                    <ResetEnvironmentAction cluster={cluster} task={task} />
                    <DeleteEnvironmentAction cluster={cluster}/>
                    {_.contains(app.version.get('feature_groups'), 'experimental') &&
                        <UpdateEnvironmentAction cluster={cluster} releases={this.props.releases} task={task}/>
                    }
                </div>
            );
        }
    });

    var Action = React.createClass({
        getDefaultProps: function() {
            return {className: 'col-xs-12 col-md-4'};
        },
        render: function() {
            return (
                <div className={'action-item ' + this.props.className}>
                    <div className='panel panel-default'>
                        <div className='panel-heading font-bold'>{this.props.title}</div>
                        <div className='panel-body'>
                            {this.props.children}
                        </div>
                    </div>
                </div>
            );
        }
    });

    var RenameEnvironmentAction = React.createClass({
        applyAction: function(e) {
            e.preventDefault();
            var cluster = this.props.cluster,
                name = this.state.name;
            if (name != cluster.get('name')) {
                var deferred = cluster.save({name: name}, {patch: true, wait: true});
                if (deferred) {
                    this.setState({disabled: true});
                    deferred
                        .fail(_.bind(function(response) {
                            if (response.status == 409) {
                                this.setState({error: utils.getResponseText(response)});
                            } else {
                                utils.showErrorDialog({
                                    title: i18n('cluster_page.actions_tab.rename_error.title'),
                                    response: response
                                });
                            }
                        }, this))
                        .done(function() {
                            dispatcher.trigger('updatePageLayout');
                        })
                        .always(_.bind(function() {
                            this.setState({disabled: false});
                        }, this));
                } else {
                    if (cluster.validationError) {
                        this.setState({error: cluster.validationError.name});
                    }
                }
            }
        },
        getInitialState: function() {
            return {
                name: this.props.cluster.get('name'),
                disabled: false,
                error: ''
            };
        },
        handleChange: function(newValue) {
            this.setState({
                name: newValue,
                error: ''
            });
        },
        render: function() {
            var valueLink = {
                value: this.state.name,
                requestChange: this.handleChange
            };
            return (
                <Action title={i18n('cluster_page.actions_tab.rename_environment')}>
                    <div className='action-body'>
                        <input type='text'
                            disabled={this.state.disabled}
                            className={utils.classNames({'form-control': true, error: this.state.error})}
                            maxLength='50'
                            valueLink={valueLink}/>
                        {this.state.error &&
                            <div className='text-danger'>
                                {this.state.error}
                            </div>
                        }
                    </div>
                    <button
                        className='btn btn-success rename-environment-btn'
                        onClick={this.applyAction}
                        disabled={this.state.disabled}>
                        {i18n('common.rename_button')}
                    </button>
                </Action>
            );
        }
    });

    var ResetEnvironmentAction = React.createClass({
        mixins: [
            componentMixins.backboneMixin('cluster'),
            componentMixins.backboneMixin('task')
        ],
        isLocked: function() {
            return this.props.cluster.get('status') == 'new' || !!this.props.task;
        },
        getDescriptionKey: function() {
            var task = this.props.task;
            if (task) {
                if (_.contains(task.get('name'), 'reset')) {return 'repeated_reset_disabled';}
                return 'reset_disabled_for_deploying_cluster';
            }
            if (this.props.cluster.get('status') == 'new') {return 'reset_disabled_for_new_cluster';}
            return 'reset_environment_description';
        },
        applyAction: function(e) {
            e.preventDefault();
            dialogs.ResetEnvironmentDialog.show({cluster: this.props.cluster});
        },
        render: function() {
            var isLocked = this.isLocked();
            return (
                <Action title={i18n('cluster_page.actions_tab.reset_environment')}>
                    <div className='action-body'>
                        <div className='action-item-description'>
                            {i18n('cluster_page.actions_tab.' + this.getDescriptionKey())}
                        </div>
                        {!isLocked && <div className='text-danger action-item-description'>{i18n('cluster_page.actions_tab.reset_environment_warning')}</div>}
                    </div>
                    <button
                        className='btn btn-danger reset-environment-btn'
                        onClick={this.applyAction}
                        disabled={isLocked}>
                        {i18n('common.reset_button')}
                    </button>
                </Action>
            );
        }
    });

    var DeleteEnvironmentAction = React.createClass({
        applyAction: function(e) {
            e.preventDefault();
            dialogs.RemoveClusterDialog.show({cluster: this.props.cluster});
        },
        render: function() {
            return (
                <Action title={i18n('cluster_page.actions_tab.delete_environment')}>
                    <div className='action-body'>
                        <div className='action-item-description text-danger'>
                            {i18n('cluster_page.actions_tab.alert_delete')}
                        </div>
                    </div>
                    <button
                        className='btn btn-danger delete-environment-btn'
                        onClick={this.applyAction}>
                        {i18n('common.delete_button')}
                    </button>
                </Action>
            );
        }
    });

    var UpdateEnvironmentAction = React.createClass({
        mixins: [
            React.addons.LinkedStateMixin,
            componentMixins.backboneMixin('cluster'),
            componentMixins.backboneMixin('releases'),
            componentMixins.backboneMixin('task')
        ],
        getInitialState: function() {
            return {pendingReleaseId: this.getPendingReleaseId()};
        },
        getAction: function() {
            return this.props.cluster.get('status') == 'update_error' ? 'rollback' : 'update';
        },
        isLocked: function() {
            return !_.contains(['operational', 'update_error'], this.props.cluster.get('status')) || !!this.props.task;
        },
        componentWillReceiveProps: function() {
            this.setState({pendingReleaseId: this.getPendingReleaseId()});
        },
        updateEnvironmentAction: function() {
            var cluster = this.props.cluster,
                isDowngrade = _.contains(cluster.get('release').get('can_update_from_versions'), this.props.releases.findWhere({id: parseInt(this.state.pendingReleaseId) || cluster.get('release_id')}).get('version'));
            dialogs.UpdateEnvironmentDialog.show({
                cluster: cluster,
                action: this.getAction(),
                isDowngrade: isDowngrade,
                pendingReleaseId: this.state.pendingReleaseId
            });
        },
        retryUpdateEnvironmentAction: function() {
            var cluster = this.props.cluster;
            dialogs.UpdateEnvironmentDialog.show({cluster: cluster, pendingReleaseId: cluster.get('pending_release_id'), action: 'retry'});
        },
        rollbackEnvironmentAction: function() {
            dialogs.UpdateEnvironmentDialog.show({cluster: this.props.cluster, action: 'rollback'});
        },
        getPendingReleaseId: function() {
            return (this.props.releases.find(this.isAvailableForUpdate, this) || {}).id;
        },
        isAvailableForUpdate: function(release) {
            var cluster = this.props.cluster,
                currentRelease = cluster.get('release');
            return (_.contains(currentRelease.get('can_update_from_versions'), release.get('version')) || _.contains(release.get('can_update_from_versions'), currentRelease.get('version'))) &&
                release.get('operating_system') == currentRelease.get('operating_system') &&
                release.id != cluster.get('release_id');
        },
        getDescriptionKey: function() {
            var cluster = this.props.cluster,
                action = this.getAction(),
                task = this.props.task,
                status = cluster.get('status');
            if (action == 'update' && status == 'operational' && !this.state.pendingReleaseId) return 'no_releases_to_update_message';
            if (action == 'rollback') return 'rollback_warning_message';
            if (task && _.contains(task.get('name'), action)) return 'repeated_' + action + '_disabled';
            if (task) return action + '_disabled_for_deploying_cluster';
            if ((action == 'reset' && status == 'new') || (action == 'update' && status != 'operational')) return action + '_disabled_for_new_cluster';
            return action + '_environment_description';
        },
        render: function() {
            var releases = this.props.releases.filter(this.isAvailableForUpdate, this),
                pendingRelease = this.props.releases.get(this.state.pendingReleaseId),
                action = this.getAction(),
                isLocked = this.isLocked(),
                options = releases.map(function(release) {
                    return <option value={release.id} key={release.id}>{release.get('name') + ' (' + release.get('version') + ')'}</option>;
                }, this);
            return (
                <Action className='col-xs-12 col-md-12 action-update' title={i18n('cluster_page.actions_tab.update_environment')}>
                    <div className='action-body'>
                        {(action == 'rollback' || releases) &&
                            <div className='action-item-description'>
                                {i18n('cluster_page.actions_tab.' + this.getDescriptionKey(), {release: pendingRelease ? pendingRelease.get('name') + ' (' + pendingRelease.get('version') + ')' : ''})}
                            </div>
                        }
                        {action == 'rollback' &&
                            <div className='action-item-description'>
                                {i18n('cluster_page.actions_tab.rollback_message')}
                            </div>
                        }
                        {action == 'update' && !isLocked && this.state.pendingReleaseId &&
                            <select className='form-control' valueLink={this.linkState('pendingReleaseId')}>
                                {options}
                            </select>
                        }
                    </div>
                    {action == 'update' &&
                        <div>
                            <button
                                className='btn btn-success update-environment-btn'
                                onClick={this.updateEnvironmentAction}
                                disabled={_.isUndefined(this.state.pendingReleaseId) || isLocked}>
                                {i18n('common.update_button')}
                            </button>
                        </div>
                    }
                    {action == 'rollback' &&
                        <div>
                            <button
                                className='btn btn-success retry-update-environment-btn'
                                onClick={this.retryUpdateEnvironmentAction}>
                                {i18n('common.retry_button')}
                            </button>
                            <button
                                className='btn btn-danger rollback-environment-btn'
                                onClick={this.rollbackEnvironmentAction}>
                                {i18n('common.rollback_button')}
                            </button>
                        </div>
                    }
                </Action>
            );
        }
    });

    return ActionsTab;
});
