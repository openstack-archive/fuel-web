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
        componentWillMount: function() {
            if (this.props.components) {
                var components = this.props.components.getComponentsByType(this.constructor.componentType, {sorted: true});
                this.processRestrictions(components);
            }
        },
        componentDidMount: function() {
            $(this.getDOMNode()).find('input:enabled').first().focus();
        },
        processRestrictions: function(paneComponents, types) {
            this.processIncompatible(paneComponents, types);
            this.processRequires(paneComponents, types);
        },
        processCompatible: function(allComponents, paneComponents, types) {
            // all previously enabled components
            // should be compatible with the current component
            _.each(paneComponents, (component) => {
                // index of compatible elements
                var index = {};
                var compatibles = component.get('compatible') || [];
                _.each(compatibles, (compatible) => {
                    index[compatible.component.id] = compatible;
                });
                // skip already disabled
                if (component.get('disabled')) {
                    return;
                }

                // scan all components to find enabled
                // and not present in the index
                var isCompatible = true;
                allComponents.each((testedComponent) => {
                    var type = testedComponent.get('type');
                    if (component.id == testedComponent.id || !_.contains(types, type)) {
                        // ignore self or forward compatibilities
                        return;
                    }
                    if (testedComponent.get('enabled') && !index[testedComponent.id]) {
                        //console.log('not compatible' component.id, testedComponent.id)
                        isCompatible = false;
                    }
                });
                component.set({
                    isCompatible: isCompatible,
                    warnings: ' ',
                    tooltipIcon: (isCompatible ? 'glyphicon-ok-sign' : 'glyphicon-info-sign')
                });
            });
        },
        processIncompatible: function(paneComponents, types) {
            // disable components that have
            // incompatible components already enabled
            _.each(paneComponents, (component) => {
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
                component.set({
                    disabled: isDisabled,
                    warnings: warnings.join(' '),
                    tooltipIcon: 'glyphicon-warning-sign'
                });
            });
        },
        processRequires: function(paneComponents, types) {
            // if component has requires,
            // it is disabled until all requires are already enabled
            _.each(paneComponents, (component) => {
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
                component.set({
                    disabled: isDisabled,
                    isRequired: true,
                    warnings: !isDisabled ? warnings.join(' ') : null,
                    tooltipIcon: 'glyphicon-warning-sign'
                });
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
        },
        renderControls: function(components, isRadio, onChange) {
            return (
                <div>
                {
                    _.map(components, (component) => {
                        return (
                            <controls.Input
                                key={component.id}
                                type={isRadio ? 'radio' : 'checkbox'}
                                name={component.id}
                                label={component.get('label')}
                                description={component.get('description')}
                                value={component.id}
                                checked={!!component.get('enabled')}
                                disabled={!!component.get('disabled')}
                                tooltipIcon={component.get('tooltipIcon')}
                                tooltipText={component.get('warnings')}
                                onChange={onChange}
                            />
                        );
                    })
                }
                </div>
            );
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
        hasErrors: function() {
            var hypervisors = this.props.components.getComponentsByType('hypervisor', {sorted: true});
            return !_.any(hypervisors, (hypervisor) => !!hypervisor.get('enabled'));
        },
        render: function() {
            if (!this.props.components) {
                return null;
            }
            var hypervisors = this.props.components.getComponentsByType('hypervisor', {sorted: true});
            this.processRestrictions(hypervisors, ['hypervisor']);
            return (
                <div className='wizard-compute-pane'>
                    {this.renderControls(hypervisors, false, this.props.onChange)}
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
            this.processCompatible(this.props.components, networks, ['hypervisor']);
            this.selectDefaultComponent(networks);
        },
        renderMonolithControls: function(components) {
            var monolith = _.filter(components, (component) => !component.isML2Driver());
            return this.renderControls(monolith, true, this.onChange);
        },
        renderML2Controls: function(components) {
            var ml2 = _.filter(components, (component) => !component.isML2Driver());
            return this.renderControls(ml2, false, this.props.onChange);
        },
        render: function() {
            if (!this.props.components) {
                return null;
            }
            var networks = this.props.components.getComponentsByType('network', {sorted: true});
            this.processRestrictions(networks, ['hypervisor']);
            this.processCompatible(this.props.components, networks, ['hypervisor']);
            return (
                <div className='wizard-network-pane'>
                    {this.renderMonolithControls(networks)}
                    <div className='ml2'>
                        {this.renderML2Controls(networks)}
                    </div>
                </div>
            );
        }
    });

    var Storage = React.createClass({
        mixins: [ClusterWizardPanesMixin],
        statics: {
            paneName: 'Storage',
            componentType: 'storage',
            title: i18n('dialog.create_cluster_wizard.storage.title')
        },
        renderSection: function(components, type, onChange) {
            var sectionComponents = _.filter(components, (component) => true || component.get('subtype') == type); // TODO remove true
            _.each(sectionComponents, (s) => s.set({description: (s.get('description') || '').substr(0, 50)})); // TODO - debug stuff
            return this.renderControls(sectionComponents, false, onChange);
        },
        render: function() {
            if (!this.props.components) {
                return null;
            }
            var storages = this.props.components.getComponentsByType('storage', {sorted: true});
            this.processRestrictions(storages, ['hypervisor', 'networks']);
            this.processCompatible(this.props.components, storages, ['hypervisor', 'networks']);
            return (
                <div className='wizard-storage-pane'>
                    <div className='section-left'>
                        <p><big>Block Storage:</big></p>
                        {this.renderSection(storages, 'block', this.props.onChange)}
                    </div>
                    <div className='section-right'>
                        <p><big>Object Storage:</big></p>
                        {this.renderSection(storages, 'object', this.props.onChange)}
                    </div>
                    <div className='clearfix'/>
                    <div className='section-left'>
                        <p><big>Image Storage:</big></p>
                        {this.renderSection(storages, 'image', this.props.onChange)}
                    </div>
                    <div className='section-right'>
                        <p><big>Ephemeral Storage:</big></p>
                        {this.renderSection(storages, 'ephemeral', this.props.onChange)}
                    </div>

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
            this.processRestrictions(additionalServices, ['hypervisor', 'network', 'storage', 'additional_service']);
            this.processCompatible(this.props.components, additionalServices, ['hypervisor', 'network', 'storage', 'additional_service']);

            return (
                <div className='wizard-compute-pane'>
                    {this.renderControls(additionalServices, false, this.props.onChange)}
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
        getListOfTypesToRestore: function(currentIndex, maxIndex) {
            var panesTypes = [];
            _.each(clusterWizardPanes, function(pane, paneIndex) {
                if ((paneIndex <= maxIndex) && (paneIndex > currentIndex) && pane.componentType) {
                    panesTypes.push(pane.componentType);
                }
            }, this);
            return panesTypes;
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
            return _.reject(this.state.panes, 'hidden');
        },
        getActivePane: function() {
            var panes = this.getEnabledPanes();
            return panes[this.state.activePaneIndex];
        },
        prevPane: function() {
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
            this.components = new models.ComponentsCollection([], {releaseId: releaseId});
            this.components.fetch().done(() => {
                this.components.invoke('expandWildcards', this.components);
                this.components.invoke('restoreDefaultValue', this.components);
                this.setState({loading: false});
            });
        },
        onChange: function(name, value) {
            var paneHasErrors = false;
            var maxAvailablePaneIndex = this.state.maxAvailablePaneIndex;
            var pane = this.refs.pane;
            switch (name) {
                case 'name':
                    this.wizard.set('name', value);
                    this.wizard.unset('name_error');
                    break;
                case 'release':
                    this.selectRelease(parseInt(value));
                    break;
                default:
                    maxAvailablePaneIndex = this.state.activePaneIndex;
                    var panesToRestore = this.getListOfTypesToRestore(this.state.activePaneIndex, this.state.maxAvailablePaneIndex);
                    if (panesToRestore.length > 0) {
                        this.components.restoreDefaultValues(panesToRestore);
                    }
                    var component = this.components.findWhere({id: name});
                    component.set({enabled: value});
                    paneHasErrors = _.isFunction(pane.hasErrors) && pane.hasErrors();
                    break;
            }
            this.updateState({paneHasErrors: paneHasErrors, maxAvailablePaneIndex: maxAvailablePaneIndex});
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
