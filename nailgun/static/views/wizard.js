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
        componentDidMount: function() {
            $(this.getDOMNode()).find('input:enabled').first().focus();
        },
        processRestrictions: function(metadata, models) {
            var actions = {},
                warnings = [];

            function processRestrictions(restrictions, key) {
                _.each(restrictions, function(restriction) {
                    var result = utils.evaluateExpression(restriction.condition, models);
                    if (result.value) {
                        actions[key] = actions[key] || {};
                        actions[key][restriction.action] = true;
                        warnings.push(restriction.message);
                    }
                }, this);
            }

            _.map(metadata, function(config, attribute) {
                if (config.restrictions) {
                    processRestrictions(config.restrictions, attribute);
                }
                if (config.type == 'radio') {
                    _.map(config.values, function(value) {
                        if (value.restrictions) {
                            processRestrictions(value.restrictions, attribute + '.' + value.data);
                        }
                    });
                }
            });
            return {actions: actions, warnings: _.uniq(warnings)};
        },
        renderWarnings: function(warnings) {
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
        },
        renderControls: function(paneName, metadata, paneData, actions) {
            var paneControls = _.pairs(metadata);
            paneControls.sort(function(control1, control2) {
                return control1[1].weight - control2[1].weight;
            });
            return _.map(paneControls, function(value) {
                var [key, meta] = value;
                switch (meta.type) {
                    case 'radio':
                        return _.map(meta.values, function(value) {
                            var optionKey = key + '.' + value.data;
                            if (actions[optionKey] && actions[optionKey].hide) {
                                return null;
                            }
                            return (
                                <controls.Input
                                    key={optionKey}
                                    name={key}
                                    type='radio'
                                    value={value.data}
                                    checked={value.data == paneData[key]}
                                    label={i18n(value.label)}
                                    description={value.description && i18n(value.description)}
                                    onChange={_.partial(this.props.onChange, paneName)}
                                    disabled={actions[optionKey] && actions[optionKey].disable}
                                />
                            );
                        }, this);
                    case 'checkbox':
                        if (actions[key] && actions[key].hide) {
                            return null;
                        }
                        return (
                            <controls.Input
                                key={key}
                                name={key}
                                type='checkbox'
                                value={paneData[key]}
                                checked={paneData[key]}
                                label={i18n(meta.label)}
                                description={meta.description && i18n(meta.description)}
                                onChange={_.partial(this.props.onChange, paneName)}
                                disabled={actions[key] && actions[key].disable}
                            />
                        );
                    default:
                        if (actions[key] && actions[key].hide) {
                            return null;
                        }
                        return (<div key={key}>{meta.type} control type isn't supported in wizard</div>);
                }
            }, this);
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
            var result = this.processRestrictions(this.props.wizard.config.Compute, this.props.configModels);
            return (
                <div className='wizard-compute-pane'>
                    {this.renderWarnings(result.warnings)}
                    {this.renderControls('Compute', this.props.wizard.config.Compute,
                        this.props.wizard.get('Compute'), result.actions)}
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
        render: function() {
            var result = this.processRestrictions(this.props.wizard.config.Network, this.props.configModels);
            return (
                <div className='wizard-network-pane'>
                    {this.renderWarnings(result.warnings)}
                    {_.contains(app.version.get('feature_groups'), 'mirantis') &&
                        <div className='network-pane-description'>
                            {i18n('dialog.create_cluster_wizard.network.description')}
                            <a href={utils.composeDocumentationLink('planning-guide.html#choose-network-topology')}
                                target='_blank'>
                                {i18n('dialog.create_cluster_wizard.network.description_link')}
                            </a>
                        </div>
                    }
                    {this.renderControls('Network', this.props.wizard.config.Network,
                        this.props.wizard.get('Network'), result.actions)
                    }
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
            var result = this.processRestrictions(this.props.wizard.config.Storage, this.props.configModels);
            return (
                <div>
                    <h5>{i18n('dialog.create_cluster_wizard.storage.ceph_description')}</h5>
                    {this.renderWarnings(result.warnings)}
                    {this.renderControls('Storage', this.props.wizard.config.Storage,
                        this.props.wizard.get('Storage'), result.actions)}
                    <p className='modal-parameter-description ceph'>{i18n('dialog.create_cluster_wizard.storage.ceph_help')}</p>
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
            var result = this.processRestrictions(this.props.wizard.config.AdditionalServices, this.props.configModels);
            return (
                <div className='wizard-additional-pane'>
                    {this.renderWarnings(result.warnings)}
                    {this.renderControls('AdditionalServices', this.props.wizard.config.AdditionalServices,
                        this.props.wizard.get('AdditionalServices'), result.actions)}
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
            this.config = {
                NameAndRelease: {
                    name: {
                        type: 'custom',
                        value: '',
                        bind: 'cluster:name'
                    },
                    release: {
                        type: 'custom',
                        bind: {id: 'cluster:release'},
                        aliases: {
                            operating_system: 'NameAndRelease.release_operating_system',
                            roles: 'NameAndRelease.release_roles',
                            name: 'NameAndRelease.release_name'
                        }
                    }
                }
            };
            this.stopHandlingKeys = false;
            this.wizard = new models.WizardModel(this.config);
            this.cluster = new models.Cluster();
            this.settings = new models.Settings();
            this.releases = this.wizard.releases || new models.Releases();

            this.wizard.processConfig(this.config);

            this.configModels = _.pick(this, 'settings', 'cluster', 'wizard');
            this.configModels.default = this.wizard;
        },
        componentDidMount: function() {
            this.releases.fetch().done(_.bind(function() {
                var defaultRelease = this.releases.findWhere({is_deployable: true});
                this.wizard.set('NameAndRelease.release', defaultRelease.id);
                this.selectRelease(defaultRelease.id);
                this.processRestrictions();
                this.processTrackedAttributes();
                this.setState({loading: false});
            }, this));

            this.updateState({activePaneIndex: 0});
        },
        processRestrictions: function() {
            var restrictions = this.restrictions = {};
            function processControlRestrictions(config, paneName, attribute) {
                var expandedRestrictions = config.restrictions = _.map(config.restrictions, utils.expandRestriction);
                restrictions[paneName][attribute] =
                    _.uniq(_.union(restrictions[paneName][attribute], expandedRestrictions), 'message');
            }
            _.each(this.wizard.config, function(paneConfig, paneName) {
                restrictions[paneName] = {};
                _.each(paneConfig, function(attributeConfig, attribute) {
                    if (attributeConfig.type == 'radio') {
                        _.each(attributeConfig.values, function(attributeValueConfig) {
                            processControlRestrictions(attributeValueConfig, paneName, attribute);
                        }, this);
                    } else {
                        processControlRestrictions(attributeConfig, paneName, attribute);
                    }
                }, this);
            }, this);
            this.wizard.restrictions = this.restrictions;
        },
        processTrackedAttributes: function() {
            this.trackedAttributes = {};
            _.each(this.restrictions, function(paneConfig) {
                _.each(paneConfig, function(paneRestrictions) {
                    _.each(paneRestrictions, function(restriction) {
                        var evaluatedExpression = utils.evaluateExpression(restriction.condition, this.configModels, {strict: false});
                        _.each(evaluatedExpression.modelPaths, function(val, attr) {
                            this.trackedAttributes[attr] = this.trackedAttributes[attr] || 0;
                            ++this.trackedAttributes[attr];
                        }, this);
                    }, this);
                }, this);
            }, this);
        },
        handleTrackedAttributeChange: function() {
            var currentIndex = this.state.activePaneIndex;

            var listOfPanesToRestoreDefaults = this.getListOfPanesToRestore(currentIndex, clusterWizardPanes.length - 1);
            this.wizard.restoreDefaultValues(listOfPanesToRestoreDefaults);
            this.updateState({maxAvailablePaneIndex: currentIndex});
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
            this.processBinds('wizard', this.getActivePane().paneName);
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
            this.processBinds('wizard', this.getActivePane().paneName);
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
            this.processBinds('wizard', this.getActivePane().paneName);
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
            this.processBinds('cluster');
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
            this.updateConfig(release.attributes.wizard_metadata);
        },
        updateConfig: function(config) {
            var name = this.wizard.get('NameAndRelease.name');
            var release = this.wizard.get('NameAndRelease.release');
            this.wizard.config = _.cloneDeep(this.config);
            _.extend(this.wizard.config, _.cloneDeep(config));
            this.wizard.off(null, null, this);
            this.wizard.initialize(this.wizard.config);
            this.wizard.processConfig(this.wizard.config);
            this.wizard.translationParams = this.buildTranslationParams();
            this.wizard.set({
                'NameAndRelease.name': name,
                'NameAndRelease.release': release
            });
            this.updateState({
                activePaneIndex: 0,
                maxAvailablePaneIndex: 0
            });
        },
        buildTranslationParams: function() {
            var result = {};
            _.each(this.wizard.attributes, function(paneConfig, paneName) {
                _.each(paneConfig, function(value, attribute) {
                    if (!_.isObject(value)) {
                        var attributeConfig = this.wizard.config[paneName][attribute];
                        if (attributeConfig && attributeConfig.type == 'radio') {
                            result[paneName + '.' + attribute] = i18n(_.find(attributeConfig.values, {data: value}).label);
                        } else if (attributeConfig && attributeConfig.label) {
                            result[paneName + '.' + attribute] = i18n(attributeConfig.label);
                        } else {
                            result[paneName + '.' + attribute] = value;
                        }
                    }
                }, this);
            }, this);
            return result;
        },
        processBinds: function(prefix, paneNameToProcess) {
            var processBind = _.bind(function(path, value) {
                if (path.slice(0, prefix.length) == prefix) {
                    utils.parseModelPath(path, this.configModels).set(value);
                }
            }, this);
            _.each(this.wizard.config, function(paneConfig, paneName) {
                if (paneNameToProcess && paneNameToProcess != paneName) {
                    return;
                }
                _.each(paneConfig, function(attributeConfig, attribute) {
                    var bind = attributeConfig.bind;
                    var value = this.wizard.get(paneName + '.' + attribute);
                    if (_.isString(bind)) {
                        // simple binding declaration - just copy the value.
                        processBind(bind, value);
                    } else if (_.isPlainObject(bind)) {
                        // binding declaration for models
                        processBind(_.values(bind)[0], value.get(_.keys(bind)[0]));
                    } else if (_.isArray(bind)) {
                        // for the case of multiple bindings
                        if (attributeConfig.type != 'checkbox' || value) {
                            _.each(bind, function(bindItem) {
                                if (!_.isPlainObject(bindItem)) {
                                    processBind(bindItem, value);
                                } else {
                                    processBind(_.keys(bindItem)[0], _.values(bindItem)[0]);
                                }
                            }, this);
                        }
                    }
                    if (attributeConfig.type == 'radio') {
                        // radiobuttons can have values with their own bindings
                        _.each(_.find(attributeConfig.values, {data: value}).bind, function(bind) {
                            processBind(_.keys(bind)[0], _.values(bind)[0]);
                        });
                    }
                }, this);
            }, this);
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
                                wizard={this.wizard}
                                releases={this.releases}
                                settings={this.settings}
                                configModels={this.configModels}
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
