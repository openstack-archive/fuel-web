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
define(
[
    'jquery',
    'underscore',
    'react',
    'i18n'
],
function($, _, React, i18n) {
    'use strict';

    var ns = 'cluster_page.nodes_tab.configure_interfaces.';

    var OffloadingModesControl = React.createClass({
        propTypes: {
            interface: React.PropTypes.object
        },
        getInitialState: function() {
            return {
                isVisible: false
            };
        },
        toggleVisibility: function() {
            this.setState({isVisible: !this.state.isVisible});
        },
        setModeState: function(mode, state) {
            mode.state = state;
            if (!_.isEmpty(mode.sub)) {
                mode.sub.forEach((function(mode) {this.setModeState(mode, state)}).bind(this));
            }
        },
        checkModes: function(mode, sub) {
            var changedState = sub.reduce(
                    (function(state, childMode) {
                        if (!_.isEmpty(childMode.sub)) {
                            this.checkModes(childMode, childMode.sub);
                        }
                        return (state === 0 || state === childMode.state) ? childMode.state : -1;
                    }).bind(this),
                    0
                ),
                oldState;

            if (mode && mode.state != changedState) {
                oldState = mode.state;
                mode.state = oldState === false ? null : (changedState === false ? false : oldState);
            }
        },
        findMode: function(name, modes) {
            var result,
                mode,
                i,
                l;
            for (i = 0, l = modes.length; i < l; i++) {
                mode = modes[i];
                if (mode.name == name) {
                    return mode;
                } else if (!_.isEmpty(mode.sub)) {
                    result = this.findMode(name, mode.sub);
                    if (result) {
                        break;
                    }
                }
            }
            return result;
        },
        rotateModeState: function(name) {
            var rotate = {
                    true: false,
                    false: null,
                    null: true
                },
                modes = _.deepClone(this.props.interface.get('offloading_modes') || []),
                mode = this.findMode(name, modes);

            return (function() {
                if (!_.isEmpty(mode)) {
                    this.setModeState(mode, rotate[mode.state]);
                    this.checkModes(null, modes);
                    this.props.interface.set('offloading_modes', modes);
                }
            }).bind(this);
        },
        renderChildModes: function(modes) {
            var states = {
                    true: i18n(ns + 'offloading_enabled'),
                    false: i18n(ns + 'offloading_disabled'),
                    null: i18n(ns + 'offloading_default')
                };
            return <ul>
                {modes.map((function(mode) {
                    var state = states[mode.state];
                    return <li key={mode.name}>
                        <div className={state} onClick={this.rotateModeState(mode.name)}>{state}</div>
                        {mode.name}
                        {mode.sub &&
                            <ul>{this.renderChildModes(mode.sub)}</ul>
                        }
                    </li>
                    }).bind(this))
                }
                </ul>
        },
        render: function() {
            var ns = 'cluster_page.nodes_tab.configure_interfaces.',
                modes = this.props.interface.get('offloading_modes') || [];
            return <div className='offloading-modes pull-right'>
                <div>
                    <button className='btn btn-default' onClick={this.toggleVisibility}>{i18n(ns + 'offloading_modes')}</button>
                    {this.state.isVisible &&
                        this.renderChildModes(modes)
                    }
                </div>
            </div>
        }
    });

    return OffloadingModesControl;
});
