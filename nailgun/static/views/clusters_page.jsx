/*
 * Copyright 2013 Mirantis, Inc.
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
    'jquery',
    'underscore',
    'i18n',
    'react',
    'models',
    'utils',
    'dispatcher',
    'jsx!component_mixins',
    'views/wizard'
],
function($, _, i18n, React, models, utils, dispatcher, componentMixins, wizard) {
    'use strict';
    var ClustersPage, ClusterList, Cluster;

    ClustersPage = React.createClass({
        statics: {
            title: i18n('clusters_page.title'),
            navbarActiveElement: 'clusters',
            breadcrumbsPath: [['home', '#'], 'environments'],
            fetchData: function() {
                var clusters = new models.Clusters();
                var nodes = new models.Nodes();
                var tasks = new models.Tasks();
                return $.when(clusters.fetch(), nodes.fetch(), tasks.fetch()).done(_.bind(function() {
                    clusters.each(function(cluster) {
                        cluster.set('nodes', new models.Nodes(nodes.where({cluster: cluster.id})));
                        cluster.set('tasks', new models.Tasks(tasks.where({cluster: cluster.id})));
                    }, this);
                }, this)).then(function() {
                    return {clusters: clusters};
                });
            }
        },
        render: function() {
            return (
                <div className='clusters-page'>
                    <div className='page-title'>
                        <h1 className='title'>{i18n('clusters_page.title')}</h1>
                    </div>
                    <ClusterList clusters={this.props.clusters} />
                </div>
            );
        }
    });

    ClusterList = React.createClass({
        mixins: [componentMixins.backboneMixin('clusters')],
        createCluster: function() {
            (new wizard.CreateClusterWizard({collection: this.props.clusters})).render();
        },
        render: function() {
            return (
                <div className='row'>
                    {this.props.clusters.map(function(cluster) {
                        return <Cluster key={cluster.id} cluster={cluster} />;
                    }, this)}
                    <div key='create-cluster' className='col-xs-3'>
                        <button className='btn-link create-cluster' onClick={this.createCluster}>
                            <span>{i18n('clusters_page.create_cluster_text')}</span>
                        </button>
                    </div>
                </div>
            );
        }
    });

    Cluster = React.createClass({
        mixins: [
            componentMixins.backboneMixin('cluster'),
            componentMixins.backboneMixin({modelOrCollection: function(props) {
                return props.cluster.get('nodes');
            }}),
            componentMixins.backboneMixin({modelOrCollection: function(props) {
                return props.cluster.get('tasks');
            }}),
            componentMixins.backboneMixin({modelOrCollection: function(props) {
                return props.cluster.task({group: 'deployment', status: 'running'});
            }}),
            componentMixins.pollingMixin(3)
        ],
        shouldDataBeFetched: function() {
            return this.props.cluster.task('cluster_deletion', ['running', 'ready']) || this.props.cluster.task({group: 'deployment', status: 'running'});
        },
        fetchData: function() {
            var request, requests = [];
            var deletionTask = this.props.cluster.task('cluster_deletion');
            if (deletionTask) {
                request = deletionTask.fetch();
                request.fail(_.bind(function(response) {
                    if (response.status == 404) {
                        this.props.cluster.collection.remove(this.props.cluster);
                        dispatcher.trigger('updateNodeStats');
                    }
                }, this));
                requests.push(request);
            }
            var deploymentTask = this.props.cluster.task({group: 'deployment', status: 'running'});
            if (deploymentTask) {
                request = deploymentTask.fetch();
                request.done(_.bind(function() {
                    if (deploymentTask.get('status') != 'running') {
                        this.props.cluster.fetch();
                        dispatcher.trigger('updateNodeStats');
                    }
                }, this));
                requests.push(request);
            }
            return $.when.apply($, requests);
        },
        render: function() {
            var cluster = this.props.cluster;
            var status = cluster.get('status');
            var nodes = cluster.get('nodes');
            var deletionTask = cluster.task('cluster_deletion', ['running', 'ready']);
            var deploymentTask = cluster.task({group: 'deployment', status: 'running'});
            return (
                <div className='col-xs-3'>
                    <a className={utils.classNames({clusterbox: true, 'cluster-disabled': !!deletionTask})} href={!deletionTask ? '#cluster/' + cluster.id : 'javascript:void 0'}>
                        <div className='name'>{cluster.get('name')}</div>
                        <div className='tech-info'>
                            <div key='nodes-title' className='item'>{i18n('clusters_page.cluster_hardware_nodes')}</div>
                            <div key='nodes-value' className='value'>{nodes.length}</div>
                            {!!nodes.length && [
                                <div key='cpu-title' className='item'>{i18n('clusters_page.cluster_hardware_cpu')}</div>,
                                <div key='cpu-value' className='value'>{nodes.resources('cores')} ({nodes.resources('ht_cores')})</div>,
                                <div key='hdd-title' className='item'>{i18n('clusters_page.cluster_hardware_hdd')}</div>,
                                <div key='hdd-value' className='value'>{nodes.resources('hdd') ? utils.showDiskSize(nodes.resources('hdd')) : '?GB'}</div>,
                                <div key='ram-title' className='item'>{i18n('clusters_page.cluster_hardware_ram')}</div>,
                                <div key='ram-value' className='value'>{nodes.resources('ram') ? utils.showMemorySize(nodes.resources('ram')) : '?GB'}</div>
                            ]}
                        </div>
                        <div className='status text-info'>
                            {deploymentTask ?
                                <div className='progress'>
                                    <div
                                        className={utils.classNames({
                                            'progress-bar': true,
                                            'progress-bar-warning': _.contains(['stop_deployment', 'reset_environment'], deploymentTask.get('name'))
                                        })}
                                        style={{width: (deploymentTask.get('progress') > 3 ? deploymentTask.get('progress') : 3) + '%'}}
                                    ></div>
                                </div>
                            :
                                <span className={utils.classNames({
                                    'text-danger': status == 'error' || status == 'update_error',
                                    'text-success': status == 'operational'
                                })}>
                                    {i18n('cluster.status.' + status, {defaultValue: status})}
                                </span>
                            }
                        </div>
                    </a>
                </div>
            );
        }
    });

    return ClustersPage;
});
