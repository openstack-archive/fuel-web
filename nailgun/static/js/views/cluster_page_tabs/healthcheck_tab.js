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

    var HealthCheckTab, TestSet, OSTFTest;

    HealthCheckTab = commonViews.Tab.extend({
        template: _.template(healthcheckTabTemplate),
        updateInterval: 3000,
        events: {
            'click .run-tests-btn:not(:disabled)': 'runTests',
            'click .stop-tests-btn:not(:disabled)': 'stopTests'
        },
        isLocked: function() {
            return this.model.get('status') == 'new' || this.hasRunningTests() || !!this.model.task('deploy', 'running');
        },
        disableControls: function(disable) {
            var disabledState = disable || this.isLocked();
            this.runTestsButton.set({'disabled': disabledState});
            this.stopTestsButton.set({'disabled': disabledState});
            this.selectAllTumbler.set({'disabled': disabledState});
            this.setAllCheckboxGivenAttributeAndValue('disabled', disabledState);
        },
        changeVisibleAndDisabledControlsStateDuringTestRun: function() {
            var hasRunningTests = this.hasRunningTests();
            this.runTestsButton.set({'disabled': !this.$('input.test-select:checked').length || hasRunningTests})
                .set({'visible': !hasRunningTests});
            this.stopTestsButton.set({'disabled': !hasRunningTests})
                .set({'visible': hasRunningTests});
            this.setAllCheckboxGivenAttributeAndValue('disabled', hasRunningTests);
            this.selectAllTumbler.set({'disabled': hasRunningTests});
        },
        calculateSelectAllTumblerState: function() {
            var checkedViews = _.filter(_.map(this.subViews, function(testSetView) {
                return testSetView.selectAllCheckbox.get('checked');
            }));
            this.selectAllTumbler.set('checked', checkedViews.length == this.testsets.length);
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
            this.changeVisibleAndDisabledControlsStateDuringTestRun();
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
                        this.changeVisibleAndDisabledControlsStateDuringTestRun();
                    }, this))
                    .always(_.bind(this.scheduleUpdate, this))
            );
        },
        runTests: function() {
            this.disableControls(true);
            var selectedTestIds = [],
                testruns = new models.TestRuns(),
                oldTestruns = new models.TestRuns(),
                currentTestrun;
            _.each(this.subViews, function(subView) {
                if (subView instanceof TestSet && subView.$('input.test-select:checked').length) {
                    subView.tests.each(function(test) {
                        if (test.get('checked')) {
                            selectedTestIds.push(test.get('id'));
                        }
                    }, this);
                    if (this.testruns.length != 0) {
                        if (_.isEmpty(this.testruns.filter(function(testr) {
                            return !_.isEmpty(_.where(testr, {'testset': subView.testset.id}));
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
                Backbone.sync('create', testruns).done(_.bind(this.update, this));
            }
            if (!_.isEmpty(oldTestruns.models)) {
                Backbone.sync('update', oldTestruns).done(_.bind(this.update, this));
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
        selectAllTests: function(model, checked, options) {
            if (options.stickitChange) {
                this.setAllCheckboxGivenAttributeAndValue('checked', checked);
            }
        },
        setAllCheckboxGivenAttributeAndValue: function(attribute, value) {
            _.each(this.subViews, function(testSet) {
                testSet.selectAllCheckbox.set(attribute, value);
            });
            this.tests.each(function(test) {
                test.set(attribute, value);
            });
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            var defaultButtonModelsData = {
                'visible': true,
                'disabled': true
            };
            this.runTestsButton = new Backbone.Model(_.extend({}, defaultButtonModelsData));
            this.stopTestsButton = new Backbone.Model(_.extend({}, defaultButtonModelsData, {'visible': false}));
            this.selectAllTumbler = new Backbone.Model({
                checked: false,
                disabled: false
            });
            this.$el.html(this.template({cluster: this.model})).i18n();
            var visibleBindings = {
                observe: 'visible',
                visible: true
            };
            var checkedBindings = {
                stickitChange: true,
                observe: 'checked'
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
            this.stickit(this.selectAllTumbler, {'.select-all-tumbler': _.extend({}, checkedBindings, disabledBindings)});
            this.selectAllTumbler.on('change:checked', this.selectAllTests, this);
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
            this.disableControls(false);
            this.changeVisibleAndDisabledControlsStateDuringTestRun();
            return this;
        }
    });

    TestSet = Backbone.View.extend({
        template: _.template(healthcheckTestSetTemplate),
        bindings: {
            '.testset-select': {
                stickitChange: true,
                observe: 'checked',
                attributes: [{
                    name: 'disabled',
                    observe: 'disabled'
                }]
            }
        },
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
        selectTests: function(model, value, options) {
            if (options.stickitChange) {
                this.tests.each(function(test) {
                    test.set({'checked': value});
                });
            }
            this.tab.calculateSelectAllTumblerState();
        },
        calculateSelectAllCheckedState: function() {
            this.selectAllCheckbox.set('checked', this.tests.where({checked: true}).length == this.tests.models.length);
            this.tab.selectAllTumbler.set('checked', this.tab.tests.where({checked: true}).length == this.tab.tests.models.length);
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.selectAllCheckbox = new Backbone.Model({
                checked: false,
                disabled: false
            });
            this.selectAllCheckbox.on('change:checked', this.selectTests, this);
            this.testrun.on('change', this.renderTests, this);
        },
        renderTests: function() {
            var testView;
            this.$('tbody').empty();
            _.each(this.tests.models, function(test, index) {
                    testView = new OSTFTest({
                        testset: this,
                        tab: this.tab,
                        testrun: this.testrun,
                        model: test,
                        testIndex: index,
                        isChecked: test.get('checked')
                    });
                    this.$('tbody').append(testView.render().el);
                }, this);
        },
        calculateControlsState: function() {
            this.tab.runTestsButton.set({'disabled': !this.tests.where({checked: true}).length});
        },
        render: function() {
            this.$el.html(this.template({testset: this.testset})).i18n();
            this.renderTests();
            this.stickit(this.selectAllCheckbox);
            return this;
        }
    });

    OSTFTest = Backbone.View.extend({
        template: _.template(healthcheckTestsTemplate),
        tagName: 'tr',
        bindings: {
            '.test-select': {
                stickitChange: true,
                observe: 'checked',
                attributes: [{
                    name: 'disabled',
                    observe: 'disabled'
                }]
            }
        },
        testSelected: function(model, checked, options) {
            this.testset.calculateControlsState();
            if (options.stickitChange) {
                this.testset.calculateSelectAllCheckedState();
            }
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.model.set({'checked': _.isUndefined(this.isChecked) ? false : this.isChecked});
            this.model.on('change:checked', this.testSelected, this);
        },
        render: function() {
            this.$el.html(this.template(_.extend({
                testrun: this.testrun,
                test: this.model,
                testIndex: this.testIndex
            }, this.testset.templateHelpers))).i18n();
            this.stickit();
            return this;
        }
    });

    return HealthCheckTab;
});
