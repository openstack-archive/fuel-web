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
define(
[
    'i18n',
    'react',
    'utils',
    'models',
    'views/dialogs',
    'component_mixins'
],
function(i18n, React, utils, models, dialogs, componentMixins) {
    'use strict';

    var NotificationsPage, Notification;

    NotificationsPage = React.createClass({
        mixins: [componentMixins.backboneMixin('notifications')],
        statics: {
            title: i18n('notifications_page.title'),
            navbarActiveElement: null,
            breadcrumbsPath: [['home', '#'], 'notifications'],
            fetchData: function() {
                var notifications = app.notifications;
                return notifications.fetch().then(function() {
                    return {notifications: notifications};
                });
            }
        },
        render: function() {
            return (
                <div className='notifications-page'>
                    <div className='page-title'>
                        <h1 className='title'>{i18n('notifications_page.title')}</h1>
                    </div>
                    <div className='content-box'>
                        {this.props.notifications.map(function(notification, index) {
                            return [
                                !!index && <hr />,
                                <Notification
                                    {...this.props}
                                    key={'notification' + notification.id}
                                    notification={notification}
                                />
                            ];
                        }, this)}
                    </div>
                </div>
            );
        }
    });

    Notification = React.createClass({
        mixins: [componentMixins.backboneMixin('notification')],
        showNodeInfo: function(id) {
            var node = new models.Node({id: id});
            node.fetch();
            dialogs.ShowNodeInfoDialog.show({node: node});
        },
        markAsRead: function() {
            var notification = this.props.notification;
            notification.toJSON = function() {
                return notification.pick('id', 'status');
            };
            notification.save({status: 'read'});
        },
        onNotificationClick: function() {
            var notification = this.props.notification;
            if (notification.get('status') == 'unread') {
                this.markAsRead();
            }
            var nodeId = notification.get('node_id');
            if (nodeId) {
                this.showNodeInfo(nodeId);
            }
        },
        render: function() {
            var notification = this.props.notification,
                notificationClasses = {
                    'text-danger': notification.get('topic') == 'error',
                    'text-warning': notification.get('topic') == 'warning',
                    unread: notification.get('status') == 'unread'
                },
                iconClass = {
                    error: 'glyphicon-exclamation-sign',
                    warning: 'glyphicon-warning-sign',
                    discover: 'glyphicon-bell'
                }[notification.get('topic')] || 'glyphicon-info-sign';
            return (
                <div className={'row notification ' + utils.classNames(notificationClasses)} onClick={this.onNotificationClick}>
                    <div className='col-xs-12 col-md-2'>
                        <i className={'glyphicon ' + iconClass}></i>
                        {notification.get('date')} {notification.get('time')}
                    </div>
                    <div className='col-xs-12 col-md-10'>
                        <span className={notification.get('node_id') && 'btn btn-link'} dangerouslySetInnerHTML={{__html: utils.urlify(notification.escape('message'))}}></span>
                    </div>
                </div>
            );
        }
    });

    return NotificationsPage;
});
