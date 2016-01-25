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
import _ from 'underscore';
import i18n from 'i18n';
import React from 'react';
import {Table} from 'views/controls';
import {backboneMixin} from 'component_mixins';

var ReleasesPage = React.createClass({
  mixins: [backboneMixin('releases')],
  getDefaultProps() {
    return {columns: ['name', 'version', 'state']};
  },
  statics: {
    title: i18n('release_page.title'),
    navbarActiveElement: 'releases',
    breadcrumbsPath: [['home', '#'], 'releases'],
    fetchData() {
      var releases = app.releases;
      return releases.fetch({cache: true}).then(() => ({releases}));
    }
  },
  getReleaseData(release) {
    return _.map(this.props.columns, (attr) => {
      if (attr === 'state') {
        return i18n('release_page.release.' + (release.get(attr)));
      }
      return release.get(attr) || i18n('common.not_available');
    });
  },
  render() {
    return (
      <div className='releases-page'>
        <div className='page-title'>
          <h1 className='title'>{i18n('release_page.title')}</h1>
        </div>
        <div className='content-box'>
          <div className='row'>
            <div className='col-xs-12 content-elements'>
              <Table
                head={_.map(this.props.columns, (column) => {
                  return ({label: i18n('release_page.' + column), className: column});
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

export default ReleasesPage;
