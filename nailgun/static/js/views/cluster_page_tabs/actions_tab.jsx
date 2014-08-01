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
    'views/common',
    'views/dialogs'
],
function(React, componentMixins, utils, models, commonViews, dialogViews) {
    'use strict';

    var ActionsTab = React.createClass({
        mixins: [
            React.BackboneMixin('model')
        ],
        render: function() {
            return (
                <div className="wrapper">
                    <h3 className="span12">{$.t('cluster_page.actions_tab.title')}</h3>
                    <div className="row-fluid environment-actions">
                        <RenameEnvironmentAction cluster={this.props.model}/>
                        <ResetEnvironmentAction cluster={this.props.model}/>
                        <DeleteEnvironmentAction cluster={this.props.model}/>
                        <UpdateEnvironmentAction cluster={this.props.model}/>
                    </div>
                </div>
            );
        }
    });

    var Action = React.createClass({
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
            var name = this.state.text;
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
                        .always(_.bind(function() {
                            this.setState({disabled: false});
                        }, this));
                }
            }
        },
        getInitialState: function() {
            return {
                text: this.props.cluster.get('name'),
                disabled: false,
                message_error: '',
                className: {
                    input: '',
                    message: 'text-error hide',
                }
            };
        },
        showValidationError: function(name, error) {
            this.setState({
                text: name,
                message_error: error,
                className: {
                    input: 'error',
                    message: 'text-error '
                }
            })
            console.log('test', this.state.message_error_text);
        },
        onClusterNameInputKeydown: function(e) {
            this.setState({
                text: e.target.value,
                className: {
                    input: '',
                    message: 'text-error hide'
                }
            });
        },
        render: function() {
            return (
                <Action className='span4' title={$.t('cluster_page.actions_tab.rename_environment')}>
                    <div className="action-body">
                        <input type="text" disabled={this.state.disabled} className={this.state.className.input} name="cluster_name" maxLength="50" onChange={this.onClusterNameInputKeydown} value={this.state.text} />
                        <div className={this.state.className.message}>{this.state.message_error}</div>
                    </div>
                    <button className="btn btn-success action-btn rename-environment-btn" onClick={this.applyAction} disabled={this.state.disabled}><span>{$.t('common.rename_button')}</span></button>
                </Action>
            );
        }
    });


    var ResetEnvironmentAction = React.createClass({
        mixins: [
            React.BackboneMixin('cluster'),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.cluster.get('tasks');
            }}),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.cluster.task({group: 'deployment', status: 'running'});
            }}),
            componentMixins.pollingMixin(2)
        ],
        shouldDataBeFetched: function() {
            return this.props.cluster.task('cluster_deletion', ['running', 'ready']) || this.props.cluster.task({group: 'deployment', status: 'running'});
        },
        fetchData: function() {
            var request, requests = [];
            var deletionTask = this.props.cluster.task('cluster_deletion');
            if (deletionTask) {
                request = deletionTask.fetch();
                request.fail(_.bind(function(response) {
                    if (response.status == 404) {
                        this.props.cluster.collection.remove(this.props.cluster);
                        app.navbar.refresh();
                    }
                }, this));
                requests.push(request);
            }
            var deploymentTask = this.props.cluster.task({group: 'deployment', status: 'running'});
            if (deploymentTask) {
                request = deploymentTask.fetch();
                request.done(_.bind(function() {
                    if (deploymentTask.get('status') != 'running') {
                        this.props.cluster.fetch();
                        app.navbar.refresh();
                    }
                }, this));
                requests.push(request);
            }
            return $.when.apply($, requests);
        },
        componentDidMount: function() {
            this.startPolling();
            this.props.cluster.on('change:status', this.actualizeState, this);
            this.props.cluster.get('tasks').bindToView(this, [{group: 'deployment'}], function(task) {
                task.on('change:status', this.actualizeState, this);
            });
        },
        actualizeState:function() {
            this.setState({disabled: this.isLocked});
            console.log('tasks', this.props.cluster.tasks({group: 'deployment', status: 'running'}).length)
        },
        isLocked: function() {
            return this.props.cluster.get('status') == 'new' || !!this.props.cluster.tasks({group: 'deployment', status: 'running'}).length;
        },
        getInitialState: function() {
            return {
                disabled: this.isLocked()
            }
        },
        getDescriptionKey: function() {
            var task = this.props.cluster.task({group: 'deployment', status: 'running'});
            if (task) {
                if (_.contains(task.get('name'), 'reset')) { return 'repeated_reset_disabled'; }
                return 'reset_disabled_for_deploying_cluster';
            }
            if (this.props.cluster.get('status') == 'new') {
                return 'reset_disabled_for_new_cluster';
            }
            return 'reset_environment_description';
        },
        applyAction:function(e) {
            e.preventDefault();
            (new dialogViews.ResetEnvironmentDialog({model: this.props.cluster, action: 'reset'})).render();
        },
        render: function() {
            return (
                <Action className='span4' title={$.t('cluster_page.actions_tab.reset_environment')}>
                    <div className="action-body">
                        <div className="action-item-description">
                            {$.t('cluster_page.actions_tab.' + this.getDescriptionKey())}
                        </div>
                        <div className={"action-item-description important " + (!this.state.disabled ? "hide" : "") }>{$.t('cluster_page.actions_tab.reset_environment_warning')}</div>
                    </div>
                    <button className="btn btn-danger action-btn reset-environment-btn" onClick={this.applyAction} disabled={this.state.disabled}>{$.t('common.reset_button')}</button>
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
                <Action className='span4' title={$.t('cluster_page.actions_tab.delete_environment')}>
                    <div className="action-body">
                        <div className="action-item-description important">{$.t('cluster_page.actions_tab.alert_delete')}</div>
                    </div>
                    <button className="btn btn-danger action-btn delete-environment-btn" onClick={this.applyAction}><span>{$.t('common.delete_button')}</span></button>
                </Action>
            );
        }
    });

    var UpdateEnvironmentAction = React.createClass({
        render: function() {
            return (
                <Action className='span12 action-update' title={$.t('cluster_page.actions_tab.update_environment')}>
                    <div className="action-body">
                        <div className="action-item-description important">{$.t('cluster_page.actions_tab.alert_delete')}</div>
                    </div>
                    <button className="btn btn-danger action-btn update-environment-btn" ><span>{$.t('common.update_button')}</span></button>
                </Action>
            );
        }
    });

    return ActionsTab;
});
