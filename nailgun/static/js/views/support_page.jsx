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
    'utils',
    'jsx!views/dialogs',
    'jsx!component_mixins',
    'models',
    'jsx!views/statistics_mixin'
],
function($, _, i18n, Backbone, React, utils, dialogs, componentMixins, models, statisticsMixin) {
    'use strict';

    var SupportPage = React.createClass({
        mixins: [
            componentMixins.backboneMixin('tasks')
        ],
        statics: {
            title: i18n('support_page.title'),
            navbarActiveElement: 'support',
            А: [['home', '#'], 'support'],
            fetchData: function() {
                var tasks = new models.Tasks();
                return $.when(app.settings.fetch(), tasks.fetch()).then(function() {
                    return {
                        tasks: tasks,
                        settings: app.settings,
                        masterNodeUid: app.masterNodeUid
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
                    <RegistrationInfo key='RegistrationInfo' {... _.pick(this.props, 'settings', 'masterNodeUid')}/>,
                    <StatisticsSettings key='StatisticsSettings' settings={this.props.settings}/>,
                    <SupportContacts key='SupportContacts' />
                );
            } else {
                elements.push(<StatisticsSettings key='StatisticsSettings' settings={this.props.settings} />);
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
            componentMixins.backboneMixin('settings', 'change invalid')
        ],
        onChange: function(inputName, value) {
            this.setState({error: null});
            var settings = this.props.settings,
                name = settings.makePath('tracking', inputName, 'value');
            if (settings.validationError) delete settings.validationError['tracking.' + inputName];
            settings.set(name, value);
        },
        setConnected: function() {
            this.setState({isConnected: true});
        },
        render: function() {
            var settings = this.props.settings,
                registrationInfo = settings.get('statistics'),
                masterNodeUid = settings.get('master_node_uid'),
                values = ['name', 'email', 'company'];
            if (this.state.loading) return null;
            if (this.state.isConnected)
                return (
                    <SupportPageElement
                        className='img-register-fuel'
                        title={i18n('support_page.product_registered_title')}
                        text={i18n('support_page.product_registered_content')}
                    >
                        <p className='registeredData enable-selection'>
                            {_.map(values, function(value) {
                                return <span key={value}><b>{i18n('statistics.setting_labels.' + value)}:</b> {registrationInfo[value].value}</span>;
                            }, this)}
                            <span key='masterNodeUid'><b>{i18n('support_page.master_node_uuid')}:</b> {masterNodeUid}</span>
                        </p>
                        <p>
                            <a className='btn registration-link' href='https://software.mirantis.com/account/' target='_blank'>
                                {i18n('support_page.manage_account')}
                            </a>
                        </p>
                    </SupportPageElement>
                );
            var actionInProgress = this.state.actionInProgress;
            return (
                <SupportPageElement
                    className='img-register-fuel'
                    title={i18n('support_page.register_fuel_title')}
                    text={i18n('support_page.register_fuel_content')}
                >
                    <div>
                        {this.renderRegistrationForm(settings, actionInProgress, this.state.error)}
                        <p>
                            <a className='btn registration-link' onClick={this.connectToMirantis} disabled={actionInProgress} target='_blank'>
                                {i18n('support_page.register_fuel_title')}
                            </a>
                        </p>
                    </div>
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
                        <a className='btn' href='https://mirantis.zendesk.com/requests/new' target='_blank'>
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

    var StatisticsSettings = React.createClass({
        mixins: [
            statisticsMixin,
            componentMixins.backboneMixin('settings')
        ],
        onBeforeunloadEvent: function() {
            if (this.hasChanges()) return i18n('dialog.dismiss_settings.default_message');
        },
        onPageLeave: function(e) {
            var href = $(e.currentTarget).attr('href');
            if (Backbone.history.getHash() != href.substr(1) && this.statisticsCheckboxesHasChanges()) {
                e.preventDefault();
                dialogs.DiscardSettingsChangesDialog.show({cb: function() {app.navigate(href, {trigger: true});}});
            }
        },
        componentWillMount: function() {
            $(window).on('beforeunload.support', _.bind(this.onBeforeunloadEvent, this));
            $('body').on('click.support', 'a[href^=#]', _.bind(this.onPageLeave, this));
        },
        componentWillUnmount: function() {
            $(window).off('beforeunload.support');
            $('body').off('click.support');
        },
        onSaveButtonClick: function(e) {
            if (e) e.preventDefault();
            this.prepareSettingsToSave('statistics');
        },
        render: function() {
            if (this.state.loading) return null;
            var statisticsSettings = this.props.settings.get('statistics'),
                sortedSettings = _.chain(_.keys(statisticsSettings))
                    .without('metadata')
                    .sortBy(function(settingName) {return statisticsSettings[settingName].weight;}, this)
                    .value();
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
                        <a className='btn' disabled={this.state.actionInProgress || !this.statisticsCheckboxesHasChanges()} onClick={this.onSaveButtonClick}>
                            {i18n('support_page.save_changes')}
                        </a>
                    </p>
                </SupportPageElement>
            );
        }
    });

    return SupportPage;
});
