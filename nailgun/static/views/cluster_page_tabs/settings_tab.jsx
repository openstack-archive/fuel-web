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

    var CSSTransitionGroup = React.addons.CSSTransitionGroup;

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
            }}),
            componentMixins.unsavedChangesMixin
        ],
        statics: {
            fetchData: function(options) {
                return $.when(options.cluster.get('settings').fetch({cache: true}), options.cluster.get('networkConfiguration').fetch({cache: true})).then(function() {
                    return {};
                });
            }
        },
        getInitialState: function() {
            var settings = this.props.cluster.get('settings');
            var activeGroupName = _.min(_.keys(settings.attributes), function(groupName) {
                return settings.get(groupName + '.metadata.weight');
            });
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
                initialAttributes: _.cloneDeep(settings.attributes),
                actionInProgress: false,
                activeGroupName: activeGroupName
            };
        },
        componentDidMount: function() {
            this.getHiddenSettings();
            this.props.cluster.get('settings').isValid({models: this.state.configModels});
        },
        componentWillUnmount: function() {
            this.loadInitialSettings();
        },
        hasChanges: function() {
            return this.props.cluster.get('settings').hasChanges(this.state.initialAttributes, this.state.configModels);
        },
        applyChanges: function() {
            if (!this.isSavingPossible()) return $.Deferred().reject();

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
                    .done(_.bind(function() {
                        this.setState({initialAttributes: _.cloneDeep(settings.attributes)});
                    }, this))
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
        checkRestrictions: function(action, path) {
            var settings = this.props.cluster.get('settings');
            return settings.checkRestrictions(this.state.configModels, action, path);
        },
        onSubtabClick: function(groupName) {
            this.setState({activeGroupName: groupName});
        },
        isSavingPossible: function() {
            var cluster = this.props.cluster,
                settings = cluster.get('settings'),
                locked = this.state.actionInProgress || !!cluster.task({group: 'deployment', status: 'running'});
            return !locked && this.hasChanges() && _.isNull(settings.validationError);
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
                allocatedRoles = _.uniq(_.flatten(_.union(cluster.get('nodes').pluck('roles'), cluster.get('nodes').pluck('pending_roles')))),
                activeGroupVisible = !this.checkRestrictions('hide', settings.makePath(this.state.activeGroupName, 'metadata')).result,
                activeGroupName = this.state.activeGroupName;
            if (!activeGroupVisible) {
                // FIXME(vkramskikh): state is not updated. Probably we should store
                // the whole restrictions processing result in state to avoid this
                activeGroupName = _.min(_.keys(settings.attributes), function(groupName) {
                    return settings.get(groupName + '.metadata.weight');
                });
            }

            return (
                <div key={this.state.key} className='row'>
                    <div className='title'>{i18n('cluster_page.settings_tab.title')}</div>
                    <SettingSubtabs
                        settings={settings}
                        groupNames={sortedSettingGroups}
                        activeGroupName={activeGroupName}
                        makePath={settings.makePath}
                        configModels={this.state.configModels}
                        onClick={this.onSubtabClick}
                        checkRestrictions={this.checkRestrictions}
                    />
                    {_.compact(_.map(sortedSettingGroups, function(groupName) {
                        if (groupName != activeGroupName) {
                            return null;
                        }
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
                            checkRestrictions={this.checkRestrictions}
                        />;
                    }, this))}
                    <div className='col-xs-12 page-buttons content-elements'>
                        <div className='well clearfix'>
                            <div className='btn-group pull-right'>
                                <button className='btn btn-default btn-load-defaults' onClick={this.loadDefaults} disabled={locked || lockedCluster}>
                                    {i18n('common.load_defaults_button')}
                                </button>
                                <button className='btn btn-default btn-revert-changes' onClick={this.revertChanges} disabled={locked || !hasChanges}>
                                    {i18n('common.cancel_changes_button')}
                                </button>
                                <button className='btn btn-success btn-apply-changes' onClick={this.applyChanges} disabled={!this.isSavingPossible()}>
                                    {i18n('common.save_settings_button')}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            );
        }
    });

    var SettingSubtabs = React.createClass({
        render: function() {
            var errors = this.props.settings.validationError,
                invalidSections = {};
            _.forEach(errors, function(error, key) {
                invalidSections[_.first(key.split('.'))] = true;
            });
            return (
                <div className='col-xs-2'>
                    <CSSTransitionGroup component='ul' transitionName='subtab-item' className='nav nav-pills nav-stacked'>
                    {
                        this.props.groupNames.map(function(groupName) {
                            var group = this.props.settings.get(groupName),
                                metadata = group.metadata;
                            if (this.props.checkRestrictions('hide', this.props.makePath(groupName, 'metadata')).result) {
                                return null;
                            }
                            var hasErrors = invalidSections[groupName];
                            return (
                                <li
                                    key={groupName}
                                    role='presentation'
                                    className={utils.classNames({active: groupName == this.props.activeGroupName})}
                                    onClick={_.partial(this.props.onClick, groupName)}
                                >
                                    <a className={'subtab-link-' + groupName}>
                                        {hasErrors && <i className='subtab-icon glyphicon-danger-sign'/>}
                                        {metadata.label}
                                    </a>
                                </li>
                            );
                        }, this)
                    }
                    </CSSTransitionGroup>
                </div>
            );
        }
    });

    var SettingGroup = React.createClass({
        processRestrictions: function(groupName, settingName) {
            var result = false,
                path = this.props.makePath(groupName, settingName),
                messages = [];

            var restrictionsCheck = this.props.checkRestrictions('disable', path),
                dependentRoles = this.checkDependentRoles(groupName, settingName),
                dependentSettings = this.checkDependentSettings(groupName, settingName),
                messagesCheck = this.props.checkRestrictions('none', path);

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
        areCalculationsPossible: function(setting) {
            return _.contains(['checkbox', 'radio'], setting.type);
        },
        getValuesToCheck: function(setting, valueAttribute) {
            return setting.values ? _.without(_.pluck(setting.values, 'data'), setting[valueAttribute]) : [!setting[valueAttribute]];
        },
        checkValues: function(values, path, currentValue, restriction) {
            var extraModels = {settings: this.props.settingsForChecks};
            var result = _.all(values, function(value) {
                this.props.settingsForChecks.set(path, value);
                return new Expression(restriction.condition, this.props.configModels, restriction).evaluate(extraModels);
            }, this);
            this.props.settingsForChecks.set(path, currentValue);
            return result;
        },
        checkDependentRoles: function(groupName, settingName) {
            if (!this.props.allocatedRoles.length) return [];
            var path = this.props.makePath(groupName, settingName),
                setting = this.props.settings.get(path);
            if (!this.areCalculationsPossible(setting)) return [];
            var valueAttribute = this.props.getValueAttribute(settingName),
                valuesToCheck = this.getValuesToCheck(setting, valueAttribute),
                pathToCheck = this.props.makePath(path, valueAttribute),
                roles = this.props.cluster.get('roles');
            return _.compact(this.props.allocatedRoles.map(function(roleName) {
                var role = roles.findWhere({name: roleName});
                if (_.any(role.expandedRestrictions.restrictions, function(restriction) {
                    if (_.contains(restriction.condition, 'settings:' + path) && !(new Expression(restriction.condition, this.props.configModels, restriction).evaluate())) {
                        return this.checkValues(valuesToCheck, pathToCheck, setting[valueAttribute], restriction);
                    }
                    return false;
                }, this)) return role.get('label');
            }, this));
        },
        checkDependentSettings: function(groupName, settingName) {
            var path = this.props.makePath(groupName, settingName),
                currentSetting = this.props.settings.get(path);
            if (!this.areCalculationsPossible(currentSetting)) return [];
            var dependentRestrictions = {};
            var addDependentRestrictions = _.bind(function(pathToCheck, label) {
                var result = _.filter(this.props.settings.expandedRestrictions[pathToCheck], function(restriction) {
                    return restriction.action == 'disable' && _.contains(restriction.condition, 'settings:' + path);
                });
                if (result.length) {
                    dependentRestrictions[label] = result.concat(dependentRestrictions[label] || []);
                }
            }, this);
            // collect dependencies
            _.each(this.props.settings.attributes, function(group, groupName) {
                // don't take into account hidden dependent settings
                if (this.props.checkRestrictions('hide', this.props.makePath(groupName, 'metadata')).result) return;
                _.each(group, function(setting, settingName) {
                    // we support dependecies on checkboxes, toggleable setting groups, dropdowns and radio groups
                    var pathToCheck = this.props.makePath(groupName, settingName);
                    if (!this.areCalculationsPossible(setting) || pathToCheck == path || this.props.checkRestrictions('hide', pathToCheck).result) return;
                    if (setting[this.props.getValueAttribute(settingName)] == true) {
                        addDependentRestrictions(pathToCheck, setting.label);
                    } else {
                        var activeOption = _.find(setting.values, {data: setting.value});
                        if (activeOption) addDependentRestrictions(this.props.makePath(pathToCheck, activeOption.data), setting.label);
                    }
                }, this);
            }, this);
            // evaluate dependencies
            if (!_.isEmpty(dependentRestrictions)) {
                var valueAttribute = this.props.getValueAttribute(settingName),
                    pathToCheck = this.props.makePath(path, valueAttribute),
                    valuesToCheck = this.getValuesToCheck(currentSetting, valueAttribute),
                    checkValues = _.partial(this.checkValues, valuesToCheck, pathToCheck, currentSetting[valueAttribute]);
                return _.compact(_.map(dependentRestrictions, function(restrictions, label) {
                    if (_.any(restrictions, checkValues)) return label;
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
            if (this.props.checkRestrictions('hide', this.props.makePath(this.props.groupName, 'metadata')).result) return null;
            var group = this.props.settings.get(this.props.groupName),
                metadata = group.metadata,
                sortedSettings = _.chain(_.keys(group))
                    .without('metadata')
                    .sortBy(function(settingName) {return group[settingName].weight;})
                    .value(),
                processedGroupRestrictions = this.processRestrictions(this.props.groupName, 'metadata'),
                isGroupDisabled = this.props.locked || (this.props.lockedCluster && !metadata.always_editable) || processedGroupRestrictions.result,
                showSettingGroupWarning = !this.props.lockedCluster || metadata.always_editable;
            return (
                <div className='col-xs-10 forms-box'>
                    {processedGroupRestrictions.message && <div className='alert alert-warning'>{processedGroupRestrictions.message}</div>}
                    <h3>
                        {metadata.toggleable &&
                            <controls.Input
                                type='checkbox'
                                name='metadata'
                                defaultChecked={metadata.enabled}
                                disabled={isGroupDisabled}
                                tooltipText={showSettingGroupWarning && processedGroupRestrictions.message}
                                onChange={this.props.onChange}
                                wrapperClassName='pull-left'
                            />
                        }
                        <span className={'subtab-group-' + this.props.groupName}>{metadata.label || this.props.groupName}</span>
                    </h3>
                    <div>
                        {_.map(sortedSettings, function(settingName) {
                            var setting = group[settingName],
                                path = this.props.makePath(this.props.groupName, settingName);

                            if (!this.props.checkRestrictions('hide', path).result) {
                                var error = (this.props.settings.validationError || {})[path],
                                    processedSettingRestrictions = this.processRestrictions(this.props.groupName, settingName),
                                    isSettingDisabled = isGroupDisabled || (metadata.toggleable && !metadata.enabled) || processedSettingRestrictions.result,
                                    showSettingWarning = showSettingGroupWarning && !isGroupDisabled && (!metadata.toggleable || metadata.enabled);

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
                                                processedValueRestrictions = this.props.checkRestrictions('disable', valuePath);
                                            if (!this.props.checkRestrictions('hide', valuePath).result) {
                                                value.disabled = isSettingDisabled || processedValueRestrictions.result;
                                                value.defaultChecked = value.data == setting.value;
                                                value.tooltipText = showSettingWarning && processedValueRestrictions.message;
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
                                        tooltipText={showSettingWarning && processedSettingRestrictions.message}
                                    />;
                                }

                                var settingDescription = setting.description &&
                                        <span dangerouslySetInnerHTML={{__html: utils.urlify(_.escape(setting.description))}} />;
                                return <controls.Input
                                    {... _.pick(setting, 'type', 'label')}
                                    key={settingName}
                                    name={settingName}
                                    description={settingDescription}
                                    children={setting.type == 'select' ? this.composeOptions(setting.values) : null}
                                    debounce={setting.type == 'text' || setting.type == 'password' || setting.type == 'textarea'}
                                    defaultValue={setting.value}
                                    defaultChecked={_.isBoolean(setting.value) ? setting.value : false}
                                    toggleable={setting.type == 'password'}
                                    error={error}
                                    disabled={isSettingDisabled}
                                    tooltipText={showSettingWarning && processedSettingRestrictions.message}
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
