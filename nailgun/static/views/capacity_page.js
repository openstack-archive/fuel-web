/*
 * Copyright 2014 Mirantis, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the 'License'); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an 'AS IS' BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
**/

import _ from 'underscore';
import i18n from 'i18n';
import React from 'react';
import models from 'models';
import {backboneMixin, pollingMixin} from 'component_mixins';
import {ProgressBar, Table} from 'views/controls';

var CapacityPage = React.createClass({
  mixins: [
    backboneMixin('capacityLog'),
    pollingMixin(2)
  ],
  statics: {
    title: i18n('capacity_page.title'),
    navbarActiveElement: 'support',
    breadcrumbsPath: [['home', '#'], ['support', '#support'], 'capacity'],
    fetchData() {
      var task = new models.Task();
      return task.save({}, {url: '/api/capacity/', method: 'PUT'})
        .then(() => ({capacityLog: new models.CapacityLog()}));
    }
  },
  shouldDataBeFetched() {
    return this.props.capacityLog.isNew();
  },
  fetchData() {
    return this.props.capacityLog.fetch();
  },
  render() {
    var capacityLog = this.props.capacityLog;
    return (
      <div className='capacity-page'>
        <div className='page-title'>
          <h1 className='title'>{i18n('capacity_page.title')}</h1>
        </div>
        <div className='content-box'>
          {!capacityLog.isNew() ?
            <LicenseUsage capacityLog={capacityLog} />
            :
            <ProgressBar />
          }
        </div>
      </div>
    );
  }
});

var LicenseUsage = React.createClass({
  render() {
    var capacityReport = this.props.capacityLog.get('report');
    var tableClassName = 'capacity-audit-table';
    var headClassName = 'name';
    return (
      <div>
        <h3>{i18n('capacity_page.license_usage')}</h3>
        <Table
          head={[{label: i18n('capacity_page.fuel_version'), className: headClassName},
              {label: i18n('capacity_page.fuel_uuid')}]}
          body={[[capacityReport.fuel_data.release, capacityReport.fuel_data.uuid]]}
          tableClassName={tableClassName}
        />
        <Table
          head={[{label: i18n('capacity_page.env_name'), className: headClassName},
            {label: i18n('capacity_page.node_count')}]}
          body={_.map(capacityReport.environment_stats, _.values)}
          tableClassName={tableClassName}
        />
        <Table
          head={[{label: i18n('capacity_page.total_number_alloc_nodes'), className: headClassName},
              {label: i18n('capacity_page.total_number_unalloc_nodes')}]}
          body={[[capacityReport.allocation_stats.allocated,
              capacityReport.allocation_stats.unallocated]]}
          tableClassName={tableClassName}
        />
        <Table
          head={[{label: i18n('capacity_page.node_role'), className: headClassName},
              {label: i18n('capacity_page.nodes_with_config')}]}
          body={_.zip(_.keys(capacityReport.roles_stat),
            _.values(capacityReport.roles_stat))}
          tableClassName={tableClassName}
        />
        <a href='/api/capacity/csv' target='_blank' className='btn btn-info'>
          <i className='glyphicon glyphicon-download-alt' />{' '}
          {i18n('capacity_page.download_report')}
        </a>
      </div>
    );
  }
});

export default CapacityPage;
