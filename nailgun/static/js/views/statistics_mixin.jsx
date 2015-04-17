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
define([
    'jquery',
    'underscore',
    'i18n',
    'react',
    'utils',
    'models',
    'jsx!views/dialogs',
    'jsx!views/controls'
], function($, _, i18n, React, utils, models, dialogs, controls) {
    'use strict';

    return {
        propTypes: {
            settings: React.PropTypes.object.isRequired
        },
        getDefaultProps: function() {
            return {fields: ['send_anonymous_statistic', 'send_user_info']};
        },
        getInitialState: function() {
            var tracking = this.props.settings.get('tracking');
            return {
                isConnected: !!(tracking.email.value && tracking.password.value),
                actionInProgress: false,
                showItems: false,
                remoteLoginForm: new models.MirantisLoginForm(),
                registrationForm: new models.MirantisRegistrationForm(),
                remoteRetrievePasswordForm: new models.MirantisRetrievePasswordForm()
            };
        },
        setConnected: function() {
            this.setState({isConnected: true});
        },
        saveSettings: function(initialAttributes) {
            var settings = this.props.settings;
            this.setState({actionInProgress: true});
            return settings.save(null, {patch: true, wait: true, validate: false})
                .fail(function(response) {
                    if (initialAttributes) settings.set(initialAttributes);
                    utils.showErrorDialog({response: response});
                })
                .always(_.bind(function() {
                    this.setState({actionInProgress: false});
                }, this));
        },
        prepareStatisticsToSave: function() {
            var currentAttributes = _.cloneDeep(this.props.settings.attributes);
            // We're saving only two checkboxes
            _.each(this.props.fields, function(field) {
                var path = this.props.settings.makePath('statistics', field, 'value');
                this.props.settings.set(path, this.props.statistics.get(path));
            }, this);
            return this.saveSettings(currentAttributes);
        },
        prepareTrackingToSave: function(response) {
            var currentAttributes = _.cloneDeep(this.props.settings.attributes),
                tracking = this.props.tracking;
            // Saving user contact data to Statistics section
            _.each(response, function(value, name) {
                if (name != 'password') {
                    var path = this.props.settings.makePath('statistics', name, 'value');
                    this.props.settings.set(path, value);
                    this.props.tracking.set(path, value);
                }
            }, this);
            // Saving email and password to Tracking section
            _.each(tracking.get('tracking'), function(data, inputName) {
                var path = this.props.settings.makePath('tracking', inputName, 'value');
                this.props.settings.set(path, tracking.get(path));
            }, this);
            this.saveSettings(currentAttributes)
                .done(_.bind(function() {
                    this.setConnected();
                }, this));
        },
        showResponseErrors: function(response) {
            var jsonObj,
                error = '';
            try {
                jsonObj = JSON.parse(response.responseText);
                error = jsonObj.message;
            } catch (e) {
                error = i18n('welcome_page.register.connection_error');
            }
            this.setState({error: error});
        },
        connectToMirantis: function() {
            this.setState({error: null});
            var settings = this.props.tracking;
            if (settings.isValid({models: this.configModels})) {
                var tracking = settings.get('tracking'),
                    remoteLoginForm = this.state.remoteLoginForm;
                this.setState({actionInProgress: true});
                _.each(tracking, function(data, inputName) {
                    var name = remoteLoginForm.makePath('credentials', inputName, 'value');
                    remoteLoginForm.set(name, tracking[inputName].value);
                }, this);
                remoteLoginForm.save()
                    .done(this.prepareTrackingToSave)
                    .fail(this.showResponseErrors)
                    .always(_.bind(function() {
                        this.setState({actionInProgress: false});
                    }, this));
            }
        },
        checkRestrictions: function(name, action) {
            action = action || 'disable';
            return this.props.settings.checkRestrictions(this.configModels, action, this.props.settings.makePath('statistics', name));
        },
        toggleItemsList: function() {
            this.setState({showItems: !this.state.showItems});
        },
        componentWillMount: function() {
            var settings = this.props.statistics || this.props.tracking;
            this.configModels = {
                fuel_settings: settings,
                version: app.version,
                default: settings
            };
        },
        getError: function(settings, name) {
            return (settings.validationError || {})[settings.makePath('statistics', name)];
        },
        getText: function(key) {
            if (_.contains(app.version.get('feature_groups'), 'mirantis')) return i18n(key);
            return i18n(key + '_community');
        },
        renderInput: function(settingName, labelClassName, wrapperClassName, disabledState) {
            var settings = this.props.statistics || this.props.tracking,
                setting = settings.get(settings.makePath('statistics', settingName));
            if (this.checkRestrictions('metadata', 'hide').result || this.checkRestrictions(settingName, 'hide').result || setting.type == 'hidden') return null;
            var error = this.getError(settings, settingName),
                disabled = this.checkRestrictions('metadata').result || this.checkRestrictions(settingName).result || disabledState;
            return <controls.Input
                key={settingName}
                type={setting.type}
                name={settingName}
                label={setting.label && this.getText(setting.label)}
                checked={!disabled && setting.value}
                value={setting.value}
                disabled={disabled}
                inputClassName={setting.type == 'text' && 'input-xlarge'}
                labelClassName={labelClassName}
                wrapperClassName={wrapperClassName}
                onChange={this.onCheckboxChange}
                error={error && i18n(error)}
            />;
        },
        renderList: function(list, key) {
            return (
                <p key={key}>
                    {i18n('statistics.' + key + '_title')}
                    <ul>
                        {_.map(list, function(item) {
                            return <li key={item}>{i18n('statistics.' + key + '.' + item)}</li>;
                        })}
                    </ul>
                </p>
            );
        },
        renderIntro: function() {
            var ns = 'statistics.',
                isMirantisIso = _.contains(app.version.get('feature_groups'), 'mirantis'),
                lists = {
                    actions: [
                        'operation_type',
                        'operation_time',
                        'actual_time',
                        'network_verification',
                        'ostf_results'
                    ],
                    settings: [
                        'envronments_amount',
                        'nistribution',
                        'network_type',
                        'kernel_parameters',
                        'admin_network_parameters',
                        'pxe_parameters',
                        'dns_parameters',
                        'storage_options',
                        'related_projects',
                        'modified_settings',
                        'networking_configuration'
                    ],
                    node_settings: [
                        'deployed_nodes_amount',
                        'deployed_roles',
                        'disk_layout',
                        'interfaces_configuration'
                    ],
                    system_info: [
                        'hypervisor',
                        'hardware_info',
                        'fuel_version',
                        'openstack_version'
                    ]
                };
            return (
                <div>
                    <div className='statistics-text-box'>
                        <div className={utils.classNames({notice: isMirantisIso})}>{this.getText(ns + 'help_to_improve')}</div>
                        <button className='btn-link' onClick={this.toggleItemsList}>{i18n(ns + 'learn_whats_collected')}</button>
                        {this.state.showItems &&
                            <div className='statistics-disclaimer-box'>
                                <p>{i18n(ns + 'statistics_includes_full')}</p>
                                {_.map(lists, this.renderList)}
                            </div>
                        }
                    </div>
                </div>
            );
        },
        onCheckboxChange: function(name, value) {
            var settings = this.props.statistics || this.props.tracking;
            settings.set(settings.makePath('statistics', name, 'value'), value);
        },
        onTrackingSettingChange: function(name, value) {
            this.setState({error: null});
            var settings = this.props.tracking;
            var path = settings.makePath('tracking', name);
            delete (settings.validationError || {})[path];
            settings.set(settings.makePath(path, 'value'), value);
        },
        clearRegistrationForm: function() {
            if (!this.state.isConnected) {
                var settings = this.props.tracking,
                    initialData = this.props.settings.get('tracking');
                _.each(settings.get('tracking'), function(data, name) {
                    var path = settings.makePath('tracking', name, 'value');
                    settings.set(path, initialData[name].value);
                });
                settings.validationError = null;
            }
        },
        renderRegistrationForm: function(settings, disabled, error, showProgressBar) {
            var tracking = settings.get('tracking'),
                sortedFields = _.chain(_.keys(tracking))
                    .without('metadata')
                    .sortBy(function(inputName) {return tracking[inputName].weight;})
                    .value();
            return (
                <div>
                    {showProgressBar && <controls.ProgressBar />}
                    {error &&
                        <div className='error'>
                            <i className='icon-attention'></i>
                            {error}
                        </div>
                    }
                    <div className='connection-form'>
                        {_.map(sortedFields, function(inputName) {
                            return <controls.Input
                                ref={inputName}
                                key={inputName}
                                name={inputName}
                                disabled={disabled}
                                {... _.pick(tracking[inputName], 'type', 'label', 'value')}
                                onChange={this.onTrackingSettingChange}
                                error={(settings.validationError || {})[settings.makePath('tracking', inputName)]}
                            />;
                        }, this)}
                        <div className='links-container'>
                            <button className='btn btn-link create-account' onClick={this.showRegistrationDialog}>
                                {i18n('welcome_page.register.create_account')}
                            </button>
                            <button className='btn btn-link retrive-password' onClick={this.showRetrievePasswordDialog}>
                                {i18n('welcome_page.register.retrieve_password')}
                            </button>
                        </div>
                    </div>
                </div>
            );
        },
        showRegistrationDialog: function() {
            dialogs.RegistrationDialog.show({
                registrationForm: this.state.registrationForm,
                setConnected: _.bind(this.setConnected, this),
                settings: this.props.settings,
                tracking: this.props.tracking,
                saveSettings: _.bind(this.saveSettings, this)
            });
        },
        showRetrievePasswordDialog: function() {
            dialogs.RetrievePasswordDialog.show({
                remoteRetrievePasswordForm: this.state.remoteRetrievePasswordForm
            });
        }
    };
});
