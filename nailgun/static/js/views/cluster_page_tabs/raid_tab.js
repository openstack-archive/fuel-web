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
        events: {
            'click .open, .closed': 'showRaidNode',
            'click .btn-link': 'applyAll'
        },
        templateHelpers: {
            showDiskSize: utils.showDiskSize
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
        updateNodes: function() {
            this.nodes.fetch()
                .done(_.bind(function() {
                    this.render();
                }, this));
        },
        initialize: function(options) {
            _.defaults(this, options);
            var self = this;
            var clusterId = this.model.id;
            this.nodes = this.model.get('nodes');
            this.nodes.fetch = function(options) {
                return this.constructor.__super__.fetch.call(this, _.extend({data: {cluster_id: clusterId}}, options));
            };
            this.nodes.fetch()
                .done(function() {
                    self.render();
                });
            this.nodes.on('change', this.updateNodes, this);
        },
        render: function() {
            this.$el.html(this.template(_.extend({
                nodes: this.nodes
            }, this.templateHelpers))).i18n();
            return this;
        }
    });
    return RaidTab;
});
