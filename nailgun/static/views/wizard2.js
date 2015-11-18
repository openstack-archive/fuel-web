/*
 * Copyright 2015 Mirantis, Inc.
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
    'backbone',
    'utils',
    'models',
    'component_mixins',
    'views/dialogs',
    'views/controls'
],
function($, _, i18n, React, Backbone, utils, models, componentMixins, dialogs, controls) {
    'use strict';

    class ComponentModel extends models.BaseModel {
        constructor(component) {
            super(component);
        }
        initialize(component) {
            this.set({
                id: component.name,
                enabled: component.enabled,
                type: _.first(component.name.split(':')),
                name: component.name,
                label: i18n(component.label),
                description: component.description && i18n(component.description),
                compatible: component.compatible,
                incompatible: component.incompatible
            })
        }
    }

    class ComponentPattern {
        constructor(pattern) {
            this.pattern = pattern;
            this.parts = pattern.split(':');
        }
        match(componentName) {
            var componentParts = componentName.split(':');
            if (componentParts.length < this.parts.length) {
                return false;
            }
            _.each(this.parts, (part, index) => {
                return part + index; // TODO remove it
                //console.log('ComponentPattern match', part, index);
            })
            return false;
        }
    }
    window.shit = new ComponentPattern('void'); // TODO, remove it

    class ComponentsCollection extends models.BaseCollection {
        constructor(releaseId) {
            super();
            this.releaseId = releaseId;
            this.model = ComponentModel;
        }
        url() {
            return '/api/v1/releases/' + this.releaseId + '/components';
        }
        parse(response) {
            return response.components;
        }
        getComponentsByType(type, options) {
            var components = this.where({type: type});
            if (options && options.sorted) {
                components.sort((component1, component2) => {
                    return component2.weight - component1.weight;
                });
            }
            return components;
        }
    }

    var ClusterWizardPanesMixin = {
        componentDidMount: function() {
            $(this.getDOMNode()).find('input:enabled').first().focus();
        },
        renderWarnings: function(/*warnings*/) {
            //if (warnings.length == 0) {
            //    return null;
            //}
            //return (
            //    <div className='alert alert-warning'>
            //        {
            //            _.map(warnings, function(warning) {
            //                return (
            //                    <div key={warning}>{i18n(warning, this.props.wizard.translationParams)}</div>
            //                )
            //            }, this)
            //        }
            //    </div>
            //);
        },
        renderControls: function(/*paneName, metadata, paneData, actions*/) {
            //var paneControls = _.pairs(metadata);
            //paneControls.sort(function(control1, control2) {
            //    return control1[1].weight - control2[1].weight;
            //});
            //return _.map(paneControls, function(value) {
            //    var [key, meta] = value;
            //    switch (meta.type) {
            //        case 'radio':
            //            return _.map(meta.values, function(value) {
            //                var optionKey = key + '.' + value.data;
            //                if (actions[optionKey] && actions[optionKey].hide) {
            //                    return null;
            //                }
            //                return (
            //                    <controls.Input
            //                        key={optionKey}
            //                        name={key}
            //                        type='radio'
            //                        value={value.data}
            //                        checked={value.data == paneData[key]}
            //                        label={i18n(value.label)}
            //                        description={value.description && i18n(value.description)}
            //                        onChange={_.partial(this.props.onChange, paneName)}
            //                        disabled={actions[optionKey] && actions[optionKey].disable}
            //                        />
            //                );
            //            }, this);
            //        case 'checkbox':
            //            if (actions[key] && actions[key].hide) {
            //                return null;
            //            }
            //            return (
            //                <controls.Input
            //                    key={key}
            //                    name={key}
            //                    type='checkbox'
            //                    value={paneData[key]}
            //                    checked={paneData[key]}
            //                    label={i18n(meta.label)}
            //                    description={meta.description && i18n(meta.description)}
            //                    onChange={_.partial(this.props.onChange, paneName)}
            //                    disabled={actions[key] && actions[key].disable}
            //                    />
            //            );
            //        default:
            //            if (actions[key] && actions[key].hide) {
            //                return null;
            //            }
            //            return (<div key={key}>{meta.type} control type isn't supported in wizard</div>);
            //    }
            //}, this);
        }
    };

    var NameAndRelease = React.createClass({
        mixins: [ClusterWizardPanesMixin],
        statics: {
            paneName: 'NameAndRelease',
            title: i18n('dialog.create_cluster_wizard.name_release.title')
        },
        render: function() {
            var releases = this.props.releases,
                nameAndRelease = this.props.wizard.get('NameAndRelease');
            if (this.props.loading) {
                return null;
            }
            var os = nameAndRelease.release.get('operating_system'),
                connectivityAlert = i18n('dialog.create_cluster_wizard.name_release.' + os + '_connectivity_alert');
            return (
                <div className='create-cluster-form name-and-release'>
                    <controls.Input
                        type='text'
                        name='name'
                        autoComplete='off'
                        label={i18n('dialog.create_cluster_wizard.name_release.name')}
                        value={nameAndRelease.name}
                        error={nameAndRelease.name_error}
                        onChange={_.partial(this.props.onChange, 'NameAndRelease')}
                    />
                    <controls.Input
                        type='select'
                        name='release'
                        label={i18n('dialog.create_cluster_wizard.name_release.release_label')}
                        value={nameAndRelease.release && nameAndRelease.release.id}
                        onChange={_.partial(this.props.onChange, 'NameAndRelease')}
                    >
                        {
                            releases.map(function(release) {
                                if (!release.get('is_deployable')) {
                                    return null;
                                }
                                return <option key={release.id} value={release.id}>{release.get('name')}</option>
                            })
                        }
                    </controls.Input>
                    <div className='help-block'>
                        {connectivityAlert &&
                        <div className='alert alert-warning'>{connectivityAlert}</div>
                        }
                        <div className='release-description'>{nameAndRelease.release.get('description')}</div>
                    </div>
                </div>
            );
        }
    });

    var Compute = React.createClass({
        mixins: [ClusterWizardPanesMixin],
        statics: {
            paneName: 'Compute',
            title: i18n('dialog.create_cluster_wizard.compute.title')
        },
        render: function() {
            if (!this.props.components) {
                return null;
            }
            var hypervisors = this.props.components.getComponentsByType('hypervisor', {sorted: true});
            return (
                <div className='wizard-compute-pane'>
                    {
                        _.map(hypervisors, (hypervisor) => {
                            return (
                                <controls.Input
                                    type='checkbox'
                                    label={hypervisor.get('label')}
                                    description={hypervisor.get('description')}
                                    value={hypervisor.get('name')}
                                    checked={!!hypervisor.get('enabled')}
                                />
                            );
                        })
                    }
                </div>
            );
        }
    });

    var Network = React.createClass({
        mixins: [ClusterWizardPanesMixin],
        statics: {
            paneName: 'Network',
            title: i18n('dialog.create_cluster_wizard.network.title')
        },
        processNetworks: function(networks) {
            var result = {
                monolith: [],
                ml2: []
            };
            _.each(networks, (network) => {
                if (network.get('name').match(/^network\:neutron\:core\:ml2/)) {
                    result.ml2.push(network);
                } else {
                    result.monolith.push(network);
                }
            });
            if (result.ml2.length > 0) {
                result.monolith.push({
                    type: 'network',
                    name: 'network:neutron:core:ml2'
                });
            }
            return result;
        },
        render: function() {
            if (!this.props.components) {
                return null;
            }
            var networks = this.props.components.getComponentsByType('network', {sorted: true});
            networks = this.processNetworks(networks);
            //console.log('networks are', networks);
            return (
                <div className='wizard-network-pane'>
                    {
                        _.map(networks.monolith, (network) => {
                            return (
                                <controls.Input
                                    type='radio'
                                    name='network'
                                    label={network.get('label')}
                                    description={network.get('description')}
                                    value={network.get('name')}
                                    checked={!!network.get('enabled')}
                                />
                            );
                        })
                    }
                    <div style={{'margin-left': '40px'}}>
                    {
                        _.map(networks.ml2, (network) => {
                            return (
                                <controls.Input
                                    type='checkbox'
                                    name={network.name}
                                    label={network.label}
                                    description={network.description}
                                    value={network.name}
                                    checked={!!network.get('enabled')}
                                />
                            );
                        })
                    }
                    </div>
                </div>
            );
        }
    });

    var Storage = React.createClass({
        mixins: [ClusterWizardPanesMixin],
        statics: {
            paneName: 'Storage',
            title: i18n('dialog.create_cluster_wizard.storage.title')
        },
        render: function() {
            if (!this.props.components) {
                return null;
            }
            var storages = this.props.components.getComponentsByType('storage', {sorted: true});
            return (
                <div className='wizard-compute-pane'>
                    <p><big>Use Ceph?</big></p>
                    {
                        _.map(storages, (storage) => {
                            return (
                                <controls.Input
                                    type='radio'
                                    name='storage'
                                    label={storage.get('label')}
                                    description={storage.get('description')}
                                    value={storage.get('name')}
                                    checked={!!storage.get('enabled')}
                                />
                            );
                        })
                    }
                </div>
            );
        }
    });

    var AdditionalServices = React.createClass({
        mixins: [ClusterWizardPanesMixin],
        statics: {
            paneName: 'AdditionalServices',
            title: i18n('dialog.create_cluster_wizard.additional.title')
        },
        render: function() {
            if (!this.props.components) {
                return null;
            }
            var additionalServices = this.props.components.getComponentsByType('additional_service', {sorted: true});
            return (
                <div className='wizard-compute-pane'>
                    {
                        _.map(additionalServices, (additionalService) => {
                            return (
                                <controls.Input
                                    type='checkbox'
                                    name={additionalService.get('name')}
                                    label={additionalService.get('label')}
                                    description={additionalService.get('description')}
                                    value={additionalService.get('name')}
                                    checked={!!additionalService.get('enabled')}
                                />
                            );
                        })
                    }
                </div>
            );
        }
    });

    var Finish = React.createClass({
        statics: {
            paneName: 'Finish',
            title: i18n('dialog.create_cluster_wizard.ready.title')
        },
        render: function() {
            return (
                <p>
                    <span>{i18n('dialog.create_cluster_wizard.ready.env_select_deploy')} </span>
                    <b>{i18n('dialog.create_cluster_wizard.ready.deploy')} </b>
                    <span>{i18n('dialog.create_cluster_wizard.ready.or_make_config_choice')} </span>
                    <b>{i18n('dialog.create_cluster_wizard.ready.env')} </b>
                    <span>{i18n('dialog.create_cluster_wizard.ready.console')}</span>
                </p>
            );
        }
    });

    var clusterWizardPanes = [
        NameAndRelease,
        Compute,
        Network,
        Storage,
        AdditionalServices,
        Finish
    ];


    var CreateClusterWizard = React.createClass({
        mixins: [dialogs.dialogMixin],
        getInitialState: function() {
            return {
                title: i18n('dialog.create_cluster_wizard.title'),
                loading: true,
                activePaneIndex: 0,
                maxAvailablePaneIndex: 0,
                panes: clusterWizardPanes,
                paneHasErrors: false,
                previousAvailable: true,
                nextAvailable: true,
                createEnabled: false
            };
        },
        componentWillMount: function() {
            this.stopHandlingKeys = false;

            this.wizard = new Backbone.DeepModel();
            this.cluster = new models.Cluster();
            this.settings = new models.Settings();
            this.releases = new models.Releases();
        },
        componentDidMount: function() {
            this.releases.fetch().done(_.bind(function() {
                var defaultRelease = this.releases.findWhere({is_deployable: true});
                this.wizard.set('NameAndRelease.release', defaultRelease.id);
                this.selectRelease(defaultRelease.id);
                //this.processRestrictions();
                //this.processTrackedAttributes();
                this.setState({loading: false});
            }, this));

            this.updateState({activePaneIndex: 0});
        },
        getListOfPanesToRestore: function(currentIndex, maxIndex) {
            var panesNames = [];
            _.each(clusterWizardPanes, function(pane, paneIndex) {
                if ((paneIndex <= maxIndex) && (paneIndex > currentIndex)) {
                    panesNames.push(pane.paneName);
                }
            }, this);
            return panesNames;
        },
        updateState: function(nextState) {
            var numberOfPanes = this.getEnabledPanes().length;
            var paneHasErrors = _.isBoolean(nextState.paneHasErrors) ? nextState.paneHasErrors : this.state.paneHasErrors;
            var nextActivePaneIndex = _.isNumber(nextState.activePaneIndex) ? nextState.activePaneIndex : this.state.activePaneIndex;

            var newState = _.merge(nextState, {
                activePaneIndex: nextActivePaneIndex,
                previousEnabled: nextActivePaneIndex > 0,
                nextEnabled: !paneHasErrors,
                nextVisible: (nextActivePaneIndex < numberOfPanes - 1),
                createVisible: nextActivePaneIndex == numberOfPanes - 1
            });
            this.setState(newState);
        },
        getEnabledPanes: function() {
            return _.filter(this.state.panes, function(pane) {return !pane.hidden});
        },
        getActivePane: function() {
            var panes = this.getEnabledPanes();
            return panes[this.state.activePaneIndex];
        },
        prevPane: function() {
            //this.processBinds('wizard', this.getActivePane().paneName);
            this.updateState({activePaneIndex: this.state.activePaneIndex - 1});
        },
        nextPane: function() {
            if (this.state.activePaneIndex == 0) {
                var status = this.createCluster();
                if (!status) {
                    this.updateState({paneHasErrors: true});
                    return;
                }
            }
            //this.processBinds('wizard', this.getActivePane().paneName);
            var nextIndex = this.state.activePaneIndex + 1;
            this.updateState({
                activePaneIndex: nextIndex,
                maxAvailablePaneIndex: _.max([nextIndex, this.state.maxAvailablePaneIndex]),
                paneHasErrors: false
            });
        },
        goToPane: function(index) {
            if (index > this.state.maxAvailablePaneIndex) {
                return;
            }
            //this.processBinds('wizard', this.getActivePane().paneName);
            this.updateState({activePaneIndex: index});
        },
        createCluster: function() {
            var success = true;
            var name = this.wizard.get('NameAndRelease.name');
            var release = this.wizard.get('NameAndRelease.release');
            this.cluster.off();
            this.cluster.on('invalid', function() {
                success = false;
            }, this);
            if (this.props.clusters.findWhere({name: name})) {
                var error = i18n('dialog.create_cluster_wizard.name_release.existing_environment', {name: name});
                this.wizard.set({'NameAndRelease.name_error': error});
                return false;
            }
            success = success && this.cluster.set({
                name: name,
                release: release
            }, {validate: true});
            if (this.cluster.validationError && this.cluster.validationError.name) {
                this.wizard.set({'NameAndRelease.name_error': this.cluster.validationError.name});
                return false;
            }
            return success;
        },
        saveCluster: function() {
            if (this.stopHandlingKeys) {
                return;
            }
            this.stopHandlingKeys = true;
            this.setState({actionInProgress: true});
            var cluster = this.cluster;
            //this.processBinds('cluster');
            var deferred = cluster.save();
            if (deferred) {
                this.updateState({disabled: true});
                deferred
                    .done(_.bind(function() {
                        this.props.clusters.add(cluster);
                        this.settings.url = _.result(cluster, 'url') + '/attributes';
                        this.settings.fetch()
                            .then(_.bind(function() {
                                this.processBinds('settings');
                                return this.settings.save(this.settings.attributes, {validate: false});
                            }, this))
                            .done(_.bind(function() {
                                this.close();
                                app.nodeNetworkGroups.fetch();
                                app.navigate('#cluster/' + this.cluster.id, {trigger: true});
                            }, this))
                            .fail(_.bind(function(response) {
                                this.close();
                                utils.showErrorDialog({
                                    response: response,
                                    title: i18n('dialog.create_cluster_wizard.create_cluster_error.title')
                                });
                            }, this))
                    }, this))
                    .fail(_.bind(function(response) {
                        this.stopHandlingKeys = false;
                        this.setState({actionInProgress: false});
                        if (response.status == 409) {
                            this.updateState({disabled: false, activePaneIndex: 0});
                            cluster.trigger('invalid', cluster, {name: utils.getResponseText(response)});
                        } else {
                            this.close();
                            utils.showErrorDialog({
                                response: response,
                                title: i18n('dialog.create_cluster_wizard.create_cluster_error.title')
                            });
                        }
                    }, this));
            }
        },
        selectRelease: function(releaseId) {
            var release = this.releases.findWhere({id: releaseId});
            this.wizard.set('NameAndRelease.release', release);

            // components
            this.setState({loading: true});
            this.components = new ComponentsCollection(releaseId);
            this.components.fetch().done(() => {
                this.setState({loading: false});
            });
        },
        onChange: function(paneName, field, value) {
            if (paneName == 'NameAndRelease') {
                if (field == 'name') {
                    this.wizard.set('NameAndRelease.name', value);
                    this.wizard.unset('NameAndRelease.name_error');
                } else if (field == 'release') {
                    this.selectRelease(parseInt(value));
                }
                this.updateState({paneHasErrors: false});
                return;
            }
            var path = paneName + '.' + field;
            this.wizard.set(path, value);
            if (this.trackedAttributes[path]) {
                this.handleTrackedAttributeChange();
            }
            this.updateState({paneHasErrors: false});
        },
        onKeyDown: function(e) {
            if (this.state.actionInProgress) {
                return;
            }
            if (e.key == 'Enter') {
                e.preventDefault();

                if (this.getActivePane().paneName == 'Finish') {
                    this.saveCluster();
                } else {
                    this.nextPane();
                }
            }
        },
        renderBody: function() {
            var activeIndex = this.state.activePaneIndex;
            var Pane = this.getActivePane();
            return (
                <div className='wizard-body'>
                    <div className='wizard-steps-box'>
                        <div className='wizard-steps-nav col-xs-3'>
                            <ul className='wizard-step-nav-item nav nav-pills nav-stacked'>
                                {
                                    this.state.panes.map(function(pane, index) {
                                        var classes = utils.classNames('wizard-step', {
                                            disabled: index > this.state.maxAvailablePaneIndex,
                                            available: index <= this.state.maxAvailablePaneIndex && index != activeIndex,
                                            active: index == activeIndex
                                        });
                                        return (
                                            <li key={pane.title} role='wizard-step'
                                                className={classes}>
                                                <a onClick={_.partial(this.goToPane, index)}>{pane.title}</a>
                                            </li>
                                        );
                                    }, this)
                                }
                            </ul>
                        </div>
                        <div className='pane-content col-xs-9 forms-box access'>
                            <Pane
                                ref='pane'
                                actionInProgress={this.state.actionInProgress}
                                loading={this.state.loading}
                                onChange={this.onChange}
                                releases={this.releases}
                                wizard={this.wizard}
                                components={this.components}
                            />
                        </div>
                        <div className='clearfix'></div>
                    </div>
                </div>
            );
        },
        renderFooter: function() {
            var actionInProgress = this.state.actionInProgress;
            return (
                <div className='wizard-footer'>
                    <button className={utils.classNames('btn btn-default pull-left', {disabled: actionInProgress})} data-dismiss='modal'>
                        {i18n('common.cancel_button')}
                    </button>
                    <button
                        className={utils.classNames('btn btn-default prev-pane-btn', {disabled: !this.state.previousEnabled || actionInProgress})}
                        onClick={this.prevPane}
                        >
                        <i className='glyphicon glyphicon-arrow-left' aria-hidden='true'></i>
                        &nbsp;
                        <span>{i18n('dialog.create_cluster_wizard.prev')}</span>
                    </button>
                    {this.state.nextVisible &&
                    <button
                        className={utils.classNames('btn btn-default btn-success next-pane-btn', {disabled: !this.state.nextEnabled || actionInProgress})}
                        onClick={this.nextPane}
                        >
                        <span>{i18n('dialog.create_cluster_wizard.next')}</span>
                        &nbsp;
                        <i className='glyphicon glyphicon-arrow-right' aria-hidden='true'></i>
                    </button>
                    }
                    {this.state.createVisible &&
                    <button
                        className={utils.classNames('btn btn-default btn-success finish-btn', {disabled: actionInProgress})}
                        onClick={this.saveCluster}
                        autoFocus
                        >
                        {i18n('dialog.create_cluster_wizard.create')}
                    </button>
                    }
                </div>
            );
        }
    });

    return CreateClusterWizard;
});
