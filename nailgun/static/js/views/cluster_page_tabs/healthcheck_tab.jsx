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
            })
        ],
        getInitialState: function() {
            var ostf = {},
                cluster = this.props.model;
            ostf.testsets = new models.TestSets();
            ostf.testsets.url = _.result(ostf.testsets, 'url') + '/' + cluster.id;
            ostf.tests = new models.Tests();
            ostf.tests.url = _.result(ostf.tests, 'url') + '/' + cluster.id;
            ostf.testruns = new models.TestRuns();
            ostf.testruns.url = _.result(ostf.testruns, 'url') + '/last/' + cluster.id;
            return {
                ostf: ostf,
                loaded: false,
                loadingFailure: false
            };
        },
        componentDidMount: function() {
            $.when(
                this.state.ostf.testsets.fetch(),
                this.state.ostf.tests.fetch(),
                this.state.ostf.testruns.fetch()
            )
            .done(_.bind(function() {
                this.setState({loaded: true});
            }, this))
            .fail(_.bind(function() {
                this.setState({
                    loadingFailure: true,
                    loaded: false
                });
            }, this));
        },
        render: function() {
            return (
                <div className='wrapper'>
                    <h3 className='span6'>{$.t('cluster_page.healthcheck_tab.title')}</h3>
                    {this.state.loadingFailure ?
                        (<div>
                            <br/>
                            <br/>
                            <div className='alert error-message alert-error'>
                                {$.t('cluster_page.healthcheck_tab.not_available_alert')}
                            </div>
                        </div>)
                    :
                        (<HealthcheckTabContent
                            testsets={this.state.ostf.testsets}
                            tests={this.state.ostf.tests}
                            testruns={this.state.ostf.testruns}
                            cluster={this.props.model}
                            loaded={this.state.loaded}
                        />)
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
            React.BackboneMixin('cluster'),
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
                credentialsVisible: null
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
            this.credentials[name].value = value;
            this.forceUpdate();
        },
        runTests: function() {
            var testruns = new models.TestRuns(),
                oldTestruns = new models.TestRuns();
            this.props.testsets.each(function(testset) {
                var selectedTestIds = _.pluck(this.props.tests.where({checked: true}), 'id');
                if (selectedTestIds.length) {
                    var addCredentials = _.bind(function(obj) {
                        obj.ostf_os_access_creds = {
                            ostf_os_username: this.credentials.user.value,
                            ostf_os_tenant_name: this.credentials.tenant.value,
                            ostf_os_password: this.credentials.password.value
                        };
                        return obj;
                    }, this);
                    var testrunConfig = {tests: selectedTestIds};
                    if (this.props.testruns.where({testset: testset.id}).length) {
                        _.each(this.props.testruns.where({testset: testset.id}), function(testrun) {
                            _.extend(testrunConfig, addCredentials({
                                id: testrun.id,
                                status: 'restarted'
                            }));
                            oldTestruns.add(new models.TestRun(testrunConfig));
                        }, this);
                    } else {
                        _.extend(testrunConfig, {
                            testset: testset.id,
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
            $.when.apply($, requests).done(_.bind(this.startPolling, this, true));
        },
        getActiveTestRuns: function() {
            return this.props.testruns.where({status: 'running'});
        },
        stopTests: function() {
            var testruns = new models.TestRuns(this.getActiveTestRuns());
            if (testruns.length) {
                testruns.invoke('set', {status: 'stopped'});
                testruns.toJSON = function() {
                    return this.map(function(testrun) {
                        return _.pick(testrun.attributes, 'id', 'status');
                    });
                };
                Backbone.sync('update', testruns)
                    .done(this.stopPolling)
                    .always(_.bind(this.startPolling, this, true));
            }
        },
        render: function() {
            var disabledState = this.isLocked(),
                hasRunningTests = !!this.props.testruns.where({status: 'running'}).length;
            this.credentials = this.props.cluster.get('settings').get('access');
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
                        <controls.SelectAllCheckbox
                            name='selectAll'
                            onChange={this.handleSelectAllClick}
                            checked={this.getNumberOfCheckedTests() == this.props.tests.length}
                            disabled={disabledState || hasRunningTests}
                            cs={{
                                common: 'span2 ostf-controls',
                                label: 'checkbox pull-right'
                            }}
                        />

                        <div className='span2 ostf-controls'>
                            {hasRunningTests ?
                                (<button className='btn btn-danger pull-right action-btn stop-tests-btn'
                                    onClick={this.stopTests}
                                >
                                    {$.t('cluster_page.healthcheck_tab.stop_tests_button')}
                                </button>)
                            :
                                ( <button className='btn btn-success pull-right action-btn run-tests-btn'
                                disabled={disabledState || !this.getNumberOfCheckedTests()}
                                onClick={this.runTests}
                                >
                                    {$.t('cluster_page.healthcheck_tab.run_tests_button')}
                                </button>)
                            }
                        </div>
                    </div>
                    <div>
                        {(this.props.cluster.get('status') == 'new') &&
                            <div className='row-fluid'>
                                <div className='span12'>
                                    <div className='alert'>{$.t('cluster_page.healthcheck_tab.deploy_alert')}</div>
                                </div>
                            </div>
                        }
                    </div>
                    <HealthcheckCredentials
                        visible={this.state.credentialsVisible}
                        credentials={this.credentials}
                        onInputChange={this.handleInputChange}
                    />
                    <div className='testsets'>
                        {(!this.props.loaded) ?
                            <controls.ProgressBar />
                            :
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
                        }
                    </div>
                </div>

            );
        }
    });

    var HealthcheckCredentials = React.createClass({
        componentDidUpdate: function() {
            var $el = $(this.getDOMNode());
            if (!_.isNull(this.props.visible)) {
                $el.collapse(this.props.visible ? 'show' : 'hide');
            }
        },
        handleInputChange: function(name, value) {
            this.props.credentials[name].value = value;
            this.forceUpdate();
        },
        render: function() {
            var inputFields = ['user', 'password','tenant'];
            return (
                <div className='healthcheck credentials collapse'>
                    <div className='fieldset-group wrapper'>
                        <div className='settings-group' >
                            <div className='clearfix note'>
                                {$.t('cluster_page.healthcheck_tab.credentials_description')}
                            </div>
                            {_.map(inputFields, function(name, index) {
                                if (name == 'password') {
                                    // any suggestions concering removing this ugly 'if' highly appreciated
                                    return (<controls.PasswordField
                                        label={$.t('cluster_page.healthcheck_tab.' + name +'_label')}
                                        name={name}
                                        value={this.props.credentials[name].value}
                                        onChange={this.props.onInputChange}
                                        description={$.t('cluster_page.healthcheck_tab.' + name + '_description')}
                                        cs={{
                                            label: 'openstack-sub-title parameter-name',
                                            description: 'parameter-description description'
                                        }}
                                    />);
                                }
                                return (<controls.TextField
                                    label={$.t('cluster_page.healthcheck_tab.' + name +'_label')}
                                    name={name}
                                    value={this.props.credentials[name].value}
                                    onChange={this.props.onInputChange}
                                    description={$.t('cluster_page.healthcheck_tab.' + name + '_description')}
                                    cs={{
                                        label: 'openstack-sub-title parameter-name',
                                        description: 'parameter-description description'
                                    }}
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
            this.props.tests.invoke('off');
        },
        componentWillMount: function() {
            this.props.tests.each(function(test) {
                test.on('change:checked', function(test) {
                    var checkedTests = this.props.tests.where({checked: true});
                    this.props.testset.set('checked', checkedTests.length == this.props.tests.length);
                }, this);
            }, this);
        },
        render: function() {
            return (
                <div className='row-fluid'>
                    <table className='table table-bordered healthcheck-table enable-selection'>
                        <thead>
                            <tr>
                                <th className='healthcheck-col-select'>
                                    <controls.Checkbox
                                        controlOnly={true}
                                        id={'testset-checkbox-' + this.props.testset.id}
                                        name={this.props.testset.get('name')}
                                        disabled={this.props.disabled}
                                        onChange={this.handleTestSetCheck}
                                        value={this.props.testset.get('checked')}
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
                                        initialState={test.get('checked')}
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
                currentStatusClassName = 'healthcheck-status healthcheck-status-' + this.props.status,
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
                        <controls.Checkbox
                            controlOnly={true}
                            id={'test-checkbox-' + test.id}
                            name={test.get('name')}
                            disabled={this.props.disabled}
                            onChange={this.handleTestCheck}
                            value={!!this.props.test.get('checked')}
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
                                        <br/><br/>
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
                            {iconClasses[status] ? <i className={iconClasses[status]} /> : '—'}
                        </div>
                    </td>
                </tr>
            );
        }
    });
    return HealthCheckTab;
});
