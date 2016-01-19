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
import dispatcher from 'dispatcher';
import utils from 'utils';
import {dispatcherMixin} from 'component_mixins';
import {Navbar, Breadcrumbs, DefaultPasswordWarning, BootstrapError, Footer} from 'views/layout';
import {DragDropContext} from 'react-dnd';
import HTML5Backend from 'react-dnd-html5-backend';

var RootComponent = React.createClass({
  mixins: [
    dispatcherMixin('updatePageLayout', 'updateTitle'),
    dispatcherMixin('showDefaultPasswordWarning', 'showDefaultPasswordWarning'),
    dispatcherMixin('hideDefaultPasswordWarning', 'hideDefaultPasswordWarning')
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
    var Page = this.state.Page;
    var title = _.isFunction(Page.title) ? Page.title(this.state.pageOptions) : Page.title;
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
            <Navbar key='navbar' ref='navbar' activeElement={Page.navbarActiveElement} {...this.props} />,
            <Breadcrumbs key='breadcrumbs' ref='breadcrumbs' {...this.state} />,
            showDefaultPasswordWarning && <DefaultPasswordWarning key='password-warning' close={this.hideDefaultPasswordWarning} />,
            fuelSettings.get('bootstrap.error.value') && <BootstrapError key='bootstrap-error' text={fuelSettings.get('bootstrap.error.value')} />
          ]}
          <div id='content'>
            <Page ref='page' {...this.state.pageOptions} />
          </div>
          {!Page.hiddenLayout && <div id='footer-spacer'></div>}
        </div>
        {!Page.hiddenLayout && <Footer version={version} />}
      </div>
    );
  }
});

export default DragDropContext(HTML5Backend)(RootComponent);
