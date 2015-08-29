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
    'underscore',
    'i18n',
    'react',
    'models',
    'jsx!views/controls',
    'jsx!component_mixins'
],
function(_, i18n, React, models, controls, componentMixins) {
    'use strict';

    var ReleasesPage = React.createClass({
        mixins: [componentMixins.backboneMixin('releases')],
        getDefaultProps: function() {
            return {columns: ['name', 'version', 'is_deployable']};
        },
        statics: {
            title: i18n('release_page.title'),
            navbarActiveElement: 'releases',
            breadcrumbsPath: [['home', '#'], 'releases'],
            fetchData: function() {
                var releases = new models.Releases();
                return releases.fetch().then(function() {
                    return {releases: releases};
                });
            }
        },
        getReleaseData: function(release) {
            return _.map(this.props.columns, function(attr) {
                if (attr == 'is_deployable') {
                    return i18n('release_page.release.' + (release.get(attr) ? 'available' : 'not_available'));
                }
                return release.get(attr) || i18n('common.not_available');
            });
        },
        render: function() {
            return (
                <div className='releases-page'>
                    <div className='page-title'>
                        <h1 className='title'>{i18n('release_page.title')}</h1>
                    </div>
                    <div className='content-box'>
                        <div className='row'>
                            <div className='col-xs-12 content-elements'>
                                <controls.Table
                                    head={_.map(this.props.columns, function(column) {
                                        return {label: i18n('release_page.' + column), className: column};
                                    })}
                                    body={this.props.releases.map(this.getReleaseData)}
                                />
                            </div>
                        </div>
                    </div>
                </div>
            );
        }
    });

    return ReleasesPage;
});
