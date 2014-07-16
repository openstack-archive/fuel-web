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
    'views/dialogs'
],
function(utils, models, dialogViews) {
    'use strict';

    var views = {};

    views.Page = Backbone.View.extend({
        navbarActiveElement: null,
        breadcrumbsPath: null,
        title: null,
        updateNavbar: function() {
            app.navbar.setActive(_.result(this, 'navbarActiveElement'));
        },
        updateBreadcrumbs: function() {
            app.breadcrumbs.setPath(_.result(this, 'breadcrumbsPath'));
        },
        updateTitle: function() {
            var defaultTitle = $.t('common.title');
            var title = _.result(this, 'title');
            document.title = title ? defaultTitle + ' - ' + title : defaultTitle;
        }
    });

    views.Tab = Backbone.View.extend({
        initialize: function(options) {
            _.defaults(this, options);
        }
    });

    return views;
});
