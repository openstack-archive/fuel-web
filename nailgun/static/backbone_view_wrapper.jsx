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
define(['react', 'backbone', 'utils'], function(React, Backbone, utils) {
    'use strict';

    var BackboneViewWrapperClass = React.createClass({
        getDefaultProps: function() {
            return {wrapperElement: 'div'};
        },
        shouldComponentUpdate: function() {
            return false;
        },
        componentDidMount: function() {
            var view = utils.universalMount(this.props.View, this.props, this.refs.wrapper.getDOMNode());
            this.setState({view: view});
        },
        componentWillUnmount: function() {
            this.state.view.tearDown();
        },
        render: function() {
            return React.createElement(this.props.wrapperElement, {ref: 'wrapper'});
        }
    });

    function BackboneViewWrapper(View) {
        return React.createClass({
            render: function() {
                return <BackboneViewWrapperClass ref='wrapper' {...this.props} View={View} />;
            }
        });
    }

    return BackboneViewWrapper;
});
