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
    'react',
    'utils',
    'models',
    'jsx!views/dialogs'
],
function(React, utils, models, dialogs) {
    'use strict';

    var NotificationsPage, Notification;

    NotificationsPage = React.createClass({
        mixins: [React.BackboneMixin('notifications')],
        navbarActiveElement: null,
        breadcrumbsPath: [['home', '#'], 'notifications'],
        title: function() {
            return $.t('notifications_page.title');
        },
        render: function() {
            return (
                <div>
                    <h3 className='page-title'>{$.t('notifications_page.title')}</h3>
                    <ul className='notification-list page-wrapper'>
                        {this.props.notifications.map(function(notification) {
                            return this.transferPropsTo(<Notification key={'notification' + notification.id} notification={notification} />);
                        }, this)}
                    </ul>
                </div>
            );
        }
    });

    Notification = React.createClass({
        mixins: [React.BackboneMixin('notification')],
        showNodeInfo: function(id) {
            var node = new models.Node({id: id});
            node.deferred = node.fetch();
            (new dialogs.ShowNodeInfoDialog({node: node})).render();
        },
        markAsRead: function() {
            var notification = this.props.notification;
            notification.toJSON = function() {
                return _.pick(notification.attributes, 'id', 'status');
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
