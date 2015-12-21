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
            _.each(mode.sub, function(mode) {this.setModeState(mode, state);}, this);
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
            var modes = _.cloneDeep(this.props.interface.get('offloading_modes') || []),
                mode = this.findMode(name, modes);

            return () => {
                if (mode) {
                    this.setModeState(mode, state);
                    this.checkModes(null, modes);
                } else {
                    // handle All Modes click
                    _.each(modes, function(mode) {
                        return this.setModeState(mode, state);
                    }, this);
                }
                this.props.interface.set('offloading_modes', modes);
            };
        },
        makeOffloadingModesExcerpt: function() {
            var states = {
                    true: i18n(ns + 'offloading_enabled'),
                    false: i18n(ns + 'offloading_disabled'),
                    null: i18n(ns + 'offloading_default')
                },
                ifcModes = this.props.interface.get('offloading_modes');

            if (_.uniq(_.pluck(ifcModes, 'state')).length == 1) {
                return states[ifcModes[0].state];
            }

            var lastState,
                added = 0,
                excerpt = [];
            _.each(ifcModes,
                    (mode) => {
                        if (!_.isNull(mode.state) && mode.state !== lastState) {
                            lastState = mode.state;
                            added++;
                            excerpt.push((added > 1 ? ', ' : '') + mode.name + ' ' + states[mode.state]);
                        }
                        // show no more than two modes in the button
                        if (added == 2) return false;
                    }
                );
            if (added < ifcModes.length) excerpt.push(', ...');
            return excerpt;
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
                                        disabled={this.props.disabled}
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
            var modes = [],
                ifcModes = this.props.interface.get('offloading_modes');
            if (ifcModes) {
                modes.push({
                    name: i18n(ns + 'all_modes'),
                    state: _.uniq(_.pluck(ifcModes, 'state')).length == 1 ? ifcModes[0].state : undefined,
                    sub: ifcModes
                });
            }

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
