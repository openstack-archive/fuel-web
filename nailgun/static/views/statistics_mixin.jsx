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
            return {statsCheckboxes: ['send_anonymous_statistic', 'send_user_info']};
        },
        getInitialState: function() {
            var tracking = this.props.settings.get('tracking');
            return {
                isConnected: !!(tracking.email.value && tracking.password.value),
                actionInProgress: false,
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
            _.each(this.props.statsCheckboxes, function(field) {
                var path = this.props.settings.makePath('statistics', field, 'value');
                this.props.settings.set(path, this.props.statistics.get(path));
            }, this);
            return this.saveSettings(currentAttributes);
        },
        prepareTrackingToSave: function(response) {
            var currentAttributes = _.cloneDeep(this.props.settings.attributes);
            // Saving user contact data to Statistics section
            _.each(response, function(value, name) {
                if (name != 'password') {
                    var path = this.props.settings.makePath('statistics', name, 'value');
                    this.props.settings.set(path, value);
                    this.props.tracking.set(path, value);
                }
            }, this);
            // Saving email and password to Tracking section
            _.each(this.props.tracking.get('tracking'), function(data, inputName) {
                var path = this.props.settings.makePath('tracking', inputName, 'value');
                this.props.settings.set(path, this.props.tracking.get(path));
            }, this);
            this.saveSettings(currentAttributes).done(this.setConnected);
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
            var tracking = this.props.tracking.get('tracking');
            if (this.props.tracking.isValid({models: this.configModels})) {
                var remoteLoginForm = this.state.remoteLoginForm;
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
        componentWillMount: function() {
            var model = this.props.statistics || this.props.tracking;
            this.configModels = {
                fuel_settings: model,
                version: app.version,
                default: model
            };
        },
        getError: function(model, name) {
            return (model.validationError || {})[model.makePath('statistics', name)];
        },
        getText: function(key) {
            if (_.contains(app.version.get('feature_groups'), 'mirantis')) return i18n(key);
            return i18n(key + '_community');
        },
        renderInput: function(settingName, wrapperClassName, disabledState) {
            var model = this.props.statistics || this.props.tracking,
                setting = model.get(model.makePath('statistics', settingName));
            if (this.checkRestrictions('metadata', 'hide').result || this.checkRestrictions(settingName, 'hide').result || setting.type == 'hidden') return null;
            var error = this.getError(model, settingName),
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
                        <button className='btn-link' data-toggle='collapse' data-target='.statistics-disclaimer-box'>{i18n(ns + 'learn_whats_collected')}</button>
                        <div className='collapse statistics-disclaimer-box'>
                            <p>{i18n(ns + 'statistics_includes_full')}</p>
                            {_.map(lists, this.renderList)}
                            <p>{i18n(ns + 'statistics_user_info')}</p>
                        </div>
                    </div>
                </div>
            );
        },
        onCheckboxChange: function(name, value) {
            var model = this.props.statistics || this.props.tracking;
            model.set(model.makePath('statistics', name, 'value'), value);
        },
        onTrackingSettingChange: function(name, value) {
            this.setState({error: null});
            var path = this.props.tracking.makePath('tracking', name);
            delete (this.props.tracking.validationError || {})[path];
            this.props.tracking.set(this.props.tracking.makePath(path, 'value'), value);
        },
        clearRegistrationForm: function() {
            if (!this.state.isConnected) {
                var tracking = this.props.tracking,
                    initialData = this.props.settings.get('tracking');
                _.each(tracking.get('tracking'), function(data, name) {
                    var path = tracking.makePath('tracking', name, 'value');
                    tracking.set(path, initialData[name].value);
                });
                tracking.validationError = null;
            }
        },
        renderRegistrationForm: function(model, disabled, error, showProgressBar) {
            var tracking = model.get('tracking'),
                sortedFields = _.chain(_.keys(tracking))
                    .without('metadata')
                    .sortBy(function(inputName) {return tracking[inputName].weight;})
                    .value();
            return (
                <div>
                    {error &&
                        <div className='text-danger'>
                            <i className='glyphicon glyphicon-warning-sign' />
                            {error}
                        </div>
                    }
                    <div className='connection-form'>
                        {showProgressBar && <controls.ProgressBar />}
                        {_.map(sortedFields, function(inputName) {
                            return <controls.Input
                                ref={inputName}
                                key={inputName}
                                name={inputName}
                                disabled={disabled}
                                {... _.pick(tracking[inputName], 'type', 'label', 'value')}
                                onChange={this.onTrackingSettingChange}
                                error={(model.validationError || {})[model.makePath('tracking', inputName)]}
                            />;
                        }, this)}
                        <div className='links-container'>
                            <button className='btn btn-link create-account pull-left' onClick={this.showRegistrationDialog}>
                                {i18n('welcome_page.register.create_account')}
                            </button>
                            <button className='btn btn-link retrive-password pull-right' onClick={this.showRetrievePasswordDialog}>
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
                setConnected: this.setConnected,
                settings: this.props.settings,
                tracking: this.props.tracking,
                saveSettings: this.saveSettings
            });
        },
        showRetrievePasswordDialog: function() {
            dialogs.RetrievePasswordDialog.show({
                remoteRetrievePasswordForm: this.state.remoteRetrievePasswordForm
            });
        }
    };
});
