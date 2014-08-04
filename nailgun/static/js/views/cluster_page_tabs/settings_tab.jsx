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
    'models'
],
function(React, utils, models) {
    'use strict';

    var SettingMixin = function() {
        return {
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
                        return _.contains(dependency.condition, 'settings:' + this.props.settingPath) && evaluatedDependency.value;
                    }, this);
                    return hasSatisfiedDependencies && this.props.cluster.get('nodes').filter(function(node) { return node.hasRole(role); }).length;
                }, this);
            },
            checkDependentSettings: function(valueAttribute) {
                var currentSetting = this.props.settings.get(this.props.settingPath);
                if (_.contains(['text', 'password'], currentSetting.type)) { return false; }
                var isDependent = function(restriction) {
                    restriction = utls.expandRestriction(restriction);
                    return restriction.action == 'disable' && _.contains(restriction.condition, 'settings:' + this.props.settingPath);
                };
                // collect restrictions to check
                var restrictions = [];
                _.each(this.props.settings.attributes, function(group, groupName) {
                    if (this.checkRestrictions('hide', group.metadata.restrictions)) { return; }
                    _.each(group, function(setting, settingName) {
                        if (_.contains(['text', 'password'], setting.type) ||
                            groupName + '.' + settingName == this.props.settingPath ||
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
                            configModels.settings.get(this.props.settingPath)[valueAttribute || 'value'] = value;
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
                loading: true,
                disabled: this.isLocked()
            };
        },
        componentWillMount: function() {
            var settings = this.props.cluster.get('settings');
            settings.on('invalid', _.bind(this.forceUpdate, this, undefined));
            $.when(settings.fetch({cache: true}), this.props.cluster.get('networkConfiguration').fetch({cache: true})).done(function() {
                this.updateInitialSettings();
                this.setState({
                    loading: false,
                    configModels: {
                        cluster: this.props.cluster,
                        settings: settings,
                        networking_parameters: this.props.cluster.get('networkConfiguration').get('networking_parameters'),
                        version: app.version,
                        default: settings
                    }
                });
            });
        },
        componentWillUnmount: function() {
            this.loadInitialSettings();
        },
        hasChanges: function() {
            return !_.isEqual(this.props.cluster.get('settings').attributes, this.initialSettings.attributes);
        },
        isLocked: function() {
            return !!this.props.cluster.task({group: 'deployment', status: 'running'}) || !this.props.cluster.isAvailableForSettingsChanges();
        },
        applyChanges: function() {
            this.setState({disabled: true});
            return this.props.cluster.get('settings').save(null, {patch: true, wait: true})
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
            var settings = this.props.cluster.get('settings');
            settings.fetch({url: _.result(settings, 'url') + '/defaults'})
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
            this.props.cluster.get('settings').set(_.cloneDeep(this.initialSettings.attributes));
        },
        updateInitialSettings: function() {
            this.initialSettings.set(_.cloneDeep(this.props.cluster.get('settings').attributes));
        },
        render: function() {
            var settings = this.props.cluster.get('settings'),
                sortedSettingGroups = _.sortBy(_.keys(settings.attributes), function(groupName) {
                    return settings.get(groupName + '.metadata.weight');
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
                            return <SettingGroup settings={settings} configModels={this.state.configModels} groupName={groupName} disabled={this.state.disabled} />
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
        isDisabled: function() {
            return this.props.disabled || this.checkRestrictions('disable') || this.checkDependentRoles() || checkDependentSettings('enabled'),
        },
        getRestrictions: function() {
            var settingGroup = this.props.settings.get(this.props.groupName + '.metadata');
            return _.map(settingGroup.restrictions, utils.expandRestriction);
        },
        render: function() {
            var sortedSettings = _.sortBy(_.without(_.keys(this.props.settings.get(this.props.groupName)), 'metadata'), function(setting) {
                    return this.props.settings.get(this.props.groupName)[setting].weight;
                }),
                cs = {common: 'toggleable'};
            return (
                {!this.checkRestrictions('hide') &&
                    <div className='fieldset-group wrapper'>
                        <legend className='openstack-settings'>
                            {metadata.toggleable ?
                                this.transferPropsTo(<Checkbox cs={cs}/>)
                                :
                                {this.props.settings.get(this.props.groupName + '.metadata').label || this.props.groupName}
                            }
                        </legend>
                        <div className='settings-group table-wrapper'>
                            {_.map(sortedSettings, function(settingName) {
                                return this.transferPropsTo(<Setting settingName={settingName} disabled={this.isDisabled())} />);
                            })}
                        </div>
                    </div>
                }
            );
        }
    });

    var Setting = React.creaeClass({
        mixins: [SettingMixin],
        isDisabled: function() {
            return this.props.disabled || this.checkRestrictions('disable') || this.checkDependentRoles() || checkDependentSettings(),
        },
        getRestrictions: function() {
            var setting = this.props.settings.get(this.props.groupName + '.' + this.props.settingName);
            return _.map(setting.restrictions, utils.expandRestriction);
        },
        render: function() {
            var type = this.props.settings.get(this.props.groupName + '.' + this.props.settingName).type,
                cs = {common: 'tablerow-wrapper', label: 'openstack-sub-title', description: 'parameter-description'},
                extendedCs = _.extend(cs, {commonClass: 'table-colspan'});
            return (
                {!this.checkRestrictions('hide') &&
                    {type == 'checkbox' && this.transferPropsTo(<Checkbox cs={extendedCs} disabled={this.isDisabled()} />)}
                    {type == 'dropdown' && this.transferPropsTo(<Dropdown cs={cs} disabled={this.isDisabled()} />)}
                    {type == 'radio' && this.transferPropsTo(<Radiogroup cs={cs} disabled={this.isDisabled()} />)}
                    {type == 'text' && this.transferPropsTo(<TextField cs={extendedCs} disabled={this.isDisabled()} />)}
                    {type == 'password' && this.transferPropsTo(<PasswordField cs={extendedCs} disabled={this.isDisabled()} />)}
                }
            );
        }
    });

    var InputMixin = {
        getInitialState: function() {
            return {value: setting.value || setting.enabled};
        },
        onChange: function() {
            var path = this.props.groupName + '.' + (this.props.settingName ? this.props.settingName + '.value' || 'metadata.enabled');
            this.props.settings.set({path: this.state.value}, {validate: true});
        },
        checkError: function() {
            var error = _.findWhere(this.props.settings.validationError, {field: this.props.groupName + '.' + this.props.settingName});
            return error ? error.message : false;
        }
    };

    var Checkbox = React.createClass({
        mixins: [
            React.addons.LinkedStateMixin,
            InputMixin
        ],
        render: function() {
            var setting = this.props.settings.get(this.props.groupName + '.' + this.props.settingName);
            return (
                <div className={this.props.cs.common + ' setting-container'}>
                    <label className='parameter-box clearfix'>
                        <div className='parameter-control'>
                            <div className='custom-tumbler'>
                                <input type='checkbox' valueLink={this.linkState('value')} disabled={this.props.disabled} onChange={this.onChange} />
                                <span>&nbsp;</span>
                            </div>
                        </div>
                        <div className={this.props.cs.label + ' parameter-name'}>{setting.label}</div>
                        <div className={this.props.cs.description + ' description'}>{setting.description}</div>
                    </label>
                </div>
            );
        }
    });

    var Dropdown = React.createClass({
        mixins: [
            React.addons.LinkedStateMixin,
            InputMixin
        ],
        render: function() {
            var setting = this.props.settings.get(this.props.groupName + '.' + this.props.settingName);
            return (
                <div className={this.props.cs.common + 'parameter-box clearfix'}>
                    <div className={this.props.cs.label + ' parameter-name'}>{setting.label}</div>
                    <div className='parameter-control'>
                        <select valueLink={this.linkState('value')} disabled={this.props.disabled} onChange={this.onChange} >
                            {_.each(setting.values, function(value) {
                                <option value={value.data}>{value.label}</option>
                            })}
                        </select>
                    </div>
                    <div className={this.props.cs.description + ' description'}>{setting.description}</div>
                </div>
            );
        }
    });

    var RadioGroup = React.createClass({
        render: function() {
            var setting = this.props.settings.get(this.props.groupName + '.' + this.props.settingName);
            return (
                <div className={this.props.cs.common}>
                    <legend className={this.props.cs.label}>{setting.label}</legend>
                    {_.map(setting.values, function(value) {
                        return this.transferPropsTo(<RadioOption data={value.data} />);
                    })}
                </div>
            );
        }
    };

    var RadioOption = React.createClass({
        mixins: [
            React.addons.LinkedStateMixin,
            viewMixins.toggleablePassword,
            SettingMixin,
            InputMixin
        ],
        isDisabled: function() {
            return this.props.disabled || this.checkRestrictions('disable')
        },
        getOption: function() {
            return _.where(this.props.settings.get(this.props.groupName + '.' + this.props.settingName + '.values'), {data: this.props.data});
        },
        getRestrictions: function() {
            return _.map(this.getOption().restrictions, utils.expandRestriction);
        },
        render: function() {
            var option = this.getOption();
            return (
                {!this.checkRestrictions('hide') &&
                    <label className='parameter-box clearfix'>
                        <div className='parameter-control'>
                            <div className='custom-tumbler'>
                                <input type='radio' name={this.props.settingName} valueLink={this.linkState('value')} disabled={this.isDisabled()} onChange={this.onChange} />
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
        mixins: [
            React.addons.LinkedStateMixin,
            InputMixin
        ],
        render: function() {
            var setting = this.props.settings.get(this.props.groupName + '.' + this.props.settingName),
                error = this.checkError();
            return (
                <div className={this.props.cs.common + 'parameter-box clearfix'}>
                    <div className={this.props.cs.label + ' parameter-name'}>{setting.label}</div>
                    <div className='parameter-control'>
                        <input className={error && 'error'} type='text' valueLink={this.linkState('value')} disabled={this.props.disabled} onChange={this.onChange} />
                    </div>
                    {error ?
                        <div className={this.props.cs.description + ' validation-error'}>{error}</div>
                        :
                        <div className={this.props.cs.description + ' description'}>{setting.description}</div>
                    }
                </div>
            );
        }
    };

    var PasswordField = React.createClass({
        mixins: [
            React.addons.LinkedStateMixin,
            InputMixin
        ],
        componentWillMount: function() {
            this.setState({visible: false});
        },
        togglePassword: function() {
            if (this.props.disabled) { return; }
            this.setState({visible: !this.state.visible});
        },
        render: function() {
            var setting = this.props.settings.get(this.props.groupName + '.' + this.props.settingName),
                error = this.checkError();
            return (
                <div className={this.props.cs.common + 'parameter-box clearfix'}>
                    <div className={this.props.cs.label + ' parameter-name'}>{setting.label}</div>
                    <div className='parameter-control input-append'>
                        <input
                            className={'input-append ' + (error && 'error')}
                            type={this.state.visible ? 'text' : 'password'}
                            valueLink={this.linkState('value')}
                            disabled={this.props.disabled}
                            onChange={this.onChange} />
                        <span className='add-on' onclick={this.togglePassword}>
                            <i className={this.state.visible ? 'icon-eye-off' : 'icon-eye'} />
                        </span>
                    </div>
                    {error ?
                        <div className={this.props.cs.description + ' validation-error'}>{error}</div>
                        :
                        <div className={this.props.cs.description + ' description'}>{setting.description}</div>
                    }
                </div>
            );
        }
    };

    return SettingsTab;
});
