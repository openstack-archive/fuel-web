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
define(['jquery', 'underscore', 'backbone', 'dispatcher', 'react', 'react.backbone'], function($, _, Backbone, dispatcher, React) {
    'use strict';

    return {
        backboneMixin: React.BackboneMixin,
        dispatcherMixin: function(events, callback) {
            return {
                componentDidMount: function() {
                    dispatcher.on(events, _.isString(callback) ? this[callback] : callback, this);
                },
                componentWillUnmount: function() {
                    dispatcher.off(null, null, this);
                }
            };
        },
        pollingMixin: function(updateInterval, delayedStart) {
            updateInterval = updateInterval * 1000;
            return {
                scheduleDataFetch: function() {
                    var shouldDataBeFetched = !_.isFunction(this.shouldDataBeFetched) || this.shouldDataBeFetched();
                    if (this.isMounted() && !this.activeTimeout && shouldDataBeFetched) {
                        this.activeTimeout = _.delay(this.startPolling, updateInterval);
                    }
                },
                startPolling: function(force) {
                    var shouldDataBeFetched = force || !_.isFunction(this.shouldDataBeFetched) || this.shouldDataBeFetched();
                    if (shouldDataBeFetched) {
                        this.stopPolling();
                        return this.fetchData().always(this.scheduleDataFetch);
                    }
                },
                stopPolling: function() {
                    if (this.activeTimeout) clearTimeout(this.activeTimeout);
                    delete this.activeTimeout;
                },
                componentDidMount: function() {
                    if (delayedStart) {
                        this.scheduleDataFetch();
                    } else {
                        this.startPolling();
                    }
                },
                componentWillUnmount: function() {
                    this.stopPolling();
                }
            };
        },
        outerClickMixin: {
            propTypes: {
                toggle: React.PropTypes.func.isRequired
            },
            getInitialState: function() {
                return {
                    clickEventName: 'click.' + _.uniqueId('outer-click')
                };
            },
            handleBodyClick: function(e) {
                if (!$(e.target).closest(this.getDOMNode()).length) {
                    _.defer(_.partial(this.props.toggle, false));
                }
            },
            componentDidMount: function() {
                $('html').on(this.state.clickEventName, this.handleBodyClick);
                Backbone.history.on('route', _.partial(this.props.toggle, false), this);
            },
            componentWillUnmount: function() {
                $('html').off(this.state.clickEventName);
                Backbone.history.off('route', null, this);
            }
        },
        nodeConfigurationScreenMixin: {
            getNodeList: function(options) {
                var utils = require('utils'),
                    models = require('models'),
                    nodeIds = utils.deserializeTabOptions(options.screenOptions[0]).nodes,
                    ids = nodeIds ? nodeIds.split(',').map(function(id) {return parseInt(id, 10);}) : [],
                    nodes = new models.Nodes(options.cluster.get('nodes').getByIds(ids));

                if (nodes.length && nodes.length == ids.length) {return nodes;}
            },
            goToNodeList: function() {
                app.navigate('#cluster/' + this.props.cluster.id + '/nodes', {trigger: true, replace: true});
            },
            isLocked: function() {
                return !!this.props.cluster.task({group: 'deployment', status: 'running'}) || !_.all(this.props.nodes.invoke('isConfigurable'));
            },
            showDiscardChangesDialog: function() {
                var dialogs = require('jsx!views/dialogs');
                dialogs.DiscardSettingsChangesDialog.show({cb: this.goToNodeList});
            },
            returnToNodeList: function() {
                if (this.hasChanges()) {
                    this.showDiscardChangesDialog();
                } else {
                    this.goToNodeList();
                }
            }
        }
    };
});
