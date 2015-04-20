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
define(
[
    'jquery',
    'underscore',
    'i18n',
    'backbone',
    'react',
    'jsx!views/dialogs',
    'jsx!component_mixins',
    'models',
    'jsx!views/statistics_mixin'
],
function($, _, i18n, Backbone, React, dialogs, componentMixins, models, statisticsMixin) {
    'use strict';

    var SupportPage = React.createClass({
        mixins: [
            componentMixins.backboneMixin('tasks')
        ],
        statics: {
            title: i18n('support_page.title'),
            navbarActiveElement: 'support',
            breadcrumbsPath: [['home', '#'], 'support'],
            fetchData: function() {
                var tasks = new models.Tasks();
                return $.when(app.settings.fetch({cache: true}), tasks.fetch()).then(function() {
                    var tracking = new models.FuelSettings(_.cloneDeep(app.settings.attributes)),
                        statistics = new models.FuelSettings(_.cloneDeep(app.settings.attributes));
                    tracking.processRestrictions();
                    return {
                        tasks: tasks,
                        settings: app.settings,
                        tracking: tracking,
                        statistics: statistics
                    };
                });
            }
        },
        render: function() {
            var elements = [
                <DocumentationLink key='DocumentationLink' />,
                <DiagnosticSnapshot key='DiagnosticSnapshot' tasks={this.props.tasks} task={this.props.tasks.findTask({name: 'dump'})} />,
                <CapacityAudit key='CapacityAudit' />
            ];
            if (_.contains(app.version.get('feature_groups'), 'mirantis')) {
                elements.unshift(
                    <RegistrationInfo key='RegistrationInfo' settings={this.props.settings} tracking={this.props.tracking}/>,
                    <StatisticsSettings key='StatisticsSettings' settings={this.props.settings} statistics={this.props.statistics}/>,
                    <SupportContacts key='SupportContacts' />
                );
            } else {
                elements.push(<StatisticsSettings key='StatisticsSettings' settings={this.props.settings} statistics={this.props.statistics}/>);
            }
            return (
                <div>
                    <h3 className='page-title'>{i18n('support_page.title')}</h3>
                    <div className='support-page page-wrapper'>{elements}</div>
                </div>
            );
        }
    });

    var SupportPageElement = React.createClass({
        render: function() {
            return (
                <div className='row-fluid'>
                    <div className={'span2 img ' + this.props.className}></div>
                    <div className='span10 el-inner'>
                        <h4>{this.props.title}</h4>
                        <p>{this.props.text}</p>
                        {this.props.children}
                    </div>
                    <hr/>
                </div>
            );
        }
    });

    var DocumentationLink = React.createClass({
        render: function() {
            var ns = 'support_page.' + (_.contains(app.version.get('feature_groups'), 'mirantis') ? 'mirantis' : 'community') + '_';
            return (
                <SupportPageElement
                    className='img-documentation-link'
                    title={i18n(ns + 'title')}
                    text={i18n(ns + 'text')}
                >
                    <p>
                        <a className='btn' href='https://www.mirantis.com/openstack-documentation/' target='_blank'>
                            {i18n('support_page.documentation_link')}
                        </a>
                    </p>
                </SupportPageElement>
            );
        }
    });

    var RegistrationInfo = React.createClass({
        mixins: [
            statisticsMixin,
            componentMixins.backboneMixin('tracking', 'change invalid')
        ],
        render: function() {
            if (this.state.isConnected)
                return (
                    <SupportPageElement
                        className='img-register-fuel'
                        title={i18n('support_page.product_registered_title')}
                        text={i18n('support_page.product_registered_content')}
                    >
                        <p className='registeredData enable-selection'>
                            {_.map(['name', 'email', 'company'], function(value) {
                                return <span key={value}><b>{i18n('statistics.setting_labels.' + value)}:</b> {this.props.tracking.get('statistics')[value].value}</span>;
                            }, this)}
                            <span><b>{i18n('support_page.master_node_uuid')}:</b> {this.props.tracking.get('master_node_uid')}</span>
                        </p>
                        <p>
                            <a className='btn registration-link' href='https://software.mirantis.com/account/' target='_blank'>
                                {i18n('support_page.manage_account')}
                            </a>
                        </p>
                    </SupportPageElement>
                );
            return (
                <SupportPageElement
                    className='img-register-fuel'
                    title={i18n('support_page.register_fuel_title')}
                    text={i18n('support_page.register_fuel_content')}
                >
                    <div>
                        {this.renderRegistrationForm(this.props.tracking, this.state.actionInProgress, this.state.error, this.state.actionInProgress)}
                        <p>
                            <button className='btn registration-link' onClick={this.connectToMirantis} disabled={this.state.actionInProgress} target='_blank'>
                                {i18n('support_page.register_fuel_title')}
                            </button>
                        </p>
                    </div>
                </SupportPageElement>
            );
        }
    });

    var StatisticsSettings = React.createClass({
        mixins: [
            statisticsMixin,
            componentMixins.backboneMixin('statistics')
        ],
        render: function() {
            var statistics = this.props.statistics.get('statistics'),
                sortedSettings = _.chain(_.keys(statistics))
                    .without('metadata')
                    .sortBy(function(settingName) {return statistics[settingName].weight;}, this)
                    .value(),
                initialData = this.props.settings.get('statistics'),
                hasChanges = _.any(this.props.fields, function(field) {
                    return !_.isEqual(initialData[field].value, statistics[field].value);
                });
            return (
                <SupportPageElement
                    className='img-statistics'
                    title={i18n('support_page.send_statistics_title')}
                >
                    {this.renderIntro()}
                    <div className='statistics-settings'>
                        {_.map(sortedSettings, this.renderInput, this)}
                    </div>
                    <p>
                        <button
                            className='btn'
                            disabled={this.state.actionInProgress || !hasChanges}
                            onClick={this.prepareStatisticsToSave}
                        >
                            {i18n('support_page.save_changes')}
                        </button>
                    </p>
                </SupportPageElement>
            );
        }
    });

    var SupportContacts = React.createClass({
        render: function() {
            return (
                <SupportPageElement
                    className='img-contact-support'
                    title={i18n('support_page.contact_support')}
                    text={i18n('support_page.contact_text')}
                >
                    <p>{i18n('support_page.irc_text')} <strong>#fuel</strong> on <a href='http://freenode.net' target='_blank'>freenode.net</a>.</p>
                    <p>
                        <a className='btn' href='http://support.mirantis.com' target='_blank'>
                            {i18n('support_page.contact_support')}
                        </a>
                    </p>
                </SupportPageElement>
            );
        }
    });

    var DiagnosticSnapshot = React.createClass({
        mixins: [
            componentMixins.backboneMixin('task'),
            componentMixins.pollingMixin(2)
        ],
        getInitialState: function() {
            return {generating: this.isDumpTaskRunning()};
        },
        shouldDataBeFetched: function() {
            return this.isDumpTaskRunning();
        },
        fetchData: function() {
            return this.props.task.fetch().done(_.bind(function() {
                if (!this.isDumpTaskRunning()) this.setState({generating: false});
            }, this));
        },
        isDumpTaskRunning: function() {
            return this.props.task && this.props.task.match({status: 'running'});
        },
        downloadLogs: function() {
            this.setState({generating: true});
            (new models.LogsPackage()).save({}, {method: 'PUT'}).always(_.bind(this.props.tasks.fetch, this.props.tasks));
        },
        componentDidUpdate: function() {
            this.startPolling();
        },
        render: function() {
            var task = this.props.task,
                generating = this.state.generating;
            return (
                <SupportPageElement
                    className='img-download-logs'
                    title={i18n('support_page.download_diagnostic_snapshot_text')}
                    text={i18n('support_page.log_text')}
                >
                    <p className='snapshot'>
                        <button className='btn' disabled={generating} onClick={this.downloadLogs}>
                            {generating ? i18n('support_page.gen_logs_snapshot_text') : i18n('support_page.gen_diagnostic_snapshot_text')}
                        </button>
                        {!generating && task &&
                            <span className={task.get('status')}>
                                {task.match({status: 'ready'}) &&
                                    <a href={task.get('message')} target='_blank'>
                                        <i className='icon-install'></i>
                                        <span>{i18n('support_page.diagnostic_snapshot')}</span>
                                    </a>
                                }
                                {task.match({status: 'error'}) && task.get('message')}
                            </span>
                        }
                    </p>
                </SupportPageElement>
            );
        }
    });

    var CapacityAudit = React.createClass({
        render: function() {
            return (
                <SupportPageElement
                    className='img-audit-logs'
                    title={i18n('support_page.capacity_audit')}
                    text={i18n('support_page.capacity_audit_text')}
                >
                    <p>
                        <a className='btn' href='#capacity'>
                            {i18n('support_page.view_capacity_audit')}
                        </a>
                    </p>
                </SupportPageElement>
            );
        }
    });

    return SupportPage;
});
