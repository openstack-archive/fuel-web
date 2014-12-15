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
                return $.Deferred().reject();
            }
            this.setState({actionInProgress: true});
            return this.props.settings.save(null, {patch: true, wait: true, validate: false})
                .done(this.updateInitialSettings)
                .fail(function() {
                    this.setState({actionInProgress: false});
                    utils.showErrorDialog();
                });
        },
        onSettingChange: function(name, value) {
            this.setState({actionInProgress: false});
            this.props.settings.set(this.props.settings.makePath('statistics', name, 'value'), value);
            this.props.settings.isValid({models: this.configModels});
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
            return !_.isEqual(this.props.settings.toJSON().settings, this.initialSettings);
        },
        updateInitialSettings: function() {
            this.initialSettings = _.cloneDeep(this.props.settings.attributes);
        },
        componentWillUnmount: function() {
            this.props.settings.set(_.cloneDeep(this.initialSettings), {silent: true});
        },
        componentDidMount: function() {
            this.props.settings.fetch({cache: true})
                .always(_.bind(function() {
                    this.props.settings.processRestrictions();
                    this.configModels = {
                        fuel_settings: this.props.settings,
                        version: app.version,
                        default: this.props.settings
                    };
                    this.updateInitialSettings();
                    this.setState({loading: false});
                }, this));
        },
        getError: function(name) {
            return this.props.settings.validationError && this.props.settings.validationError[this.props.settings.makePath('statistics', name)];
        },
        getText: function(key) {
            if (_.contains(app.version.get('feature_groups'), 'mirantis')) return $.t(key);
            return $.t(key + '_community');
        },
        renderInput: function(settingName, labelClassName, wrapperClassName, hideErrors) {
            if (this.checkRestrictions('metadata', 'hide') || this.checkRestrictions(settingName, 'hide')) return null;
            var setting = this.props.settings.get(this.props.settings.makePath('statistics', settingName)),
                error = this.getError(settingName),
                disabled = this.checkRestrictions('metadata') || this.checkRestrictions(settingName);
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
                error={error ? hideErrors ? '' : $.t(error) : null}
            />;
        },
        renderList: function(list, key) {
            return (
                <p key={key}>
                    {$.t('statistics.' + key + '_title')}
                    <ul>
                        {_.map(list, function(item) {
                            return <li key={item}>{$.t('statistics.' + key + '.' + item)}</li>;
                        })}
                    </ul>
                </p>
            );
        },
        renderIntro: function() {
            var ns = 'statistics.',
                isMirantisIso = _.contains(app.version.get('feature_groups'), 'mirantis'),
                statsCollectorLink = 'https://stats.fuel-infra.org/',
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
                        <p>{this.getText(ns + 'help_to_improve')}</p>
                        <p>
                            {$.t(ns + 'statistics_includes')}
                            <a onClick={this.toggleItemsList}>{$.t(ns + 'click_here')}</a>.
                        </p>
                        {isMirantisIso ?
                            <p>
                                {$.t(ns + 'privacy_policy')}
                                <a href='https://www.mirantis.com/company/privacy-policy/' target='_blank'>{$.t(ns + 'privacy_policy_link')}</a>.
                            </p>
                        :
                            <p>
                                {$.t(ns + 'statistics_collector')}
                                <a href={statsCollectorLink} target='_blank'>{statsCollectorLink}</a>.
                            </p>
                        }
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
