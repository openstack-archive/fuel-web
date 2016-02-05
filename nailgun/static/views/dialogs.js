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

import $ from 'jquery';
import _ from 'underscore';
import i18n from 'i18n';
import React from 'react';
import ReactDOM from 'react-dom';
import Backbone from 'backbone';
import utils from 'utils';
import models from 'models';
import dispatcher from 'dispatcher';
import {Input, ProgressBar} from 'views/controls';
import {backboneMixin, renamingMixin} from 'component_mixins';
import LinkedStateMixin from 'react-addons-linked-state-mixin';

function getActiveDialog() {
  return app.dialog;
}

function setActiveDialog(dialog) {
  if (dialog) {
    app.dialog = dialog;
  } else {
    delete app.dialog;
  }
}

export var dialogMixin = {
  propTypes: {
    title: React.PropTypes.node,
    message: React.PropTypes.node,
    modalClass: React.PropTypes.node,
    error: React.PropTypes.bool,
    closeable: React.PropTypes.bool,
    keyboard: React.PropTypes.bool,
    background: React.PropTypes.bool,
    backdrop: React.PropTypes.oneOfType([
      React.PropTypes.string,
      React.PropTypes.bool
    ])
  },
  statics: {
    show(dialogOptions = {}, showOptions = {}) {
      var activeDialog = getActiveDialog();
      if (activeDialog) {
        var result = $.Deferred();
        if (showOptions.preventDuplicate && activeDialog.constructor === this) {
          result.reject();
        } else {
          $(ReactDOM.findDOMNode(activeDialog)).on('hidden.bs.modal', () => {
            this.show(dialogOptions).then(result.resolve, result.reject);
          });
        }
        return result;
      } else {
        return ReactDOM.render(
          React.createElement(this, dialogOptions),
          $('#modal-container')[0]
        ).getResult();
      }
    }
  },
  updateProps(partialProps) {
    var props;
    props = _.extend({}, this.props, partialProps);
    ReactDOM.render(
      React.createElement(this.constructor, props),
      ReactDOM.findDOMNode(this).parentNode
    );
  },
  getInitialState() {
    return {
      actionInProgress: false,
      result: $.Deferred()
    };
  },
  getResult() {
    return this.state.result;
  },
  componentDidMount() {
    setActiveDialog(this);
    Backbone.history.on('route', this.close, this);
    var $el = $(ReactDOM.findDOMNode(this));
    $el.on('hidden.bs.modal', this.handleHidden);
    $el.on('shown.bs.modal', () => $el.find('input:enabled:first').focus());
    $el.modal(_.defaults(
      {keyboard: false},
      _.pick(this.props, ['background', 'backdrop']),
      {background: true, backdrop: true}
    ));
  },
  rejectResult() {
    if (this.state.result.state() === 'pending') this.state.result.reject();
  },
  componentWillUnmount() {
    Backbone.history.off(null, null, this);
    $(ReactDOM.findDOMNode(this)).off('shown.bs.modal hidden.bs.modal');
    this.rejectResult();
    setActiveDialog(null);
  },
  handleHidden() {
    ReactDOM.unmountComponentAtNode(ReactDOM.findDOMNode(this).parentNode);
  },
  close() {
    $(ReactDOM.findDOMNode(this)).modal('hide');
    this.rejectResult();
  },
  closeOnLinkClick(e) {
    // close dialogs on click of any internal link inside it
    if (e.target.tagName === 'A' && !e.target.target && e.target.href) this.close();
  },
  closeOnEscapeKey(e) {
    if (
      this.props.keyboard !== false &&
      this.props.closeable !== false &&
      e.key === 'Escape'
    ) this.close();
    if (_.isFunction(this.onKeyDown)) this.onKeyDown(e);
  },
  showError(response, message) {
    var props = {error: true};
    props.message = utils.getResponseText(response) || message;
    this.updateProps(props);
  },
  renderImportantLabel() {
    return <span className='label label-danger'>{i18n('common.important')}</span>;
  },
  submitAction() {
    this.state.result.resolve();
    this.close();
  },
  render() {
    var classes = {'modal fade': true};
    classes[this.props.modalClass] = this.props.modalClass;
    return (
      <div
        className={utils.classNames(classes)}
        tabIndex='-1'
        onClick={this.closeOnLinkClick}
        onKeyDown={this.closeOnEscapeKey}
      >
        <div className='modal-dialog'>
          <div className='modal-content'>
            <div className='modal-header'>
              {this.props.closeable !== false &&
                <button type='button' className='close' aria-label='Close' onClick={this.close}>
                  <span aria-hidden='true'>&times;</span>
                </button>
              }
              <h4 className='modal-title'>
                {
                  this.props.title ||
                  this.state.title ||
                  (this.props.error ? i18n('dialog.error_dialog.title') : '')
                }
              </h4>
            </div>
            <div className='modal-body'>
              {this.props.error ?
                <div className='text-error'>
                  {this.props.message || i18n('dialog.error_dialog.server_error')}
                </div>
              : this.renderBody()}
            </div>
            <div className='modal-footer'>
              {this.renderFooter && !this.props.error ?
                this.renderFooter()
              :
                <button className='btn btn-default' onClick={this.close}>
                  {i18n('common.close_button')}
                </button>
              }
            </div>
          </div>
        </div>
      </div>
    );
  }
};

var registrationResponseErrorMixin = {
  showResponseErrors(response, form) {
    var jsonObj;
    var error = '';
    try {
      jsonObj = JSON.parse(response.responseText);
      error = jsonObj.message;
      if (_.isObject(form)) {
        form.validationError = {};
        _.each(jsonObj.errors, (value, name) => {
          form.validationError['credentials.' + name] = value;
        });
      }
    } catch (e) {
      error = i18n('welcome_page.register.connection_error');
    }
    this.setState({error: error});
  }
};

export var ErrorDialog = React.createClass({
  mixins: [dialogMixin],
  getDefaultProps() {
    return {error: true};
  }
});

export var NailgunUnavailabilityDialog = React.createClass({
  mixins: [dialogMixin],
  getDefaultProps() {
    return {
      title: i18n('dialog.nailgun_unavailability.title'),
      modalClass: 'nailgun-unavailability-dialog',
      closeable: false,
      keyboard: false,
      backdrop: false,
      retryDelayIntervals: [5, 10, 15, 20, 30, 60]
    };
  },
  getInitialState() {
    var initialDelay = this.props.retryDelayIntervals[0];
    return {
      currentDelay: initialDelay,
      currentDelayInterval: initialDelay
    };
  },
  componentWillMount() {
    this.startCountdown();
  },
  componentDidMount() {
    $(ReactDOM.findDOMNode(this)).on('shown.bs.modal', () => {
      return $(ReactDOM.findDOMNode(this.refs['retry-button'])).focus();
    });
  },
  startCountdown() {
    this.activeTimeout = _.delay(this.countdown, 1000);
  },
  stopCountdown() {
    if (this.activeTimeout) clearTimeout(this.activeTimeout);
    delete this.activeTimeout;
  },
  countdown() {
    var {currentDelay} = this.state;
    currentDelay--;
    if (!currentDelay) {
      this.setState({currentDelay, actionInProgress: true});
      this.reinitializeUI();
    } else {
      this.setState({currentDelay});
      this.startCountdown();
    }
  },
  reinitializeUI() {
    app.initialize().then(this.close, () => {
      var {retryDelayIntervals} = this.props;
      var nextDelay = retryDelayIntervals[
        retryDelayIntervals.indexOf(this.state.currentDelayInterval) + 1
      ] || _.last(retryDelayIntervals);
      _.defer(() => this.setState({
        actionInProgress: false,
        currentDelay: nextDelay,
        currentDelayInterval: nextDelay
      }, this.startCountdown));
    });
  },
  retryNow() {
    this.stopCountdown();
    this.setState({
      currentDelay: 0,
      currentDelayInterval: 0,
      actionInProgress: true
    });
    this.reinitializeUI();
  },
  renderBody() {
    return (
      <div>
        <p>
          {i18n('dialog.nailgun_unavailability.unavailability_message')}
          {' '}
          {this.state.currentDelay ?
            i18n(
              'dialog.nailgun_unavailability.retry_delay_message',
              {count: this.state.currentDelay}
            )
          :
            i18n('dialog.nailgun_unavailability.retrying')
          }
        </p>
        <p>
          {i18n('dialog.nailgun_unavailability.unavailability_reasons')}
        </p>
      </div>
    );
  },
  renderFooter() {
    return (
      <button
        ref='retry-button'
        className='btn btn-success'
        onClick={this.retryNow}
        disabled={this.state.actionInProgress}
      >
        {i18n('dialog.nailgun_unavailability.retry_now')}
      </button>
    );
  }
});

export var DiscardNodeChangesDialog = React.createClass({
  mixins: [dialogMixin],
  getDefaultProps() {
    return {
      title: i18n('dialog.discard_changes.title')
    };
  },
  discardNodeChanges() {
    this.setState({actionInProgress: true});
    var nodes = new models.Nodes(this.props.nodes.map((node) => {
      if (node.get('pending_deletion')) {
        return {
          id: node.id,
          pending_deletion: false
        };
      }
      return {
        id: node.id,
        cluster_id: null,
        pending_addition: false,
        pending_roles: []
      };
    }));
    Backbone.sync('update', nodes)
      .then(() => this.props.cluster.fetchRelated('nodes'))
      .done(() => {
        dispatcher
          .trigger('updateNodeStats networkConfigurationUpdated labelsConfigurationUpdated');
        this.state.result.resolve();
        this.close();
      })
      .fail((response) => this.showError(response, i18n('dialog.discard_changes.cant_discard')));
  },
  renderBody() {
    return (
      <div className='text-danger'>
        {this.renderImportantLabel()}
        {i18n('dialog.discard_changes.' + (
          this.props.nodes[0].get('pending_deletion') ? 'discard_deletion' : 'discard_addition'
        ))}
      </div>
    );
  },
  renderFooter() {
    return ([
      <button
        key='cancel'
        className='btn btn-default'
        onClick={this.close}
        disabled={this.state.actionInProgress}
      >
        {i18n('common.cancel_button')}
      </button>,
      <button
        key='discard'
        className='btn btn-danger'
        disabled={this.state.actionInProgress}
        onClick={this.discardNodeChanges}
      >
        {i18n('dialog.discard_changes.discard_button')}
      </button>
    ]);
  }
});

export var DeployChangesDialog = React.createClass({
  mixins: [
    dialogMixin,
    // this is needed to somehow handle the case when
    // verification is in progress and user pressed Deploy
    backboneMixin({
      modelOrCollection(props) {
        return props.cluster.get('tasks');
      },
      renderOn: 'update change:status'
    })
  ],
  getDefaultProps() {
    return {title: i18n('dialog.display_changes.title')};
  },
  ns: 'dialog.display_changes.',
  deployCluster() {
    this.setState({actionInProgress: true});
    dispatcher.trigger('deploymentTasksUpdated');
    var task = new models.Task();
    task.save({}, {url: _.result(this.props.cluster, 'url') + '/changes', type: 'PUT'})
      .done(() => {
        this.close();
        dispatcher.trigger('deploymentTaskStarted');
      })
      .fail(this.showError);
  },
  renderBody() {
    var cluster = this.props.cluster;
    return (
      <div className='display-changes-dialog'>
        {!cluster.needsRedeployment() && _.contains(['new', 'stopped'], cluster.get('status')) &&
          <div>
            <div className='text-warning'>
              <i className='glyphicon glyphicon-warning-sign' />
              <div className='instruction'>
                {i18n('cluster_page.dashboard_tab.locked_settings_alert') + ' '}
              </div>
            </div>
            <div className='text-warning'>
              <i className='glyphicon glyphicon-warning-sign' />
              <div className='instruction'>
                {i18n('cluster_page.dashboard_tab.package_information') + ' '}
                <a
                  target='_blank'
                  href={utils.composeDocumentationLink('operations.html#troubleshooting')}
                >
                  {i18n('cluster_page.dashboard_tab.operations_guide')}
                </a>
                {i18n('cluster_page.dashboard_tab.for_more_information_configuration')}
              </div>
            </div>
          </div>
        }
        <div className='confirmation-question'>
          {i18n(this.ns + 'are_you_sure_deploy')}
        </div>
      </div>
    );
  },
  renderFooter() {
    return ([
      <button
        key='cancel'
        className='btn btn-default'
        onClick={this.close}
        disabled={this.state.actionInProgress}
      >
        {i18n('common.cancel_button')}
      </button>,
      <button key='deploy'
        className='btn start-deployment-btn btn-success'
        disabled={this.state.actionInProgress || this.state.isInvalid}
        onClick={this.deployCluster}
      >{i18n(this.ns + 'deploy')}</button>
    ]);
  }
});

export var ProvisionVMsDialog = React.createClass({
  mixins: [dialogMixin],
  getDefaultProps() {
    return {title: i18n('dialog.provision_vms.title')};
  },
  startProvisioning() {
    this.setState({actionInProgress: true});
    var task = new models.Task();
    task.save({}, {url: _.result(this.props.cluster, 'url') + '/spawn_vms', type: 'PUT'})
      .done(() => {
        this.close();
        dispatcher.trigger('deploymentTaskStarted');
      })
      .fail((response) => {
        this.showError(response, i18n('dialog.provision_vms.provision_vms_error'));
      });
  },
  renderBody() {
    var vmsCount = this.props.cluster.get('nodes').where((node) => {
      return node.get('pending_addition') && node.hasRole('virt');
    }).length;
    return i18n('dialog.provision_vms.text', {count: vmsCount});
  },
  renderFooter() {
    return ([
      <button
        key='cancel'
        className='btn btn-default'
        onClick={this.close}
        disabled={this.state.actionInProgress}
      >
        {i18n('common.cancel_button')}
      </button>,
      <button
        key='provision'
        className='btn btn-success'
        disabled={this.state.actionInProgress}
        onClick={this.startProvisioning}
      >
        {i18n('common.start_button')}
      </button>
    ]);
  }
});

export var StopDeploymentDialog = React.createClass({
  mixins: [dialogMixin],
  getDefaultProps() {
    return {title: i18n('dialog.stop_deployment.title')};
  },
  stopDeployment() {
    this.setState({actionInProgress: true});
    var task = new models.Task();
    task.save({}, {url: _.result(this.props.cluster, 'url') + '/stop_deployment', type: 'PUT'})
      .done(() => {
        this.close();
        dispatcher.trigger('deploymentTaskStarted');
      })
      .fail((response) => {
        this.showError(
          response,
          i18n('dialog.stop_deployment.stop_deployment_error.stop_deployment_warning')
        );
      });
  },
  renderBody() {
    var ns = 'dialog.stop_deployment.';
    return (
      <div className='text-danger'>
        {this.renderImportantLabel()}
        {this.props.cluster.get('nodes').any({status: 'provisioning'}) ?
          <span>
            {i18n(ns + 'provisioning_warning')}
            <br/><br/>
            {i18n(ns + 'redeployment_warning')}
          </span>
        :
          i18n(ns + 'text')
        }
      </div>
    );
  },
  renderFooter() {
    return ([
      <button
        key='cancel'
        className='btn btn-default'
        onClick={this.close}
        disabled={this.state.actionInProgress}
      >
        {i18n('common.cancel_button')}
      </button>,
      <button
        key='deploy'
        className='btn stop-deployment-btn btn-danger'
        disabled={this.state.actionInProgress}
        onClick={this.stopDeployment}
      >
        {i18n('common.stop_button')}
      </button>
    ]);
  }
});

export var RemoveClusterDialog = React.createClass({
  mixins: [dialogMixin],
  getInitialState() {
    return {confirmation: false};
  },
  getDefaultProps() {
    return {title: i18n('dialog.remove_cluster.title')};
  },
  removeCluster() {
    this.setState({actionInProgress: true});
    this.props.cluster
      .destroy({wait: true})
      .then(
        () => {
          this.close();
          dispatcher.trigger('updateNodeStats updateNotifications');
          app.navigate('#clusters', {trigger: true});
        },
        this.showError
      );
  },
  showConfirmationForm() {
    this.setState({confirmation: true});
  },
  getText() {
    var ns = 'dialog.remove_cluster.';
    var runningTask = this.props.cluster.task({active: true});
    if (runningTask) {
      if (runningTask.match({name: 'stop_deployment'})) {
        return i18n(ns + 'stop_deployment_is_running');
      }
      return i18n(ns + 'incomplete_actions_text');
    }
    if (this.props.cluster.get('nodes').length) {
      return i18n(ns + 'node_returned_text');
    }
    return i18n(ns + 'default_text');
  },
  renderBody() {
    var clusterName = this.props.cluster.get('name');
    return (
      <div>
        <div className='text-danger'>
          {this.renderImportantLabel()}
          {this.getText()}
        </div>
        {this.state.confirmation &&
          <div className='confirm-deletion-form'>
            {i18n('dialog.remove_cluster.enter_environment_name', {name: clusterName})}
            <Input
              type='text'
              disabled={this.state.actionInProgress}
              onChange={(name, value) => this.setState({confirmationError: value !== clusterName})}
              onPaste={(e) => e.preventDefault()}
              autoFocus
            />
          </div>
        }
      </div>
    );
  },
  renderFooter() {
    return ([
      <button
        key='cancel'
        className='btn btn-default'
        onClick={this.close}
        disabled={this.state.actionInProgress}
      >
        {i18n('common.cancel_button')}
      </button>,
      <button
        key='remove'
        className='btn btn-danger remove-cluster-btn'
        disabled={this.state.actionInProgress || this.state.confirmation &&
         _.isUndefined(this.state.confirmationError) || this.state.confirmationError}
        onClick={this.props.cluster.get('status') === 'new' || this.state.confirmation ?
         this.removeCluster : this.showConfirmationForm}
      >
        {i18n('common.delete_button')}
      </button>
    ]);
  }
});

// FIXME: the code below neeeds deduplication
// extra confirmation logic should be moved out to dialog mixin
export var ResetEnvironmentDialog = React.createClass({
  mixins: [dialogMixin],
  getInitialState() {
    return {confirmation: false};
  },
  getDefaultProps() {
    return {title: i18n('dialog.reset_environment.title')};
  },
  resetEnvironment() {
    this.setState({actionInProgress: true});
    dispatcher.trigger('deploymentTasksUpdated');
    var task = new models.Task();
    task.save({}, {url: _.result(this.props.cluster, 'url') + '/reset', type: 'PUT'})
      .done(() => {
        this.close();
        dispatcher.trigger('deploymentTaskStarted');
      })
      .fail(this.showError);
  },
  renderBody() {
    var clusterName = this.props.cluster.get('name');
    return (
      <div>
        <div className='text-danger'>
          {this.renderImportantLabel()}
          {i18n('dialog.reset_environment.text')}
        </div>
        {this.state.confirmation &&
          <div className='confirm-reset-form'>
            {i18n('dialog.reset_environment.enter_environment_name', {name: clusterName})}
            <Input
              type='text'
              name='name'
              disabled={this.state.actionInProgress}
              onChange={(name, value) => {
                this.setState({confirmationError: value !== clusterName});
              }}
              onPaste={(e) => e.preventDefault()}
              autoFocus
            />
          </div>
        }
      </div>
    );
  },
  showConfirmationForm() {
    this.setState({confirmation: true});
  },
  renderFooter() {
    return ([
      <button
        key='cancel'
        className='btn btn-default'
        disabled={this.state.actionInProgress}
        onClick={this.close}
      >
        {i18n('common.cancel_button')}
      </button>,
      <button
        key='reset'
        className='btn btn-danger reset-environment-btn'
        disabled={this.state.actionInProgress || this.state.confirmation &&
         _.isUndefined(this.state.confirmationError) || this.state.confirmationError}
        onClick={this.state.confirmation ? this.resetEnvironment : this.showConfirmationForm}
      >
        {i18n('common.reset_button')}
      </button>
    ]);
  }
});

export var ShowNodeInfoDialog = React.createClass({
  mixins: [
    dialogMixin,
    backboneMixin('node'),
    renamingMixin('hostname')
  ],
  getDefaultProps() {
    return {modalClass: 'always-show-scrollbar'};
  },
  getInitialState() {
    return {
      title: i18n('dialog.show_node.default_dialog_title'),
      VMsConf: null,
      VMsConfValidationError: null,
      hostnameChangingError: null
    };
  },
  goToConfigurationScreen(url) {
    this.close();
    app.navigate(
      '#cluster/' + this.props.node.get('cluster') + '/nodes/' + url + '/' +
        utils.serializeTabOptions({nodes: this.props.node.id}),
      {trigger: true}
    );
  },
  showSummary(meta, group) {
    var summary = '';
    try {
      switch (group) {
        case 'system':
          summary = (meta.system.manufacturer || '') + ' ' + (meta.system.product || '');
          break;
        case 'memory':
          if (_.isArray(meta.memory.devices) && meta.memory.devices.length) {
            var sizes = _.countBy(_.pluck(meta.memory.devices, 'size'), utils.showMemorySize);
            summary = _.map(_.keys(sizes).sort(), (size) => sizes[size] + ' x ' + size).join(', ');
            summary += ', ' + utils.showMemorySize(meta.memory.total) + ' ' +
              i18n('dialog.show_node.total');
          } else {
            summary = utils.showMemorySize(meta.memory.total) + ' ' +
              i18n('dialog.show_node.total');
          }
          break;
        case 'disks':
          summary = meta.disks.length + ' ';
          summary += i18n('dialog.show_node.drive', {count: meta.disks.length});
          summary += ', ' + utils.showDiskSize(_.reduce(_.pluck(meta.disks, 'size'), (sum, n) =>
            sum + n, 0)) + ' ' + i18n('dialog.show_node.total');
          break;
        case 'cpu':
          var frequencies = _.countBy(_.pluck(meta.cpu.spec, 'frequency'), utils.showFrequency);
          summary = _.map(_.keys(frequencies).sort(), (frequency) => frequencies[frequency] +
          ' x ' + frequency).join(', ');
          break;
        case 'interfaces':
          var bandwidths = _.countBy(_.pluck(meta.interfaces, 'current_speed'),
            utils.showBandwidth);
          summary = _.map(_.keys(bandwidths).sort(), (bandwidth) => bandwidths[bandwidth] +
          ' x ' + bandwidth).join(', ');
          break;
      }
    } catch (ignore) {}
    return summary;
  },
  showPropertyName(propertyName) {
    return String(propertyName).replace(/_/g, ' ');
  },
  showPropertyValue(group, name, value) {
    var valueFormatters = {
      size: group === 'disks' ?
          utils.showDiskSize
        :
          group === 'memory' ? utils.showMemorySize : utils.showSize,
      frequency: utils.showFrequency,
      max_speed: utils.showBandwidth,
      current_speed: utils.showBandwidth,
      maximum_capacity: group === 'memory' ? utils.showMemorySize : _.identity,
      total: group === 'memory' ? utils.showMemorySize : _.identity
    };
    try {
      value = valueFormatters[name](value);
    } catch (ignore) {}
    if (_.isBoolean(value)) return value ? i18n('common.true') : i18n('common.false');
    return !_.isNumber(value) && _.isEmpty(value) ? '\u00A0' : value;
  },
  componentDidUpdate() {
    this.assignAccordionEvents();
  },
  componentDidMount() {
    this.assignAccordionEvents();
    this.setDialogTitle();
    if (this.props.node.get('pending_addition') && this.props.node.hasRole('virt')) {
      var VMsConfModel = new models.BaseModel();
      VMsConfModel.url = _.result(this.props.node, 'url') + '/vms_conf';
      this.updateProps({VMsConfModel: VMsConfModel});
      this.setState({actionInProgress: true});
      VMsConfModel.fetch()
        .always(() => {
          this.setState({
            actionInProgress: false,
            VMsConf: JSON.stringify(VMsConfModel.get('vms_conf'))
          });
        });
    }
  },
  setDialogTitle() {
    var name = this.props.node && this.props.node.get('name');
    if (name && name !== this.state.title) this.setState({title: name});
  },
  assignAccordionEvents() {
    $('.panel-collapse', ReactDOM.findDOMNode(this))
      .on('show.bs.collapse', (e) => $(e.currentTarget).siblings('.panel-heading').find('i')
        .removeClass('glyphicon-plus').addClass('glyphicon-minus'))
      .on('hide.bs.collapse', (e) => $(e.currentTarget).siblings('.panel-heading').find('i')
        .removeClass('glyphicon-minus').addClass('glyphicon-plus'))
      .on('hidden.bs.collapse', (e) => e.stopPropagation());
  },
  toggle(groupIndex) {
    $(ReactDOM.findDOMNode(this.refs['togglable_' + groupIndex])).collapse('toggle');
  },
  onVMsConfChange() {
    this.setState({VMsConfValidationError: null});
  },
  saveVMsConf() {
    var parsedVMsConf;
    try {
      parsedVMsConf = JSON.parse(this.refs['vms-config'].getInputDOMNode().value);
    } catch (e) {
      this.setState({VMsConfValidationError: i18n('node_details.invalid_vms_conf_msg')});
    }
    if (parsedVMsConf) {
      this.setState({actionInProgress: true});
      this.props.VMsConfModel.save({vms_conf: parsedVMsConf}, {method: 'PUT'})
        .fail((response) => {
          this.setState({VMsConfValidationError: utils.getResponseText(response)});
        })
        .always(() => {
          this.setState({actionInProgress: false});
        });
    }
  },
  startHostnameRenaming(e) {
    this.setState({hostnameChangingError: null});
    this.startRenaming(e);
  },
  onHostnameInputKeydown(e) {
    this.setState({hostnameChangingError: null});
    if (e.key === 'Enter') {
      this.setState({actionInProgress: true});
      var hostname = _.trim(this.refs.hostname.getInputDOMNode().value);
      (hostname !== this.props.node.get('hostname') ?
        this.props.node.save({hostname: hostname}, {patch: true, wait: true}) :
        $.Deferred().resolve()
      )
      .fail((response) => {
        this.setState({
          hostnameChangingError: utils.getResponseText(response),
          actionInProgress: false
        });
        this.refs.hostname.getInputDOMNode().focus();
      })
      .done(this.endRenaming);
    } else if (e.key === 'Escape') {
      this.endRenaming();
      e.stopPropagation();
      ReactDOM.findDOMNode(this).focus();
    }
  },
  renderNodeSummary() {
    var {cluster, node, nodeNetworkGroup} = this.props;
    return (
      <div className='node-summary'>
        {node.get('cluster') &&
          <div><strong>{i18n('dialog.show_node.cluster')}: </strong>
            {cluster.get('name')}
          </div>
        }
        <div><strong>{i18n('dialog.show_node.manufacturer_label')}: </strong>
          {node.get('manufacturer') || i18n('common.not_available')}
        </div>
        {nodeNetworkGroup &&
          <div>
            <strong>{i18n('dialog.show_node.node_network_group')}: </strong>
            {nodeNetworkGroup.get('name')}
          </div>
        }
        <div><strong>{i18n('dialog.show_node.mac_address_label')}: </strong>
          {node.get('mac') || i18n('common.not_available')}
        </div>
        <div><strong>{i18n('dialog.show_node.fqdn_label')}: </strong>
          {
            (node.get('meta').system || {}).fqdn ||
            node.get('fqdn') ||
            i18n('common.not_available')
          }
        </div>
        <div className='change-hostname'>
          <strong>{i18n('dialog.show_node.hostname_label')}: </strong>
          {this.state.isRenaming ?
            <Input
              ref='hostname'
              type='text'
              defaultValue={node.get('hostname')}
              inputClassName={'input-sm'}
              error={this.state.hostnameChangingError}
              disabled={this.state.actionInProgress}
              onKeyDown={this.onHostnameInputKeydown}
              selectOnFocus
              autoFocus
            />
          :
            <span>
              <span className='node-hostname'>
                {node.get('hostname') || i18n('common.not_available')}
              </span>
              {(node.get('pending_addition') || !node.get('cluster')) &&
                <button
                  className='btn-link glyphicon glyphicon-pencil'
                  onClick={this.startHostnameRenaming}
                />
              }
            </span>
          }
        </div>
      </div>
    );
  },
  renderNodeHardware() {
    var {node} = this.props;
    var meta = node.get('meta');

    var groupOrder = ['system', 'cpu', 'memory', 'disks', 'interfaces'];
    var groups = _.sortBy(_.keys(meta), (group) => _.indexOf(groupOrder, group));
    if (this.state.VMsConf) groups.push('config');

    var sortOrder = {
      disks: ['name', 'model', 'size'],
      interfaces: ['name', 'mac', 'state', 'ip', 'netmask', 'current_speed', 'max_speed',
        'driver', 'bus_info']
    };

    return (
      <div className='panel-group' id='accordion' role='tablist' aria-multiselectable='true'>
        {_.map(groups, (group, groupIndex) => {
          var groupEntries = meta[group];
          if (group === 'interfaces' || group === 'disks') {
            groupEntries = _.sortBy(groupEntries, 'name');
          }
          var subEntries = _.isPlainObject(groupEntries) ?
            _.find(_.values(groupEntries), _.isArray) : [];

          return (
            <div className='panel panel-default' key={group}>
              <div
                className='panel-heading'
                role='tab'
                id={'heading' + group}
                onClick={this.toggle.bind(this, groupIndex)}
              >
                <div className='panel-title'>
                  <div
                    data-parent='#accordion'
                    aria-expanded='true'
                    aria-controls={'body' + group}
                  >
                    <strong>{i18n('node_details.' + group, {defaultValue: group})}</strong>
                    {this.showSummary(meta, group)}
                    <i className='glyphicon glyphicon-plus pull-right' />
                  </div>
                </div>
              </div>
              <div
                className='panel-collapse collapse'
                role='tabpanel'
                aria-labelledby={'heading' + group}
                ref={'togglable_' + groupIndex}
              >
                <div className='panel-body enable-selection'>
                  {_.isArray(groupEntries) &&
                    <div>
                      {_.map(groupEntries, (entry, entryIndex) => {
                        return (
                          <div className='nested-object' key={'entry_' + groupIndex + entryIndex}>
                            {_.map(utils.sortEntryProperties(entry, sortOrder[group]),
                              (propertyName) => {
                                if (
                                  !_.isPlainObject(entry[propertyName]) &&
                                  !_.isArray(entry[propertyName])
                                ) {
                                  return this.renderNodeInfo(
                                    propertyName,
                                    this.showPropertyValue(group, propertyName, entry[propertyName])
                                  );
                                }
                              }
                            )}
                          </div>
                        );
                      })}
                    </div>
                  }
                  {_.isPlainObject(groupEntries) &&
                    <div>
                      {_.map(groupEntries, (propertyValue, propertyName) => {
                        if (
                          !_.isPlainObject(propertyValue) &&
                          !_.isArray(propertyValue) &&
                          !_.isNumber(propertyName)
                        ) {
                          return this.renderNodeInfo(
                            propertyName,
                            this.showPropertyValue(group, propertyName, propertyValue)
                          );
                        }
                      })}
                      {!_.isEmpty(subEntries) &&
                        <div>
                          {_.map(subEntries, (subentry, subentrysIndex) => {
                            return (
                              <div
                                className='nested-object'
                                key={'subentries_' + groupIndex + subentrysIndex}
                              >
                                {_.map(utils.sortEntryProperties(subentry), (propertyName) => {
                                  return this.renderNodeInfo(
                                    propertyName,
                                    this.showPropertyValue(
                                      group, propertyName, subentry[propertyName]
                                    )
                                  );
                                })}
                              </div>
                            );
                          })}
                        </div>
                      }
                    </div>
                  }
                  {
                    !_.isPlainObject(groupEntries) &&
                    !_.isArray(groupEntries) &&
                    !_.isUndefined(groupEntries) &&
                      <div>{groupEntries}</div>
                  }
                  {group === 'config' &&
                    <div className='vms-config'>
                      <Input
                        ref='vms-config'
                        type='textarea'
                        label={i18n('node_details.vms_config_msg')}
                        error={this.state.VMsConfValidationError}
                        onChange={this.onVMsConfChange}
                        defaultValue={this.state.VMsConf}
                      />
                      <button
                        className='btn btn-success'
                        onClick={this.saveVMsConf}
                        disabled={this.state.VMsConfValidationError ||
                          this.state.actionInProgress}
                      >
                        {i18n('common.save_settings_button')}
                      </button>
                    </div>
                  }
                </div>
              </div>
            </div>
          );
        })}
      </div>
    );
  },
  renderBody() {
    if (!this.props.node.get('meta')) return <ProgressBar />;
    return (
      <div className='node-details-popup'>
        <div className='row'>
          <div className='col-xs-5'><div className='node-image-outline' /></div>
          <div className='col-xs-7'>{this.renderNodeSummary()}</div>
        </div>
        {this.renderNodeHardware()}
      </div>
    );
  },
  renderFooter() {
    return (
      <div>
        {this.props.renderActionButtons && this.props.node.get('cluster') &&
          <div className='btn-group' role='group'>
            <button
              className='btn btn-default btn-edit-disks'
              onClick={_.partial(this.goToConfigurationScreen, 'disks')}
            >
              {i18n('dialog.show_node.disk_configuration' +
                (this.props.node.areDisksConfigurable() ? '_action' : ''))}
            </button>
            <button
              className='btn btn-default btn-edit-networks'
              onClick={_.partial(this.goToConfigurationScreen, 'interfaces')}
            >
              {i18n('dialog.show_node.network_configuration' +
                (this.props.node.areInterfacesConfigurable() ? '_action' : ''))}
            </button>
          </div>
        }
        <div className='btn-group' role='group'>
          <button
            className='btn btn-default'
            onClick={this.close}
          >
            {i18n('common.close_button')}
          </button>
        </div>
      </div>
    );
  },
  renderNodeInfo(name, value) {
    return (
      <div key={name + value} className='node-details-row'>
        <label>
          {i18n('dialog.show_node.' + name, {defaultValue: this.showPropertyName(name)})}
        </label>
        {value}
      </div>
    );
  }
});

export var DiscardSettingsChangesDialog = React.createClass({
  mixins: [dialogMixin],
  getDefaultProps() {
    return {title: i18n('dialog.dismiss_settings.title')};
  },
  proceedWith(method) {
    this.setState({actionInProgress: true});
    $.when(method ? method() : $.Deferred().resolve())
      .done(this.state.result.resolve)
      .done(this.close)
      .fail(_.partial(this.showError, null, i18n('dialog.dismiss_settings.saving_failed_message')));
  },
  discard() {
    this.proceedWith(this.props.revertChanges);
  },
  save() {
    this.proceedWith(this.props.applyChanges);
  },
  getMessage() {
    if (this.props.isDiscardingPossible === false) return 'no_discard_message';
    if (this.props.isSavingPossible === false) return 'no_saving_message';
    return 'default_message';
  },
  renderBody() {
    return (
      <div className='text-danger dismiss-settings-dialog'>
        {this.renderImportantLabel()}
        {i18n('dialog.dismiss_settings.' + this.getMessage())}
      </div>
    );
  },
  renderFooter() {
    var buttons = [
      <button
        key='stay'
        className='btn btn-default'
        onClick={this.close}
      >
        {i18n('dialog.dismiss_settings.stay_button')}
      </button>,
      <button
        key='leave'
        className='btn btn-danger proceed-btn'
        onClick={this.discard}
        disabled={this.state.actionInProgress || this.props.isDiscardingPossible === false}
      >
        {i18n('dialog.dismiss_settings.leave_button')}
      </button>,
      <button
        key='save'
        className='btn btn-success'
        onClick={this.save}
        disabled={this.state.actionInProgress || this.props.isSavingPossible === false}
      >
        {i18n('dialog.dismiss_settings.apply_and_proceed_button')}
      </button>
    ];
    return buttons;
  }
});

export var RemoveOfflineNodeDialog = React.createClass({
  mixins: [dialogMixin],
  getDefaultProps() {
    return {
      title: i18n('dialog.remove_node.title'),
      defaultMessage: i18n('dialog.remove_node.default_message')
    };
  },
  renderBody() {
    return (
      <div className='text-danger'>
        {this.renderImportantLabel()}
        {this.props.defaultMessage}
      </div>
    );
  },
  renderFooter() {
    return [
      <button key='close' className='btn btn-default' onClick={this.close}>
        {i18n('common.cancel_button')}
      </button>,
      <button key='remove' className='btn btn-danger btn-delete' onClick={this.submitAction}>
        {i18n('cluster_page.nodes_tab.node.remove')}
      </button>
    ];
  }
});

export var DeleteNodesDialog = React.createClass({
  mixins: [dialogMixin],
  getDefaultProps() {
    return {title: i18n('dialog.delete_nodes.title')};
  },
  renderBody() {
    var ns = 'dialog.delete_nodes.';
    var notDeployedNodesAmount = this.props.nodes.reject({status: 'ready'}).length;
    var deployedNodesAmount = this.props.nodes.length - notDeployedNodesAmount;
    return (
      <div className='text-danger'>
        {this.renderImportantLabel()}
        {i18n(ns + 'common_message', {count: this.props.nodes.length})}
        <br/>
        {!!notDeployedNodesAmount && i18n(ns + 'not_deployed_nodes_message',
          {count: notDeployedNodesAmount})}
        {' '}
        {!!deployedNodesAmount && i18n(ns + 'deployed_nodes_message', {count: deployedNodesAmount})}
      </div>
    );
  },
  renderFooter() {
    return [
      <button
        key='cancel'
        className='btn btn-default'
        onClick={this.close}>{i18n('common.cancel_button')}
      </button>,
      <button
        key='delete'
        className='btn btn-danger btn-delete'
        onClick={this.deleteNodes} disabled={this.state.actionInProgress}
      >
        {i18n('common.delete_button')}
      </button>
    ];
  },
  deleteNodes() {
    this.setState({actionInProgress: true});
    var nodes = new models.Nodes(this.props.nodes.map((node) => {
      // mark deployed node as pending deletion
      if (node.get('status') === 'ready') {
        return {
          id: node.id,
          pending_deletion: true
        };
      }
      // remove not deployed node from cluster
      return {
        id: node.id,
        cluster_id: null,
        pending_addition: false,
        pending_roles: []
      };
    }));
    Backbone.sync('update', nodes)
      .then(() => {
        return this.props.cluster.fetchRelated('nodes');
      })
      .done(() => {
        dispatcher.trigger('updateNodeStats networkConfigurationUpdated ' +
          'labelsConfigurationUpdated');
        this.state.result.resolve();
        this.close();
      })
      .fail((response) => {
        this.showError(response, i18n('cluster_page.nodes_tab.node_deletion_error.' +
          'node_deletion_warning'));
      });
  }
});

export var ChangePasswordDialog = React.createClass({
  mixins: [
    dialogMixin,
    LinkedStateMixin
  ],
  getDefaultProps() {
    return {
      title: i18n('dialog.change_password.title'),
      modalClass: 'change-password'
    };
  },
  getInitialState() {
    return {
      currentPassword: '',
      confirmationPassword: '',
      newPassword: '',
      validationError: false
    };
  },
  getError(name) {
    var ns = 'dialog.change_password.';
    if (name === 'currentPassword' && this.state.validationError) {
      return i18n(ns + 'wrong_current_password');
    }
    if (this.state.newPassword !== this.state.confirmationPassword) {
      if (name === 'confirmationPassword') return i18n(ns + 'new_password_mismatch');
      if (name === 'newPassword') return '';
    }
    return null;
  },
  renderBody() {
    var ns = 'dialog.change_password.';
    var fields = ['currentPassword', 'newPassword', 'confirmationPassword'];
    var translationKeys = ['current_password', 'new_password', 'confirm_new_password'];
    return (
      <div className='forms-box'>
        {_.map(fields, (name, index) => {
          return <Input
            key={name}
            name={name}
            ref={name}
            type='password'
            label={i18n(ns + translationKeys[index])}
            maxLength='50'
            onChange={this.handleChange.bind(this, (name === 'currentPassword'))}
            onKeyDown={this.handleKeyDown}
            disabled={this.state.actionInProgress}
            toggleable={name === 'currentPassword'}
            defaultValue={this.state[name]}
            error={this.getError(name)}
          />;
        })}
      </div>
    );
  },
  renderFooter() {
    return [
      <button
        key='cancel'
        className='btn btn-default'
        onClick={this.close}
        disabled={this.state.actionInProgress}
      >
        {i18n('common.cancel_button')}
      </button>,
      <button key='apply' className='btn btn-success' onClick={this.changePassword}
        disabled={this.state.actionInProgress || !this.isPasswordChangeAvailable()}>
        {i18n('common.apply_button')}
      </button>
    ];
  },
  isPasswordChangeAvailable() {
    return this.state.newPassword.length && !this.state.validationError &&
      (this.state.newPassword === this.state.confirmationPassword);
  },
  handleKeyDown(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      this.changePassword();
    }
    if (e.key === ' ') {
      e.preventDefault();
      return false;
    }
  },
  handleChange(clearError, name, value) {
    var newState = {};
    newState[name] = value.trim();
    if (clearError) {
      newState.validationError = false;
    }
    this.setState(newState);
  },
  changePassword() {
    if (this.isPasswordChangeAvailable()) {
      var keystoneClient = app.keystoneClient;
      this.setState({actionInProgress: true});
      keystoneClient.changePassword(this.state.currentPassword, this.state.newPassword)
        .done(() => {
          dispatcher.trigger(this.state.newPassword === keystoneClient.DEFAULT_PASSWORD ?
            'showDefaultPasswordWarning' : 'hideDefaultPasswordWarning');
          app.user.set({token: keystoneClient.token});
          this.close();
        })
        .fail(() => {
          this.setState({validationError: true, actionInProgress: false});
          $(this.refs.currentPassword.getInputDOMNode()).focus();
        });
    }
  }
});

export var RegistrationDialog = React.createClass({
  mixins: [
    dialogMixin,
    registrationResponseErrorMixin,
    backboneMixin('registrationForm', 'change invalid')
  ],
  getInitialState() {
    return {
      loading: true
    };
  },
  getDefaultProps() {
    return {
      title: i18n('dialog.registration.title'),
      modalClass: 'registration',
      backdrop: 'static'
    };
  },
  componentDidMount() {
    var registrationForm = this.props.registrationForm;
    registrationForm.fetch()
      .then(null, () => {
        registrationForm.url = registrationForm.nailgunUrl;
        return registrationForm.fetch();
      })
      .fail((response) => {
        this.showResponseErrors(response);
        this.setState({connectionError: true});
      })
      .always(() => {
        this.setState({loading: false});
      });
  },
  onChange(inputName, value) {
    var registrationForm = this.props.registrationForm;
    var name = registrationForm.makePath('credentials', inputName, 'value');
    if (registrationForm.validationError) {
      delete registrationForm.validationError['credentials.' + inputName];
    }
    registrationForm.set(name, value);
  },
  composeOptions(values) {
    return _.map(values, (value, index) => {
      return (
        <option key={index} value={value.data}>
          {value.label}
        </option>
      );
    });
  },
  getAgreementLink(link) {
    return (
      <span>
        {i18n('dialog.registration.i_agree')}
        <a href={link} target='_blank'>
          {i18n('dialog.registration.terms_and_conditions')}
        </a>
      </span>);
  },
  validateRegistrationForm() {
    var registrationForm = this.props.registrationForm;
    var isValid = registrationForm.isValid();
    if (!registrationForm.attributes.credentials.agree.value) {
      if (!registrationForm.validationError) registrationForm.validationError = {};
      registrationForm.validationError['credentials.agree'] =
        i18n('dialog.registration.agree_error');
      isValid = false;
    }
    this.setState({
      error: null,
      hideRequiredFieldsNotice: isValid
    });
    if (isValid) this.createAccount();
  },
  createAccount() {
    var registrationForm = this.props.registrationForm;
    this.setState({actionInProgress: true});
    registrationForm.save(registrationForm.attributes, {type: 'POST'})
      .done((response) => {
        var currentAttributes = _.cloneDeep(this.props.settings.attributes);

        var collector = (path) => {
          return (name) => {
            this.props.settings.set(
              this.props.settings.makePath(path, name, 'value'),
              response[name]
            );
          };
        };
        _.each(['company', 'name', 'email'], collector('statistics'));
        _.each(['email', 'password'], collector('tracking'));

        this.props.saveSettings(currentAttributes)
          .done(() => {
            this.props.tracking.set(this.props.settings.attributes);
            this.props.setConnected();
            this.close();
          });
      })
      .fail((response) => {
        this.setState({actionInProgress: false});
        this.showResponseErrors(response, registrationForm);
      });
  },
  checkCountry() {
    var country = this.props.registrationForm.attributes.credentials.country.value;
    return !(country === 'Canada' || country === 'United States' || country === 'us');
  },
  renderBody() {
    var registrationForm = this.props.registrationForm;
    if (this.state.loading) return <ProgressBar />;
    var fieldsList = registrationForm.attributes.credentials;
    var actionInProgress = this.state.actionInProgress;
    var error = this.state.error;
    var sortedFields = _.chain(_.keys(fieldsList))
      .without('metadata')
      .sortBy((inputName) => fieldsList[inputName].weight)
      .value();
    var halfWidthField = ['first_name', 'last_name', 'company', 'phone', 'country', 'region'];
    return (
      <div className='registration-form tracking'>
        {actionInProgress && <ProgressBar />}
        {error &&
          <div className='text-danger'>
            <i className='glyphicon glyphicon-danger-sign' />
            {error}
          </div>
        }
        {!this.state.hideRequiredFieldsNotice && !this.state.connectionError &&
          <div className='alert alert-warning'>
            {i18n('welcome_page.register.required_fields')}
          </div>
        }
        <form className='form-inline row'>
          {_.map(sortedFields, (inputName) => {
            var input = fieldsList[inputName];
            var path = 'credentials.' + inputName;
            var inputError = (registrationForm.validationError || {})[path];
            var classes = {
              'col-md-12': !_.contains(halfWidthField, inputName),
              'col-md-6': _.contains(halfWidthField, inputName),
              'text-center': inputName === 'agree'
            };
            return <Input
              ref={inputName}
              key={inputName}
              name={inputName}
              label={inputName !== 'agree' ? input.label : this.getAgreementLink(input.description)}
              {... _.pick(input, 'type', 'value')}
              children={input.type === 'select' && this.composeOptions(input.values)}
              wrapperClassName={utils.classNames(classes)}
              onChange={this.onChange}
              error={inputError}
              disabled={actionInProgress || (inputName === 'region' && this.checkCountry())}
              description={inputName !== 'agree' && input.description}
              maxLength='50'
            />;
          })}
        </form>
      </div>
    );
  },
  renderFooter() {
    var buttons = [
      <button key='cancel' className='btn btn-default' onClick={this.close}>
        {i18n('common.cancel_button')}
      </button>
    ];
    if (!this.state.loading) {
      buttons.push(
        <button
          key='apply'
          className='btn btn-success'
          disabled={this.state.actionInProgress || this.state.connectionError}
          onClick={this.validateRegistrationForm}
        >
          {i18n('welcome_page.register.create_account')}
        </button>
      );
    }
    return buttons;
  }
});

export var RetrievePasswordDialog = React.createClass({
  mixins: [
    dialogMixin,
    registrationResponseErrorMixin,
    backboneMixin('remoteRetrievePasswordForm', 'change invalid')
  ],
  getInitialState() {
    return {loading: true};
  },
  getDefaultProps() {
    return {
      title: i18n('dialog.retrieve_password.title'),
      modalClass: 'retrieve-password-form'
    };
  },
  componentDidMount() {
    var remoteRetrievePasswordForm = this.props.remoteRetrievePasswordForm;
    remoteRetrievePasswordForm.fetch()
      .then(null, () => {
        remoteRetrievePasswordForm.url = remoteRetrievePasswordForm.nailgunUrl;
        return remoteRetrievePasswordForm.fetch();
      })
      .fail((response) => {
        this.showResponseErrors(response);
        this.setState({connectionError: true});
      })
      .always(() => {
        this.setState({loading: false});
      });
  },
  onChange(inputName, value) {
    var remoteRetrievePasswordForm = this.props.remoteRetrievePasswordForm;
    if (remoteRetrievePasswordForm.validationError) {
      delete remoteRetrievePasswordForm.validationError['credentials.email'];
    }
    remoteRetrievePasswordForm.set('credentials.email.value', value);
  },
  retrievePassword() {
    var remoteRetrievePasswordForm = this.props.remoteRetrievePasswordForm;
    if (remoteRetrievePasswordForm.isValid()) {
      this.setState({actionInProgress: true});
      remoteRetrievePasswordForm.save()
        .done(this.passwordSent)
        .fail(this.showResponseErrors)
        .always(() => {
          this.setState({actionInProgress: false});
        });
    }
  },
  passwordSent() {
    this.setState({passwordSent: true});
  },
  renderBody() {
    var ns = 'dialog.retrieve_password.';
    var remoteRetrievePasswordForm = this.props.remoteRetrievePasswordForm;
    if (this.state.loading) return <ProgressBar />;
    var error = this.state.error;
    var actionInProgress = this.state.actionInProgress;
    var input = (remoteRetrievePasswordForm.get('credentials') || {}).email;
    var inputError = remoteRetrievePasswordForm ? (remoteRetrievePasswordForm.validationError ||
      {})['credentials.email'] : null;
    return (
      <div className='retrieve-password-content'>
        {!this.state.passwordSent ?
          <div>
            {actionInProgress && <ProgressBar />}
            {error &&
              <div className='text-danger'>
                <i className='glyphicon glyphicon-danger-sign' />
                {error}
              </div>
            }
            {input &&
              <div>
                <p>{i18n(ns + 'submit_email')}</p>
                <Input
                  {... _.pick(input, 'type', 'value', 'description')}
                  onChange={this.onChange}
                  error={inputError}
                  disabled={actionInProgress}
                  placeholder={input.label}
                />
              </div>
            }
          </div>
        :
          <div>
            <div>{i18n(ns + 'done')}</div>
            <div>{i18n(ns + 'check_email')}</div>
          </div>
        }
      </div>
    );
  },
  renderFooter() {
    if (this.state.passwordSent) {
      return [
        <button key='close' className='btn btn-default' onClick={this.close}>
          {i18n('common.close_button')}
        </button>
      ];
    }
    var buttons = [
      <button key='cancel' className='btn btn-default' onClick={this.close}>
        {i18n('common.cancel_button')}
      </button>
    ];
    if (!this.state.loading) {
      buttons.push(
        <button
          key='apply'
          className='btn btn-success'
          disabled={this.state.actionInProgress || this.state.connectionError}
          onClick={this.retrievePassword}
        >
          {i18n('dialog.retrieve_password.send_new_password')}
        </button>
      );
    }
    return buttons;
  }
});

export var CreateNodeNetworkGroupDialog = React.createClass({
  mixins: [dialogMixin],
  getDefaultProps() {
    return {
      title: i18n('cluster_page.network_tab.add_node_network_group'),
      ns: 'cluster_page.network_tab.'
    };
  },
  getInitialState() {
    return {
      error: null
    };
  },
  renderBody() {
    return (
      <div className='node-network-group-creation'>
        <Input
          name='node-network-group-name'
          type='text'
          label={i18n(this.props.ns + 'node_network_group_name')}
          onChange={this.onChange}
          error={this.state.error}
          wrapperClassName='node-group-name'
          inputClassName='node-group-input-name'
          maxLength='50'
          disabled={this.state.actionInProgress}
          autoFocus
        />
      </div>
    );
  },
  renderFooter() {
    return [
      <button
        key='cancel'
        className='btn btn-default'
        onClick={this.close}
        disabled={this.state.actionInProgress}
      >
        {i18n('common.cancel_button')}
      </button>,
      <button
        key='apply'
        className='btn btn-success'
        onClick={this.createNodeNetworkGroup}
        disabled={this.state.actionInProgress || this.state.error}
      >
        {i18n(this.props.ns + 'add')}
      </button>
    ];
  },
  onKeyDown(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      this.createNodeNetworkGroup();
    }
  },
  onChange(name, value) {
    this.setState({
      error: null,
      name: value
    });
  },
  createNodeNetworkGroup() {
    var error = (new models.NodeNetworkGroup()).validate({
      name: this.state.name,
      nodeNetworkGroups: this.props.nodeNetworkGroups
    });
    if (error) {
      this.setState({error: error});
    } else {
      this.setState({actionInProgress: true});
      (new models.NodeNetworkGroup({
        cluster_id: this.props.clusterId,
        name: this.state.name
      }))
        .save(null, {validate: false})
        .then(
          this.submitAction,
          (response) => {
            this.close();
            utils.showErrorDialog({
              title: i18n(this.props.ns + 'node_network_group_creation_error'),
              response: response
            });
          }
        );
    }
  }
});

export var RemoveNodeNetworkGroupDialog = React.createClass({
  mixins: [dialogMixin],
  getDefaultProps() {
    return {title: i18n('dialog.remove_node_network_group.title')};
  },
  renderBody() {
    return (
      <div>
        <div className='text-danger'>
          {this.renderImportantLabel()}
          {this.props.showUnsavedChangesWarning &&
            (i18n('dialog.remove_node_network_group.unsaved_changes_alert') + ' ')
          }
          {i18n('dialog.remove_node_network_group.confirmation')}
        </div>
      </div>
    );
  },
  renderFooter() {
    return ([
      <button key='cancel' className='btn btn-default' onClick={this.close}>
        {i18n('common.cancel_button')}
      </button>,
      <button
        key='remove'
        className='btn btn-danger remove-cluster-btn'
        onClick={this.submitAction}
      >
        {i18n('common.delete_button')}
      </button>
    ]);
  }
});
