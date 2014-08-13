/*
 * Copyright 2013 Mirantis, Inc.
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
    'utils',
    'models',
    'views/common',
    'views/cluster_page_tabs/nodes_tab_screens/cluster_nodes_screen',
    'views/cluster_page_tabs/nodes_tab_screens/add_nodes_screen',
    'views/cluster_page_tabs/nodes_tab_screens/edit_nodes_screen',
    'views/cluster_page_tabs/nodes_tab_screens/edit_node_disks_screen',
    'views/cluster_page_tabs/nodes_tab_screens/edit_node_interfaces_screen'
],
function(utils, models, commonViews, ClusterNodesScreen, AddNodesScreen, EditNodesScreen, EditNodeDisksScreen, EditNodeInterfacesScreen) {
    'use strict';
    var NodesTab;

    NodesTab = commonViews.Tab.extend({
        className: 'wrapper',
        screen: null,
        scrollPositions: {},
        hasChanges: function() {
            return this.screen && _.result(this.screen, 'hasChanges');
        },
        changeScreen: function(NewScreenView, screenOptions) {
            var options = _.extend({model: this.model, tab: this, screenOptions: screenOptions || []});
            if (this.screen) {
                if (this.screen.keepScrollPosition) {
                    this.scrollPositions[this.screen.constructorName] = $(window).scrollTop();
                }
                this.screen.$el.fadeOut('fast', _.bind(function() {
                    this.screen.tearDown();
                    this.screen = new NewScreenView(options);
                    this.screen.render();
                    this.screen.$el.hide().fadeIn('fast');
                    this.$el.html(this.screen.el);
                    if (this.screen.keepScrollPosition && this.scrollPositions[this.screen.constructorName]) {
                        $(window).scrollTop(this.scrollPositions[this.screen.constructorName]);
                    }
                    this.registerSubView(this.screen);
                }, this));
            } else {
                this.screen = new NewScreenView(options);
                this.$el.html(this.screen.render().el);
                this.registerSubView(this.screen);
            }
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.revertChanges = _.bind(function() {
                return this.screen && this.screen.revertChanges();
            }, this);
            this.selectedNodes = new models.Nodes();
            this.selectedNodes.cluster = this.model;
        },
        routeScreen: function(options) {
            var screens = {
                'list': ClusterNodesScreen,
                'add': AddNodesScreen,
                'edit': EditNodesScreen,
                'disks': EditNodeDisksScreen,
                'interfaces': EditNodeInterfacesScreen
            };
            this.changeScreen(screens[options[0]] || screens.list, options.slice(1));
        },
        render: function() {
            this.routeScreen(this.tabOptions);
            return this;
        }
    });

    return NodesTab;
});
