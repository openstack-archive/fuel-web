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
import dispatcher from 'dispatcher';
import {Input, ProgressBar, Tooltip} from 'views/controls';
import {
  DiscardNodeChangesDialog, DeployChangesDialog, ProvisionVMsDialog,
  RemoveClusterDialog, ResetEnvironmentDialog, StopDeploymentDialog
} from 'views/dialogs';
import {backboneMixin, pollingMixin, renamingMixin} from 'component_mixins';

var namespace = 'cluster_page.dashboard_tab.';

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
    backboneMixin('cluster', 'change'),
    pollingMixin(20, true)
  ],
  fetchData() {
    return this.props.cluster.get('nodes').fetch();
  },
  render() {
    var cluster = this.props.cluster;
    var nodes = cluster.get('nodes');
    var release = cluster.get('release');
    var runningDeploymentTask = cluster.task({group: 'deployment', active: true});

    var dashboardLinks = [{
      url: '/',
      title: i18n(namespace + 'horizon'),
      description: i18n(namespace + 'horizon_description')
    }].concat(cluster.get('pluginLinks').invoke('pick', 'url', 'title', 'description'));

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
          <DeploymentInProgressControl cluster={cluster} task={runningDeploymentTask} />
        :
          [
            cluster.task({group: 'deployment', active: false}) &&
              <DeploymentResult key='task-result' cluster={cluster} />,
            cluster.get('status') === 'operational' &&
              <DashboardLinks key='plugin-links' cluster={cluster} links={dashboardLinks} />,
            (nodes.hasChanges() || cluster.needsRedeployment()) &&
              <DeployReadinessBlock
                key='changes-to-deploy'
                {... _.pick(this.props, 'cluster', 'nodeNetworkGroups')}
              />,
            !nodes.length && (
              <div className='row' key='new-cluster'>
                <div className='dashboard-block clearfix'>
                  <div className='col-xs-12'>
                    <h4>{i18n(namespace + 'new_environment_welcome')}</h4>
                    <InstructionElement
                      description='no_nodes_instruction'
                      explanation='for_more_information_roles'
                      link='user-guide.html#add-nodes-ug'
                      linkTitle='user_guide'
                    />
                    <AddNodesButton cluster={cluster} />
                  </div>
                </div>
              </div>
            )
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
    return (
      <DashboardLink
        {...link}
        className={this.props.links.length > 1 ? 'col-xs-6' : 'col-xs-12'}
        cluster={this.props.cluster}
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
    var isSSLEnabled = this.props.cluster.get('settings').get('public_ssl.horizon.value');
    var isURLRelative = !(/^(?:https?:)?\/\//.test(this.props.url));
    var url = isURLRelative ? this.processRelativeURL(this.props.url) : this.props.url;
    return (
      <div className={'link-block ' + this.props.className}>
        <div className='title'>
          <a href={url} target='_blank'>{this.props.title}</a>
          {isURLRelative && isSSLEnabled &&
            <a href={this.getHTTPLink(this.props.url)} className='http-link' target='_blank'>
              {i18n(namespace + 'http_plugin_link')}
            </a>
          }
        </div>
        <div className='description'>{this.props.description}</div>
      </div>
    );
  }
});

var DeploymentInProgressControl = React.createClass({
  showDialog(Dialog) {
    Dialog.show({cluster: this.props.cluster});
  },
  render() {
    var task = this.props.task;
    var taskName = task.get('name');
    var isInfiniteTask = task.isInfinite();
    var taskProgress = task.get('progress');
    var showStopButton = task.match({name: 'deploy'});
    return (
      <div className='row'>
        <div className='dashboard-block clearfix'>
          <div className='col-xs-12'>
            <div className={utils.classNames({
              'deploy-process': true,
              [taskName]: true,
              'has-stop-control': showStopButton
            })}>
              <h4>
                <strong>
                  {i18n(namespace + 'current_task') + ' '}
                </strong>
                {i18n('cluster_page.' + taskName) + '...'}
              </h4>
              <ProgressBar progress={!isInfiniteTask && taskProgress} />
              {showStopButton &&
                <Tooltip text={i18n('cluster_page.stop_deployment_button')}>
                  <button
                    className='btn btn-danger btn-xs pull-right stop-deployment-btn'
                    onClick={_.partial(this.showDialog, StopDeploymentDialog)}
                    disabled={!task.isStoppable()}
                  >
                    {i18n(namespace + 'stop')}
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
    var task = this.props.cluster.task({group: 'deployment'});
    if (task) task.destroy();
  },
  componentDidMount() {
    $('.result-details', ReactDOM.findDOMNode(this))
      .on('show.bs.collapse', this.setState.bind(this, {collapsed: true}, null))
      .on('hide.bs.collapse', this.setState.bind(this, {collapsed: false}, null));
  },
  render() {
    var task = this.props.cluster.task({group: 'deployment', active: false});
    if (!task) return null;
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
            {i18n(namespace + labelKey)}
          </a>
        </span>
      </div>
    );
  },
  render() {
    var isMirantisIso = _.contains(app.version.get('feature_groups'), 'mirantis');
    return (
      <div className='row content-elements'>
        <div className='title'>{i18n(namespace + 'documentation')}</div>
        <div className='col-xs-12'>
          <p>{i18n(namespace + 'documentation_description')}</p>
        </div>
        <div className='documentation col-xs-12'>
          {isMirantisIso ?
            [
              this.renderDocumentationLinks(
                'https://www.mirantis.com/openstack-documentation/',
                'mos_documentation'
              ),
              this.renderDocumentationLinks(
                utils.composeDocumentationLink('plugin-dev.html#plugin-dev'),
                'plugin_documentation'
              ),
              this.renderDocumentationLinks(
                'https://software.mirantis.com/mirantis-openstack-technical-bulletins/',
                'technical_bulletins'
              )
            ]
          :
            [
              this.renderDocumentationLinks(
                'http://docs.openstack.org/',
                'openstack_documentation'
              ),
              this.renderDocumentationLinks(
                'https://wiki.openstack.org/wiki/Fuel/Plugins',
                'plugin_documentation'
              )
            ]
          }
        </div>
      </div>
    );
  }
});

// @FIXME (morale): this component is written in a bad pattern of 'monolith' component
// it should be refactored to provide proper logics separation and decoupling
var DeployReadinessBlock = React.createClass({
  mixins: [
    // this is needed to somehow handle the case when verification
    // is in progress and user pressed Deploy
    backboneMixin({
      modelOrCollection(props) {
        return props.cluster.get('tasks');
      },
      renderOn: 'update change'
    }),
    backboneMixin('cluster', 'change')
  ],
  ns: 'dialog.display_changes.',
  getConfigModels() {
    var {cluster} = this.props;
    return {
      cluster: cluster,
      settings: cluster.get('settings'),
      version: app.version,
      release: cluster.get('release'),
      default: cluster.get('settings'),
      networking_parameters: cluster.get('networkConfiguration').get('networking_parameters')
    };
  },
  validate(cluster) {
    return _.reduce(
      this.validations,
      (accumulator, validator) => _.merge(accumulator, validator.call(this, cluster), (a, b) =>
        a.concat(_.compact(b))),
      {blocker: [], error: [], warning: []}
    );
  },
  validations: [
    // check if TLS settings are not configured
    function(cluster) {
      var sslSettings = cluster.get('settings').get('public_ssl');
      if (!sslSettings.horizon.value && !sslSettings.services.value) {
        return {warning: [i18n(this.ns + 'tls_not_enabled')]};
      }
      if (!sslSettings.horizon.value) {
        return {warning: [i18n(this.ns + 'tls_for_horizon_not_enabled')]};
      }
      if (!sslSettings.services.value) {
        return {warning: [i18n(this.ns + 'tls_for_services_not_enabled')]};
      }
    },
    // check if deployment failed
    function(cluster) {
      return cluster.needsRedeployment() && {
        error: [
          <InstructionElement
            key='unsuccessful_deploy'
            description='unsuccessful_deploy'
            link='operations.html#troubleshooting'
            linkTitle='user_guide'
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
            {i18n(this.ns + 'invalid_settings')}
            {' ' + i18n(this.ns + 'get_more_info') + ' '}
            <a href={'#cluster/' + cluster.id + '/settings'}>
              {i18n(this.ns + 'settings_link')}
            </a>.
          </span>
        ]};
    },
    // check node amount restrictions according to their roles
    function(cluster) {
      var configModels = this.getConfigModels();
      var roleModels = cluster.get('roles');
      var validRoleModels = roleModels.filter((role) => {
        return !role.checkRestrictions(configModels).result;
      });
      var limitValidations = _.zipObject(validRoleModels.map((role) => {
        return [role.get('name'), role.checkLimits(configModels, cluster.get('nodes'))];
      }));
      var limitRecommendations = _.zipObject(validRoleModels.map((role) => {
        return [role.get('name'), role.checkLimits(configModels, cluster.get('nodes'), true,
          ['recommended'])];
      }));
      return {
        blocker: roleModels.map((role) => {
          var name = role.get('name');
          var limits = limitValidations[name];
          return limits && !limits.valid && limits.message;
        }),
        warning: roleModels.map((role) => {
          var name = role.get('name');
          var recommendation = limitRecommendations[name];
          return recommendation && !recommendation.valid && recommendation.message;
        })
      };
    },
    // check cluster network configuration
    function(cluster) {
      if (this.props.nodeNetworkGroups.where({cluster_id: cluster.id}).length > 1) return null;
      var networkVerificationTask = cluster.task('verify_networks');
      var makeComponent = (text, isError) => {
        var span = (
          <span key='invalid_networks'>
            {text}
            {' ' + i18n(this.ns + 'get_more_info') + ' '}
            <a href={'#cluster/' + this.props.cluster.id + '/network'}>
              {i18n(this.ns + 'networks_link')}
            </a>.
          </span>
        );
        return isError ? {error: [span]} : {warning: [span]};
      };
      if (_.isUndefined(networkVerificationTask)) {
        return makeComponent(i18n(this.ns + 'verification_not_performed'));
      } else if (networkVerificationTask.match({status: 'error'})) {
        return makeComponent(i18n(this.ns + 'verification_failed'), true);
      } else if (networkVerificationTask.match({active: true})) {
        return makeComponent(i18n(this.ns + 'verification_in_progress'));
      }
    }
  ],
  showDialog(Dialog, options) {
    Dialog.show(_.extend({cluster: this.props.cluster}, options));
  },
  renderChangedNodesAmount(nodes, dictKey) {
    if (!nodes.length) return null;
    return (
      <li className='changes-item' key={dictKey}>
        {i18n('dialog.display_changes.' + dictKey, {count: nodes.length})}
        <button
          className='btn btn-link btn-discard-changes'
          onClick={_.partial(this.showDialog, DiscardNodeChangesDialog, {nodes: nodes})}
        >
          <i className='discard-changes-icon' />
        </button>
      </li>
    );
  },
  render() {
    var cluster = this.props.cluster;
    var nodes = cluster.get('nodes');
    var alerts = this.validate(cluster);
    var isDeploymentPossible = cluster.isDeploymentPossible() && !alerts.blocker.length;
    var isVMsProvisioningAvailable = nodes.any((node) => {
      return node.get('pending_addition') && node.hasRole('virt');
    });

    return (
      <div className='row'>
        <div className='dashboard-block clearfix'>
          <div className='col-xs-3 changes-list'>
            {nodes.hasChanges() &&
              <div>
                <h4>{i18n(namespace + 'changes_header')}</h4>
                <ul>
                  {this.renderChangedNodesAmount(
                    nodes.where({pending_addition: true}),
                    'added_node'
                  )}
                  {this.renderChangedNodesAmount(
                    nodes.where({status: 'provisioned'}),
                    'provisioned_node'
                  )}
                  {this.renderChangedNodesAmount(
                    nodes.where({pending_deletion: true}),
                    'deleted_node'
                  )}
                </ul>
              </div>
            }
            {isVMsProvisioningAvailable ?
              <button
                className='btn btn-primary deploy-btn'
                onClick={_.partial(this.showDialog, ProvisionVMsDialog)}
              >
                <div className='deploy-icon' />
                {i18n('cluster_page.provision_vms')}
              </button>
            :
              <button
                className={utils.classNames({
                  'btn btn-primary deploy-btn': true,
                  'btn-warning': (
                    _.isEmpty(alerts.blocker) &&
                    (!_.isEmpty(alerts.error) || !_.isEmpty(alerts.warning))
                  )
                })}
                onClick={_.partial(this.showDialog, DeployChangesDialog)}
                disabled={!isDeploymentPossible}
              >
                <div className='deploy-icon' />
                {i18n('cluster_page.deploy_changes')}
              </button>
            }
          </div>
          <div className='col-xs-9 environment-alerts'>
            {_.map(['blocker', 'error', 'warning'],
              (severity) => <WarningsBlock
                key={severity}
                severity={severity}
                alerts={alerts[severity]}
              />
            )}
          </div>
        </div>
      </div>
    );
  }
});

var WarningsBlock = React.createClass({
  ns: 'dialog.display_changes.',
  render() {
    if (_.isEmpty(this.props.alerts)) return null;
    var className = this.props.severity === 'warning' ? 'warning' : 'danger';
    return (
      <div className='warnings-block'>
        {this.props.severity === 'blocker' &&
          <InstructionElement
            description='deployment_cannot_be_started'
            explanation='for_more_information_roles'
            link='user-guide.html#add-nodes-ug'
            linkTitle='user_guide'
            wrapperClass='invalid'
          />
        }
        <ul className={'text-' + className}>
          {_.map(this.props.alerts, (alert, index) => {
            return <li key={this.props.severity + index}>{alert}</li>;
          }, this)}
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
          return computeLabel + ' ' + i18n(namespace + 'and_vcenter');
        }
        return computeLabel;
      case 'network':
        var networkingParameters = cluster.get('networkConfiguration').get('networking_parameters');
        if (cluster.get('net_provider') === 'nova_network') {
          return i18n(namespace + 'nova_with') + ' ' + networkingParameters.get('net_manager');
        }
        return (i18n('common.network.neutron_' + networkingParameters.get('segmentation_type')));
      case 'storage_backends':
        return _.map(_.where(settings.get('storage'), {value: true}), 'label') ||
          i18n(namespace + 'no_storage_enabled');
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
                {i18n(namespace + 'cluster_info_fields.' + field)}
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
    var cores = 0;
    var hdds = 0;
    var ram = 0;
    var ns = namespace + 'cluster_info_fields.';

    this.props.cluster.get('nodes').each((node) => {
      cores += node.resource('ht_cores');
      hdds += node.resource('hdd');
      ram += node.resource('ram');
    }, this);

    return (
      <div className='row capacity-block content-elements'>
        <div className='title'>{i18n(ns + 'capacity')}</div>
        <div className='col-xs-12 capacity-items'>
          <div className='col-xs-4 cpu capacity-item'>
            <span>{i18n(ns + 'cpu_cores')}</span>
            <span className='capacity-value pull-right'>{cores}</span>
          </div>
          <div className='col-xs-4 hdd capacity-item'>
            <span>{i18n(ns + 'hdd')}</span>
            <span className='capacity-value pull-right'>{utils.showDiskSize(hdds)}</span>
          </div>
          <div className='col-xs-4 ram capacity-item'>
            <span>{i18n(ns + 'ram')}</span>
            <span className='capacity-value pull-right'>{utils.showDiskSize(ram)}</span>
          </div>
        </div>
      </div>
    );
  },
  getNumberOfNodesWithRole(field) {
    var nodes = this.props.cluster.get('nodes');
    if (!nodes.length) return 0;
    if (field === 'total') return nodes.length;
    return _.filter(nodes.invoke('hasRole', field)).length;
  },
  getNumberOfNodesWithStatus(field) {
    var nodes = this.props.cluster.get('nodes');
    if (!nodes.length) return 0;
    switch (field) {
      case 'offline':
        return nodes.where({online: false}).length;
      case 'error':
        return nodes.where({status: 'error'}).length;
      case 'pending_addition':
      case 'pending_deletion':
        var searchObject = {};
        searchObject[field] = true;
        return nodes.where(searchObject).length;
      default:
        return nodes.where({status: field}).length;
    }
  },
  renderLegend(fieldsData, isRole) {
    var result = _.map(fieldsData, (field) => {
      var numberOfNodes = isRole ? this.getNumberOfNodesWithRole(field) :
        this.getNumberOfNodesWithStatus(field);
      return numberOfNodes ?
        <div key={field}>
          <div className='col-xs-10'>
            <div className='cluster-info-title'>
              {isRole && field !== 'total' ?
                this.props.cluster.get('roles').find({name: field}).get('label')
              :
                field === 'total' ?
                  i18n(namespace + 'cluster_info_fields.total')
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
    var hasNodes = !!this.props.cluster.get('nodes').length;
    var fieldRoles = _.union(['total'], this.props.cluster.get('roles').pluck('name'));
    var fieldStatuses = [
      'offline', 'error', 'pending_addition', 'pending_deletion', 'ready',
      'provisioned', 'provisioning', 'deploying', 'removing'
    ];
    return (
      <div className='row statistics-block'>
        <div className='title'>{i18n(namespace + 'cluster_info_fields.statistics')}</div>
        {hasNodes ?
          [
            <div className='col-xs-6' key='roles'>
              <div className='row'>
                {this.renderLegend(fieldRoles, true)}
              </div>
              <AddNodesButton
                cluster={this.props.cluster}
              />
            </div>,
            <div className='col-xs-6' key='statuses'>
              <div clasName='row'>
                {this.renderLegend(fieldStatuses)}
              </div>
            </div>
          ]
        :
          <div className='col-xs-12 no-nodes-block'>
            <p>
              {i18n(namespace + 'no_nodes_warning_add_them')}
            </p>
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
              <div className='title'>{i18n(namespace + 'summary')}</div>
              <div className='col-xs-6'>
                <div className='cluster-info-title'>
                  {i18n(namespace + 'cluster_info_fields.name')}
                </div>
              </div>
              <div className='col-xs-6'>
                {this.state.isRenaming ?
                  <RenameEnvironmentAction
                    cluster={cluster}
                    ref='clustername'
                    startRenaming={this.startRenaming}
                    endRenaming={this.endRenaming}
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
                  {i18n(namespace + 'healthcheck')}
                  <a href={'#cluster/' + cluster.id + '/healthcheck'}>
                    {i18n(namespace + 'healthcheck_tab')}
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
    var disabled = !!this.props.cluster.task({group: 'deployment', active: true});
    return (
      <a
        className='btn btn-success btn-add-nodes'
        href={'#cluster/' + this.props.cluster.id + '/nodes/add'}
        disabled={disabled}
      >
        <i className='glyphicon glyphicon-plus' />
        {i18n(namespace + 'go_to_nodes')}
      </a>
    );
  }
});

var RenameEnvironmentAction = React.createClass({
  applyAction(e) {
    e.preventDefault();
    var cluster = this.props.cluster;
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
                title: i18n(namespace + 'rename_error.title'),
                response: response
              });
            }
          })
          .done(() => {
            dispatcher.trigger('updatePageLayout');
          })
          .always(() => {
            this.setState({disabled: false});
            if (!(this.state && this.state.error)) this.props.endRenaming();
          });
      } else if (cluster.validationError) {
        this.setState({error: cluster.validationError.name});
      }
    } else {
      this.props.endRenaming();
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
            <div className='text-danger'>
              {this.state.error}
            </div>
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
    if (this.props.task) {
      if (this.props.task.match({name: 'reset_environment'})) return 'repeated_reset_disabled';
      return 'reset_disabled_for_deploying_cluster';
    }
    if (this.props.cluster.get('status') === 'new') return 'no_changes_to_reset';
    return 'reset_environment_description';
  },
  applyAction(e) {
    e.preventDefault();
    ResetEnvironmentDialog.show({cluster: this.props.cluster});
  },
  render() {
    var isLocked = this.props.cluster.get('status') === 'new' || !!this.props.task;
    return (
      <div className='pull-right reset-environment'>
        <button
          className='btn reset-environment-btn btn-default'
          onClick={this.applyAction}
          disabled={isLocked}
        >
          {i18n(namespace + 'reset_environment')}
        </button>
        <Tooltip
          key='reset-tooltip'
          placement='right'
          text={!isLocked ? i18n(namespace + 'reset_environment_warning') :
            i18n(namespace + this.getDescriptionKey())}
        >
          <i className='glyphicon glyphicon-info-sign' />
        </Tooltip>
      </div>
    );
  }
});

var DeleteEnvironmentAction = React.createClass({
  applyAction(e) {
    e.preventDefault();
    RemoveClusterDialog.show({cluster: this.props.cluster});
  },
  render() {
    return (
      <div className='delete-environment pull-left'>
        <button
          className='btn delete-environment-btn btn-default'
          onClick={this.applyAction}
        >
          {i18n(namespace + 'delete_environment')}
        </button>
        <Tooltip
          key='delete-tooltip'
          placement='right'
          text={i18n(namespace + 'alert_delete')}
        >
          <i className='glyphicon glyphicon-info-sign' />
        </Tooltip>
      </div>
    );
  }
});

var InstructionElement = React.createClass({
  render() {
    var link = utils.composeDocumentationLink(this.props.link);
    var classes = {
      instruction: true
    };
    classes[this.props.wrapperClass] = !!this.props.wrapperClass;
    return (
      <div className={utils.classNames(classes)}>
        {i18n(namespace + this.props.description) + ' '}
        <a href={link} target='_blank'>{i18n(namespace + this.props.linkTitle)}</a>
        {this.props.explanation ? ' ' + i18n(namespace + this.props.explanation) : '.'}
      </div>
    );
  }
});

export default DashboardTab;
