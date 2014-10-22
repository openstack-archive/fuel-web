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
    'react',
    'utils',
    'models',
    'jsx!views/controls'
], function($, _, React, utils, models, controls) {
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
            e.preventDefault();
            this.props.settings.isValid({models: this.configModels});
            if (this.props.settings.validationError) {
                this.forceUpdate();
                return (new $.Deferred()).reject();
            }
            this.setState({actionInProgress: true});
            return this.props.settings.save(null, {patch: true, wait: true, validate: false})
                .fail(function() {
                    this.setState({actionInProgress: false});
                    utils.showErrorDialog();
                });
        },
        onSettingChange: function(name, value) {
            this.setState({actionInProgress: false});
            this.props.settings.set(utils.makePath(name, 'value'), value);
            this.props.settings.isValid({models: this.configModels});
        },
        checkRestrictions: function(name, action) {
            action = action || 'disable';
            return this.props.settings.checkRestrictions(this.configModels, action, name);
        },
        get: function() {
            return this.props.settings.get(utils.makePath.apply(utils, arguments));
        },
        toggleItemsList: function(e) {
            e.preventDefault();
            this.setState({showItems: !this.state.showItems});
        },
        componentDidMount: function() {
            this.props.settings.fetch({cache: true})
                .always(_.bind(function() {
                    this.props.settings.processRestrictions();
                    this.configModels = {
                        master_node_settings: this.props.settings,
                        version: app.version,
                        default: this.props.settings
                    };
                    this.setState({loading: false});
                }, this));
        },
        renderInput: function(setting, groupName, settingName, labelClassName, wrapperClassName, hideErrors) {
            var name = utils.makePath(groupName, settingName),
                visible = !(this.checkRestrictions(utils.makePath(groupName, 'metadata'), 'hide') || this.checkRestrictions(name, 'hide'));
            if (!visible) return null;
            var errors = this.props.settings.validationError,
                disabled = this.checkRestrictions(utils.makePath(groupName, 'metadata')) || this.checkRestrictions(name);
            return this.checkRestrictions() ? null : (
                <controls.Input
                    key={name}
                    type={setting.type}
                    name={name}
                    label={setting.label}
                    checked={!disabled && setting.value}
                    value={setting.value}
                    disabled={disabled}
                    inputClassName={setting.type == 'text' && 'input-xlarge'}
                    labelClassName={labelClassName}
                    wrapperClassName={wrapperClassName}
                    onChange={this.onSettingChange}
                    error={(errors && errors[name]) ? hideErrors ? '' : errors[name] : null}
                />
            );
        },
        renderList: function(list, key) {
            return (
                <p key={key}>
                    {$.t('welcome_page.' + key + '_title')}
                    <ul>
                        {_.map(list, function(item) {
                            return <li key={item}>{$.t('welcome_page.' + key + '.' + item)}</li>;
                        })}
                    </ul>
                </p>
            );
        },
        renderIntro: function() {
            var ns = 'statistics.',
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
                        <p>{$.t(ns + 'help_to_improve')}</p>
                        <p>
                            {$.t(ns + 'statistics_includes')}
                            <a onClick={this.toggleItemsList}>{$.t(ns + 'click_here')}</a>.
                        </p>
                        <p>
                            {$.t(ns + 'privacy_policy')}
                            <a href='https://www.mirantis.com/company/privacy-policy/' target='_blank'>{$.t(ns + 'privacy_policy_link')}</a>.
                        </p>
                    </div>
                    {this.state.showItems &&
                        <div className='statistics-disclaimer-box'>
                            <p>{$.t(ns + 'statistics_includes_full')}</p>
                            {_.map(lists, this.renderList)}
                        </div>
                    }
                </div>
            );
        }
    };
});
