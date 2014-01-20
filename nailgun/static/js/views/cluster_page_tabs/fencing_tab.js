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
    'models',
    'views/common',
    'views/dialogs',
    'text!templates/cluster/fencing_tab.html'
],
function(models, commonViews, dialogViews, fencingTabTemplate) {
    'use strict';
    var FencingTab = commonViews.Tab.extend({
        template: _.template(fencingTabTemplate),
        initialize: function(options) {
            _.defaults(this, options);
            this.model.on('change:name', this.render, this);
            this.model.on('invalid', this.showValidationError, this);
        },
        render: function() {
            this.$el.html(this.template({cluster: this.model})).i18n();
            return this;
        }
    });

    return FencingTab;
});
