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

import $ from 'jquery';
import _ from 'underscore';
import i18n from 'i18n';
import React from 'react';
import ReactDOM from 'react-dom';
import {ProgressBar} from 'views/controls';
import ClusterNodesScreen from 'views/cluster_page_tabs/nodes_tab_screens/cluster_nodes_screen';
import AddNodesScreen from 'views/cluster_page_tabs/nodes_tab_screens/add_nodes_screen';
import EditNodesScreen from 'views/cluster_page_tabs/nodes_tab_screens/edit_nodes_screen';
import EditNodeDisksScreen from 'views/cluster_page_tabs/nodes_tab_screens/edit_node_disks_screen';
import EditNodeInterfacesScreen from
  'views/cluster_page_tabs/nodes_tab_screens/edit_node_interfaces_screen';
import ReactTransitionGroup from 'react-addons-transition-group';

var NodesTab = React.createClass({
  statics: {
    breadcrumbsPath(pageOptions) {
      var subroute = pageOptions.tabOptions[0];
      var breadcrumbs = [
        [
          i18n('cluster_page.tabs.nodes'),
          '#cluster/' + pageOptions.cluster.id + '/nodes',
          {active: !subroute}
        ]
      ];
      if (subroute) {
        return breadcrumbs.concat([
          [
            i18n('cluster_page.nodes_tab.breadcrumbs.' + subroute, {defaultValue: subroute}),
            null,
            {active: true}
          ]
        ]);
      }
      return breadcrumbs;
    }
  },
  getInitialState() {
    var screen = this.getScreen();
    return {
      loading: this.shouldScreenDataBeLoaded(screen),
      screen: screen,
      screenOptions: this.getScreenOptions(),
      screenData: {}
    };
  },
  getScreenConstructor(screen) {
    return {
      list: ClusterNodesScreen,
      add: AddNodesScreen,
      edit: EditNodesScreen,
      disks: EditNodeDisksScreen,
      interfaces: EditNodeInterfacesScreen
    }[screen];
  },
  checkScreenExists(screen) {
    if (!this.getScreenConstructor(screen || this.state.screen)) {
      app.navigate('cluster/' + this.props.cluster.id + '/nodes', {trigger: true, replace: true});
      return false;
    }
    return true;
  },
  loadScreenData(screen, screenOptions) {
    return this.getScreenConstructor(screen || this.state.screen)
      .fetchData({
        cluster: this.props.cluster,
        screenOptions: screenOptions || this.state.screenOptions
      })
      .done((data) => {
        this.setState({
          loading: false,
          screenData: data || {}
        });
      })
      .fail(() => {
        app.navigate(
          '#cluster/' + this.props.cluster.id + '/nodes',
          {trigger: true, replace: true}
        );
      });
  },
  getScreen(props) {
    return (props || this.props).tabOptions[0] || 'list';
  },
  getScreenOptions(props) {
    return (props || this.props).tabOptions.slice(1);
  },
  shouldScreenDataBeLoaded(screen) {
    return !!this.getScreenConstructor(screen).fetchData;
  },
  componentDidMount() {
    if (this.checkScreenExists() && this.state.loading) this.loadScreenData();
  },
  componentWillReceiveProps(newProps) {
    var screen = this.getScreen(newProps);
    if (this.state.screen !== screen && this.checkScreenExists(screen)) {
      var screenOptions = this.getScreenOptions(newProps);
      var newState = {
        screen: screen,
        screenOptions: screenOptions,
        screenData: {}
      };
      if (this.shouldScreenDataBeLoaded(screen)) {
        this.setState(_.extend(newState, {loading: true}));
        this.loadScreenData(screen, screenOptions);
      } else {
        this.setState(_.extend(newState, {loading: false}));
      }
    }
  },
  render() {
    var Screen = this.getScreenConstructor(this.state.screen) || {};
    return (
      <ReactTransitionGroup
        component='div'
        className='wrapper'
        transitionName='screen'
      >
        <ScreenTransitionWrapper
          key={this.state.screen}
          loading={this.state.loading}
        >
          <Screen
            {...this.state.screenData}
            {..._.pick(
              this.props,
              'cluster', 'nodeNetworkGroups', 'selectedNodeIds', 'selectNodes'
            )}
            ref='screen'
            screenOptions={this.state.screenOptions}
          />
        </ScreenTransitionWrapper>
      </ReactTransitionGroup>
    );
  }
});

// additional screen wrapper to keep ref to screen in the tab component
// see https://github.com/facebook/react/issues/1950 for more info
var ScreenTransitionWrapper = React.createClass({
  componentWillEnter(cb) {
    $(ReactDOM.findDOMNode(this)).hide().delay('fast').fadeIn('fast', cb);
  },
  componentWillLeave(cb) {
    $(ReactDOM.findDOMNode(this)).fadeOut('fast', cb);
  },
  render() {
    if (this.props.loading) return (
      <div className='row'>
        <div className='col-xs-12' style={{paddingTop: '40px'}}>
          <ProgressBar />
        </div>
      </div>
    );
    return <div>{this.props.children}</div>;
  }
});

export default NodesTab;
