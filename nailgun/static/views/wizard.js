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
import Backbone from 'backbone';
import models from 'models';
import utils from 'utils';
import {dialogMixin} from 'views/dialogs';
import {Input, ProgressBar} from 'views/controls';

var AVAILABILITY_STATUS_ICONS = {
  compatible: 'glyphicon-ok-sign',
  available: 'glyphicon-info-sign',
  incompatible: 'glyphicon-warning-sign'
};

var ComponentCheckboxGroup = React.createClass({
  hasEnabledComponents() {
    return _.any(this.props.components, (component) => component.get('enabled'));
  },
  render() {
    return (
      <div>
        {
          _.map(this.props.components, (component) => {
            var icon = AVAILABILITY_STATUS_ICONS[component.get('availability')];
            return (
              <Input
                key={component.id}
                type='checkbox'
                name={component.id}
                label={component.get('label')}
                description={component.get('description')}
                value={component.id}
                checked={component.get('enabled')}
                disabled={component.get('disabled')}
                tooltipIcon={icon}
                tooltipText={component.get('warnings')}
                tooltipPlacement='top'
                onChange={this.props.onChange}
              />
            );
          })
        }
      </div>
    );
  }
});

var ComponentRadioGroup = React.createClass({
  getInitialState() {
    var activeComponent = _.find(this.props.components, (component) => component.get('enabled'));
    return {
      value: activeComponent && activeComponent.id
    };
  },
  hasEnabledComponents() {
    return _.any(this.props.components, (component) => component.get('enabled'));
  },
  onChange(name, value) {
    _.each(this.props.components, (component) => {
      this.props.onChange(component.id, component.id === value);
    });
    this.setState({value: value});
  },
  render() {
    return (
      <div>
        {
          _.map(this.props.components, (component) => {
            var icon = AVAILABILITY_STATUS_ICONS[component.get('availability')];
            return (
              <Input
                key={component.id}
                type='radio'
                name={this.props.groupName}
                label={component.get('label')}
                description={component.get('description')}
                value={component.id}
                checked={this.state.value === component.id}
                disabled={component.get('disabled')}
                tooltipPlacement='top'
                tooltipIcon={icon}
                tooltipText={component.get('warnings')}
                onChange={this.onChange}
              />
            );
          })
        }
      </div>
    );
  }
});

var ClusterWizardPanesMixin = {
  componentWillMount() {
    if (this.props.allComponents) {
      this.components = this.props.allComponents.getComponentsByType(
        this.constructor.componentType,
        {sorted: true}
      );
    }
  },
  componentDidMount() {
    $(ReactDOM.findDOMNode(this)).find('input:enabled').first().focus();
  },
  areComponentsMutuallyExclusive(components) {
    if (components.length <= 1) {
      return false;
    }
    var allComponentsExclusive = _.all(components, (component) => {
      var peerIds = _.pluck(_.reject(components, {id: component.id}), 'id');
      var incompatibleIds = _.pluck(_.pluck(component.get('incompatible'), 'component'), 'id');
      // peerIds should be subset of incompatibleIds to have exclusiveness property.
      return peerIds.length === _.intersection(peerIds, incompatibleIds).length;
    });
    return allComponentsExclusive;
  },
  processRestrictions(paneComponents, types, stopList = []) {
    this.processIncompatible(paneComponents, types, stopList);
    this.props.allComponents.processPaneRequires(this.constructor.componentType);
  },
  processCompatible(allComponents, paneComponents, types, stopList = []) {
    // all previously enabled components
    // should be compatible with the current component
    _.each(paneComponents, (component) => {
      // skip already disabled
      if (component.get('disabled')) {
        return;
      }

      // index of compatible elements
      var compatibleComponents = {};
      _.each(component.get('compatible'), (compatible) => {
        compatibleComponents[compatible.component.id] = compatible;
      });

      // scan all components to find enabled
      // and not present in the index
      var isCompatible = true;
      var warnings = [];
      allComponents.each((testedComponent) => {
        var type = testedComponent.get('type');
        var isInStopList = _.find(stopList, (component) => component.id === testedComponent.id);
        if (component.id === testedComponent.id || !_.contains(types, type) || isInStopList) {
          // ignore self or forward compatibilities
          return;
        }
        if (testedComponent.get('enabled') && !compatibleComponents[testedComponent.id]) {
          warnings.push(testedComponent.get('label'));
          isCompatible = false;
        }
      });
      component.set({
        isCompatible: isCompatible,
        warnings: isCompatible ? i18n('dialog.create_cluster_wizard.compatible') :
          i18n('dialog.create_cluster_wizard.incompatible_list') + warnings.join(', '),
        availability: (isCompatible ? 'compatible' : 'available')
      });
    });
  },
  processIncompatible(paneComponents, types, stopList) {
    // disable components that have
    // incompatible components already enabled
    _.each(paneComponents, (component) => {
      var incompatibles = component.get('incompatible') || [];
      var isDisabled = false;
      var warnings = [];
      _.each(incompatibles, (incompatible) => {
        var type = incompatible.component.get('type');
        var isInStopList = _.find(
          stopList,
          (component) => component.id === incompatible.component.id
        );
        if (!_.contains(types, type) || isInStopList) {
          // ignore forward incompatibilities
          return;
        }
        if (incompatible.component.get('enabled')) {
          isDisabled = true;
          warnings.push(incompatible.message);
        }
      });
      component.set({
        disabled: isDisabled,
        warnings: warnings.join(' '),
        enabled: isDisabled ? false : component.get('enabled'),
        availability: 'incompatible'
      });
    });
  },
  selectActiveComponent(components) {
    var active = _.find(components, (component) => component.get('enabled'));
    if (active && !active.get('disabled')) {
      return;
    }
    var newActive = _.find(components, (component) => !component.get('disabled'));
    if (newActive) {
      newActive.set({enabled: true});
    }
    if (active) {
      active.set({enabled: false});
    }
  },
  renderWarnings() {
    if (!this.props.allComponents.validationError) {
      return null;
    }
    return _.map(this.props.allComponents.validationError,
        (warning, index) => <div key={index} className='alert alert-warning'>{warning}</div>);
  }
};

var NameAndRelease = React.createClass({
  mixins: [ClusterWizardPanesMixin],
  statics: {
    paneName: 'NameAndRelease',
    title: i18n('dialog.create_cluster_wizard.name_release.title'),
    hasErrors(wizard) {
      return !!wizard.get('name_error');
    }
  },
  isValid() {
    var wizard = this.props.wizard;
    var [name, cluster, clusters] = [
      wizard.get('name'),
      wizard.get('cluster'),
      wizard.get('clusters')
    ];
    // test cluster name is already taken
    if (clusters.findWhere({name: name})) {
      var error = i18n('dialog.create_cluster_wizard.name_release.existing_environment',
        {name: name});
      wizard.set({name_error: error});
      return false;
    }
    // validate cluster fields
    cluster.isValid();
    if (cluster.validationError && cluster.validationError.name) {
      wizard.set({name_error: cluster.validationError.name});
      return false;
    }
    return true;
  },
  render() {
    var releases = this.props.releases;
    var name = this.props.wizard.get('name');
    var nameError = this.props.wizard.get('name_error');
    var release = this.props.wizard.get('release');

    if (this.props.loading) {
      return null;
    }
    var os = release.get('operating_system');
    var connectivityAlert = i18n(
      'dialog.create_cluster_wizard.name_release.' + os + '_connectivity_alert'
    );
    return (
      <div className='create-cluster-form name-and-release'>
        <Input
          type='text'
          name='name'
          autoComplete='off'
          label={i18n('dialog.create_cluster_wizard.name_release.name')}
          value={name}
          error={nameError}
          onChange={this.props.onChange}
        />
        <Input
          type='select'
          name='release'
          label={i18n('dialog.create_cluster_wizard.name_release.release_label')}
          value={release.id}
          onChange={this.props.onChange}
        >
          {
            releases.map((release) => {
              if (!release.get('is_deployable')) {
                return null;
              }
              return <option key={release.id} value={release.id}>{release.get('name')}</option>;
            })
          }
        </Input>
        <div className='help-block'>
          {connectivityAlert &&
            <div className='alert alert-warning'>{connectivityAlert}</div>
          }
          <div className='release-description'>{release.get('description')}</div>
        </div>
      </div>
    );
  }
});

var Compute = React.createClass({
  mixins: [ClusterWizardPanesMixin],
  statics: {
    paneName: 'Compute',
    componentType: 'hypervisor',
    title: i18n('dialog.create_cluster_wizard.compute.title'),
    vCenterPath: 'hypervisor:vmware',
    vCenterNetworkBackends: ['network:neutron:core:nsx', 'network:neutron:ml2:dvs'],
    hasErrors(wizard) {
      var allComponents = wizard.get('components');
      allComponents.validate(this.componentType);
      if (allComponents.validationError) {
        return true;
      }
      var components = allComponents.getComponentsByType(this.componentType, {sorted: true});
      return !_.any(components, (component) => component.get('enabled'));
    }
  },
  componentWillMount() {
    this.updateRestrictions();
  },
  updateRestrictions() {
    this.processRestrictions(this.components, ['hypervisor']);
  },
  render() {
    var vcenter = this.props.allComponents.findWhere({id: 'hypervisor:vmware'});
    return (
      <div className='wizard-compute-pane'>
        <ComponentCheckboxGroup
          groupName='hypervisor'
          components={this.components}
          onChange={this.props.onChange}
        />
        {vcenter && vcenter.get('invalid') &&
          <div className='alert alert-warning vcenter-locked'>
            <div>
              {i18n('dialog.create_cluster_wizard.compute.vcenter_requires_network_backend')}
            </div>
            <a href='https://www.mirantis.com/products/openstack-drivers-and-plugins/fuel-plugins/'
              target='_blank'>
              {i18n('dialog.create_cluster_wizard.compute.vcenter_plugins_page')}
            </a>
          </div>
        }
        {this.constructor.hasErrors(this.props.wizard) &&
          <div className='alert alert-warning empty-choice'>
            {i18n('dialog.create_cluster_wizard.compute.empty_choice')}
          </div>
        }
        {this.renderWarnings()}
      </div>
    );
  }
});

var Network = React.createClass({
  mixins: [ClusterWizardPanesMixin],
  statics: {
    paneName: 'Network',
    panesForRestrictions: ['hypervisor', 'network'],
    componentType: 'network',
    title: i18n('dialog.create_cluster_wizard.network.title'),
    ml2CorePath: 'network:neutron:core:ml2',
    hasErrors(wizard) {
      var allComponents = wizard.get('components');
      allComponents.validate(this.componentType);
      if (allComponents.validationError) {
        return true;
      }
    }
  },
  componentWillMount() {
    var groups = _.groupBy(this.components,
        (component) => component.isML2Driver() ? 'ml2' : 'monolithic');
    this.monolithic = groups.monolithic;
    this.ml2 = groups.ml2;
    this.updateRestrictions();
  },
  updateRestrictions() {
    this.processRestrictions(this.monolithic, this.constructor.panesForRestrictions);
    this.processCompatible(this.props.allComponents, this.monolithic,
        this.constructor.panesForRestrictions, this.monolithic);
    this.selectActiveComponent(this.monolithic);

    this.processRestrictions(this.ml2, this.constructor.panesForRestrictions);
    this.processCompatible(this.props.allComponents, this.ml2,
        this.constructor.panesForRestrictions);
  },
  onChange(name, value) {
    this.props.onChange(name, value);
    // reset all ml2 drivers if ml2 core unselected
    var component = _.find(this.components, (component) => component.id === name);
    if (!component.isML2Driver() && component.id !== this.constructor.ml2CorePath) {
      _.each(this.components, (component) => {
        if (component.isML2Driver()) {
          component.set({enabled: false});
        }
      });
    }
  },
  renderMonolithicDriverControls() {
    return (
      <ComponentRadioGroup
        groupName='network'
        components={this.monolithic}
        onChange={this.onChange}
      />
    );
  },
  renderML2DriverControls() {
    return (
      <ComponentCheckboxGroup
        groupName='ml2'
        components={this.ml2}
        onChange={this.props.onChange}
      />
    );
  },
  render() {
    return (
      <div className='wizard-network-pane'>
        {this.renderMonolithicDriverControls()}
        <div className='ml2'>
          {this.renderML2DriverControls()}
        </div>
        {this.renderWarnings()}
      </div>
    );
  }
});

var Storage = React.createClass({
  mixins: [ClusterWizardPanesMixin],
  statics: {
    paneName: 'Storage',
    panesForRestrictions: ['hypervisor', 'network', 'storage'],
    componentType: 'storage',
    title: i18n('dialog.create_cluster_wizard.storage.title'),
    hasErrors(wizard) {
      var allComponents = wizard.get('components');
      allComponents.validate(this.componentType);
      if (allComponents.validationError) {
        return true;
      }
    }
  },
  componentWillMount() {
    this.updateRestrictions();
  },
  updateRestrictions() {
    var components = this.components;
    _.each(['block', 'object', 'image', 'ephemeral'], (subtype) => {
      var sectionComponents = _.filter(components,
          (component) => component.get('subtype') === subtype);
      var isRadio = this.areComponentsMutuallyExclusive(sectionComponents);
      this.processRestrictions(sectionComponents,
          this.constructor.panesForRestrictions, isRadio ? sectionComponents : []);
      this.processCompatible(this.props.allComponents, sectionComponents,
          this.constructor.panesForRestrictions, isRadio ? sectionComponents : []);
    });
  },
  renderSection(components, type) {
    var sectionComponents = _.filter(components, (component) => component.get('subtype') === type);
    var isRadio = this.areComponentsMutuallyExclusive(sectionComponents);
    return (
      React.createElement((isRadio ? ComponentRadioGroup : ComponentCheckboxGroup), {
        groupName: type,
        components: sectionComponents,
        onChange: this.props.onChange
      })
    );
  },
  render() {
    return (
      <div className='wizard-storage-pane'>
        <div className='row'>
          <div className='col-xs-6'>
            <h4>{i18n('dialog.create_cluster_wizard.storage.block')}</h4>
            {this.renderSection(this.components, 'block', this.props.onChange)}
          </div>
          <div className='col-xs-6'>
            <h4>{i18n('dialog.create_cluster_wizard.storage.object')}</h4>
            {this.renderSection(this.components, 'object', this.props.onChange)}
          </div>
        </div>
        <div className='row'>
          <div className='col-xs-6'>
            <h4>{i18n('dialog.create_cluster_wizard.storage.image')}</h4>
            {this.renderSection(this.components, 'image', this.props.onChange)}
          </div>
          <div className='col-xs-6'>
            <h4>{i18n('dialog.create_cluster_wizard.storage.ephemeral')}</h4>
            {this.renderSection(this.components, 'ephemeral', this.props.onChange)}
          </div>
        </div>
        {this.renderWarnings()}
      </div>
    );
  }
});

var AdditionalServices = React.createClass({
  mixins: [ClusterWizardPanesMixin],
  statics: {
    paneName: 'AdditionalServices',
    panesForRestrictions: ['hypervisor', 'network', 'storage', 'additional_service'],
    componentType: 'additional_service',
    title: i18n('dialog.create_cluster_wizard.additional.title'),
    hasErrors(wizard) {
      var allComponents = wizard.get('components');
      allComponents.validate(this.componentType);
      if (allComponents.validationError) {
        return true;
      }
    }
  },
  componentWillMount() {
    this.updateRestrictions();
  },
  updateRestrictions() {
    this.processRestrictions(this.components, this.constructor.panesForRestrictions);
    this.processCompatible(
      this.props.allComponents,
      this.components,
      this.constructor.panesForRestrictions
    );
  },
  render() {
    return (
      <div className='wizard-compute-pane'>
        <ComponentCheckboxGroup
          groupName='additionalComponents'
          components={this.components}
          onChange={this.props.onChange}
        />
        {this.renderWarnings()}
      </div>
    );
  }
});

var Finish = React.createClass({
  statics: {
    paneName: 'Finish',
    title: i18n('dialog.create_cluster_wizard.ready.title')
  },
  render() {
    return (
      <p>
        <span>{i18n('dialog.create_cluster_wizard.ready.env_select_deploy')} </span>
        <b>{i18n('dialog.create_cluster_wizard.ready.deploy')} </b>
        <span>{i18n('dialog.create_cluster_wizard.ready.or_make_config_choice')} </span>
        <b>{i18n('dialog.create_cluster_wizard.ready.env')} </b>
        <span>{i18n('dialog.create_cluster_wizard.ready.console')}</span>
      </p>
    );
  }
});

var clusterWizardPanes = [
  NameAndRelease,
  Compute,
  Network,
  Storage,
  AdditionalServices,
  Finish
];

var CreateClusterWizard = React.createClass({
  mixins: [dialogMixin],
  getInitialState() {
    return {
      title: i18n('dialog.create_cluster_wizard.title'),
      loading: true,
      activePaneIndex: 0,
      maxAvailablePaneIndex: 0,
      panes: clusterWizardPanes,
      paneHasErrors: false,
      previousAvailable: true,
      nextAvailable: true,
      createEnabled: false
    };
  },
  componentWillMount() {
    this.stopHandlingKeys = false;

    this.wizard = new Backbone.DeepModel();
    this.settings = new models.Settings();
    this.releases = new models.Releases();
    this.cluster = new models.Cluster();
    this.wizard.set({cluster: this.cluster, clusters: this.props.clusters});
  },
  componentDidMount() {
    this.releases.fetch().done(() => {
      var defaultRelease = this.releases.findWhere({is_deployable: true});
      this.wizard.set('release', defaultRelease.id);
      this.selectRelease(defaultRelease.id);
      this.setState({loading: false});
    });

    this.updateState({activePaneIndex: 0});
  },
  getListOfTypesToRestore(currentIndex, maxIndex) {
    var panesTypes = [];
    _.each(clusterWizardPanes, (pane, paneIndex) => {
      if ((paneIndex <= maxIndex) && (paneIndex > currentIndex) && pane.componentType) {
        panesTypes.push(pane.componentType);
      }
    }, this);
    return panesTypes;
  },
  updateState(nextState) {
    if (this.refs.pane && this.refs.pane.updateRestrictions) {
      this.refs.pane.updateRestrictions();
    }
    var numberOfPanes = this.getEnabledPanes().length;
    var nextActivePaneIndex = _.isNumber(nextState.activePaneIndex) ? nextState.activePaneIndex :
      this.state.activePaneIndex;
    var pane = clusterWizardPanes[nextActivePaneIndex];
    var paneHasErrors = _.isFunction(pane.hasErrors) ? pane.hasErrors(this.wizard) : false;

    var newState = _.merge(nextState, {
      activePaneIndex: nextActivePaneIndex,
      previousEnabled: nextActivePaneIndex > 0,
      nextEnabled: !paneHasErrors,
      nextVisible: (nextActivePaneIndex < numberOfPanes - 1),
      createVisible: nextActivePaneIndex === numberOfPanes - 1,
      paneHasErrors: paneHasErrors
    });
    this.setState(newState);
  },
  getEnabledPanes() {
    return _.reject(this.state.panes, 'hidden');
  },
  getActivePane() {
    var panes = this.getEnabledPanes();
    return panes[this.state.activePaneIndex];
  },
  isCurrentPaneValid() {
    var pane = this.refs.pane;
    if (pane && _.isFunction(pane.isValid) && !pane.isValid()) {
      this.updateState({paneHasErrors: true});
      return false;
    }
    return true;
  },
  prevPane() {
    // check for pane's validation errors
    if (!this.isCurrentPaneValid()) {
      return;
    }

    this.updateState({activePaneIndex: this.state.activePaneIndex - 1});
  },
  nextPane() {
    // check for pane's validation errors
    if (!this.isCurrentPaneValid()) {
      return;
    }

    var nextIndex = this.state.activePaneIndex + 1;
    this.updateState({
      activePaneIndex: nextIndex,
      maxAvailablePaneIndex: _.max([nextIndex, this.state.maxAvailablePaneIndex])
    });
  },
  goToPane(index) {
    if (index > this.state.maxAvailablePaneIndex) {
      return;
    }

    // check for pane's validation errors
    if (!this.isCurrentPaneValid()) {
      return;
    }

    this.updateState({activePaneIndex: index});
  },
  saveCluster() {
    if (this.stopHandlingKeys) {
      return;
    }
    this.stopHandlingKeys = true;
    this.setState({actionInProgress: true});
    var cluster = this.cluster;
    cluster.set({components: this.components});
    var deferred = cluster.save();
    if (deferred) {
      this.updateState({disabled: true});
      deferred
        .done(() => {
          this.props.clusters.add(cluster);
          this.close();
          app.navigate('#cluster/' + this.cluster.id, {trigger: true});
        })
        .fail((response) => {
          this.stopHandlingKeys = false;
          this.setState({actionInProgress: false});
          if (response.status === 409) {
            this.updateState({disabled: false, activePaneIndex: 0});
            cluster.trigger('invalid', cluster, {name: utils.getResponseText(response)});
          } else {
            this.close();
            utils.showErrorDialog({
              response: response,
              title: i18n('dialog.create_cluster_wizard.create_cluster_error.title')
            });
          }
        });
    }
  },
  selectRelease(releaseId) {
    var release = this.releases.findWhere({id: releaseId});
    this.wizard.set({release: release});
    this.cluster.set({release: releaseId});

    // fetch components based on releaseId
    this.setState({loading: true});
    this.components = new models.ComponentsCollection([], {releaseId: releaseId});
    this.wizard.set({components: this.components});
    this.components.fetch().done(() => {
      this.components.invoke('expandWildcards', this.components);
      this.components.invoke('restoreDefaultValue', this.components);
      this.components.invoke('preprocessRequires', this.components);
      this.setState({loading: false});
    });
  },
  onChange(name, value) {
    var maxAvailablePaneIndex = this.state.maxAvailablePaneIndex;
    switch (name) {
      case 'name':
        this.wizard.set('name', value);
        this.cluster.set('name', value);
        this.wizard.unset('name_error');
        break;
      case 'release':
        this.selectRelease(parseInt(value, 10));
        break;
      default:
        maxAvailablePaneIndex = this.state.activePaneIndex;
        var panesToRestore = this.getListOfTypesToRestore(
          this.state.activePaneIndex,
          this.state.maxAvailablePaneIndex
        );
        if (panesToRestore.length > 0) {
          this.components.restoreDefaultValues(panesToRestore);
        }
        var component = this.components.findWhere({id: name});
        component.set({enabled: value});
        break;
    }
    this.updateState({maxAvailablePaneIndex: maxAvailablePaneIndex});
  },
  onKeyDown(e) {
    if (this.state.actionInProgress) {
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();

      if (this.getActivePane().paneName === 'Finish') {
        this.saveCluster();
      } else {
        this.nextPane();
      }
    }
  },
  renderBody() {
    var activeIndex = this.state.activePaneIndex;
    var Pane = this.getActivePane();
    return (
      <div className='wizard-body'>
        <div className='wizard-steps-box'>
          <div className='wizard-steps-nav col-xs-3'>
            <ul className='wizard-step-nav-item nav nav-pills nav-stacked'>
              {
                this.state.panes.map((pane, index) => {
                  var classes = utils.classNames('wizard-step', {
                    disabled: index > this.state.maxAvailablePaneIndex,
                    available: index <= this.state.maxAvailablePaneIndex && index !== activeIndex,
                    active: index === activeIndex
                  });
                  return (
                    <li key={pane.title} role='wizard-step'
                      className={classes}>
                      <a onClick={_.partial(this.goToPane, index)}>{pane.title}</a>
                    </li>
                  );
                })
              }
            </ul>
          </div>
          {!this.components &&
            <div className='pane-content col-xs-9 pane-progress-bar'>
              <ProgressBar/>
            </div>
          }
          {this.components &&
            <div className='pane-content col-xs-9 forms-box access'>
              <Pane
                ref='pane'
                actionInProgress={this.state.actionInProgress}
                loading={this.state.loading}
                onChange={this.onChange}
                releases={this.releases}
                wizard={this.wizard}
                allComponents={this.components}
              />
            </div>
          }
          <div className='clearfix'></div>
        </div>
      </div>
    );
  },
  renderFooter() {
    var actionInProgress = this.state.actionInProgress;
    return (
      <div className='wizard-footer'>
        <button
          className={utils.classNames('btn btn-default pull-left', {disabled: actionInProgress})}
          data-dismiss='modal'
        >
          {i18n('common.cancel_button')}
        </button>
        <button
          className={utils.classNames(
            'btn btn-default prev-pane-btn',
            {disabled: !this.state.previousEnabled || actionInProgress}
          )}
          onClick={this.prevPane}
        >
          <i className='glyphicon glyphicon-arrow-left' aria-hidden='true'></i>
          &nbsp;
          <span>{i18n('dialog.create_cluster_wizard.prev')}</span>
        </button>
        {this.state.nextVisible &&
          <button
            className={utils.classNames(
              'btn btn-default btn-success next-pane-btn',
              {disabled: !this.state.nextEnabled || actionInProgress}
            )}
            onClick={this.nextPane}
          >
            <span>{i18n('dialog.create_cluster_wizard.next')}</span>
            &nbsp;
            <i className='glyphicon glyphicon-arrow-right' aria-hidden='true'></i>
          </button>
        }
        {this.state.createVisible &&
          <button
            className={utils.classNames(
              'btn btn-default btn-success finish-btn',
              {disabled: actionInProgress}
            )}
            onClick={this.saveCluster}
            autoFocus
          >
            {i18n('dialog.create_cluster_wizard.create')}
          </button>
        }
      </div>
    );
  }
});

export default CreateClusterWizard;
