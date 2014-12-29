/*
 * Copyright 2014 Mirantis, Inc.
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
    'utils',
    'models',
    'expression',
    'jsx!component_mixins',
    'jsx!views/controls'
],
function($, _, i18n, React, utils, models, Expression, componentMixins, controls) {
    'use strict';

    var dependenciesMixin = {
        componentWillMount: function() {
            var cluster = this.props.model;
            this.settings = cluster.get('settings');
            this.configModels = {
                cluster: cluster,
                settings: this.settings,
                networking_parameters: cluster.get('networkConfiguration').get('networking_parameters'),
                version: app.version,
                default: this.settings
            };
            this.allocatedRoles = _.uniq(_.flatten(_.union(cluster.get('nodes').pluck('roles'), cluster.get('nodes').pluck('pending_roles'))));
        },
        checkRestrictions: function(action, path) {
            return this.settings.checkRestrictions(this.configModels, action, path);
        },
        processRestrictions: function(path) {
            var restrictionsCheck = this.checkRestrictions('disable', path),
                dependentRoles = this.checkDependentRoles(path),
                dependentSettings = this.checkDependentSettings(path),
                messages = [];
            if (restrictionsCheck.message) messages.push(restrictionsCheck.message);
            if (dependentRoles.length) messages.push(i18n('cluster_page.settings_tab.dependent_role_warning', {roles: dependentRoles.join(', '), count: dependentRoles.length}));
            if (dependentSettings.length) messages.push(i18n('cluster_page.settings_tab.dependent_settings_warning', {settings: dependentSettings.join(', '), count: dependentSettings.length}));
            return {
                result: restrictionsCheck.result || !!dependentRoles.length || !!dependentSettings.length,
                message: messages.join(' ')
            };
        },
        checkDependentRoles: function(path) {
            var setting = this.settings.get(path);
            if (_.contains(['text', 'password', 'hidden'], setting.type)) return false;
            var roles = this.props.model.get('release').get('role_models');
            return _.compact(_.map(this.allocatedRoles, function(roleName) {
                var role = roles.findWhere({name: roleName});
                if (_.any(role.expandedRestrictions.restrictions, function(restriction) {
                    return _.contains(restriction.condition, 'settings:' + path) && !(new Expression(restriction.condition, this.configModels).evaluate());
                }, this)) return role.get('label');
            }, this));
        },
        checkDependentSettings: function(path) {
            var currentSetting = this.settings.get(path);
            if (_.contains(['text', 'password', 'hidden'], currentSetting.type)) return [];
            var getDependentRestrictions = _.bind(function(pathToCheck) {
                return _.pluck(_.filter(this.settings.expandedRestrictions[pathToCheck], function(restriction) {
                    return restriction.action == 'disable' && _.contains(restriction.condition, 'settings:' + path);
                }), 'condition');
            }, this);
            // collect dependent settings
            var dependentSettings = {};
            _.each(this.settings.attributes, function(group, groupName) {
                // don't take into account hidden dependent settings
                if (this.checkRestrictions('hide', groupName + '.metadata').result) return;
                _.each(group, function(setting, settingName) {
                    // we support dependecies on checkboxes, toggleable setting groups, dropdowns and radio groups
                    var pathToCheck = this.settings.makePath(groupName, settingName);
                    if (_.contains(['text', 'password', 'hidden'], setting.type) || pathToCheck == path || this.checkRestrictions('hide', pathToCheck).result) return;
                    var value = settingName == 'metadata' ? 'enabled' : 'value',
                        dependentRestrictions;
                    if (setting[value] == true) {
                        dependentRestrictions = getDependentRestrictions(pathToCheck);
                        if (dependentRestrictions.length) {
                            dependentSettings[setting.label] = _.union(dependentSettings[setting.label], dependentRestrictions);
                        }
                    } else {
                        var activeOption = _.find(setting.values, {data: setting.value});
                        if (activeOption) {
                            dependentRestrictions = getDependentRestrictions(this.settings.makePath(pathToCheck, value.data));
                            if (dependentRestrictions.length) {
                                dependentSettings[setting.label] = _.union(dependentSettings[setting.label], dependentRestrictions);
                            }
                        }
                    }
                }, this);
            }, this);
            // evaluate dependencies
            if (!_.isEmpty(dependentSettings)) {
                var valueAttr = _.isUndefined(currentSetting.value) ? 'enabled' : 'value',
                    currentValue = currentSetting[valueAttr],
                    values = currentSetting.values ? _.without(_.pluck(currentSetting.values, 'data'), currentValue) : [!currentValue],
                    settingsForTests = {settings: new models.Settings(_.cloneDeep(this.settings.attributes))};
                return _.compact(_.map(dependentSettings, function(conditions, label) {
                    return _.any(conditions, function(condition) {
                        return _.all(values, function(value) {
                            settingsForTests.settings.get(path)[valueAttr] = value;
                            return (new Expression(condition, settingsForTests).evaluate());
                        });
                    }) ? label : null;
                }));
            }
            return [];
        }
    };

    var SettingsTab = React.createClass({
        mixins: [
            dependenciesMixin,
            componentMixins.backboneMixin('model', 'change:status'),
            componentMixins.backboneMixin({modelOrCollection: function(props) {
                return props.model.get('settings');
            }}),
            componentMixins.backboneMixin({modelOrCollection: function(props) {
                return props.model.get('tasks');
            }}),
            componentMixins.backboneMixin({modelOrCollection: function(props) {
                return props.model.task({group: 'deployment', status: 'running'});
            }})
        ],
        getInitialState: function() {
            return {
                loading: true,
                actionInProgress: false
            };
        },
        componentDidMount: function() {
            var cluster = this.props.model;
            $.when(this.settings.fetch({cache: true}), cluster.get('networkConfiguration').fetch({cache: true})).done(_.bind(function() {
                this.updateInitialAttributes();
                this.setState({loading: false});
            }, this));
        },
        componentWillUpdate: function() {
            this.settings.isValid({models: this.configModels});
        },
        componentWillUnmount: function() {
            this.loadInitialSettings();
        },
        hasChanges: function() {
            return this.state.loading ? false : this.settings.hasChanges(this.initialAttributes, this.configModels);
        },
        applyChanges: function() {
            var deferred = this.settings.save(null, {patch: true, wait: true, validate: false});
            if (deferred) {
                this.setState({actionInProgress: true});
                deferred
                    .done(this.updateInitialAttributes)
                    .always(_.bind(function() {
                        this.setState({actionInProgress: false});
                        this.props.model.fetch();
                    }, this))
                    .fail(function() {
                        utils.showErrorDialog({
                            title: i18n('cluster_page.settings_tab.settings_error.title'),
                            message: i18n('cluster_page.settings_tab.settings_error.saving_warning')
                        });
                    });
            }
            return deferred;
        },
        loadDefaults: function() {
            var deferred = this.settings.fetch({url: _.result(this.settings, 'url') + '/defaults'});
            if (deferred) {
                this.setState({actionInProgress: true});
                deferred
                    .always(_.bind(function() {
                        this.setState({actionInProgress: false});
                    }, this))
                    .fail(function() {
                        utils.showErrorDialog({
                            title: i18n('cluster_page.settings_tab.settings_error.title'),
                            message: i18n('cluster_page.settings_tab.settings_error.load_defaults_warning')
                        });
                    });
            }
        },
        revertChanges: function() {
            this.loadInitialSettings();
        },
        loadInitialSettings: function() {
            this.settings.set(_.cloneDeep(this.initialAttributes));
        },
        updateInitialAttributes: function() {
            this.initialAttributes = _.cloneDeep(this.settings.attributes);
        },
        onChange: function(groupName, settingName, value) {
            this.settings.set(this.settings.makePath(groupName, settingName, settingName == 'metadata' ? 'enabled' : 'value'), value);
        },
        render: function() {
            var cluster = this.props.model,
                sortedSettingGroups = _.sortBy(_.keys(this.settings.attributes), function(groupName) {
                    return this.settings.get(groupName + '.metadata.weight');
                }, this),
                locked = this.state.actionInProgress || !!cluster.task({group: 'deployment', status: 'running'}) || !cluster.isAvailableForSettingsChanges(),
                hasChanges = this.hasChanges();
            return (
                <div className={React.addons.classSet({'openstack-settings wrapper': true, 'changes-locked': locked})}>
                    <h3>{i18n('cluster_page.settings_tab.title')}</h3>
                    {this.state.loading ?
                        <controls.ProgressBar />
                        :
                        <div>
                            {_.map(sortedSettingGroups, function(groupName) {
                                var path = groupName + '.metadata';
                                if (!this.checkRestrictions('hide', path).result) {
                                    var processedRestrictions = this.processRestrictions(path);
                                    return <SettingGroup {...this.props}
                                        key={groupName}
                                        groupName={groupName}
                                        onChange={_.bind(this.onChange, this, groupName)}
                                        disabled={locked || (!!this.settings.get(path).toggleable && processedRestrictions.result)}
                                        message={processedRestrictions.message}
                                    />;
                                }
                            }, this)}
                            <div className='row'>
                                <div className='page-control-box'>
                                    <div className='page-control-button-placeholder'>
                                        <button key='loadDefaults' className='btn btn-load-defaults' onClick={this.loadDefaults} disabled={locked}>
                                            {i18n('common.load_defaults_button')}
                                        </button>
                                        <button key='cancelChanges' className='btn btn-revert-changes' onClick={this.revertChanges} disabled={locked || !hasChanges}>
                                            {i18n('common.cancel_changes_button')}
                                        </button>
                                        <button key='applyChanges' className='btn btn-success btn-apply-changes' onClick={this.applyChanges} disabled={locked || !hasChanges || this.settings.validationError}>
                                            {i18n('common.save_settings_button')}
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    }
                </div>
            );
        }
    });

    var SettingGroup = React.createClass({
        mixins: [dependenciesMixin],
        composeOptions: function(values) {
            return _.map(values, function(value, index) {
                return (
                    <option key={index} value={value.data} disabled={value.disabled}>
                        {value.label}
                    </option>
                );
            });
        },
        render: function() {
            var group = this.settings.get(this.props.groupName),
                metadata = group.metadata,
                sortedSettings = _.chain(_.keys(group))
                    .without('metadata')
                    .sortBy(function(settingName) {return group[settingName].weight;})
                    .value();
            return (
                <div className='fieldset-group wrapper'>
                    <legend className='openstack-settings'>
                        {metadata.toggleable ?
                            <controls.Input
                                type='checkbox'
                                name='metadata'
                                checked={metadata.enabled}
                                label={metadata.label || this.props.groupName}
                                disabled={this.props.disabled}
                                tooltipText={this.props.message}
                                onChange={this.props.onChange}
                            />
                            :
                            metadata.label || this.props.groupName
                        }
                    </legend>
                    <div className='settings-group table-wrapper'>
                        {_.map(sortedSettings, function(settingName) {
                            var setting = group[settingName],
                                path = this.settings.makePath(this.props.groupName, settingName);
                            if (!this.checkRestrictions('hide', path).result) {
                                var error = this.settings.validationError && this.settings.validationError[path],
                                    processedRestrictions = this.processRestrictions(path),
                                    disabled = (metadata.toggleable && !metadata.enabled) || processedRestrictions.result;
                                if (setting.values) {
                                    var values = _.chain(_.cloneDeep(setting.values))
                                        .map(function(value) {
                                            var valuePath = this.settings.makePath(path, value.data),
                                                processedValueRestrictions = this.checkRestrictions('disable', valuePath);
                                            if (!this.checkRestrictions('hide', valuePath).result) {
                                                value.disabled = this.props.disabled || disabled || processedValueRestrictions.result;
                                                value.checked = value.data == setting.value;
                                                value.tooltipText = processedValueRestrictions.message;
                                                return value;
                                            }
                                        }, this)
                                        .compact()
                                        .value();
                                    if (setting.type == 'radio') return <controls.RadioGroup {...this.props}
                                        key={settingName}
                                        name={settingName}
                                        label={setting.label}
                                        values={values}
                                        error={error}
                                        tooltipText={processedRestrictions.message}
                                    />;
                                }
                                return <controls.Input {...this.props}
                                    key={settingName}
                                    type={setting.type}
                                    name={settingName}
                                    children={setting.type == 'select' ? this.composeOptions(setting.values) : null}
                                    value={setting.value}
                                    checked={_.isBoolean(setting.value) ? setting.value : false}
                                    label={setting.label}
                                    description={setting.description}
                                    toggleable={setting.type == 'password'}
                                    error={error}
                                    disabled={this.props.disabled || disabled}
                                    wrapperClassName='tablerow-wrapper'
                                    tooltipText={processedRestrictions.message}
                                />;
                            }
                        }, this)}
                    </div>
                </div>
            );
        }
    });

    return SettingsTab;
});
