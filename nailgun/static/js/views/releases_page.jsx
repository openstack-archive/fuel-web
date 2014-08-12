/*
 * Copyright 2013 Mirantis, Inc.
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
    'jsx!component_mixins'
],
function(React, utils, componentMixins) {
    'use strict';

    var ReleasesPage = React.createClass({
        mixins: [
            componentMixins.pollingMixin(5),
            React.BackboneMixin('releases'),
            React.BackboneMixin('tasks'),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.tasks.findTask({group: 'release_setup', status: 'running'});
            }})
        ],
        navbarActiveElement: 'releases',
        breadcrumbsPath: [['home', '#'], 'releases'],
        title: function() {
            return $.t('release_page.title');
        },
        shouldDataBeFetched: function() {
            return !!this.props.tasks.findTask({group: 'release_setup', status: 'running'});
        },
        fetchData: function() {
            this.props.tasks.fetch();
        },
        render: function() {
            return (
                <div>
                    <h3 className='page-title'>{$.t('release_page.title')}</h3>
                    <div className='table-releases-box'>
                        {this.props.releases.length ?
                            <table className='table table-bordered table-striped releases-table'>
                                <thead>
                                    <tr>
                                        {_.map(['name', 'version', 'status'], function(attr, index) {
                                            return <th key={index} className={attr}>{$.t('release_page.' + attr)}</th>;
                                        })}
                                    </tr>
                                </thead>
                                <tbody>
                                    {this.props.releases.map(function(release) {
                                        return <Release
                                            key={release.id}
                                            release={release}
                                            task={this.props.tasks.findTask({group: 'release_setup', release: release.id})} />;
                                    }, this)}
                                </tbody>
                            </table>
                        :
                          <div className='alert'>{$.t('release_page.no_releases_message')}</div>
                        }
                    </div>
                </div>
            );
        }
    });

    var Release = React.createClass({
        mixins: [
            React.BackboneMixin('release'),
            React.BackboneMixin('task')
        ],
        componentWillUpdate: function() {
            var task = this.props.task;
            if (!task.match({status: 'running'})) {
                this.props.release.fetch();
                app.navbar.refresh();
                if (task.match({status: 'ready'})) {
                    task.destroy();
                }
            }
        },
        render: function() {
            var release = this.props.release,
                stateLabel = $.t('release_page.release.' + release.get('state')),
                task = this.props.task;
            return (
                <tr>
                    <td className='enable-selection'>
                        {release.get('name')}
                        {(task && task.match({status: 'error'})) &&
                            <div className='release-error' dangerouslySetInnerHTML={{__html: utils.urlify(task.escape('message'))}}></div>
                        }
                    </td>
                    <td className='enable-selection'>{release.get('version')}</td>
                    <td>
                        {task ?
                            <div className='download_progress'>
                                <div className='progress progress-success progress-striped active'>
                                    <div className='bar' style={'width: ' + task.get('progress') + '%'}></div>
                                </div>
                                <div className='bar-title'>
                                    <span>{stateLabel}</span>: <span className='bar-title-progress'>{task.get('progress')}%</span>
                                </div>
                            </div>
                        :
                            <span className={'enable-selection' + release.get('state')}>{stateLabel}</span>
                        }
                    </td>
                </tr>
            );
        }
    });

    return ReleasesPage;
});
