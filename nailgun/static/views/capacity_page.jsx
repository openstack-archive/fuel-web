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
    'underscore',
    'i18n',
    'react',
    'models',
    'jsx!component_mixins',
    'jsx!views/controls'
],
function(_, i18n, React, models, componentMixins, controls) {
    'use strict';

    var CapacityPage = React.createClass({
        mixins: [
            componentMixins.backboneMixin('capacityLog'),
            componentMixins.pollingMixin(2)
        ],
        statics: {
            title: i18n('capacity_page.title'),
            navbarActiveElement: 'support',
            breadcrumbsPath: [['home', '#'], ['support', '#support'], 'capacity'],
            fetchData: function() {
                var task = new models.Task();
                return task.save({}, {url: '/api/capacity/', method: 'PUT'}).then(function() {
                    return {capacityLog: new models.CapacityLog()};
                });
            }
        },
        shouldDataBeFetched: function() {
            return this.props.capacityLog.isNew();
        },
        fetchData: function() {
            return this.props.capacityLog.fetch();
        },
        render: function() {
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
                            <controls.ProgressBar />
                        }
                    </div>
                </div>
            );
        }
    });

    var LicenseUsage = React.createClass({
        render: function() {
            var capacityReport = this.props.capacityLog.get('report');
            return (
                <div>
                    <h3>{i18n('capacity_page.license_usage')}</h3>
                    <div className='row'>
                        <div className='col-xs-3'>{i18n('capacity_page.fuel_version')}</div>
                        <div className='col-xs-9'>{capacityReport.fuel_data.release}</div>
                    </div>
                    <div className='row'>
                        <div className='col-xs-3'>{i18n('capacity_page.fuel_uuid')}</div>
                        <div className='col-xs-9'>{capacityReport.fuel_data.uuid}</div>
                    </div>
                    <div className='row'>
                        <div className='col-xs-3'>{i18n('capacity_page.env_name')}</div>
                        <div className='col-xs-9'>
                            {_.map(capacityReport.environment_stats, function(value) {
                                    return <div>{value.cluster} ({i18n('capacity_page.node_count')}: {value.nodes})</div>;
                                }
                            )}
                        </div>
                    </div>
                    <div className='row'>
                        <div className='col-xs-3'>{i18n('capacity_page.total_number_alloc_nodes')}</div>
                        <div className='col-xs-9'>{capacityReport.allocation_stats.allocated}</div>
                    </div>
                    <div className='row'>
                        <div className='col-xs-3'>{i18n('capacity_page.total_number_unalloc_nodes')}</div>
                        <div className='col-xs-9'>{capacityReport.allocation_stats.unallocated}</div>
                    </div>
                    <div className='row'>
                        <div className='col-xs-3'>{i18n('capacity_page.node_role')}</div>
                        <div className='col-xs-9'>
                            {_.map(capacityReport.roles_stat, function(value, name) {
                                    return <div>{name} ({value})</div>;
                                }
                            )}
                        </div>
                    </div>
                    <a href='/api/capacity/csv' target='_blank' className='btn btn-info'>
                        <i className='glyphicon glyphicon-download-alt' />{' '}
                        {i18n('capacity_page.download_report')}
                    </a>
                </div>
            );
        }
    });

    return CapacityPage;
});
