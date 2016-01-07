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

import _ from 'underscore';
import i18n from 'i18n';
import React from 'react';
import utils from 'utils';
import layoutComponents from 'views/layout';
import dispatcher from 'dispatcher';
import componentMixins from 'component_mixins';
import {DragDropContext} from 'react-dnd';
import HTML5Backend from 'react-dnd-html5-backend';

    var RootComponent = React.createClass({
        mixins: [
            componentMixins.dispatcherMixin('updatePageLayout', 'updateTitle'),
            componentMixins.dispatcherMixin('showDefaultPasswordWarning', 'showDefaultPasswordWarning'),
            componentMixins.dispatcherMixin('hideDefaultPasswordWarning', 'hideDefaultPasswordWarning')
        ],
        showDefaultPasswordWarning() {
            this.setState({showDefaultPasswordWarning: true});
        },
        hideDefaultPasswordWarning() {
            this.setState({showDefaultPasswordWarning: false});
        },
        getInitialState() {
            return {showDefaultPasswordWarning: false};
        },
        setPage(Page, pageOptions) {
            this.setState({
                Page: Page,
                pageOptions: pageOptions
            });
            return this.refs.page;
        },
        updateTitle() {
            var Page = this.state.Page,
                title = _.isFunction(Page.title) ? Page.title(this.state.pageOptions) : Page.title;
            document.title = i18n('common.title') + (title ? ' - ' + title : '');
        },
        componentDidUpdate() {
            dispatcher.trigger('updatePageLayout');
        },
        render() {
            var {Page, showDefaultPasswordWarning} = this.state;
            var {fuelSettings, version} = this.props;

            if (!Page) return null;
            var layoutClasses = {
                clamp: true,
                'fixed-width-layout': !Page.hiddenLayout
            };

            return (
                <div id='content-wrapper'>
                    <div className={utils.classNames(layoutClasses)}>
                        {!Page.hiddenLayout && [
                            <layoutComponents.Navbar key='navbar' ref='navbar' activeElement={Page.navbarActiveElement} {...this.props} />,
                            <layoutComponents.Breadcrumbs key='breadcrumbs' ref='breadcrumbs' {...this.state} />,
                            showDefaultPasswordWarning && <layoutComponents.DefaultPasswordWarning key='password-warning' close={this.hideDefaultPasswordWarning} />,
                            fuelSettings.get('bootstrap.error.value') && <layoutComponents.BootstrapError key='bootstrap-error' text={fuelSettings.get('bootstrap.error.value')} />
                        ]}
                        <div id='content'>
                            <Page ref='page' {...this.state.pageOptions} />
                        </div>
                        {!Page.hiddenLayout && <div id='footer-spacer'></div>}
                    </div>
                    {!Page.hiddenLayout && <layoutComponents.Footer version={version} />}
                </div>
            );
        }
    });

    export default DragDropContext(HTML5Backend)(RootComponent);
