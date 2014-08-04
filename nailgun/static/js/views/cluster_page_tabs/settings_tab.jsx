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
    'view_mixins'
],
function(React, utils, models, viewMixins) {
    'use strict';

    var SettingMixin = function() {
        return {,
            transferPropsTo: function(component) {
                component.props = _.extend{
                    settings: this.props.settings,
                    cluster: this.props.cluster,
                    configModels: this.props.configModels,
                    settingPath: this.state.settingPath,
                    onChange: this.handleChange,
                    disabled: this.state.disabled,
                    visible: this.state.visible
                }, component.props);
                return component;
            },
            checkRestrictions: function(action, restrictions) {
                restrictions = restrictions || this.getRestrictions();
                return _.any(_.where(restrictions, {action: action}), function(restriction) {
                    return utils.evaluateExpression(restriction.condition, this.configModels).value;
                }, this);
            },
            checkDependentRoles: function() {
                var release = this.props.cluster.get('release'),
                    rolesData = release.get('roles_metadata');
                return _.any(release.get('roles'), function(role) {
                    var hasSatisfiedDependencies = _.any(_.map(rolesData[role].depends, utils.expandRestriction), function(dependency) {
                        var evaluatedDependency = utils.evaluateExpression(dependency.condition, this.state.configModels);
                        return _.contains(dependency.condition, 'settings:' + this.state.settingPath) && evaluatedDependency.value;
                    }, this);
                    return hasSatisfiedDependencies && this.props.cluster.get('nodes').filter(function(node) { return node.hasRole(role); }).length;
                }, this);
            },
            checkDependentSettings: function(valueAttribute) {
                var currentSetting = this.props.settings.get(this.state.settingPath);
                if (_.contains(['text', 'password'], currentSetting.type)) { return false; }
                var isDependent = function(restriction) {
                    restriction = utls.expandRestriction(restriction);
                    return restriction.action == 'disable' && _.contains(restriction.condition, 'settings:' + this.state.settingPath);
                };
                // collect restrictions to check
                var restrictions = [];
                _.each(this.props.settings.attributes, function(group, groupName) {
                    if (this.checkRestrictions('hide', group.metadata.restrictions)) { return; }
                    _.each(group, function(setting, settingName) {
                        if (_.contains(['text', 'password'], setting.type) ||
                            groupName + '.' + settingName == this.state.settingPath ||
                            this.checkRestrictions('hide', setting.restrictions)
                        ) { return; }
                        if (setting[settingName == 'metadata' ? 'enabled' : 'value'] == true) { // for checkboxes and toggleable setting groups
                            restrictions.push(_.find(setting.restrictions, isDependent));
                        } else {
                            var activeOption = _.find(setting.values, {data: setting.value}); // for dropdowns and radio groups
                            if (activeOption) {
                                restrictions.push(_.find(activeOption.restrictions, isDependent));
                            }
                        }
                    }, this);
                }, this);
                restrictions = _.map(_.compact(restrictions), utls.expandRestriction);
                if (restrictions.length) {
                    var currentValue =  currentSetting[valueAttribute || 'value'];
                    var values = _.without(_.pluck(currentSetting.values, 'data'), currentValue) || [!currentValue];
                    var configModels = _.extend({}, this.state.configModels, {settings: new models.Settings(_.cloneDeep(this.props.settings.attributes)});
                    return _.any(restrictions, function(restriction) {
                        var suitableValues = _.filter(values, function(value) {
                            configModels.settings.get(this.state.settingPath)[valueAttribute || 'value'] = value;
                            return !utils.evaluateExpression(restriction.condition, configModels).value;
                        }, this);
                        return !suitableValues.length;
                    }, this);
                }
                return false;
            }
        };
    };

    var SettingsTab = React.createClass({
        mixins: [
            React.BackboneMixin('cluster'),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.cluster.get('tasks');
            }}),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.cluster.task({group: 'deployment', status: 'running'});
            }})
        ],
        getInitialState: function() {
            return {
                initialSettings: new models.Settings(),
                settings: this.props.cluster.get('settings'),
                loading: true,
                disabled: this.isLocked()
            };
        },
        componentWillMount: function() {
            this.state.settings.on('invalid', _.bind(this.forceUpdate, this, undefined));
            $.when(this.state.settings.fetch({cache: true}), this.props.cluster.get('networkConfiguration').fetch({cache: true})).done(function() {
                this.updateInitialSettings();
                this.setState({
                    loading: false,
                    configModels: {
                        cluster: this.props.cluster,
                        settings: this.state.settings,
                        networking_parameters: this.props.cluster.get('networkConfiguration').get('networking_parameters'),
                        version: app.version,
                        default: this.state.settings
                    }
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
            this.setState({disabled: true});
            return this.props.settings.save(null, {patch: true, wait: true})
                .done(this.updateInitialSettings)
                .always(function() {
                    this.setState({disabled: this.isLocked()});
                    this.props.cluster.fetch();
                })
                .fail(function() {
                    utils.showErrorDialog({
                        title: $.t('cluster_page.settings_tab.settings_error.title'),
                        message: $.t('cluster_page.settings_tab.settings_error.saving_warning')
                    });
                };
        },
        loadDefaults: function() {
            this.setState({disabled: true});
            this.props.settings.fetch({url: _.result(this.props.settings, 'url') + '/defaults'})
                .always(function() {
                    this.setState({disabled: this.isLocked()});
                })
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
        render: function() {
            var sortedSettingGroups = _.sortBy(_.keys(this.state.settings.attributes), function(groupName) {
                return this.state.settings.get(groupName + '.metadata.weight');
            }, this);
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
                                settings = {this.state.settings}
                                cluster = {this.props.cluster}
                                configModels = {this.state.configModels}
                                groupName = {groupName}
                                disabled = {this.state.disabled} />
                        });
                        <div class='row'>
                            <div class='page-control-box'>
                                <div class='page-control-button-placeholder'>
                                    <button key='loadDefaults' className='btn' onclick={this.loadDefaults} disabled={this.state.disabled}>{$.t('common.load_defaults_button')}</button>
                                    <button key='cancelChanges' className='btn' onclick={this.revertChanges} disabled={!this.hasChanges()}>{$.t('common.cancel_changes_button')}</button>
                                    <button key='applyChanges' className='btn btn-success' onclick={this.applyChanges} disabled={!this.hasChanges() || settings.validationError}>{$.t('common.save_settings_button')}</button>
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
        getInitialState: function() {
            return {
                settingPath: this.props.groupName + '.metadata',
                disabled: this.props.disabled || this.checkRestrictions('disable') || this.checkDependentRoles() || checkDependentSettings('enabled'),
                visible: !this.checkRestrictions('hide')
            };
        },
        getRestrictions: function() {
            var SettingGroup = this.props.settings.get(this.state.settingPath);
            return _.map(settingGroup.restrictions, utils.expandRestriction);
        },
        handleChange: function(e) {
            this.props.settings.set({this.state.settingPath + '.enabled': e.target.value}, {validate: true});
        },
        render: function() {
            var sortedSettings = _.sortBy(_.without(_.keys(this.props.settings.get(this.props.groupName)), 'metadata'), function(setting) {
                    return this.props.settings.get(this.props.groupName)[setting].weight;
                }),
                cs = {common: 'toggleable'};
            return (
                {this.state.visible &&
                    <div className='fieldset-group wrapper'>
                        <legend className='openstack-settings'>
                            {metadata.toggleable ?
                                this.transferPropsTo(<Checkbox cs={cs}/>)
                                :
                                {this.props.settings.get(this.state.settingPath).label || this.props.groupName}
                            }
                        </legend>
                        <div className='settings-group table-wrapper'>
                            {_.map(sortedSettings, function(settingName) {
                                return this.transferPropsTo(<Setting settingPath = {this.props.groupName + '.' + settingName} />);
                            })}
                        </div>
                    </div>
                }
            );
        }
    });

    var Setting = React.creaeClass({
        mixins: [SettingMixin],
        getInitialState: function() {
            settingPath: this.props.settingPath,
            disabled: this.props.disabled || this.checkRestrictions('disable') || this.checkDependentRoles() || checkDependentSettings(),
            visible: !this.checkRestrictions('hide')
        },
        getRestrictions: function() {
            var setting = this.props.settings.get(this.state.settingPath);
            return _.map(setting.restrictions, utils.expandRestriction);
        },
        handleChange: function(e) {
            this.props.settings.set({this.state.settingPath + '.value': e.target.value}, {validate: true});
        },
        render: function() {
            var type = this.props.settings.get(this.state.settingPath).type,
                cs = {common: 'tablerow-wrapper', label: 'openstack-sub-title', description: 'parameter-description'};
            return (
                {this.state.visible &&
                    {type == 'checkbox' && this.transferPropsTo(<Checkbox cs={_.extend(cs, {commonClass: 'table-colspan'})} />)}
                    {type == 'dropdown' && this.transferPropsTo(<Dropdown/>)}
                    {type == 'radio' && this.transferPropsTo(<Radiogroup/>)}
                    {_.contains(['text', 'password'], type) && this.transferPropsTo(<TextField cs={_.extend(cs, {commonClass: 'table-colspan'})} />)}
                }
            );
        }
    });

    var Checkbox = React.createClass({
        render: function() {
            var setting = this.props.settings.get(this.props.settingPath),
                cs = this.props.cs;
            return (
                <div className={cs.common + ' setting-container'}>
                    <label className='parameter-box clearfix'>
                        <div className='parameter-control'>
                            <div className='custom-tumbler'>
                                <input
                                    type='checkbox'
                                    name={this.props.settingPath}
                                    value={setting.value || setting.enabled}
                                    disabled={this.props.disabled}
                                    onChange={this.props.onChange} />
                                <span>&nbsp;</span>
                            </div>
                        </div>
                        <div className={cs.label + ' parameter-name'}>{setting.label}</div>
                        <div className={cs.description + ' description'}>{setting.description}</div>
                    </label>
                </div>
            );
        }
    });

    var Dropdown = React.createClass({
        render: function() {
            var setting = this.props.settings.get(this.props.settingPath),
                cs = this.props.cs;
            return (
                <div className={cs.common + 'parameter-box clearfix'}>
                    <div className={cs.label + ' parameter-name'}>{setting.label}</div>
                    <div className='parameter-control'>
                        <select
                            name={this.props.settingPath}
                            value={setting.value || setting.enabled}
                            disabled={this.props.disabled}
                            onChange={data.onChange} >
                            {_.each(setting.values, function(value) {
                                <option value={value.data}>{value.label}</option>
                            })}
                        </select>
                    </div>
                    <div className={cs.description + ' description'}>{setting.description}</div>
                </div>
            );
        }
    });

    var RadioGroup = React.createClass({
        mixins: [SettingMixin],
        render: function() {
            var setting = this.props.settings.get(this.props.settingPath),
                cs = this.props.cs;
            return (
                <div className={cs.common}>
                    <legend className={cs.label}>{setting.label}</legend>
                    {_.map(setting.values, function(value) {
                        return this.transferPropsTo(<RadioOption data={value.data} />);
                    })}
                </div>
            );
        }
    };

    var RadioOption = React.createClass({
        getInitialState: function() {
            settingPath: this.props.settingPath,
            disabled: this.props.disabled || this.checkRestrictions('disable'),
            visible: this.props.visible && !this.checkRestrictions('hide')
        },
        getOption: function() {
            return _.where(this.props.settings.get(this.state.settingPath + '.values'), {data: this.props.data});
        },
        getRestrictions: function() {
            return _.map(this.getOption().restrictions, utils.expandRestriction);
        },
        render: function() {
            var option = this.getOption();
            return (
                {this.state.visible &&
                    <label className='parameter-box clearfix'>
                        <div className='parameter-control'>
                            <div className='custom-tumbler'>
                                <input
                                    type='radio'
                                    name={this.state.settingPath}
                                    value={this.props.data}
                                    disabled={this.state.disabled}
                                    onChange={this.props.onChange} />
                                <span>&nbsp;</span>
                            </div>
                        </div>
                        <div className='parameter-name'>{option.label}</div>
                        <div className={this.props.cs.description + ' description'}>{option.description}</div>
                    </label>
                }
            );
        }
    };

    var TextField = React.createClass({
        mixins: [viewMixins.toggleablePassword],
        checkError: function() {
            var error = _.findWhere(this.props.settings.validationError, {field: this.props.settingPath});
            return error ? error.message : false;
        },
        render: function() {
            var setting = this.props.settings.get(this.props.settingPath),
                error = this.checkError(),
                cs = this.props.cs;
            return (
                <div className={cs.common + 'parameter-box clearfix'}>
                    <div className={cs.label + ' parameter-name'}>{setting.label}</div>
                    <div className='parameter-control'>
                        <input
                            name={this.props.settingPath}
                            className={error && 'error'}
                            type={setting.type}
                            name={setting.name}
                            value={setting.value || setting.enabled}
                            disabled={this.props.disabled}
                            onChange={this.props.onChange} />
                    </div>
                    {error ?
                        <div className={cs.description + ' validation-error'}>{error}</div>
                        :
                        <div className={cs.description + ' description'}>{setting.description}</div>
                    }
                </div>
            );
        }
    };

    return SettingsTab;
});
