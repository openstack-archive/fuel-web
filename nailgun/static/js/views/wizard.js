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
define(
[
    'require',
    'jquery',
    'underscore',
    'i18n',
    'backbone',
    'utils',
    'models',
    'cocktail',
    'view_mixins',
    'text!templates/wizard/create_cluster_wizard.html',
    'text!templates/wizard/name_and_release.html',
    'text!templates/wizard/common_wizard_panel.html',
    'text!templates/wizard/mode.html',
    'text!templates/wizard/network.html',
    'text!templates/wizard/storage.html',
    'text!templates/wizard/ready.html',
    'text!templates/wizard/control_template.html',
    'text!templates/wizard/warning.html',
    'text!templates/wizard/text_input.html'
],
function(require, $, _, i18n, Backbone, utils, models, Cocktail, viewMixins, createClusterWizardTemplate, clusterNameAndReleasePaneTemplate, commonWizardTemplate, modePaneTemplate, networkPaneTemplate, storagePaneTemplate, clusterReadyPaneTemplate, controlTemplate, warningTemplate, textInputTemplate) {
    'use strict';

    var views = {},
        clusterWizardPanes = {};

    views.CreateClusterWizard = Backbone.View.extend({
        className: 'modal fade create-cluster-modal',
        template: _.template(createClusterWizardTemplate),
        events: {
            keydown: 'onKeydown',
            'click .next-pane-btn': 'nextPane',
            'click .prev-pane-btn': 'prevPane',
            'click .wizard-step.available': 'onStepClick',
            'click .finish-btn': 'createCluster'
        },
        composeStickitBindings: function() {
            var bindings = {};
            _.each(this.panesConstructors, function(PaneConstructor, paneIndex) {
                bindings['.wizard-step[data-pane=' + paneIndex + ']'] = {
                    observe: PaneConstructor.prototype.constructorName,
                    visible: function(value) {
                        return value != 'hidden';
                    },
                    attributes: [{
                        name: 'class',
                        observe: PaneConstructor.prototype.constructorName
                    }]
                };
            }, this);
            bindings['.prev-pane-btn'] = {
                attributes: [{
                    name: 'disabled',
                    observe: 'activePaneIndex',
                    onGet: function(value) {
                        return value == 0;
                    }
                }]
            };
            bindings['.next-pane-btn'] = {
                observe: 'activePaneIndex',
                visible: function(value) {
                    return value != this.panesConstructors.length - 1;
                },
                attributes: [{
                    name: 'disabled',
                    observe: 'invalid'
                }]
            };
            bindings['.finish-btn'] = {
                observe: 'activePaneIndex',
                visible: function(value) {
                    return value == this.panesConstructors.length - 1;
                }
            };
            this.stickit(this.panesModel, bindings);
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.config = {
                NameAndRelease: {
                    name: {
                        type: 'custom',
                        value: '',
                        bind: 'cluster:name'
                    },
                    release: {
                        type: 'custom',
                        bind: {id: 'cluster:release'},
                        aliases: {
                            operating_system: 'NameAndRelease.release_operating_system',
                            roles: 'NameAndRelease.release_roles',
                            name: 'NameAndRelease.release_name'
                        }
                    }
                }
            };
            this.panesModel = new Backbone.Model({
                activePaneIndex: 0,
                maxAvailablePaneIndex: 0
            });
            this.updatePanesStatuses();
            this.cluster = new models.Cluster();
            this.settings = new models.Settings();
            this.panesModel.on('change:activePaneIndex', this.handlePaneIndexChange, this);
            this.panesModel.on('change:maxAvailablePaneIndex', function() {
                this.updatePanesStatuses();
                //FIXME: this should be moved to view method
                this.$('.wizard-footer .btn-success:visible').focus();
            }, this);
            this.model = new models.WizardModel(this.config);
            this.model.processConfig(this.config);
            this.configModels = {
                settings: this.settings,
                cluster: this.cluster,
                wizard: this.model,
                default: this.model,
                version: app.version
            };
            this.processRestrictions();
            this.attachModelListeners();
        },
        processPaneRestrictions: function() {
            _.each(this.config, function(pane, paneName) {
                this.panesModel.set(paneName, 'unavailable');
                _.each((pane.metadata || {}).restrictions, function(restriction) {
                    if (restriction.action == 'hide') {
                        if (utils.evaluateExpression(restriction.condition, this.configModels).value) {
                            this.panesModel.set(paneName, 'hidden');
                        }
                    }
                }, this);
            }, this);
        },
        attachModelListeners: function() {
            _.each(this.restrictions, function(paneConfig) {
                _.each(paneConfig, function(paneRestrictions) {
                    _.each(paneRestrictions, function(restriction) {
                        var evaluatedExpression = utils.evaluateExpression(restriction.condition, this.configModels, {strict: false});
                        _.invoke(evaluatedExpression.modelPaths, 'change', _.bind(this.handleTrackedAttributeChange, this));
                    }, this);
                }, this);
            }, this);
        },
        handleTrackedAttributeChange: function() {
            var maxIndex = this.panesModel.get('maxAvailablePaneIndex');
            var currentIndex = this.panesModel.get('activePaneIndex');
            if (maxIndex > currentIndex && this.panesModel.get([this.panesConstructors[maxIndex].name]) != 'current') {
                this.panesModel.set('maxAvailablePaneIndex', currentIndex);
                var listOfPanesToRestoreDefaults = this.getListOfPanesToRestore(currentIndex, maxIndex);
                this.model.restoreDefaultValues(listOfPanesToRestoreDefaults);
            }
        },
        processRestrictions: function() {
            var restrictions = this.restrictions = {};
            function processControlRestrictions(config, paneName, attribute) {
                var expandedRestrictions = config.restrictions = _.map(config.restrictions, utils.expandRestriction);
                restrictions[paneName][attribute] =
                    _.uniq(_.union(restrictions[paneName][attribute], expandedRestrictions), 'message');
            }
            _.each(this.config, function(paneConfig, paneName) {
                restrictions[paneName] = {};
                _.each(paneConfig, function(attributeConfig, attribute) {
                    if (attributeConfig.type == 'radio') {
                        _.each(attributeConfig.values, function(attributeValueConfig) {
                            processControlRestrictions(attributeValueConfig, paneName, attribute);
                        }, this);
                    } else {
                        processControlRestrictions(attributeConfig, paneName, attribute);
                    }
                }, this);
            }, this);
        },
        handlePaneIndexChange: function() {
            this.processBinds('wizard', this.activePane.constructorName);
            this.renderPane(this.panesConstructors[this.panesModel.get('activePaneIndex')]);
        },
        beforeClusterCreation: function() {
            var success = this.processBinds('cluster');
            return $.Deferred()[success ? 'resolve' : 'reject']();
        },
        beforeSettingsSaving: function() {
            var success = this.processBinds('settings');
            return $.Deferred()[success ? 'resolve' : 'reject']();
        },
        processBinds: function(prefix, paneNameToProcess) {
            var result = true;
            var processBind = _.bind(function(path, value) {
                if (path.slice(0, prefix.length) == prefix) {
                    utils.parseModelPath(path, this.configModels).set(value);
                }
            }, this);
            _.each(this.config, function(paneConfig, paneName) {
                if (paneNameToProcess && paneNameToProcess != paneName) {
                    return;
                }
                _.each(paneConfig, function(attributeConfig, attribute) {
                    var bind = attributeConfig.bind;
                    var value = this.model.get(paneName + '.' + attribute);
                    if (_.isString(bind)) {
                        // simple binding declaration - just copy the value
                        processBind(bind, value);
                    } else if (_.isPlainObject(bind)) {
                        // binding declaration for models
                        processBind(_.values(bind)[0], value.get(_.keys(bind)[0]));
                    } else if (_.isArray(bind)) {
                        // for the case of multiple bindings
                        if (attributeConfig.type != 'checkbox' || value) {
                            _.each(bind, function(bindItem) {
                                if (!_.isPlainObject(bindItem)) {
                                    processBind(bindItem, value);
                                } else {
                                    processBind(_.keys(bindItem)[0], _.values(bindItem)[0]);
                                }
                            }, this);
                        }
                    }
                    if (attributeConfig.type == 'radio') {
                        // radiobuttons can have values with their own bindings
                        _.each(_.find(attributeConfig.values, {data: value}).bind, function(bind) {
                            processBind(_.keys(bind)[0], _.values(bind)[0]);
                        });
                    }
                }, this);
            }, this);
            return result;
        },
        onKeydown: function(e) {
            if (e.which == 13) {
                e.preventDefault();
                this.nextPane();
            }
        },
        goToPane: function(index) {
            this.panesModel.set({
                invalid: false,
                activePaneIndex: index,
                maxAvailablePaneIndex: _.max([this.panesModel.get('maxAvailablePaneIndex'), this.panesModel.get('activePaneIndex'), index])
            });
        },
        getRelativePaneIndex: function(paneIndex, direction) {
            paneIndex += direction;
            if (this.panesModel.get(this.panesConstructors[paneIndex].name) == 'hidden') return this.getRelativePaneIndex(paneIndex, direction);
            return paneIndex;
        },
        prevPane: function() {
            this.goToPane(this.getRelativePaneIndex(this.panesModel.get('activePaneIndex'), -1));
        },
        nextPane: function() {
            this.activePane.processPaneData().done(_.bind(function() {
                this.goToPane(this.getRelativePaneIndex(this.panesModel.get('activePaneIndex'), 1));
            }, this));
        },
        onStepClick: function(e) {
            var paneIndex = parseInt($(e.currentTarget).data('pane'), 10),
                activePaneIndex = this.panesModel.get('activePaneIndex');

            // if last or one of the previous panes - not processing data
            if (activePaneIndex > paneIndex) {
                this.goToPane(paneIndex);
            } else {
                this.activePane.processPaneData().done(_.bind(function() {
                    this.goToPane(paneIndex);
                }, this));
            }
        },
        getListOfPanesToRestore: function(currentIndex, maxIndex) {
            var panesNames = [];
            _.each(this.panesConstructors, function(PaneConstructor, paneIndex) {
                if ((paneIndex <= maxIndex) && (paneIndex > currentIndex)) {
                    panesNames.push(PaneConstructor.prototype.constructorName);
                }
            }, this);
            return panesNames;
        },
        updatePanesStatuses: function() {
            _.each(this.panesConstructors, function(PaneConstructor, paneIndex) {
                var paneName = PaneConstructor.prototype.constructorName;
                if (this.panesModel.get(paneName) != 'hidden') {
                    if (paneIndex == this.panesModel.get('activePaneIndex')) {
                        this.panesModel.set(paneName, 'current');
                    } else if (paneIndex <= this.panesModel.get('maxAvailablePaneIndex')) {
                        this.panesModel.set(paneName, 'available');
                    } else {
                        this.panesModel.set(paneName, 'unavailable');
                    }
                }
            }, this);
        },
        renderPane: function(Pane) {
            this.tearDownRegisteredSubViews();
            var pane = this.activePane = new Pane({
                wizard: this,
                config: this.config[Pane.prototype.constructorName]
            });
            this.registerSubView(pane);
            this.updatePanesStatuses();
            this.$('.pane-content').html('').append(pane.render().el);
        },
        createCluster: function() {
            var cluster = this.cluster;
            this.beforeClusterCreation();
            var deferred = cluster.save();
            if (deferred) {
                this.$('.wizard-footer button').prop('disabled', true);
                deferred
                    .done(_.bind(function() {
                        this.collection.add(cluster);
                        this.settings.url = _.result(cluster, 'url') + '/attributes';
                        this.settings.fetch()
                            .then(_.bind(this.beforeSettingsSaving, this))
                            .then(_.bind(function() {
                                return this.settings.save(this.settings.attributes, {validate: false});
                            }, this))
                            .done(_.bind(function() {
                                this.$el.modal('hide');
                                app.navigate('#cluster/' + this.cluster.id + '/nodes', {trigger: true});
                            }, this))
                            .fail(_.bind(function() {
                                this.$el.modal('hide');
                                utils.showErrorDialog({message: i18n('dialog.create_cluster_wizard.configuration_failed_warning')});
                            }, this));
                    }, this))
                    .fail(_.bind(function(response) {
                        if (response.status == 409) {
                            this.$('.wizard-footer button').prop('disabled', false);
                            this.panesModel.set('activePaneIndex', 0);
                            cluster.trigger('invalid', cluster, {name: utils.getResponseText(response)});
                        } else {
                            this.$el.modal('hide');
                            utils.showErrorDialog({
                                title: i18n('dialog.create_cluster_wizard.create_cluster_error.title'),
                                message: response.status == 400 ? utils.getResponseText(response) : undefined
                            });
                        }
                    }, this));
            }
        },
        render: function() {
            this.$el.attr('tabindex', -1);
            this.$el.html(this.template({
                panesTitles: this.panesConstructors.map(function(Constructor) {return Constructor.prototype.title;}),
                currentStep: this.panesModel.get('activePaneIndex'),
                maxAvailableStep: this.panesModel.get('maxAvailablePaneIndex')
            })).i18n();
            if (!this.modalBound) {
                this.$el.on('hidden', _.bind(this.tearDown, this));
                this.$el.on('shown', _.bind(function() {
                    this.$('[autofocus]:first').focus();
                }, this));
                this.$el.modal({backdrop: 'static', background: true, keyboard: true});
                this.modalBound = true;
            }
            this.$('.wizard-footer .btn-success:visible').focus();
            this.renderPane(this.panesConstructors[this.panesModel.get('activePaneIndex')]);
            this.composeStickitBindings();
            return this;
        }
    });

    views.WizardPane = Backbone.View.extend({
        template: _.template(commonWizardTemplate),
        constructorName: 'WizardPane',
        initialize: function(options) {
            _.defaults(this, options);
            this.attachWarningListeners();
            this.processPaneAliases();
            this.wizard.model.on('invalid', function(model, errors) {
                _.each(errors, function(error) {
                    var input = this.$('input[name="' + error.field + '"]');
                    input.addClass('error');
                    input.parent().siblings('.description').addClass('hide');
                    input.parent().siblings('.validation-error').text(error.message).removeClass('hide');
                    this.wizard.panesModel.set('invalid', true);
                }, this);
            }, this);
            this.wizard.cluster.on('invalid', function(model, error) {
                _.each(error, function(message, field) {
                    this.$('*[name=' + field + ']').closest('.control-group').addClass('error').find('.help-inline').text(message);
                }, this);
                this.wizard.panesModel.set('invalid', true);
            }, this);
        },
        renderControls: function(config) {
            var controlsHtml = '';
            var configToUse = _.defaults(config, {
                labelClasses: '',
                descriptionClasses: '',
                description: ''
            });
            var controlTpl = _.template(controlTemplate);
            var sortedConfig = _.sortBy(_.pairs(this.config), function(configEntry) {
                return configEntry[1].weight;
            });
            _.each(sortedConfig, function(configEntry) {
                var attribute = configEntry[0];
                var attributeConfig = configEntry[1];
                switch (attributeConfig.type) {
                    case 'checkbox':
                        var conditions = _.pluck(attributeConfig.restrictions, 'condition');
                        controlsHtml += (controlTpl(_.extend(attributeConfig, {
                            pane: attribute,
                            labelClasses: configToUse.labelClasses,
                            disabled: this.checkRestrictions(conditions) ? 'disabled' : '',
                            descriptionClasses: configToUse.descriptionClasses,
                            label: attributeConfig.label,
                            hasDescription: _.isUndefined(configToUse.hasDescription) ? false : configToUse.hasDescription ,
                            description: attributeConfig.description
                        })));
                        break;
                    case 'radio':
                        _.each(attributeConfig.values, function(value) {
                            var shouldBeAdded = _.isUndefined(configToUse.additionalAttribute) ? true : attribute == configToUse.additionalAttribute,
                                conditions = _.pluck(value.restrictions, 'condition');
                            if (shouldBeAdded) {
                                controlsHtml += (controlTpl(_.extend(attributeConfig, {
                                    value: value.data,
                                    pane: attribute,
                                    labelClasses: configToUse.labelClasses || '',
                                    disabled: this.checkRestrictions(conditions) ? 'disabled' : '',
                                    descriptionClasses: configToUse.descriptionClasses || '',
                                    label: value.label,
                                    hasDescription: _.isUndefined(configToUse.hasDescription) ? false : configToUse.hasDescription,
                                    description: value.description || ''
                                })));
                            }
                        }, this);
                        break;
                    case 'text':
                    case 'password':
                        var newControlTemplate = _.template(textInputTemplate);
                        var newControlsHtml = '';
                        newControlsHtml = (newControlTemplate(_.extend(attributeConfig, {attribute: attribute})));
                        controlsHtml += newControlsHtml;
                        break;
                }
            }, this);
            return controlsHtml;
        },
        attachWarningListeners: function() {
            var attributesToObserve = [];
            _.each(this.wizard.restrictions[this.constructorName], function(paneConfig) {
                _.each(paneConfig, function(paneRestriction) {
                    var evaluatedExpression = utils.evaluateExpression(paneRestriction.condition, this.wizard.configModels, {strict: false});
                    _.each(evaluatedExpression.modelPaths, function(modelPath) {
                        attributesToObserve.push(modelPath.attribute);
                    }, this);
                }, this);
            }, this);
            _.each(_.uniq(attributesToObserve), function(condition) {
                this.wizard.model.on('change:' + condition, this.handleWarnings, this);
            }, this);
        },
        composePaneBindings: function() {
            this.bindings = {};
            _.each(this.config, function(attributeConfig, attribute) {
                this.bindings['[name=' + attribute + ']'] = {observe: this.constructorName + '.' + attribute};
                switch (attributeConfig.type) {
                    case 'radio':
                        _.each(attributeConfig.values, function(value) {
                            this.createRestrictionBindings(value.restrictions, {name: attribute, value: value.data});
                        }, this);
                        break;
                    case 'checkbox':
                        this.createRestrictionBindings(attributeConfig.restrictions, {name: attribute});
                        break;
                    case 'text':
                    case 'password':
                        this.createRestrictionBindings(attributeConfig.restrictions, {'data-attribute': attribute});
                        break;
                }
            }, this);
            this.stickit(this.wizard.model);
        },
        checkRestrictions: function(conditions) {
            return _.any(conditions, function(condition) {
                return utils.evaluateExpression(condition, this.wizard.configModels).value;
            }, this);
        },
        createRestrictionBindings: function(controlRestrictions, selectorOptions) {
            _.each(_.groupBy(controlRestrictions, 'action'), function(restrictions, action) {
                var conditions = _.pluck(restrictions, 'condition');
                var attributesToObserve = _.uniq(_.flatten(_.map(conditions, function(condition) {
                    return _.keys(utils.evaluateExpression(condition, this.wizard.configModels).modelPaths);
                }, this)));
                var selector = _.map(selectorOptions, function(value, key) {
                    return '[' + key + '=' + value + ']';
                }, this).join('');
                switch (action) {
                    case 'disable':
                        this.bindings[selector] = _.extend(this.bindings[selector] || {}, {
                            attributes: [{
                                name: 'disabled',
                                observe: attributesToObserve,
                                onGet: function() {
                                    return this.checkRestrictions(conditions);
                                }
                            }]
                        });
                        break;
                    case 'hide':
                        this.bindings[selector] = _.extend(this.bindings[selector] || {}, {
                            observe: attributesToObserve,
                            visible: function() {
                                return !this.checkRestrictions(conditions);
                            }
                        });
                        break;
                }
            }, this);
        },
        processPaneAliases: function() {
            _.each(this.config, function(attributeConfig, attribute) {
                _.each(attributeConfig.aliases, function(wizardModelAttribute, modelAttribute) {
                    this.wizard.model.on('change:' + this.constructorName + '.' + attribute, function(wizardModel, model) {
                        wizardModel.set(wizardModelAttribute, model.get(modelAttribute));
                    }, this);
                }, this);
            }, this);
        },
        processPaneData: function() {
            if (this.wizard.model.isValid({
                    config: this.config,
                    paneName: this.constructorName
                })) {
                return $.Deferred().resolve();
            }
            return $.Deferred().reject();
        },
        buildTranslationParams: function() {
            var result = {};
            _.each(this.wizard.model.attributes, function(paneConfig, paneName) {
                _.each(paneConfig, function(value, attribute) {
                    if (!_.isObject(value)) {
                        var attributeConfig = this.wizard.config[paneName][attribute];
                        if (attributeConfig && attributeConfig.type == 'radio') {
                            result[paneName + '.' + attribute] = i18n(_.find(attributeConfig.values, {data: value}).label);
                        } else if (attributeConfig && attributeConfig.label) {
                            result[paneName + '.' + attribute] = i18n(attributeConfig.label);
                        } else {
                            result[paneName + '.' + attribute] = value;
                        }
                    }
                }, this);
            }, this);
            return result;
        },
        handleWarnings: function() {
            this.$('.alert:not(.alert-regular)').remove();
            var messages = [];
            _.each(this.wizard.restrictions[this.constructorName], function(paneConfig) {
                _.each(paneConfig, function(paneRestriction) {
                    var result = utils.evaluateExpression(paneRestriction.condition, this.wizard.configModels).value;
                    if (result) {
                        messages.push(paneRestriction.message);
                    }
                }, this);
            }, this);
            if (messages.length) {
                var translationParams = this.buildTranslationParams();
                _.each(_.compact(_.uniq(messages)), function(message) {
                    this.showWarning(i18n(message, translationParams));
                }, this);
            }
        },
        showWarning: function(message) {
            this.$('.form-horizontal').before(_.template(warningTemplate, {message: message}));
        },
        renderCustomElements: function() {
            this.$('.control-group').append(this.renderControls({}));
        },
        onWizardChange: function() {
            this.$('input.error').removeClass('error');
            this.$('.parameter-description').removeClass('hide');
            this.$('.validation-error').addClass('hide');
            this.wizard.panesModel.set('invalid', false);
            if (this.$('input[type=text], input[type=password]').is(':focus')) {
                this.wizard.model.isValid({
                    config: this.config,
                    paneName: this.constructorName
                });
            }
        },
        render: function() {
            this.$el.html(this.template());
            this.renderCustomElements();
            this.$el.i18n();
            this.handleWarnings();

            if (!_.isUndefined(this.releases) && this.releases.length) {
                this.releases = new Backbone.Collection(this.releases.where({is_deployable: true}));
            }
            this.composePaneBindings();
            return this;
        }
    });
    Cocktail.mixin(views.WizardPane, viewMixins.toggleablePassword);

    clusterWizardPanes.NameAndRelease = views.WizardPane.extend({
        constructorName: 'NameAndRelease',
        title: 'dialog.create_cluster_wizard.name_release.title',
        template: _.template(clusterNameAndReleasePaneTemplate),
        events: {
            'keydown input': 'onInputKeydown'
        },
        processPaneData: function() {
            var success = this.createCluster();
            return $.Deferred()[success ? 'resolve' : 'reject']();
        },
        createCluster: function() {
            this.$('.control-group').removeClass('error').find('.help-inline').text('');
            var success = true;
            var name = this.wizard.model.get('NameAndRelease.name');
            var release = this.wizard.model.get('NameAndRelease.release').id;
            this.wizard.cluster.on('invalid', function() {success = false;}, this);
            if (this.wizard.collection.findWhere({name: name})) {
                this.wizard.cluster.trigger('invalid', this.wizard.cluster,
                    {name: i18n('dialog.create_cluster_wizard.name_release.existing_environment', {name: name})});
            }
            success = success && this.wizard.cluster.set({
                name: name,
                release: release
            }, {validate: true});
            return success;
        },
        onInputKeydown: function() {
            this.$('.control-group.error').removeClass('error');
            this.$('.help-inline').html('');
            this.wizard.panesModel.set('invalid', false);
        },
        composePaneBindings: function() {
            this.constructor.__super__.composePaneBindings.apply(this, arguments);
            this.bindings['[name=release]'].selectOptions = {
                collection: function() {
                    return this.releases.map(function(release, index) {
                        var label = release.get('name') + ' (' + release.get('version') + ')';
                        // FIXME (morale): dirty hack for #1403108
                        if (index == 0) label += ' (default)';
                        return {
                            value: release,
                            label: label
                        };
                    });
                }
            };
            this.stickit(this.wizard.model);
        },
        initialize: function() {
            this.constructor.__super__.initialize.apply(this, arguments);
            this.releases = this.wizard.releases || new models.Releases();
            if (!this.releases.length) {
                this.wizard.releases = this.releases;
                this.releases.fetch();
            }
            this.releases.once('sync', function() {
                this.render();
                $('input[name=name]').focus();
            }, this);
            this.wizard.model.on('change:NameAndRelease.release', this.updateRelease, this);
        },
        updateConfig: function(config) {
            var name = this.wizard.model.get('NameAndRelease.name');
            var release = this.wizard.model.get('NameAndRelease.release');
            _.extend(this.wizard.config, _.cloneDeep(config));
            this.wizard.model.off(null, null, this);
            this.wizard.processPaneRestrictions();
            this.wizard.model.initialize(this.wizard.config);
            this.wizard.model.processConfig(this.wizard.config);
            this.wizard.model.set({
                'NameAndRelease.name': name,
                'NameAndRelease.release': release
            });
            this.wizard.panesModel.set({
                activePaneIndex: 0,
                maxAvailablePaneIndex: 0
            });
            this.wizard.processRestrictions();
            this.wizard.attachModelListeners();
            this.wizard.renderPane(this.constructor);
        },
        updateRelease: function() {
            var release = this.wizard.model.get('NameAndRelease.release');
            this.updateConfig(release.get('wizard_metadata'));
        },
        render: function() {
            this.constructor.__super__.render.call(this);
            if (this.releases.length) {
                var release = this.wizard.model.get('NameAndRelease.release');
                if (!release) {
                    this.wizard.model.set('NameAndRelease.release', this.releases.first());
                } else {
                    this.$('.release-description').text(release.get('description'));
                }
            }
            return this;
        }
    });

    clusterWizardPanes.Mode = views.WizardPane.extend({
        constructorName: 'Mode',
        template: _.template(modePaneTemplate),
        title: 'dialog.create_cluster_wizard.mode.title',
        initialize: function(options) {
            this.constructor.__super__.initialize.call(this, options);
            this.wizard.model.on('change:Mode.mode', this.updateModeDescription, this);
        },
        updateModeDescription: function() {
            var description = this.wizard.model.get('NameAndRelease.release').get('modes_metadata')[this.wizard.model.get('Mode.mode')].description;
            this.$('.mode-description').text(description);
        },
        renderCustomElements: function() {
            this.$('.mode-control-group .span5').append(this.renderControls({labelClasses: 'setting'})).i18n();
            this.updateModeDescription();
        }
    });

    clusterWizardPanes.Compute = views.WizardPane.extend({
        constructorName: 'Compute',
        title: 'dialog.create_cluster_wizard.compute.title',
        initialize: function(options) {
            this.constructor.__super__.initialize.call(this, options);
            this.wizard.model.on('change:Compute.*', this.onWizardChange, this);
            this.events = _.extend(this.events, {
                'focus input': 'onWizardChange'
            });
        },
        renderCustomElements: function() {
            this.$('.control-group').append(this.renderControls({hasDescription: true})).i18n();
        }
    });

    clusterWizardPanes.Network = views.WizardPane.extend({
        constructorName: 'Network',
        template: _.template(networkPaneTemplate),
        title: 'dialog.create_cluster_wizard.network.title',
        renderCustomElements: function() {
            this.$('.control-group').append(this.renderControls({hasDescription: true}));
        }
    });

    clusterWizardPanes.Storage = views.WizardPane.extend({
        constructorName: 'Storage',
        template: _.template(storagePaneTemplate),
        title: 'dialog.create_cluster_wizard.storage.title',
        renderCustomElements: function() {
            this.$('.control-group .cinder h5').after(this.renderControls({
                hasDescription: false,
                additionalAttribute: 'cinder'
            }));
            this.$('.control-group .glance h5').after(this.renderControls({
                hasDescription: false,
                additionalAttribute: 'glance'
            }));
        }
    });

    clusterWizardPanes.AdditionalServices = views.WizardPane.extend({
        constructorName: 'AdditionalServices',
        title: 'dialog.create_cluster_wizard.additional.title',
        renderCustomElements: function() {
            this.$('.control-group').append(this.renderControls({
                hasDescription: true,
                additionalAttribute: 'services'
            })).i18n();
        }
    });

    clusterWizardPanes.Ready = views.WizardPane.extend({
        constructorName: 'Ready',
        title: 'dialog.create_cluster_wizard.ready.title',
        template: _.template(clusterReadyPaneTemplate),
        processPaneData: function() {
            var success = this.wizard.createCluster();
            return $.Deferred()[success ? 'resolve' : 'reject']();
        }
    });

    views.CreateClusterWizard.prototype.panesConstructors = [
        clusterWizardPanes.NameAndRelease,
        clusterWizardPanes.Mode,
        clusterWizardPanes.Compute,
        clusterWizardPanes.Network,
        clusterWizardPanes.Storage,
        clusterWizardPanes.AdditionalServices,
        clusterWizardPanes.Ready
    ];

    return views;
});
