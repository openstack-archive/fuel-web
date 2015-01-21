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
define([
    'underscore',
    'i18n',
    'react',
    'jsx!views/layout',
    'models'
], function(_, i18n, React, layoutComponents, models) {
    'use strict';

    var RootComponent = React.createClass({
        getInitialState: function() {
            return {
                statistics: new models.NodesStatistics(),
                notifications: new models.Notifications()
            };
        },
        setPage: function(Page, pageOptions, version, user) {
            this.setState({
                Page: Page,
                pageOptions: pageOptions,
                version: version,
                user: user
            });
            return this.refs.page;
        },
        refreshNavbar: function() {
            this.refs.navbar.refresh();
        },
        updateClusterBreadcrumbs: function() {
            this.setState({clusterName: this.refs.page.props.cluster.get('name')});
        },
        updateTitle: function() {
            var cluster = this.refs.page.props.cluster,
                title = cluster ? cluster.get('name') : this.state.Page.title;
            document.title = i18n('common.title') + (title ? ' - ' + title : '');
        },
        componentDidUpdate: function() {
            this.updateTitle();
        },
        render: function() {
            var Page = this.state.Page;
            if (!Page) return null;
            var cluster = this.state.pageOptions ? this.state.pageOptions.cluster : null;
            return (
                <div id='content-wrapper'>
                    <div id='wrap'>
                        <div className='container'>
                            {!Page.hiddenLayout &&
                                <div>
                                    <layoutComponents.Navbar
                                        ref='navbar'
                                        activeElement={Page.navbarActiveElement}
                                        {... _.pick(this.state, 'user', 'version', 'statistics', 'notifications')}
                                    />
                                    <layoutComponents.Breadcrumbs
                                        ref='breadcrumbs'
                                        path={cluster ? Page.getBreadcrumbs(cluster) : Page.breadcrumbsPath}
                                    />
                                </div>
                            }
                            <div id='content'>
                                <Page ref='page' {...this.state.pageOptions} />
                            </div>
                            <div id='push'></div>
                        </div>
                    </div>
                    {!Page.hiddenLayout && <layoutComponents.Footer version={this.state.version}/>}
                </div>

            );
        }
    });

    return RootComponent;
});
