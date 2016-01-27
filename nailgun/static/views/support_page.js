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
import models from 'models';
import {backboneMixin, pollingMixin, unsavedChangesMixin} from 'component_mixins';
import statisticsMixin from 'views/statistics_mixin';

var SupportPage = React.createClass({
  mixins: [
    backboneMixin('tasks')
  ],
  statics: {
    title: i18n('support_page.title'),
    navbarActiveElement: 'support',
    breadcrumbsPath: [['home', '#'], 'support'],
    fetchData() {
      var tasks = new models.Tasks();
      return $.when(app.fuelSettings.fetch({cache: true}), tasks.fetch()).then(() => {
        var tracking = new models.FuelSettings(_.cloneDeep(app.fuelSettings.attributes));
        var statistics = new models.FuelSettings(_.cloneDeep(app.fuelSettings.attributes));
        return {
          tasks: tasks,
          settings: app.fuelSettings,
          tracking: tracking,
          statistics: statistics
        };
      });
    }
  },
  render() {
    var elements = [
      <DocumentationLink key='DocumentationLink' />,
      <DiagnosticSnapshot
        key='DiagnosticSnapshot'
        tasks={this.props.tasks}
        task={this.props.tasks.findTask({name: 'dump'})}
      />,
      <CapacityAudit key='CapacityAudit' />
    ];
    if (_.contains(app.version.get('feature_groups'), 'mirantis')) {
      elements.unshift(
        <RegistrationInfo
          key='RegistrationInfo'
          settings={this.props.settings}
          tracking={this.props.tracking}
        />,
        <StatisticsSettings
          key='StatisticsSettings'
          settings={this.props.settings}
          statistics={this.props.statistics}
        />,
        <SupportContacts key='SupportContacts' />
      );
    } else {
      elements.push(<StatisticsSettings
        key='StatisticsSettings'
        settings={this.props.settings}
        statistics={this.props.statistics}
      />);
    }
    return (
      <div className='support-page'>
        <div className='page-title'>
          <h1 className='title'>{i18n('support_page.title')}</h1>
        </div>
        <div className='content-box'>
          {_.reduce(elements, (result, element, index) => {
            if (index) result.push(<hr key={index} />);
            result.push(element);
            return result;
          }, [])}
        </div>
      </div>
    );
  }
});

var SupportPageElement = React.createClass({
  render() {
    return (
      <div className='support-box'>
        <div className={'support-box-cover ' + this.props.className}></div>
        <div className='support-box-content'>
          <h3>{this.props.title}</h3>
          <p>{this.props.text}</p>
          {this.props.children}
        </div>
      </div>
    );
  }
});

var DocumentationLink = React.createClass({
  render() {
    var ns = 'support_page.' + (_.contains(app.version.get('feature_groups'), 'mirantis') ?
        'mirantis' : 'community') + '_';
    return (
      <SupportPageElement
        className='img-documentation-link'
        title={i18n(ns + 'title')}
        text={i18n(ns + 'text')}
      >
        <p>
          <a
            className='btn btn-default documentation-link'
            href='https://www.mirantis.com/openstack-documentation/'
            target='_blank'
          >
            {i18n('support_page.documentation_link')}
          </a>
        </p>
      </SupportPageElement>
    );
  }
});

var RegistrationInfo = React.createClass({
  mixins: [
    statisticsMixin,
    backboneMixin('tracking', 'change invalid')
  ],
  render() {
    if (this.state.isConnected) {
      return (
        <SupportPageElement
          className='img-register-fuel'
          title={i18n('support_page.product_registered_title')}
          text={i18n('support_page.product_registered_content')}
        >
          <div className='registeredData enable-selection'>
            {_.map(['name', 'email', 'company'], (value) => {
              return (
                <div key={value}>
                  <b>{i18n('statistics.setting_labels.' + value)}:</b>
                  {' '}
                  {this.props.tracking.get('statistics')[value].value}
                </div>
              );
            })}
            <div>
              <b>{i18n('support_page.master_node_uuid')}:</b>
              {' '}
              {this.props.tracking.get('master_node_uid')}
            </div>
          </div>
          <p>
            <a
              className='btn btn-default'
              href='https://software.mirantis.com/account/'
              target='_blank'
            >
              {i18n('support_page.manage_account')}
            </a>
          </p>
        </SupportPageElement>
      );
    }
    return (
      <SupportPageElement
        className='img-register-fuel'
        title={i18n('support_page.register_fuel_title')}
        text={i18n('support_page.register_fuel_content')}
      >
        <div className='tracking'>
          {this.renderRegistrationForm(
            this.props.tracking,
            this.state.actionInProgress,
            this.state.error,
            this.state.actionInProgress
          )}
          <p>
            <button
              className='btn btn-default'
              onClick={this.connectToMirantis}
              disabled={this.state.actionInProgress} target='_blank'
            >
              {i18n('support_page.register_fuel_title')}
            </button>
          </p>
        </div>
      </SupportPageElement>
    );
  }
});

var StatisticsSettings = React.createClass({
  mixins: [
    statisticsMixin,
    backboneMixin('statistics'),
    unsavedChangesMixin
  ],
  hasChanges() {
    var initialData = this.props.settings.get('statistics');
    var currentData = this.props.statistics.get('statistics');
    return _.any(this.props.statsCheckboxes, (field) => {
      return !_.isEqual(initialData[field].value, currentData[field].value);
    });
  },
  isSavingPossible() {
    return !this.state.actionInProgress && this.hasChanges();
  },
  applyChanges() {
    return this.isSavingPossible() ? this.prepareStatisticsToSave() : $.Deferred().resolve();
  },
  render() {
    var statistics = this.props.statistics.get('statistics');
    var sortedSettings = _.chain(_.keys(statistics))
      .without('metadata')
      .sortBy((settingName) => statistics[settingName].weight)
      .value();
    return (
      <SupportPageElement
        className='img-statistics'
        title={i18n('support_page.send_statistics_title')}
      >
        <div className='tracking'>
          {this.renderIntro()}
          <div className='statistics-settings'>
            {_.map(sortedSettings, (name) => this.renderInput(name))}
          </div>
          <p>
            <button
              className='btn btn-default'
              disabled={!this.isSavingPossible()}
              onClick={this.prepareStatisticsToSave}
            >
              {i18n('support_page.save_changes')}
            </button>
          </p>
        </div>
      </SupportPageElement>
    );
  }
});

var SupportContacts = React.createClass({
  render() {
    return (
      <SupportPageElement
        className='img-contact-support'
        title={i18n('support_page.contact_support')}
        text={i18n('support_page.contact_text')}
      >
        <p>
          {i18n('support_page.irc_text')}
          {' '}
          <strong>#fuel</strong> on <a href='http://freenode.net' target='_blank'>freenode.net</a>.
        </p>
        <p>
          <a
            className='btn btn-default'
            href='http://support.mirantis.com/requests/new'
            target='_blank'
          >
            {i18n('support_page.contact_support')}
          </a>
        </p>
      </SupportPageElement>
    );
  }
});

var DiagnosticSnapshot = React.createClass({
  mixins: [
    backboneMixin('task'),
    pollingMixin(2)
  ],
  getInitialState() {
    return {generating: this.isDumpTaskActive()};
  },
  shouldDataBeFetched() {
    return this.isDumpTaskActive();
  },
  fetchData() {
    return this.props.task.fetch().done(() => {
      if (!this.isDumpTaskActive()) this.setState({generating: false});
    });
  },
  isDumpTaskActive() {
    return this.props.task && this.props.task.match({active: true});
  },
  downloadLogs() {
    this.setState({generating: true});
    (new models.LogsPackage()).save({}, {method: 'PUT'}).always(() => this.props.tasks.fetch());
  },
  componentDidUpdate() {
    this.startPolling();
  },
  render() {
    var task = this.props.task;
    var generating = this.state.generating;
    return (
      <SupportPageElement
        className='img-download-logs'
        title={i18n('support_page.download_diagnostic_snapshot_text')}
        text={i18n('support_page.log_text')}
      >
        <p className='snapshot'>
          <button className='btn btn-default' disabled={generating} onClick={this.downloadLogs}>
            {generating ? i18n('support_page.gen_logs_snapshot_text') :
              i18n('support_page.gen_diagnostic_snapshot_text')}
          </button>
          {' '}
          {!generating && task &&
            <span className={task.get('status')}>
              {task.match({status: 'ready'}) &&
                <a href={task.get('message')} target='_blank'>
                  <i className='icon-install'></i>
                  <span>{i18n('support_page.diagnostic_snapshot')}</span>
                </a>
              }
              {task.match({status: 'error'}) && task.get('message')}
            </span>
          }
        </p>
      </SupportPageElement>
    );
  }
});

var CapacityAudit = React.createClass({
  render() {
    return (
      <SupportPageElement
        className='img-audit-logs'
        title={i18n('support_page.capacity_audit')}
        text={i18n('support_page.capacity_audit_text')}
      >
        <p>
          <a className='btn btn-default capacity-audit' href='#capacity'>
            {i18n('support_page.view_capacity_audit')}
          </a>
        </p>
      </SupportPageElement>
    );
  }
});

export default SupportPage;
