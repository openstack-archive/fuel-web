/*
 * Copyright 2013 Mirantis, Inc.
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
define(
[
    'utils',
    'models',
    'view_mixins',
    'views/common',
    'views/dialogs',
    'text!templates/cluster/healthcheck_tab.html',
    'text!templates/cluster/healthcheck_credentials.html',
    'text!templates/cluster/healthcheck_testset.html',
    'text!templates/cluster/healthcheck_tests.html'
],
function(utils, models, viewMixins, commonViews, dialogViews, healthcheckTabTemplate, credentialsTemplate, healthcheckTestSetTemplate, healthcheckTestsTemplate) {
    'use strict';

    var HealthCheckTab, CredentialsForm, TestSet, Test;

    HealthCheckTab = commonViews.Tab.extend({
        template: _.template(healthcheckTabTemplate),
        updateInterval: 3000,
        events: {
            'click .run-tests-btn:not(:disabled)': 'runTests',
            'click .stop-tests-btn:not(:disabled)': 'stopTests',
            'click .toggle-credentials': 'toggleCredentialsForm'
        },
        getNumberOfCheckedTests: function() {
            return this.tests.where({checked: true}).length;
        },
        isLocked: function() {
            return this.model.get('status') == 'new' || this.model.task({group: 'deployment', status: 'running'});
        },
        toggleCredentialsForm: function(e) {
            this.$('.credentials').collapse('toggle');
        },
        disableControls: function(disable) {
            var disabledState = disable || this.isLocked();
            var hasRunningTests = this.hasRunningTests();
            this.runTestsButton.set({disabled: disabledState || !this.getNumberOfCheckedTests()});
            this.stopTestsButton.set({disabled: !hasRunningTests});
            this.selectAllCheckbox.set({disabled: disabledState || hasRunningTests});
            this.credentialsWrapper.set({disabled: disabledState || hasRunningTests});
        },
        toggleTestsVisibility: function() {
            var hasRunningTests = this.hasRunningTests();
            this.runTestsButton.set({visible: !hasRunningTests});
            this.stopTestsButton.set({visible: hasRunningTests});
        },
        getActiveTestRuns: function() {
            return this.testruns.where({status: 'running'});
        },
        hasRunningTests: function() {
            return !!this.getActiveTestRuns().length;
        },
        scheduleUpdate: function() {
            if (this.hasRunningTests()) {
                this.registerDeferred(this.timeout = $.timeout(this.updateInterval).done(_.bind(this.update, this)));
            }
            this.toggleTestsVisibility();
            this.disableControls();
        },
        update: function() {
            this.registerDeferred(
                this.testruns.fetch()
                    .done(_.bind(function() {
                        if (!this.hasRunningTests()) {
                            this.disableControls(false);
                        }
                    }, this))
                    .always(_.bind(this.scheduleUpdate, this))
            );
        },
        runTests: function() {
            this.disableControls(true);
            var testruns = new models.TestRuns(),
                oldTestruns = new models.TestRuns();
            _.each(this.subViews, function(subView) {
                if (subView instanceof TestSet) {
                    var selectedTestIds = _.pluck(subView.tests.where({checked: true}), 'id');
                    if (selectedTestIds.length) {
                        var addCredentials = _.bind(function(obj) {
                            obj.ostf_os_access_creds = {
                                ostf_os_username:this.credentials.get('username'),
                                ostf_os_tenant_name: this.credentials.get('tenant'),
                                ostf_os_password: this.credentials.get('password')
                            };
                            return obj;
                        }, this);
                        var testrunConfig = {tests: selectedTestIds};
                        if (this.testruns.where({testset: subView.testset.id}).length) {
                            _.extend(testrunConfig, addCredentials({
                                id: subView.testrun.id,
                                status: 'restarted'
                            }));
                            oldTestruns.add(new models.TestRun(testrunConfig));
                        } else {
                            _.extend(testrunConfig, {
                                testset: subView.testset.id,
                                metadata: addCredentials({
                                    config: {},
                                    cluster_id: this.model.id
                                })
                            });
                            testruns.add(new models.TestRun(testrunConfig));
                        }
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
            $.when.apply($, requests).done(_.bind(this.update, this));
        },
        stopTests: function() {
            var testruns = new models.TestRuns(this.getActiveTestRuns());
            if (testruns.length) {
                this.disableControls(true);
                testruns.invoke('set', {status: 'stopped'});
                testruns.toJSON = function() {
                    return this.map(function(testrun) {
                        return _.pick(testrun.attributes, 'id', 'status');
                    });
                };
                Backbone.sync('update', testruns).done(_.bind(function() {
                    if (this.timeout) {
                        this.timeout.clear();
                    }
                    this.update();
                }, this));
            }
        },
        updateTestRuns: function() {
            _.each(this.subViews, function(subView) {
                if (subView instanceof TestSet) {
                    var testrun = this.testruns.findWhere({testset: subView.testset.id});
                    if (testrun) {
                        subView.testrun.set(testrun.attributes);
                    }
                }
            }, this);
        },
        initialize: function(options) {
            _.defaults(this, options);
             this.runTestsButton = new Backbone.Model({
                visible: true,
                disabled: true
            });
            this.stopTestsButton = new Backbone.Model({
                visible: false,
                disabled: true
            });
            this.selectAllCheckbox = new Backbone.Model({
                checked: false,
                disabled: false
            });
            this.credentialsWrapper = new Backbone.Model({
                visible: false,
                disabled: false
            });
            this.model.on('change:status', this.render, this);
            this.model.get('tasks').bindToView(this, [{group: 'deployment'}], function(task) {
                task.on('change:status', this.render, this);
            });
            this.selectAllCheckbox.on('change:disabled', _.bind(function(model, value) {
                _.each(this.subViews, function(testSetView) {
                    if (testSetView instanceof TestSet) {
                        testSetView.selectAllCheckbox.set({disabled: value});
                    }
                }, this);
                this.tests.invoke('set', {disabled: value});
            }, this));
            if (!this.model.get('ostf')) {
                var ostf = {};
                ostf.testsets = new models.TestSets();
                ostf.testsets.url = _.result(ostf.testsets, 'url') + '/' + this.model.id;
                ostf.tests = new models.Tests();
                ostf.tests.url = _.result(ostf.tests, 'url') + '/' + this.model.id;
                ostf.testruns = new models.TestRuns();
                ostf.testruns.url = _.result(ostf.testruns, 'url') + '/last/' + this.model.id;
                _.extend(this, ostf);
                $.when(
                    this.testsets.deferred = this.testsets.fetch(),
                    this.tests.fetch(),
                    this.testruns.fetch()
                ).always(_.bind(function() {
                        this.render();
                        this.disableControls();
                }, this)
                ).done(_.bind(function() {
                    this.model.set({ostf: ostf}, {silent: true});
                    this.scheduleUpdate();
                }, this)
                ).fail(_.bind(function() {
                    this.$('.error-message').show();
                }, this)
                );
            } else {
                _.extend(this, this.model.get('ostf'));
                if (this.hasRunningTests()) {
                    this.update();
                }
            }
            this.testruns.on('sync', this.updateTestRuns, this);
            if (!this.model.has('ostfCredentials')) {
                var credentials = new models.OSTFCredentials();
                this.model.set({ostfCredentials: credentials});
                credentials.update(this.model.get('settings'));
                this.model.get('settings').on('change:access.*', _.bind(credentials.update, credentials));
            }
            this.credentials = this.model.get('ostfCredentials');
        },
        initStickitBindings: function() {
            var visibleBindings = {
                observe: 'visible',
                visible: true
            };
            var disabledBindings = {
                attributes: [
                    {
                        name: 'disabled',
                        observe: 'disabled'
                    }
                ]
            };
            this.stickit(this.runTestsButton, {'.run-tests-btn': _.extend({}, visibleBindings, disabledBindings)});
            this.stickit(this.stopTestsButton, {'.stop-tests-btn':  _.extend({}, visibleBindings, disabledBindings)});
            var selectAllBindings = {
                '.select-all-tumbler': {
                    observe: 'checked',
                    onSet: _.bind(function(value) {
                        _.each(this.subViews, function(testSetView) {
                            if (testSetView instanceof TestSet) {
                                testSetView.selectAllCheckbox.set({checked: value});
                            }
                        });
                        this.tests.invoke('set', {checked: value});
                    }, this),
                    attributes: [
                        {
                            name: 'disabled',
                            observe: 'disabled'
                        }
                    ]
                }
            };
            this.stickit(this.selectAllCheckbox, selectAllBindings);
            var credentialsWrapperBindings = {
                '.toggle-credentials i' : {
                    attributes: [{
                        name: 'class',
                        observe: 'visible',
                        onGet: function(value) {
                            return 'icon-' + (value ? 'minus' : 'plus') + '-circle';
                        }
                    }]
                },
                '.credentials input': {
                    attributes: [{
                        name: 'disabled',
                        observe: 'disabled'
                    }]
                }
            };
            this.stickit(this.credentialsWrapper, credentialsWrapperBindings);
            var controlsBindings = {
                '.ostf-controls': {
                    observe: 'visible',
                    visible: function() {
                        return !!this.testsets.length;
                    }
                }
            };
            this.stickit(this.model, controlsBindings);
        },
        renderCredentials: function() {
            this.$('.credentials').html('');
            if (this.testsets && this.testsets.length > 0) {
                this.credentialsForm = new CredentialsForm({credentials: this.credentials, tab: this});
                this.registerSubView(this.credentialsForm);
                this.$('.credentials').append(this.credentialsForm.render().el);
            }
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html(this.template({cluster: this.model, isLocked: this.isLocked()})).i18n();
            if (this.testsets.deferred.state() != 'pending') {
                this.$('.testsets').html('');
                this.testsets.each(function(testset) {
                    var testsetView = new TestSet({
                        cluster: this.model,
                        testset: testset,
                        testrun: this.testruns.findWhere({testset: testset.id}) || new models.TestRun({testset: testset.id}),
                        tests: new models.Tests(this.tests.where({testset: testset.id})),
                        tab: this
                    });
                    this.registerSubView(testsetView);
                    this.$('.testsets').append(testsetView.render().el);
                }, this);
            }
            this.$('.testsets > .progress-bar').hide();
            this.$('.credentials').collapse({toggle: false});
            this.$('.credentials').on('show.bs.collapse', _.bind(function() {this.credentialsWrapper.set({visible: true});}, this));
            this.$('.credentials').on('hide.bs.collapse',  _.bind(function() {this.credentialsWrapper.set({visible: false});}, this));
            this.renderCredentials();
            this.initStickitBindings();
            return this;
        }
    });

    CredentialsForm = Backbone.View.extend({
        className: 'fieldset-group wrapper',
        template: _.template(credentialsTemplate),
        mixins: [viewMixins.toggleablePassword],
        bindings: {
            'input[name=password]': 'password',
            'input[name=username]': 'username',
            'input[name=tenant]': 'tenant'
        },
        initialize: function(options) {
            _.defaults(this, options);
        },
        render: function() {
            this.$el.html(this.template()).i18n();
            this.stickit(this.credentials);
            return this;
        }
    });

    TestSet = Backbone.View.extend({
        template: _.template(healthcheckTestSetTemplate),
        templateHelpers: _.extend(_.pick(utils, 'linebreaks'), {highlightStep: function(text, step) {
            var lines = text.split('\n');
            var rx = new RegExp('^\\s*' + step + '\\.');
            _.each(lines, function(line, index) {
                if (line.match(rx)) {
                    lines[index] = '<b><u>' + line + '</u></b>';
                }
            });
            return lines.join('\n');
        }}),
        calculateSelectAllCheckedState: function() {
            this.selectAllCheckbox.set({checked: this.tests.where({checked: true}).length == this.tests.length});
            this.tab.selectAllCheckbox.set({checked: this.tab.getNumberOfCheckedTests() == this.tab.tests.length});
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.selectAllCheckbox = new Backbone.Model({
                checked: false,
                disabled: false
            });
            this.testrun.on('change', this.renderTests, this);
            this.tests.invoke('set', {disabled: false});
            this.tests.on('change:checked', _.bind(function() {
                this.calculateSelectAllCheckedState();
                this.tab.disableControls();
            }, this));
        },
        renderTests: function() {
            this.$('tbody').empty();
            this.tests.each(function(test, index) {
                var testView = new Test({
                    testset: this,
                    tab: this.tab,
                    testrun: this.testrun,
                    model: test,
                    testIndex: index
                });
                this.$('tbody').append(testView.render().el);
            }, this);
            var commonDisabledState = this.tab.selectAllCheckbox.get('disabled');
            this.selectAllCheckbox.set({disabled: commonDisabledState});
            this.tests.invoke('set', {disabled: commonDisabledState});
        },
        initStickitBindings: function() {
            var bindings = {
                '.testset-select': {
                    observe: 'checked',
                    onSet: _.bind(function(value) {
                       this.tests.invoke('set', {checked: value});
                    }, this),
                    attributes: [{
                        name: 'disabled',
                        observe: 'disabled'
                    }]
                }
            };
            this.stickit(this.selectAllCheckbox, bindings);
        },
        render: function() {
            this.$el.html(this.template({testset: this.testset})).i18n();
            this.renderTests();
            this.initStickitBindings();
            this.calculateSelectAllCheckedState();
            return this;
        }
    });

    Test = Backbone.View.extend({
        template: _.template(healthcheckTestsTemplate),
        tagName: 'tr',
        initStickitBindings: function() {
            var bindings = {
                '.test-select': {
                    observe: 'checked',
                    attributes: [{
                        name: 'disabled',
                        observe: 'disabled'
                    }]
                }
            };
            this.stickit(this.model, bindings);
        },
        initialize: function(options) {
            _.defaults(this, options);
        },
        render: function() {
            this.$el.html(this.template(_.extend({
                testrun: this.testrun,
                test: this.model,
                testIndex: this.testIndex
            }, this.testset.templateHelpers))).i18n();
            this.initStickitBindings();
            this.tab.disableControls();
            return this;
        }
    });

    return HealthCheckTab;
});
