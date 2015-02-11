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
    'utils',
    'jsx!backbone_view_wrapper',
    'jsx!views/controls',
    'jsx!views/cluster_page_tabs/nodes_tab_screens/cluster_nodes_screen',
    'jsx!views/cluster_page_tabs/nodes_tab_screens/add_nodes_screen',
    'jsx!views/cluster_page_tabs/nodes_tab_screens/edit_nodes_screen',
    'views/cluster_page_tabs/nodes_tab_screens/edit_node_disks_screen',
    'jsx!views/cluster_page_tabs/nodes_tab_screens/edit_node_interfaces_screen'
],
function($, _, React, utils, BackboneViewWrapper, controls, ClusterNodesScreen, AddNodesScreen, EditNodesScreen, EditNodeDisksScreen, EditNodeInterfacesScreen) {
    'use strict';

    var ReactTransitionGroup = React.addons.TransitionGroup;

    var NodesTab = React.createClass({
        getInitialState: function() {
            var screen = this.getScreen();
            return {
                loading: this.shouldScreenDataBeLoaded(screen),
                screen: screen,
                screenOptions: this.getScreenOptions(),
                screenData: {}
            };
        },
        hasChanges: function() {
            return _.result(this.refs.screen, 'hasChanges');
        },
        revertChanges: function() {
            return this.refs.screen.revertChanges();
        },
        getScreenConstructor: function(screen) {
            return {
                list: ClusterNodesScreen,
                add: AddNodesScreen,
                edit: EditNodesScreen,
                disks: BackboneViewWrapper(EditNodeDisksScreen),
                interfaces: EditNodeInterfacesScreen
            }[screen];
        },
        checkScreen: function(screen) {
            if (!this.getScreenConstructor(screen || this.state.screen)) {
                app.navigate('cluster/' + this.props.cluster.id + '/nodes', {trigger: true, replace: true});
                return false;
            }
            return true;
        },
        loadScreenData: function(screen, screenOptions) {
            return this.getScreenConstructor(screen || this.state.screen)
                .fetchData({
                    cluster: this.props.cluster,
                    screenOptions: screenOptions || this.state.screenOptions
                })
                .done(_.bind(function(data) {
                    this.setState({
                        loading: false,
                        screenData: data || {}
                    });
                }, this));
        },
        getScreen: function(props) {
            return (props || this.props).tabOptions[0] || 'list';
        },
        getScreenOptions: function(props) {
            return (props || this.props).tabOptions.slice(1);
        },
        shouldScreenDataBeLoaded: function(screen) {
            return !!this.getScreenConstructor(screen).fetchData;
        },
        componentDidMount: function() {
            if (this.checkScreen() && this.state.loading) this.loadScreenData();
        },
        componentWillReceiveProps: function(newProps) {
            var screen = this.getScreen(newProps);
            if (this.state.screen != screen && this.checkScreen(screen)) {
                var screenOptions = this.getScreenOptions(newProps),
                    newState = {
                        screen: screen,
                        screenOptions: screenOptions,
                        screenData: {}
                    };
                if (this.shouldScreenDataBeLoaded(screen)) {
                    this.setState(_.extend(newState, {loading: true}));
                    this.loadScreenData(screen, screenOptions);
                } else {
                    this.setState(newState);
                }
            }
        },
        render: function() {
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
        getInitialState: function() {
            return {loaded: true};
        },
        componentWillEnter: function(cb) {
            var node = $(this.getDOMNode());
            node.hide().delay('fast').fadeIn('fast', _.bind(function() {
                this.setState({loaded: true});
                cb();
            }, this));
        },
        componentWillLeave: function(cb) {
            this.setState({loaded: false});
            $(this.getDOMNode()).fadeOut('fast', cb);
        },
        render: function() {
            if (this.props.loading) return (
                <div className='row'>
                    <div className='col-xs-12' style={{paddingTop: '40px'}}>
                        <controls.ProgressBar />
                    </div>
                </div>
            );
            return <div className={utils.classNames({loaded: this.state.loaded})}>{this.props.children}</div>;
        }
    });

    return NodesTab;
});
