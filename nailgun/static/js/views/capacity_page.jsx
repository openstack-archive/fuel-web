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
    'views/common',
    'models',
    'jsx!component_mixins'
],
function(React, commonViews, models, componentMixins) {
    'use strict';

    var CapacityPage = React.createClass({
         mixins: [
            componentMixins.pollingMixin(20)
        ],
        navbarActiveElement: 'support',
        breadcrumbsPath: [['home', '#'], ['support', '#support'], 'capacity'],
        title: function() {
            return $.t('capacity_page.title');
        },
        getInitialState: function() {
            return {
                task: new models.Task()
            };
        },
        componentDidMount: function() {
            this.state.task.save({}, {url: '/api/capacity/', method: 'PUT'}).done(this.fetchTask, this, undefined);
        },
        fetchTask: function() {
            var task = this.state.task;
            task.fetch({url: '/api/tasks/'+ task.id}).always(_.bind(this.forceUpdate, this, undefined));
        },
        render: function() {
            var task = this.state.task;
            return (
                <div>
                    <h3 className="page-title">{$.t('capacity_page.title')}</h3>
                    <div className="capacity page-wrapper">
                      {(task.id) &&
                         <LicenseUsage/>
                      }
                      {!(task.id) &&
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
           var data = this.props.data;
            return (
                <table className="table table-bordered table-striped releases-table">
                  <thead>
                    <tr>
                      <th className="name">{data.head[0]}</th>
                      <th>{data.head[1]}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {_.map(data.body, function(row) {
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
            return (
                <div>
                    {(model.id) &&
                      <div>
                        <h3>{$.t('capacity_page.license_usage')}</h3>
                        <TableWrapper data = {{head: [$.t('capacity_page.fuel_version'), $.t('capacity_page.fuel_uuid')],
                            body: [[model.get('report').fuel_data.release, model.get('report').fuel_data.uuid]]}} />

                        <TableWrapper data = {{head: [$.t('capacity_page.env_name'), $.t('capacity_page.node_count')],
                            body: _.map(model.get('report').environment_stats, function(env) {
                              return _.values(env);
                            })}} />

                         <TableWrapper data = {{head: [$.t('capacity_page.total_number_alloc_nodes'),
                                $.t('capacity_page.total_number_unalloc_nodes')],
                            body: [[model.get('report').allocation_stats.allocated,
                                model.get('report').allocation_stats.unallocated]]}} />

                        <TableWrapper data = {{head: [$.t('capacity_page.node_role'),
                                $.t('capacity_page.nodes_with_config')],
                           body: _.zip(_.keys(model.get('report').roles_stat), _.values(model.get('report').roles_stat))}} />

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
