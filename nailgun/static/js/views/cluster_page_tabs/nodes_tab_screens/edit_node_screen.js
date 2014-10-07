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
define(['utils', 'models'], function(utils, models) {
    'use strict';

    var EditNodeScreen = Backbone.View.extend({
        constructorName: 'EditNodeScreen',
        keepScrollPosition: true,
        disableControls: function(disable) {
            this.updateButtonsState(disable || this.isLocked());
        },
        returnToNodeList: function() {
            if (this.hasChanges()) {
                this.tab.page.discardSettingsChanges({cb: _.bind(this.goToNodeList, this)});
            } else {
                this.goToNodeList();
            }
        },
        goToNodeList: function() {
            app.navigate('#cluster/' + this.model.id + '/nodes', {trigger: true});
        },
        isLocked: function() {
            return !!this.model.tasks({group: 'deployment', status: 'running'}).length;
        },
        initButtons: function() {
            this.loadDefaultsButton = new Backbone.Model({disabled: false});
            this.cancelChangesButton = new Backbone.Model({disabled: true});
            this.applyChangesButton = new Backbone.Model({disabled: true});
        },
        setupButtonsBindings: function() {
            var bindings = {attributes: [{name: 'disabled', observe: 'disabled'}]};
            this.stickit(this.loadDefaultsButton, {'.btn-defaults': bindings});
            this.stickit(this.cancelChangesButton, {'.btn-revert-changes': bindings});
            this.stickit(this.applyChangesButton, {'.btn-apply': bindings});
        },
        updateButtonsState: function(state) {
            this.applyChangesButton.set('disabled', state);
            this.cancelChangesButton.set('disabled', state);
            this.loadDefaultsButton.set('disabled',  state);
        },
        initialize: function(options) {
            _.defaults(this, options);
            var nodeIds = utils.deserializeTabOptions(this.screenOptions[0]).nodes.split(',').map(function(id) {return parseInt(id, 10);});
            this.nodes = new models.Nodes(this.model.get('nodes').getByIds(nodeIds));
        }
    });

    return EditNodeScreen;
});
