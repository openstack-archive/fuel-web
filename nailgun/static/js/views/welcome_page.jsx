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
    'jsx!views/statistics_mixin'
],
function($, React, statisticsMixin) {
    'use strict';

    var WelcomePage = React.createClass({
        mixins: [statisticsMixin],
        breadcrumbsPath: [],
        customLayout: true,
        title: function() {
            return $.t('welcome_page.title');
        },
        getInitialState: function() {
            return {
                errors: [],
                actionInProgress: false,
                sendStatistics: true,
                personalizeStatistics: true,
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
        componentWillMount: function() {
            this.ns = 'welcome_page.';
        },
        render: function() {
            var lists = {
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
                <div className='welcome-page'>
                    <div>
                        <h2 className='center'>{$.t(this.ns + 'title')}</h2>
                        <div className='welcome-text-box'>
                            <p>{$.t(this.ns + 'help_to_improve')}</p>
                            <p>
                                {$.t(this.ns + 'statistics_includes')}
                                <a onClick={this.toggleItemsList}>{$.t(this.ns + 'click_here')}</a>.
                            </p>
                        </div>
                        {this.state.showItems &&
                            <div className='welcome-disclaimer-box'>
                                <p>{$.t(this.ns + 'statistics_includes_full')}</p>
                                {_.map(lists, function(list, key) {
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
                                })}
                            </div>
                        }
                        {this.renderCheckbox('send_statistics', 'welcome-checkbox-box')}
                        <div className='welcome-text-box'>
                            <p className='center'>
                                {$.t(this.ns + 'support')}<br/>
                                {$.t(this.ns + 'provide_contacts')}
                            </p>
                        </div>
                        {this.renderCheckbox('personalize_statistics', 'welcome-checkbox-box')}
                        <form className='form-horizontal'>
                            {this.renderContactForm('welcome-form-item', 'welcome-form-box', true)}
                            {(this.state.personalizeStatistics && !!this.state.errors.length) &&
                                <div className='welcome-form-error'>{$.t(this.ns + 'errors.' + this.state.errors[0])}</div>
                            }
                            <div className='welcome-button-box'>
                                <button className='btn btn-large btn-success' disabled={this.state.actionInProgress} onClick={this.onStartButtonClick}>
                                    {$.t(this.ns + 'start_fuel')}
                                </button>
                            </div>
                        </form>
                        <div className='welcome-text-box'>
                            <p className='center'>
                                {$.t(this.ns + 'change_settings')}<br/>
                                {$.t(this.ns + 'thanks')}
                            </p>
                        </div>
                    </div>
                </div>
            );
        }
    });

    return WelcomePage;
});
