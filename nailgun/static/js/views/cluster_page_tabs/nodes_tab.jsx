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
    'jquery',
    'underscore',
    'react',
    'jsx!backbone_view_wrapper',
    'jsx!views/controls',
    'jsx!views/cluster_page_tabs/nodes_tab_screens/cluster_nodes_screen',
    'jsx!views/cluster_page_tabs/nodes_tab_screens/add_nodes_screen',
    'jsx!views/cluster_page_tabs/nodes_tab_screens/edit_nodes_screen',
    'views/cluster_page_tabs/nodes_tab_screens/edit_node_disks_screen',
    'jsx!views/cluster_page_tabs/nodes_tab_screens/edit_node_interfaces_screen'
],
function($, _, React, BackboneViewWrapper, controls, ClusterNodesScreen, AddNodesScreen, EditNodesScreen, EditNodeDisksScreen, EditNodeInterfacesScreen) {
    'use strict';

    var ReactTransitionGroup = React.addons.TransitionGroup;

    var NodesTab = React.createClass({
        getInitialState: function() {
            return {loading: true};
        },
        hasChanges: function() {
            return _.result(this.refs.screen, 'hasChanges');
        },
        revertChanges: function() {
            return this.refs.screen.revertChanges();
        },
        getAvailableScreens: function() {
            return {
                list: ClusterNodesScreen,
                add: AddNodesScreen,
                edit: EditNodesScreen,
                disks: BackboneViewWrapper(EditNodeDisksScreen),
                interfaces: EditNodeInterfacesScreen
            };
        },
        loadScreen: function(props) {
            props = props || this.props;
            var screen = this.getScreen(props),
                screenComponent = this.getAvailableScreens()[screen];
            if (!screenComponent) {
                app.navigate('cluster/' + this.props.cluster.id + '/nodes', {trigger: true, replace: true});
                return;
            }
            var options = {cluster: this.props.cluster, screenOptions: props.tabOptions.slice(1)};
            return (screenComponent.fetchData ? screenComponent.fetchData(options) : $.Deferred().resolve()).done(_.bind(function(data) {
                this.setState({
                    loading: false,
                    screen: screen,
                    screenData: data || {}
                });
            }, this));
        },
        getScreen: function(props) {
            props = props || this.props;
            return props.tabOptions[0] || 'list';
        },
        componentDidMount: function() {
            this.loadScreen();
        },
        componentWillReceiveProps: function(newProps) {
            // if url was changed, load data and change screen
            if (this.state.screen != this.getScreen(newProps)) {
                this.setState({loading: true});
                this.loadScreen(newProps);
            }
        },
        render: function() {
            if (this.state.loading) return <controls.ProgressBar />;
            var Screen = this.getAvailableScreens()[this.state.screen];
            return (
                <ReactTransitionGroup component='div' className='wrapper' transitionName='screen'>
                    <ScreenTransitionWrapper key={this.state.screen}>
                        <Screen {...this.state.screenData}
                            ref='screen'
                            cluster={this.props.cluster}
                            screenOptions={this.props.tabOptions.slice(1)}
                        />
                    </ScreenTransitionWrapper>
                </ReactTransitionGroup>
            );
        }
    });

    // additional screen wrapper to keep ref to screen in the tab component
    // see https://github.com/facebook/react/issues/1950 for more info
    var ScreenTransitionWrapper = React.createClass({
        componentWillEnter: function(cb) {
            $(this.getDOMNode()).hide().delay('fast').fadeIn('fast', cb);
        },
        componentWillLeave: function(cb) {
            $(this.getDOMNode()).fadeOut('fast', cb);
        },
        render: function() {
            return <div>{this.props.children}</div>;
        }
    });

    return NodesTab;
});
