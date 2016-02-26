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
import _ from 'underscore';
import i18n from 'i18n';
import Backbone from 'backbone';
import React from 'react';
import utils from 'utils';
import models from 'models';
import dispatcher from 'dispatcher';
import {Input, Popover, Tooltip} from 'views/controls';
import {DeleteNodesDialog, RemoveOfflineNodeDialog, ShowNodeInfoDialog} from 'views/dialogs';
import {renamingMixin} from 'component_mixins';

var Node = React.createClass({
  mixins: [renamingMixin('name')],
  getInitialState() {
    return {
      actionInProgress: false,
      extendedView: false,
      labelsPopoverVisible: false
    };
  },
  componentDidUpdate() {
    if (!this.props.node.get('cluster') && !this.props.checked) {
      this.props.node.set({pending_roles: []}, {assign: true});
    }
  },
  getNodeLogsLink() {
    var status = this.props.node.get('status');
    var error = this.props.node.get('error_type');
    var options = {type: 'remote', node: this.props.node.id};
    if (status === 'discover') {
      options.source = 'bootstrap/messages';
    } else if (
      status === 'provisioning' ||
      status === 'provisioned' ||
      (status === 'error' && error === 'provision')
    ) {
      options.source = 'install/fuel-agent';
    } else if (
      status === 'deploying' ||
      status === 'ready' ||
      (status === 'error' && error === 'deploy')
    ) {
      options.source = 'install/puppet';
    }
    return '#cluster/' + this.props.node.get('cluster') + '/logs/' +
      utils.serializeTabOptions(options);
  },
  applyNewNodeName(newName) {
    if (newName && newName !== this.props.node.get('name')) {
      this.setState({actionInProgress: true});
      this.props.node.save({name: newName}, {patch: true, wait: true}).always(this.endRenaming);
    } else {
      this.endRenaming();
    }
  },
  onNodeNameInputKeydown(e) {
    if (e.key === 'Enter') {
      this.applyNewNodeName(this.refs.name.getInputDOMNode().value);
    } else if (e.key === 'Escape') {
      this.endRenaming();
    }
  },
  discardNodeDeletion(e) {
    e.preventDefault();
    if (this.state.actionInProgress) return;
    this.setState({actionInProgress: true});
    new models.Node(this.props.node.attributes)
      .save({pending_deletion: false}, {patch: true})
      .done(() => {
        this.props.cluster.fetchRelated('nodes').done(() => {
          this.setState({actionInProgress: false});
        });
      })
      .fail((response) => {
        utils.showErrorDialog({
          title: i18n('cluster_page.nodes_tab.node.cant_discard'),
          response: response
        });
      });
  },
  removeNode(e) {
    e.preventDefault();
    if (this.props.viewMode === 'compact') this.toggleExtendedNodePanel();
    RemoveOfflineNodeDialog
      .show()
      .done(() => {
        // sync('delete') is used instead of node.destroy() because we want
        // to keep showing the 'Removing' status until the node is truly removed
        // Otherwise this node would disappear and might reappear again upon
        // cluster nodes refetch with status 'Removing' which would look ugly
        // to the end user
        return Backbone
          .sync('delete', this.props.node)
          .then(
            (task) => {
              dispatcher.trigger('networkConfigurationUpdated updateNodeStats ' +
                'updateNotifications labelsConfigurationUpdated');
              if (task.status === 'ready') {
                // Do not send the 'DELETE' request again, just get rid
                // of this node.
                this.props.node.trigger('destroy', this.props.node);
                return;
              }
              if (this.props.cluster) {
                this.props.cluster.get('tasks').add(new models.Task(task), {parse: true});
              }
              this.props.node.set('status', 'removing');
            },
            (response) => {
              utils.showErrorDialog({response: response});
            }
          );
      });
  },
  showNodeDetails(e) {
    e.preventDefault();
    if (this.state.extendedView) this.toggleExtendedNodePanel();
    ShowNodeInfoDialog.show({
      node: this.props.node,
      cluster: this.props.cluster,
      nodeNetworkGroup: this.props.nodeNetworkGroups.get(this.props.node.get('group_id')),
      renderActionButtons: this.props.renderActionButtons
    });
  },
  toggleExtendedNodePanel() {
    var states = this.state.extendedView ?
      {extendedView: false, isRenaming: false} : {extendedView: true};
    this.setState(states);
  },
  renderNameControl() {
    if (this.state.isRenaming) {
      return (
        <Input
          ref='name'
          type='text'
          name='node-name'
          defaultValue={this.props.node.get('name')}
          inputClassName='form-control node-name-input'
          disabled={this.state.actionInProgress}
          onKeyDown={this.onNodeNameInputKeydown}
          maxLength='100'
          selectOnFocus
          autoFocus
        />
      );
    }
    return (
      <Tooltip text={i18n('cluster_page.nodes_tab.node.edit_name')}>
        <p onClick={!this.state.actionInProgress && this.startRenaming}>
          {this.props.node.get('name') || this.props.node.get('mac')}
        </p>
      </Tooltip>
    );
  },
  renderStatusLabel(status) {
    return (
      <span>
        {i18n('cluster_page.nodes_tab.node.status.' + status, {
          os: this.props.cluster && this.props.cluster.get('release').get('operating_system')
            || 'OS'
        })}
      </span>
    );
  },
  renderNodeProgress(status) {
    var nodeProgress = this.props.node.get('progress');
    return (
      <div className='progress'>
        {status &&
          <div className='progress-bar-title'>
            {this.renderStatusLabel(status)}
            {': ' + nodeProgress + '%'}
          </div>
        }
        <div
          className='progress-bar'
          role='progressbar'
          style={{width: _.max([nodeProgress, 3]) + '%'}}
        >
        </div>
      </div>
    );
  },
  renderNodeHardwareSummary() {
    var htCores = this.props.node.resource('ht_cores');
    var hdd = this.props.node.resource('hdd');
    var ram = this.props.node.resource('ram');
    return (
      <div className='node-hardware'>
        <span>
          {i18n('node_details.cpu')}
          {': '}
          {this.props.node.resource('cores') || '0'} ({_.isUndefined(htCores) ? '?' : htCores})
        </span>
        <span>
          {i18n('node_details.ram')}
          {': '}
          {_.isUndefined(ram) ? '?' + i18n('common.size.gb') : utils.showMemorySize(ram)}
        </span>
        <span>
          {i18n('node_details.hdd')}
          {': '}
          {_.isUndefined(hdd) ? '?' + i18n('common.size.gb') : utils.showDiskSize(hdd)}
        </span>
      </div>
    );
  },
  renderLogsLink(iconRepresentation) {
    return (
      <Tooltip
        key='logs'
        text={iconRepresentation ? i18n('cluster_page.nodes_tab.node.view_logs') : null}
      >
        <a
          className={'btn-view-logs ' + (iconRepresentation ? 'icon icon-logs' : 'btn')}
          href={this.getNodeLogsLink()}
        >
          {!iconRepresentation && i18n('cluster_page.nodes_tab.node.view_logs')}
        </a>
      </Tooltip>
    );
  },
  renderNodeCheckbox() {
    return (
      <Input
        type='checkbox'
        name={this.props.node.id}
        checked={this.props.checked}
        disabled={
          this.props.locked ||
          !this.props.node.isSelectable()
          || this.props.mode === 'edit'
        }
        onChange={this.props.mode !== 'edit' ? this.props.onNodeSelection : _.noop}
        wrapperClassName='pull-left'
      />
    );
  },
  renderRemoveButton() {
    return (
      <button onClick={this.removeNode} className='btn node-remove-button'>
        {i18n('cluster_page.nodes_tab.node.remove')}
      </button>
    );
  },
  renderRoleList(roles) {
    return (
      <ul>
        {_.map(roles, (role) => {
          return (
            <li
              key={this.props.node.id + role}
              className={utils.classNames({'text-success': !this.props.node.get('roles').length})}
            >
              {role}
            </li>
          );
        })}
      </ul>
    );
  },
  showDeleteNodesDialog(e) {
    e.preventDefault();
    if (this.props.viewMode === 'compact') this.toggleExtendedNodePanel();
    DeleteNodesDialog
      .show({
        nodes: new models.Nodes(this.props.node),
        cluster: this.props.cluster
      })
      .done(this.props.onNodeSelection);
  },
  renderLabels() {
    var labels = this.props.node.get('labels');
    if (_.isEmpty(labels)) return null;
    return (
      <ul>
        {_.map(_.keys(labels).sort(_.partialRight(utils.natsort, {insensitive: true})), (key) => {
          var value = labels[key];
          return (
            <li key={key + value} className='label'>
              {key + (_.isNull(value) ? '' : ' "' + value + '"')}
            </li>
          );
        })}
      </ul>
    );
  },
  renderExtendedView(options) {
    var {node, locked, renderActionButtons} = this.props;
    var {ns, status, roles, logoClasses, statusClasses} = options;

    return (
      <Popover className='node-popover' toggle={this.toggleExtendedNodePanel}>
        <div>
          <div className='node-name clearfix'>
            {this.renderNodeCheckbox()}
            <div className='name pull-left'>
              {this.props.nodeSelectionPossibleOnly ?
                <div>{node.get('name') || node.get('mac')}</div>
              :
                this.renderNameControl()
              }
            </div>
          </div>
          <div className='node-stats'>
            {!!roles.length &&
              <div className='role-list'>
                <i className='glyphicon glyphicon-pushpin' />
                {this.renderRoleList(roles)}
              </div>
            }
            {!_.isEmpty(node.get('labels')) &&
              <div className='node-labels'>
                <i className='glyphicon glyphicon-tags pull-left' />
                {this.renderLabels()}
              </div>
            }
            <div className={utils.classNames(statusClasses)}>
              <i className='glyphicon glyphicon-time' />
              {_.contains(['provisioning', 'deploying'], status) ?
                <div>
                  {this.renderStatusLabel(status)}
                  <div className='node-buttons'>
                    {this.renderLogsLink()}
                  </div>
                  {this.renderNodeProgress(status)}
                </div>
              :
                <div>
                  {this.renderStatusLabel(status)}
                  {!this.props.nodeSelectionPossibleOnly &&
                    <div className='node-buttons'>
                      {status === 'offline' && this.renderRemoveButton()}
                      {[
                        !!node.get('cluster') && this.renderLogsLink(),
                        renderActionButtons &&
                          (node.get('pending_addition') || node.get('pending_deletion')) &&
                          !locked &&
                          <button
                            className='btn btn-discard'
                            key='btn-discard'
                            onClick={node.get('pending_deletion') ?
                              this.discardNodeDeletion
                            :
                              this.showDeleteNodesDialog
                            }
                          >
                            {i18n(ns + (node.get('pending_deletion') ?
                              'discard_deletion'
                            :
                              'delete_node'
                            ))}
                          </button>
                      ]}
                    </div>
                  }
                </div>
              }
            </div>
          </div>
          <div className='hardware-info clearfix'>
            <div className={utils.classNames(logoClasses)} />
            {this.renderNodeHardwareSummary()}
          </div>
          {!this.props.nodeSelectionPossibleOnly &&
            <div className='node-popover-buttons'>
              <button className='btn btn-default node-settings' onClick={this.showNodeDetails}>
                {i18n(ns + 'details')}
              </button>
            </div>
          }
        </div>
      </Popover>
    );
  },
  renderCompactNode(options) {
    var {node, checked, onNodeSelection} = this.props;
    var {ns, status, nodePanelClasses, statusClasses, isSelectable} = options;

    return (
      <div className='compact-node'>
        <div className={utils.classNames(nodePanelClasses)}>
          <label className='node-box'>
            <div
              className='node-box-inner clearfix'
              onClick={isSelectable && _.partial(onNodeSelection, null, !checked)}
            >
              <div className='node-checkbox'>
                {checked && <i className='glyphicon glyphicon-ok' />}
              </div>
              <div className='node-name'>
                <p>{node.get('name') || node.get('mac')}</p>
              </div>
              <div className={utils.classNames(statusClasses)}>
                {_.contains(['provisioning', 'deploying'], status) ?
                  this.renderNodeProgress()
                :
                  this.renderStatusLabel(status)
                }
              </div>
            </div>
            <div className='node-hardware'>
              <p>
                <span>
                  {node.resource('cores')} ({node.resource('ht_cores') || '?'})
                </span> / <span>
                  {node.resource('hdd') ? utils.showDiskSize(node.resource('hdd')) : '?' +
                    i18n('common.size.gb')
                  }
                </span> / <span>
                  {node.resource('ram') ? utils.showMemorySize(node.resource('ram')) : '?' +
                    i18n('common.size.gb')
                  }
                </span>
              </p>
              <p className='btn btn-link' onClick={this.toggleExtendedNodePanel}>
                {i18n(ns + 'more_info')}
              </p>
            </div>
          </label>
        </div>
        {this.state.extendedView && this.renderExtendedView(options)}
      </div>
    );
  },
  renderStandardNode(options) {
    var {node, locked, renderActionButtons} = this.props;
    var {ns, status, roles, nodePanelClasses, logoClasses, statusClasses} = options;
    return (
      <div className={utils.classNames(nodePanelClasses)}>
        <label className='node-box'>
          {this.renderNodeCheckbox()}
          <div className={utils.classNames(logoClasses)} />
          <div className='node-name'>
            <div className='name'>
              {this.props.nodeSelectionPossibleOnly ?
                <p>{node.get('name') || node.get('mac')}</p>
              :
                this.renderNameControl()
              }
            </div>
            <div className='role-list'>
              {this.renderRoleList(roles)}
            </div>
          </div>
          <div className='node-labels'>
            {!_.isEmpty(node.get('labels')) &&
              <button className='btn btn-link' onClick={this.toggleLabelsPopover}>
                <i className='glyphicon glyphicon-tag-alt' />
                {_.keys(node.get('labels')).length}
              </button>
            }
            {this.state.labelsPopoverVisible &&
              <Popover className='node-labels-popover' toggle={this.toggleLabelsPopover}>
                {this.renderLabels()}
              </Popover>
            }
          </div>
          <div className='node-action'>
            {!this.props.nodeSelectionPossibleOnly && [
              !!node.get('cluster') && this.renderLogsLink(true),
              renderActionButtons &&
                (node.get('pending_addition') || node.get('pending_deletion')) &&
                !locked &&
                <Tooltip
                  key={'discard-node-changes-' + node.id}
                  text={i18n(ns +
                    (node.get('pending_deletion') ? 'discard_deletion' : 'delete_node')
                  )}
                >
                  <div
                    className='icon btn-discard'
                    onClick={node.get('pending_deletion') ?
                      this.discardNodeDeletion
                    :
                      this.showDeleteNodesDialog
                    }
                  />
                </Tooltip>
            ]}
          </div>
          <div className={utils.classNames(statusClasses)}>
            {_.contains(['provisioning', 'deploying'], status) ?
              this.renderNodeProgress(status)
            :
              <div>
                {this.renderStatusLabel(status)}
                {status === 'offline' && this.renderRemoveButton()}
              </div>
            }
          </div>
          {this.renderNodeHardwareSummary()}
          {!this.props.nodeSelectionPossibleOnly &&
            <div className='node-settings' onClick={this.showNodeDetails} />
          }
        </label>
      </div>
    );
  },
  toggleLabelsPopover(visible) {
    this.setState({
      labelsPopoverVisible: _.isBoolean(visible) ? visible : !this.state.labelsPopoverVisible
    });
  },
  render() {
    var ns = 'cluster_page.nodes_tab.node.';
    var node = this.props.node;
    var isSelectable = node.isSelectable() && !this.props.locked && this.props.mode !== 'edit';
    var status = node.getStatusSummary();
    var roles = this.props.cluster ? node.sortedRoles(
      this.props.cluster.get('roles').pluck('name')
    ) : [];

    // compose classes
    var nodePanelClasses = {
      node: true,
      selected: this.props.checked,
      'col-xs-12': this.props.viewMode !== 'compact',
      unavailable: !isSelectable
    };
    nodePanelClasses[status] = status;

    var manufacturer = node.get('manufacturer') || '';
    var logoClasses = {
      'manufacturer-logo': true
    };
    logoClasses[manufacturer.toLowerCase()] = manufacturer;

    var statusClasses = {
      'node-status': true
    };
    var statusClass = {
      pending_addition: 'text-success',
      pending_deletion: 'text-warning',
      error: 'text-danger',
      ready: 'text-info',
      provisioning: 'text-info',
      deploying: 'text-success',
      provisioned: 'text-info'
    }[status];
    statusClasses[statusClass] = true;

    var renderMethod = this.props.viewMode === 'compact' ? this.renderCompactNode :
      this.renderStandardNode;

    return renderMethod({
      ns, status, roles, nodePanelClasses,
      logoClasses, statusClasses, isSelectable
    });
  }
});

export default Node;
