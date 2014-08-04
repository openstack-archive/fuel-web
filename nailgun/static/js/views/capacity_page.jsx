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
    'component_mixins'
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
        componentWillMount: function() {
            this.state.task.save({}, {url: '/api/capacity/', method: 'PUT'})
            .done(_.bind(this.fetchTask, this, undefined));
        },
        fetchTask: function() {
            var task = this.state.task;
            task.fetch({url: '/api/tasks/'+ task.id}).always(_.bind(this.forceUpdate, this, undefined));
        },
        render: function() {
            var task = this.state.task;
            return (
                <div>
                    <div className="row-fluid">
                      <div className="span12">
                        <h3 className="page-title">{$.t('capacity_page.title')}</h3>
                      </div>
                    </div>
                    <div className="capacity page-wrapper">
                      {(task.toJSON().id) &&
                         <LicenseUsage/>
                      }
                      {!(task.toJSON().id) &&
                        <div className="row-fluid">
                          <div className="span12" style={{textAlign: 'center'}}>
                            <span className="icon-process animate-spin"></span><span>{$.t('capacity_page.loading')}</span>
                          </div>
                        </div>
                      }
                    </div>
                </div>
            );
        }
    });

    var LicenseUsage = React.createClass({
        mixins: [React.BackboneMixin('capacityLog')],
        getInitialState: function() {
            return {
                capacityModel: new models.CapacityLog()
            };
        },
        componentWillMount: function() {
            this.state.capacityModel.fetch().done(_.bind(this.forceUpdate, this, undefined));
        },
        render: function() {
            var model = this.state.capacityModel;
            return (
                <div>
                    {(model.toJSON().id) &&
                        <div>
                          <div className="row-fluid">
                            <div className="span12">
                               <h3>{$.t('capacity_page.license_usage')}</h3>
                            </div>
                          </div>
                          <div className="row-fluid">
                            <div className="span12">
                          <table className="table table-bordered table-striped releases-table">
                            <thead>
                              <tr>
                                <th className="name">{$.t('capacity_page.fuel_version')}</th>
                                <th>{$.t('capacity_page.fuel_uuid')}</th>
                              </tr>
                            </thead>
                            <tbody>
                              <tr>
                                <td>{model.get('report').fuel_data.release}</td>
                                <td>{model.get('report').fuel_data.uuid}</td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </div>
                      <div className="row-fluid">
                        <div className="span12">
                          <table className="table table-bordered table-striped releases-table">
                            <thead>
                              <tr>
                                <th className="name">{$.t('capacity_page.env_name')}</th>
                                <th>{$.t('capacity_page.node_count')}</th>
                              </tr>
                            </thead>
                            <tbody>
                            {_.map(model.get('report').environment_stats, function(env) {
                              return <tr>
                                    <td>{env.cluster}</td>
                                    <td>{env.nodes}</td>
                                  </tr>;
                            })}
                            </tbody>
                          </table>
                        </div>
                      </div>
                      <div className="row-fluid">
                        <div className="span12">
                          <table className="table table-bordered table-striped releases-table">
                            <thead>
                              <tr>
                                <th className="name">{$.t('capacity_page.total_number_alloc_nodes')}</th>
                                <th>{$.t('capacity_page.total_number_unalloc_nodes')}</th>
                              </tr>
                            </thead>
                            <tbody>
                              <tr>
                                <td>{model.get('report').allocation_stats.allocated}</td>
                                <td>{model.get('report').allocation_stats.unallocated}</td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </div>
                      <div className="row-fluid">
                        <div className="span12">
                          <table className="table table-bordered table-striped releases-table">
                            <thead>
                              <tr>
                                <th className="name">{$.t('capacity_page.node_role')}</th>
                                <th>{$.t('capacity_page.nodes_with_config')}</th>
                              </tr>
                            </thead>
                            <tbody>
                            {_.each(_.pairs(model.get('report').roles_stat), function(stats) {
                              <tr>
                                <td>{stats[0]}</td>
                                <td>{tats[1]}</td>
                              </tr>
                              })}
                            </tbody>
                          </table>
                        </div>
                      </div>
                      <div className="row-fluid">
                        <div className="span12">
                                <a href="/api/capacity/csv" className="btn btn-info">
                                  <i className="icon-install"></i>
                                  <span>{$.t('capacity_page.download_report')}</span>
                                </a>
                            </div>
                          </div>
                        </div>
                    }
                </div>
            );
        }
    });

    return CapacityPage;
});
