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
import $ from 'jquery';
import _ from 'underscore';
import i18n from 'i18n';
import React from 'react';
import utils from 'utils';
import models from 'models';
import componentMixins from 'component_mixins';
import SettingSection from 'views/cluster_page_tabs/setting_section';
import CSSTransitionGroup from 'react-addons-transition-group';

    var SettingsTab = React.createClass({
        mixins: [
            componentMixins.backboneMixin('cluster', 'change:status'),
            componentMixins.backboneMixin({
                modelOrCollection(props) {
                    return props.cluster.get('settings');
                },
                renderOn: 'change invalid'
            }),
            componentMixins.backboneMixin({modelOrCollection(props) {
                return props.cluster.get('tasks');
            }}),
            componentMixins.backboneMixin({modelOrCollection(props) {
                return props.cluster.task({group: 'deployment', active: true});
            }}),
            componentMixins.unsavedChangesMixin
        ],
        statics: {
            fetchData(options) {
                return $.when(options.cluster.get('settings').fetch({cache: true}),
                    options.cluster.get('networkConfiguration').fetch({cache: true})).then(() => ({}));
            }
        },
        getInitialState() {
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
                initialAttributes: _.cloneDeep(settings.attributes),
                actionInProgress: false
            };
        },
        componentDidMount() {
            this.props.cluster.get('settings').isValid({models: this.state.configModels});
        },
        componentWillUnmount() {
            this.loadInitialSettings();
        },
        hasChanges() {
            return this.props.cluster.get('settings').hasChanges(this.state.initialAttributes, this.state.configModels);
        },
        applyChanges() {
            if (!this.isSavingPossible()) return $.Deferred().reject();

            // collecting data to save
            var settings = this.props.cluster.get('settings'),
                dataToSave = this.props.cluster.isAvailableForSettingsChanges() ? settings.attributes :
                    _.pick(settings.attributes, (group) => (group.metadata || {}).always_editable);
            var options = {url: settings.url, patch: true, wait: true, validate: false},
                deferred = new models.Settings(_.cloneDeep(dataToSave)).save(null, options);
            if (deferred) {
                this.setState({actionInProgress: true});
                deferred
                    .done(() => {
                        this.setState({initialAttributes: _.cloneDeep(settings.attributes)});
                        // some networks may have restrictions which are processed by nailgun,
                        // so networks need to be refetched after updating cluster attributes
                        this.props.cluster.get('networkConfiguration').cancelThrottling();
                    })
                    .always(() => {
                        this.setState({
                            actionInProgress: false,
                            key: _.now()
                        });
                        this.props.cluster.fetch();
                    })
                    .fail((response) => {
                        utils.showErrorDialog({
                            title: i18n('cluster_page.settings_tab.settings_error.title'),
                            message: i18n('cluster_page.settings_tab.settings_error.saving_warning'),
                            response: response
                        });
                    });
            }
            return deferred;
        },
        loadDefaults() {
            var settings = this.props.cluster.get('settings'),
                lockedCluster = !this.props.cluster.isAvailableForSettingsChanges(),
                defaultSettings = new models.Settings(),
                deferred = defaultSettings.fetch({url: _.result(this.props.cluster, 'url') + '/attributes/defaults'});

            if (deferred) {
                this.setState({actionInProgress: true});
                deferred
                    .done(() => {
                        _.each(settings.attributes, (section, sectionName) => {
                            if ((!lockedCluster || section.metadata.always_editable) && section.metadata.group != 'network') {
                                _.each(section, (setting, settingName) => {
                                    // do not update hidden settings (hack for #1442143),
                                    // the same for settings with group network
                                    if (setting.type == 'hidden' || setting.group == 'network') return;
                                    var path = settings.makePath(sectionName, settingName);
                                    settings.set(path, defaultSettings.get(path), {silent: true});
                                });
                            }
                        });
                        settings.mergePluginSettings();
                        settings.isValid({models: this.state.configModels});
                        this.setState({
                            actionInProgress: false,
                            key: _.now()
                        });
                    })
                    .fail((response) => {
                        utils.showErrorDialog({
                            title: i18n('cluster_page.settings_tab.settings_error.title'),
                            message: i18n('cluster_page.settings_tab.settings_error.load_defaults_warning'),
                            response: response
                        });
                    });
            }
        },
        revertChanges() {
            this.loadInitialSettings();
            this.setState({key: _.now()});
        },
        loadInitialSettings() {
            var settings = this.props.cluster.get('settings');
            settings.set(_.cloneDeep(this.state.initialAttributes), {silent: true, validate: false});
            settings.mergePluginSettings();
            settings.isValid({models: this.state.configModels});
        },
        onChange(groupName, settingName, value) {
            var settings = this.props.cluster.get('settings'),
                name = settings.makePath(groupName, settingName, settings.getValueAttribute(settingName));
            this.state.settingsForChecks.set(name, value);
            // FIXME: the following hacks cause we can't pass {validate: true} option to set method
            // this form of validation isn't supported in Backbone DeepModel
            settings.validationError = null;
            settings.set(name, value);
            settings.isValid({models: this.state.configModels});
        },
        checkRestrictions(action, path) {
            return this.props.cluster.get('settings').checkRestrictions(this.state.configModels, action, path);
        },
        isSavingPossible() {
            var cluster = this.props.cluster,
                settings = cluster.get('settings'),
                locked = this.state.actionInProgress || !!cluster.task({group: 'deployment', active: true});
            return !locked && this.hasChanges() && _.isNull(settings.validationError);
        },
        render() {
            var cluster = this.props.cluster,
                settings = cluster.get('settings'),
                settingsGroupList = settings.getGroupList(),
                locked = this.state.actionInProgress || !!cluster.task({group: 'deployment', active: true}),
                lockedCluster = !cluster.isAvailableForSettingsChanges(),
                someSettingsEditable = _.any(settings.attributes, (group) => group.metadata.always_editable),
                hasChanges = this.hasChanges(),
                allocatedRoles = _.uniq(_.flatten(_.union(cluster.get('nodes').pluck('roles'), cluster.get('nodes').pluck('pending_roles')))),
                classes = {
                    row: true,
                    'changes-locked': lockedCluster
                };

            var invalidSections = {};
            _.each(settings.validationError, (error, key) => {
                invalidSections[_.first(key.split('.'))] = true;
            });

            // Prepare list of settings organized by groups
            var groupedSettings = {};
            _.each(settingsGroupList, (group) => groupedSettings[group] = {});
            _.each(settings.attributes, function(section, sectionName) {
                var isHidden = this.checkRestrictions('hide', settings.makePath(sectionName, 'metadata')).result;
                if (!isHidden) {
                    var group = section.metadata.group,
                        hasErrors = invalidSections[sectionName];
                    if (group) {
                        if (group != 'network') {
                            groupedSettings[settings.sanitizeGroup(group)][sectionName] = {invalid: hasErrors};
                        }
                    } else {
                        // Settings like 'Common' can be splitted to different groups
                        var settingGroups = _.chain(section)
                            .omit('metadata')
                            .pluck('group')
                            .unique()
                            .without('network')
                            .value();

                        // to support plugins without settings (just for user to be able to switch its version)
                        if (!settingGroups.length && settings.isPlugin(section)) {
                            groupedSettings.other[sectionName] = {settings: [], invalid: hasErrors};
                        }

                        _.each(settingGroups, function(settingGroup) {
                            var calculatedGroup = settings.sanitizeGroup(settingGroup),
                                pickedSettings = _.compact(_.map(section, function(setting, settingName) {
                                    if (
                                        settingName != 'metadata' &&
                                        setting.type != 'hidden' &&
                                        settings.sanitizeGroup(setting.group) == calculatedGroup &&
                                        !this.checkRestrictions('hide', settings.makePath(sectionName, settingName)).result
                                    ) return settingName;
                                }, this)),
                                hasErrors = _.any(pickedSettings, (settingName) => {
                                    return (settings.validationError || {})[settings.makePath(sectionName, settingName)];
                                });
                            if (!_.isEmpty(pickedSettings)) {
                                groupedSettings[calculatedGroup][sectionName] = {settings: pickedSettings, invalid: hasErrors};
                            }
                        }, this);
                    }
                }
            }, this);
            groupedSettings = _.omit(groupedSettings, _.isEmpty);

            return (
                <div key={this.state.key} className={utils.classNames(classes)}>
                    <div className='title'>{i18n('cluster_page.settings_tab.title')}</div>
                    <SettingSubtabs
                        settings={settings}
                        settingsGroupList={settingsGroupList}
                        groupedSettings={groupedSettings}
                        makePath={settings.makePath}
                        configModels={this.state.configModels}
                        setActiveSettingsGroupName={this.props.setActiveSettingsGroupName}
                        activeSettingsSectionName={this.props.activeSettingsSectionName}
                        checkRestrictions={this.checkRestrictions}
                    />
                    {_.map(groupedSettings, function(selectedGroup, groupName) {
                        if (groupName != this.props.activeSettingsSectionName) return null;

                        var sortedSections = _.sortBy(_.keys(selectedGroup), (name) => settings.get(name + '.metadata.weight'));
                        return (
                            <div className={'col-xs-10 forms-box ' + groupName} key={groupName}>
                                {_.map(sortedSections, function(sectionName) {
                                    var settingsToDisplay = selectedGroup[sectionName].settings ||
                                        _.compact(_.map(settings.get(sectionName), function(setting, settingName) {
                                            if (
                                                settingName != 'metadata' &&
                                                setting.type != 'hidden' &&
                                                !this.checkRestrictions('hide', settings.makePath(sectionName, settingName)).result
                                            ) return settingName;
                                        }, this));
                                    return <SettingSection
                                        {... _.pick(this.state, 'initialAttributes', 'settingsForChecks', 'configModels')}
                                        key={sectionName}
                                        cluster={this.props.cluster}
                                        sectionName={sectionName}
                                        settingsToDisplay={settingsToDisplay}
                                        onChange={_.bind(this.onChange, this, sectionName)}
                                        allocatedRoles={allocatedRoles}
                                        settings={settings}
                                        makePath={settings.makePath}
                                        getValueAttribute={settings.getValueAttribute}
                                        locked={locked}
                                        lockedCluster={lockedCluster}
                                        checkRestrictions={this.checkRestrictions}
                                    />;
                                }, this)}
                            </div>
                        );
                    }, this)}
                    <div className='col-xs-12 page-buttons content-elements'>
                        <div className='well clearfix'>
                            <div className='btn-group pull-right'>
                                <button className='btn btn-default btn-load-defaults' onClick={this.loadDefaults} disabled={locked || (lockedCluster && !someSettingsEditable)}>
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
        render() {
            return (
                <div className='col-xs-2'>
                    <CSSTransitionGroup component='ul' transitionName='subtab-item' className='nav nav-pills nav-stacked'>
                    {
                        this.props.settingsGroupList.map(function(groupName) {
                            if (!this.props.groupedSettings[groupName]) return null;

                            var hasErrors = _.any(_.pluck(this.props.groupedSettings[groupName], 'invalid'));
                            return (
                                <li
                                    key={groupName}
                                    role='presentation'
                                    className={utils.classNames({active: groupName == this.props.activeSettingsSectionName})}
                                    onClick={_.partial(this.props.setActiveSettingsGroupName, groupName)}
                                >
                                    <a className={'subtab-link-' + groupName}>
                                        {hasErrors && <i className='subtab-icon glyphicon-danger-sign'/>}
                                        {i18n('cluster_page.settings_tab.groups.' + groupName, {defaultValue: groupName})}
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

    export default SettingsTab;
