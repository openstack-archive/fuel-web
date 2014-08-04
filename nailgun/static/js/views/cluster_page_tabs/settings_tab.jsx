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
    'expression',
    'utils',
    'models',
    'jsx!views/controls'
],
function(React, Expression, utils, models, controls) {
    'use strict';

    var parsedRestrictions = {},
        expandedRestrictions = {},
        roleRestrictions = {};

    var SettingMixin = {
        checkRestrictions: function(path, action) {
            return utils.checkRestrictions(expandedRestrictions[path], parsedRestrictions, {}, action);
        },
        checkDependentRoles: function(path) {
            var setting = this.props.model.get('settings').get(path);
            if (_.contains(['text', 'password'], setting.type)) { return false; }
            var nodes = this.props.model.get('nodes'),
                allocatedRoles = _.uniq(_.flatten(_.union(nodes.pluck('roles'), nodes.pluck('pending_roles'))));
            return _.filter(allocatedRoles, function(role) {
                return _.any(roleRestrictions[role], function(expression) {
                    return _.contains(expression.expressionText, 'settings:' + path) && expression.evaluate();
                });
            });
        },
        getDependentRestrictions: function(path, pathToCheck, action) {
            action = action || 'disable';
            return _.pluck(_.filter(expandedRestrictions[path], function(restriction) {
                return restriction.action == action && _.contains(restriction.condition, 'settings:' + pathToCheck);
            }), 'condition');
        },
        checkDependentSettings: function(path, valueAttr) {
            var settings = this.props.model.get('settings'),
                currentSetting = settings.get(path);
            if (_.contains(['text', 'password'], currentSetting.type)) { return []; }
            var dependentSettings = {};
            _.each(settings.attributes, function(group, groupName) {
                if (this.checkRestrictions(groupName + '.metadata', 'hide').result) { return; }
                _.each(group, function(setting, settingName) {
                    if (_.contains(['text', 'password', 'hidden'], setting.type) || groupName + '.' + settingName == path || this.checkRestrictions(groupName + '.' + settingName, 'hide').result) { return; }
                    var value = settingName == 'metadata' ? 'enabled' : 'value',
                        restrictions;
                    var dependentRestrictions;
                    if (setting[value] == true) { // for checkboxes and toggleable setting groups
                        dependentRestrictions = this.getDependentRestrictions(groupName + '.' + settingName, path);
                        if (dependentRestrictions.length) {
                            restrictions = dependentSettings[setting.label] = dependentSettings[setting.label] || [];
                            dependentSettings[setting.label] = _.union(restrictions, dependentRestrictions);
                        }
                    } else {
                        var activeOption = _.find(setting.values, {data: setting.value}); // for dropdowns and radio groups
                        if (activeOption) {
                            dependentRestrictions = this.getDependentRestrictions(groupName + '.' + settingName + '.' + value.data, path);
                            if (dependentRestrictions.length) {
                                restrictions = dependentSettings[setting.label] = dependentSettings[setting.label] || [];
                                dependentSettings[setting.label] = _.union(restrictions, dependentRestrictions);
                            }
                        }
                    }
                }, this);
            }, this);
            if (!_.isEmpty(dependentSettings)) {
                var currentValue =  currentSetting[valueAttr || 'value'],
                    values = _.without(_.pluck(currentSetting.values, 'data'), currentValue) || [!currentValue],
                    settingsForTests = new models.Settings(_.cloneDeep(settings.attributes));
                return _.compact(_.map(dependentSettings, function(conditions, label) {
                    return _.any(conditions, function(condition) {
                        return _.all(values, function(value) {
                            settingsForTests.get(path)[valueAttr || 'value'] = value;
                            return parsedRestrictions[condition].evaluate(settingsForTests);
                        });
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
                    cluster: this.props.model,
                    settings: settings,
                    networking_parameters: this.props.model.get('networkConfiguration').get('networking_parameters'),
                    version: app.version,
                    default: settings
                };
                if (_.isEmpty(parsedRestrictions)) {
                    this.parseSettingsRestrictions();
                }
                if (_.isEmpty(roleRestrictions)) {
                    this.parseRolesRestrictions();
                }
                this.setState({loading: false});
            }, this));
        },
        parseSettingsRestrictions: function() {
            var settings = this.props.model.get('settings');
            _.each(settings.attributes, function(group, groupName) {
                this.processSettingRestrictions(group.metadata, groupName + '.metadata');
                _.each(group, function(setting, settingName) {
                    this.processSettingRestrictions(setting, groupName + '.' + settingName);
                    _.each(setting.values, function(value, index) {
                        this.processSettingRestrictions(value, groupName + '.' + settingName + '.' + value.data);
                    }, this);
                }, this);
            }, this);
        },
        processSettingRestrictions: function(setting, path) {
            if (setting.restrictions && setting.restrictions.length) {
                expandedRestrictions[path] = _.map(setting.restrictions, utils.expandRestriction);
                _.each(expandedRestrictions[path], function(restriction) {
                    parsedRestrictions[restriction.condition] = new Expression(restriction.condition, this.configModels);
                }, this);
            }
        },
        parseRolesRestrictions: function() {
            _.each(this.props.model.get('release').get('roles_metadata'), function(data, role) {
                roleRestrictions[role] = [];
                _.each(_.map(data.depends, utils.expandRestriction), function(dependency) {
                    roleRestrictions[role].push(new Expression(dependency.condition, this.configModels));
                }, this);
            }, this);
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
            var deferred = this.props.model.get('settings').save(null, {patch: true, wait: true, validate: false});
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
                <div className={'openstack-settings wrapper' + (this.state.locked ? ' changes-locked' : '')}>
                    <h3>{$.t('cluster_page.settings_tab.title')}</h3>
                    {this.state.loading ?
                        <controls.ProgressBar />
                        :
                        <div>
                            {_.map(sortedSettingGroups, function(groupName) {
                                var path = groupName + '.metadata';
                                if (!this.checkRestrictions(path, 'hide').result) {
                                    var disabled = this.state.locked,
                                        warnings = [];
                                    if (!disabled && settings.get(path).toggleable) {
                                        var restrictionsCheck = this.checkRestrictions(path, 'disable');
                                        warnings = restrictionsCheck.warnings;
                                        disabled = restrictionsCheck.disabled;
                                        var dependentRoles = this.checkDependentRoles(path);
                                        if (dependentRoles.length) {
                                            disabled = true;
                                            warnings.push($.t('cluster_page.settings_tab.dependent_role_warning', {roles: dependentRoles.join(', ')}));
                                        }
                                        var dependentSettings = this.checkDependentSettings(path, 'enabled');
                                        if (dependentSettings.length) {
                                            disabled = true;
                                            warnings.push($.t('cluster_page.settings_tab.dependent_settings_warning', {settings: dependentSettings.join(', ')}));
                                        }
                                    }
                                    return this.transferPropsTo(<SettingGroup
                                        key={groupName}
                                        groupName={groupName}
                                        settings={settings.get(groupName)}
                                        configModels={this.configModels}
                                        disabled={disabled}
                                        warnings={warnings} />);
                                }
                            }, this)}
                            <div className='row'>
                                <div className='page-control-box'>
                                    <div className='page-control-button-placeholder'>
                                        <button key='loadDefaults' className='btn btn-load-defaults' onClick={this.loadDefaults} disabled={this.state.locked}>
                                            {$.t('common.load_defaults_button')}
                                        </button>
                                        <button key='cancelChanges' className='btn btn-revert-changes' onClick={this.revertChanges} disabled={this.state.locked || !this.hasChanges()}>
                                            {$.t('common.cancel_changes_button')}
                                        </button>
                                        <button key='applyChanges' className='btn btn-success btn-apply-changes' onClick={this.applyChanges} disabled={this.state.locked || !this.hasChanges() || settings.validationError}>
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
        mixins: [SettingMixin],
        onChange: function(valueAttr, groupName, settingName, value) {
            settingName = valueAttr == 'enabled' ? 'metadata' : settingName;
            var path = groupName + '.' + settingName + '.' + valueAttr,
                settings = this.props.model.get('settings');
            settings.set(path, value);
            settings.isValid({parsedRestrictions: parsedRestrictions, expandedRestrictions: expandedRestrictions});
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
                                    onChange={_.bind(this.onChange, this, 'enabled', this.props.groupName)}
                                    cs={{common: 'toggleable', label: 'openstack-sub-title toggleable'}} />
                            </div>
                            :
                            metadata.label || this.props.groupName
                        }
                    </legend>
                    <div className='settings-group table-wrapper'>
                        {_.map(sortedSettings, function(settingName) {
                            var setting = settings[settingName],
                                path = this.props.groupName + '.' + settingName;
                            if (setting.type != 'hidden' && !this.checkRestrictions(path, 'hide').result) {
                                var disabled = this.props.disabled,
                                    warnings = [];
                                if (!disabled) {
                                    var restrictionsCheck = this.checkRestrictions(path, 'disable');
                                    disabled = disabled || restrictionsCheck.result;
                                    warnings = restrictionsCheck.warnings;
                                    var dependentRoles = this.checkDependentRoles(path);
                                    if (dependentRoles.length) {
                                        disabled = true;
                                        warnings.push($.t('cluster_page.settings_tab.dependent_role_warning', {roles: dependentRoles.join(', ')}));
                                    }
                                    var dependentSettings = this.checkDependentSettings(path);
                                    if (dependentSettings.length) {
                                        disabled = true;
                                        warnings.push($.t('cluster_page.settings_tab.dependent_settings_warning', {settings: dependentSettings.join(', ')}));
                                    }
                                    disabled = disabled || !!warnings.length;
                                }
                                var hiddenValues = [],
                                    disabledValues = [],
                                    valueWarnings = {};
                                if (setting.values) {
                                    _.each(setting.values, function(value) {
                                        if (this.checkRestrictions(path + '.' + value.data, 'hide').result) {
                                            hiddenValues.push(value.data);
                                        } else {
                                            var restrictionsCheck = this.checkRestrictions(path + '.' + value.data, 'disable');
                                            valueWarnings[value.data] = restrictionsCheck.warnings;
                                            if (restrictionsCheck.result) {
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
                                    onChange={_.bind(this.onChange, this, 'value', this.props.groupName)}
                                    validate={_.bind(this.validate, this, this.props.groupName)}
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
            var cs = {common: 'tablerow-wrapper', label: 'parameter-name', description: 'parameter-description'},
                extendedCs = _.extend({}, cs, {common: 'table-colspan', description: 'global-description'});
            var input;
            switch (this.props.type) {
                case 'checkbox':
                    input = <controls.Checkbox cs={_.extend({}, cs, {common: 'table-colspan', description: 'global-description'})} />;
                    break;
                case 'dropdown':
                    input = <controls.Dropdown cs={cs} />;
                    break;
                case 'radio':
                    input = <controls.RadioGroup cs={_.extend({}, cs, {common: 'table-colspan', description: 'global-description', radioGrouplabel: 'openstack-sub-title'})} />;
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
