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
    'jsx!views/controls'
], function($, _, i18n, React, utils, models, controls) {
    'use strict';

    return {
        propTypes: {
            settings: React.PropTypes.object.isRequired
        },
        getInitialState: function() {
            return {
                loading: true,
                actionInProgress: false,
                showItems: false
            };
        },
        saveSettings: function(e) {
            if (e) e.preventDefault();
            return this.props.settings.save(null, {patch: true, wait: true, validate: false})
                .done(this.updateInitialAttributes)
                .fail(function(response) {
                    utils.showErrorDialog({response: response});
                });
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
        saveConnected: function(response) {
            var registrationData = this.props.settings.get('statistics');
            _.each(response, function(value, name) {
                if (name != 'password') registrationData[name].value = value;
            });
            this.saveSettings()
                .done(_.bind(function() {
                    this.setState({isConnected: true});
                }, this))
                .fail(_.bind(function() {
                    this.setState({error: i18n('common.error')});
                }, this));
        },
        connectToMirantis: function(e) {
            if (e) e.preventDefault();
            var settings = this.props.settings,
                loginInfo = this.props.settings.get('tracking'),
                remoteLoginForm = this.props.remoteLoginForm;
            this.setState({error: null});
            if (settings.isValid({models: this.configModels})) {
                this.setState({actionInProgress: true});
                _.each(loginInfo, function(data, inputName) {
                    var name = remoteLoginForm.makePath('credentials', inputName, 'value');
                    remoteLoginForm.set(name, loginInfo[inputName].value);
                }, this);
                remoteLoginForm.save()
                    .done(_.bind(this.saveConnected, this))
                    .fail(this.showResponseErrors)
                    .always(_.bind(function() {
                        this.setState({actionInProgress: false});
                    }, this));
            }
        },
        onSettingChange: function(name, value) {
            this.setState({actionInProgress: false});
            this.props.settings.set(this.props.settings.makePath('statistics', name, 'value'), value);
        },
        checkRestrictions: function(name, action) {
            action = action || 'disable';
            return this.props.settings.checkRestrictions(this.configModels, action, this.props.settings.makePath('statistics', name));
        },
        toggleItemsList: function(e) {
            e.preventDefault();
            this.setState({showItems: !this.state.showItems});
        },
        hasChanges: function() {
            return this.state.loading ? false : this.props.settings.hasChanges(this.initialAttributes, this.configModels);
        },
        updateInitialAttributes: function() {
            this.initialAttributes = _.cloneDeep(this.props.settings.attributes);
        },
        componentWillUnmount: function() {
            this.props.settings.set(_.cloneDeep(this.initialAttributes), {silent: true});
        },
        componentDidMount: function() {
            this.props.settings.fetch({cache: true})
                .always(_.bind(function() {
                    this.configModels = {
                        fuel_settings: this.props.settings,
                        version: app.version,
                        default: this.props.settings
                    };
                    this.updateInitialAttributes();
                    this.setState({loading: false});
                }, this));
        },
        getError: function(name) {
            return this.props.settings.validationError && this.props.settings.validationError[this.props.settings.makePath('statistics', name)];
        },
        getText: function(key) {
            if (_.contains(app.version.get('feature_groups'), 'mirantis')) return i18n(key);
            return i18n(key + '_community');
        },
        renderInput: function(settingName, labelClassName, wrapperClassName, disabledState) {
            var setting = this.props.settings.get(this.props.settings.makePath('statistics', settingName));
            if (this.checkRestrictions('metadata', 'hide').result || this.checkRestrictions(settingName, 'hide').result || setting.type == 'hidden') return null;
            var error = this.getError(settingName),
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
                onChange={this.onSettingChange}
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
                        <button className="btn-link" onClick={this.toggleItemsList}>{i18n(ns + 'learn_whats_collected')}</button>
                        {this.state.showItems &&
                            <div className='statistics-disclaimer-box'>
                                <p>{i18n(ns + 'statistics_includes_full')}</p>
                                {_.map(lists, this.renderList)}
                            </div>
                        }
                    </div>
                </div>
            );
        }
    };
});
