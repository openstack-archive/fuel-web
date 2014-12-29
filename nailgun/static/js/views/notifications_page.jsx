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
    'jsx!views/dialogs',
    'jsx!component_mixins'
],
function(i18n, React, utils, models, dialogs, componentMixins) {
    'use strict';

    var NotificationsPage, Notification;

    NotificationsPage = React.createClass({
        mixins: [componentMixins.backboneMixin('notifications')],
        navbarActiveElement: null,
        breadcrumbsPath: [['home', '#'], 'notifications'],
        title: function() {
            return i18n('notifications_page.title');
        },
        statics: {
            fetchData: function() {
                var notifications = app.navbar.props.notifications;
                return notifications.fetch().then(function() {
                    return {notifications: notifications};
                });
            }
        },
        render: function() {
            return (
                <div>
                    <h3 className='page-title'>{i18n('notifications_page.title')}</h3>
                    <ul className='notification-list page-wrapper'>
                        {this.props.notifications.map(function(notification) {
                            return <Notification {...this.props} key={'notification' + notification.id} notification={notification} />;
                        }, this)}
                    </ul>
                </div>
            );
        }
    });

    Notification = React.createClass({
        mixins: [componentMixins.backboneMixin('notification')],
        showNodeInfo: function(id) {
            var node = new models.Node({id: id});
            node.deferred = node.fetch();
            utils.showDialog(dialogs.ShowNodeInfoDialog, {node: node, title: node.get('name')});
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
                topic = notification.get('topic'),
                notificationClass = topic + ' ' + notification.get('status') + ' ' + (notification.get('node_id') ? 'clickable' : ''),
                iconClass = {error: 'icon-attention', discover: 'icon-bell'}[topic] || 'icon-info-circled';
            return (
                <li className={notificationClass} onClick={this.onNotificationClick}>
                    <div className='icon'><i className={iconClass}></i></div>
                    <div className='datetime enable-selection'>
                        {notification.get('date')} {notification.get('time')}
                    </div>
                    <div
                        className='message enable-selection'
                        dangerouslySetInnerHTML={{__html: utils.urlify(notification.escape('message'))}}
                    ></div>
                </li>
            );
        }
    });

    return NotificationsPage;
});
