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
import ReactDOM from 'react-dom';
import utils from 'utils';
import models from 'models';
import dispatcher from 'dispatcher';
import {Input, ProgressBar, Tooltip} from 'views/controls';
import {
  DiscardNodeChangesDialog, DeployClusterDialog, ProvisionVMsDialog, ProvisionNodesDialog,
  DeployNodesDialog, RemoveClusterDialog, ResetEnvironmentDialog, StopDeploymentDialog,
  SelectNodesDialog
} from 'views/dialogs';
import {backboneMixin, pollingMixin, renamingMixin} from 'component_mixins';

var ns = 'cluster_page.dashboard_tab.';

var DashboardTab = React.createClass({
  mixins: [
    // this is needed to somehow handle the case when verification
    // is in progress and user pressed Deploy
    backboneMixin({
      modelOrCollection: (props) => props.cluster.get('tasks'),
      renderOn: 'update change'
    }),
    backboneMixin({
      modelOrCollection: (props) => props.cluster.get('nodes'),
      renderOn: 'update change'
    }),
    backboneMixin({
      modelOrCollection: (props) => props.cluster.get('pluginLinks'),
      renderOn: 'update change'
    }),
    backboneMixin({
      modelOrCollection: (props) => props.cluster.get('networkConfiguration')
    }),
    backboneMixin('cluster', 'change'),
    pollingMixin(20, true)
  ],
  statics: {
    breadcrumbsPath() {
      return [
        [i18n('cluster_page.tabs.dashboard'), null, {active: true}]
      ];
    }
  },
  fetchData() {
    return this.props.cluster.get('nodes').fetch();
  },
  render() {
    var cluster = this.props.cluster;
    var release = cluster.get('release');
    var runningDeploymentTask = cluster.task({group: 'deployment', active: true});
    var finishedDeploymentTask = cluster.task({group: 'deployment', active: false});
    var dashboardLinks = [{
      url: '/',
      title: i18n(ns + 'horizon'),
      description: i18n(ns + 'horizon_description')
    }].concat(
      cluster.get('pluginLinks').invoke('pick', 'url', 'title', 'description')
    );

    return (
      <div className='wrapper'>
        {release.get('state') === 'unavailable' &&
          <div className='alert alert-warning'>
            {i18n('cluster_page.unavailable_release', {name: release.get('name')})}
          </div>
        }
        {cluster.get('is_customized') &&
          <div className='alert alert-warning'>
            {i18n('cluster_page.cluster_was_modified_from_cli')}
          </div>
        }
        {runningDeploymentTask ?
          <DeploymentInProgressControl
            cluster={cluster}
            task={runningDeploymentTask}
          />
        :
          [
            finishedDeploymentTask &&
              <DeploymentResult
                key='task-result'
                cluster={cluster}
                task={finishedDeploymentTask}
              />,
            cluster.get('status') === 'operational' &&
              <DashboardLinks
                key='plugin-links'
                cluster={cluster}
                links={dashboardLinks}
              />,
            <ClusterActionsPanel
              key='actions-panel'
              cluster={cluster}
            />
          ]
        }
        <ClusterInfo cluster={cluster} />
        <DocumentationLinks />
      </div>
    );
  }
});

var DashboardLinks = React.createClass({
  renderLink(link) {
    var {links, cluster} = this.props;
    return (
      <DashboardLink
        {...link}
        className={links.length > 1 ? 'col-xs-6' : 'col-xs-12'}
        cluster={cluster}
      />
    );
  },
  render() {
    var {links} = this.props;
    if (!links.length) return null;
    return (
      <div className='row'>
        <div className='dashboard-block links-block clearfix'>
          <div className='col-xs-12'>
            {links.map((link, index) => {
              if (index % 2 === 0) {
                return (
                  <div className='row' key={link.url}>
                    {this.renderLink(link)}
                    {index + 1 < links.length && this.renderLink(links[index + 1])}
                  </div>
                );
              }
            }, this)}
          </div>
        </div>
      </div>
    );
  }
});

var DashboardLink = React.createClass({
  propTypes: {
    title: React.PropTypes.string.isRequired,
    url: React.PropTypes.string.isRequired,
    description: React.PropTypes.node
  },
  processRelativeURL(url) {
    var sslSettings = this.props.cluster.get('settings').get('public_ssl');
    if (sslSettings.horizon.value) return 'https://' + sslSettings.hostname.value + url;
    return this.getHTTPLink(url);
  },
  getHTTPLink(url) {
    return 'http://' + this.props.cluster.get('networkConfiguration').get('public_vip') + url;
  },
  render() {
    var {url, title, description, className, cluster} = this.props;
    var isSSLEnabled = cluster.get('settings').get('public_ssl.horizon.value');
    var isURLRelative = !(/^(?:https?:)?\/\//.test(url));
    var link = isURLRelative ? this.processRelativeURL(url) : url;
    return (
      <div className={'link-block ' + className}>
        <div className='title'>
          <a href={link} target='_blank'>{title}</a>
          {isURLRelative && isSSLEnabled &&
            <a href={this.getHTTPLink(link)} className='http-link' target='_blank'>
              {i18n(ns + 'http_plugin_link')}
            </a>
          }
        </div>
        <div className='description'>{description}</div>
      </div>
    );
  }
});

var DeploymentInProgressControl = React.createClass({
  render() {
    var task = this.props.task;
    var showStopButton = task.match({name: 'deploy'});
    return (
      <div className='row'>
        <div className='dashboard-block clearfix'>
          <div className='col-xs-12'>
            <div className={utils.classNames({
              'deploy-process': true,
              [task.get('name')]: true,
              'has-stop-control': showStopButton
            })}>
              <h4>
                <strong>
                  {i18n(ns + 'current_task') + ' '}
                </strong>
                {i18n('cluster_page.' + task.get('name')) + '...'}
              </h4>
              <ProgressBar progress={task.isInfinite() ? null : task.get('progress')} />
              {showStopButton &&
                <Tooltip text={i18n('cluster_page.stop_deployment_button')}>
                  <button
                    className='btn btn-danger btn-xs pull-right stop-deployment-btn'
                    onClick={() => StopDeploymentDialog.show({cluster: this.props.cluster})}
                    disabled={!task.isStoppable()}
                  >
                    {i18n(ns + 'stop')}
                  </button>
                </Tooltip>
              }
            </div>
          </div>
        </div>
      </div>
    );
  }
});

var DeploymentResult = React.createClass({
  getInitialState() {
    return {collapsed: false};
  },
  dismissTaskResult() {
    var {task, cluster} = this.props;
    if (task.match({name: 'deploy'})) {
      // deletion of 'deploy' task invokes all deployment tasks deletion in backend
      task.destroy({silent: true})
        .done(() => cluster.get('tasks').fetch());
    } else {
      task.destroy();
    }
  },
  componentDidMount() {
    $('.result-details', ReactDOM.findDOMNode(this))
      .on('show.bs.collapse', this.setState.bind(this, {collapsed: true}, null))
      .on('hide.bs.collapse', this.setState.bind(this, {collapsed: false}, null));
  },
  render() {
    var {task} = this.props;
    var error = task.match({status: 'error'});
    var delimited = task.escape('message').split('\n\n');
    var summary = delimited.shift();
    var details = delimited.join('\n\n');
    var warning = task.match({name: ['reset_environment', 'stop_deployment']});
    var classes = {
      alert: true,
      'alert-warning': warning,
      'alert-danger': !warning && error,
      'alert-success': !warning && !error
    };
    return (
      <div className={utils.classNames(classes)}>
        <button className='close' onClick={this.dismissTaskResult}>&times;</button>
        <strong>{i18n('common.' + (error ? 'error' : 'success'))}</strong>
        <br />
        <span dangerouslySetInnerHTML={{__html: utils.urlify(summary)}} />
        <div className={utils.classNames({'task-result-details': true, hidden: !details})}>
          <pre
            className='collapse result-details'
            dangerouslySetInnerHTML={{__html: utils.urlify(details)}}
          />
          <button className='btn-link' data-toggle='collapse' data-target='.result-details'>
            {this.state.collapsed ? i18n('cluster_page.hide_details_button') :
              i18n('cluster_page.show_details_button')}
          </button>
        </div>
      </div>
    );
  }
});

var DocumentationLinks = React.createClass({
  renderDocumentationLinks(link, labelKey) {
    return (
      <div className='documentation-link' key={labelKey}>
        <span>
          <i className='glyphicon glyphicon-list-alt' />
          <a href={link} target='_blank'>
            {i18n(ns + labelKey)}
          </a>
        </span>
      </div>
    );
  },
  render() {
    return (
      <div className='row content-elements'>
        <div className='title'>{i18n(ns + 'documentation')}</div>
        <div className='col-xs-12'>
          <p>{i18n(ns + 'documentation_description')}</p>
        </div>
        <div className='documentation col-xs-12'>
          {this.renderDocumentationLinks('http://docs.openstack.org/', 'openstack_documentation')}
          {this.renderDocumentationLinks(
            'https://wiki.openstack.org/wiki/Fuel/Plugins',
            'plugin_documentation'
          )}
        </div>
      </div>
    );
  }
});

var ClusterActionsPanel = React.createClass({
  getDefaultProps() {
    return {
      actions: ['spawn_vms', 'deploy', 'provision', 'deployment']
    };
  },
  getInitialState() {
    return {
      currentAction: this.isActionAvailable('spawn_vms') ? 'spawn_vms' : 'deploy'
    };
  },
  getConfigModels() {
    var {cluster} = this.props;
    return {
      cluster,
      settings: cluster.get('settings'),
      version: app.version,
      release: cluster.get('release'),
      default: cluster.get('settings'),
      networking_parameters: cluster.get('networkConfiguration').get('networking_parameters')
    };
  },
  validate(action) {
    return _.reduce(
      this.validations(action),
      (accumulator, validator) => _.merge(
        accumulator,
        validator.call(this, this.props.cluster),
        (a, b) => a.concat(_.compact(b))
      ),
      {blocker: [], error: [], warning: []}
    );
  },
  validations(action) {
    var checkForUnpovisionedVirtNodes = function(cluster) {
      var unprovisionedVirtNodes = cluster.get('nodes').filter(
        (node) => node.hasRole('virt') && node.get('status') === 'discover'
      );
      if (unprovisionedVirtNodes.length) {
        return {blocker: [
          i18n(ns + 'unprovisioned_virt_nodes', {
            role: cluster.get('roles').find({name: 'virt'}).get('label'),
            count: unprovisionedVirtNodes.length
          })
        ]};
      }
    };
    switch (action) {
      case 'deploy':
        return [
          checkForUnpovisionedVirtNodes,
          // check if some cluster nodes are offline
          function(cluster) {
            if (cluster.get('nodes').any({online: false})) {
              return {blocker: [i18n(ns + 'offline_nodes')]};
            }
          },
          // check if TLS settings are not configured
          function(cluster) {
            var sslSettings = cluster.get('settings').get('public_ssl');
            if (!sslSettings.horizon.value && !sslSettings.services.value) {
              return {warning: [i18n(ns + 'tls_not_enabled')]};
            }
            if (!sslSettings.horizon.value) {
              return {warning: [i18n(ns + 'tls_for_horizon_not_enabled')]};
            }
            if (!sslSettings.services.value) {
              return {warning: [i18n(ns + 'tls_for_services_not_enabled')]};
            }
          },
          // check if deployment failed
          function(cluster) {
            return cluster.needsRedeployment() && {
              error: [
                <InstructionElement
                  key='unsuccessful_deploy'
                  description='unsuccessful_deploy'
                  link={{
                    url: 'operations.html#troubleshooting',
                    title: 'user_guide'
                  }}
                />
              ]
            };
          },
          // check VCenter settings
          function(cluster) {
            if (cluster.get('settings').get('common.use_vcenter.value')) {
              var vcenter = cluster.get('vcenter');
              vcenter.setModels(this.getConfigModels());
              return !vcenter.isValid() && {
                blocker: [
                  <span key='vcenter'>{i18n('vmware.has_errors') + ' '}
                    <a href={'/#cluster/' + cluster.id + '/vmware'}>
                      {i18n('vmware.tab_name')}
                    </a>
                  </span>
                ]
              };
            }
          },
          // check cluster settings
          function(cluster) {
            var configModels = this.getConfigModels();
            var areSettingsInvalid = !cluster.get('settings').isValid({models: configModels});
            return areSettingsInvalid &&
              {blocker: [
                <span key='invalid_settings'>
                  {i18n(ns + 'invalid_settings')}
                  {' ' + i18n(ns + 'get_more_info') + ' '}
                  <a href={'#cluster/' + cluster.id + '/settings'}>
                    {i18n(ns + 'settings_link')}
                  </a>.
                </span>
              ]};
          },
          // check node amount restrictions according to their roles
          function(cluster) {
            var configModels = this.getConfigModels();
            var roleModels = cluster.get('roles');
            var validRoleModels = roleModels.filter(
              (role) => !role.checkRestrictions(configModels).result
            );
            var limitValidations = _.zipObject(validRoleModels.map(
              (role) => [role.get('name'), role.checkLimits(configModels, cluster.get('nodes'))]
            ));
            var limitRecommendations = _.zipObject(validRoleModels.map(
              (role) => [
                role.get('name'),
                role.checkLimits(configModels, cluster.get('nodes'), true, ['recommended'])
              ]
            ));
            return {
              blocker: roleModels.map((role) => {
                var limits = limitValidations[role.get('name')];
                return limits && !limits.valid && limits.message;
              }),
              warning: roleModels.map((role) => {
                var recommendation = limitRecommendations[role.get('name')];
                return recommendation && !recommendation.valid && recommendation.message;
              })
            };
          },
          // check cluster network configuration
          function(cluster) {
            // network verification is not supported in multi-rack environment
            if (cluster.get('nodeNetworkGroups').length > 1) return null;

            var task = cluster.task('verify_networks');
            var makeComponent = (text, isError) => {
              var span = (
                <span key='invalid_networks'>
                  {text}
                  {' ' + i18n(ns + 'get_more_info') + ' '}
                  <a href={'#cluster/' + cluster.id + '/network/network_verification'}>
                    {i18n(ns + 'networks_link')}
                  </a>.
                </span>
              );
              return isError ? {error: [span]} : {warning: [span]};
            };

            if (_.isUndefined(task)) {
              return makeComponent(i18n(ns + 'verification_not_performed'));
            }
            if (task.match({status: 'error'})) {
              return makeComponent(i18n(ns + 'verification_failed'), true);
            }
            if (task.match({active: true})) {
              return makeComponent(i18n(ns + 'verification_in_progress'));
            }
          }
        ];
      case 'provision':
        return [
          checkForUnpovisionedVirtNodes,
          // check if some discovered nodes are offline
          function(cluster) {
            if (cluster.get('nodes').any(
              (node) => node.isProvisioningPossible() && !node.get('online')
            )) {
              return {blocker: [i18n(ns + 'offline_nodes')]};
            }
          }
        ];
      case 'deployment':
        return [
          checkForUnpovisionedVirtNodes,
          // check if some provisioned nodes are offline
          function(cluster) {
            if (cluster.get('nodes').any(
              (node) => node.isDeploymentPossible() && !node.get('online')
            )) {
              return {blocker: [i18n(ns + 'offline_nodes')]};
            }
          }
        ];
      case 'spawn_vms':
        return [
          // check if some virt nodes are offline
          function(cluster) {
            if (cluster.get('nodes').any(
              (node) => node.isProvisioningPossible() &&
                node.hasRole('virt') &&
                !node.get('online')
            )) {
              return {blocker: [i18n(ns + 'offline_nodes')]};
            }
          }
        ];
    }
  },
  showDialog(Dialog, options) {
    Dialog.show(_.extend({cluster: this.props.cluster}, options));
  },
  renderNodesAmount(nodes, dictKey) {
    if (!nodes.length) return null;
    return (
      <li className='changes-item'>
        {i18n(ns + dictKey, {count: nodes.length})}
        {_.all(nodes, (node) => node.get('pending_addition') || node.get('pending_deletion')) &&
          <button
            className='btn btn-link btn-discard-changes'
            onClick={() => this.showDialog(DiscardNodeChangesDialog, {nodes: nodes})}
          >
            <i className='discard-changes-icon' />
          </button>
        }
      </li>
    );
  },
  isActionAvailable(action) {
    var {cluster} = this.props;
    switch (action) {
      case 'deploy':
        return !this.validate(action).blocker.length && cluster.isDeploymentPossible();
      case 'provision':
        return !this.validate(action).blocker.length && cluster.get('nodes').any(
          (node) => node.isProvisioningPossible()
        );
      case 'deployment':
        return !this.validate(action).blocker.length && cluster.get('nodes').any(
          (node) => node.isDeploymentPossible()
        );
      case 'spawn_vms':
        return cluster.get('nodes').any(
          (node) => node.hasRole('virt') && node.get('status') === 'discover'
        );
      default:
        return true;
    }
  },
  toggleAction(action) {
    this.setState({currentAction: action});
  },
  showSelectNodesDialog(nodeList, callback) {
    var cluster = this.props.cluster;
    var nodes = new models.Nodes(nodeList);
    nodes.fetch = function(options) {
      return this.constructor.__super__.fetch.call(this,
        _.extend({data: {cluster_id: cluster.id}}, options));
    };
    nodes.parse = function() {
      return this.getByIds(nodes.pluck('id'));
    };
    this.showDialog(
      SelectNodesDialog,
      {
        nodes,
        callback,
        roles: cluster.get('roles'),
        nodeNetworkGroups: cluster.get('nodeNetworkGroups')
      }
    );
  },
  renderActions() {
    var action = this.state.currentAction;
    var actionNs = ns + 'actions.' + action + '.';
    var isActionAvailable = this.isActionAvailable(action);

    var nodes = this.props.cluster.get('nodes');
    var nodesToProvision = nodes.filter((node) => node.isProvisioningPossible());
    var nodesToDeploy = nodes.filter((node) => node.isDeploymentPossible());

    var alerts = this.validate(action);
    var blockerDescriptions = {
      provision: <InstructionElement
        description='provisioning_cannot_be_started'
        isAlert
      />,
      deployment: <InstructionElement
        description='deployment_of_nodes_cannot_be_started'
        isAlert
      />,
      spawn_vms: <InstructionElement
        description='provisioning_cannot_be_started'
        isAlert
      />,
      deploy: <InstructionElement
        description='deployment_of_environment_cannot_be_started'
        isAlert
        link={{
          url: 'user-guide.html#add-nodes-ug',
          title: 'user_guide'
        }}
        explanation='for_more_information_roles'
      />
    };

    var getButtonProps = function(className) {
      return {
        className: utils.classNames({
          'btn btn-primary': true,
          'btn-warning': _.isEmpty(alerts.blocker) &&
            (!_.isEmpty(alerts.error) || !_.isEmpty(alerts.warning)),
          [className]: true
        }),
        disabled: !isActionAvailable
      };
    };

    var actionControls = {
      deploy: (
        <div className='col-xs-3 changes-list'>
          {nodes.hasChanges() &&
            <ul>
              {this.renderNodesAmount(nodes.where({pending_addition: true}), 'added_node')}
              {this.renderNodesAmount(
                nodes.where({status: 'provisioned', pending_deletion: false}),
                'provisioned_node'
              )}
              {this.renderNodesAmount(nodes.where({pending_deletion: true}), 'deleted_node')}
            </ul>
          }
          <button
            {... getButtonProps('deploy-btn')}
            onClick={() => this.showDialog(DeployClusterDialog)}
          >
            <div className='deploy-icon' />
            {i18n(actionNs + 'button_title')}
          </button>
        </div>
      ),
      provision: [
        nodesToProvision.length ?
          <div className='action-description' key='action-description'>
            {i18n(actionNs + 'description')}
          </div>
        :
          <div className='no-nodes' key='no-nodes'>
            {i18n(actionNs + 'no_nodes_to_provision')}
          </div>,
        <div className='col-xs-3 changes-list' key='changes-list'>
          {nodesToProvision.length > 1 ?
            <div className='btn-group'>
              <button
                {... getButtonProps('btn-provision')}
                onClick={() => this.showDialog(ProvisionNodesDialog, {
                  nodeIds: _.map(nodesToProvision, (node) => node.id)
                })}
              >
                {i18n(actionNs + 'button_title', {count: nodesToProvision.length})}
              </button>
              <button
                {... getButtonProps('dropdown-toggle')}
                data-toggle='dropdown'
              >
                <span className='caret' />
              </button>
              <ul className='dropdown-menu'>
                <li>
                  <button
                    className='btn btn-link btn-select-nodes'
                    onClick={() => this.showSelectNodesDialog(
                      nodesToProvision,
                      (nodeIds) => this.showDialog(ProvisionNodesDialog, {nodeIds})
                    )}
                  >
                    {i18n(actionNs + 'choose_nodes')}
                  </button>
                </li>
              </ul>
            </div>
          :
            <button
              {... getButtonProps('btn-provision')}
              onClick={() => this.showDialog(ProvisionNodesDialog, {
                nodeIds: _.map(nodesToProvision, (node) => node.id)
              })}
            >
              {nodesToProvision.length ?
                i18n(actionNs + 'button_title', {count: nodesToProvision.length})
              :
                i18n(actionNs + 'button_title_no_nodes')
              }
            </button>
          }
        </div>
      ],
      deployment: [
        nodesToDeploy.length ?
          <div className='action-description' key='action-description'>
            {i18n(actionNs + 'description')}
          </div>
        :
          <div className='no-nodes' key='no-nodes'>
            {i18n(actionNs + 'no_nodes_to_deploy')}
          </div>,
        <div className='col-xs-3 changes-list' key='changes-list'>
          {nodesToDeploy.length > 1 ?
            <div className='btn-group'>
              <button
                {... getButtonProps('btn-deploy-nodes')}
                onClick={() => this.showDialog(DeployNodesDialog, {
                  nodeIds: _.map(nodesToDeploy, (node) => node.id)
                })}
              >
                {i18n(actionNs + 'button_title', {count: nodesToDeploy.length})}
              </button>
              <button
                {... getButtonProps('dropdown-toggle')}
                data-toggle='dropdown'
              >
                <span className='caret' />
              </button>
              <ul className='dropdown-menu'>
                <li>
                  <button
                    className='btn btn-link btn-select-nodes'
                    onClick={() => this.showSelectNodesDialog(
                      nodesToDeploy,
                      (nodeIds) => this.showDialog(DeployNodesDialog, {nodeIds})
                    )}
                  >
                    {i18n(actionNs + 'choose_nodes')}
                  </button>
                </li>
              </ul>
            </div>
          :
            <button
              {... getButtonProps('btn-deploy-nodes')}
              onClick={() => this.showDialog(DeployNodesDialog, {
                nodeIds: _.map(nodesToDeploy, (node) => node.id)
              })}
            >
              {nodesToDeploy.length ?
                i18n(actionNs + 'button_title', {count: nodesToDeploy.length})
              :
                i18n(actionNs + 'button_title_no_nodes')
              }
            </button>
          }
        </div>
      ],
      spawn_vms: (
        <div className='col-xs-3 changes-list'>
          <ul>
            <li>
              {i18n(actionNs + 'nodes_to_provision', {
                count: nodes.filter(
                  (node) => node.hasRole('virt') && node.get('status') === 'discover'
                ).length
              })}
            </li>
          </ul>
          <button
            className='btn btn-primary btn-provision-vms'
            onClick={() => this.showDialog(ProvisionVMsDialog)}
          >
            {i18n(actionNs + 'button_title')}
          </button>
        </div>
      )
    };
    return (
      <div className='dashboard-block actions-panel clearfix'>
        {this.renderActionsDropdown()}
        {actionControls[action]}
        <div className='col-xs-9 task-alerts'>
          {_.map(['blocker', 'error', 'warning'],
            (severity) => <WarningsBlock
              key={severity}
              severity={severity}
              blockersDescription={blockerDescriptions[action]}
              alerts={alerts[severity]}
            />
          )}
        </div>
      </div>
    );
  },
  renderActionsDropdown() {
    var actions = _.without(this.props.actions, this.state.currentAction);
    if (!this.isActionAvailable('spawn_vms')) actions = _.without(actions, 'spawn_vms');

    return (
      <ul className='nav navbar-nav navbar-right'>
        <li className='deployment-modes-label'>
          {i18n(ns + 'deployment_mode')}:
        </li>
        <li className='dropdown'>
          <button className='btn btn-link dropdown-toggle' data-toggle='dropdown'>
            {i18n(
              ns + 'actions.' + this.state.currentAction + '.title'
            )} <span className='caret'></span>
          </button>
          <ul className='dropdown-menu'>
            {_.map(actions,
              (action) => <li key={action} className={action}>
                <button
                  className='btn btn-link'
                  onClick={() => this.toggleAction(action)}
                >
                  {i18n(ns + 'actions.' + action + '.title')}
                </button>
              </li>
            )}
          </ul>
        </li>
      </ul>
    );
  },
  render() {
    var {cluster} = this.props;
    var nodes = cluster.get('nodes');
    if (nodes.length && !nodes.hasChanges() && !cluster.needsRedeployment()) return null;

    if (!nodes.length) {
      return (
        <div className='row'>
          <div className='dashboard-block clearfix'>
            <div className='col-xs-12'>
              <h4>{i18n(ns + 'new_environment_welcome')}</h4>
              <InstructionElement
                description='no_nodes_instruction'
                link={{
                  url: 'user-guide.html#add-nodes-ug',
                  title: 'user_guide'
                }}
                explanation='for_more_information_roles'
              />
              <AddNodesButton cluster={cluster} />
            </div>
          </div>
        </div>
      );
    }
    return <div className='row'>{this.renderActions()}</div>;
  }
});

var WarningsBlock = React.createClass({
  render() {
    var {alerts, severity, blockersDescription} = this.props;
    if (_.isEmpty(alerts)) return null;
    return (
      <div className='warnings-block'>
        {severity === 'blocker' && blockersDescription}
        <ul className={'text-' + (severity === 'warning' ? 'warning' : 'danger')}>
          {_.map(alerts, (alert, index) => <li key={severity + index}>{alert}</li>)}
        </ul>
      </div>
    );
  }
});

var ClusterInfo = React.createClass({
  mixins: [renamingMixin('clustername')],
  getClusterValue(fieldName) {
    var cluster = this.props.cluster;
    var settings = cluster.get('settings');
    switch (fieldName) {
      case 'status':
        return i18n('cluster.status.' + cluster.get('status'));
      case 'openstack_release':
        return cluster.get('release').get('name');
      case 'compute':
        var libvirtSettings = settings.get('common').libvirt_type;
        var computeLabel = _.find(libvirtSettings.values, {data: libvirtSettings.value}).label;
        if (settings.get('common').use_vcenter.value) {
          return computeLabel + ' ' + i18n(ns + 'and_vcenter');
        }
        return computeLabel;
      case 'network':
        var networkingParameters = cluster.get('networkConfiguration').get('networking_parameters');
        if (cluster.get('net_provider') === 'nova_network') {
          return i18n(ns + 'nova_with') + ' ' + networkingParameters.get('net_manager');
        }
        return (i18n('common.network.neutron_' + networkingParameters.get('segmentation_type')));
      case 'storage_backends':
        return _.map(_.where(settings.get('storage'), {value: true}), 'label') ||
          i18n(ns + 'no_storage_enabled');
      default:
        return cluster.get(fieldName);
    }
  },
  renderClusterInfoFields() {
    return (
      _.map(['status', 'openstack_release', 'compute', 'network', 'storage_backends'], (field) => {
        var value = this.getClusterValue(field);
        return (
          <div key={field}>
            <div className='col-xs-6'>
              <div className='cluster-info-title'>
                {i18n(ns + 'cluster_info_fields.' + field)}
              </div>
            </div>
            <div className='col-xs-6'>
              <div className={utils.classNames({
                'cluster-info-value': true,
                [field]: true,
                'text-danger': field === 'status' && value === i18n('cluster.status.error')
              })}>
                {_.isArray(value) ? value.map((line) => <p key={line}>{line}</p>) : <p>{value}</p>}
              </div>
            </div>
          </div>
        );
      }, this)
    );
  },
  renderClusterCapacity() {
    var capacityNs = ns + 'cluster_info_fields.';
    var capacity = this.props.cluster.getCapacity();

    return (
      <div className='row capacity-block content-elements'>
        <div className='title'>{i18n(capacityNs + 'capacity')}</div>
        <div className='col-xs-12 capacity-items'>
          <div className='col-xs-4 cpu'>
            <span>{i18n(capacityNs + 'cpu_cores')}</span>
            <span className='capacity-value'>{capacity.cores} ({capacity.ht_cores})</span>
          </div>
          <div className='col-xs-4 ram'>
            <span>{i18n(capacityNs + 'ram')}</span>
            <span className='capacity-value'>{utils.showDiskSize(capacity.ram)}</span>
          </div>
          <div className='col-xs-4 hdd'>
            <span>{i18n(capacityNs + 'hdd')}</span>
            <span className='capacity-value'>{utils.showDiskSize(capacity.hdd)}</span>
          </div>
        </div>
      </div>
    );
  },
  getNumberOfNodesWithRole(field) {
    var nodes = this.props.cluster.get('nodes');
    if (field === 'total') return nodes.length;
    return _.filter(nodes.invoke('hasRole', field)).length;
  },
  getNumberOfNodesWithStatus(field) {
    var nodes = this.props.cluster.get('nodes');
    switch (field) {
      case 'offline':
        return nodes.where({online: false}).length;
      case 'pending_addition':
      case 'pending_deletion':
        return nodes.where({[field]: true}).length;
      default:
        return nodes.where({status: field}).length;
    }
  },
  renderLegend(fieldsData, isRole) {
    var result = _.map(fieldsData, (field) => {
      var numberOfNodes = isRole ? this.getNumberOfNodesWithRole(field) :
        this.getNumberOfNodesWithStatus(field);
      return numberOfNodes ?
        <div key={field} className='row'>
          <div className='col-xs-10'>
            <div className='cluster-info-title'>
              {isRole && field !== 'total' ?
                this.props.cluster.get('roles').find({name: field}).get('label')
              :
                field === 'total' ?
                  i18n(ns + 'cluster_info_fields.total')
                :
                  i18n('cluster_page.nodes_tab.node.status.' + field,
                    {os: this.props.cluster.get('release').get('operating_system') || 'OS'})
              }
            </div>
          </div>
          <div className='col-xs-2'>
            <div className={'cluster-info-value ' + field}>
              {numberOfNodes}
            </div>
          </div>
        </div>
      :
        null;
    });

    return result;
  },
  renderStatistics() {
    var {cluster} = this.props;
    var roles = _.union(['total'], cluster.get('roles').pluck('name'));
    var statuses = [
      'offline', 'error', 'pending_addition', 'pending_deletion', 'ready',
      'provisioned', 'provisioning', 'deploying', 'removing'
    ];
    return (
      <div className='row statistics-block'>
        <div className='title'>{i18n(ns + 'cluster_info_fields.statistics')}</div>
        {cluster.get('nodes').length ?
          [
            <div className='col-xs-6' key='roles'>
              {this.renderLegend(roles, true)}
              {!cluster.task({group: 'deployment', active: true}) &&
                <AddNodesButton cluster={cluster} />
              }
            </div>,
            <div className='col-xs-6' key='statuses'>
              {this.renderLegend(statuses)}
            </div>
          ]
        :
          <div className='col-xs-12 no-nodes-block'>
            <p>{i18n(ns + 'no_nodes_warning_add_them')}</p>
          </div>
        }
      </div>
    );
  },
  render() {
    var cluster = this.props.cluster;
    return (
      <div className='cluster-information'>
        <div className='row'>
          <div className='col-xs-6'>
            <div className='row'>
              <div className='title'>{i18n(ns + 'summary')}</div>
              <div className='col-xs-6'>
                <div className='cluster-info-title'>
                  {i18n(ns + 'cluster_info_fields.name')}
                </div>
              </div>
              <div className='col-xs-6'>
                {this.state.isRenaming ?
                  <RenameEnvironmentAction
                    cluster={cluster}
                    ref='clustername'
                    {... _.pick(this, 'startRenaming', 'endRenaming')}
                  />
                :
                  <div className='cluster-info-value name' onClick={this.startRenaming}>
                    <button className='btn-link cluster-name'>
                      {cluster.get('name')}
                    </button>
                    <i className='glyphicon glyphicon-pencil'></i>
                  </div>
                }
              </div>
              {this.renderClusterInfoFields()}
              {(cluster.get('status') === 'operational') &&
                <div className='col-xs-12 go-to-healthcheck'>
                  {i18n(ns + 'healthcheck')}
                  <a href={'#cluster/' + cluster.id + '/healthcheck'}>
                    {i18n(ns + 'healthcheck_tab')}
                  </a>
                </div>
              }
              <div className='col-xs-12 dashboard-actions-wrapper'>
                <DeleteEnvironmentAction cluster={cluster} />
                <ResetEnvironmentAction
                  cluster={cluster}
                  task={cluster.task({group: 'deployment', active: true})}
                />
              </div>
            </div>
          </div>
          <div className='col-xs-6'>
            {this.renderClusterCapacity()}
            {this.renderStatistics()}
          </div>
        </div>
      </div>
    );
  }
});

var AddNodesButton = React.createClass({
  render() {
    return (
      <a
        className='btn btn-success btn-add-nodes'
        href={'#cluster/' + this.props.cluster.id + '/nodes/add'}
      >
        <i className='glyphicon glyphicon-plus' />
        {i18n(ns + 'go_to_nodes')}
      </a>
    );
  }
});

var RenameEnvironmentAction = React.createClass({
  applyAction(e) {
    e.preventDefault();
    var {cluster, endRenaming} = this.props;
    var name = this.state.name;
    if (name !== cluster.get('name')) {
      var deferred = cluster.save({name: name}, {patch: true, wait: true});
      if (deferred) {
        this.setState({disabled: true});
        deferred
          .fail((response) => {
            if (response.status === 409) {
              this.setState({error: utils.getResponseText(response)});
            } else {
              utils.showErrorDialog({
                title: i18n(ns + 'rename_error.title'),
                response: response
              });
            }
          })
          .done(() => {
            dispatcher.trigger('updatePageLayout');
          })
          .always(() => {
            this.setState({disabled: false});
            if (!this.state.error) endRenaming();
          });
      } else if (cluster.validationError) {
        this.setState({error: cluster.validationError.name});
      }
    } else {
      endRenaming();
    }
  },
  getInitialState() {
    return {
      name: this.props.cluster.get('name'),
      disabled: false,
      error: ''
    };
  },
  onChange(inputName, newValue) {
    this.setState({
      name: newValue,
      error: ''
    });
  },
  handleKeyDown(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      this.applyAction(e);
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      this.props.endRenaming();
    }
  },
  render() {
    var classes = {
      'rename-block': true,
      'has-error': !!this.state.error
    };
    return (
      <div className={utils.classNames(classes)}>
        <div className='action-body' onKeyDown={this.handleKeyDown}>
          <Input
            type='text'
            disabled={this.state.disabled}
            className={utils.classNames({'form-control': true, error: this.state.error})}
            maxLength='50'
            onChange={this.onChange}
            defaultValue={this.state.name}
            selectOnFocus
            autoFocus
          />
          {this.state.error &&
            <div className='text-danger'>{this.state.error}</div>
          }
        </div>
      </div>
    );
  }
});

var ResetEnvironmentAction = React.createClass({
  mixins: [
    backboneMixin('cluster'),
    backboneMixin('task')
  ],
  getDescriptionKey() {
    var {cluster, task} = this.props;
    if (task) {
      if (task.match({name: 'reset_environment'})) return 'repeated_reset_disabled';
      return 'reset_disabled_for_deploying_cluster';
    }
    if (cluster.get('nodes').all({status: 'discover'})) return 'no_changes_to_reset';
    return 'reset_environment_description';
  },
  render() {
    var {cluster, task} = this.props;
    var isLocked = cluster.get('status') === 'new' &&
      cluster.get('nodes').all({status: 'discover'}) ||
      !!task;
    return (
      <div className='pull-right reset-environment'>
        <button
          className='btn btn-default reset-environment-btn'
          onClick={() => ResetEnvironmentDialog.show({cluster})}
          disabled={isLocked}
        >
          {i18n(ns + 'reset_environment')}
        </button>
        <Tooltip
          key='reset-tooltip'
          placement='right'
          text={!isLocked ? i18n(ns + 'reset_environment_warning') :
            i18n(ns + this.getDescriptionKey())}
        >
          <i className='glyphicon glyphicon-info-sign' />
        </Tooltip>
      </div>
    );
  }
});

var DeleteEnvironmentAction = React.createClass({
  render() {
    return (
      <div className='delete-environment pull-left'>
        <button
          className='btn delete-environment-btn btn-default'
          onClick={() => RemoveClusterDialog.show({cluster: this.props.cluster})}
        >
          {i18n(ns + 'delete_environment')}
        </button>
        <Tooltip
          key='delete-tooltip'
          placement='right'
          text={i18n(ns + 'alert_delete')}
        >
          <i className='glyphicon glyphicon-info-sign' />
        </Tooltip>
      </div>
    );
  }
});

var InstructionElement = React.createClass({
  propTypes: {
    description: React.PropTypes.string.isRequired,
    isAlert: React.PropTypes.bool,
    link: React.PropTypes.shape({
      url: React.PropTypes.string,
      title: React.PropTypes.string
    }),
    explanation: React.PropTypes.string
  },
  getDefaultProps() {
    return {
      isAlert: false
    };
  },
  render() {
    var {description, isAlert, link, explanation} = this.props;
    return (
      <div className={utils.classNames({instruction: true, invalid: isAlert})}>
        {i18n(ns + description) + (link ? ' ' : '')}
        {link && <a href={link.url} target='_blank'>{i18n(ns + link.title)}</a>}
        {explanation ? ' ' + i18n(ns + explanation) : '.'}
      </div>
    );
  }
});

export default DashboardTab;
