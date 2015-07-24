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

    var SupportContacts = React.createClass({
        render: function() {
            return (
                <SupportPageElement
                    className='img-contact-support'
                    title={i18n('support_page.contact_support')}
                    text={i18n('support_page.contact_text')}
                >
                    <p>{i18n('support_page.irc_text')} <strong>邮箱</strong> on <a href='zehin@zehin.com.cn' target='_blank'>Email</a>. </p>
                    <p>
                        <a className='btn' href='http://www.zehin.com.cn' target='_blank'>
                            {i18n('support_page.contact_support')}
                        </a>
                    </p>
                </SupportPageElement>
            );
        }
    });

    return SupportPage;
});
