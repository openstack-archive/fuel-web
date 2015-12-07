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

    var ComponentCheckboxGroup = React.createClass({
        hasEnabledComponents: function() {
            return _.any(this.props.components, (component) => component.get('enabled'));
        },
        render: function() {
            return (
                <div ref={this.props.groupName}>
                    {
                        _.map(this.props.components, (component) => {
                            return (
                                <controls.Input
                                    key={component.id}
                                    type='checkbox'
                                    name={component.id}
                                    label={component.get('label')}
                                    description={component.get('description')}
                                    value={component.id}
                                    checked={component.get('enabled')}
                                    disabled={component.get('disabled')}
                                    tooltipIcon={component.get('tooltipIcon')}
                                    tooltipText={component.get('warnings')}
                                    onChange={this.props.onChange}
                                />
                            );
                        })
                    }
                </div>
            );
        }
    });

    var ComponentRadioGroup = React.createClass({
        getInitialState: function() {
            var activeComponent = _.find(this.props.components, (component) => component.get('enabled'));
            return {
                value: activeComponent && activeComponent.id
            };
        },
        hasEnabledComponents: function() {
            return _.any(this.props.components, (component) => component.get('enabled'));
        },
        onChange: function(name, value) {
            _.each(this.props.components, (component) => {
                this.props.onChange(component.id, component.id == value);
            });
            this.setState({value: value});
        },
        render: function() {
            return (
                <div>
                    {
                        _.map(this.props.components, (component) => {
                            return (
                                <controls.Input
                                    key={component.id}
                                    type='radio'
                                    name={this.props.groupName}
                                    label={component.get('label')}
                                    description={component.get('description')}
                                    value={component.id}
                                    checked={this.state.value == component.id}
                                    disabled={!!component.get('disabled')}
                                    tooltipIcon={component.get('tooltipIcon')}
                                    tooltipText={component.get('warnings')}
                                    onChange={this.onChange}
                                />
                            );
                        })
                    }
                </div>
            );
        }
    });

    var ClusterWizardPanesMixin = {
        componentWillMount: function() {
            if (this.props.allComponents) {
                this.components = this.props.allComponents.getComponentsByType(this.constructor.componentType, {sorted: true});
                this.processRestrictions(this.components);
            }
        },
        componentDidMount: function() {
            $(this.getDOMNode()).find('input:enabled').first().focus();
        },
        areComponentsMutuallyExclusive: function(components) {
            var componentIndex = {};
            _.each(components, (component) => {
                componentIndex[component.id] = component;
            });

            var componentDependencies = {};
            _.each(components, (component) => {
                _.each(component.get('incompatible'), (incompatible) => {
                    var incompatibleComponent = incompatible.component;
                    if (componentIndex[incompatibleComponent.id]) {
                        componentDependencies[component.id] = componentDependencies[component.id] || 0;
                        ++componentDependencies[component.id];
                    }
                });
            });

            return _.keys(componentDependencies).length > 0;
        },
        processRestrictions: function(paneComponents, types, stopList = []) {
            this.processIncompatible(paneComponents, types, stopList);
            this.processRequires(paneComponents, types);
        },
        processCompatible: function(allComponents, paneComponents, types) {
            // all previously enabled components
            // should be compatible with the current component
            _.each(paneComponents, (component) => {
                // index of compatible elements
                var compatibleComponents = {};
                var compatibles = component.get('compatible') || [];
                _.each(compatibles, (compatible) => {
                    compatibleComponents[compatible.component.id] = compatible;
                });
                // skip already disabled
                if (component.get('disabled')) {
                    return;
                }

                // scan all components to find enabled
                // and not present in the index
                var isCompatible = true;
                var warnings = [];
                allComponents.each((testedComponent) => {
                    var type = testedComponent.get('type');
                    if (component.id == testedComponent.id || !_.contains(types, type)) {
                        // ignore self or forward compatibilities
                        return;
                    }
                    if (testedComponent.get('enabled') && !compatibleComponents[testedComponent.id]) {
                        warnings.push(testedComponent.get('label'));
                        isCompatible = false;
                    }
                });
                component.set({
                    isCompatible: isCompatible,
                    warnings: isCompatible ? ' ' : warnings.join(', '),
                    tooltipIcon: (isCompatible ? 'glyphicon-ok-sign' : 'glyphicon-info-sign')
                });
            });
        },
        processIncompatible: function(paneComponents, types, stopList) {
            // disable components that have
            // incompatible components already enabled
            _.each(paneComponents, (component) => {
                var incompatibles = component.get('incompatible') || [];
                var isDisabled = false;
                var warnings = [];
                _.each(incompatibles, (incompatible) => {
                    var type = incompatible.component.get('type'),
                        isInStopList = _.find(stopList, (component) => component.id == incompatible.component.id);
                    if (!_.contains(types, type) || isInStopList) {
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
                var isDisabled = false;
                var warnings = [];
                _.each(requires, (require) => {
                    var type = require.component.get('type');
                    if (!_.contains(types, type)) {
                        // ignore forward requires
                        return;
                    }
                    if (!require.component.get('enabled')) {
                        isDisabled = true;
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
        selectActiveComponent: function(components) {
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
            return !_.any(this.components, (component) => !!component.get('enabled'));
        },
        render: function() {
            this.processRestrictions(this.components, ['hypervisor']);
            return (
                <div className='wizard-compute-pane'>
                    <ComponentCheckboxGroup
                        groupName='hypervisor'
                        components={this.components}
                        onChange={this.props.onChange}
                    />
                </div>
            );
        }
    });

    var Network = React.createClass({
        mixins: [ClusterWizardPanesMixin],
        statics: {
            paneName: 'Network',
            panesForRestrictions: ['hypervisor', 'network'],
            componentType: 'network',
            title: i18n('dialog.create_cluster_wizard.network.title'),
            ml2core: 'network:neutron:core:ml2'
        },
        hasErrors: function() {
            var ml2core = _.find(this.components, (component) => component.id == this.constructor.ml2core);
            if (ml2core.get('enabled')) {
                var ml2 = _.filter(this.components, (component) => component.isML2Driver());
                return !_.any(ml2, (ml2driver) => ml2driver.get('enabled'));
            }
            return false;
        },
        onChangeNetwork: function(name, value) {
            var component = _.find(this.components, (component) => component.id == name);
            if (component.isML2Driver()) {
                this.props.onChange(name, value);
            } else {
                this.onChange(name, value);
                if (component.id != this.constructor.ml2core) {
                    _.each(this.components, (component) => {
                        if (component.isML2Driver()) {
                            component.set({enabled: false});
                        }
                    });
                }
            }
        },
        renderMonolithControls: function() {
            var monolith = _.filter(this.components, (component) => !component.isML2Driver());
            var hasMl2 = _.any(this.components, (component) => component.isML2Driver());
            if (!hasMl2) {
                monolith = _.filter(monolith, (component) => component.id != this.constructor.ml2core);
            }
            return (
                <ComponentRadioGroup
                    groupName='network'
                    components={monolith}
                    onChange={this.props.onChange}
                />
            );
        },
        renderML2Controls: function() {
            var ml2 = _.filter(this.components, (component) => component.isML2Driver());
            return (
                <ComponentCheckboxGroup
                    groupName='ml2'
                    components={ml2}
                    onChange={this.props.onChange}
                />
            );
        },
        render: function() {
            this.processRestrictions(this.components, this.constructor.panesForRestrictions);
            this.processCompatible(this.props.allComponents, this.components, this.constructor.panesForRestrictions);
            this.selectActiveComponent(this.components);
            return (
                <div className='wizard-network-pane'>
                    {this.renderMonolithControls()}
                    <div className='ml2'>
                        {this.renderML2Controls()}
                    </div>
                </div>
            );
        }
    });

    var Storage = React.createClass({
        mixins: [ClusterWizardPanesMixin],
        statics: {
            paneName: 'Storage',
            panesForRestrictions: ['hypervisor', 'network', 'storage'],
            componentType: 'storage',
            title: i18n('dialog.create_cluster_wizard.storage.title')
        },
        renderSection: function(components, type) {
            var sectionComponents = _.filter(components, (component) => component.get('subtype') == type);
            var isRadio = this.areComponentsMutuallyExclusive(sectionComponents);
            this.processRestrictions(sectionComponents, this.constructor.panesForRestrictions, (isRadio ? sectionComponents : []));
            this.processCompatible(this.props.allComponents, sectionComponents, this.constructor.panesForRestrictions);
            return (
                React.createElement((isRadio ? ComponentRadioGroup : ComponentCheckboxGroup), {
                    groupName: type,
                    components: sectionComponents,
                    onChange: this.props.onChange
                })
            );
        },
        render: function() {
            this.processRestrictions(this.components, this.constructor.panesForRestrictions);
            this.processCompatible(this.props.allComponents, this.components, this.constructor.panesForRestrictions);
            return (
                <div className='wizard-storage-pane'>
                    <div className='section-left'>
                        <p><big>Block Storage:</big></p>
                        {this.renderSection(this.components, 'block', this.props.onChange)}
                    </div>
                    <div className='section-right'>
                        <p><big>Object Storage:</big></p>
                        {this.renderSection(this.components, 'object', this.props.onChange)}
                    </div>
                    <div className='clearfix'/>
                    <div className='section-left'>
                        <p><big>Image Storage:</big></p>
                        {this.renderSection(this.components, 'image', this.props.onChange)}
                    </div>
                    <div className='section-right'>
                        <p><big>Ephemeral Storage:</big></p>
                        {this.renderSection(this.components, 'ephemeral', this.props.onChange)}
                    </div>

                </div>
            );
        }
    });

    var AdditionalServices = React.createClass({
        mixins: [ClusterWizardPanesMixin],
        statics: {
            paneName: 'AdditionalServices',
            panesForRestrictions: ['hypervisor', 'network', 'storage', 'additional_service'],
            componentType: 'additional_service',
            title: i18n('dialog.create_cluster_wizard.additional.title')
        },
        render: function() {
            this.processRestrictions(this.components, this.constructor.panesForRestrictions);
            this.processCompatible(this.props.allComponents, this.components, this.constructor.panesForRestrictions);
            return (
                <div className='wizard-compute-pane'>
                    <ComponentCheckboxGroup
                        groupName='additionalComponents'
                        components={this.components}
                        onChange={this.props.onChange}
                    />
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
                        {this.components &&
                            <div className='pane-content col-xs-9 forms-box access'>
                                <Pane
                                    ref='pane'
                                    actionInProgress={this.state.actionInProgress}
                                    loading={this.state.loading}
                                    onChange={this.onChange}
                                    releases={this.releases}
                                    wizard={this.wizard}
                                    allComponents={this.components}
                                />
                            </div>
                        }
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
