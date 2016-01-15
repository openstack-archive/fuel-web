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
import $ from 'jquery';
import _ from 'underscore';
import i18n from 'i18n';
import Backbone from 'backbone';
import React from 'react';
import utils from 'utils';
import models from 'models';
import {Input} from 'views/controls';
import {backboneMixin, pollingMixin} from 'component_mixins';

var HealthCheckTab = React.createClass({
  mixins: [
    backboneMixin({
      modelOrCollection: (props) => props.cluster.get('tasks'),
      renderOn: 'update change:status'
    }),
    backboneMixin('cluster', 'change:status')
  ],
  statics: {
    fetchData(options) {
      if (!options.cluster.get('ostf')) {
        var ostf = {},
          clusterId = options.cluster.id;
        ostf.testsets = new models.TestSets();
        ostf.testsets.url = _.result(ostf.testsets, 'url') + '/' + clusterId;
        ostf.tests = new models.Tests();
        ostf.tests.url = _.result(ostf.tests, 'url') + '/' + clusterId;
        ostf.testruns = new models.TestRuns();
        ostf.testruns.url = _.result(ostf.testruns, 'url') + '/last/' + clusterId;
        return $.when(ostf.testsets.fetch(), ostf.tests.fetch(), ostf.testruns.fetch()).then(() => {
          options.cluster.set({ostf: ostf});
          return {};
        }, () => $.Deferred().resolve()
        );
      }
      return $.Deferred().resolve();
    }
  },
  render() {
    var ostf = this.props.cluster.get('ostf');
    return (
      <div className='row'>
        <div className='title'>
          {i18n('cluster_page.healthcheck_tab.title')}
        </div>
        <div className='col-xs-12 content-elements'>
          {ostf ?
            <HealthcheckTabContent
              ref='content'
              testsets={ostf.testsets}
              tests={ostf.tests}
              testruns={ostf.testruns}
              cluster={this.props.cluster}
            />
          :
            <div className='alert alert-danger'>
              {i18n('cluster_page.healthcheck_tab.not_available_alert')}
            </div>
          }
        </div>
      </div>
    );
  }
});

var HealthcheckTabContent = React.createClass({
  mixins: [
    backboneMixin('tests', 'update change'),
    backboneMixin('testsets', 'update change:checked'),
    backboneMixin('testruns', 'update change'),
    pollingMixin(3)
  ],
  shouldDataBeFetched() {
    return this.props.testruns.any({status: 'running'});
  },
  fetchData() {
    return this.props.testruns.fetch();
  },
  getInitialState() {
    return {
      actionInProgress: false,
      credentialsVisible: null,
      credentials: _.transform(this.props.cluster.get('settings').get('access'), (result, value, key) => {
        result[key] = value.value;
      })
    };
  },
  isLocked() {
    var cluster = this.props.cluster;
    return cluster.get('status') != 'operational' || !!cluster.task({group: 'deployment', active: true});
  },
  getNumberOfCheckedTests() {
    return this.props.tests.where({checked: true}).length;
  },
  toggleCredentials() {
    this.setState({credentialsVisible: !this.state.credentialsVisible});
  },
  handleSelectAllClick(name, value) {
    this.props.tests.invoke('set', {checked: value});
  },
  handleInputChange(name, value) {
    var credentials = this.state.credentials;
    credentials[name] = value;
    this.setState({credentials: credentials});
  },
  runTests() {
    var testruns = new models.TestRuns(),
      oldTestruns = new models.TestRuns(),
      testsetIds = this.props.testsets.pluck('id');
    this.setState({actionInProgress: true});
    _.each(testsetIds, function(testsetId) {
      var testsToRun = _.pluck(this.props.tests.where({
        testset: testsetId,
        checked: true
      }), 'id');
      if (testsToRun.length) {
        var testrunConfig = {tests: testsToRun},
          addCredentials = (obj) => {
            obj.ostf_os_access_creds = {
              ostf_os_username: this.state.credentials.user,
              ostf_os_tenant_name: this.state.credentials.tenant,
              ostf_os_password: this.state.credentials.password
            };
            return obj;
          };

        if (this.props.testruns.where({testset: testsetId}).length) {
          _.each(this.props.testruns.where({testset: testsetId}), (testrun) => {
            _.extend(testrunConfig, addCredentials({
              id: testrun.id,
              status: 'restarted'
            }));
            oldTestruns.add(new models.TestRun(testrunConfig));
          }, this);
        } else {
          _.extend(testrunConfig, {
            testset: testsetId,
            metadata: addCredentials({
              config: {},
              cluster_id: this.props.cluster.id
            })
          });
          testruns.add(new models.TestRun(testrunConfig));
        }
      }
    }, this);

    var requests = [];
    if (testruns.length) {
      requests.push(Backbone.sync('create', testruns));
    }
    if (oldTestruns.length) {
      requests.push(Backbone.sync('update', oldTestruns));
    }
    $.when(...requests)
      .done(() => {
        this.startPolling(true);
      })
      .fail((response) => {
        utils.showErrorDialog({response: response});
      })
      .always(() => {
        this.setState({actionInProgress: false});
      });
  },
  getActiveTestRuns() {
    return this.props.testruns.where({status: 'running'});
  },
  stopTests() {
    var testruns = new models.TestRuns(this.getActiveTestRuns());
    if (testruns.length) {
      this.setState({actionInProgress: true});
      testruns.invoke('set', {status: 'stopped'});
      testruns.toJSON = function() {
        return this.map((testrun) =>
          _.pick(testrun.attributes, 'id', 'status')
        );
      };
      Backbone.sync('update', testruns).done(() => {
        this.setState({actionInProgress: false});
        this.startPolling(true);
      });
    }
  },
  render() {
    var disabledState = this.isLocked(),
      hasRunningTests = !!this.props.testruns.where({status: 'running'}).length;
    return (
      <div>
        {!disabledState &&
          <div className='healthcheck-controls row well well-sm'>
            <div className='pull-left'>
              <Input
                type='checkbox'
                name='selectAll'
                onChange={this.handleSelectAllClick}
                checked={this.getNumberOfCheckedTests() == this.props.tests.length}
                disabled={hasRunningTests}
                label={i18n('common.select_all')}
                wrapperClassName='select-all'
              />
            </div>
            {hasRunningTests ?
              (<button className='btn btn-danger stop-tests-btn pull-right'
                disabled={this.state.actionInProgress}
                onClick={this.stopTests}
              >
                {i18n('cluster_page.healthcheck_tab.stop_tests_button')}
              </button>)
              :
              (<button className='btn btn-success run-tests-btn pull-right'
                disabled={!this.getNumberOfCheckedTests() || this.state.actionInProgress}
                onClick={this.runTests}
              >
                {i18n('cluster_page.healthcheck_tab.run_tests_button')}
              </button>)
            }
            <button
              className='btn btn-default toggle-credentials pull-right'
              data-toggle='collapse'
              data-target='.credentials'
              onClick={this.toggleCredentials}
              >
              {i18n('cluster_page.healthcheck_tab.provide_credentials')}
            </button>

            <HealthcheckCredentials
              credentials={this.state.credentials}
              onInputChange={this.handleInputChange}
              disabled={hasRunningTests}
            />
          </div>
        }
        <div>
          {(this.props.cluster.get('status') == 'new') &&
            <div className='alert alert-warning'>{i18n('cluster_page.healthcheck_tab.deploy_alert')}</div>
          }
          <div key='testsets'>
            {this.props.testsets.map((testset) => {
              return <TestSet
                key={testset.id}
                testset={testset}
                testrun={this.props.testruns.findWhere({testset: testset.id}) || new models.TestRun({testset: testset.id})}
                tests={new Backbone.Collection(this.props.tests.where({testset: testset.id}))}
                disabled={disabledState || hasRunningTests}
              />;
            })}
          </div>
        </div>
      </div>
    );
  }
});

var HealthcheckCredentials = React.createClass({
  render() {
    var inputFields = ['user', 'password', 'tenant'];
    return (
      <div className='credentials collapse col-xs-12'>
        <div className='forms-box'>
          <div className='alert alert-warning'>
            {i18n('cluster_page.healthcheck_tab.credentials_description')}
          </div>
          {_.map(inputFields, function(name) {
            return (<Input
              key={name}
              type={(name == 'password') ? 'password' : 'text'}
              name={name}
              label={i18n('cluster_page.healthcheck_tab.' + name + '_label')}
              value={this.props.credentials[name]}
              onChange={this.props.onInputChange}
              toggleable={name == 'password'}
              description={i18n('cluster_page.healthcheck_tab.' + name + '_description')}
              disabled={this.props.disabled}
              inputClassName='col-xs-3'
            />);
          }, this)}
        </div>
      </div>
    );
  }
});

var TestSet = React.createClass({
  mixins: [
    backboneMixin('tests'),
    backboneMixin('testset')
  ],
  handleTestSetCheck(name, value) {
    this.props.testset.set('checked', value);
    this.props.tests.invoke('set', {checked: value});
  },
  componentWillUnmount() {
    this.props.tests.invoke('off', 'change:checked', this.updateTestsetCheckbox, this);
  },
  componentWillMount() {
    this.props.tests.invoke('on', 'change:checked', this.updateTestsetCheckbox, this);
  },
  updateTestsetCheckbox() {
    this.props.testset.set('checked', this.props.tests.where({checked: true}).length == this.props.tests.length);
  },
  render() {
    var classes = {
      'table healthcheck-table': true,
      disabled: this.props.disabled
    };
    return (
      <table className={utils.classNames(classes)}>
        <thead>
          <tr>
            <th>
              <Input
                type='checkbox'
                id={'testset-checkbox-' + this.props.testset.id}
                name={this.props.testset.get('name')}
                disabled={this.props.disabled}
                onChange={this.handleTestSetCheck}
                checked={this.props.testset.get('checked')}
              />
            </th>
            <th className='col-xs-7 healthcheck-name'>
              <label htmlFor={'testset-checkbox-' + this.props.testset.id}>
                {this.props.testset.get('name')}
              </label>
            </th>
            <th className='healthcheck-col-duration col-xs-2'>
              {i18n('cluster_page.healthcheck_tab.expected_duration')}
            </th>
            <th className='healthcheck-col-duration col-xs-2'>
              {i18n('cluster_page.healthcheck_tab.actual_duration')}
            </th>
            <th className='healthcheck-col-status col-xs-1'>
              {i18n('cluster_page.healthcheck_tab.status')}
            </th>
          </tr>
        </thead>
        <tbody>
          {this.props.tests.map(function(test) {
            var result = this.props.testrun &&
              _.find(this.props.testrun.get('tests'), {id: test.id});
            var status = result && result.status || 'unknown';
            return <Test
              key={test.id}
              test={test}
              result={result}
              status={status}
              disabled={this.props.disabled}
            />;
          }, this)}
        </tbody>
      </table>
    );
  }
});

var Test = React.createClass({
  mixins: [
    backboneMixin('test')
  ],
  handleTestCheck(name, value) {
    this.props.test.set('checked', value);
  },
  render() {
    var test = this.props.test,
      result = this.props.result,
      description = _.escape(_.trim(test.get('description'))),
      status = this.props.status,
      currentStatusClassName = 'text-center healthcheck-status healthcheck-status-' + status,
      iconClasses = {
        success: 'glyphicon glyphicon-ok text-success',
        failure: 'glyphicon glyphicon-remove text-danger',
        error: 'glyphicon glyphicon-remove text-danger',
        running: 'glyphicon glyphicon-refresh animate-spin',
        wait_running: 'glyphicon glyphicon-time'
      };

    return (
      <tr>
        <td>
          <Input
            type='checkbox'
            id={'test-checkbox-' + test.id}
            name={test.get('name')}
            disabled={this.props.disabled}
            onChange={this.handleTestCheck}
            checked={test.get('checked')}
          />
        </td>
        <td className='healthcheck-name'>
          <label htmlFor={'test-checkbox-' + test.id}>{test.get('name')}</label>
          {_.contains(['failure', 'error', 'skipped'], status) &&
            <div className='text-danger'>
              {(result && result.message) &&
                <div>
                  <b>{result.message}</b>
                </div>
              }
              <div className='well' dangerouslySetInnerHTML={{__html:
                utils.urlify(
                  (result && _.isNumber(result.step)) ?
                    utils.highlightTestStep(description, result.step)
                  :
                    description
                  )
                }}>
              </div>
            </div>
          }
        </td>
        <td className='healthcheck-col-duration'>
          <div className='healthcheck-duration'>{test.get('duration') || ''}</div>
        </td>
        <td className='healthcheck-col-duration'>
          {(status != 'running' && result && _.isNumber(result.taken)) ?
            <div className='healthcheck-duration'>{result.taken.toFixed(1)}</div>
          :
            <div className='healthcheck-status healthcheck-status-unknown'>&mdash;</div>
          }
        </td>
        <td className='healthcheck-col-status'>
          <div className={currentStatusClassName}>
            {iconClasses[status] ? <i className={iconClasses[status]} /> : String.fromCharCode(0x2014)}
          </div>
        </td>
      </tr>
    );
  }
});

export default HealthCheckTab;
