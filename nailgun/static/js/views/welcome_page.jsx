/*
 * Copyright 2014 Mirantis, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the 'License'); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an 'AS IS' BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
 **/
define(
[
    'jquery',
    'react',
    'utils',
    'jsx!views/statistics_mixin'
],
function($, React, utils, statisticsMixin) {
    'use strict';

    var WelcomePage = React.createClass({
        mixins: [
            statisticsMixin,
            React.BackboneMixin('settings')
        ],
        breadcrumbsPath: [],
        customLayout: true,
        title: function() {
            return $.t('welcome_page.title');
        },
        getInitialState: function() {
            return {
                actionInProgress: false,
                showItems: false
            };
        },
        onStartButtonClick: function(e) {
            this.saveSettings(e).done(function() {
                app.navigate('#clusters', {trigger: true});
            });
        },
        toggleItemsList: function(e) {
            e.preventDefault();
            this.setState({showItems: !this.state.showItems});
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
        render: function() {
            var ns = 'welcome_page.',
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
                },
                errors = this.props.settings.validationError;
            return (
                <div className='welcome-page'>
                    <div>
                        <h2 className='center'>{$.t(ns + 'title')}</h2>
                        <div className='welcome-text-box'>
                            <p>{$.t(ns + 'help_to_improve')}</p>
                            <p>
                                {$.t(ns + 'statistics_includes')}
                                <a onClick={this.toggleItemsList}>{$.t(ns + 'click_here')}</a>.
                            </p>
                        </div>
                        {this.state.showItems &&
                            <div className='welcome-disclaimer-box'>
                                <p>{$.t(ns + 'statistics_includes_full')}</p>
                                {_.map(lists, this.renderList)}
                            </div>
                        }
                        {this.renderInput(this.get('statistics', 'send_anonymous_statistic'), 'statistics', 'send_anonymous_statistic', null, 'welcome-checkbox-box')}
                        <div className='welcome-text-box'>
                            <p className='center'>
                                {$.t(ns + 'support')}<br/>
                                {$.t(ns + 'provide_contacts')}
                            </p>
                        </div>
                        {this.renderInput(this.get('statistics', 'send_user_info'), 'statistics', 'send_user_info', null, 'welcome-checkbox-box')}
                        <form className='form-horizontal'>
                            {_.chain(_.keys(this.get('user_info')))
                                .sortBy(function(settingName) {
                                    return this.get(settingName, 'weight');
                                }, this)
                                .without('metadata')
                                .map(function(settingName) {
                                    return this.renderInput(this.get('user_info', settingName), 'user_info', settingName, 'welcome-form-item', 'welcome-form-box', true);
                                }, this)
                                .value()
                            }
                            {errors &&
                                <div className='welcome-form-error'>{_.values(errors)[0]}</div>
                            }
                            <div className='welcome-button-box'>
                                <button className='btn btn-large btn-success' disabled={this.state.actionInProgress} onClick={this.onStartButtonClick}>
                                    {$.t(ns + 'start_fuel')}
                                </button>
                            </div>
                        </form>
                        <div className='welcome-text-box'>
                            <p className='center'>
                                {$.t(ns + 'change_settings')}<br/>
                                {$.t(ns + 'thanks')}
                            </p>
                        </div>
                    </div>
                </div>
            );
        }
    });

    return WelcomePage;
});
