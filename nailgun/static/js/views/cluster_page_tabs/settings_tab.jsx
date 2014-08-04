/*
 * Copyright 2013 Mirantis, Inc.
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
    'view_mixins',
    'views/common',
    'views/dialogs'
],
function(React, utils, models, viewMixins, commonViews, dialogViews) {
    'use strict';

    var SettingsTab = React.createClass({
        mixins: [
            React.BackboneMixin('cluster'),
            React.BackboneMixin('settings'),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.cluster.get('tasks');
            }})
        ],
        getInitialState: function() {
            return {initialSettings: new models.Settings()};
        },
        componentWillMount: function() {
            this.props.settings.on('invalid', _.bind(this.forceUpdate, this, undefined));
            $.when(this.props.settings.fetch({cache: true}), this.props.cluster.get('networkConfiguration').fetch({cache: true})).done(function() {
                this.updateInitialSettings();
                this.setState(configModels: {
                    cluster: this.props.cluster,
                    settings: this.props.settings,
                    networking_parameters: this.props.cluster.get('networkConfiguration').get('networking_parameters'),
                    version: app.version,
                    default: this.props.settings
                });
            });
        },
        componentWillUnmount: function() {
            this.loadInitialSettings();
        },
        hasChanges: function() {
            return !_.isEqual(this.props.settings.attributes, this.initialSettings.attributes);
        },
        isLocked: function() {
            return !!this.props.cluster.task({group: 'deployment', status: 'running'}) || !this.props.cluster.isAvailableForSettingsChanges();
        },
        applyChanges: function() {
            this.$('.btn, input, select').attr('disabled', true);
            return this.props.settings.save(null, {patch: true, wait: true})
                .done(this.updateInitialSettings)
                .always(_.bind(this.props.cluster.fetch, this.props.cluster)
                .fail(function() {
                    utils.showErrorDialog({
                        title: $.t('cluster_page.settings_tab.settings_error.title'),
                        message: $.t('cluster_page.settings_tab.settings_error.saving_warning')
                    });
                };
        },
        loadDefaults: function() {
            this.$('.btn, input, select').attr('disabled', true);
            this.props.settings.fetch({url: _.result(this.props.settings, 'url') + '/defaults'})
                .fail(function() {
                    utils.showErrorDialog({
                        title: $.t('cluster_page.settings_tab.settings_error.title'),
                        message: $.t('cluster_page.settings_tab.settings_error.load_defaults_warning')
                    });
                });
        },
        revertChanges: function() {
            this.loadInitialSettings();
        },
        loadInitialSettings: function() {
            this.props.settings.set(_.cloneDeep(this.initialSettings.attributes));
        },
        updateInitialSettings: function() {
            this.initialSettings.set(_.cloneDeep(this.props.settings.attributes));
        },
        getValueAttribute: function(settingName) {
            return settingName == 'metadata' ? 'enabled' : 'value';
        },
        checkDependentSettings: function(groupName, settingName) {
            var unsupportedTypes = ['text', 'password'];
            var settingPath = groupName + '.' + settingName;
            var processedSetting = this.props.settings.get(settingPath);
            var valueAttribute = this.getValueAttribute(settingName);
            var notToggleableGroup = settingName == 'metadata' && !processedSetting.toggleable;
            if (notToggleableGroup || _.contains(unsupportedTypes, this.props.settings.get(settingPath).type)) {
                return false;
            }
            var isDependent = function(restriction) {
                return restriction.action == 'disable' && _.contains(restriction.condition, 'settings:' + settingPath);
            };
            // collect restrictions to check
            var restrictions = [];
            _.each(this.props.settings.attributes, function(group, groupName) {
                // FIXME(ja): invisible dependent settings and options should not be checked also
                if (this.checkRestrictions(group.metadata, 'hide')) { return; }
                _.each(group, function(setting, settingName) {
                    if (_.contains(unsupportedTypes, setting.type) || groupName + '.' + settingName == settingPath) { return; }
                    if (setting[this.getValueAttribute(settingName)] == true) { // for checkboxes and toggleable setting groups
                        restrictions.push(_.find(setting.restrictions, isDependent));
                    } else {
                        var activeOption = _.find(setting.values, {data: setting.value}); // for dropdowns and radio groups
                        if (activeOption) {
                            restrictions.push(_.find(activeOption.restrictions, isDependent));
                        }
                    }
                }, this);
            }, this);
            restrictions = _.compact(restrictions);
            if (restrictions.length) {
                var processedValues = _.without(_.pluck(processedSetting.values, 'data'), processedSetting[valueAttribute]) || [!processedSetting[valueAttribute]];
                var configModels = _.extend({}, this.configModels, {settings: new models.Settings(this.props.settings.toJSON().editable)});
                return _.any(restrictions, function(restriction) {
                    var suitableValues = _.filter(processedValues, function(value) {
                        configModels.settings.get(settingPath)[valueAttribute] = value;
                        return !utils.evaluateExpression(restriction.condition, configModels).value;
                    });
                    return !suitableValues.length;
                });
            }
            return false;
        },
        calculateSettingState: function(groupName, settingName) {
            var settingPath = groupName + '.' + settingName;
            var setting = this.props.settings.get(settingPath);
            this.props.settings.set(settingPath + '.disabled', setting.hasDependentRole || this.checkRestrictions(setting, 'disable') || this.checkDependentSettings(groupName, settingName));
            this.props.settings.set(settingPath + '.visible', !this.checkRestrictions(setting, 'hide'));
            _.each(setting.values, function(value, index) {
                var values = _.cloneDeep(setting.values);
                values[index].disabled = this.checkRestrictions(values[index], 'disable');
                values[index].visible = !this.checkRestrictions(values[index], 'hide');
                this.props.settings.set(settingPath + '.values', values);
            }, this);
        },
        checkDependentRoles: function(groupName, settingName) {
            var settingPath = groupName + '.' + settingName;
            var rolesData = this.props.cluster.get('release').get('roles_metadata');
            this.props.settings.get(settingPath).hasDependentRole = _.any(this.props.cluster.get('release').get('roles'), function(role) {
                var roleDependencies = _.map(rolesData[role].depends, utils.expandRestriction);
                var hasSatisfiedDependencies = _.any(roleDependencies, function(dependency) {
                    var evaluatedDependency = utils.evaluateExpression(dependency.condition, this.configModels);
                    return _.contains(dependency.condition, 'settings:' + settingPath) && evaluatedDependency.value;
                }, this);
                var assignedNodes = this.props.cluster.get('nodes').filter(function(node) { return node.hasRole(role); });
                return hasSatisfiedDependencies && assignedNodes.length;
            }, this);
        },
        render: function() {
            var settings = this.props.settings;
            var sortedSettingGroups = _.sortBy(_.keys(settings.attributes), function(groupName) {
                return settings.get(groupName + '.metadata.weight');
            });
            return (
                <div className='openstack-settings wrapper'>
                    <h3>{$.t('cluster_page.settings_tab.title')}</h3>
                    {this.state.loading ? 
                        <div className='progress-bar'>
                            <div className='progress progress-striped progress-success active'><div className='bar'></div></div>
                        </div>
                        :
                        _.map(sortedSettingGroups, function(groupName) {
                            return <SettingGroup
                                settings={settings}
                                groupName={groupName}
                                locked={this.isLocked()}
                                configModels={this.state.configModels}
                                errors={settings.validationError}
                                roles={this.props.cluster.get('release').get('roles')}
                                roleData={this.props.cluster.get('release').get('roles_metadata')}
                                nodes={this.props.cluster.get('nodes')} />
                        });
                    }
                    <div class='row'>
                        <div class='page-control-box'>
                            <div class='page-control-button-placeholder'>
                                <button className='btn' onclick={this.loadDefaults} {this.isLocked() && 'disabled'}>{$.t('common.load_defaults_button')}</button>
                                <button className='btn' onclick={this.revertChanges} {!this.hasChanges() && 'disabled'}>{$.t('common.cancel_changes_button')}</button>
                                <button className='btn' onclick={this.applyChanges} {(!this.hasChanges() || settings.validationError) && 'disabled'}>{$.t('common.save_settings_button')}</button>
                            </div>
                        </div>
                    </div>
                </div>
            );
        }
    });

    var SettingGroup = React.createClass({
        mixins: [
            React.addons.LinkedStateMixin
        ],
        getInitialState: function() {
            return {
                disabled: this.props.locked || this.isDisabled(),
                visible: this.isVisible()
            };
        },
        isDisabled: function() {
            return this.checkDependentRoles() || this.checkRestrictions('disable') || this.checkDependentSettings();
        },
        isVisible: function() {
            return !this.checkRestrictions('hide');
        },
        checkDependentRoles: function() {
            return _.any(this.props.roles, function(role) {
                var roleDependencies = _.map(this.props.roleData[role].depends, utils.expandRestriction);
                var hasSatisfiedDependencies = _.any(roleDependencies, function(dependency) {
                    var evaluatedDependency = utils.evaluateExpression(dependency.condition, this.props.configModels);
                    return _.contains(dependency.condition, 'settings:' + this.groupName + '.metadata') && evaluatedDependency.value;
                }, this);
                var assignedNodes = this.props.nodes.filter(function(node) { return node.hasRole(role); });
                return hasSatisfiedDependencies && assignedNodes.length;
            }, this);
        },
        checkRestrictions: function(action, setting) {
            setting = setting || this.props.settings.get(groupName + '.metadata');
            var restrictions = _.map(setting.restrictions, utils.expandRestriction);
            return _.any(_.where(restrictions, {action: action}), function(restriction) {
                return utils.evaluateExpression(restriction.condition, this.configModels).value;
            }, this);
        },
        checkDependentSettings: function(groupName, settingName) {
            var settingPath = groupName + '.metadata';
            if (!this.props.settings.get(settingPath + '.toggleable')) { return false; }
            var isDependent = function(restriction) {
                return restriction.action == 'disable' && _.contains(utils.expandRestriction(restriction).condition, 'settings:' + settingPath);
            };
            var getValueAttribute = function(settingName) {
                return settingName == 'metadata' ? 'enabled' : 'value';
            },
            var restrictions = [];
            _.each(this.props.settings.attributes, function(group, groupName) {
                // FIXME(ja): invisible dependent settings and options should not be checked also
                if (this.checkRestrictions('hide', group.metadata)) { return; }
                _.each(group, function(setting, settingName) {
                    if (_.contains(['text', 'password'], setting.type) || groupName + '.' + settingName == settingPath) { return; }
                    if (setting[getValueAttribute(settingName)] == true) { // for checkboxes and toggleable setting groups
                        restrictions.push(_.find(setting.restrictions, isDependent));
                    } else {
                        var activeOption = _.find(setting.values, {data: setting.value}); // for dropdowns and radio groups
                        if (activeOption) {
                            restrictions.push(_.find(activeOption.restrictions, isDependent));
                        }
                    }
                }, this);
            }, this);
            restrictions = _.compact(restrictions);
            if (restrictions.length) {
                var configModels = _.extend({}, this.configModels, {settings: new models.Settings(_.cloneDeep(this.props.settings.attributes))});
                configModels.settings.set(settingPath + '.enabled', !this.props.settings.get(settingPath + '.enabled');
                return _.any(restrictions, function(restriction) {
                    return utils.evaluateExpression(utils.expandRestriction(restriction).condition, configModels).value;
                });
            }
            return false;
        },
        handleSettingGroup: function(e) {
            this.props.settings.set({this.props.groupName + '.metadata.enabled': e.target.value}, {validate: true});
        },
        render: function() {
            var settings = this.props.settings.get(groupName),
                metadata = settings.metadata,
                groupName = this.props.groupName;
            var sortedSettingNames = _.without(_.sortBy(_.keys(settings), function(setting) { return settings[setting].weight; }), 'metadata');
            return (
                {this.state.visible && 
                    <div className='fieldset-group wrapper'>
                        <legend className='openstack-settings'>
                        {metadata.toggleable ?
                            <label className='toggleable'>
                                <div className='tumbler'>
                                    <div className='parameter-control'>
                                        <div className='custom-tumbler'>
                                            <input type='checkbox' name={groupName + '.enabled'} value={metadata.enabled} {this.state.disabled && 'disabled'} onChange={this.handleSettingGroup} />
                                            <span>&nbsp;</span>
                                        </div>
                                    </div>
                                </div>
                                {metadata.label || groupName}
                            </label>
                            :
                            {metadata.label || groupName}
                        }
                        </legend>
                        <div className='settings-group table-wrapper'>
                            {_.map(sortedSettingNames, function(settingName) {
                                return <Setting
                                    settings={this.props.settings}
                                    settingPath={groupName + '.' + settingName}
                                    groupDisabled={this.state.disabled}
                                    locked={this.props.locked}
                                    configModels={this.props.configModels}
                                    errors={this.props.errors} />;
                            })}
                        </div>
                    </div>
                }
            );
        }
    });

    var Setting = React.creaeClass({
        getInitialState: function() {
            disabled: this.props.locked || this.props.groupDisabled || this.isDisabled(),
            visible: this.isVisible()
        },
        onSettingChange: function(e) {
            this.props.settings.set({this.props.settingPath + '.value': e.target.value}, {validate: true});
        },
        isDisabled: function() {

        },
        isVisible: function() {

        },
        render: function() {
            var setting = this.props.setting,
                settingPath = this.props.settingPath;
            var data = {
                settingPath: settingPath,
                setting: setting,
                commonClass: 'tablerow-wrapper setting-container',
                labelClass: 'openstack-sub-title',
                descriptionClass: 'parameter-description'
                onChange: this.onSettingChange,
                disabled: this.state.disabled
            };
            return (
                {this.state.visible &&
                    {setting.type == 'checkbox' && <Checkbox data={_.extend(data, {})} />}
                    {setting.type == 'dropdown' && <Dropdown data={_.extend(data, {})} />}
                    {setting.type == 'radio' && <Radiogroup
                        data={_.extend(data, {commonClass: 'table-colspan setting-container'})}
                        disabled={this.state.disabled}
                        visible={this.state.visible}
                        configModels={this.props.configModels} />
                    }
                    {_.contains(['text', 'password'], setting.type) && <TextField
                        data={_.extend(data, {commonClass: 'table-colspan setting-container'})}
                        errors={this.props.errors} />
                    }
                }
            );
        }
    });

    var Checkbox = React.createClass({
        render: function() {
            var data = this.props.data,
                setting = data.setting;
            return (
                <div className={data.commonClass}>
                    <label className='parameter-box clearfix'>
                        <div className='parameter-control'>
                            <div className='custom-tumbler'>
                                <input
                                    type='checkbox'
                                    name={setting.name}
                                    value={setting.value}
                                    {data.disabled && 'disabled'}
                                    onChange={data.onChange} />
                                <span>&nbsp;</span>
                            </div>
                        </div>
                        <div className={data.labelClass + ' parameter-name'}>{setting.label}</div>
                        <div className={data.descriptionClass + ' description'}>{setting.description}</div>
                    </label>
                </div>
            );
        }
    });

    var Dropdown = React.createClass({
        render: function() {
            var data = this.props.data,
                setting = data.setting;
            return (
                <div className={data.commonClass + 'parameter-box clearfix'}>
                    <div className={data.labelClass + ' parameter-name'}>{setting.label}</div>
                    <div className='parameter-control'>
                        <select
                            name={setting.name}
                            value={setting.value}
                            {data.disabled && 'disabled'}
                            onChange={data.onChange}
                        >
                            {_.each(setting.values, function(value) {
                                <option value={value.data}>{value.label}</option>
                            })}
                        </select>
                    </div>
                    <div className={data.descriptionClass + ' description'}>{setting.description}</div>
                </div>
            );
        }
    });

    var RadioGroup = React.createClass({
        render: function() {
            var data = this.props.data;
            return (
                <div className={data.commonClass}>
                    <legend className={data.labelClass}>{data.setting.label}</legend>
                    {_.map(data.setting.values, function(value) {
                        return <RadioOption data={data} value={value} settingDisabled={this.props.disabled} settingVisible={this.props.visible} configModels={this.props.configModels} />
                    })}
                </div>
            );
        }
    };

    var RadioOption = React.createClass({
        getInitialState: function() {
            disabled: this.props.locked || this.props.settingDisabled || this.isDisabled(),
            visible: this.props.settingVisible && this.isVisible()
        },
        isDisabled: function() {

        },
        isVisible: function() {

        }
        render: function() {
            var data = this.props.data,
                value = this.props.value;
            return (
                {this.state.visible && 
                    <label className='parameter-box clearfix'>
                        <div className='parameter-control'>
                            <div className='custom-tumbler'>
                                <input
                                    type='radio'
                                    name={data.setting.name}
                                    value={value.data}
                                    {data.disabled && 'disabled'}
                                    onChange={data.onChange} />
                                <span>&nbsp;</span>
                            </div>
                        </div>
                        <div className='parameter-name'>{value.label}</div>
                        <div className={this.props.descriptionClass + ' description'}>{value.description}</div>
                    </label>
                }
            );
        }
    };

    var TextField = React.createClass({
        mixins: [viewMixins.toggleablePassword],
        isInvalid: function() {
            var error = _.findWhere(this.props.errors, {field: this.props.data.settingPath});
            return error ? error.message : false;
        },
        render: function() {
            var data = this.props.data,
                setting = data.setting;
            var error = this.isInvalid();
            return (
                <div className={data.commonClass + 'parameter-box clearfix'}>
                    <div className={data.labelClass + ' parameter-name'}>{setting.label}</div>
                    <div className='parameter-control'>
                        <input
                            className={error && 'error'}
                            type={setting.type} name={setting.name}
                            value={setting.value}
                            {data.disabled && 'disabled'}
                            onChange={data.onChange} />
                    </div>
                    {error ?
                        <div className={this.props.descriptionClass + ' validation-error'}>{error}</div>
                        :
                        <div className={this.props.descriptionClass + ' description'}>{setting.description}</div>
                    }
                </div>
            );
        }
    };

    return SettingsTab;
});
