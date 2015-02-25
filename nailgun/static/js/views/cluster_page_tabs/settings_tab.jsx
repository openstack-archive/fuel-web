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

    var SettingsTab = React.createClass({
        mixins: [
            componentMixins.backboneMixin('cluster', 'change:status'),
            componentMixins.backboneMixin({modelOrCollection: function(props) {
                return props.cluster.get('settings');
            }}),
            componentMixins.backboneMixin({modelOrCollection: function(props) {
                return props.cluster.get('tasks');
            }}),
            componentMixins.backboneMixin({modelOrCollection: function(props) {
                return props.cluster.task({group: 'deployment', status: 'running'});
            }})
        ],
        getInitialState: function() {
            var settings = this.props.cluster.get('settings');
            return {
                configModels: {
                    cluster: this.props.cluster,
                    settings: settings,
                    networking_parameters: this.props.cluster.get('networkConfiguration').get('networking_parameters'),
                    version: app.version,
                    default: settings
                },
                loading: true,
                actionInProgress: false
            };
        },
        componentDidMount: function() {
            var cluster = this.props.cluster;
            $.when(cluster.get('settings').fetch({cache: true}), cluster.get('networkConfiguration').fetch({cache: true})).done(_.bind(function() {
                this.updateInitialAttributes();
                this.setState({loading: false});
            }, this));
        },
        componentWillUnmount: function() {
            this.loadInitialSettings();
        },
        hasChanges: function() {
            return this.state.loading ? false : this.props.cluster.get('settings').hasChanges(this.state.initialAttributes, this.state.configModels);
        },
        applyChanges: function() {
            var deferred = this.props.cluster.get('settings').save(null, {patch: true, wait: true, models: this.state.configModels});
            if (deferred) {
                this.setState({actionInProgress: true});
                deferred
                    .done(this.updateInitialAttributes)
                    .always(_.bind(function() {
                        this.setState({actionInProgress: false});
                        this.props.cluster.fetch();
                    }, this))
                    .fail(function(response) {
                        utils.showErrorDialog({
                            title: i18n('cluster_page.settings_tab.settings_error.title'),
                            message: i18n('cluster_page.settings_tab.settings_error.saving_warning'),
                            response: response
                        });
                    });
            }
            return deferred;
        },
        loadDefaults: function() {
            var settings = this.props.cluster.get('settings'),
                deferred = settings.fetch({url: _.result(settings, 'url') + '/defaults'});
            if (deferred) {
                this.setState({actionInProgress: true});
                deferred
                    .always(_.bind(function() {
                        this.setState({
                            actionInProgress: false,
                            key: Date.now()
                        });
                    }, this))
                    .fail(function(response) {
                        utils.showErrorDialog({
                            title: i18n('cluster_page.settings_tab.settings_error.title'),
                            message: i18n('cluster_page.settings_tab.settings_error.load_defaults_warning'),
                            response: response
                        });
                    });
            }
        },
        revertChanges: function() {
            this.loadInitialSettings();
            this.setState({key: Date.now()});
        },
        loadInitialSettings: function() {
            this.props.cluster.get('settings').set(_.cloneDeep(this.state.initialAttributes));
        },
        updateInitialAttributes: function() {
            this.setState({initialAttributes: _.cloneDeep(this.props.cluster.get('settings').attributes)});
        },
        onChange: function(groupName, settingName, value) {
            var settings = this.props.cluster.get('settings');
            settings.set(settings.makePath(groupName, settingName, settingName == 'metadata' ? 'enabled' : 'value'), value);
            // can't pass {validate: true} option to set method
            // cause this form of validation isn't supported in Backbone DeepModel
            settings.isValid({models: this.state.configModels});
        },
        render: function() {
            var cluster = this.props.cluster,
                settings = cluster.get('settings'),
                sortedSettingGroups = _.sortBy(_.keys(settings.attributes), function(groupName) {
                    return settings.get(groupName + '.metadata.weight');
                }),
                locked = this.state.actionInProgress || !!cluster.task({group: 'deployment', status: 'running'}) || !cluster.isAvailableForSettingsChanges(),
                hasChanges = this.hasChanges(),
                allocatedRoles = _.uniq(_.flatten(_.union(cluster.get('nodes').pluck('roles'), cluster.get('nodes').pluck('pending_roles'))));
            return (
                <div key={this.state.key} className={React.addons.classSet({'openstack-settings wrapper': true, 'changes-locked': locked})}>
                    <h3>{i18n('cluster_page.settings_tab.title')}</h3>
                    {this.state.loading ?
                        <controls.ProgressBar />
                        :
                        <div>
                            {_.map(sortedSettingGroups, function(groupName) {
                                return <SettingGroup
                                    key={groupName}
                                    cluster={this.props.cluster}
                                    groupName={groupName}
                                    onChange={_.bind(this.onChange, this, groupName)}
                                    allocatedRoles={allocatedRoles}
                                    settings={settings}
                                    makePath={settings.makePath}
                                    locked={locked}
                                    configModels={this.state.configModels}
                                />;
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
                                        <button key='applyChanges' className='btn btn-success btn-apply-changes' onClick={this.applyChanges} disabled={locked || !hasChanges || settings.validationError}>
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
        checkRestrictions: function(action, path) {
            return this.props.settings.checkRestrictions(this.props.configModels, action, path);
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
        areCalсulationsPossible: function(setting) {
            return _.contains(['checkbox', 'radio'], setting.type);
        },
        checkDependentRoles: function(path) {
            var setting = this.props.settings.get(path);
            if (!this.areCalсulationsPossible(setting)) return false;
            var roles = this.props.cluster.get('release').get('role_models');
            return _.compact(_.map(this.props.allocatedRoles, function(roleName) {
                var role = roles.findWhere({name: roleName});
                if (_.any(role.expandedRestrictions.restrictions, function(restriction) {
                    return _.contains(restriction.condition, 'settings:' + path) && !(new Expression(restriction.condition, this.props.configModels).evaluate());
                }, this)) return role.get('label');
            }, this));
        },
        checkDependentSettings: function(path) {
            var currentSetting = this.props.settings.get(path);
            if (!this.areCalсulationsPossible(currentSetting)) return [];
            var getDependentRestrictions = _.bind(function(pathToCheck) {
                return _.pluck(_.filter(this.props.settings.expandedRestrictions[pathToCheck], function(restriction) {
                    return restriction.action == 'disable' && _.contains(restriction.condition, 'settings:' + path);
                }), 'condition');
            }, this);
            // collect dependent settings
            var dependentSettings = {};
            _.each(this.props.settings.attributes, function(group, groupName) {
                // don't take into account hidden dependent settings
                if (this.checkRestrictions('hide', groupName + '.metadata').result) return;
                _.each(group, function(setting, settingName) {
                    // we support dependecies on checkboxes, toggleable setting groups, dropdowns and radio groups
                    var pathToCheck = this.props.makePath(groupName, settingName);
                    if (!this.areCalсulationsPossible(setting) || pathToCheck == path || this.checkRestrictions('hide', pathToCheck).result) return;
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
                            dependentRestrictions = getDependentRestrictions(this.props.makePath(pathToCheck, activeOption.data));
                            if (dependentRestrictions.length) {
                                dependentSettings[setting.label] = _.union(dependentSettings[setting.label], dependentRestrictions);
                            }
                        }
                    }
                }, this);
            }, this);
            // evaluate dependencies
            if (!_.isEmpty(dependentSettings)) {
                var valueAttribute = _.isUndefined(currentSetting.value) ? 'enabled' : 'value',
                    currentValue = currentSetting[valueAttribute],
                    values = currentSetting.values ? _.without(_.pluck(currentSetting.values, 'data'), currentValue) : [!currentValue],
                    settingsForTests = {settings: new models.Settings(_.cloneDeep(this.props.settings.attributes))};
                return _.compact(_.map(dependentSettings, function(conditions, label) {
                    return _.any(conditions, function(condition) {
                        return _.all(values, function(value) {
                            settingsForTests.settings.get(path)[valueAttribute] = value;
                            return (new Expression(condition, settingsForTests).evaluate());
                        });
                    }) ? label : null;
                }));
            }
            return [];
        },
        composeOptions: function(values) {
            return _.map(values, function(value, index) {
                return (
                    <option key={index} value={value.data} disabled={value.disabled}>
                        {value.label}
                    </option>
                );
            });
        },
        debouncedOnChange: _.debounce(function(name, value) {
            return this.props.onChange(name, value);
        }, 200, {leading: true}),
        render: function() {
            var path = this.props.groupName + '.metadata';
            if (this.checkRestrictions('hide', path).result) return null;
            var group = this.props.settings.get(this.props.groupName),
                metadata = group.metadata,
                sortedSettings = _.chain(_.keys(group))
                    .without('metadata')
                    .sortBy(function(settingName) {return group[settingName].weight;})
                    .value(),
                processedGroupRestrictions = this.processRestrictions(path),
                isGroupDisabled = this.props.locked || (metadata.toggleable && processedGroupRestrictions.result);
            return (
                <div className='fieldset-group wrapper'>
                    <legend className='openstack-settings'>
                        {metadata.toggleable ?
                            <controls.Input
                                type='checkbox'
                                name='metadata'
                                defaultChecked={metadata.enabled}
                                label={metadata.label || this.props.groupName}
                                disabled={isGroupDisabled}
                                tooltipText={processedGroupRestrictions.message}
                                onChange={this.props.onChange}
                            />
                            :
                            metadata.label || this.props.groupName
                        }
                    </legend>
                    <div className='settings-group table-wrapper'>
                        {_.map(sortedSettings, function(settingName) {
                            var setting = group[settingName],
                                path = this.props.makePath(this.props.groupName, settingName);
                            if (!this.checkRestrictions('hide', path).result) {
                                var error = this.props.settings.validationError && this.props.settings.validationError[path],
                                    processedSettingRestrictions = this.processRestrictions(path),
                                    isSettingDisabled = (metadata.toggleable && !metadata.enabled) || processedSettingRestrictions.result;
                                if (setting.values) {
                                    var values = _.chain(_.cloneDeep(setting.values))
                                        .map(function(value) {
                                            var valuePath = this.props.makePath(path, value.data),
                                                processedValueRestrictions = this.checkRestrictions('disable', valuePath);
                                            if (!this.checkRestrictions('hide', valuePath).result) {
                                                value.disabled = isGroupDisabled || isSettingDisabled || processedValueRestrictions.result;
                                                value.defaultChecked = value.data == setting.value;
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
                                        tooltipText={processedSettingRestrictions.message}
                                    />;
                                }
                                return <controls.Input
                                    key={settingName}
                                    type={setting.type}
                                    name={settingName}
                                    children={setting.type == 'select' ? this.composeOptions(setting.values) : null}
                                    defaultValue={setting.value}
                                    defaultChecked={_.isBoolean(setting.value) ? setting.value : false}
                                    label={setting.label}
                                    description={setting.description}
                                    toggleable={setting.type == 'password'}
                                    error={error}
                                    disabled={isGroupDisabled || isSettingDisabled}
                                    wrapperClassName='tablerow-wrapper'
                                    tooltipText={processedSettingRestrictions.message}
                                    onChange={this.debouncedOnChange}
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
