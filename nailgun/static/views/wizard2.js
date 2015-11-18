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

    class ComponentPattern {
        constructor(pattern) {
            this.pattern = pattern;
            this.parts = pattern.split(':');
            this.hasWildcard = _.contains(this.parts, '*');
        }
        match(componentName) {
            if (!this.hasWildcard) {
                return this.pattern == componentName;
            }

            var componentParts = componentName.split(':');
            if (componentParts.length < this.parts.length) {
                return false;
            }
            var matched = true;
            _.each(this.parts, (part, index) => {
                if (part == '*') {
                    return;
                }
                if (part != componentParts[index]) {
                    matched = false;
                }
            });
            return matched;
        }
    }

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
        expandWildcards(components) {
            // compatible
            var compatibleComponents = [];
            _.each(this.get('compatible'), (compatible) => {
                var pattern = new ComponentPattern(compatible.name);
                components.each((component) => {
                    if (pattern.match(component.id)) {
                        compatibleComponents.push({
                            component: component,
                            message: i18n(compatible.message || '')
                        });
                    }
                })
            });
            // incompatible
            var incompatibleComponents = [];
            _.each(this.get('incompatible'), (incompatible) => {
                var pattern = new ComponentPattern(incompatible.name);
                components.each((component) => {
                    if (pattern.match(component.id)) {
                        incompatibleComponents.push({
                            component: component,
                            message: i18n(incompatible.message || '')
                        });
                    }
                })
            });
            this.set({
                compatible: compatibleComponents,
                incompatible: incompatibleComponents
            });
        }
        toJSON() {
            return this.get('enabled') ? this.id : null;
        }
    }

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
            if (_.isArray(response)) {
                return response;
            }
            return [];
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
        toJSON() {
            return _.compact(_.map(this.models, (model) => model.toJSON()))
        }
    }

    var ClusterWizardPanesMixin = {
        componentDidMount: function() {
            $(this.getDOMNode()).find('input:enabled').first().focus();
        },
        processRestrictions: function(components, types) {
            _.each(components, (component) => {
                var incompatibles = component.get('incompatible') || [];

                var isDisabled = false;
                var warnings = [];
                _.each(incompatibles, (incompatible) => {
                    var type = incompatible.component.get('type');
                    if (!_.contains(types, type)) {
                        // ignore forward incompatibilities
                        return;
                    }
                    if (incompatible.component.get('enabled')) {
                        isDisabled = true;
                        warnings.push(incompatible.message)
                    }
                });
                component.set({disabled: isDisabled, warnings: warnings});
            });
        },
        debug: function(components) {
            _.each(components, (component) => {
                //console.log(component.id, component.get('enabled'), incompatibles.map((item) => item.id).join(' '));
                var incompatibles = component.get('incompatible') || [];
                return incompatibles;
            });
        },
        renderWarnings: function(components) {
            var warnings = _.flatten(_.map(components, (component) => {
                return component.get('warnings');
            }));

            if (warnings.length == 0) {
                return null;
            }

            return (
                <div className='alert alert-warning'>
                    {
                        _.map(warnings, function(warning) {
                            return (
                                <div key={warning}>{i18n(warning, this.props.wizard.translationParams)}</div>
                            )
                        }, this)
                    }
                </div>
            );
        }
    };

    var ClusterRadioPanesMixin = {
        getInitialState: function() {
            var networks = this.props.components.getComponentsByType(this.constructor.componentType, {sorted: true});
            var active = _.find(networks, (network) => network.get('enabled'));
            return {
                activeComponentId: active.id
            }
        },
        onChange: function(componentId) {
            if (this.state.activeComponentId == componentId) {
                return;
            }
            this.props.onChange(this.state.activeComponentId, false);
            this.props.onChange(componentId, true);
            this.setState({activeComponentId: componentId});
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
                name = this.props.wizard.get('name'),
                nameError = this.props.wizard.get('name_error'),
                release = this.props.wizard.get('release');

            if (this.props.loading) {
                return null;
            }
            var os = release.get('operating_system'),
                connectivityAlert = i18n('dialog.create_cluster_wizard.name_release.' + os + '_connectivity_alert');
            return (
                <div className='create-cluster-form name-and-release'>
                    <controls.Input
                        type='text'
                        name='name'
                        autoComplete='off'
                        label={i18n('dialog.create_cluster_wizard.name_release.name')}
                        value={name}
                        error={nameError}
                        onChange={this.props.onChange}
                    />
                    <controls.Input
                        type='select'
                        name='release'
                        label={i18n('dialog.create_cluster_wizard.name_release.release_label')}
                        value={release.id}
                        onChange={this.props.onChange}
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
                        <div className='release-description'>{release.get('description')}</div>
                    </div>
                </div>
            );
        }
    });

    var Compute = React.createClass({
        mixins: [ClusterWizardPanesMixin],
        statics: {
            paneName: 'Compute',
            componentType: 'hypervisor',
            title: i18n('dialog.create_cluster_wizard.compute.title')
        },
        render: function() {
            if (!this.props.components) {
                return null;
            }
            var hypervisors = this.props.components.getComponentsByType('hypervisor', {sorted: true});
            this.processRestrictions(hypervisors, ['hypervisor']);
            this.debug(hypervisors);
            return (
                <div className='wizard-compute-pane'>
                    {this.renderWarnings(hypervisors)}
                    {
                        _.map(hypervisors, (hypervisor) => {
                            return (
                                <controls.Input
                                    type='checkbox'
                                    name={hypervisor.id}
                                    label={hypervisor.get('label')}
                                    description={hypervisor.get('description')}
                                    value={hypervisor.id}
                                    checked={!!hypervisor.get('enabled')}
                                    disabled={hypervisor.get('disabled')}
                                    onChange={this.props.onChange}
                                />
                            );
                        })
                    }
                </div>
            );
        }
    });

    var Network = React.createClass({
        mixins: [ClusterWizardPanesMixin, ClusterRadioPanesMixin],
        statics: {
            paneName: 'Network',
            componentType: 'network',
            title: i18n('dialog.create_cluster_wizard.network.title')
        },
        render: function() {
            if (!this.props.components) {
                return null;
            }
            var networks = this.props.components.getComponentsByType('network', {sorted: true});
            this.processRestrictions(networks, ['hypervisor']);
            this.debug(networks);
            return (
                <div className='wizard-network-pane'>
                    {this.renderWarnings(networks)}
                    {
                        _.map(networks, (network) => {
                            return (
                                <controls.Input
                                    type='radio'
                                    name={network.id}
                                    label={network.get('label')}
                                    description={network.get('description')}
                                    value={network.id}
                                    checked={!!network.get('enabled')}
                                    disabled={!!network.get('disabled')}
                                    onChange={this.onChange}
                                />
                            );
                        })
                    }
                </div>
            );
        }
    });

    var Storage = React.createClass({
        mixins: [ClusterWizardPanesMixin, ClusterRadioPanesMixin],
        statics: {
            paneName: 'Storage',
            componentType: 'storage',
            title: i18n('dialog.create_cluster_wizard.storage.title')
        },
        render: function() {
            if (!this.props.components) {
                return null;
            }
            var storages = this.props.components.getComponentsByType('storage', {sorted: true});
            this.processRestrictions(storages, ['hypervisor', 'networks']);
            this.debug(storages);
            return (
                <div className='wizard-compute-pane'>
                    {this.renderWarnings(storages)}
                    <p><big>Use Ceph?</big></p>
                    {
                        _.map(storages, (storage) => {
                            return (
                                <controls.Input
                                    type='radio'
                                    name={storage.id}
                                    label={storage.get('label')}
                                    description={storage.get('description')}
                                    value={storage.get('name')}
                                    checked={!!storage.get('enabled')}
                                    disabled={!!storage.get('disabled')}
                                    onChange={this.onChange}
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
            componentType: 'additional_service',
            title: i18n('dialog.create_cluster_wizard.additional.title')
        },
        render: function() {
            if (!this.props.components) {
                return null;
            }
            var additionalServices = this.props.components.getComponentsByType('additional_service', {sorted: true});
            this.processRestrictions(additionalServices, ['hypervisor', 'network', 'storage']);
            this.debug(additionalServices);
            return (
                <div className='wizard-compute-pane'>
                    {this.renderWarnings(additionalServices)}
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
                                    disabled={!!additionalService.get('disabled')}
                                    onChange={this.props.onChange}
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
            this.settings = new models.Settings();
            this.releases = new models.Releases();
            this.cluster = new models.Cluster();
        },
        componentDidMount: function() {
            this.releases.fetch().done(_.bind(function() {
                var defaultRelease = this.releases.findWhere({is_deployable: true});
                this.wizard.set('release', defaultRelease.id);
                this.selectRelease(defaultRelease.id);
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
            var name = this.wizard.get('name');
            var release = this.wizard.get('release');
            this.cluster.off();
            this.cluster.on('invalid', function() {
                success = false;
            }, this);
            if (this.props.clusters.findWhere({name: name})) {
                var error = i18n('dialog.create_cluster_wizard.name_release.existing_environment', {name: name});
                this.wizard.set({name_error: error});
                return false;
            }
            success = success && this.cluster.set({
                name: name,
                release: release.id,
                components: this.components
            }, {validate: true});
            if (this.cluster.validationError && this.cluster.validationError.name) {
                this.wizard.set({name_error: this.cluster.validationError.name});
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
            var deferred = cluster.save();
            if (deferred) {
                this.updateState({disabled: true});
                deferred.done(() => {
                        this.props.clusters.add(cluster);
                        this.close();
                        app.nodeNetworkGroups.fetch();
                        app.navigate('#cluster/' + this.cluster.id, {trigger: true});
                    })
                    .fail((response) => {
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
                    });
            }
        },
        selectRelease: function(releaseId) {
            var release = this.releases.findWhere({id: releaseId});
            this.wizard.set('release', release);

            // components
            this.setState({loading: true});
            this.components = new ComponentsCollection(releaseId);
            this.components.fetch().done(() => {
                this.components.invoke('expandWildcards', this.components);
                this.setState({loading: false});
            });
        },
        onChange: function(name, value) {
            switch (name) {
                case 'name':
                    this.wizard.set('name', value);
                    this.wizard.unset('name_error');
                    break;
                case 'release':
                    this.selectRelease(parseInt(value));
                    break;
                default:
                    var component = this.components.findWhere({id: name});
                    component.set({enabled: value});
                    break;
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
