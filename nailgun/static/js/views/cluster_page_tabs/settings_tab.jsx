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
    'react',
    'utils',
    'models',
    'expression',
    'jsx!views/controls'
],
function(React, utils, models, Expression, controls) {
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
            return this.checkRestrictions('disable', path) || !!this.checkDependentRoles(path).length || !!this.checkDependentSettings(path).length;
        },
        checkDependentRoles: function(path) {
            var setting = this.settings.get(path);
            if (_.contains(['text', 'password', 'hidden'], setting.type)) return false;
            var roles = this.props.model.get('release').get('roles');
            return _.compact(_.map(this.allocatedRoles, function(roleName) {
                var role = roles.findWhere({name: roleName});
                if (_.any(role.expandedRestrictions, function(restriction) {
                    return _.contains(restriction.condition, 'settings:' + path) && !Expression.prototype.compile(restriction.condition).evaluate(this.configModels);
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
                if (this.checkRestrictions('hide', groupName + '.metadata')) return;
                _.each(group, function(setting, settingName) {
                    if (_.contains(['text', 'password', 'hidden'], setting.type) || groupName + '.' + settingName == path || this.checkRestrictions('hide', groupName + '.' + settingName)) return;
                    var value = settingName == 'metadata' ? 'enabled' : 'value',
                        restrictions,
                        dependentRestrictions;
                    // we support dependecies on checkboxes and toggleable setting groups
                    if (setting[value] == true) {
                        dependentRestrictions = getDependentRestrictions(groupName + '.' + settingName);
                        if (dependentRestrictions.length) {
                            restrictions = dependentSettings[setting.label] || [];
                            dependentSettings[setting.label] = _.union(restrictions, dependentRestrictions);
                        }
                    } else {
                        // and dropdowns and radio groups
                        var activeOption = _.find(setting.values, {data: setting.value});
                        if (activeOption) {
                            dependentRestrictions = getDependentRestrictions(groupName + '.' + settingName + '.' + value.data);
                            if (dependentRestrictions.length) {
                                restrictions = dependentSettings[setting.label] || [];
                                dependentSettings[setting.label] = _.union(restrictions, dependentRestrictions);
                            }
                        }
                    }
                }, this);
            }, this);
            // evaluate dependencies
            if (!_.isEmpty(dependentSettings)) {
                var valueAttr = _.isUndefined(currentSetting.value) ? 'enabled' : 'value',
                    currentValue = currentSetting[valueAttr],
                    values = _.without(_.pluck(currentSetting.values, 'data'), currentValue) || [!currentValue],
                    settingsForTests = {settings: new models.Settings(_.cloneDeep(this.settings.attributes))};
                return _.compact(_.map(dependentSettings, function(conditions, label) {
                    return _.any(conditions, function(condition) {
                        return _.all(values, function(value) {
                            settingsForTests.settings.get(path)[valueAttr || 'value'] = value;
                            return Expression.prototype.compile(condition).evaluate(settingsForTests);
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
            React.BackboneMixin('model', 'change:status'),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.model.get('settings');
            }}),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.model.get('tasks');
            }}),
            React.BackboneMixin({modelOrCollection: function(props) {
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
                this.updateInitialSettings();
                this.settings.isValid({models: this.configModels});
                this.setState({loading: false});
            }, this));
        },
        componentWillUnmount: function() {
            this.loadInitialSettings();
        },
        hasChanges: function() {
            return !_.isEqual(this.settings.attributes, this.initialAttributes);
        },
        applyChanges: function() {
            var deferred = this.settings.save(null, {patch: true, wait: true, validate: false});
            if (deferred) {
                this.setState({actionInProgress: true});
                deferred
                    .done(this.updateInitialSettings)
                    .always(_.bind(function() {
                        this.setState({actionInProgress: false});
                        this.props.model.fetch();
                    }, this))
                    .fail(function() {
                        utils.showErrorDialog({
                            title: $.t('cluster_page.settings_tab.settings_error.title'),
                            message: $.t('cluster_page.settings_tab.settings_error.saving_warning')
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
                            title: $.t('cluster_page.settings_tab.settings_error.title'),
                            message: $.t('cluster_page.settings_tab.settings_error.load_defaults_warning')
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
        updateInitialSettings: function() {
            this.initialAttributes = _.cloneDeep(this.settings.attributes);
        },
        onChange: function(groupName, settingName, value) {
            this.settings.set(groupName + '.' + settingName + '.' + (settingName == 'metadata' ? 'enabled' : 'value'), value);
            this.settings.isValid({models: this.configModels});
        },
        render: function() {
            var cluster = this.props.model,
                sortedSettingGroups = _.sortBy(_.keys(this.settings.attributes), function(groupName) {
                    return this.settings.get(groupName + '.metadata.weight');
                }, this),
                locked = this.state.actionInProgress || !!cluster.task({group: 'deployment', status: 'running'}) || !cluster.isAvailableForSettingsChanges();
            return (
                <div className={React.addons.classSet({'openstack-settings wrapper': true, 'changes-locked': locked})}>
                    <h3>{$.t('cluster_page.settings_tab.title')}</h3>
                    {this.state.loading ?
                        <controls.ProgressBar />
                        :
                        <div>
                            {_.map(sortedSettingGroups, function(groupName) {
                                var path = groupName + '.metadata';
                                if (!this.checkRestrictions('hide', path)) {
                                    return this.transferPropsTo(
                                        <SettingGroup
                                            key={groupName}
                                            groupName={groupName}
                                            onChange={_.bind(this.onChange, this, groupName)}
                                            disabled={locked || (!!this.settings.get(path).toggleable && this.processRestrictions(path))}
                                        />
                                    );
                                }
                            }, this)}
                            <div className='row'>
                                <div className='page-control-box'>
                                    <div className='page-control-button-placeholder'>
                                        <button key='loadDefaults' className='btn btn-load-defaults' onClick={this.loadDefaults} disabled={locked}>
                                            {$.t('common.load_defaults_button')}
                                        </button>
                                        <button key='cancelChanges' className='btn btn-revert-changes' onClick={this.revertChanges} disabled={locked || !this.hasChanges()}>
                                            {$.t('common.cancel_changes_button')}
                                        </button>
                                        <button key='applyChanges' className='btn btn-success btn-apply-changes' onClick={this.applyChanges} disabled={locked || !this.hasChanges() || this.settings.validationError}>
                                            {$.t('common.save_settings_button')}
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
        render: function() {
            var group = this.settings.get(this.props.groupName),
                metadata = group.metadata,
                sortedSettings = _.sortBy(_.without(_.keys(group), 'metadata'), function(settingName) {return group[settingName].weight; });
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
                                onChange={this.props.onChange}
                            />
                            :
                            metadata.label || this.props.groupName
                        }
                    </legend>
                    <div className='settings-group table-wrapper'>
                        {_.map(sortedSettings, function(settingName) {
                            var setting = group[settingName],
                                path = this.props.groupName + '.' + settingName;
                            if (!this.checkRestrictions('hide', path)) {
                                var error = _.find(this.settings.validationError, {field: this.props.groupName + '.' + settingName});
                                if (setting.values) {
                                    var values = _.compact(_.map(_.cloneDeep(setting.values), function(value) {
                                        if (!this.checkRestrictions('hide', path + '.' + value.data)) {
                                            value.disabled = this.props.disabled || (metadata.toggleable && !metadata.enabled) || this.processRestrictions(path) || this.checkRestrictions('disable', path + '.' + value.data);
                                            value.checked = value.data == setting.value;
                                            return value;
                                        }
                                    }, this));
                                    return this.transferPropsTo(
                                        <controls.RadioGroup
                                            key={settingName}
                                            name={settingName}
                                            label={setting.label}
                                            values={values}
                                            error={error ? error.message : null}
                                        />
                                    );
                                }
                                return this.transferPropsTo(
                                    <controls.Input
                                        key={settingName}
                                        type={setting.type}
                                        name={settingName}
                                        value={setting.value}
                                        checked={_.isBoolean(setting.value) ? setting.value : false}
                                        label={setting.label}
                                        description={setting.description}
                                        toggleable={setting.type == 'password'}
                                        error={error ? error.message : null}
                                        disabled={this.props.disabled || (metadata.toggleable && !metadata.enabled) || this.processRestrictions(path)}
                                    />
                                );
                            }
                        }, this)}
                    </div>
                </div>
            );
        }
    });

    return SettingsTab;
});
