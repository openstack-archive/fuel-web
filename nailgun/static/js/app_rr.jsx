/*
 * Copyright 2014 Mirantis, Inc.
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

define([
    'react',
    'react-router',
    'utils',
    'jquery',
    'underscore',
    'backbone',
    'jsx!views/layout',
    'jsx!views/support_page',
    //
    'less!/static/css/styles',
    'stickit',
    'coccyx',
    'react',
    'react.backbone',
    'cocktail',
    'routefilter',
    'i18next',
    'bootstrap',
    'jquery-cookie',
    'jquery-checkbox',
    'jquery-timeout',
    'jquery-ui',
    'jquery-autoNumeric'
], function(React, Router, utils, $, _, Backbone, Layout, SupportPage) {
    'use strict';

    function App() {
        var Route = Router.Route,
            DefaultRoute = Router.DefaultRoute,
            RouteHandler = Router.RouteHandler;

        var routes = (
            <Route name="index" path="/" handler={Layout}>
                <Route name="support" path="/support" handler={SupportPage} />
                <DefaultRoute handler={SupportPage} />
            </Route>
        );
        Router.run(routes, function(Handler, state) {
            React.render(<Handler />, document.body);
        });
    }
    _.extend(App.prototype, {
    });

    var app = window.app = new App();

    return app;
});
