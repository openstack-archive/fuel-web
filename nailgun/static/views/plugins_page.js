/*
 * Copyright 2015 Mirantis, Inc.
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
import i18n from 'i18n';
import React from 'react';
import classNames from 'classnames';
import utils from 'utils';
import models from 'models';

var PluginsPage = React.createClass({
  statics: {
    title: i18n('plugins_page.title'),
    navbarActiveElement: 'plugins',
    breadcrumbsPath: [['home', '#'], 'plugins'],
    fetchData() {
      var plugins = new models.Plugins();
      return plugins.fetch()
        .then(() => {
          return $.when(...plugins.map((plugin) => {
            var links = new models.PluginLinks();
            links.url = _.result(plugin, 'url') + '/links';
            plugin.set({links: links});
            return links.fetch();
          }));
        })
        .then(() => ({plugins}));
    }
  },
  getDefaultProps() {
    return {
      details: [
        'version',
        'description',
        'homepage',
        'authors',
        'licenses',
        'releases',
        'links'
      ]
    };
  },
  processPluginData(plugin, attribute) {
    var data = plugin.get(attribute);
    if (attribute == 'releases') {
      return _.map(_.groupBy(data, 'os'), (osReleases, osName) =>
        <div key={osName}>
          {i18n('plugins_page.' + osName) + ': '}
          {_.pluck(osReleases, 'version').join(', ')}
        </div>
      );
    }
    if (attribute == 'homepage') {
      return <span dangerouslySetInnerHTML={{__html: utils.composeLink(data)}} />;
    }
    if (attribute == 'links') {
      return data.map((link) =>
        <div key={link.get('url')} className='plugin-link'>
          <a href={link.get('url')} target='_blank'>{link.get('title')}</a>
          {link.get('description')}
        </div>
      );
    }
    if (_.isArray(data)) return data.join(', ');
    return data;
  },
  renderPlugin(plugin, index) {
    return (
      <div key={index} className='plugin'>
        <div className='row'>
          <div className='col-xs-2' />
          <h3 className='col-xs-10'>
            {plugin.get('title')}
          </h3>
        </div>
        {_.map(this.props.details, (attribute) => {
          var data = this.processPluginData(plugin, attribute);
          if (data.length) return (
            <div className='row' key={attribute}>
              <div className='col-xs-2 detail-title text-right'>
                {i18n('plugins_page.' + attribute)}:
              </div>
              <div className='col-xs-10'>{data}</div>
            </div>
          );
        }, this)}
      </div>
    );
  },
  render() {
    var isMirantisIso = _.contains(app.version.get('feature_groups'), 'mirantis');
    var links = {
      catalog: isMirantisIso ?
        'https://www.mirantis.com/products/openstack-drivers-and-plugins/fuel-plugins/' :
        'http://stackalytics.com/report/driverlog?project_id=openstack%2Ffuel',
      documentation: utils.composeDocumentationLink('plugin-dev.html')
    };
    return (
      <div className='plugins-page'>
        <div className='page-title'>
          <h1 className='title'>{i18n('plugins_page.title')}</h1>
        </div>
        <div className='content-box'>
          <div className='row'>
            <div className='col-xs-12'>
              {this.props.plugins.map(this.renderPlugin)}
              <div className={classNames({
                'plugin-page-links': !!this.props.plugins.length,
                'text-center': true
              })}>
                {!this.props.plugins.length && i18n('plugins_page.no_plugins')}{' '}
                <span>
                  {i18n('plugins_page.more_info')}{' '}
                  <a href={links.catalog} target='_blank'>
                    {i18n('plugins_page.plugins_catalog')}
                  </a>{' '}
                  {i18n('common.and')}{' '}
                  <a href={links.documentation} target='_blank'>
                    {i18n('plugins_page.plugins_documentation')}
                  </a>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }
});

export default PluginsPage;
