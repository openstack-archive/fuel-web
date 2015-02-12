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
    'jsx!views/cluster_page_tabs/nodes_tab_screens/cluster_nodes_screen',
    'jsx!views/cluster_page_tabs/nodes_tab_screens/add_nodes_screen',
    'jsx!views/cluster_page_tabs/nodes_tab_screens/edit_nodes_screen',
    'views/cluster_page_tabs/nodes_tab_screens/edit_node_disks_screen',
    'jsx!views/cluster_page_tabs/nodes_tab_screens/edit_node_interfaces_screen'
],
function($, _, React, BackboneViewWrapper, ClusterNodesScreen, AddNodesScreen, EditNodesScreen, EditNodeDisksScreen, EditNodeInterfacesScreen) {
    'use strict';

    var ReactTransitionGroup = React.addons.TransitionGroup;

    var NodesTab = React.createClass({
        getInitialState: function() {
            return {
                screen: this.props.tabOptions[0] || 'list',
                screenOptions: this.props.tabOptions.slice(1)
            };
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
        checkScreen: function(newScreen) {
            if (newScreen && !this.getAvailableScreens()[newScreen]) {
                app.navigate('cluster/' + this.props.cluster.id + '/nodes', {trigger: true, replace: true});
            }
        },
        changeScreen: function(newScreen, screenOptions) {
            var NewScreenComponent = this.getAvailableScreens()[newScreen];
            if (!NewScreenComponent) return;
            var options = {cluster: this.props.cluster, screenOptions: screenOptions};
            return (NewScreenComponent.fetchData ? NewScreenComponent.fetchData(options) : $.Deferred().resolve())
                .done(_.bind(function(data) {
                    this.setState({
                        screen: newScreen,
                        screenOptions: screenOptions,
                        screenData: data || {}
                    });
                }, this));
        },
        componentWillMount: function() {
            var newScreen = this.props.tabOptions[0] || 'list';
            this.checkScreen(newScreen);
            this.changeScreen(newScreen, this.props.tabOptions.slice(1));
        },
        componentWillReceiveProps: function(newProps) {
            var newScreen = newProps.tabOptions[0] || 'list';
            this.checkScreen(newScreen);
            this.changeScreen(newScreen, newProps.tabOptions.slice(1));
        },
        render: function() {
            var Screen = this.getAvailableScreens()[this.state.screen];
            if (!Screen || !_.isObject(this.state.screenData)) return null;
            return (
                <ReactTransitionGroup component='div' className='wrapper' transitionName='screen'>
                    <ScreenTransitionWrapper key={this.state.screen}>
                        <Screen {...this.state.screenData}
                            ref='screen'
                            cluster={this.props.cluster}
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
