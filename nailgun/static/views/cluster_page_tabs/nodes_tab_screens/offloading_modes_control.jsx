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
    'i18n',
    'utils'
],
function($, _, React, i18n, utils) {
    'use strict';

    var ns = 'cluster_page.nodes_tab.configure_interfaces.',
        OffloadingModesControl = React.createClass({
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
            _.each(mode.sub, function(mode) {this.setModeState(mode, state)}, this);
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
                index = 0,
                modesLength = modes.length;
            for (; index < modesLength; index++) {
                mode = modes[index];
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
        onModeStateChange: function(name, state) {
            var modes = _.deepClone(this.props.interface.get('offloading_modes') || []),
                mode = this.findMode(name, modes);

            return (function() {
                if (!_.isEmpty(mode)) {
                    this.setModeState(mode, state);
                    this.checkModes(null, modes);
                    this.props.interface.set('offloading_modes', modes);
                }
            }).bind(this);
        },
        makeOffloadingModesExcerpt: function() {
            var states = {
                    true: i18n(ns + 'offloading_enabled'),
                    false: i18n(ns + 'offloading_disabled'),
                    null: i18n(ns + 'offloading_default')
                },
                lastState = -1,
                added = 0,
                modes = this.props.interface.get('offloading_modes'),
                excerpt = modes.map(
                    function(mode) {
                        if (mode.state !== null && mode.state !== lastState) {
                            lastState = mode.state;
                            added++;
                            return (added > 1 ? ', ' : '') +
                                mode.name + ' ' + states[mode.state];
                        }
                        return null;
                    });
            if (added) {
                if (added < modes.length) {
                    excerpt.push(', ...');
                }
                return excerpt;
            } else {
                return states[null];
            }
        },
        renderChildModes: function(modes, level) {
            return modes.map((function(mode) {
                var lines = [
                    <tr key={mode.name} className={'level' + level}>
                        <td>{mode.name}</td>
                        {[true, false, null].map((function(modeState) {
                            var styles = {
                                'btn-link': true,
                                active: mode.state === modeState
                            };
                            return (
                                <td key={mode.name + modeState}>
                                    <button
                                        className={utils.classNames(styles)}
                                        onClick={this.onModeStateChange(mode.name, modeState)}>
                                        <i className='glyphicon glyphicon-ok'></i>
                                    </button>
                                </td>
                            );
                        }).bind(this))}
                    </tr>
                ];
                if (mode.sub) {
                    return _.union([lines, this.renderChildModes(mode.sub, level + 1)]);
                }
                return lines;
            }).bind(this));
        },
        render: function() {
            var modes = this.props.interface.get('offloading_modes') || [];
            return (
                <div className='offloading-modes'>
                    <div>
                        <button className='btn btn-default' onClick={this.toggleVisibility}>
                            {i18n(ns + 'offloading_modes')}: {this.makeOffloadingModesExcerpt()}
                        </button>
                        {this.state.isVisible &&
                            <table className='table'>
                                <thead>
                                    <tr>
                                        <th>{i18n(ns + 'offloading_mode')}</th>
                                        <th>{i18n(ns + 'offloading_enabled')}</th>
                                        <th>{i18n(ns + 'offloading_disabled')}</th>
                                        <th>{i18n(ns + 'offloading_default')}</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {this.renderChildModes(modes, 1)}
                                </tbody>
                            </table>
                        }
                    </div>
                </div>
            );
        }
    });

    return OffloadingModesControl;
});
