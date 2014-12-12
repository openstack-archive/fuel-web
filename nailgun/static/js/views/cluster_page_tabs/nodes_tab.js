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
    'underscore',
    'utils',
    'models',
    'views/common',
    'jsx!views/cluster_page_tabs/nodes_tab_screens/node_list_screen',
    'views/cluster_page_tabs/nodes_tab_screens/edit_node_disks_screen',
    'jsx!views/cluster_page_tabs/nodes_tab_screens/edit_node_interfaces_screen'
],
function(_, utils, models, commonViews, NodeListScreen, EditNodeDisksScreen, EditNodeInterfacesScreen) {
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
            var mode = screenOptions.shift(),
                options = _.extend({
                    model: this.model,
                    nodes: mode == 'add' ? new models.Nodes() : this.model.get('nodes'),
                    tab: this,
                    mode: mode,
                    screenOptions: screenOptions || []
                });
            if (this.screen) {
                if (this.screen.keepScrollPosition) {
                    this.scrollPositions[this.screen.constructorName || this.screen.displayName] = $(window).scrollTop();
                }
                this.$el.fadeOut('fast', _.bind(function() {
                    utils.universalUnmount(this.screen);
                    this.screen = utils.universalMount(NewScreenView, options, this.$el, this);
                    this.$el.hide().fadeIn('fast');
                    var newScrollPosition = this.screen.keepScrollPosition && this.scrollPositions[this.screen.constructorName || this.screen.displayName];
                    if (newScrollPosition) $(window).scrollTop(newScrollPosition);
                }, this));
            } else {
                this.screen = utils.universalMount(NewScreenView, options, this.$el, this);
            }
        },
        beforeTearDown: function() {
            if (this.screen) utils.universalUnmount(this.screen);
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.revertChanges = _.bind(function() {
                return this.screen && this.screen.revertChanges();
            }, this);
        },
        routeScreen: function(options) {
            options[0] = options[0] || 'list';
            var screens = {disks: EditNodeDisksScreen, interfaces: EditNodeInterfacesScreen};
            this.changeScreen(screens[options[0]] || NodeListScreen, options);
        },
        render: function() {
            this.routeScreen(this.tabOptions);
            return this;
        }
    });

    return NodesTab;
});
