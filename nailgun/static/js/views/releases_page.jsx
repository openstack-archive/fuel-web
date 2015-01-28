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
    'jquery',
    'underscore',
    'i18n',
    'react',
    'models',
    'utils',
    'jsx!views/dialogs',
    'jsx!views/controls',
    'jsx!component_mixins'
],
function($, _, i18n, React, models, utils, dialogs, controls, componentMixins) {
    'use strict';

    var ReleasesPage = React.createClass({
        mixins: [componentMixins.backboneMixin('releases')],
        getDefaultProps: function() {
            return {columns: ['name', 'version', 'state']};
        },
        statics: {
            title: i18n('release_page.title'),
            navbarActiveElement: 'releases',
            breadcrumbsPath: [['home', '#'], 'releases'],
            fetchData: function() {
                var releases = new models.Releases();
                return $.when(releases.fetch(), app.tasks.fetch({data: {cluster_id: ''}})).then(function() {
                    return {
                        releases: releases,
                        tasks: new models.Tasks(app.tasks.filterTasks({name: 'prepare_release', status: 'running'}))
                    };
                });
            }
        },
        getReleaseData: function(release) {
            return _.map(this.props.columns, function(attr) {
                if (attr == 'state') {
                    var task = this.props.tasks.findTask({release: release.id});
                    if (task) {
                        return (
                            <div className='progress progress-success progress-striped active'>
                                <div className='bar' style={{width: '100%'}}></div>
                            </div>
                        );
                    }
                    if (release.get(attr) == 'unavailable') {
                        return <button className='btn' onClick={_.bind(this.showUploadISODialog, this, release)}>{i18n('release_page.upload_iso')}</button>;
                    }
                    return i18n('release_page.states.' + release.get(attr));
                }
                return release.get(attr) || i18n('common.not_available');
            }, this);
        },
        showUploadISODialog: function(release) {
            utils.showDialog(dialogs.UploadISODialog, {release: release});
        },
        render: function() {
            return (
                <div>
                    <h3 className='page-title'>{i18n('release_page.title')}</h3>
                    <div className='table-releases-box'>
                        {this.props.releases.length ?
                            <controls.Table
                                head={_.map(this.props.columns, function(column) {
                                    return {label: i18n('release_page.' + column), className: column};
                                })}
                                body={this.props.releases.map(this.getReleaseData)}
                                tableClassName='releases-table'
                            />
                        :
                            <div className='alert'>{i18n('release_page.no_releases_message')}</div>
                        }
                    </div>
                </div>
            );
        }
    });

    return ReleasesPage;
});
