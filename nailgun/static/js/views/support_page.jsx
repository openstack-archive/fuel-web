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
    'react',
    'jsx!component_mixins',
    'models',
    'jsx!views/controls',
    'jsx!views/statistics_mixin'
],
function(React, componentMixins, models, controls, statisticsMixin) {
    'use strict';

    var SupportPage = React.createClass({
        mixins: [React.BackboneMixin('tasks')],
        navbarActiveElement: 'support',
        breadcrumbsPath: [['home', '#'], 'support'],
        title: function() {
            return $.t('support_page.title');
        },
        render: function() {
            var elements = [
                <DiagnosticSnapshot key='DiagnosticSnapshot' tasks={this.props.tasks} task={this.props.tasks.findTask({name: 'dump'})} />,
                <CapacityAudit key='CapacityAudit' />,
                <StatisticsSettings key='StatisticsSettings' settings={this.props.settings} />
            ];
            if (_.contains(app.version.get('feature_groups'), 'mirantis')) {
                elements.unshift(
                    <RegistrationLink key='RegistrationLink' fuelKey={new models.FuelKey()}/>,
                    <SupportContacts key='SupportContacts' />
                );
            }
            return (
                <div>
                    <h3 className='page-title'>{$.t('support_page.title')}</h3>
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

    var RegistrationLink = React.createClass({
        mixins: [React.BackboneMixin('fuelKey')],
        componentDidMount: function() {
            this.props.fuelKey.fetch();
        },
        render: function() {
            var key = this.props.fuelKey.get('key');
            return (
                <SupportPageElement
                    className='img-register-fuel'
                    title={$.t('support_page.register_fuel_title')}
                    text={$.t('support_page.register_fuel_content')}
                >
                    <p><a className='btn registration-link' href={_.isUndefined(key) ? '/' : 'http://fuel.mirantis.com/create-subscriber/?key=' + key} target='_blank'>
                        {$.t('support_page.register_fuel_title')}
                    </a></p>
                </SupportPageElement>
            );
        }
    });

    var SupportContacts = React.createClass({
        render: function() {
            return (
                <SupportPageElement
                    className='img-contact-support'
                    title={$.t('support_page.contact_support')}
                    text={$.t('support_page.contact_text')}
                >
                    <p>{$.t('support_page.irc_text')} <strong>#fuel</strong> on <a href='http://freenode.net' target='_blank'>freenode.net</a>.</p>
                    <p><a className='btn' href='https://mirantis.zendesk.com/requests/new' target='_blank'>{$.t('support_page.contact_support')}</a></p>
                </SupportPageElement>
            );
        }
    });

    var DiagnosticSnapshot = React.createClass({
        mixins: [
            React.BackboneMixin('task'),
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
                    title={$.t('support_page.download_diagnostic_snapshot_text')}
                    text={$.t('support_page.log_text')}
                >
                    <p className='snapshot'>
                        <button className='btn' disabled={generating} onClick={this.downloadLogs}>
                            {generating ? $.t('support_page.gen_logs_snapshot_text') : $.t('support_page.gen_diagnostic_snapshot_text')}
                        </button>
                        {!generating && task &&
                            <span className={task.get('status')}>
                                {task.match({status: 'ready'}) &&
                                    <a href={task.get('message')} target='_blank'>
                                        <i className='icon-install'></i>
                                        <span>{$.t('support_page.diagnostic_snapshot')}</span>
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
                    title={$.t('support_page.capacity_audit')}
                    text={$.t('support_page.capacity_audit_text')}
                >
                    <p><a className='btn' href='#capacity'>{$.t('support_page.view_capacity_audit')}</a></p>
                </SupportPageElement>
            );
        }
    });

    var StatisticsSettings = React.createClass({
        mixins: [
            statisticsMixin,
            React.BackboneMixin('settings')
        ],
        onSaveButtonClick: function(e) {
            this.saveSettings(e).done(_.bind(this.updateInitialSettings, this));
        },
        updateInitialSettings: function() {
            this.initialSettings = _.cloneDeep(this.props.settings.attributes);
        },
        componentDidMount: function() {
            this.updateInitialSettings();
        },
        componentWillUnmount: function() {
            this.props.settings.set(_.cloneDeep(this.initialSettings));
        },
        render: function() {
            if (this.state.loading) return <controls.ProgressBar />;
            var sortedSettingGroups = _.sortBy(_.keys(this.props.settings.attributes), function(groupName) {
                return this.get(groupName, 'metadata.weight');
            }, this);
            return (
                <SupportPageElement title={$.t('support_page.send_statistics_title')}>
                    {this.renderIntro()}
                    <div className='statistics-settings'>
                        {_.map(sortedSettingGroups, function(groupName) {
                            return _.chain(_.keys(this.get(groupName)))
                                .sortBy(function(settingName) {
                                    return this.get(groupName, settingName, 'weight');
                                }, this)
                                .without('metadata')
                                .map(function(settingName) {
                                    return this.renderInput(this.get(groupName, settingName), groupName, settingName);
                                }, this)
                                .value();
                        }, this)}
                    </div>
                    <p>
                        <a className='btn' disabled={this.state.actionInProgress} onClick={this.onSaveButtonClick}>
                            {$.t('support_page.save_changes')}
                        </a>
                    </p>
                </SupportPageElement>
            );
        }
    });

    return SupportPage;
});
