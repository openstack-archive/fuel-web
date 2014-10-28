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
define(
[
    'react',
    'models',
    'utils',
    'jsx!component_mixins',
    'jsx!views/controls'
],
function(React, models, utils, componentMixins, controls) {
    'use strict';

    var HealthCheckTab = React.createClass({
        mixins: [
            React.BackboneMixin({
                modelOrCollection: function(props) {return props.model.get('tasks');},
                renderOn: 'add remove change:status'
            }),
            React.BackboneMixin('cluster', 'change:status')
        ],
        getInitialState: function() {
            var ostf = {},
                clusterId = this.props.model.id;
            ostf.testsets = new models.TestSets();
            ostf.testsets.url = _.result(ostf.testsets, 'url') + '/' + clusterId;
            ostf.tests = new models.Tests();
            ostf.tests.url = _.result(ostf.tests, 'url') + '/' + clusterId;
            ostf.testruns = new models.TestRuns();
            ostf.testruns.url = _.result(ostf.testruns, 'url') + '/last/' + clusterId;
            return {
                ostf: ostf,
                loaded: false,
                loadingFailure: false
            };
        },
        componentDidMount: function() {
            if (!this.props.model.get('ostf')) {
                $.when(
                    this.state.ostf.testsets.fetch(),
                    this.state.ostf.tests.fetch(),
                    this.state.ostf.testruns.fetch()
                )
                .done(_.bind(function() {
                    this.props.model.set({ostf: this.state.ostf});
                    this.setState({loaded: true});
                }, this))
                .fail(_.bind(function() {
                    this.setState({loadingFailure: true});
                }, this));
            } else {
                this.setState({loaded: true});
            }
        },
        render: function() {
            var cluster = this.props.model,
                ostf = cluster.get('ostf') || this.state.ostf;
            return (
                <div className='wrapper'>
                    <h3 className='span6 healthcheck-title'>{$.t('cluster_page.healthcheck_tab.title')}</h3>
                    {this.state.loadingFailure ?
                        <div className='cleared'>
                            <div className='alert error-message alert-error'>
                                {$.t('cluster_page.healthcheck_tab.not_available_alert')}
                            </div>
                        </div>
                    : !this.state.loaded ?
                        <div className='row-fluid'><div className='span12'><controls.ProgressBar /></div></div>
                    :
                        <HealthcheckTabContent
                            ref='content'
                            testsets={ostf.testsets}
                            tests={ostf.tests}
                            testruns={ostf.testruns}
                            cluster={cluster}
                            loaded={this.state.loaded}
                        />
                    }
                </div>
            );
        }
    });

    var HealthcheckTabContent = React.createClass({
        mixins: [
            React.BackboneMixin('tests', 'add remove change'),
            React.BackboneMixin('testsets', 'add remove change:checked'),
            React.BackboneMixin('testruns', 'add remove change'),
            componentMixins.pollingMixin(3)
        ],
        shouldDataBeFetched: function() {
            return !!this.props.testruns.where({status: 'running'}).length;
        },
        fetchData: function() {
            return this.props.testruns.fetch();
        },
        getInitialState: function() {
            return {
                actionInProgress: false,
                credentialsVisible: null,
                credentials: _.transform(this.props.cluster.get('settings').get('access'), function(result, value, key) {result[key] = value.value})
            };
        },
        isLocked: function() {
            var cluster = this.props.cluster;
            return cluster.get('status') == 'new' || !!cluster.task({group: 'deployment', status: 'running'});
        },
        getNumberOfCheckedTests: function() {
            return this.props.tests.where({checked: true}).length;
        },
        toggleCredentials: function() {
            this.setState({credentialsVisible: !this.state.credentialsVisible});
        },
        handleSelectAllClick: function(name, value) {
            this.props.tests.invoke('set', {checked: value});
        },
        handleInputChange: function(name, value) {
            var credentials = this.state.credentials;
            credentials[name] = value;
            this.setState({credentials: credentials});
        },
        runTests: function() {
            var testruns = new models.TestRuns(),
                oldTestruns = new models.TestRuns(),
                selectedTests = this.props.tests.where({checked: true});
            this.setState({actionInProgress: true});
            _.each(selectedTests, function(test) {
                var testsetId = test.get('testset'),
                    testrunConfig = {tests: _.pluck(selectedTests, 'id')},
                    addCredentials = _.bind(function(obj) {
                        obj.ostf_os_access_creds = {
                            ostf_os_username: this.state.credentials.user,
                            ostf_os_tenant_name: this.state.credentials.tenant,
                            ostf_os_password: this.state.credentials.password
                        };
                        return obj;
                    }, this);
                if (this.props.testruns.where({testset: testsetId}).length) {
                    _.each(this.props.testruns.where({testset: testsetId}), function(testrun) {
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
            }, this);
            var requests = [];
            if (testruns.length) {
                requests.push(Backbone.sync('create', testruns));
            }
            if (oldTestruns.length) {
                requests.push(Backbone.sync('update', oldTestruns));
            }
            $.when.apply($, requests)
                .done(_.bind(function() {
                    this.startPolling(true);
                }, this))
                .fail(function() {
                    utils.showErrorDialog();
                })
                .always(_.bind(function() {
                    this.setState({actionInProgress: false});
                }, this));
        },
        getActiveTestRuns: function() {
            return this.props.testruns.where({status: 'running'});
        },
        stopTests: function() {
            var testruns = new models.TestRuns(this.getActiveTestRuns());
            if (testruns.length) {
                this.setState({actionInProgress: true});
                testruns.invoke('set', {status: 'stopped'});
                testruns.toJSON = function() {
                    return this.map(function(testrun) {
                        return _.pick(testrun.attributes, 'id', 'status');
                    });
                };
                Backbone.sync('update', testruns).done(_.bind(function() {
                    this.setState({actionInProgress: false});
                    this.startPolling(true);
                }, this));
            }
        },
        render: function() {
            var disabledState = this.isLocked(),
                hasRunningTests = !!this.props.testruns.where({status: 'running'}).length;
            return (
                <div>
                    <div className='row-fluid page-sub-title'>
                        <div className='span2 ostf-controls'>
                            {!disabledState &&
                                <div className='toggle-credentials pull-right' onClick={this.toggleCredentials}>
                                    <i className={this.state.credentialsVisible ? 'icon-minus-circle' : 'icon-plus-circle'}></i>
                                    <div>{$.t('cluster_page.healthcheck_tab.provide_credentials')}</div>
                                </div>
                            }
                        </div>
                        <controls.Input
                            type='checkbox'
                            name='selectAll'
                            onChange={this.handleSelectAllClick}
                            checked={this.getNumberOfCheckedTests() == this.props.tests.length}
                            disabled={disabledState || hasRunningTests}
                            labelClassName='checkbox pull-right'
                            label={$.t('common.select_all')}
                            wrapperClassName='span2 ostf-controls select-all'
                        />
                        <div className='span2 ostf-controls'>
                            {hasRunningTests ?
                                (<button className='btn btn-danger pull-right action-btn stop-tests-btn'
                                    disabled={disabledState || this.state.actionInProgress}
                                    onClick={this.stopTests}
                                >
                                    {$.t('cluster_page.healthcheck_tab.stop_tests_button')}
                                </button>)
                            :
                                (<button className='btn btn-success pull-right action-btn run-tests-btn'
                                    disabled={disabledState || !this.getNumberOfCheckedTests() || this.state.actionInProgress}
                                    onClick={this.runTests}
                                >
                                    {$.t('cluster_page.healthcheck_tab.run_tests_button')}
                                </button>)
                            }
                        </div>
                    </div>
                    {(this.props.cluster.get('status') == 'new') &&
                        <div className='row-fluid'>
                            <div className='span12'>
                                <div className='alert'>{$.t('cluster_page.healthcheck_tab.deploy_alert')}</div>
                            </div>
                        </div>
                    }
                    <HealthcheckCredentials
                        key='credentials'
                        visible={this.state.credentialsVisible}
                        credentials={this.state.credentials}
                        onInputChange={this.handleInputChange}
                        disabled={disabledState || hasRunningTests}
                    />
                    <div className='testsets' key='testsets'>
                        <div>
                            {this.props.testsets.map(_.bind(function(testset) {
                                return <TestSet
                                key={testset.id}
                                testset={testset}
                                testrun={this.props.testruns.findWhere({testset: testset.id}) || new models.TestRun({testset: testset.id})}
                                tests={new Backbone.Collection(this.props.tests.where({testset: testset.id}))}
                                disabled={disabledState || hasRunningTests}
                                />;
                            }, this))}
                        </div>
                    </div>
                </div>
            );
        }
    });

    var HealthcheckCredentials = React.createClass({
        componentDidUpdate: function() {
            if (!_.isNull(this.props.visible)) {
                $(this.getDOMNode()).collapse(this.props.visible ? 'show' : 'hide');
            }
        },
        render: function() {
            var inputFields = ['user', 'password', 'tenant'];
            return (
                <div className='healthcheck credentials collapse'>
                    <div className='fieldset-group wrapper'>
                        <div className='healthcheck-group' >
                            <div className='clearfix note'>
                                {$.t('cluster_page.healthcheck_tab.credentials_description')}
                            </div>
                            {_.map(inputFields, function(name, index) {
                                return (<controls.Input
                                    key={name}
                                    type={(name == 'password') ? 'password' : 'text'}
                                    name={name}
                                    label={$.t('cluster_page.healthcheck_tab.' + name + '_label')}
                                    value={this.props.credentials[name]}
                                    onChange={this.props.onInputChange}
                                    toggleable={name == 'password'}
                                    description={$.t('cluster_page.healthcheck_tab.' + name + '_description')}
                                    labelClassName='openstack-sub-title'
                                    descriptionClassName={React.addons.classSet({'healthcheck-password': name == 'password'})}
                                    disabled={this.props.disabled}
                                />);
                            }, this)}
                        </div>
                    </div>
                </div>
            );
        }
    });

    var TestSet = React.createClass({
        mixins: [
            React.BackboneMixin('tests'),
            React.BackboneMixin('testset')
        ],
        handleTestSetCheck: function(name, value) {
            this.props.testset.set('checked', value);
            this.props.tests.invoke('set', {checked: value});
        },
        componentWillUnmount: function() {
            this.props.tests.invoke('off', 'change:checked', this.updateTestsetCheckbox, this);
        },
        componentWillMount: function() {
            this.props.tests.invoke('on', 'change:checked', this.updateTestsetCheckbox, this);
        },
        updateTestsetCheckbox: function() {
            this.props.testset.set('checked', this.props.tests.where({checked: true}).length == this.props.tests.length);
        },
        render: function() {
            return (
                <div className='row-fluid'>
                    <table className='table table-bordered healthcheck-table enable-selection'>
                        <thead>
                            <tr>
                                <th className='healthcheck-col-select'>
                                    <controls.Input
                                        type='checkbox'
                                        id={'testset-checkbox-' + this.props.testset.id}
                                        name={this.props.testset.get('name')}
                                        disabled={this.props.disabled}
                                        onChange={this.handleTestSetCheck}
                                        checked={this.props.testset.get('checked')}
                                    />
                                </th>
                                <th>
                                    <label className='testset-name' htmlFor={'testset-checkbox-' + this.props.testset.id}>
                                        {this.props.testset.get('name')}
                                    </label>
                                </th>
                                <th className='healthcheck-col-duration'>{$.t('cluster_page.healthcheck_tab.expected_duration')}</th>
                                <th className='healthcheck-col-duration'>{$.t('cluster_page.healthcheck_tab.actual_duration')}</th>
                                <th className='healthcheck-col-status'>{$.t('cluster_page.healthcheck_tab.status')}</th>
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
                </div>
            );
        }
    });

    var Test = React.createClass({
        mixins: [
            React.BackboneMixin('test')
        ],
        handleTestCheck: function(name, value) {
            this.props.test.set('checked', value);
        },
        highlightStep: function(text, step) {
            var lines = text.split('\n');
            var rx = new RegExp('^\\s*' + step + '\\.');
            _.each(lines, function(line, index) {
                if (line.match(rx)) {
                    lines[index] = '<b><u>' + line + '</u></b>';
                }
            });
            return lines.join('\n');
        },
        render: function() {
            var test = this.props.test,
                result = this.props.result,
                status = this.props.status,
                currentStatusClassName = 'healthcheck-status healthcheck-status-' + status,
                iconClasses = {
                    success: 'icon-passed',
                    failure: 'icon-failed',
                    error: 'icon-failed',
                    running: 'icon-process animate-spin',
                    wait_running: 'icon-clock'
                };
            return (
                <tr>
                    <td className='healthcheck-col-select'>
                        <controls.Input
                            type='checkbox'
                            controlOnly={true}
                            id={'test-checkbox-' + test.id}
                            name={test.get('name')}
                            disabled={this.props.disabled}
                            onChange={this.handleTestCheck}
                            checked={test.get('checked')}
                        />
                    </td>
                    <td>
                        <div className='healthcheck-name'>
                            <label htmlFor={'test-checkbox-' + test.id}>{test.get('name')}</label>
                        </div>
                        {_.contains(['failure', 'error', 'skipped'], status) &&
                            <div className='healthcheck-msg healthcheck-status-failure'>
                                {(result && result.message) &&
                                    <div>
                                        <b>{result.message}</b>
                                    </div>
                                }
                                <div className='well' dangerouslySetInnerHTML={{__html:
                                    utils.linebreaks((result && _.isNumber(result.step)) ? this.highlightStep(test.escape('description'), result.step) : test.escape('description'))
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
    return HealthCheckTab;
});
