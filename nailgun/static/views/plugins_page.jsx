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
    'jsx!views/controls',
    'jsx!component_mixins'
],
function(_, i18n, React, models, controls, componentMixins) {
    'use strict';

    var PluginsPage = React.createClass({
        mixins: [componentMixins.backboneMixin('plugins')],
        getDefaultProps: function() {
            return {columns: ['information', 'releases']};
        },
        statics: {
            title: i18n('plugins_page.title'),
            navbarActiveElement: 'plugins',
            breadcrumbsPath: [['home', '#'], 'plugins'],
            fetchData: function() {
                var plugins = new models.Plugins();
                return plugins.fetch().then(function() {
                    return {plugins: plugins};
                });
            }
        },
        renderPlugin: function(plugin) {
            return _.map(this.props.columns, function(attr) {
                if (attr == 'information') {
                    var details = ['version', 'description', 'homepage', 'authors', 'licenses'];
                    return (
                        <div>
                            <h4>{plugin.get('title')}</h4>
                            {_.map(details, function(name) {
                                var data = plugin.get(name);
                                if (_.isArray(data)) data = _.map(data).join(', ');
                                return (
                                    <div className='row'>
                                        <div className='col-xs-3 detail-title text-right'>{i18n('plugins_page.' + name)}:</div>
                                        <div className='col-xs-9'>
                                            {name == 'homepage' ? <a href={data}>{data}</a> : data}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    );
                }
                if (attr == 'releases') {
                    return (
                        <div className='releases'>
                            {_.map(_.groupBy(plugin.get(attr), 'os'), function(release, osName) {
                                return (
                                    <div className='row'>
                                        <div className="col-xs-3">{osName}: </div>
                                        <div className="col-xs-9">
                                            <ul>
                                                {_.map(release, function(data) {
                                                    return (
                                                        <li>{data.version}</li>
                                                    );
                                                })}
                                            </ul>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    );
                }
                return plugin.get(attr);
            });
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
                                    <controls.Table
                                        head={_.map(this.props.columns, function(column) {
                                            return {label: i18n('plugins_page.' + column), className: column};
                                        })}
                                        body={this.props.plugins.map(this.renderPlugin)}
                                    />
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
