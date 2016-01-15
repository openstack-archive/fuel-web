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
import $ from 'jquery';
import _ from 'underscore';
import Backbone from 'backbone';
import i18n from 'i18n';
import React from 'react';
import ReactDOM from 'react-dom';
import dispatcher from 'dispatcher';
import {DiscardSettingsChangesDialog} from 'views/dialogs';
import 'react.backbone';

        export var backboneMixin = React.BackboneMixin;

        export function dispatcherMixin(events, callback) {
            return {
                componentDidMount() {
                    dispatcher.on(events, _.isString(callback) ? this[callback] : callback, this);
                },
                componentWillUnmount() {
                    dispatcher.off(null, null, this);
                }
            };
        }

        export var unsavedChangesMixin = {
            onBeforeunloadEvent() {
                if (this.hasChanges()) return _.result(this, 'getStayMessage') || i18n('dialog.dismiss_settings.default_message');
            },
            componentWillMount() {
                this.eventName = _.uniqueId('unsavedchanges');
                $(window).on('beforeunload.' + this.eventName, this.onBeforeunloadEvent);
                $('body').on('click.' + this.eventName, 'a[href^=#]:not(.no-leave-check)', this.onLeave);
            },
            componentWillUnmount() {
                $(window).off('beforeunload.' + this.eventName);
                $('body').off('click.' + this.eventName);
            },
            onLeave(e) {
                var href = $(e.currentTarget).attr('href');
                if (Backbone.history.getHash() !== href.substr(1) && _.result(this, 'hasChanges')) {
                    e.preventDefault();

                    DiscardSettingsChangesDialog
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
        };

        export function pollingMixin(updateInterval, delayedStart) {
            updateInterval = updateInterval * 1000;
            return {
                scheduleDataFetch() {
                    var shouldDataBeFetched = !_.isFunction(this.shouldDataBeFetched) || this.shouldDataBeFetched();
                    if (this.isMounted() && !this.activeTimeout && shouldDataBeFetched) {
                        this.activeTimeout = _.delay(this.startPolling, updateInterval);
                    }
                },
                startPolling(force) {
                    var shouldDataBeFetched = force || !_.isFunction(this.shouldDataBeFetched) || this.shouldDataBeFetched();
                    if (shouldDataBeFetched) {
                        this.stopPolling();
                        return this.fetchData().always(this.scheduleDataFetch);
                    }
                },
                stopPolling() {
                    if (this.activeTimeout) clearTimeout(this.activeTimeout);
                    delete this.activeTimeout;
                },
                componentDidMount() {
                    if (delayedStart) {
                        this.scheduleDataFetch();
                    } else {
                        this.startPolling();
                    }
                },
                componentWillUnmount() {
                    this.stopPolling();
                }
            };
        }

        export var outerClickMixin = {
            propTypes: {
                toggle: React.PropTypes.func.isRequired
            },
            getInitialState() {
                return {
                    clickEventName: 'click.' + _.uniqueId('outer-click')
                };
            },
            handleBodyClick(e) {
                if (!$(e.target).closest(ReactDOM.findDOMNode(this)).length) {
                    _.defer(_.partial(this.props.toggle, false));
                }
            },
            componentDidMount() {
                $('html').on(this.state.clickEventName, this.handleBodyClick);
                Backbone.history.on('route', _.partial(this.props.toggle, false), this);
            },
            componentWillUnmount() {
                $('html').off(this.state.clickEventName);
                Backbone.history.off('route', null, this);
            }
        };

        export function renamingMixin(refname) {
            return {
                getInitialState() {
                    return {
                        isRenaming: false,
                        renamingMixinEventName: 'click.' + _.uniqueId('rename')
                    };
                },
                componentWillUnmount() {
                    $('html').off(this.state.renamingMixinEventName);
                },
                startRenaming(e) {
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
                endRenaming() {
                    $('html').off(this.state.renamingMixinEventName);
                    this.setState({
                        isRenaming: false,
                        actionInProgress: false
                    });
                }
            };
        }
