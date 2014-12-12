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
    'react-router',
    'jsx!views/layout'
], function(_, i18n, React, Router, layoutComponents) {
    'use strict';

    var RootComponent = React.createClass({
        refreshNavbar: function() {
            this.refs.navbar.refresh();
        },
        updateLayout: function() {
            this.updateTitle();
            if (this.refs.breadcrumbs) {
                this.refs.breadcrumbs.refresh();
            }
        },
        updateTitle: function() {
            var Page = this.props.Page,
                title = _.isFunction(Page.title) ? Page.title(this.props.pageOptions) : Page.title;
            document.title = i18n('common.title') + (title ? ' - ' + title : '');
        },
        componentDidUpdate: function() {
            this.updateLayout();
        },
        render: function() {
            var Page = this.props.Page;
            if (!Page) return <div className='loading' />;
            return (
                <div id='content-wrapper'>
                    <div id='wrap'>
                        <div className='container'>
                            {!Page.hiddenLayout &&
                                <div>
                                    <layoutComponents.Navbar ref='navbar' {...this.props} />
                                    <layoutComponents.Breadcrumbs ref='breadcrumbs' {...this.props} />
                                </div>
                            }
                            <div id='content'>
                                <Router.RouteHandler ref='page' {...this.props.pageOptions} />
                            </div>
                            <div id='push' />
                        </div>
                    </div>
                    {!Page.hiddenLayout && <layoutComponents.Footer version={this.props.version} />}
                </div>
            );
        }
    });

    return RootComponent;
});
