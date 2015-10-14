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
        'utils',
        'models',
        'jsx!component_mixins',
        'jsx!views/dialogs'
    ],
    function(require, $, _, i18n, React, utils, models, componentMixins /*, dialogs */) {
        'use strict';

        var clusterWizardPanes = [];

        var CommonControl = React.createClass({
            render: function() {
                return (
                    <div className={this.props.classes}>
                        <label className='parameter-box clearfix col-xs-12' disabled={this.props.disabled}>
                            <div className='parameter-control col-xs-1'>
                                <div className='custom-tumbler'>
                                    <input type={this.props.type} name={this.props.name} checked={this.props.checked}
                                        value={this.props.value} onChange={this.props.onChange} disabled={this.props.disabled}/>
                                    <span>&nbsp;</span>
                                </div>
                            </div>
                            <div className='parameter-name col-xs-0'>{this.props.label}</div>
                        </label>
                        {
                            this.props.hasDescription &&
                            <div className='modal-parameter-description col-xs-offset-1'>
                                {this.props.description}
                            </div>
                        }
                    </div>
                );
            }
        });

        var CreateCluster = React.createClass({
            mixins: [
                componentMixins.backboneMixin('releases'),
                componentMixins.backboneMixin('wizard')
            ],
            getActivePane: function() {
                var pane = this.props.panes[this.props.activePaneIndex];
                return pane || {};
            },
            render: function() {
                var activeIndex = this.props.activePaneIndex,
                    nextStyle = this.props.nextVisible ? {display: 'inline-block'} : {display: 'none'},
                    createStyle = this.props.createVisible ? {display: 'inline-block'} : {display: 'none'};
                return (
                    <div className='modal fade create-cluster-modal'>
                        <div id='wizard' className='modal-dialog'>
                            <div className='modal-content'>
                                <div className='modal-header'>
                                    <button type='button' className='close' aria-label='Close'
                                            data-dismiss='modal'>
                                        <span aria-hidden='true'>×</span>
                                    </button>
                                    <h4 className='modal-title'>{i18n('dialog.create_cluster_wizard.title')}</h4>
                                </div>
                                <div className='modal-body wizard-body'>
                                    <div className='wizard-steps-box'>
                                        <div className='wizard-steps-nav col-xs-3'>
                                            <ul className='wizard-step-nav-item nav nav-pills nav-stacked'>
                                                {
                                                    this.props.panes.map(function(pane, i) {
                                                        var classes = utils.classNames('wizard-step', {
                                                            disabled: i > this.props.maxAvailablePaneIndex,
                                                            available: i <= this.props.maxAvailablePaneIndex,
                                                            active: i == activeIndex
                                                        });
                                                        return (
                                                            <li key={pane.title} role='wizard-step'
                                                                className={classes}>
                                                                <a onClick={_.bind(function() {this.props.goToPane(i);}, this)}>{pane.title}</a>
                                                            </li>
                                                        );
                                                    }, this)
                                                }
                                            </ul>
                                        </div>
                                        <div className='pane-content col-xs-9'>
                                            {
                                                React.createElement(this.getActivePane().view, this.props)
                                            }
                                        </div>
                                        <div className='clearfix'></div>
                                    </div>
                                </div>

                                <div className='modal-footer wizard-footer'>
                                    <button className='btn btn-default pull-left' data-dismiss='modal'>
                                        {i18n('common.cancel_button')}
                                    </button>
                                    <button
                                        className={utils.classNames('btn btn-default prev-pane-btn', {disabled: !this.props.previousEnabled})}
                                        onClick={this.props.prevPane}>
                                        <span className='glyphicon glyphicon-arrow-left' aria-hidden='true'></span>
                                        <span>{i18n('dialog.create_cluster_wizard.prev')}</span>
                                    </button>
                                    <button className={utils.classNames('btn btn-default btn-success next-pane-btn', {disabled: !this.props.nextEnabled})}
                                            style={nextStyle}
                                            onClick={this.props.nextPane}>
                                        <span>{i18n('dialog.create_cluster_wizard.next')}</span>
                                        <span className='glyphicon glyphicon-arrow-right'
                                            aria-hidden='true'></span>
                                    </button>
                                    <button className='btn btn-default btn-success finish-btn'
                                            style={createStyle}>
                                        {i18n('dialog.create_cluster_wizard.create')}
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                );
            }
        });

        var ClusterWizardPanesMixin = {
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
                return _.map(warnings, function(warning) {
                    return (
                        <div className='alert alert-warning'>
                            {i18n(warning, this.props.wizard.translationParams)}
                        </div>
                    );
                }, this);
            },
            renderControls: function(paneName, metadata, data, actions) {
                return _.map(metadata, function(meta, key) {
                    switch (meta.type) {
                        case 'radio':
                            return _.map(meta.values, function(value) {
                                var optionKey = key + '.' + value.data;
                                if (actions[optionKey] && actions[optionKey].hide) {
                                    return null;
                                }
                                return (
                                    <CommonControl
                                        name={key}
                                        type='radio'
                                        value={value.data}
                                        checked={value.data == data[key]}
                                        label={i18n(value.label)}
                                        description={_.isString(value.description) && i18n(value.description)}
                                        hasDescription={_.isString(value.description)}
                                        onChange={_.bind(function(event) {this.props.onChange(paneName, key, event)}, this)}
                                        disabled={actions[optionKey] && actions[optionKey].disable}
                                        />
                                );
                            }, this);
                        case 'checkbox':
                            if (actions[key] && actions[key].hide) {
                                return null;
                            }
                            return (
                                <CommonControl
                                    name={key}
                                    type='checkbox'
                                    value={data[key]}
                                    checked={data[key]}
                                    label={i18n(meta.label)}
                                    description={_.isString(meta.description) && i18n(meta.description)}
                                    hasDescription={_.isString(meta.description)}
                                    onChange={_.bind(function(event) {this.props.onChange(paneName, key, event)}, this)}
                                    disabled={actions[key] && actions[key].disable}
                                    />
                            );
                        default:
                            return <div>Unknown Control type {meta.type}</div>
                    }
                }, this);
            }
        };

        var NameRelease = React.createClass({
            componentWillMount: function() {
                this.needAutofocus = true;
            },
            componentDidUpdate: function() {
                _.delay(_.bind(function() {
                    if (this.needAutofocus && this.refs.autofocus) {
                        this.refs.autofocus.getDOMNode().focus();
                        this.needAutofocus = false;
                    }
                }, this), 300);
            },
            render: function() {
                if (!this.props.releases || !this.props.wizard) {
                    return null;
                }
                var releases = this.props.releases;
                var nameAndRelease = this.props.wizard.get('NameAndRelease');
                return (
                    <form className='form-horizontal create-cluster-form'
                        onSubmit={function() {return false;}}
                        autoComplete='off'>
                        <fieldset>
                            <div className={utils.classNames('form-group', {'has-error': !!nameAndRelease.name_error})}>
                                <label
                                    className='control-label col-xs-3'>{i18n('dialog.create_cluster_wizard.name_release.name')}</label>
                                <div className='controls col-xs-9'>
                                    <input type='text' className='form-control' name='name' maxLength='50'
                                        ref='autofocus' value={nameAndRelease.name}
                                        autoFocus={true} onChange={_.bind(function(val) {this.props.onChange('NameAndRelease', 'name', val)}, this)}/>
                                    <span className='help-block danger'>{nameAndRelease.name_error}</span>
                                </div>
                            </div>
                            <div className='form-group'>
                                <label
                                    className='control-label col-xs-3'>{i18n('dialog.create_cluster_wizard.name_release.release_label')}</label>

                                <div className='controls col-xs-9 has-warning'>
                                    <select className='form-control' name='release' value={nameAndRelease.id}
                                            onChange={_.bind(function(val) {this.props.onChange('NameAndRelease', 'release', val)}, this)}>
                                        {
                                            releases.map(function(release) {
                                                if (!release.get('is_deployable')) {
                                                    return null;
                                                }
                                                return <option value={release.get('id')}>{release.get('name')}</option>
                                            })
                                        }
                                    </select>
                                    {
                                        this.props.connectivityAlert && <div
                                        className='alert alert-warning alert-nailed'>{this.props.connectivityAlert}</div>
                                    }
                                    <div className='release-description'>{this.props.releaseDescription}</div>
                                </div>
                            </div>
                        </fieldset>
                    </form>
                );
            }
        });
        clusterWizardPanes.push({view: NameRelease, name: 'NameAndRelease', title: i18n('dialog.create_cluster_wizard.name_release.title')
        });

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
                            </div>
                            <div className='ceph col-xs-12'>
                                <p className='modal-parameter-description col-xs-12'>{i18n('dialog.create_cluster_wizard.storage.ceph_help')}</p>
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
                        <span>{i18n('dialog.create_cluster_wizard.ready.console')}</span>
                    </p>

                );
            }
        });
        clusterWizardPanes.push({view: Finish, name: 'Finish', title: i18n('dialog.create_cluster_wizard.ready.title')});

        var CreateClusterWizard = React.createClass({
            statics: {
                show: function(options) {
                    return utils.universalMount(this, options, $('#modal-container'));
                }
            },
            getInitialState: function() {
                return {
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

                var $el = $(this.getDOMNode());
                $el.on('hidden.bs.modal', this.handleHidden);
                $el.on('shown.bs.modal', function() {
                    $el.find('[autofocus]:first').focus();
                });
                $el.modal(_.defaults(
                    {keyboard: false},
                    _.pick(this.props, ['background', 'backdrop']),
                    {background: true, backdrop: true}
                ));

                this.updateState({});
            },
            componentWillUnmount: function() {
                //Backbone.history.off(null, null, this);
                $(this.getDOMNode()).off('shown.bs.modal hidden.bs.modal');
                //this.rejectResult();
            },
            handleHidden: function() {
                React.unmountComponentAtNode(this.getDOMNode().parentNode);
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
                var nextActivePaneIndex = _.isNumber(nextState.activePaneIndex) ? nextState.activePaneIndex : this.state.activePaneIndex;

                var newState = _.merge(nextState, {
                    activePaneIndex: nextActivePaneIndex,
                    previousEnabled: nextActivePaneIndex > 0,
                    nextEnabled: !this.state.paneHasErrors,
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
            prevPane: function() {
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
            selectRelease: function(releaseId) {
                var release = this.releases.findWhere({id: releaseId});
                this.wizard.set('NameAndRelease.release', releaseId);
                this.updateConfig(release.attributes.wizard_metadata);
            },
            updateConfig: function(config) {
                var name = this.wizard.get('NameAndRelease.name');
                var release = this.wizard.get('NameAndRelease.release');
                this.wizard.config = _.cloneDeep(this.config);
                _.extend(this.wizard.config, _.cloneDeep(config));
                this.wizard.off(null, null, this);
                //this.wizard.processPaneRestrictions();
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
            applyBinds: function(paneName, field, bindValue) {
                if (bindValue == false) {
                    return;
                }
                var pane = this.wizard.config[paneName];
                var binds = pane && pane[field] && pane[field].bind;
                binds = _.isString(binds) ? [binds] : binds;
                if (!_.isArray(binds)) {
                    return;
                }
                _.each(binds, function(bind) {
                    var path, value;
                    if (_.isObject(bind)) {
                        path = _.first(_.keys(bind));
                        value = bind[path];
                    } else {
                        path = bind;
                        value = bindValue;
                    }
                    var model, key;
                    var pathParts = path.split(':');
                    if (pathParts.length == 1) {
                        model = this.configModels.default;
                        key = pathParts[0];
                    } else {
                        model = this.configModels[pathParts[0]];
                        key = pathParts[1]
                    }
                    var attribute = {};
                    attribute[key] = value;
                    model.set(attribute);
                }, this);
            },
            onChange: function(paneName, field, event) {
                var value = event.target.type == 'checkbox' ? event.target.checked : event.target.value;
                if (paneName == 'NameAndRelease') {
                    if (field == 'name') {
                        this.wizard.set('NameAndRelease.name', value);
                        this.wizard.unset('NameAndRelease.name_error');
                    } else if (field == 'release') {
                        this.selectRelease(parseInt(value));
                    }
                }
                var path = paneName + '.' + field;
                this.wizard.set(path, value);
                if (this.trackedAttributes[path]) {
                    this.handleTrackedAttributeChange();
                }
                this.applyBinds(paneName, field, value);
                this.updateState({paneHasErrors: false});
            },
            render: function() {
                return (
                    <CreateCluster
                        {...this.state}
                        onChange={this.onChange}
                        nextPane={this.nextPane}
                        prevPane={this.prevPane}
                        goToPane={this.goToPane}
                    />
                );
            }
        });

        return {
            CreateClusterWizard: CreateClusterWizard
        };
    });
