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
    'jquery',
    'underscore',
    'i18n',
    'react',
    'models',
    'jsx!views/controls',
    'jsx!component_mixins'
],
function($, _, i18n, React, models, controls, componentMixins) {
    'use strict';

    var PluginsPage = React.createClass({
        mixins: [componentMixins.backboneMixin('plugins')],
        getDefaultProps: function() {
            return {columns: ['information']};
        },
        statics: {
            title: i18n('plugins_page.title'),
            navbarActiveElement: 'plugins',
            breadcrumbsPath: [['home', '#'], 'plugins'],
            fetchData: function() {
                var plugins = new models.Plugins(),
                    clusters = new models.Clusters();
                return $.when(plugins.fetch(), clusters.fetch()).then(function() {
                    return {
                        plugins: plugins,
                        clusters: clusters
                    };
                });
            }
        },
        renderPlugin: function(plugin) {
            var details = ['version', 'description', 'homepage', 'authors', 'licenses', 'releases'];
            return (
                <div className='plugin'>
                    <div className='row'>
                        <div className='col-xs-2' />
                        <h3 className='col-xs-10'>
                            {plugin.get('title')}
                        </h3>
                    </div>
                    {_.map(details, function(attribute) {
                        var data = plugin.get(attribute);
                        if (attribute == 'releases') {
                            data = _.map(_.groupBy(plugin.get(attribute), 'os'), function(release, osName) {
                                return (
                                    <div key={osName}>
                                        {i18n('plugins_page.' + osName) + ': '}
                                        {_.map(release, function(data, i) {
                                            return release.length == i + 1 ? data.version : data.version += ', ';
                                        })}
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
                                    {attribute == 'homepage' ? <a href={encodeURI(data)} target='_blank'>{data}</a> : data}
                                </div>
                            </div>
                        );
                    }, this)}
                </div>
            );
        },
        render: function() {
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
                                    <div className='alert alert-warning'>
                                        {i18n('plugins_page.no_plugins')}
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
