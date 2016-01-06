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
    'jquery',
    'underscore',
    'backbone',
    'utils',
    'i18n',
    'dispatcher',
    'react',
    'react-dom',
    'react.backbone'
], ($, _, Backbone, utils, i18n, dispatcher, React, ReactDOM) => {
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
        unsavedChangesMixin: {
            onBeforeunloadEvent: function() {
                if (this.hasChanges()) return _.result(this, 'getStayMessage') || i18n('dialog.dismiss_settings.default_message');
            },
            componentWillMount: function() {
                this.eventName = _.uniqueId('unsavedchanges');
                $(window).on('beforeunload.' + this.eventName, this.onBeforeunloadEvent);
                $('body').on('click.' + this.eventName, 'a[href^=#]:not(.no-leave-check)', this.onLeave);
            },
            componentWillUnmount: function() {
                $(window).off('beforeunload.' + this.eventName);
                $('body').off('click.' + this.eventName);
            },
            onLeave: function(e) {
                var href = $(e.currentTarget).attr('href');
                if (Backbone.history.getHash() != href.substr(1) && _.result(this, 'hasChanges')) {
                    e.preventDefault();

                    var dialogs = require('views/dialogs');
                    dialogs.DiscardSettingsChangesDialog
                        .show({
                            isDiscardingPossible: _.result(this, 'isDiscardingPossible'),
                            isSavingPossible: _.result(this, 'isSavingPossible'),
                            applyChanges: this.applyChanges,
                            revertChanges: this.revertChanges
                        }).done(() => {
                            app.navigate(href, {trigger: true});
                        });
                }
            }
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
                if (!$(e.target).closest(ReactDOM.findDOMNode(this)).length) {
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
        renamingMixin: function(refname) {
            return {
                getInitialState: function() {
                    return {
                        isRenaming: false,
                        renamingMixinEventName: 'click.' + _.uniqueId('rename')
                    };
                },
                componentWillUnmount: function() {
                    $('html').off(this.state.renamingMixinEventName);
                },
                startRenaming: function(e) {
                    e.preventDefault();
                    $('html').on(this.state.renamingMixinEventName, (e) => {
                        if (e && !$(e.target).closest(ReactDOM.findDOMNode(this.refs[refname])).length) {
                            this.endRenaming();
                        } else {
                            e.preventDefault();
                        }
                    });
                    this.setState({isRenaming: true});
                },
                endRenaming: function() {
                    $('html').off(this.state.renamingMixinEventName);
                    this.setState({
                        isRenaming: false,
                        actionInProgress: false
                    });
                }
            };
        }
    };
});
