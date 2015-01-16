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
define([
    'react',
    'backbone',
    'jsx!backbone_view_wrapper'
], function(React, Backbone, BackboneViewWrapper) {
    'use strict';

    var RootComponent = React.createClass({
        getInitialState: function() {
            return {};
        },
        setPage: function(Page, pageOptions) {
            var isBackboneView = Page.prototype instanceof Backbone.View;
            this.setState({Page: isBackboneView ? BackboneViewWrapper(Page) : Page, pageOptions: pageOptions});
            return isBackboneView ? this.refs.page.refs.wrapper.state.view : this.refs.page;
        },
        render: function() {
            return this.state.Page ? <this.state.Page ref='page' {...this.state.pageOptions} /> : null;
        }
    });

    return RootComponent;
});
