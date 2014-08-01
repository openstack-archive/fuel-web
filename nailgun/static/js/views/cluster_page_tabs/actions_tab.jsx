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
    'react',
    'utils',
    'models',
    'views/dialogs'
],
function(React, utils, models, dialogViews) {
    'use strict';

    var releases = new models.Releases();
    var ActionsTab = React.createClass({
        mixins: [
            React.BackboneMixin('model'),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.model.get('tasks');
            }}),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.model.task({group: 'deployment', status: 'running'});
            }})
        ],
        render: function() {
            var cluster = this.props.model;
            var task = cluster.task({group: 'deployment', status: 'running'});
            return (
                <div className='wrapper'>
                    <h3 className='span12'>{$.t('cluster_page.actions_tab.title')}</h3>
                    <div className='row-fluid environment-actions'>
                        <RenameEnvironmentAction cluster={cluster}/>
                        <ResetEnvironmentAction cluster={cluster} task={task} />
                        <DeleteEnvironmentAction cluster={cluster}/>
                        <UpdateEnvironmentAction cluster={cluster} releases={releases} task={task}/>
                    </div>
                </div>
            );
        }
    });

    var Action = React.createClass({
        getDefaultProps: function() {
            return {className: 'span4'};
        },
        render: function() {
            return (
                <div className={'action-item-placeholder ' + this.props.className}>
                    <form className='environment-action-form' onsubmit='return false'>
                      <h4>{this.props.title}</h4>
                      <div className='action-item-controls'>
                        {this.props.children}
                      </div>
                    </form>
                </div>
            );
        }
    });

    var RenameEnvironmentAction = React.createClass({
        applyAction: function(e) {
            e.preventDefault();
            var cluster = this.props.cluster;
            var name = this.state.name;
            if (name != cluster.get('name')) {
                var deferred = cluster.save({name: name}, {patch: true, wait: true});
                if (deferred) {
                    this.setState({disabled: true});
                    deferred
                        .fail(_.bind(function(response) {
                            if (response.status == 409) {
                                this.setState({error: response.responseText});
                            } else {
                                utils.showErrorDialog({title: $.t('cluster_page.actions_tab.rename_error.title')});
                            }
                        }, this))
                        .done(function(){
                            app.breadcrumbs.setPath(_.result(app.page, 'breadcrumbsPath'));
                        })
                        .always(_.bind(function() {
                            this.setState({disabled: false});
                        }, this));
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
                <Action title={$.t('cluster_page.actions_tab.rename_environment')}>
                    <div className='action-body'>
                        <input type='text'
                            disabled={this.state.disabled}
                            className={this.state.error && 'error'}
                            maxLength='50'
                            valueLink={valueLink}/>
                        {this.state.error &&
                            <div className='text-error'>
                                {this.state.error}
                            </div>
                        }
                    </div>
                    <button
                        className='btn btn-success rename-environment-btn'
                        onClick={this.applyAction} disabled={this.state.disabled}>
                        {$.t('common.rename_button')}
                    </button>
                </Action>
            );
        }
    });

    var ResetEnvironmentAction = React.createClass({
        mixins: [
            React.BackboneMixin('cluster'),
            React.BackboneMixin('task')
        ],
        isLocked: function() {
            return this.props.cluster.get('status') == 'new' || !!this.props.cluster.tasks({group: 'deployment', status: 'running'}).length;
        },
        getInitialState: function() {
            return {disabled: this.isLocked()}
        },
        componentWillReceiveProps: function() {
            this.setState({disabled: this.isLocked()});
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
        applyAction:function(e) {
            e.preventDefault();
            (new dialogViews.ResetEnvironmentDialog({model: this.props.cluster})).render();
        },
        render: function() {
            return (
                <Action title={$.t('cluster_page.actions_tab.reset_environment')}>
                    <div className='action-body'>
                        <div className='action-item-description'>
                            {$.t('cluster_page.actions_tab.' + this.getDescriptionKey())}
                        </div>
                        {!this.state.disabled && <div className='important action-item-description'>{$.t('cluster_page.actions_tab.reset_environment_warning')}</div>}
                    </div>
                    <button
                        className='btn btn-danger reset-environment-btn'
                        onClick={this.applyAction}
                        disabled={this.state.disabled}>
                        {$.t('common.reset_button')}
                    </button>
                </Action>
            );
        }
    });

    var DeleteEnvironmentAction = React.createClass({
        applyAction: function(e) {
            e.preventDefault();
            (new dialogViews.RemoveClusterDialog({model: this.props.cluster})).render();
        },
        render: function() {
            return (
                <Action title={$.t('cluster_page.actions_tab.delete_environment')}>
                    <div className='action-body'>
                        <div className='action-item-description important'>
                            {$.t('cluster_page.actions_tab.alert_delete')}
                        </div>
                    </div>
                    <button
                        className='btn btn-danger delete-environment-btn'
                        onClick={this.applyAction}>
                        {$.t('common.delete_button')}
                    </button>
                </Action>
            );
        }
    });

    var UpdateEnvironmentAction = React.createClass({
        mixins: [
            React.addons.LinkedStateMixin,
            React.BackboneMixin('cluster'),
            React.BackboneMixin('releases'),
            React.BackboneMixin('task')
        ],
        getInitialState: function() {
            return {
                action: this.getAction(),
                releases: [],
                pendingReleaseId: '',
                disabled: this.isLocked()
            };
        },
        getAction: function() {
            return this.props.cluster.get('status') == 'update_error' ? 'rollback' : 'update';
        },
        isLocked: function() {
            return !_.contains(['operational', 'update_error'], this.props.cluster.get('status'))
                || !!this.props.cluster.tasks({group: 'deployment', status: 'running'}).length;
        },
        componentWillReceiveProps: function() {
            this.setState({
                disabled: this.isLocked(),
                action: this.getAction(),
                pendingReleaseId: this.getPendingReleaseId()
            });
        },
        componentDidMount: function() {
            var releases = this.props.releases;
            if (!releases.length) {
                releases.fetch().done(_.bind(function() {
                    this.setState({pendingReleaseId: this.getPendingReleaseId()});
                }, this));
            }
        },
        applyAction: function() {
            var cluster = this.props.cluster;
            var isDowngrade = _.contains(cluster.get('release').get('can_update_from_versions'), this.props.releases.findWhere({id: cluster.get('pending_release_id') || cluster.get('release_id')}).get('version'));
            (new dialogViews.UpdateEnvironmentDialog({
                model: cluster,
                action: this.state.action,
                isDowngrade: isDowngrade,
                pendingReleaseId: this.state.pendingReleaseId
            })).render();
        },
        getPendingReleaseId: function() {
            var release = _.find(releases.models, this.isAvailableForUpdate, this);
            if (release) {
                return release.id;
            }
            return '';
        },
        isAvailableForUpdate: function(release) {
            var cluster = this.props.cluster;
            var currentRelease = cluster.get('release');
            return (_.contains(currentRelease.get('can_update_from_versions'), release.get('version')) || _.contains(release.get('can_update_from_versions'), currentRelease.get('version')))
                && release.get('operating_system') == currentRelease.get('operating_system')
                && release.get('id') != cluster.get('release_id');
        },
        getDescriptionKey: function() {
            var cluster = this.props.cluster;
            var action = this.state.action;
            var task = cluster.task({group: 'deployment', status: 'running'});
            if (action == 'update' && cluster.get('status') == 'operational' && this.props.releases.length == 0) {return 'no_releases_to_update_message';}
            if (action == 'rollback') {return 'rollback_message';}
            if (task) {
                if (_.contains(task.get('name'), action)) { return 'repeated_' + action + '_disabled'; }
                return action + '_disabled_for_deploying_cluster';
            }
            if ((action == 'reset' && cluster.get('status') == 'new') || (action == 'update' && cluster.get('status') != 'operational')) {
                return action + '_disabled_for_new_cluster';
            }
            return action + '_environment_description';
        },
        render: function() {
            var releases = this.props.releases.filter(this.isAvailableForUpdate, this);
            var options = releases.map(function(release, i){
                return <option value={release.id} key={release.id}>{release.get('name') + ' (' + release.get('version') + ')'}</option>;
            }, this);
            return (
                <Action className='span12 action-update' title={$.t('cluster_page.actions_tab.update_environment')}>
                    <div className='action-body'>
                        <div className='action-item-description'>
                            {$.t('cluster_page.actions_tab.' + this.getDescriptionKey())}
                        </div>
                        {(this.state.action == 'update' && !this.state.disabled && this.state.pendingReleaseId) &&
                            <select valueLink={this.linkState('pendingReleaseId')}>
                                {options}
                            </select>
                        }
                    </div>
                    <button
                        className='btn btn-danger update-environment-btn'
                        onClick={this.applyAction}
                        disabled={(this.state.action == 'update' && !this.state.pendingReleaseId) || this.state.disabled}>
                            {$.t('common.' + this.state.action + '_button')}
                    </button>
                </Action>
            );
        }
    });

    return ActionsTab;
});
