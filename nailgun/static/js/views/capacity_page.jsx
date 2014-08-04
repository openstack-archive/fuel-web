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
define(
[
    'react',
    'models',
    'jsx!component_mixins'
],
function(React, models, componentMixins) {
    'use strict';

    var CapacityPage = React.createClass({
         mixins: [
            React.BackboneMixin('capacityLog'),
            componentMixins.pollingMixin(2)
        ],
        navbarActiveElement: 'support',
        breadcrumbsPath: [['home', '#'], ['support', '#support'], 'capacity'],
        title: function() {
            return $.t('capacity_page.title');
        },
        shouldDataBeFetched: function() {
            var condition = false;
            if (this.props.capacityLog.isNew()) {
                condition = true;
            }
            return condition;
        },
        fetchData: function() {
            return this.props.capacityLog.fetch();
        },
        componentDidMount: function() {
            this.startPolling();
        },
        render: function() {
            var capacityLog = this.props.capacityLog;
            return (
                <div>
                    <h3 className='page-title'>{$.t('capacity_page.title')}</h3>
                    <div className='capacity page-wrapper'>
                      {!capacityLog.isNew() ?
                         <LicenseUsage capacityLog = {capacityLog} />
                        :
                        <div className='row-fluid'>
                          <div className='span12 loading-container'>
                            <span className='icon-process animate-spin'></span>
                            <span>{$.t('capacity_page.loading')}</span>
                          </div>
                        </div>
                      }
                    </div>
                </div>
            );
        }
    });


    var TableWrapper = React.createClass({
        render: function() {
            var tableClass = 'table table-bordered table-striped ' + this.props.className;
            return (
                <table className={tableClass}>
                  <thead>
                      {_.map(this.props.head, function(row) {
                        return <tr> {
                            _.map(row, function(column) {
                                return <th className={column.className || ''}>{column.label}</th>;
                            })
                       }
                       </tr>;
                    })}
                  </thead>
                  <tbody>
                    {_.map(this.props.body, function(row) {
                        return <tr> {
                            _.map(row, function(column) {
                                return <td>{column}</td>;
                            })
                       }
                       </tr>;
                    })}
                  </tbody>
                </table>
            );
        }
    });

    var LicenseUsage = React.createClass({
        render: function() {
            var capacityReport = this.props.capacityLog.get('report'),
                tableClassName =  'releases-table',
                headClassName = 'name';
            return (
                <div>
                    <h3>{$.t('capacity_page.license_usage')}</h3>
                    <TableWrapper
                        head = {[[{label: $.t('capacity_page.fuel_version'), className: headClassName},
                                {label: $.t('capacity_page.fuel_uuid')}]]}
                        body = {[[capacityReport.fuel_data.release, capacityReport.fuel_data.uuid]]}
                        className= {tableClassName} />

                    <TableWrapper
                        head = {[[{label: $.t('capacity_page.env_name'),  className: headClassName},
                            {label: $.t('capacity_page.node_count')}]]}
                        body = {_.map(capacityReport.environment_stats, _.values)}
                        className= {tableClassName} />

                     <TableWrapper
                        head = {[[{label: $.t('capacity_page.total_number_alloc_nodes'), className: headClassName},
                                {label: $.t('capacity_page.total_number_unalloc_nodes')}]]}
                        body = {[[capacityReport.allocation_stats.allocated,
                              capacityReport.allocation_stats.unallocated]] }
                        className = {tableClassName} />

                    <TableWrapper
                        head = {[[{label: $.t('capacity_page.node_role'),  className: headClassName},
                                {label: $.t('capacity_page.nodes_with_config')}]]}
                        body = {_.zip(_.keys(capacityReport.roles_stat),
                            _.values(capacityReport.roles_stat))}
                        className = {tableClassName} />

                    <a href='/api/capacity/csv'  target='_blank' className='btn btn-info'>
                      <i className='icon-install'></i>
                      <span>{$.t('capacity_page.download_report')}</span>
                    </a>
                </div>
            );
        }
    });

    return CapacityPage;
});
