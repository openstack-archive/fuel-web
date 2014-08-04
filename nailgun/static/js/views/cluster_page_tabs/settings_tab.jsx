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
    'jsx!views/controls'
],
function(React, utils, models, controls) {
    'use strict';

    var SettingMixin = {
        checkRestrictions: function(setting, action) {
            var configModels = this.props.configModels || this.configModels;
            var warnings = _.map(setting.restrictions, function(restriction) {
                restriction = utils.expandRestriction(restriction);
                if (restriction.action == action && utils.evaluateExpression(restriction.condition, configModels).value) {
                    return restriction.message;
                };
            }, this);
            return action == 'disable' ? warnings : !!warnings.length;
        },
        checkDependentRoles: function(settingPath) {
            var setting = this.props.model.get('settings').get(settingPath),
                configModels = this.props.configModels || this.configModels;
            if (_.contains(['text', 'password'], setting.type)) { return false; }
            var nodes = this.props.model.get('nodes'),
                allocatedRoles = _.uniq(_.union(nodes.pluck('roles'), nodes.pluck('pending_roles')));
            return _.filter(allocatedRoles, function(role) {
                return _.any(this.props.model.get('release').get('roles_metadata')[role].depends, function(dependency) {
                    var conditions = utils.expandRestriction(dependency).condition.split(' or ');
                    return _.any(conditions, function(condition) {
                        _.contains(condition, 'settings:' + settingPath) && utils.evaluateExpression(condition, configModels).value;
                    }, this);
                }, this);
            }, this);
        },
        isDependent: function(settingPath, restriction) {
            restriction = utils.expandRestriction(restriction);
            return restriction.action == 'disable' && _.contains(restriction.condition, 'settings:' + settingPath);
        },
        pushRestriction: function(settingPath, dependentSettings, setting, label) {
            var dependentRestriction = _.find(setting.restrictions, _.bind(this.isDependent, this, settingPath));
            if (dependentRestriction) {
                var restrictions = dependentSettings[label];
                restrictions = restrictions || [];
                restrictions.push(dependentRestriction.condition);
            }
        },
        checkDependentSettings: function(settingPath, valueAttr) {
            var settings = this.props.model.get('settings'),
                currentSetting = settings.get(settingPath);
            if (_.contains(['text', 'password'], currentSetting.type)) { return false; }
            var dependentSettings = {},
                pushRestriction = _.bind(this.pushRestriction, this, settingPath);
            _.each(settings.attributes, function(group, groupName) {
                if (this.checkRestrictions(group.metadata, 'hide')) { return; }
                _.each(group, function(setting, settingName) {
                    if (_.contains(['text', 'password', 'hidden'], setting.type) || groupName + '.' + settingName == settingPath || this.checkRestrictions(setting, 'hide')) { return; }
                    var value = settingName == 'metadata' ? 'enabled' : 'value';
                    if (setting[value] == true) { // for checkboxes and toggleable setting groups
                        pushRestriction(dependentSettings, setting, setting.label);
                    } else {
                        var activeOption = _.find(setting.values, {data: setting.value}); // for dropdowns and radio groups
                        if (activeOption) {
                            pushRestriction(dependentSettings, activeOption, setting.label);
                        }
                    }
                }, this);
            }, this);
            if (!_.isEmpty(dependentSettings)) {
                var currentValue =  currentSetting[valueAttr || 'value'];
                var values = _.without(_.pluck(currentSetting.values, 'data'), currentValue) || [!currentValue];
                var configModels = this.props.configModels || this.configModels;
                configModels = _.extend({}, configModels, {settings: new models.Settings(_.cloneDeep(settings.attributes))});
                var setting = configModels.settings.get(settingPath);
                return _.compact(_.map(dependentSettings, function(condition, label) {
                    return _.all(values, function(value) {
                        setting[valueAttr || 'value'] = value;
                        return utils.evaluateExpression(restriction.condition, configModels).value;
                    }) ? label : null;
                }));
            }
            return [];
        }
    };

    var SettingsTab = React.createClass({
        mixins: [
            SettingMixin,
            React.BackboneMixin('model'),
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
                locked: this.isLocked()
            };
        },
        componentDidMount: function() {
            var cluster = this.props.model,
                settings = cluster.get('settings');
            settings.on('invalid', _.bind(this.forceUpdate, this, undefined));
            $.when(settings.fetch({cache: true}), cluster.get('networkConfiguration').fetch({cache: true})).done(_.bind(function() {
                this.updateInitialSettings();
                this.configModels = {
                    cluster: cluster,
                    settings: cluster.get('settings'),
                    networking_parameters: cluster.get('networkConfiguration').get('networking_parameters'),
                    version: app.version,
                    default: cluster.get('settings')
                };
                this.setState({loading: false});
            }, this));
        },
        componentWillUnmount: function() {
            this.loadInitialSettings();
        },
        hasChanges: function() {
            return !_.isEqual(this.props.model.get('settings').attributes, this.state.initialAttributes);
        },
        isLocked: function() {
            return !!this.props.model.task({group: 'deployment', status: 'running'}) || !this.props.model.isAvailableForSettingsChanges();
        },
        updateDisabledState: function() {
            this.setState({locked: this.isLocked()});
        },
        applyChanges: function() {
            var deferred = this.props.model.get('settings').save(null, {patch: true, wait: true});
            if (deferred) {
                this.setState({locked: true});
                deferred
                    .done(this.updateInitialSettings)
                    .always(_.bind(function() {
                        this.updateDisabledState();
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
            var settings = this.props.model.get('settings');
            var deferred = settings.fetch({url: _.result(settings, 'url') + '/defaults'});
            if (deferred) {
                this.setState({locked: true});
                deferred
                    .always(this.updateDisabledState)
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
            this.props.model.get('settings').set(_.cloneDeep(this.state.initialAttributes));
        },
        updateInitialSettings: function() {
            this.setState({initialAttributes: _.cloneDeep(this.props.model.get('settings').attributes)});
        },
        render: function() {
            var settings = this.props.model.get('settings'),
                sortedSettingGroups = _.sortBy(_.keys(settings.attributes), function(groupName) {
                    return settings.get(groupName + '.metadata.weight');
                });
            return (
                <div className='openstack-settings wrapper'>
                    <h3>{$.t('cluster_page.settings_tab.title')}</h3>
                    {this.state.loading ?
                        <controls.ProgressBar />
                        :
                        <div>
                            {_.map(sortedSettingGroups, function(groupName) {
                                var path = groupName + '.metadata',
                                    metadata = settings.get(path);
                                if (!this.checkRestrictions(metadata, 'hide')) {
                                    var disabled = this.state.locked;
                                    var warnings = [];
                                    if (!disabled && metadata.toggleable) {
                                        warnings = this.checkRestrictions(metadata, 'disable');
                                        var dependentRoles = this.checkDependentRoles(path);
                                        if (dependentRoles.length) {
                                            warnings.push($.t('cluster_page.settings_tab.dependent_role_warning', {roles: dependentRoles.join(', ')}));
                                        }
                                        var dependentSettings = this.checkDependentSettings(path, 'enabled');
                                        if (dependentSettings.length) {
                                            warnings.push($.t('cluster_page.settings_tab.dependent_settings_warning', {settings: dependentSettings.join(', ')}));
                                        }
                                        disabled = !!warnings.length;
                                    }
                                    return this.transferPropsTo(<SettingGroup
                                        key={groupName}
                                        groupName={groupName}
                                        settings={settings.get(groupName)}
                                        configModels={this.configModels}
                                        locked={this.state.locked}
                                        disabled={disabled}
                                        warnings={warnings} />);
                                }
                            }, this)}
                            <div className='row'>
                                <div className='page-control-box'>
                                    <div className='page-control-button-placeholder'>
                                        <button key='loadDefaults' className='btn' onclick={this.loadDefaults} disabled={this.state.disabled}>{$.t('common.load_defaults_button')}</button>
                                        <button key='cancelChanges' className='btn' onclick={this.revertChanges} disabled={!this.hasChanges()}>{$.t('common.cancel_changes_button')}</button>
                                        <button key='applyChanges' className='btn btn-success' onclick={this.applyChanges} disabled={!this.hasChanges() || settings.validationError}>{$.t('common.save_settings_button')}</button>
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
        mixins: [SettingMixin],
        handleChange: function(valueAttr, groupName, settingName, value) {
            var settingName = valueAttr == 'enabled' ? 'metadata' : settingName,
                path = groupName + '.' + settingName + '.' + valueAttr,
                settings = this.props.model.get('settings');
            settings.set(path, value);
            settings.isValid();
        },
        validate: function(groupName, settingName) {
            var error = _.findWhere(this.props.model.get('settings').validationError, {field: groupName + '.' + settingName});
            return error ? error.message : false;
        },
        render: function() {
            var settings = this.props.settings,
                metadata = settings.metadata;
            var sortedSettings = _.sortBy(_.without(_.keys(settings), 'metadata'), function(settingName) {return settings[settingName].weight; });
            return (
                <div className='fieldset-group wrapper'>
                    <legend className='openstack-settings'>
                        {metadata.toggleable ?
                            <div>
                                <controls.Checkbox
                                    name={this.props.groupName}
                                    initialState={metadata.enabled}
                                    label={metadata.label || this.props.groupName}
                                    disabled={this.props.disabled}
                                    warnings={this.props.warnings}
                                    handleChange={_.bind(this.handleChange, this, 'enabled', this.props.groupName)}
                                    cs={{common: 'toggleable'}} />
                                <controls.TooltipIcon warning={warning} />
                            </div>
                            :
                            metadata.label || this.props.groupName
                        }
                    </legend>
                    <div className='settings-group table-wrapper'>
                        {_.map(sortedSettings, function(settingName) {
                            var setting = settings[settingName];
                            if (setting.type != 'hidden' && !this.checkRestrictions(setting, 'hide')) {
                                var path = this.props.groupName + '.' + settingName;
                                var disabled = this.props.disabled;
                                var warnings = [];
                                if (!this.props.locked) {
                                    warnings = this.checkRestrictions(setting, 'disable');
                                    var dependentRoles = this.checkDependentRoles(path);
                                    if (dependentRoles.length) {
                                        warnings.push($.t('cluster_page.settings_tab.dependent_role_warning', {roles: dependentRoles.join(', ')}));
                                    }
                                    var dependentSettings = this.checkDependentSettings(path);
                                    if (dependentSettings.length) {
                                        warnings.push($.t('cluster_page.settings_tab.dependent_settings_warning', {settings: dependentSettings.join(', ')}));
                                    }
                                    disabled = disabled || !!warnings.length;
                                }
                                var hiddenValues = [],
                                    disabledValues = [],
                                    valueWarnings = {};
                                if (setting.values) {
                                    _.each(setting.values, function(value) {
                                        if (this.checkRestrictions(value, 'hide')) {
                                            hiddenValues.push(value.data);
                                        } else {
                                            valueWarnings[value.data] = this.checkRestrictions(value, 'disable');
                                            if (valueWarnings[value.data].length) {
                                                disabledValues.push(value.data);
                                            }
                                        }
                                    }, this);
                                }
                                return this.transferPropsTo(<Setting
                                    key={settingName}
                                    type={setting.type}
                                    name={settingName}
                                    value={setting.value}
                                    label={setting.label}
                                    description={setting.description}
                                    values={setting.values}
                                    hiddenValues={hiddenValues}
                                    disabledValues={disabledValues}
                                    valueWarnings={valueWarnings}
                                    handleChange={_.bind(this.handleChange, this, 'value', this.props.groupName)}
                                    validate={_.bind(this.validate, this, this.props.groupName)}
                                    locked={this.props.locked}
                                    disabled={disabled}
                                    warnings={warnings} />);
                            }
                        }, this)}
                    </div>
                </div>
            );
        }
    });

    var Setting = React.createClass({
        render: function() {
            var cs = {common: 'tablerow-wrapper', label: 'openstack-sub-title', description: 'parameter-description'},
                extendedCs = _.extend({}, cs, {common: 'table-colspan', description: 'global-description'});
            var input;
            switch (this.props.type) {
                case 'checkbox':
                    input = <controls.Checkbox cs={extendedCs} />;
                    break;
                case 'dropdown':
                    input = <controls.Dropdown cs={cs} />;
                    break;
                case 'radio':
                    input = <controls.RadioGroup cs={extendedCs} />;
                    break;
                case 'text':
                    input = <controls.TextField cs={cs} />;
                    break;
                case 'password':
                    input = <controls.PasswordField cs={cs} />;
                    break;
            }
            return input ? this.transferPropsTo(input) : null;
        }
    });

    return SettingsTab;
});
