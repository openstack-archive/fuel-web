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
        getNumberOfCheckedTests: function() {
            return this.tests.where({checked: true}).length;
        },
        isLocked: function() {
            return this.model.get('status') == 'new' || this.model.task({group: 'deployment', status: 'running'});
        },
        disableControls: function(disable) {
            var disabledState = disable || this.isLocked();
            this.runTestsButton.set({disabled: disabledState || !this.getNumberOfCheckedTests()});
            this.stopTestsButton.set({disabled: !this.hasRunningTests()});
            this.selectAllCheckbox.set({disabled: disabledState});
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
                var selectedTests = subView.tests.where({checked: true});
                if (selectedTests.length) {
                    var selectedTestIds = _.pluck(selectedTests, 'id');
                    var currentTestrun = new models.TestRun({
                        testset: subView.testset.id,
                        metadata: {
                            config: {},
                            cluster_id: this.model.id
                        },
                        tests: selectedTestIds
                    });
                    var currentTestForReRun  = new models.TestRun({
                        id: subView.testrun.id,
                        tests: selectedTestIds,
                        status: 'restarted'
                    });
                    if (this.testruns.length != 0) {
                        if (this.testruns.where({testset: subView.testset.id}).length) {
                            oldTestruns.add(currentTestForReRun);
                        } else {
                            testruns.add(currentTestrun);
                        }
                    } else {
                        testruns.add(currentTestrun);
                    }
                }
            }, this);
            var requests = [];
            if (testruns.models.length) {
                requests.push(Backbone.sync('create', testruns));
            }
            if (oldTestruns.models.length) {
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
            this.model.on('change:status', this.render, this);
            this.model.get('tasks').bindToView(this, [{group: 'deployment'}], function(task) {
                task.on('change:status', this.render, this);
            });
            this.selectAllCheckbox.on('change:disabled', _.bind(function(model, value) {
                _.each(this.subViews, function(testSetView) {
                    testSetView.selectAllCheckbox.set({disabled: value});
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
                ).done(_.bind(function() {
                    this.model.set({ostf: ostf}, {silent: true});
                    this.render();
                    this.scheduleUpdate();
                }, this)
                ).fail(_.bind(function() {
                    this.$('.testsets > .row').hide();
                    this.$('.testsets > .progress-bar').hide();
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
                        _.each(this.subViews, function(testSetView) {
                            testSetView.selectAllCheckbox.set({checked: value});
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
            this.stickit(this.selectAllCheckbox, bindings);
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html(this.template({cluster: this.model})).i18n();
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
            this.initStickitBindings();
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
            return this;
        }
    });

    return HealthCheckTab;
});
