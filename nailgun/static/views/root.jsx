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
    'dispatcher',
    'jsx!component_mixins',
    'react-dnd'
], function(_, i18n, React, layoutComponents, dispatcher, componentMixins, DND) {
    'use strict';

    var RootComponent = React.createClass({
        mixins: [
            componentMixins.dispatcherMixin('updatePageLayout', 'updateTitle')
        ],
        getInitialState: function() {
            return {};
        },
        setPage: function(Page, pageOptions) {
            this.setState({
                Page: Page,
                pageOptions: pageOptions
            });
            return this.refs.page;
        },
        updateTitle: function() {
            var Page = this.state.Page,
                title = _.isFunction(Page.title) ? Page.title(this.state.pageOptions) : Page.title;
            document.title = i18n('common.title') + (title ? ' - ' + title : '');
        },
        componentDidUpdate: function() {
            dispatcher.trigger('updatePageLayout');
        },
        render: function() {
            var Page = this.state.Page;
            if (!Page) return <div className='loading' />;
            return (
                <div id='content-wrapper'>
                    <div className='clamp'>
                        {!Page.hiddenLayout && [
                            <layoutComponents.Navbar key='navbar' ref='navbar' activeElement={Page.navbarActiveElement} {...this.props} />,
                            <layoutComponents.Breadcrumbs key='breadcrumbs' ref='breadcrumbs' {...this.state} />
                        ]}
                        <div id='content'>
                            <Page ref='page' {...this.state.pageOptions} />
                        </div>
                        {!Page.hiddenLayout && <div id='footer-spacer'></div>}
                    </div>
                    {!Page.hiddenLayout && <layoutComponents.Footer version={this.props.version} />}
                </div>
            );
        }
    });

    return DND.DragDropContext(DND.HTML5)(RootComponent);
});
