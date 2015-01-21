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
            var isBackboneView = Page.prototype instanceof Backbone.View;
            this.setState({
                Page: isBackboneView ? BackboneViewWrapper(Page) : Page,
                pageOptions: pageOptions,
                version: version,
                user: user
            });
            var view = isBackboneView ? this.refs.page.refs.wrapper.state.view : this.refs.page;
            return view;
        },
        refreshNavbar: function() {this.refs.navbar.refresh();},
        updateTitle: function(newTitle) {document.title = i18n('common.title') + (newTitle ? ' - ' + newTitle : '');},
        render: function() {
            var Page = this.state.Page;
            if (!Page) return null;
            var pageComponent = <Page ref='page' {...this.state.pageOptions} />;
            this.updateTitle(Page.title || pageComponent.props.title);
            return (
                <div className='main-container'>
                    <div id='wrap'>
                        <div className='container'>
                            {!Page.hiddenLayout &&
                                <div>
                                    <layoutComponents.Navbar
                                        ref='navbar'
                                        elements={[
                                            {label: 'environments', url: '#clusters'},
                                            {label: 'releases', url: '#releases'},
                                            {label: 'support', url: '#support'}
                                        ]}
                                        activeElement={Page.navbarActiveElement || pageComponent.props.navbarActiveElement}
                                        user={this.state.user}
                                        version={this.state.version}
                                        statistics={this.state.statistics}
                                        notifications={this.state.notifications}
                                    />
                                    <div id='breadcrumbs' className='container'>
                                        <layoutComponents.Breadcrumbs path={Page.breadcrumbsPath || pageComponent.props.breadcrumbsPath}/>
                                    </div>
                                </div>
                            }
                            <div id='content'>
                                {pageComponent}
                            </div>
                            <div id='push'></div>
                        </div>
                    </div>
                    {!Page.hiddenLayout &&
                        <div id='footer'>
                            <layoutComponents.Footer version={this.state.version}/>
                        </div>
                    }
                </div>

            );
        }
    });

    return RootComponent;
});
