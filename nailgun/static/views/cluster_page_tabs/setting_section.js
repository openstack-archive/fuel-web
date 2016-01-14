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
import _ from 'underscore';
import i18n from 'i18n';
import utils from 'utils';
import React from 'react';
import Expression from 'expression';
import {Input, RadioGroup} from 'views/controls';
import customControls from 'views/custom_controls';

    var SettingSection = React.createClass({
        processRestrictions(setting, settingName) {
            var result = false,
                restrictionsCheck = this.props.checkRestrictions('disable', setting),
                messagesCheck = this.props.checkRestrictions('none', setting),
                messages = _.compact([restrictionsCheck.message, messagesCheck.message]);

            // FIXME: hack for #1442475 to lock images_ceph in env with controllers
            if (settingName == 'images_ceph') {
                if (_.contains(_.flatten(this.props.cluster.get('nodes').pluck('pending_roles')), 'controller')) {
                    result = true;
                    messages.push(i18n('cluster_page.settings_tab.images_ceph_warning'));
                }
            }

            return {
                result: result || restrictionsCheck.result,
                message: messages.join(' ')
            };
        },
        checkDependencies(sectionName, settingName) {
            var messages = [],
                dependentRoles = this.checkDependentRoles(sectionName, settingName),
                dependentSettings = this.checkDependentSettings(sectionName, settingName);

            if (dependentRoles.length) messages.push(i18n('cluster_page.settings_tab.dependent_role_warning', {roles: dependentRoles.join(', '), count: dependentRoles.length}));
            if (dependentSettings.length) messages.push(i18n('cluster_page.settings_tab.dependent_settings_warning', {settings: dependentSettings.join(', '), count: dependentSettings.length}));

            return {
                result: !!dependentRoles.length || !!dependentSettings.length,
                message: messages.join(' ')
            };
        },
        areCalculationsPossible(setting) {
            return setting.toggleable || _.contains(['checkbox', 'radio'], setting.type);
        },
        getValuesToCheck(setting, valueAttribute) {
            return setting.values ? _.without(_.pluck(setting.values, 'data'), setting[valueAttribute]) : [!setting[valueAttribute]];
        },
        checkValues(values, path, currentValue, restriction) {
            var extraModels = {settings: this.props.settingsForChecks};
            var result = _.all(values, function(value) {
                this.props.settingsForChecks.set(path, value);
                return new Expression(restriction.condition, this.props.configModels, restriction).evaluate(extraModels);
            }, this);
            this.props.settingsForChecks.set(path, currentValue);
            return result;
        },
        checkDependentRoles(sectionName, settingName) {
            if (!this.props.allocatedRoles.length) return [];
            var path = this.props.makePath(sectionName, settingName),
                setting = this.props.settings.get(path);
            if (!this.areCalculationsPossible(setting)) return [];
            var valueAttribute = this.props.getValueAttribute(settingName),
                valuesToCheck = this.getValuesToCheck(setting, valueAttribute),
                pathToCheck = this.props.makePath(path, valueAttribute),
                roles = this.props.cluster.get('roles');
            return _.compact(this.props.allocatedRoles.map(function(roleName) {
                var role = roles.findWhere({name: roleName});
                if (_.any(role.get('restrictions'), (restriction) => {
                    restriction = utils.expandRestriction(restriction);
                    if (_.contains(restriction.condition, 'settings:' + path) && !(new Expression(restriction.condition, this.props.configModels, restriction).evaluate())) {
                        return this.checkValues(valuesToCheck, pathToCheck, setting[valueAttribute], restriction);
                    }
                })) return role.get('label');
            }, this));
        },
        checkDependentSettings(sectionName, settingName) {
            var path = this.props.makePath(sectionName, settingName),
                currentSetting = this.props.settings.get(path);
            if (!this.areCalculationsPossible(currentSetting)) return [];
            var dependentRestrictions = {};
            var addDependentRestrictions = (setting, label) => {
                var result = _.filter(_.map(setting.restrictions, utils.expandRestriction),
                        (restriction) => restriction.action == 'disable' && _.contains(restriction.condition, 'settings:' + path)
                    );
                if (result.length) {
                    dependentRestrictions[label] = result.concat(dependentRestrictions[label] || []);
                }
            };
            // collect dependencies
            _.each(this.props.settings.attributes, function(section, sectionName) {
                // don't take into account hidden dependent settings
                if (this.props.checkRestrictions('hide', section.metadata).result) return;
                _.each(section, function(setting, settingName) {
                    // we support dependecies on checkboxes, toggleable setting groups, dropdowns and radio groups
                    if (!this.areCalculationsPossible(setting) ||
                        this.props.makePath(sectionName, settingName) == path ||
                        this.props.checkRestrictions('hide', setting).result
                    ) return;
                    if (setting[this.props.getValueAttribute(settingName)] == true) {
                        addDependentRestrictions(setting, setting.label);
                    } else {
                        var activeOption = _.find(setting.values, {data: setting.value});
                        if (activeOption) addDependentRestrictions(activeOption, setting.label);
                    }
                }, this);
            }, this);
            // evaluate dependencies
            if (!_.isEmpty(dependentRestrictions)) {
                var valueAttribute = this.props.getValueAttribute(settingName),
                    pathToCheck = this.props.makePath(path, valueAttribute),
                    valuesToCheck = this.getValuesToCheck(currentSetting, valueAttribute),
                    checkValues = _.partial(this.checkValues, valuesToCheck, pathToCheck, currentSetting[valueAttribute]);
                return _.compact(_.map(dependentRestrictions, (restrictions, label) => {
                    if (_.any(restrictions, checkValues)) return label;
                }));
            }
            return [];
        },
        composeOptions(values) {
            return _.map(values, (value, index) => {
                return (
                    <option key={index} value={value.data} disabled={value.disabled}>
                        {value.label}
                    </option>
                );
            });
        },
        onPluginVersionChange(pluginName, version) {
            var settings = this.props.settings;
            // FIXME: the following hacks cause we can't pass {validate: true} option to set method
            // this form of validation isn't supported in Backbone DeepModel
            settings.validationError = null;
            settings.set(this.props.makePath(pluginName, 'metadata', 'chosen_id'), Number(version));
            settings.mergePluginSettings();
            settings.isValid({models: this.props.configModels});
            this.props.settingsForChecks.set(_.cloneDeep(settings.attributes));
        },
        togglePlugin(pluginName, settingName, enabled) {
            this.props.onChange(settingName, enabled);
            var pluginMetadata = this.props.settings.get(pluginName).metadata;
            if (enabled) {
                // check for editable plugin version
                var chosenVersionData = _.find(pluginMetadata.versions, (version) => version.metadata.plugin_id == pluginMetadata.chosen_id);
                if (this.props.lockedCluster && !chosenVersionData.metadata.always_editable) {
                    var editableVersion = _.find(pluginMetadata.versions, (version) => version.metadata.always_editable).metadata.plugin_id;
                    this.onPluginVersionChange(pluginName, editableVersion);
                }
            } else {
                var initialVersion = this.props.initialAttributes[pluginName].metadata.chosen_id;
                if (pluginMetadata.chosen_id !== initialVersion) this.onPluginVersionChange(pluginName, initialVersion);
            }
        },
        render() {
            var {settings, sectionName} = this.props,
                section = settings.get(sectionName),
                isPlugin = settings.isPlugin(section),
                metadata = section.metadata,
                sortedSettings = _.sortBy(this.props.settingsToDisplay, (settingName) => section[settingName].weight),
                processedGroupRestrictions = this.processRestrictions(metadata),
                processedGroupDependencies = this.checkDependencies(sectionName, 'metadata'),
                isGroupAlwaysEditable = isPlugin ? _.any(metadata.versions, (version) => version.metadata.always_editable) : metadata.always_editable,
                isGroupDisabled = this.props.locked || (this.props.lockedCluster && !isGroupAlwaysEditable) || processedGroupRestrictions.result,
                showSettingGroupWarning = !this.props.lockedCluster || metadata.always_editable,
                groupWarning = _.compact([processedGroupRestrictions.message, processedGroupDependencies.message]).join(' ');

            return (
                <div className={'setting-section setting-section-' + sectionName}>
                    <h3>
                        {metadata.toggleable ?
                            <Input
                                type='checkbox'
                                name='metadata'
                                label={metadata.label || sectionName}
                                defaultChecked={metadata.enabled}
                                disabled={isGroupDisabled || processedGroupDependencies.result}
                                tooltipText={showSettingGroupWarning && groupWarning}
                                onChange={isPlugin ? _.partial(this.togglePlugin, sectionName) : this.props.onChange}
                            />
                        :
                            <span className={'subtab-group-' + sectionName}>{sectionName == 'common' ? i18n('cluster_page.settings_tab.groups.common') : metadata.label || sectionName}</span>
                        }
                    </h3>
                    <div>
                        {isPlugin &&
                            <div className='plugin-versions clearfix'>
                                <RadioGroup
                                    key={metadata.chosen_id}
                                    name={sectionName}
                                    label={i18n('cluster_page.settings_tab.plugin_versions')}
                                    values={_.map(metadata.versions, (version) => {
                                        return {
                                            data: version.metadata.plugin_id,
                                            label: version.metadata.plugin_version,
                                            defaultChecked: version.metadata.plugin_id == metadata.chosen_id,
                                            disabled: this.props.locked || (this.props.lockedCluster && !version.metadata.always_editable) || processedGroupRestrictions.result || (metadata.toggleable && !metadata.enabled)
                                        };
                                    }, this)}
                                    onChange={this.onPluginVersionChange}
                                />
                            </div>
                        }
                        {_.map(sortedSettings, function(settingName) {
                            var setting = section[settingName],
                                settingKey = settingName + (isPlugin ? '-' + metadata.chosen_id : ''),
                                path = this.props.makePath(sectionName, settingName),
                                error = (settings.validationError || {})[path],
                                processedSettingRestrictions = this.processRestrictions(setting, settingName),
                                processedSettingDependencies = this.checkDependencies(sectionName, settingName),
                                isSettingDisabled = isGroupDisabled || (metadata.toggleable && !metadata.enabled) || processedSettingRestrictions.result || processedSettingDependencies.result,
                                showSettingWarning = showSettingGroupWarning && !isGroupDisabled && (!metadata.toggleable || metadata.enabled),
                                settingWarning = _.compact([processedSettingRestrictions.message, processedSettingDependencies.message]).join(' ');

                            // support of custom controls
                            var CustomControl = customControls[setting.type];
                            if (CustomControl) {
                                return <CustomControl
                                    {...setting}
                                    {... _.pick(this.props, 'cluster', 'settings', 'configModels')}
                                    key={settingKey}
                                    path={path}
                                    error={error}
                                    disabled={isSettingDisabled}
                                    tooltipText={showSettingWarning && settingWarning}
                                />;
                            }

                            if (setting.values) {
                                var values = _.chain(_.cloneDeep(setting.values))
                                    .map(function(value) {
                                        var processedValueRestrictions = this.props.checkRestrictions('disable', value);
                                        if (!this.props.checkRestrictions('hide', value).result) {
                                            value.disabled = isSettingDisabled || processedValueRestrictions.result;
                                            value.defaultChecked = value.data == setting.value;
                                            value.tooltipText = showSettingWarning && processedValueRestrictions.message;
                                            return value;
                                        }
                                    }, this)
                                    .compact()
                                    .value();
                                if (setting.type == 'radio') return <RadioGroup {...this.props}
                                    key={settingKey}
                                    name={settingName}
                                    label={setting.label}
                                    values={values}
                                    error={error}
                                    tooltipText={showSettingWarning && settingWarning}
                                />;
                            }

                            var settingDescription = setting.description &&
                                    <span dangerouslySetInnerHTML={{__html: utils.urlify(_.escape(setting.description))}} />;
                            return <Input
                                {... _.pick(setting, 'type', 'label')}
                                key={settingKey}
                                name={settingName}
                                description={settingDescription}
                                children={setting.type == 'select' ? this.composeOptions(setting.values) : null}
                                debounce={setting.type == 'text' || setting.type == 'password' || setting.type == 'textarea'}
                                defaultValue={setting.value}
                                defaultChecked={_.isBoolean(setting.value) ? setting.value : false}
                                toggleable={setting.type == 'password'}
                                error={error}
                                disabled={isSettingDisabled}
                                tooltipText={showSettingWarning && settingWarning}
                                onChange={this.props.onChange}
                            />;
                        }, this)}
                    </div>
                </div>
            );
        }
    });

    export default SettingSection;
