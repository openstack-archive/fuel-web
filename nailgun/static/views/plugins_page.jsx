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
            return {columns: ['name', 'version', 'type', 'provider', 'certified', 'actions']};
        },
        statics: {
            title: i18n('plugins_page.title'),
            navbarActiveElement: 'plugins',
            breadcrumbsPath: [['home', '#'], 'plugins'],
            fetchData: function() {
                var plugins = new models.Plugins();
                return plugins.fetch().then(function() {
                    plugins.reset([
                        {name: 'Contrail', type: 'Network', provider: 'Mirantis', certified: 'Yes', version: '1.2.3'},
                        {name: 'vCenter', type: '???', provider: 'Mirantis', certified: 'No', version: '3.2.1'},
                        {name: 'Ceph', type: 'Storage', provider: 'Mirantis', certified: 'Maybe', version: '4.5.6'}
                    ]);
                    return {plugins: plugins};
                });
            }
        },
        renderPlugin: function(plugin) {
            return _.map(this.props.columns, function(attr) {
                if (attr == 'actions') return (
                    <button className='btn btn-danger btn-sm'>
                        <i className='glyphicon glyphicon-minus' />
                        {' ' + i18n('plugins_page.remove_plugin')}
                    </button>
                );
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
                            <div className='col-xs-12'>
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
                            <div className='col-xs-12'>
                                <button className='btn btn-success'>
                                    <i className='glyphicon glyphicon-plus' />
                                    {' ' + i18n('plugins_page.install_plugin')}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            );
        }
    });

    return PluginsPage;
});
