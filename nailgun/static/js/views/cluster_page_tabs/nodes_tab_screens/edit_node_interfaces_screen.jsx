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
    'underscore',
    'react',
    'utils',
    'models',
    'jsx!views/dialogs',
    'jsx!views/controls'
],
function(_, React, utils, models, dialogs, controls) {
    'use strict';

    var cx = React.addons.classSet;

    var EditNodeInterfacesScreen = React.createClass({
        mixins: [
            React.BackboneMixin('model', 'change:status'),
            React.BackboneMixin({modelOrCollection: function(props) {
                return props.model.get('networkConfiguration');
            }})
        ],
        getInitialState: function() {
            return {
                loading: true,
                actionInProgress: false
            };
        },
        componentDidMount: function() {
            var cluster = this.props.model;
            var nodeIds = utils.deserializeTabOptions(this.props.screenOptions[0]).nodes.split(',').map(function(id) {return parseInt(id, 10);});
            console.log('nodeIds', nodeIds);
            this.networkConfiguration = cluster.get('networkConfiguration');
            this.nodes = new models.Nodes(cluster.get('nodes').getByIds(nodeIds));

            this.loading = $.when.apply($, this.nodes.map(function(node) {
                node.interfaces = new models.Interfaces();
                //node.interfaces.url = _.result(node, 'url') + '/interfaces';
                return node.interfaces.fetch({
                    url: _.result(node, 'url') + '/interfaces/default_assignment',
                    reset: true
                });
            }, this).concat(this.networkConfiguration.fetch({cache: true})))
                .done(_.bind(function() {
                    if(this.nodes.length) {
                        this.interfaces = new models.Interfaces(this.nodes.at(0).interfaces.toJSON(), {parse: true});
                        this.setState({loading: false});
                    } else {
                        // TODO: just set nonexisting node id to get here
                        utils.showErrorDialog({
                            title: $.t('cluster_page.nodes_tab.configure_interfaces.configuration_error.title'),
                            message: $.t('cluster_page.nodes_tab.configure_interfaces.configuration_error.load_defaults_warning')
                        });
                    }
                }, this));
        },
        render: function() {
            var changesLocked = true;
            var bondingAvailable = true;
            var nodes = [];

            return (
                <div className="edit-node-networks-screen" style={{display: 'block'}}>
                    <div className={cx({'edit-node-interfaces': true, 'changes-locked': changesLocked})}>
                        <h3>
                            {$.t('cluster_page.nodes_tab.configure_interfaces.title', {count: nodes.length, name: nodes.length && nodes.at(0).get('name')})}
                        </h3>
                    </div>

                    <div className="row">
                        {bondingAvailable ?
                            <div className="page-control-box">
                                <div className="page-control-button-placeholder">
                                    <button className="btn btn-bond">{$.t("cluster_page.nodes_tab.configure_interfaces.bond_button")}</button>
                                    <button className="btn btn-unbond">{$.t("cluster_page.nodes_tab.configure_interfaces.unbond_button")}</button>
                                </div>
                            </div>
                            : null
                        }
                        {bondingAvailable ?
                            <div className="bond-speed-warning alert hide">{$.t("cluster_page.nodes_tab.configure_interfaces.bond_speed_warning")}</div>
                            : null
                        }

                        {this.state.loading ? <controls.ProgressBar /> : null }

                        <div className="page-control-box">
                            <div className="back-button pull-left">
                                <button className="btn btn-return">{$.t("cluster_page.nodes_tab.back_to_nodes_button")}</button>
                            </div>
                            <div className="page-control-button-placeholder">
                                <button className="btn btn-defaults">{$.t("common.load_defaults_button")}</button>
                                <button className="btn btn-revert-changes">{$.t("common.cancel_changes_button")}</button>
                                <button className="btn btn-success btn-apply">{$.t("common.apply_button")}</button>
                            </div>
                        </div>
                    </div>
                </div>
            );
        }
    });

    return EditNodeInterfacesScreen;
});
