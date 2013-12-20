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
    'views/common',
    'views/dialogs',
    'text!templates/cluster/healthcheck_tab.html',
    'text!templates/cluster/healthcheck_testset.html',
    'text!templates/cluster/healthcheck_tests.html'
],
function(utils, models, commonViews, dialogViews, healthcheckTabTemplate, healthcheckTestSetTemplate, healthcheckTestsTemplate) {
    'use strict';

    var HealthCheckTab, TestSet, Test;

    HealthCheckTab = commonViews.Tab.extend({
        template: _.template(healthcheckTabTemplate),
        updateInterval: 3000,
        events: {
            'click .run-tests-btn:not(:disabled)': 'runTests',
            'click .stop-tests-btn:not(:disabled)': 'stopTests'
        },
        isLocked: function() {
            return this.model.get('status') == 'new' || this.hasRunningTests() || !!this.model.task('deploy', 'running') ;
        },
        disableControls: function(disable) {
            var disabledState = disable || this.isLocked();
            this.runTestsButton.set({'disabled': disabledState || !this.tests.where({checked: true}).length});
            this.stopTestsButton.set({'disabled': disabledState});
            this.selectAllCheckbox.set({'disabled': disabledState});
        },
        checkIfRunningTests: function() {
            var hasRunningTests = this.hasRunningTests();
            this.runTestsButton.set({'disabled':  !this.tests.where({checked: true}).length || hasRunningTests})
                .set({'visible': !hasRunningTests});
            this.stopTestsButton.set({'disabled': !hasRunningTests})
                .set({'visible': hasRunningTests});
            this.selectAllCheckbox.set({'disabled': hasRunningTests});
        },
        calculateSelectAllCheckboxState: function() {
            var selectedTestSets = _.filter(this.subViews, function(testSetView) {
                return testSetView.selectAllCheckbox.get('checked');
            });
            this.selectAllCheckbox.set('checked', selectedTestSets.length == this.testsets.length);
        },
        calculateControlsState: function() {
            this.tab.runTestsButton.set({'disabled': !this.tests.where({checked: true}).length});
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
            this.checkIfRunningTests();
            this.disableControls();
        },
        update: function() {
            this.registerDeferred(
                this.testruns.fetch()
                    .done(_.bind(function() {
                        if (!this.hasRunningTests()) {
                            this.$('input[type=checkbox]').prop('checked', false)
                                .trigger('change');
                            this.disableControls(false);
                        }
                        this.checkIfRunningTests();
                    }, this))
                    .always(_.bind(this.scheduleUpdate, this))
            );
        },
        runTests: function() {
            this.disableControls(true);
            var testruns = new models.TestRuns(),
                oldTestruns = new models.TestRuns(),
                currentTestrun;
            _.each(this.subViews, function(subView) {
                if (subView.tests.where({checked: true}).length) {
                    var selectedTestIds = _.pluck(subView.tests.where({'checked': true}), 'id');
                    if (this.testruns.length != 0) {
                        if (_.isEmpty(this.testruns.filter(function(testRun) {
                            return !_.isEmpty(_.where(testRun, {'testset': subView.testset.id}));
                        }))) {
                            currentTestrun = new models.TestRun({
                                testset: subView.testset.id,
                                metadata: {
                                    config: {},
                                    cluster_id: this.model.id
                                },
                                tests: selectedTestIds
                            });
                            testruns.add(currentTestrun);
                        } else {
                                currentTestrun = new models.TestRun({
                                    id: subView.testrun.id,
                                    tests: selectedTestIds,
                                    status: 'restarted'
                                });
                                oldTestruns.add(currentTestrun);
                            }
                    } else {
                        currentTestrun = new models.TestRun({
                            testset: subView.testset.id,
                            metadata: {
                                config: {},
                                cluster_id: this.model.id
                            },
                            tests: selectedTestIds
                        });
                        testruns.add(currentTestrun);
                    }
                }
            }, this);
            if (!_.isEmpty(testruns.models)) {
                $.when(Backbone.sync('create', testruns).done(_.bind(this.update, this)));
            }
            if (!_.isEmpty(oldTestruns.models)) {
                $.when(Backbone.sync('update', oldTestruns).done(_.bind(this.update, this)));
            }
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
        bindTaskEvents: function(task) {
            return task.get('name') == 'deploy' ? task.on('change:status', this.render, this) : null;
        },
        onNewTask: function(task) {
            return this.bindTaskEvents(task) && this.render();
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.model.on('change:status', this.render, this);
            this.model.get('tasks').each(this.bindTaskEvents, this);
            this.model.get('tasks').on('add', this.onNewTask, this);
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
                ).done(_.bind(function() {
                    this.model.set({'ostf': ostf}, {silent: true});
                    this.render();
                    this.scheduleUpdate();
                }, this)
                ).fail(_.bind(function() {
                    this.$('.testsets > .row').hide();
                    this.$('.testsets > .error-message').show();
                }, this));
            } else {
                _.extend(this, this.model.get('ostf'));
                if (this.hasRunningTests()) {
                    this.update();
                }
            }
            this.testruns.on('sync', this.updateTestRuns, this);
        },
        initStickitBindings: function() {
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
            this.$el.html(this.template({cluster: this.model})).i18n();
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
            var bindings = {
                '.select-all-tumbler': {
                    observe: 'checked',
                    onSet: _.bind(function(value) {
                        _.each(this.subViews, function(testsSet) {
                            testsSet.selectAllCheckbox.set('checked', value);
                        }, this);
                        this.tests.each(function(test) {
                            test.set('checked', value);
                        }, this);
                    }, this),
                        attributes: [
                        {
                            name: 'disabled',
                            observe: 'disabled'
                        }
                    ]
                }
            };
            this.stickit(this.selectAllCheckbox, bindings);
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.tests.each(function(test) {
                test.set(
                    {
                        'checked': false,
                        'disabled': false
                    }
                );
            });
            this.initStickitBindings();
            this.selectAllCheckbox.on('change:disabled', _.bind(function(model, value){
                _.each(this.subViews, function(testsSet) {
                    testsSet.selectAllCheckbox.set('disabled', value);
                }, this);
                this.tests.each(function(test) {
                    test.set('disabled', value);
                }, this);
            }, this));
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
                this.disableControls();
            }
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
            this.selectAllCheckbox.set('checked', !this.tests.where({checked: false}).length);
            this.tab.selectAllCheckbox.set('checked', this.tab.tests.where({checked: true}).length == this.tab.tests.models.length);
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.selectAllCheckbox = new Backbone.Model({
                checked: false,
                disabled: false
            });
            this.testrun.on('change', this.renderTests, this);
            this.tests.on('change:checked', _.bind(function() {
                this.calculateSelectAllCheckedState();
                this.tab.disableControls();
            }, this));
        },
        renderTests: function() {
            this.$('tbody').empty();
            _.each(this.tests.models, function(test, index) {
                    test.set({'checked': false});
                    var testView = new Test({
                        testset: this,
                        tab: this.tab,
                        testrun: this.testrun,
                        model: test,
                        testIndex: index
                    });
                    this.$('tbody').append(testView.render().el);
                }, this);
        },
        calculateControlsState: function() {
            this.tab.runTestsButton.set({'disabled': !this.tests.where({checked: true}).length});
        },
        initStickitBindings: function() {
            var bindings = {
                '.testset-select': {
                    observe: 'checked',
                    onSet: _.bind(function(value) {
                       this.tests.each(function(test) {
                            test.set('checked', value);
                        });
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
            return this;
        }
    });

    return HealthCheckTab;
});
