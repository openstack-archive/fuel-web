/*
 * Copyright 2015 Mirantis, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the 'License"); you may
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
    'require',
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
function(require, $, _, i18n, React, Backbone, utils, models, componentMixins, dialogs, controls) {
    'use strict';

    var clusterWizardPanes = [];

    var Loading = React.createClass({
        render: function() {
            return null;
        }
    });

    var ClusterWizardPanesMixin = {
        setFocus: function() {
            if (this.isMounted()) {
                $(this.getDOMNode()).find('input:enabled').first().focus();
            }
        },
        componentDidMount: function() {
            this.setFocus();
        },
        componentDidUpdate: function() {
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
        renderControls: function(paneName, metadata, data, actions) {
            var paneControls = _.pairs(metadata);
            paneControls.sort(function(control1, control2) {
                return control1[1].weight - control2[1].weight;
            });
            return _.map(paneControls, function(value) {
                var key = value[0],
                    meta = value[1];
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
                                    checked={value.data == data[key]}
                                    label={i18n(value.label)}
                                    description={_.isString(value.description) && i18n(value.description)}
                                    hasDescription={_.isString(value.description)}
                                    onChange={_.bind(function(name, val) {this.props.onChange(paneName, key, val)}, this)}
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
                                value={data[key]}
                                checked={data[key]}
                                label={i18n(meta.label)}
                                description={_.isString(meta.description) && i18n(meta.description)}
                                hasDescription={_.isString(meta.description)}
                                onChange={_.bind(function(name, val) {this.props.onChange(paneName, key, val)}, this)}
                                disabled={actions[key] && actions[key].disable}
                                />
                        );
                    default:
                        return <div key={key}>Unknown Control type {meta.type}</div>
                }
            }, this);
        }
    };

    var NameRelease = React.createClass({
        mixins: [ClusterWizardPanesMixin],
        render: function() {
            var releases = this.props.releases,
                nameAndRelease = this.props.wizard && this.props.wizard.get('NameAndRelease');
            if (!this.props.releases || !this.props.wizard || !(nameAndRelease.release instanceof Backbone.Model)) {
                return null;
            }
            var os = nameAndRelease.release.get('operating_system'),
                connectivityAlert = i18n('dialog.create_cluster_wizard.name_release.' + os + '_connectivity_alert');
            return (
                <form className='form-horizontal create-cluster-form name-and-release'
                    onSubmit={function() { return false; }}
                    autoComplete='off'>
                    <fieldset>
                        <controls.Input
                            type='text'
                            name='name'
                            label={i18n('dialog.create_cluster_wizard.name_release.name')}
                            value={nameAndRelease.name}
                            error={nameAndRelease.name_error}
                            onChange={_.bind(function(name, val) {this.props.onChange('NameAndRelease', name, val)}, this)}
                        />
                        <controls.Input
                            type='select'
                            name='release'
                            label={i18n('dialog.create_cluster_wizard.name_release.release_label')}
                            value={nameAndRelease.release && nameAndRelease.release.id}
                            onChange={_.bind(function(name, val) {this.props.onChange('NameAndRelease', name, val)}, this)}
                        >
                            {
                                releases.map(function(release) {
                                    if (!release.get('is_deployable')) {
                                        return null;
                                    }
                                    return <option key={release.get('id')} value={release.get('id')}>{release.get('name')}</option>
                                })
                            }
                        </controls.Input>
                        {
                            connectivityAlert &&
                            <div className='alert alert-warning alert-nailed'>{connectivityAlert}</div>
                        }
                        <div className='release-description'>{nameAndRelease.release.get('description')}</div>
                    </fieldset>
                </form>
            );
        }
    });
    clusterWizardPanes.push({view: NameRelease, name: 'NameAndRelease', title: i18n('dialog.create_cluster_wizard.name_release.title')});

    var Compute = React.createClass({
        mixins: [ClusterWizardPanesMixin],
        render: function() {
            var result = this.processRestrictions(this.props.wizard.config.Compute, this.props.configModels),
                actions = result.actions,
                warnings = result.warnings;

            return (
                <form className='form-horizontal wizard-compute-pane'
                    onSubmit={function() {return false;}}>
                    <fieldset>
                        <div className='form-group'>
                            {this.renderWarnings(warnings)}
                            {this.renderControls('Compute', this.props.wizard.config.Compute,
                                this.props.wizard.get('Compute'), actions)}
                        </div>
                    </fieldset>
                </form>
            );
        }
    });
    clusterWizardPanes.push({view: Compute, name: 'Compute', title: i18n('dialog.create_cluster_wizard.compute.title')});

    var Network = React.createClass({
        mixins: [ClusterWizardPanesMixin],
        render: function() {
            var result = this.processRestrictions(this.props.wizard.config.Network, this.props.configModels),
                actions = result.actions,
                warnings = result.warnings;

            return (
                <form className='form-horizontal wizard-network-pane'
                    onSubmit={function() {return false;}}>
                    <fieldset>
                        {
                            false &&
                            <div className='network-pane-description'>
                                {i18n('dialog.create_cluster_wizard.network.description')}
                                <a href={require('utils').composeDocumentationLink('planning-guide.html#choose-network-topology')}
                                    target='_blank'>
                                    {i18n('dialog.create_cluster_wizard.network.description_link')}
                                </a>
                            </div>
                        }
                        {this.renderWarnings(warnings)}
                        <div className='form-group'>
                            {this.renderControls('Network', this.props.wizard.config.Network,
                                this.props.wizard.get('Network'), actions)}
                        </div>
                    </fieldset>
                </form>
            );
        }
    });
    clusterWizardPanes.push({view: Network, name: 'Network', title: i18n('dialog.create_cluster_wizard.network.title')});

    var Storage = React.createClass({
        mixins: [ClusterWizardPanesMixin],
        render: function() {
            var result = this.processRestrictions(this.props.wizard.config.Storage, this.props.configModels),
                actions = result.actions,
                warnings = result.warnings;

            return (
                <form className='form-horizontal' oonSubmit={function() {return false;}}>
                    <fieldset>
                        <h5>{i18n('dialog.create_cluster_wizard.storage.ceph_description')}</h5>
                        <div className='form-group'>
                            {this.renderWarnings(warnings)}
                            {this.renderControls('Storage', this.props.wizard.config.Storage,
                                this.props.wizard.get('Storage'), actions)}
                            <p className='modal-parameter-description ceph'>{i18n('dialog.create_cluster_wizard.storage.ceph_help')}</p>
                        </div>
                    </fieldset>
                </form>
            );
        }
    });
    clusterWizardPanes.push({view: Storage, name: 'Storage', title: i18n('dialog.create_cluster_wizard.storage.title')});

    var AdditionalServices = React.createClass({
        mixins: [ClusterWizardPanesMixin],
        render: function() {
            var result = this.processRestrictions(this.props.wizard.config.AdditionalServices, this.props.configModels),
                actions = result.actions,
                warnings = result.warnings;

            return (
                <form className='form-horizontal wizard-additional-pane'
                    onSubmit={function() {return false;}}>
                    <fieldset>
                        <div className='form-group'>
                            {this.renderWarnings(warnings)}
                            {this.renderControls('AdditionalServices', this.props.wizard.config.AdditionalServices,
                                this.props.wizard.get('AdditionalServices'), actions)}
                        </div>
                    </fieldset>
                </form>
            );
        }
    });
    clusterWizardPanes.push({view: AdditionalServices, name: 'AdditionalServices', title: i18n('dialog.create_cluster_wizard.additional.title')});

    var Finish = React.createClass({
        render: function() {
            return (
                <p>
                    <span>{i18n('dialog.create_cluster_wizard.ready.env_select_deploy')} </span>
                    <b>{i18n('dialog.create_cluster_wizard.ready.deploy')} </b>
                    <span>{i18n('dialog.create_cluster_wizard.ready.or_make_config_choice')} </span>
                    <b>{i18n('dialog.create_cluster_wizard.ready.env')} </b>
                    <span>{i18n('dialog.create_cluster_wizard.ready.gulp ')}</span>
                </p>
            );
        }
    });
    clusterWizardPanes.push({view: Finish, name: 'Finish', title: i18n('dialog.create_cluster_wizard.ready.title')});

    var CreateClusterWizard = React.createClass({
        mixins: [dialogs.dialogMixin],
        statics: {
            showWizard: function(options) {
                options.modalClass = 'wizard';
                return utils.universalMount(this, options, $('#modal-container'));
            }
        },
        getInitialState: function() {
            return {
                title: i18n('dialog.create_cluster_wizard.title'),
                activePaneIndex: 0,
                maxAvailablePaneIndex: 0,
                panes: clusterWizardPanes,
                paneHasErrors: false,
                previousAvailable: true,
                nextAvailable: true,
                createEnabled: false
            }
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

            this.wizard = new models.WizardModel(this.config);
            this.cluster = new models.Cluster();
            this.settings = new models.Settings();
            this.releases = this.wizard.releases || new models.Releases();

            this.wizard.processConfig(this.config);

            this.configModels = _.pick(this, 'settings', 'cluster', 'wizard');
            this.configModels.default = this.wizard;
        },
        componentDidMount: function() {
            //Backbone.history.on('route', this.close, this);

            this.setState(_.pick(this, 'wizard', 'cluster', 'settings', 'releases', 'configModels'), function() {
                this.releases.fetch().done(_.bind(function() {
                    var defaultRelease = this.releases.where({is_deployable: true})[0];
                    this.wizard.set('NameAndRelease.release', defaultRelease.get('id'));
                    this.selectRelease(defaultRelease.id);
                    this.processRestrictions();
                    this.processTrackedAttributes();
                }, this));
            });

            this.updateState({activePaneIndex: 0});
        },
        componentWillUnmount: function() {
            //Backbone.history.off(null, null, this);
        },
        componentDidUpdate: function() {
            if (this.getActivePane().name == 'Finish') {
                $(this.getDOMNode()).find('.finish-btn').focus();
            }
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
                        for (var attr in evaluatedExpression.modelPaths) {
                            this.trackedAttributes[attr] = this.trackedAttributes[attr] || 0;
                            ++this.trackedAttributes[attr];
                        }
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
                    panesNames.push(pane.name);
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
            var res = this.state.panes.filter(function(pane) {
                return !pane.hidden;
            });
            return res;
        },
        getActivePane: function() {
            var panes = this.getEnabledPanes();
            return panes[this.state.activePaneIndex];
        },
        prevPane: function() {
            this.processBinds('wizard', this.getActivePane().name);
            this.updateState({activePaneIndex: --this.state.activePaneIndex});
        },
        nextPane: function() {
            if (this.state.activePaneIndex == 0) {
                var status = this.createCluster();
                if (!status) {
                    this.updateState({paneHasErrors: true});
                    return;
                }
            }
            this.processBinds('wizard', this.getActivePane().name);
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
            this.processBinds('wizard', this.getActivePane().name);
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
            if (this.props.collection.findWhere({name: name})) {
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
            var cluster = this.cluster;
            this.processBinds('cluster');
            var deferred = cluster.save();
            if (deferred) {
                this.updateState({disabled: true});
                deferred
                    .done(_.bind(function() {
                        this.props.collection.add(cluster);
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
                            .fail(_.bind(function() {
                                this.close();
                                utils.showErrorDialog({message: i18n('dialog.create_cluster_wizard.configuration_failed_warning')});
                            }, this));
                    }, this))
                    .fail(_.bind(function(response) {
                        if (response.status == 409) {
                            this.updateState({disabled: false, activePaneIndex: 0});
                            cluster.trigger('invalid', cluster, {name: utils.getResponseText(response)});
                        } else {
                            this.close();
                            utils.showErrorDialog({
                                title: i18n('dialog.create_cluster_wizard.create_cluster_error.title'),
                                message: response.status == 400 ? utils.getResponseText(response) : undefined
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
            if (e.which == 13) {
                e.preventDefault();

                if (this.getActivePane().name == 'Finish') {
                    this.saveCluster();
                } else {
                    this.nextPane();
                }
            }
        },
        renderBody: function() {
            var activeIndex = this.state.activePaneIndex,
                releaseId = this.state.wizard && this.state.wizard.get('NameAndRelease.release.id');
            return (
                <div className='wizard-body'>
                    <div className='wizard-steps-box'>
                        <div className='wizard-steps-nav col-xs-3'>
                            <ul className='wizard-step-nav-item nav nav-pills nav-stacked'>
                                {
                                    this.state.panes.map(function(pane, i) {
                                        var classes = utils.classNames('wizard-step', {
                                            disabled: i > this.state.maxAvailablePaneIndex,
                                            available: i <= this.state.maxAvailablePaneIndex && i != activeIndex,
                                            active: i == activeIndex
                                        });
                                        return (
                                            <li key={pane.title} role='wizard-step'
                                                className={classes}>
                                                <a onClick={_.bind(function() {this.goToPane(i);}, this)}>{pane.title}</a>
                                            </li>
                                        );
                                    }, this)
                                }
                            </ul>
                        </div>
                        <div className='pane-content col-xs-9 forms-box access'>
                            {
                                React.createElement(
                                    _.isNumber(releaseId) ? this.getActivePane().view : Loading,
                                    _.merge({ref: 'pane', onChange: this.onChange}, this.state))
                            }
                        </div>
                        <div className='clearfix'></div>
                    </div>
                </div>
            );
        },
        renderFooter: function() {
            var nextStyle = this.state.nextVisible ? {display: 'inline-block'} : {display: 'none'},
                createStyle = this.state.createVisible ? {display: 'inline-block'} : {display: 'none'};
            return (
                <div className='wizard-footer'>
                    <button className='btn btn-default pull-left' data-dismiss='modal'>
                        {i18n('common.cancel_button')}
                    </button>
                    <button
                        className={utils.classNames('btn btn-default prev-pane-btn', {disabled: !this.state.previousEnabled})}
                        onClick={this.prevPane}>
                        <span className='glyphicon glyphicon-arrow-left' aria-hidden='true'></span>
                        <span>{i18n('dialog.create_cluster_wizard.prev')}</span>
                    </button>
                    <button className={utils.classNames('btn btn-default btn-success next-pane-btn', {disabled: !this.state.nextEnabled})}
                            style={nextStyle}
                            onClick={this.nextPane}>
                        <span>{i18n('dialog.create_cluster_wizard.next')}</span>
                        <span className='glyphicon glyphicon-arrow-right' aria-hidden='true'></span>
                    </button>
                    <button ref='finish' className='btn btn-default btn-success finish-btn'
                            style={createStyle} onClick={this.saveCluster}>
                        {i18n('dialog.create_cluster_wizard.create')}
                    </button>
                </div>
            );
        }
    });

    return {
        CreateClusterWizard: CreateClusterWizard
    };
});
