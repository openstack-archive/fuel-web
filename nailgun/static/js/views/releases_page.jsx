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
    'jsx!views/controls'
],
function(React, controls) {
    'use strict';

    var ReleasesPage = React.createClass({
        getInitialState: function() {
            return {columns: ['name', 'version', 'state']};
        },
        mixins: [
            React.BackboneMixin('releases')
        ],
        navbarActiveElement: 'releases',
        breadcrumbsPath: [['home', '#'], 'releases'],
        title: function() {
            return $.t('release_page.title');
        },
        getReleaseData: function(release) {
            return _.map(this.state.columns, function(attr) {
                if (attr == 'state') return $.t('release_page.release.' + release.get(attr));
                return release.get(attr) || $.t('common.not_available');
            });
        },
        render: function() {
            return (
                <div>
                    <h3 className='page-title'>{$.t('release_page.title')}</h3>
                    <div className='table-releases-box'>
                        {this.props.releases.length ?
                            <controls.Table
                                head={_.map(this.state.columns, function(column) {
                                    return {label: $.t('release_page.' + column), className: column};
                                })}
                                body={this.props.releases.map(this.getReleaseData)}
                                tableClassName='releases-table'
                            />
                        :
                            <div className='alert'>{$.t('release_page.no_releases_message')}</div>
                        }
                    </div>
                </div>
            );
        }
    });

    return ReleasesPage;
});
