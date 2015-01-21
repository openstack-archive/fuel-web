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
    'i18n',
    'react',
    'backbone',
    'jsx!backbone_view_wrapper',
    'jsx!views/layout',
    'models'
], function(i18n, React, Backbone, BackboneViewWrapper, layoutComponents, models) {
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
        refreshBreadcrumbs: function() {
            this.setState({clusterName: this.refs.page.props.cluster.get('name')});
        },
        updateTitle: function(newTitle, cluster) {
            var title = cluster ? cluster.get('name') : newTitle;
            document.title = i18n('common.title') + (title ? ' - ' + title : '');
        },
        componentDidUpdate: function() {
            this.updateTitle(this.state.Page.title, this.refs.page.props.cluster);
        },
        render: function() {
            var Page = this.state.Page;
            if (!Page) return null;
            var pageComponent = <Page ref='page' {...this.state.pageOptions} />,
                cluster = pageComponent.props.cluster;
            return (
                <div className='main-container'>
                    <div id='wrap'>
                        <div className='container'>
                            {!Page.hiddenLayout &&
                                <div>
                                    <layoutComponents.Navbar
                                        ref='navbar'
                                        activeElement={Page.navbarActiveElement}
                                        {..._.pick(this.state, 'user', 'version', 'statistics', 'notifications')}
                                    />
                                    <layoutComponents.Breadcrumbs
                                        ref='breadcrumbs'
                                        path={cluster ? Page.getBreadcrumbs(cluster) : Page.breadcrumbsPath}
                                    />
                                </div>
                            }
                            <div id='content'>
                                {pageComponent}
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
