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
    'component_mixins',
    'views/common',
    'models'
],
function(React, componentMixins, commonViews, models) {
    'use strict';

    var SupportPage, RegistrationLink, SupportContacts, DiagnosticSnapshot, CapacityAudit;

    var SupportPage = React.createClass({
        mixins: [React.BackboneMixin('tasks')],
        navbarActiveElement: 'support',
        breadcrumbsPath: [['home', '#'], 'support'],
        title: function() {
            return $.t('support_page.title');
        },
        render: function() {
            return (
                <div>
                    <h3 className='page-title'>{$.t('support_page.title')}</h3>
                    <div className='support-page page-wrapper'>
                        {_.contains(app.version.get('feature_groups'), 'mirantis') && <RegistrationLink /> + '<hr/>'}
                        <SupportContacts />
                        <hr/>
                        <DiagnosticSnapshot tasks={this.props.tasks} task={this.props.tasks.findTask({name: 'dump'})} />
                        <hr/>
                        <CapacityAudit />
                    </div>
                </div>
            );
        }
    });

    RegistrationLink = React.createClass({
        mixins: [React.BackboneMixin('fuelKey')],
        getInitialState: function() {
            return {fuelKey: new models.FuelKey()};
        },
        componentWillMount: function() {
            this.state.fuelKey.fetch();
        },
        render: function() {
            var fuelKey = this.state.fuelKey.get('key');
            return (
                <div className='row-fluid'>
                    <div className='span2 img img-register-fuel'></div>
                    <div className='span10'>
                        <h4>{$.t('support_page.register_fuel_title')}</h4>
                        <p>{$.t('support_page.register_fuel_content')}</p>
                        <p>
                            <a className='btn registration-link' href={!_.isUndefined(fuelKey) ? 'http://fuel.mirantis.com/create-subscriber/?key=' + fuelKey : '/'} target='_blank'>
                                {$.t('support_page.register_fuel_title')}
                            </a>
                        </p>
                    </div>
                </div>
            );
        }
    });

    SupportContacts = React.createClass({
        render: function() {
            return (
                <div className='row-fluid'>
                    <div className='span2 img img-contact-support'></div>
                    <div className='span10'>
                        <h4>{$.t('support_page.contact_support')}</h4>
                        <p>{$.t('support_page.contact_text')}</p>
                        <p>{$.t('support_page.irc_text')} <strong>#fuel</strong> on <a href='http://freenode.net' target='_blank'>freenode.net</a>.</p>
                        <p><a className='btn' href='https://mirantis.zendesk.com/requests/new' target='_blank'>{$.t('support_page.contact_support')}</a></p>
                    </div>
              </div>
            );
        }
    });

    DiagnosticSnapshot = React.createClass({
        mixins: [
            React.BackboneMixin('task'),
            componentMixins.pollingMixin(2)
        ],
        shouldDataBeFetched: function() {
            return this.props.task && this.props.task.match({status: 'running'});
        },
        fetchData: function() {
            if (this.props.task && this.props.task.match({status: 'running'})) {
                return this.props.task.fetch();
            }
        },
        componentDidUpdate: function() {
            this.startPolling();
        },
        downloadLogs: function() {
            this.props.tasks.reset();
            var task = new models.LogsPackage();
            task.save({}, {method: 'PUT'}).always(_.bind(function() {
                this.props.tasks.fetch().done(_.bind(this.startPolling, this));
            }, this));
            this.startPolling();
        },
        render: function() {
            var task = this.props.task;
            return (
                <div className='row-fluid snapshot'>
                    <div className='span2 img img-download-logs'></div>
                    <div className='span10'>
                        <h4>{$.t('support_page.download_diagnostic_snapshot_text')}</h4>
                        <p>{$.t('support_page.log_text')}</p>
                        <p>
                            {task && task.match({status: 'running'}) ?
                                <button className='btn' disabled>{$.t('support_page.gen_logs_snapshot_text')}</button>
                                :
                                <button className='btn' onClick={this.downloadLogs}>{$.t('support_page.gen_diagnostic_snapshot_text')}</button>
                            }
                            {task && task.match({status: 'ready'}) &&
                                <span>
                                    <a href={task.get('message')}>
                                        <i className='icon-install'></i>
                                        <span>{$.t('support_page.diagnostic_snapshot')}</span>
                                    </a>
                                </span>
                            }
                            {task && task.match({status: 'error'}) &&
                                <span className='error'>{task.get('message')}</span>
                            }
                        </p>
                    </div>
                </div>
            );
        }
    });

    CapacityAudit = React.createClass({
        render: function() {
            return (
                <div className='row-fluid'>
                    <div className='span2 img img-audit-logs'></div>
                    <div className='span10'>
                        <h4>{$.t('support_page.capacity_audit')}</h4>
                        <p>{$.t('support_page.capacity_audit_text')}</p>
                        <p><a className='btn' href='#capacity'>{$.t('support_page.view_capacity_audit')}</a></p>
                    </div>
                </div>
            );
        }
    });

    return SupportPage;
});
