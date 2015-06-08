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
    'jsx!views/controls',
    'jsx!views/custom_controls'
],
function($, _, i18n, React, utils, models, Expression, componentMixins, controls, customControls) {
    'use strict';

    var SettingsTab = React.createClass({
        mixins: [
            componentMixins.backboneMixin('cluster', 'change:status'),
            componentMixins.backboneMixin({
                modelOrCollection: function(props) {
                    return props.cluster.get('settings');
                },
                renderOn: 'change invalid'
            }),
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
                    release: this.props.cluster.get('release'),
                    default: settings
                },
                settingsForChecks: new models.Settings(_.cloneDeep(settings.attributes)),
                loading: true,
                actionInProgress: false
            };
        },
        componentDidMount: function() {
            var cluster = this.props.cluster,
                settings = cluster.get('settings');
            $.when(settings.fetch({cache: true}), cluster.get('networkConfiguration').fetch({cache: true})).done(_.bind(function() {
                this.updateInitialAttributes();
                this.getHiddenSettings();
                settings.isValid({models: this.state.configModels});
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
            // collecting data to save
            var settings = this.props.cluster.get('settings'),
                dataToSave = this.props.cluster.isAvailableForSettingsChanges() ? settings.attributes : _.pick(settings.attributes, function(group) {
                    return (group.metadata || {}).always_editable;
                });

            var options = {url: settings.url, patch: true, wait: true, validate: false},
                deferred = new models.Settings(_.cloneDeep(dataToSave)).save(null, options);
            if (deferred) {
                this.setState({actionInProgress: true});
                deferred
                    .done(this.updateInitialAttributes)
                    .always(_.bind(function() {
                        this.setState({
                            actionInProgress: false,
                            key: _.now()
                        });
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
        getHiddenSettings: function() {
            var hidden = {};
            var settings = this.props.cluster.get('settings');
            _.each(settings.attributes, function(group, groupKey) {
                _.each(group, function(field, fieldKey) {
                    if (field && field.type != 'hidden') {
                        return;
                    }
                    var key = settings.makePath(groupKey, fieldKey);
                    hidden[key] = _.clone(field);
                });
            });
            this.hiddenSettings = hidden;
        },
        setHiddenSettings: function() {
            var settings = this.props.cluster.get('settings');
            _.each(this.hiddenSettings, function(value, key) {
                settings.set(key, value, {silent: true});
            });
        },
        loadDefaults: function() {
            var settings = this.props.cluster.get('settings'),
                deferred = settings.fetch({url: _.result(settings, 'url') + '/defaults'});
            if (deferred) {
                this.setState({actionInProgress: true});
                deferred
                    .always(_.bind(function() {
                        this.setHiddenSettings();
                        settings.isValid({models: this.state.configModels});
                        this.setState({
                            actionInProgress: false,
                            key: _.now()
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
            this.setState({key: _.now()});
        },
        loadInitialSettings: function() {
            this.props.cluster.get('settings').set(_.cloneDeep(this.state.initialAttributes)).isValid({models: this.state.configModels});
        },
        updateInitialAttributes: function() {
            this.setState({initialAttributes: _.cloneDeep(this.props.cluster.get('settings').attributes)});
        },
        onChange: function(groupName, settingName, value) {
            var settings = this.props.cluster.get('settings'),
                name = settings.makePath(groupName, settingName, settings.getValueAttribute(settingName));
            this.state.settingsForChecks.set(name, value);
            // FIXME: the following hacks cause we can't pass {validate: true} option to set method
            // this form of validation isn't supported in Backbone DeepModel
            settings.validationError = null;
            settings.set(name, value);
            settings.isValid({models: this.state.configModels});
        },
        render: function() {
            var cluster = this.props.cluster,
                settings = cluster.get('settings'),
                sortedSettingGroups = _.sortBy(_.keys(settings.attributes), function(groupName) {
                    return settings.get(groupName + '.metadata.weight');
                }),
                locked = this.state.actionInProgress || !!cluster.task({group: 'deployment', status: 'running'}),
                lockedCluster = !cluster.isAvailableForSettingsChanges(),
                hasChanges = this.hasChanges(),
                allocatedRoles = _.uniq(_.flatten(_.union(cluster.get('nodes').pluck('roles'), cluster.get('nodes').pluck('pending_roles'))));

            return (
                <div key={this.state.key} className='row'>
                    <div className='title'>{i18n('cluster_page.settings_tab.title')}</div>
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
                                    settingsForChecks={this.state.settingsForChecks}
                                    makePath={settings.makePath}
                                    getValueAttribute={settings.getValueAttribute}
                                    locked={locked}
                                    lockedCluster={lockedCluster}
                                    configModels={this.state.configModels}
                                />;
                            }, this)}
                            <div className='col-xs-12 page-buttons'>
                                <div className='well clearfix'>
                                    <div className='btn-group pull-right'>
                                        <button className='btn btn-default btn-load-defaults' onClick={this.loadDefaults} disabled={locked || lockedCluster}>
                                            {i18n('common.load_defaults_button')}
                                        </button>
                                        <button className='btn btn-default btn-revert-changes' onClick={this.revertChanges} disabled={locked || !hasChanges}>
                                            {i18n('common.cancel_changes_button')}
                                        </button>
                                        <button className='btn btn-success btn-apply-changes' onClick={this.applyChanges} disabled={locked || !hasChanges || settings.validationError}>
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
        processRestrictions: function(groupName, settingName) {
            var result = false,
                path = this.props.makePath(groupName, settingName),
                messages = [];

            var restrictionsCheck = this.checkRestrictions('disable', path),
                dependentRoles = this.checkDependentRoles(groupName, settingName),
                dependentSettings = this.checkDependentSettings(groupName, settingName),
                messagesCheck = this.checkRestrictions('none', path);

            if (restrictionsCheck.message) messages.push(restrictionsCheck.message);
            if (dependentRoles.length) messages.push(i18n('cluster_page.settings_tab.dependent_role_warning', {roles: dependentRoles.join(', '), count: dependentRoles.length}));
            if (dependentSettings.length) messages.push(i18n('cluster_page.settings_tab.dependent_settings_warning', {settings: dependentSettings.join(', '), count: dependentSettings.length}));
            if (messagesCheck.message) messages.push(messagesCheck.message);

            // FIXME: hack for #1442475 to lock images_ceph in env with controllers
            if (settingName == 'images_ceph') {
                if (_.contains(_.flatten(this.props.cluster.get('nodes').pluck('pending_roles')), 'controller')) {
                    result = true;
                    messages.push(i18n('cluster_page.settings_tab.images_ceph_warning'));
                }
            }

            return {
                result: result || restrictionsCheck.result || !!dependentRoles.length || !!dependentSettings.length,
                message: messages.join(' ')
            };
        },
        areCalсulationsPossible: function(setting) {
            return _.contains(['checkbox', 'radio'], setting.type);
        },
        getValuesToCheck: function(setting, valueAttribute) {
            return setting.values ? _.without(_.pluck(setting.values, 'data'), setting[valueAttribute]) : [!setting[valueAttribute]];
        },
        checkValues: function(values, path, currentValue, condition) {
            var result = _.all(values, function(value) {
                this.props.settingsForChecks.set(path, value);
                return new Expression(condition, {settings: this.props.settingsForChecks}).evaluate();
            }, this);
            this.props.settingsForChecks.set(path, currentValue);
            return result;
        },
        checkDependentRoles: function(groupName, settingName) {
            if (!this.props.allocatedRoles.length) return [];
            var path = this.props.makePath(groupName, settingName),
                setting = this.props.settings.get(path);
            if (!this.areCalсulationsPossible(setting)) return [];
            var valueAttribute = this.props.getValueAttribute(settingName),
                valuesToCheck = this.getValuesToCheck(setting, valueAttribute),
                pathToCheck = this.props.makePath(path, valueAttribute),
                roles = this.props.cluster.get('release').get('role_models');
            return _.compact(this.props.allocatedRoles.map(function(roleName) {
                var role = roles.findWhere({name: roleName});
                if (_.any(role.expandedRestrictions.restrictions, function(restriction) {
                    var condition = restriction.condition;
                    if (_.contains(condition, 'settings:' + path) && !(new Expression(condition, this.props.configModels).evaluate())) {
                        return this.checkValues(valuesToCheck, pathToCheck, setting[valueAttribute], condition);
                    }
                    return false;
                }, this)) return role.get('label');
            }, this));
        },
        checkDependentSettings: function(groupName, settingName) {
            var path = this.props.makePath(groupName, settingName),
                currentSetting = this.props.settings.get(path);
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
                if (this.checkRestrictions('hide', this.props.makePath(groupName, 'metadata')).result) return;
                _.each(group, function(setting, settingName) {
                    // we support dependecies on checkboxes, toggleable setting groups, dropdowns and radio groups
                    var pathToCheck = this.props.makePath(groupName, settingName);
                    if (!this.areCalсulationsPossible(setting) || pathToCheck == path || this.checkRestrictions('hide', pathToCheck).result) return;
                    var dependentRestrictions;
                    if (setting[this.props.getValueAttribute(settingName)] == true) {
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
                var valueAttribute = this.props.getValueAttribute(settingName),
                    pathToCheck = this.props.makePath(path, valueAttribute),
                    valuesToCheck = this.getValuesToCheck(currentSetting, valueAttribute),
                    checkValues = _.bind(this.checkValues, this, valuesToCheck, pathToCheck, currentSetting[valueAttribute]);
                return _.compact(_.map(dependentSettings, function(conditions, label) {
                    if (_.any(conditions, checkValues)) return label;
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
        render: function() {
            if (this.checkRestrictions('hide', this.props.makePath(this.props.groupName, 'metadata')).result) return null;
            var group = this.props.settings.get(this.props.groupName),
                metadata = group.metadata,
                sortedSettings = _.chain(_.keys(group))
                    .without('metadata')
                    .sortBy(function(settingName) {return group[settingName].weight;})
                    .value(),
                processedGroupRestrictions = this.processRestrictions(this.props.groupName, 'metadata'),
                isGroupDisabled = this.props.locked || (this.props.lockedCluster && !metadata.always_editable) || (metadata.toggleable && processedGroupRestrictions.result);
            return (
                <div className='col-xs-12 forms-box'>
                    <h3>
                        {metadata.toggleable &&
                            <controls.Input
                                type='checkbox'
                                defaultChecked={metadata.enabled}
                                disabled={isGroupDisabled}
                                tooltipText={processedGroupRestrictions.message}
                                onChange={this.props.onChange}
                                wrapperClassName='pull-left'
                            />
                        }
                        {metadata.label || this.props.groupName}
                    </h3>
                    <div>
                        {_.map(sortedSettings, function(settingName) {
                            var setting = group[settingName];
                            if (setting.type == 'hidden') return null;

                            var path = this.props.makePath(this.props.groupName, settingName);

                            if (!this.checkRestrictions('hide', path).result) {
                                var error = (this.props.settings.validationError || {})[path],
                                    processedSettingRestrictions = this.processRestrictions(this.props.groupName, settingName),
                                    isSettingDisabled = isGroupDisabled || (metadata.toggleable && !metadata.enabled) || processedSettingRestrictions.result;

                                // support of custom controls
                                var CustomControl = customControls[setting.type];
                                if (CustomControl) {
                                    return <CustomControl
                                        {...setting}
                                        {... _.pick(this.props, 'cluster', 'settings', 'configModels')}
                                        key={settingName}
                                        path={path}
                                        error={error}
                                        disabled={isSettingDisabled}
                                        tooltipText={processedSettingRestrictions.message}
                                    />;
                                }

                                if (setting.values) {
                                    var values = _.chain(_.cloneDeep(setting.values))
                                        .map(function(value) {
                                            var valuePath = this.props.makePath(path, value.data),
                                                processedValueRestrictions = this.checkRestrictions('disable', valuePath);
                                            if (!this.checkRestrictions('hide', valuePath).result) {
                                                value.disabled = isSettingDisabled || processedValueRestrictions.result;
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
                                    {... _.pick(setting, 'type', 'label', 'description')}
                                    key={settingName}
                                    name={settingName}
                                    children={setting.type == 'select' ? this.composeOptions(setting.values) : null}
                                    defaultValue={setting.value}
                                    defaultChecked={_.isBoolean(setting.value) ? setting.value : false}
                                    toggleable={setting.type == 'password'}
                                    error={error}
                                    disabled={isSettingDisabled}
                                    tooltipText={processedSettingRestrictions.message}
                                    onChange={this.props.onChange}
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
