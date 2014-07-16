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
        'jsx!component_mixins'
    ],
    function (React, models, utils, componentMixins) {
        'use strict';

        var HealthCheckTab = React.createClass({
             mixins: [
                React.BackboneMixin('testruns'),
                React.BackboneMixin('tests'),
                React.BackboneMixin('testsets')
            ],
            getInitialState: function() {
                var ostf = {},
                    model = this.props.model;
                ostf.testsets = new models.TestSets();
                ostf.testsets.url = _.result(ostf.testsets, 'url') + '/' + model.id;
                ostf.tests = new models.Tests();
                ostf.tests.url = _.result(ostf.tests, 'url') + '/' + model.id;
                ostf.testruns = new models.TestRuns();
                ostf.testruns.url = _.result(ostf.testruns, 'url') + '/last/' + model.id;
                if (!this.props.model.has('ostfCredentials')) {
                    var credentials = new models.OSTFCredentials();
                    this.props.model.set({ostfCredentials: credentials});
                    credentials.update(this.props.model.get('settings'));
                    this.props.model.get('settings').on('change:access.*', _.bind(credentials.update, credentials));
                }
                this.credentials = this.props.model.get('ostfCredentials');
                return {ostf: ostf,
                       credentialsVisible: false};

            },
            componentDidMount: function() {
                $.when(
                    this.state.ostf.testsets.deferred =  this.state.ostf.testsets.fetch(),
                    this.state.ostf.tests.fetch(),
                    this.state.ostf.testruns.fetch()
                )
                    .always(_.bind(function() {
                            this.forceUpdate();
                    }, this))
                    .done(_.bind(function() {
                        this.props.model.set({ostf: this.state.ostf}, {silent: true});
                        this.state.ostf.tests.each(_.bind(function(test){
                            test.on('change:checked', _.bind(function(test) {
                                var currentTestsetId = test.get('testset');
                                var currentTestSet = this.state.ostf.testsets.where({id: currentTestsetId})[0];
                                var testsInTestset = this.state.ostf.tests.where({testset: currentTestsetId});
                                var checkedTestsInTestset = _.compact(_.map(testsInTestset, function(test) {
                                    return test.get('checked')
                                }));
                                if (testsInTestset.length == checkedTestsInTestset.length) {
                                     currentTestSet.set({checked: true});
                                     this.forceUpdate();
                                }
                                else {
                                    currentTestSet.set({checked: false});
                                    this.forceUpdate();
                                }

                            }, this));
                        }, this));
                        this.state.ostf.testruns.each(_.bind(function(testrun) {
                            testrun.on('change', _.bind(function(){
                                this.forceUpdate();
                            }, this));
                        }, this));
                        this.forceUpdate();
                    }, this)
                    ).fail(_.bind(function() {
                        this.$('.error-message').show();
                    }, this)
                );
                this.props.model.on('change:status', this.forceUpdate, this);
                if (!this.props.model.has('ostfCredentials')) {
                    var credentials = new models.OSTFCredentials();
                    this.props.model.set({ostfCredentials: credentials});
                    credentials.update(this.props.model.get('settings'));
                    this.props.model.get('settings').on('change:access.*', _.bind(credentials.update, credentials));
                }
                this.props.credentials = this.props.model.get('ostfCredentials');

            },
            getNumberOfCheckedTests: function() {
                return this.state.ostf.tests.where({checked: true}).length;
            },
            isLocked: function() {
                var model =  this.props.model;
                return model.get('status') == 'new' || !!model.task({group: 'deployment', status: 'running'});
            },
            toggleCredentials: function() {
                this.setState({'credentialsVisible': !this.state.credentialsVisible});
            },
            handleSelectAllClick: function(event) {
                this.state.ostf.tests.invoke('set', {'checked': event.target.checked});
            },
            runTests: function() {
                var testruns = new models.TestRuns(),
                    oldTestruns = new models.TestRuns();
                this.state.ostf.testsets.each(function(testset) {
                    var selectedTestIds = _.pluck(this.state.ostf.tests.where({checked: true}), 'id');
                    if (selectedTestIds.length) {
                        var addCredentials = _.bind(function(obj) {
                            obj.ostf_os_access_creds = {
                                ostf_os_username:this.props.credentials.get('username'),
                                ostf_os_tenant_name: this.props.credentials.get('tenant'),
                                ostf_os_password: this.props.credentials.get('password')
                            };
                            return obj;
                        }, this);
                        var testrunConfig = {tests: selectedTestIds};
                        if (this.state.ostf.testruns.where({testset: testset.id}).length) {
                            _.each(this.state.ostf.testruns.where({testset: testset.id}), function(testrun) {
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
                                    cluster_id: this.props.model.id
                                })
                            });
                            testruns.add(new models.TestRun(testrunConfig));
                        }
                    }
                }, this);
                var requests = [];


                if (testruns.length) {
                    testruns.each(function(testrun) {
                        testrun.on('change:status', _.bind(function() {
                            this.forceUpdate();
                        }, this));
                    }, this);
                    requests.push(Backbone.sync('create', testruns));
                }
                if (oldTestruns.length) {
                     oldTestruns.each(function(testrun) {
                        testrun.on('change:status', _.bind(function() {
                            this.forceUpdate();
                        }, this));
                    }, this);
                    requests.push(Backbone.sync('update', oldTestruns));
                }
                $.when($, requests)
                    .done(_.bind(function() {
                        this.forceUpdate();
                    }, this));
            },
            render: function () {
                var cluster = this.props.model,
                    disabledState = this.isLocked(),
                    hasRunningTests = !!this.state.ostf.testruns.where({status: 'running'}).length;
                return (
                    <div className='wrapper'>
                        <div className='row-fluid page-sub-title'>
                            <h3 className='span6'> {$.t('cluster_page.healthcheck_tab.title')}</h3>
                            <div className='span2 ostf-controls'>
                                {!disabledState &&
                                    <div className='toggle-credentials pull-right' onClick={_.bind(this.toggleCredentials, this)}>
                                        <i className={this.state.credentialsVisible ? 'icon-minus-circle' : 'icon-plus-circle'}></i>
                                        <div>{$.t('cluster_page.healthcheck_tab.provide_credentials')}</div>
                                    </div>
                                }
                            </div>
                            <div className='span2 ostf-controls'>
                                <label className='checkbox pull-right select-all'>
                                    <input type='checkbox' className='select-all-tumbler'
                                        disabled={disabledState || hasRunningTests}
                                        checked={this.getNumberOfCheckedTests() ==
                                            this.state.ostf.tests.length}
                                        onChange={_.bind(this.handleSelectAllClick, this)}
                                    />
                                    <span>&nbsp;</span>
                                    <span>{$.t('common.select_all_button')}</span>
                                </label>
                                </div>
                                <div className='span2 ostf-controls'>
                                    <button className='btn btn-success pull-right action-btn run-tests-btn'
                                        disabled={disabledState || !this.getNumberOfCheckedTests()}
                                        onClick={_.bind(this.runTests, this)} >
                                        {$.t('cluster_page.healthcheck_tab.run_tests_button')}
                                    </button>
                                    <button className='btn btn-danger pull-right action-btn stop-tests-btn hide'
                                        disabled={!hasRunningTests}>
                                    {$.t('cluster_page.healthcheck_tab.stop_tests_button')}
                                    </button>
                                </div>
                            </div>
                            <div>
                                {(cluster.get('status') == 'new') &&
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
                            />
                            <div className='testsets'>
                                {(!cluster.get('ostf')) ?
                                    <div className='progress-bar'>
                                        <div className='progress progress-striped progress-success active'>
                                            <div className='bar'></div>
                                        </div>
                                    </div>
                                    :
                                    <div>
                                        {this.state.ostf.testsets.map(_.bind(function(testset) {
                                            return <TestSet
                                                key={testset.id}
                                                value={testset.get('checked')}
                                                testset={testset}
                                                testrun={this.state.ostf.testruns.findWhere({testset: testset.id}) || new models.TestRun({testset: testset.id})}
                                                tests={new Backbone.Collection(this.state.ostf.tests.where({testset: testset.id}))}
                                                disabled={disabledState || hasRunningTests}
                                                />;
                                        }, this))}
                                    </div>
                                }
                        </div>
                        <div className='alert hide error-message alert-error'>{$.t('cluster_page.healthcheck_tab.not_available_alert')}</div>
                    </div>
                    );
            }
        });

    var HealthcheckCredentials = React.createClass({
        mixins: [
            React.BackboneMixin('credentials')
        ],
        handleInputChange: function(event) {
            var target = event.target;
            this.props.credentials.set(target.name, target.value);
        },
        togglePassword: function(event) {
            var input = $(event.currentTarget).prev();
            if (input.attr('disabled')) {return;}
            input.attr('type', input.attr('type') == 'text' ? 'password' : 'text');
            $(event.currentTarget).find('i').toggleClass('hide');
        },
        render: function() {
            if (this.props.visible) {
                return (
                    <div className='credentials'>
                        <div className='fieldset-group wrapper'>
                            <div className='settings-group' >
                                <div className='clearfix note'>
                                {$.t('cluster_page.healthcheck_tab.credentials_description')}
                               </div>
                               <div className='parameter-box clearfix'>
                                 <div className='openstack-sub-title parameter-name'>
                                   { $.t('cluster_page.healthcheck_tab.username_label') }
                                 </div>
                                 <div className='parameter-control '>
                                   <input type='text' name='username'
                                   defaultValue={this.props.credentials.get('username')}
                                   onChange={_.bind(this.handleInputChange, this)} />
                                 </div>
                                 <div className='parameter-description description'>
                                   { $.t('cluster_page.healthcheck_tab.username_description') }
                                 </div>
                               </div>
                               <div className='parameter-box clearfix'>
                                 <div className='openstack-sub-title parameter-name'>
                                   { $.t('cluster_page.healthcheck_tab.password_label') }
                                 </div>
                                 <div className='parameter-control input-append'>
                                   <input type='password' name='password' className='input-append'
                                    defaultValue={this.props.credentials.get('password')}
                                    onChange={_.bind(this.handleInputChange, this)} />
                                   <span className='add-on' onClick={this.togglePassword}>
                                       <i className='icon-eye'></i>
                                       <i className='icon-eye-off hide'></i>
                                   </span>
                                 </div>
                                 <div className='parameter-description description'>
                                   { $.t('cluster_page.healthcheck_tab.password_description') }
                                 </div>
                               </div>
                               <div className='parameter-box clearfix'>
                                 <div className='openstack-sub-title parameter-name'>
                                   { $.t('cluster_page.healthcheck_tab.tenant_label') }
                                 </div>
                                 <div className='parameter-control'>
                                   <input type='text' name='tenant'
                                   defaultValue={this.props.credentials.get('tenant')}
                                   onChange={_.bind(this.handleInputChange, this)} />
                                 </div>
                                 <div className='parameter-description description'>
                                   { $.t('cluster_page.healthcheck_tab.tenant_description') }
                                 </div>
                               </div>
                            </div>
                        </div>
                    </div>
                );
            }
            else {
                return (<div></div>);
            }
        }
    });

    var TestSet = React.createClass({
        mixins: [
            React.BackboneMixin('tests'),
            React.BackboneMixin('testset')
        ],
        handleTestSetCheck: function(event) {
            this.props.testset.set('checked', event.target.checked);
            this.props.tests.invoke('set', {checked: event.target.checked});
        },
        render: function() {
            return (
                <div className='row-fluid'>
                    <table className='table table-bordered healthcheck-table enable-selection'>
                        <thead>
                            <tr>
                                <th className='healthcheck-col-select'>
                                    <div className='custom-tumbler'>
                                        <input
                                            type='checkbox'
                                            name={this.props.testset.get('name')}
                                            disabled={this.props.disabled}
                                            onChange={_.bind(this.handleTestSetCheck, this)}
                                            checked={this.props.value} />
                                        <span>&nbsp;</span>
                                    </div>
                                </th>
                                <th>
                                    <label className='testset-name'>
                                        {this.props.testset.get('name')}
                                    </label>
                                </th>
                                <th className='healthcheck-col-duration'>{$.t('cluster_page.healthcheck_tab.expected_duration')}</th>
                                <th className='healthcheck-col-duration'>{$.t('cluster_page.healthcheck_tab.actual_duration')}</th>
                                <th className='healthcheck-col-status'>{$.t('cluster_page.healthcheck_tab.status')}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {this.props.tests.map(_.bind(function(test, testIndex) {
                                var result = this.props.testrun &&
                                    _.find(this.props.testrun.get('tests'), {id: test.id});
                                var status = result && result.status || 'unknown';
                                return <Test
                                        key={test.id}
                                        test={test}
                                        result={result}
                                        testIndex={testIndex}
                                        status={status}
                                        disabled={this.props.disabled}
                                        initialState={test.get('checked')}
                                    />;
                            }, this))}
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
        handleTestCheck: function(event) {
            this.props.test.set('checked', event.target.checked);
        },
        render: function() {
            var test = this.props.test,
                result = this.props.result,
                testIndex = this.props.testIndex,
                status = this.props.status,
                currentStatusClassName = 'healthcheck-status healthcheck-status-' + this.props.status;
            return (
                <tr>
                    <td className='healthcheck-col-select'>
                        <div className='custom-tumbler'>
                                <input
                                    type='checkbox'
                                    name={test.get('name')}
                                    disabled={this.props.disabled}
                                    onChange={_.bind(this.handleTestCheck, this)}
                                    checked={!!this.props.test.get('checked')}
                                />
                               <span>&nbsp;</span>
                        </div>
                    </td>
                    <td>
                        <div className='healthcheck-name'>
                            <label>{test.get('name')}</label>
                        </div>
                        {(status == 'failure' || status == 'error' || status == 'skipped') && (result && result.message) &&
                            <div className='healthcheck-msg healthcheck-status-failure'>
                                <b>{result.message}</b>
                                <br/><br/>
                                <div className='well'></div>
                            </div>
                        }
                    </td>
                    <td className='healthcheck-col-duration'>
                        <div className='healthcheck-duration'>{test.get('duration') || '' }</div>
                    </td>
                    <td className='healthcheck-col-duration'>
                        {(status != 'running' && result && _.isNumber(result.taken)) ?
                            <div className='healthcheck-duration'>{result.taken.toFixed(1) }</div>
                          :
                            <div className={currentStatusClassName}>&mdash;</div>
                        }
                    </td>
                    <td className='healthcheck-col-status'>
                        <div className={currentStatusClassName}>
                        {(status == 'success') ?
                              <i className='icon-passed'></i>
                            : (status == 'failure' || status == 'error') ?
                              <i className='icon-failed'></i>
                            : (status == 'running') ?
                              <i className='icon-process animate-spin'></i>
                            : (status == 'wait_running') ?
                              <i className='icon-clock'></i>
                            :  '—'
                        }

                      </div>
                    </td>
                 </tr>
            )
        }
    });

    return HealthCheckTab;

});