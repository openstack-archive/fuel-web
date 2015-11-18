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

    var ClusterWizardPanesMixin = {
        componentWillMount() {
            if (this.props.components) {
                var components = this.props.components.getComponentsByType(this.constructor.componentType, {sorted: true});
                this.processRestrictions(components);
            }
        },
        componentDidMount: function() {
            $(this.getDOMNode()).find('input:enabled').first().focus();
        },
        processRestrictions: function(components, types) {
            this.processIncompatible(components, types);
            this.processRequires(components, types);
        },
        processIncompatible: function(components, types) {
            // disable components that have
            // incompatible components already enabled
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
                        warnings.push(incompatible.message);
                    }
                });
                component.set({disabled: isDisabled, warnings: warnings.join(' ')});
            });
        },
        processRequires: function(components, types) {
            // if component has requires,
            // it is disabled until all requires are already enabled
            _.each(components, (component) => {
                var requires = component.get('requires') || [];
                if (requires.length == 0) {
                    // no requires
                    component.set({isRequired: false});
                    return;
                }
                var isDisabled = true;
                var warnings = [];
                _.each(requires, (require) => {
                    var type = require.component.get('type');
                    if (!_.contains(types, type)) {
                        // ignore forward requires
                        return;
                    }
                    if (require.component.get('enabled')) {
                        isDisabled = false;
                        warnings.push(require.message);
                    }
                });
                component.set({disabled: isDisabled, isRequired: true, warnings: warnings.join(' ')});
            });
        },
        selectDefaultComponent: function(components) {
            var active = _.find(components, (component) => component.get('enabled'));
            if (active && !active.get('disabled')) {
                return;
            }
            var newActive = _.find(components, (component) => !component.get('disabled'));
            if (newActive) {
                newActive.set({enabled: true});
            }
            if (active) {
                active.set({enabled: false});
            }
        }
    };

    var ClusterRadioPanesMixin = {
        getInitialState: function() {
            var components = this.props.components.getComponentsByType(this.constructor.componentType, {sorted: true});
            var active = _.find(components, (component) => component.get('enabled'));
            return {
                activeComponentId: active && active.id
            };
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
                                return <option key={release.id} value={release.id}>{release.get('name')}</option>;
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
            return (
                <div className='wizard-compute-pane'>
                    {
                        _.map(hypervisors, (hypervisor) => {
                            return (
                                <controls.Input
                                    key={hypervisor.id}
                                    type='checkbox'
                                    name={hypervisor.id}
                                    label={hypervisor.get('label')}
                                    description={hypervisor.get('description')}
                                    value={hypervisor.id}
                                    checked={!!hypervisor.get('enabled')}
                                    disabled={hypervisor.get('disabled')}
                                    tooltipText={hypervisor.get('warnings')}
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
        componentWillMount: function() {
            var networks = this.props.components.getComponentsByType('network', {sorted: true});
            this.processRestrictions(networks, ['hypervisor']);
            this.selectDefaultComponent(networks);
        },
        render: function() {
            if (!this.props.components) {
                return null;
            }
            var networks = this.props.components.getComponentsByType('network', {sorted: true});
            this.processRestrictions(networks, ['hypervisor']);
            return (
                <div className='wizard-network-pane'>
                    {
                        _.map(networks, (network) => {
                            return (
                                <controls.Input
                                    key={network.id}
                                    type='radio'
                                    name={network.id}
                                    label={network.get('label')}
                                    description={network.get('description')}
                                    value={network.id}
                                    checked={!!network.get('enabled')}
                                    disabled={!!network.get('disabled')}
                                    tooltipText={network.get('warnings')}
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
            return (
                <div className='wizard-compute-pane'>
                    <p><big>Use Ceph?</big></p>
                    {
                        _.map(storages, (storage) => {
                            return (
                                <controls.Input
                                    key={storage.id}
                                    type='radio'
                                    name={storage.id}
                                    label={storage.get('label')}
                                    description={storage.get('description')}
                                    value={storage.get('name')}
                                    checked={!!storage.get('enabled')}
                                    disabled={!!storage.get('disabled')}
                                    tooltipText={storage.get('warnings')}
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
            return (
                <div className='wizard-compute-pane'>
                    {
                        _.map(additionalServices, (additionalService) => {
                            return (
                                <controls.Input
                                    key={additionalService.id}
                                    type='checkbox'
                                    name={additionalService.get('name')}
                                    label={additionalService.get('label')}
                                    description={additionalService.get('description')}
                                    value={additionalService.get('name')}
                                    checked={!!additionalService.get('enabled')}
                                    disabled={!!additionalService.get('disabled')}
                                    tooltipText={additionalService.get('warnings')}
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
            return _.filter(this.state.panes, function(pane) {return !pane.hidden;});
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
            this.components = new models.ComponentsCollection(releaseId);
            this.components.fetch().done(() => {
                this.components.invoke('expandWildcards', this.components);
                this.components.invoke('restoreDefaultValue', this.components);
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
