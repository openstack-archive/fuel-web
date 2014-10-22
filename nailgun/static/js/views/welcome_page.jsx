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
    'jsx!views/controls'
],
function($, React, controls) {
    'use strict';

    var WelcomePage = React.createClass({
        breadcrumbsPath: [],
        title: function() {
            return $.t('welcome_page.title');
        },
        getInitialState: function() {
            return {
                error: false,
                actionInProgress: false
            };
        },
        onStartButtonClick: function(e) {
            e.preventDefault();
            this.setState({error: false, actionInProgress: true});
            var userData = {},
                error;
            _.each(this.refs, function(control, key) {
                var input = control.refs.input.getDOMNode();
                userData[key] = input.type == 'checkbox' ? input.checked : input.value;
                // TODO: implement contacts validation
                if (!_.isBoolean(userData[key]) && userData[key] == '') error = error || key;
            });
            if (error) {
                this.setState({error: error, actionInProgress: false});
            } else {
                // TODO: send user data to backend
                app.navigate('#clusters', {trigger: true});
            }
        },
        removeError: function() {
            this.setState({error: false});
        },
        renderCheckbox: function(name) {
            return <controls.Input
                type='checkbox'
                ref={name}
                name={name}
                label={$.t('welcome_page.' + name)}
                wrapperClassName='welcome-checkbox-box'
            />;
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
                };
            // TODO: insert a correct link
            return (
                <div className='welcome-page'>
                    <div>
                        <h2 className='center'>{$.t(ns + 'title')}</h2>
                        <div className='welcome-text-box'>
                            <p>{$.t(ns + 'help_to_improve')}</p>
                            <p>{$.t(ns + 'statistics_includes_full')}<a href='#' target="_blank">{$.t(ns + 'click_here')}</a>.</p>
                        </div>
                        <div className='welcome-disclaimer-box'>
                            <p>{$.t(ns + 'statistics_includes')}</p>
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
                        {this.renderCheckbox('send_statistics')}
                        <div className='welcome-text-box'>
                            <p className='center'>
                                {$.t(ns + 'support')}<br/>
                                {$.t(ns + 'provide_contacts')}
                            </p>
                        </div>
                        {this.renderCheckbox('identify_errors')}
                        <form className='form-horizontal'>
                            {_.map(['name', 'email', 'company'], function(data) {
                                return (
                                    <controls.Input
                                        type='text'
                                        key={data}
                                        ref={data}
                                        name={data}
                                        label={$.t(ns + 'contacts.' + data)}
                                        inputClassName='input-xlarge'
                                        labelClassName='welcome-form-item'
                                        wrapperClassName='welcome-form-box'
                                        onChange={this.removeError}
                                    />
                                );
                            }, this)}
                            {this.state.error &&
                                <div className='welcome-form-error'>{$.t(ns + 'invalid') + this.state.error}</div>
                            }
                            <div className='welcome-button-box'>
                                <button className='btn btn-large btn-success' disabled={this.state.actionInProgress} onClick={this.onStartButtonClick}
                                >{$.t(ns + 'start_fuel')}</button>
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
