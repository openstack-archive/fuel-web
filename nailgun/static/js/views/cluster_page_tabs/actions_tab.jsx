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
    'react',
    'component_mixins',
    'utils',
    'models',
    'views/dialogs'
],
function(React, componentMixins, utils, models, dialogViews) {
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
            var task = this.props.model.task({group: 'deployment', status: 'running'});
            return (
                <div className="wrapper">
                    <h3 className="span12">{$.t('cluster_page.actions_tab.title')}</h3>
                    <div className="row-fluid environment-actions">
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
                    <form className="environment-action-form" onsubmit="return false">
                      <h4>{this.props.title}</h4>
                      <div className="action-item-controls">
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
                                this.showValidationError(name, response.responseText);
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
        showValidationError: function(name, error) {
            this.setState({
                error: error
            })
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
                    <div className="action-body">
                        <input type="text"
                            disabled={this.state.disabled}
                            className={this.state.error ? 'error' : ''}
                            maxLength="50"
                            valueLink={valueLink}/>
                        <div className={'text-error ' + this.state.error ? '' : 'hide'}>{this.state.error}</div>
                    </div>
                    <button key="rename" className="btn btn-success rename-environment-btn" onClick={this.applyAction} disabled={this.state.disabled}><span>{$.t('common.rename_button')}</span></button>
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
            (new dialogViews.ResetEnvironmentDialog({model: this.props.cluster, action: 'reset'})).render();
        },
        render: function() {
            return (
                <Action title={$.t('cluster_page.actions_tab.reset_environment')}>
                    <div className="action-body">
                        <div className="action-item-description">
                            {$.t('cluster_page.actions_tab.' + this.getDescriptionKey())}
                        </div>
                        <div className={"important " + (this.state.disabled ? "hide" : "action-item-description") }>{$.t('cluster_page.actions_tab.reset_environment_warning')}</div>
                    </div>
                    <button key="reset" className="btn btn-danger reset-environment-btn" onClick={this.applyAction} disabled={this.state.disabled}>{$.t('common.reset_button')}</button>
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
                    <div className="action-body">
                        <div className="action-item-description important">{$.t('cluster_page.actions_tab.alert_delete')}</div>
                    </div>
                    <button key="delete" className="btn btn-danger delete-environment-btn" onClick={this.applyAction}><span>{$.t('common.delete_button')}</span></button>
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
                action: this.props.cluster.get('status') == 'update_error' ? 'rollback' : 'update',
                releasesFiltered: [],
                pendingReleaseId: '',
                disabled: this.isLocked()
            }
        },
        isLocked: function() {
            return !_.contains(['operational', 'update_error'], this.props.cluster.get('status')) || !!this.props.cluster.tasks({group: 'deployment', status: 'running'}).length;
        },
        componentWillReceiveProps: function() {
            this.setState({
                disabled: this.isLocked(),
                action: this.props.cluster.get('status') == 'update_error' ? 'rollback' : 'update'
            });
            this.getReleasesForUpdate();
        },
        componentDidMount: function() {
            if (!this.props.releases.length) {
                this.props.releases.fetch().done(_.bind(function() {
                    this.getReleasesForUpdate();
                }, this));
            } else {
                this.getReleasesForUpdate();
            }
        },
        applyAction: function() {
            var isDowngrade = _.contains(this.props.cluster.get('release').get('can_update_from_versions'), this.props.releases.findWhere({id: this.props.cluster.get('pending_release_id') || this.props.cluster.get('release_id')}).get('version'));
            (new dialogViews.UpdateEnvironmentDialog({model: this.props.cluster, action: this.state.action, isDowngrade: isDowngrade, pendingReleaseId: this.state.pendingReleaseId || this.state.releasesFiltered[0].id})).render();
        },
        getReleasesForUpdate: function() {
            var releaseId = this.props.cluster.get('release_id');
            var currentRelease = this.props.cluster.get('release');
            var operatingSystem = currentRelease.get('operating_system');
            var version = currentRelease.get('version');
            var releasesForDowngrade = currentRelease.get('can_update_from_versions');
            var releasesList = this.props.releases;
            this.setState({
                releasesFiltered: releasesList.filter(function(release) {
                    return (_.contains(releasesForDowngrade, release.get('version')) || _.contains(release.get('can_update_from_versions'), version)) && release.get('operating_system') == operatingSystem && release.get('id') != releaseId;
                })
            });
        },
        getDescriptionKey: function() {
            var releasesForUpdate = this.props.releases;
            var action = this.state.action;
            var task = this.props.cluster.task({group: 'deployment', status: 'running'});
            if (action == 'update' && this.props.cluster.get('status') == 'operational' && releasesForUpdate.length == 0) {return 'no_releases_to_update_message';}
            if (action == 'rollback') {return 'rollback_message';}
            if (task) {
                if (_.contains(task.get('name'), action)) { return 'repeated_' + action + '_disabled'; }
                return action + '_disabled_for_deploying_cluster';
            }
            if ((action == 'reset' && this.props.cluster.get('status') == 'new') || (action == 'update' && this.props.cluster.get('status') != 'operational')) {
                return action + '_disabled_for_new_cluster';
            }
            return action + '_environment_description';
        },
        render: function() {
            var valueLink = this.linkState('pendingReleaseId');
            var handleChange = function(e) {
                valueLink.requestChange(e.target.value);
            };
            var options = this.state.releasesFiltered.map(function(release, i){
                return <option value={release.id} key={release.id}>{release.get('name') + ' (' + release.get('version') + ')'}</option>;
            }, this);
            return (
                <Action className='span12 action-update' title={$.t('cluster_page.actions_tab.update_environment')}>
                    <div className="action-body">
                        <div className="action-item-description">
                            {$.t('cluster_page.actions_tab.' + this.getDescriptionKey())}
                        </div>
                        {(this.state.action == 'update' && !this.state.disabled && this.state.releasesFiltered.length) &&
                            <select onChange={handleChange}>
                                {options}
                            </select>
                        }
                    </div>
                    <button key="update" className="btn btn-danger update-environment-btn" onClick={this.applyAction} disabled={(this.state.action == 'update' && this.state.releasesFiltered.length == 0) || this.state.disabled}><span>{$.t('common.' + this.state.action + '_button')}</span></button>
                </Action>
            );
        }
    });

    return ActionsTab;
});
