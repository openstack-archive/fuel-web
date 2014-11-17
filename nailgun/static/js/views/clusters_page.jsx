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
    'react',
    'utils',
    'jsx!component_mixins',
    'views/wizard'
],
function(React, utils, componentMixins, wizard) {
    'use strict';
    var ClustersPage, ClusterList, Cluster;

    ClustersPage = React.createClass({
        navbarActiveElement: 'clusters',
        breadcrumbsPath: [['home', '#'], 'environments'],
        title: function() {
            return $.t('clusters_page.title');
        },
        componentDidMount: function() {
            $(app.footer.getDOMNode()).toggle(app.user.get('authenticated'));
            $(app.breadcrumbs.getDOMNode()).toggle(app.user.get('authenticated'));
            $(app.navbar.getDOMNode()).toggle(app.user.get('authenticated'));
        },
        render: function() {
            return (
                <div>
                    <h3 className="page-title">{$.t('clusters_page.title')}</h3>
                    <ClusterList clusters={this.props.clusters} />
                </div>
            );
        }
    });

    ClusterList = React.createClass({
        mixins: [React.BackboneMixin('clusters')],
        createCluster: function() {
            (new wizard.CreateClusterWizard({collection: this.props.clusters})).render();
        },
        render: function() {
            return (
                <div className="cluster-list">
                    <div className="roles-block-row">
                        {this.props.clusters.map(function(cluster) {
                            return <Cluster key={cluster.id} cluster={cluster} />;
                        }, this)}
                        <div key="add" className="span3 clusterbox create-cluster" onClick={this.createCluster}>
                            <div className="add-icon"><i className="icon-create"></i></div>
                            <div className="create-cluster-text">{$.t('clusters_page.create_cluster_text')}</div>
                        </div>
                    </div>
                </div>
            );
        }
    });

    Cluster = React.createClass({
        mixins: [
            React.BackboneMixin('cluster'),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.cluster.get('nodes');
            }}),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.cluster.get('tasks');
            }}),
            React.BackboneMixin({modelOrCollection: function(props) {
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
                        app.navbar.refresh();
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
                        app.navbar.refresh();
                    }
                }, this));
                requests.push(request);
            }
            return $.when.apply($, requests);
        },
        render: function() {
            var cluster = this.props.cluster;
            var nodes = cluster.get('nodes');
            var deletionTask = cluster.task('cluster_deletion', ['running', 'ready']);
            var deploymentTask = cluster.task({group: 'deployment', status: 'running'});
            return (
                <a className={'span3 clusterbox ' + (deletionTask ? 'disabled-cluster' : '')} href={!deletionTask ? '#cluster/' + cluster.id + '/nodes' : 'javascript:void 0'}>
                    <div className="cluster-name">{cluster.get('name')}</div>
                    <div className="cluster-hardware">
                        {(!nodes.deferred || nodes.deferred.state() == 'resolved') &&
                            <div className="row-fluid">
                                <div key="nodes-title" className="span6">{$.t('clusters_page.cluster_hardware_nodes')}</div>
                                <div key="nodes-value" className="span4">{nodes.length}</div>
                                {!!nodes.length && [
                                    <div key="cpu-title" className="span6">{$.t('clusters_page.cluster_hardware_cpu')}</div>,
                                    <div key="cpu-value" className="span4">{nodes.resources('cores')} ({nodes.resources('ht_cores')})</div>,
                                    <div key="hdd-title" className="span6">{$.t('clusters_page.cluster_hardware_hdd')}</div>,
                                    <div key="hdd-value" className="span4">{nodes.resources('hdd') ? utils.showDiskSize(nodes.resources('hdd')) : '?GB'}</div>,
                                    <div key="ram-title" className="span6">{$.t('clusters_page.cluster_hardware_ram')}</div>,
                                    <div key="ram-value" className="span4">{nodes.resources('ram') ? utils.showMemorySize(nodes.resources('ram')) : '?GB'}</div>
                                ]}
                            </div>
                        }
                    </div>
                    <div className="cluster-status">
                        {deploymentTask ?
                            <div className={'cluster-status-progress ' + deploymentTask.get('name')}>
                                <div className={'progress progress-' + (_.contains(['stop_deployment', 'reset_environment'], deploymentTask.get('name')) ? 'warning' : 'success') + ' progress-striped active'}>
                                    <div className="bar" style={{width: (deploymentTask.get('progress') > 3 ? deploymentTask.get('progress') : 3) + '%'}}></div>
                                </div>
                            </div>
                        :
                            $.t('cluster.status.' + cluster.get('status'), {defaultValue: cluster.get('status')})
                        }
                    </div>
                </a>
            );
        }
    });

    return ClustersPage;
});
