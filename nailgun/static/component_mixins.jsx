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
define(['jquery', 'underscore', 'i18n', 'backbone', 'dispatcher', 'react', 'react.backbone'], function($, _, i18n, Backbone, dispatcher, React) {
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
            isLockedScreen: function() {
                var nodesAvailableForChanges = this.props.nodes.any(function(node) {
                    return node.get('pending_addition') || node.get('status') == 'error';
                });
                return !nodesAvailableForChanges ||
                    this.props.cluster && !!this.props.cluster.tasks({group: 'deployment', status: 'running'}).length;
            },
            showDiscardChangesDialog: function() {
                var dialogs = require('jsx!views/dialogs');
                // TODO: need to check possibility to use onLeaveCheckMixin in this place
                dialogs.DiscardSettingsChangesDialog.show({
                    href: '#cluster/' + this.props.cluster.id + '/nodes'
                });
            },
            returnToNodeList: function() {
                if (this.hasChanges()) {
                    this.showDiscardChangesDialog();
                } else {
                    app.navigate('#cluster/' + this.props.cluster.id + '/nodes', {trigger: true, replace: true});
                }
            }
        },
        onLeaveCheckMixin: {
            onLeave: function(e) {
                var dialogs = require('jsx!views/dialogs'),
                    href = $(e.currentTarget).attr('href'),
                    options = this.state.onLeaveCheckOptions || {};

                if (Backbone.history.getHash() != href.substr(1) && _.result(this, 'hasChanges')) {
                    e.preventDefault();
                    dialogs.DiscardSettingsChangesDialog.show({
                        message: _.result(options, 'message') || undefined,
                        hideLeaveButton: _.result(options, 'hideLeaveButton'),
                        href: href,
                        cb: options.cb
                    });
                }
            },
            componentWillMount: function() {
                $(window).on('beforeunload.' + this.state.eventNamespace, _.bind(this.onBeforeunloadEvent, this));
                $('body').on('click.' + this.state.eventNamespace, 'a[href^=#]:not(.no-leave-check)', _.bind(this.onLeave, this));
            },
            componentWillUnmount: function() {
                $(window).off('beforeunload.' + this.state.eventNamespace);
                $('body').off('click.' + this.state.eventNamespace);
            },
            onBeforeunloadEvent: function() {
                if (this.hasChanges()) return i18n('dialog.dismiss_settings.default_message');
            }
        }
    };
});
