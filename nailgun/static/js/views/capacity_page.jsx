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
    'models',
    'jsx!component_mixins'
],
function(React, models, componentMixins) {
    'use strict';

//     scheduleUpdate: function() {
//            if (this.timeout) {
//                this.timeout.clear();
//            }
//            if (_.isUndefined(this.task.get('progress')) || this.task.get('progress') < 100 ) {
//                this.registerDeferred(this.timeout = $.timeout(this.updateInterval).done(_.bind(this.update, this)));
//            } else {
//                this.model = new models.CapacityLog();
//                this.model.deferred = this.model.fetch();
//                this.model.on('sync', this.render, this);
//            }
//        },
//        update: function() {
//            this.registerDeferred(this.task.fetch({url: '/api/tasks/'+ this.task.id}).always(_.bind(this.scheduleUpdate, this)));
//        },
//
//

    var CapacityPage = React.createClass({
         mixins: [
            React.BackboneMixin('task'),
            componentMixins.pollingMixin(2)
        ],
        navbarActiveElement: 'support',
        breadcrumbsPath: [['home', '#'], ['support', '#support'], 'capacity'],
        title: function() {
            return $.t('capacity_page.title');
        },
        shouldDataBeFetched: function() {
            return this.props.task && this.props.task.match({status: 'running'});
        },
        fetchData: function() {
            if (_.isUndefined(this.props.task.get('progress')) || this.props.task.get('progress') < 100 ) {
                return this.props.task.fetch({url: '/api/tasks/'+ this.props.task.id});
            } else {
                this.model = new models.CapacityLog();
                return this.model.fetch();
            }
        },
        componentDidMount: function() {
            this.startPolling();
        },
        render: function() {
            var task = this.props.task;
            return (
                <div>
                    <h3 className="page-title">{$.t('capacity_page.title')}</h3>
                    <div className="capacity page-wrapper">
                      {task && task.match({status: 'ready'}) ?
                         <LicenseUsage/>
                        :
                        <div className="row-fluid">
                          <div className="span12 loading-container">
                            <span className="icon-process animate-spin"></span>
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
            var tableClasses = "table table-bordered table-striped ";
            var classToUse = this.props.class || '';
            return (
                <table className={tableClasses + classToUse}>
                  <thead>
                    <tr>
                      <th className="name">{this.props.head[0]}</th>
                      <th>{this.props.head[1]}</th>
                    </tr>
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
        mixins: [React.BackboneMixin('capacityLog')],
        getInitialState: function() {
            return {
                capacityLog: new models.CapacityLog()
            };
        },
        componentDidMount: function() {
            this.state.capacityLog.fetch().done(_.bind(this.forceUpdate, this, undefined));
        },
        render: function() {
            var model = this.state.capacityLog;
            if (model.id) {
                var capacityReport = this.state.capacityLog.get('report')
            }
            return (
                <div>
                    {model.id &&
                      <div>
                        <h3>{$.t('capacity_page.license_usage')}</h3>
                        <TableWrapper
                            head = {[$.t('capacity_page.fuel_version'), $.t('capacity_page.fuel_uuid')]}
                            body = {[[capacityReport.fuel_data.release, capacityReport.fuel_data.uuid]]}
                            class = 'releases-table' />

                        <TableWrapper
                            head = {[$.t('capacity_page.env_name'), $.t('capacity_page.node_count')]}
                            body = {_.map(capacityReport.environment_stats, _.values)}
                            class = 'releases-table' />

                         <TableWrapper
                            head = {[$.t('capacity_page.total_number_alloc_nodes'),
                                  $.t('capacity_page.total_number_unalloc_nodes')]}
                            body = {[[capacityReport.allocation_stats.allocated,
                                  capacityReport.allocation_stats.unallocated]] }
                            class = 'releases-table' />

                        <TableWrapper
                            head = {[$.t('capacity_page.node_role'),
                                  $.t('capacity_page.nodes_with_config')]}
                            body = {_.zip(_.keys(capacityReport.roles_stat),
                                _.values(capacityReport.roles_stat))}
                            class = 'releases-table' />

                        <a href="/api/capacity/csv"  target="_blank" className="btn btn-info">
                          <i className="icon-install"></i>
                          <span>{$.t('capacity_page.download_report')}</span>
                        </a>
                      </div>
                    }
                </div>
            );
        }
    });

    return CapacityPage;
});
