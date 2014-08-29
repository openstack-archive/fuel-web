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
define(['jquery', 'underscore', 'react'], function($, _, React) {
    'use strict';

    return {
        pollingMixin: function(updateInterval) {
            updateInterval = updateInterval * 1000;
            return {
                scheduleDataFetch: function() {
                    var shouldDataBeFetched = !_.isFunction(this.shouldDataBeFetched) || this.shouldDataBeFetched();
                    if (this.isMounted() && !this.activeTimeout && shouldDataBeFetched) {
                        this.activeTimeout = $.timeout(updateInterval).done(_.bind(this.startPolling, this));
                    }
                },
                startPolling: function() {
                    var shouldDataBeFetched = !_.isFunction(this.shouldDataBeFetched) || this.shouldDataBeFetched();
                    if (shouldDataBeFetched) {
                        this.stopPolling();
                        this.fetchData().always(_.bind(this.scheduleDataFetch, this));
                    }
                },
                stopPolling: function() {
                    if (this.activeTimeout) {
                        this.activeTimeout.clear();
                    }
                    delete this.activeTimeout;
                },
                componentDidMount: function() {
                    this.startPolling();
                }
            };
        },
        dialogMixin: {
            componentDidMount: function() {
                var $el = $(this.getDOMNode());
                var modalOptions = _.clone(this.props.modalOptions) || {};
                _.defaults(modalOptions, {background: true, keyboard: true});
                $el.modal(modalOptions);
                $el.on('hidden', this.handleHidden);
                $el.on('shown', function() {
                    $el.find('input:first').focus();
                });
            },
            componentWillUnmount: function() {
                $(this.getDOMNode()).off('shown hidden');
            },
            handleHidden: function() {
                React.unmountComponentAtNode(this.getDOMNode().parentNode);
            },
            close: function() {
                $(this.getDOMNode()).modal('hide');
            },
            setDefaultValues: function(errorTitle, errorMessage) {
                return {title: errorTitle || $.t('dialog.error_dialog.title'), message: errorMessage || $.t('dialog.error_dialog.warning')};
            },
            showError: function(error) {
                this.setState({
                    showError: true,
                    errorTitle: error.title,
                    errorMessage: error.message
                });
            },
            render: function() {
                var error = {};
                if (this.props.showError) {
                    error = this.setDefaultValues(this.props.title, this.props.message);
                } else if (this.state && this.state.showError) {
                    error = this.setDefaultValues(this.state.errorTitle, this.state.errorMessage);
                }
                return (
                    <div className="modal fade" tabIndex="-1">
                        <div className="modal-header">
                            <button type="button" className="close" onClick={this.close}>&times;</button>
                            <h3>{error.title || this.props.title}</h3>
                        </div>
                            <div>
                                <div className="modal-body">
                                    {error.message || this.renderBody()}
                                </div>
                                <div className="modal-footer">
                                    {(this.renderFooter && !error.message) ? this.renderFooter() : <button className="btn" onClick={this.close}>{$.t('common.close_button')}</button>}
                                </div>
                            </div>
                    </div>
                );
            }
        }
    };
});
