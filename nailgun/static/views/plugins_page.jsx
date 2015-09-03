/*
 * Copyright 2015 Mirantis, Inc.
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
    'underscore',
    'i18n',
    'react',
    'models',
    'utils'
],
function(_, i18n, React, models, utils) {
    'use strict';

    var PluginsPage = React.createClass({
        statics: {
            title: i18n('plugins_page.title'),
            navbarActiveElement: 'plugins',
            breadcrumbsPath: [['home', '#'], 'plugins'],
            fetchData: function() {
                var plugins = new models.Plugins();
                return plugins.fetch().then(function() {
                    return {
                        plugins: plugins
                    };
                });
            }
        },
        getDefaultProps: function() {
            return {details: ['version', 'description', 'homepage', 'authors', 'licenses', 'releases']};
        },
        renderPlugin: function(plugin) {
            return (
                <div key={plugin.get('name')} className='plugin'>
                    <div className='row'>
                        <div className='col-xs-2' />
                        <h3 className='col-xs-10'>
                            {plugin.get('title')}
                        </h3>
                    </div>
                    {_.map(this.props.details, function(attribute) {
                        var data = plugin.get(attribute);
                        if (!_.isEmpty(data)) {
                            if (attribute == 'releases') {
                                data = _.map(_.groupBy(data, 'os'), function(osReleases, osName) {
                                    return (
                                        <div key={osName}>
                                            {i18n('plugins_page.' + osName) + ': '}
                                            {_.pluck(osReleases, 'version').join(', ')}
                                        </div>
                                    );
                                });
                            } else if (_.isArray(data)) {
                                data = _.map(data).join(', ');
                            }
                            return (
                                <div className='row' key={attribute}>
                                    <div className='col-xs-2 detail-title text-right'>{i18n('plugins_page.' + attribute)}:</div>
                                    <div className='col-xs-10'>
                                        {attribute == 'homepage' ?
                                            <span dangerouslySetInnerHTML={{__html: utils.composeLink(data)}} />
                                        :
                                            data
                                        }
                                    </div>
                                </div>
                            );
                        }
                    }, this)}
                </div>
            );
        },
        render: function() {
            var isMirantisIso = _.contains(app.version.get('feature_groups'), 'mirantis'),
                links = {
                    catalog: isMirantisIso ? 'https://www.mirantis.com/products/openstack-drivers-and-plugins/fuel-plugins/' : 'http://stackalytics.com/report/driverlog?project_id=openstack%2Ffuel',
                    documentation: utils.composeDocumentationLink('plugin-dev.html')
                };
            return (
                <div className='plugins-page'>
                    <div className='page-title'>
                        <h1 className='title'>{i18n('plugins_page.title')}</h1>
                    </div>
                    <div className='content-box'>
                        <div className='row'>
                            <div className='col-xs-12 content-elements'>
                                {this.props.plugins.length ?
                                    this.props.plugins.map(this.renderPlugin)
                                :
                                    <div>
                                        {i18n('plugins_page.no_plugins')}
                                        <span> {i18n('plugins_page.more_info')}:</span>
                                        <ul>
                                            <li><a href={links.catalog} target='_blank'>{i18n('plugins_page.plugins_catalog')}</a></li>
                                            <li><a href={links.documentation} target='_blank'>{i18n('plugins_page.plugins_documentation')}</a></li>
                                        </ul>
                                    </div>
                                }
                            </div>
                        </div>
                    </div>
                </div>
            );
        }
    });

    return PluginsPage;
});
