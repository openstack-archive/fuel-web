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
    'text!templates/cluster/raid_tab.html'
],
function(utils, models, commonViews, raidTabTemplate) {
    'use strict';
    var RaidTab;

    RaidTab = commonViews.Tab.extend({
        className: 'raid_tab',
        template: _.template(raidTabTemplate),
        updateInterval: 20000,
        events: {
            'click .open, .closed': 'showRaidNode',
            'click .btn-link': 'applyAll'
        },
        templateHelpers: {
            showDiskSize: utils.showDiskSize
        },
        scheduleUpdate: function() {
            this.registerDeferred($.timeout(this.updateInterval).done(_.bind(this.update, this)));
        },
        update: function() {
            this.nodes.fetch().always(_.bind(this.scheduleUpdate, this));
            this.state = this.currentState();
            this.render();
        },
        check: function() {
            var count = this.countOpen();
            var title = $('.page-sub-title');
            if (count == this.nodes.length) {
                $(title[0]).attr('style', 'display: block');
                $(title[1]).attr('style', 'display: none');
            } else {
                $(title[0]).attr('style', 'display: none');
                $(title[1]).attr('style', 'display: block');
            }
        },
        currentState: function() {
            var state = [];
            var i = 0;
            var closed = '';
            var open = '';
            var node = $('.raid-node');
            for (i; i < node.length; i += 1) {
                closed = $(node[i]).find($('.closed')).css('display');
                open = $(node[i]).find($('.open')).css('display');
                state.push({'open': open, 'closed': closed});
            }
            return state;

        },
        drawState: function(state) {
            var i = 0;
            var node = $('.raid-node');
            for (i; i < node.length; i += 1) {
                $(node[i]).find($('.closed')).attr('style', 'display: ' + state[i].closed);
                $(node[i]).find($('.open')).attr('style', 'display: ' + state[i].open);
                $(node[i]).find($('.raid-node-controller-block')).attr('style', 'display: ' + state[i].open);
            }
        },
        changeStyle: function(obj) {
            var currentClosed = $(obj).find($('.closed')).css('display');
            var currentOpen = $(obj).find($('.open')).css('display');
            $(obj).find($('.closed')).attr('style', 'display: ' + currentOpen);
            $(obj).find($('.open')).attr('style', 'display: ' + currentClosed);
            $(obj).find($('.raid-node-controller-block')).attr('style', 'display: ' + currentClosed);
            this.check();
        },
        countOpen: function() {
            var node = $('.raid-node');
            var i = 0;
            var count = 0;
            var style = '';
            for (i; i < node.length; i += 1) {
                style = $(node[i]).find($('.open')).css('display');
                if (style == 'block') {
                    count += 1;
                }
            }
            return count;
        },
        applyAll: function(e) {
            var allNode = $('.raid-node');
            var count = this.countOpen();
            var i = 0;
            for (i; i<allNode.length; i += 1) {
                if (count != 0 && count != this.nodes.length) {
                    if ($(allNode[i]).find($('.open')).css('display') == 'none') {
                        this.changeStyle(allNode[i]);
                    }
                } else {
                    this.changeStyle(allNode[i]);
                }
            }
            this.check();
        },
        showRaidNode: function(e) {
            this.changeStyle($(e.currentTarget).parent());
        },
        initialize: function(options) {
            _.defaults(this, options);
            var self = this;
            var clusterId = this.model.id;
            this.nodes = this.model.get('nodes');
            this.scheduleUpdate();
            this.state = [];
            this.nodes.fetch = function(options) {
                return this.constructor.__super__.fetch.call(this, _.extend({data: {cluster_id: clusterId}}, options));
            };
            this.nodes.each(_.bind(function(){
                this.state.push({'open': 'none', 'closed': 'block'});
            }, this));
            this.nodes.fetch()
                .done(function() {
                    self.state = self.currentState();
                    self.render();
                });
        },
        render: function() {
            this.$el.html(this.template(_.extend({
                nodes: this.nodes
            }, this.templateHelpers))).i18n();
            this.drawState(this.state);
            this.check();
            return this;
        }
    });
    return RaidTab;
});
