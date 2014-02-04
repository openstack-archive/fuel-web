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
    'require',
    'utils',
    'models',
    'views/dialogs',
    'text!templates/dialogs/create_cluster_wizard.html',
    'text!templates/dialogs/create_cluster_wizard/name_and_release.html',
    'text!templates/dialogs/create_cluster_wizard/common_wizard_panel.html',
    'text!templates/dialogs/create_cluster_wizard/mode.html',
    'text!templates/dialogs/create_cluster_wizard/storage.html',
    'text!templates/dialogs/create_cluster_wizard/ready.html',
    'text!templates/dialogs/create_cluster_wizard/control_template.html',
    'text!templates/dialogs/create_cluster_wizard/warning.html',
    'text!js/wizard.json'
],
function(require, utils, models, dialogs, createClusterWizardTemplate, clusterNameAndReleasePaneTemplate, commonWizardTemplate, modePaneTemplate, storagePaneTemplate, clusterReadyPaneTemplate, controlTemplate, warningTemplate, wizardInfo) {
    'use strict';

    var views = {};

    var clusterWizardPanes = {};

    views.CreateClusterWizard = dialogs.Dialog.extend({
        className: 'modal fade create-cluster-modal',
        template: _.template(createClusterWizardTemplate),
        modalOptions: {backdrop: 'static'},
        events: {
            'keydown': 'onInputKeydown',
            'click .next-pane-btn': 'nextPane',
            'click .prev-pane-btn': 'prevPane',
            'click .wizard-step.available': 'onStepClick',
            'click .finish-btn': 'createCluster'
        },
        composeStickitBindings: function() {
            var bindings = {};
            _.each(_.keys(this.config), function(paneConstructor, paneIndex) {
                bindings['.wizard-step[data-pane=' + paneIndex + ']'] = {
                    attributes: [{
                        name: 'class',
                        observe: paneConstructor
                    }]
                };
            }, this);
            bindings['.prev-pane-btn'] = {
                attributes: [{
                    name: 'disabled',
                    observe: 'activePaneIndex',
                    onGet: function(value, options) {
                        return value == 0;
                    }
                }]
            };
            bindings['.next-pane-btn'] = {
                observe: 'activePaneIndex',
                visible: function(value, options) {
                    return value != this.panesConstructors.length - 1;
                }
            };
            bindings['.finish-btn'] = {
                observe: 'activePaneIndex',
                visible: function(value, options) {
                    return value == this.panesConstructors.length - 1;
                }
            };
            this.stickit(this.panesModel, bindings);
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.config = JSON.parse(wizardInfo);
            this.panesModel = new Backbone.Model({
                activePaneIndex: 0,
                maxAvailablePaneIndex: 0
            });
            this.updatePanesStatuses();
            this.settings = new models.Settings();
            this.panesModel.on('change:activePaneIndex', this.handlePaneIndexChange, this);
            this.panesModel.on('change:maxAvailablePaneIndex', function() {
                this.updatePanesStatuses();
                this.$('.wizard-footer .btn-success:visible').focus();
            }, this);
            this.model = new models.WizardModel();
            this.model.processConfig(this.config);
            this.calculateDependencies();
            _.each(this.trackedAttributes, function(attribute) {
                this.model.on('change:' + attribute, this.handleTrackedAttributeChange, this);
            }, this);
        },
        handleTrackedAttributeChange: function() {
            var maxIndex = this.panesModel.get('maxAvailablePaneIndex');
            var currentIndex = this.panesModel.get('activePaneIndex');
            if ((maxIndex > currentIndex) && _.contains(this.trackedPanes, this.activePane.constructorName)) {
                this.panesModel.set('maxAvailablePaneIndex', currentIndex);
            }
        },
        calculateDependencies: function() {
            var trackedAttributes = [];
            function processRestrictions(restrictions) {
                _.each(restrictions, function(restriction) {
                    trackedAttributes.push(_.keys(restriction.condition)[0]);
                });
            }
            _.each(this.config, function(paneConfig, paneName) {
                _.each(paneConfig, function(attributeConfig, attribute) {
                    _.each(attributeConfig.restrictions, processRestrictions);
                    if (attributeConfig.type == 'radio') {
                        _.each(attributeConfig.values, function(attributeValueConfig) {
                            _.each(attributeValueConfig.restrictions, processRestrictions);
                        });
                    }
                }, this);
            }, this);
            this.trackedAttributes = _.uniq(trackedAttributes);
            this.trackedPanes = _.uniq(_.map(this.trackedAttributes, function(attribute) {
                return attribute.split('.')[0];
            }));
        },
        handlePaneIndexChange: function() {
            this.renderPane(this.panesConstructors[this.panesModel.get('activePaneIndex')]);
        },
        beforeClusterCreation: function() {
            var success = this.processBinds('cluster');
            return $.Deferred()[success ? 'resolve' : 'reject']();
        },
        beforeSettingsSaving: function(settings) {
            var success = this.processBinds('settings');
            return $.Deferred()[success ? 'resolve' : 'reject']();
        },
        processBinds: function(prefix) {
            var result = true;
            var configModels = {settings: this.settings, cluster: this.cluster};
            function processBind(path, value) {
                if (path.slice(0, prefix.length) == prefix) {
                    utils.parseModelPath(path, configModels).set(value);
                }
            }
            _.each(this.config, function(paneConfig, paneName) {
                _.each(paneConfig, function(attributeConfig, attribute) {
                    var bind = attributeConfig.bind;
                    var value = this.model.get(paneName + '.' + attribute);
                    if (_.isString(bind)) {
                        // simple binding declaration - just copy the value
                        processBind(bind, value);
                    } else if (_.isPlainObject(bind)) {
                        // binding declaration for models
                        processBind(_.values(bind)[0], value.get(_.keys(bind)[0]));
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
        onInputKeydown: function(e) {
            if (e.which == 13) {
                e.preventDefault();
                this.nextPane();
            }

        },
        goToPane: function(index) {
            this.panesModel.set({
                activePaneIndex: index,
                maxAvailablePaneIndex: _.max([this.panesModel.get('maxAvailablePaneIndex'), this.panesModel.get('activePaneIndex'), index])
            });
        },
        prevPane: function() {
            this.goToPane(this.panesModel.get('activePaneIndex') - 1);
        },
        nextPane: function() {
            this.activePane.processPaneData().done(_.bind(function() {
                this.goToPane(this.panesModel.get('activePaneIndex') + 1);
            }, this));
        },
        onStepClick: function(e) {
            var paneIndex = parseInt($(e.currentTarget).data('pane'), 10);
            if (this.panesModel.get('activePaneIndex') != this.panesConstructors.length - 1) {
                this.activePane.processPaneData().done(_.bind(function() {
                    this.goToPane(paneIndex);
                }, this));
            }
            else {
                this.goToPane(paneIndex);
            }
        },
        updatePanesStatuses: function() {
            _.each(_.keys(this.config), function(paneName, paneIndex) {
                if (paneIndex == this.panesModel.get('activePaneIndex')) {
                    this.panesModel.set(paneName, 'current');
                } else if (paneIndex <= this.panesModel.get('maxAvailablePaneIndex')) {
                    this.panesModel.set(paneName, 'available');
                } else {
                    this.panesModel.set(paneName, 'unavailable');
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
            pane.checkForRestrictions();

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
                                return this.settings.save();
                            }, this))
                            .done(_.bind(function() {
                                this.$el.modal('hide');
                            }, this))
                            .fail(_.bind(function() {
                                this.displayErrorMessage({message: $.t('dialog.create_cluster_wizard.same_name_warning')});
                            }, this));
                    }, this))
                    .fail(_.bind(function(response) {
                        if (response.status == 409) {
                            this.$('.wizard-footer button').prop('disabled', false);
                            this.panesModel.set('activePaneIndex', 0);
                            cluster.trigger('invalid', cluster, {name: response.responseText});
                        } else if (response.status == 400) {
                            this.displayErrorMessage({message: response.responseText});
                        } else {
                            this.displayError();
                        }
                    }, this));
            }
        },
        render: function() {
            var panesTitles = _.map(this.panesConstructors, function(PaneConstructor) {
                return PaneConstructor.prototype.title;
            });
            this.constructor.__super__.render.call(this, _.extend({
                panesTitles: panesTitles,
                currentStep: this.panesModel.get('activePaneIndex'),
                maxAvailableStep: this.panesModel.get('maxAvailablePaneIndex')
            }));
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
            this.processPaneAliases();
        },
        renderControls: function(config) {
            var controlsHtml = '';
            var configToUse = _.defaults(config, {
                labelClasses: '',
                descriptionClasses: '',
                description: ''

            });
            var controlTpl = _.template(controlTemplate);
            _.each(this.config, function(attributeConfig, attribute) {
                if (attributeConfig.type == 'checkbox') {
                    controlsHtml += (controlTpl(_.extend(attributeConfig, {
                        pane: attribute,
                        labelClasses: configToUse.labelClasses,
                        descriptionClasses: configToUse.descriptionClasses,
                        label: attributeConfig.label,
                        hasDescription: _.isUndefined(configToUse.hasDescription) ? false : configToUse.hasDescription ,
                        description: attributeConfig.description
                    })));
                }
                else {
                    _.each(attributeConfig.values, function(value, valueIndex) {
                        var shouldBeAdded = _.isUndefined(configToUse.additionalAttribute) ? true : attribute == configToUse.additionalAttribute;
                        if (shouldBeAdded) {
                            controlsHtml += (controlTpl(_.extend(attributeConfig, {
                                value: value.data,
                                pane: attribute,
                                labelClasses: configToUse.labelClasses || '',
                                descriptionClasses: configToUse.descriptionClasses || '',
                                label: value.label,
                                hasDescription: _.isUndefined(configToUse.hasDescription) ? false : configToUse.hasDescription,
                                description: value.description || ''
                            })));
                        }
                    }, this);
                }
            }, this);
            return controlsHtml;
        },
        composePaneBindings: function() {
            this.bindings = {};
            _.each(this.config, function(attributeConfig, attribute) {
                this.bindings['[name=' + attribute + ']'] = {observe: this.constructorName + '.' + attribute};
            }, this);
            if (_.pluck(this.config, 'type')[0] == 'radio') {
                var restrictions = _.compact(_.pluck(_.pluck(this.config, 'values')[0], 'restrictions'));
                if (restrictions.length) {
                     this.prepareDisabledBindings('radio');
                }
            }
            if (_.pluck(this.config, 'type')[0] == 'checkbox') {
                if (_.compact(_.pluck(this.config, 'restrictions')).length) {
                     this.prepareDisabledBindings('checkbox');
                }
            }
            this.stickit(this.wizard.model);
        },
        prepareDisabledBindings: function(type) {
            _.each(this.config, function(paneAttribute, paneAttributeName) {
                if (type == 'checkbox') {
                    if (!_.isUndefined(paneAttribute.restrictions)) {
                        this.composeDisabledBindings(paneAttribute.restrictions, 'name', paneAttributeName);
                    }
                    else {
                        this.bindings['[name=' + paneAttributeName + ']'] = {observe: this.constructorName + '.' + paneAttributeName};
                    }
                }
                if (type == 'radio') {
                    _.each(paneAttribute.values, function(value) {
                        if (!_.isUndefined(value.restrictions)) {
                            this.composeDisabledBindings(value.restrictions, 'value', value.data);
                        }
                        else {
                            this.bindings['[value=' + value.data + ']'] = {observe: this.constructorName + '.' + paneAttributeName};
                        }
                    }, this);
                }
            }, this);
        },
        composeDisabledBindings: function(restrictions, attributeName, elementName) {
            if (restrictions.conflicts) {
                this.createDisabledBindings(restrictions.conflicts, attributeName, elementName);
            }
            else if (restrictions.depends) {
                this.createDisabledBindings(restrictions.depends, attributeName, elementName);
            }
        },
        createDisabledBindings: function(restrictedAttributes, attributeName, elementName) {
            var attributesToObserve, restrictedValues, restrictedList;
            attributesToObserve = _.map(_.pluck(restrictedAttributes, 'condition'), function(elem) {return _.keys(elem)[0];});
            restrictedList = _.map(restrictedAttributes, function(elem) {return elem.condition;});
            restrictedValues = _.map(restrictedList, function(conflict) {return _.values(conflict)[0];});
            this.bindings['[' + attributeName + '=' + elementName +']'] = {
                observe: this.constructorName + '.' + elementName,
                attributes: [{
                    name: 'disabled',
                    observe: attributesToObserve,
                    onGet: function(values) {
                        return !!_.intersection(restrictedValues, values).length;
                    }
                }]
            };
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
            return $.Deferred().resolve();
        },
        checkForRestrictions: function() {
            _.each(this.config, function(paneAttribute) {
                var restrictions = _.compact(_.pluck(paneAttribute.values, 'restrictions'));
                if (paneAttribute.type == 'checkbox') {
                    if (!_.isUndefined(paneAttribute.restrictions)) {
                        this.handleWarnings(paneAttribute.restrictions);
                    }
                }
               _.each(restrictions, this.handleWarnings, this);
            }, this);
        },
        handleWarnings: function(restrictions) {
            var translationParams = {};
            function processPiece(json) {
                var result = [];
                 _.each(json, function(attributeValue, attributeKey) {
                    result.push(_.map(attributeValue, function(secondLevelValue, secondLevelKey) {
                        if (!_.isObject(secondLevelValue)) {
                            return attributeKey + '.' + secondLevelKey;
                        }
                    }, this));
                 });
                return _.compact(_.flatten(result));
            }
             var keys = processPiece(this.wizard.model.toJSON());
            _.each(keys, function(key) {
                translationParams[key] = this.wizard.model.get(key);
            }, this);
            _.each(restrictions.conflicts, function(conflict) {
                if (this.wizard.model.get(_.keys(conflict.condition)[0]) == _.values(conflict.condition)[0]) {
                    this.showWarning($.t(conflict.warning, translationParams));
                }
            }, this);
            _.each(restrictions.depends, function(conflict) {
                if (!_.contains(this.wizard.model.get(_.keys(conflict.condition)[0]), _.values(conflict.condition)[0])) {
                    this.showWarning($.t(conflict.warning, translationParams));
                }
            }, this);
        },
        showWarning: function(warningText) {
            if (!$('.alert').length) {
                this.$('.form-horizontal').before(_.template(warningTemplate, {warningMessage: warningText}));
            }
        },
        render: function() {
            this.$el.html(this.template()).i18n();
            return this;
        }
    });

    clusterWizardPanes.NameAndRelease = views.WizardPane.extend({
        constructorName: 'NameAndRelease',
        title:'dialog.create_cluster_wizard.name_release.title',
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
            this.wizard.cluster = new models.Cluster();
            this.wizard.cluster.on('invalid', function(model, error) {
                success = false;
                _.each(error, function(message, field) {
                    $('*[name=' + field + ']').closest('.control-group').addClass('error').find('.help-inline').text(message);
                }, this);
            }, this);
            if (this.wizard.collection.findWhere({name: name})) {
                this.wizard.cluster.trigger('invalid', this.wizard.cluster, {name: $.t('dialog.create_cluster_wizard.name_release.existing_environment', {name: name})});
            }
            success = success && this.wizard.cluster.set({
                name: name,
                release: release
            }, {validate: true});
            return success;
        },
        onInputKeydown: function(e) {
            this.$('.control-group.error').removeClass('error');
            this.$('.help-inline').html('');
        },
        composePaneBindings: function() {
            this.constructor.__super__.composePaneBindings.apply(this, arguments);
            this.bindings['[name=release]'].selectOptions = {
                collection: function() {
                    return this.releases.map(function(release) {
                        return {
                            value: release,
                            label: release.get('name') + ' (' + release.get('version') + ')'
                        };
                    });
                }
            };
            this.stickit(this.wizard.model);
        },
        initialize: function(options) {
            this.constructor.__super__.initialize.apply(this, arguments);
            this.releases = this.wizard.releases || new models.Releases();
            if (!this.releases.length) {
                this.wizard.releases = this.releases;
                this.releases.fetch();
            }
            this.releases.on('sync', this.render, this);
            this.wizard.model.on('change:NameAndRelease.release', this.updateReleaseDescription, this);
        },
        updateReleaseDescription: function(model, value) {
            var description = this.wizard.model.get('NameAndRelease.release').get('description');
            this.$('.release-description').text(description);
        },
        render: function() {
            this.$el.html(this.template()).i18n();
            if (this.releases.length) {
                if (!this.wizard.model.get('NameAndRelease.release')) {
                    this.wizard.model.set('NameAndRelease.release', this.releases.first());
                } else {
                    this.updateReleaseDescription();
                }
                this.composePaneBindings();
            }
            return this;
        }
    });

    clusterWizardPanes.Mode = views.WizardPane.extend({
        constructorName: 'Mode',
        template: _.template(modePaneTemplate),
        title: 'dialog.create_cluster_wizard.mode.title',
        updateModeDescription: function() {
            var description = this.wizard.model.get('NameAndRelease.release').get('modes_metadata')[this.wizard.model.get('Mode.mode')].description;
            this.$('.mode-description').text(description);
        },
        render: function() {
            this.$el.html(this.template());
            this.$('.mode-control-group .span5').append(this.renderControls({labelClasses: 'setting', descriptionClasses:'openstack-sub-title'})).i18n();
            this.composePaneBindings();
            this.wizard.model.on('change:Mode.mode', this.updateModeDescription, this);
            this.updateModeDescription();
            return this;
        }
    });

    clusterWizardPanes.Compute = views.WizardPane.extend({
        constructorName: 'Compute',
        title: 'dialog.create_cluster_wizard.compute.title',
        render: function() {
            this.$el.html(this.template());
            this.$('.control-group').append(this.renderControls({hasDescription: true})).i18n();
            this.composePaneBindings();
            return this;
        }
    });

    clusterWizardPanes.Network = views.WizardPane.extend({
        constructorName: 'Network',
        template: _.template(commonWizardTemplate),
        title: 'dialog.create_cluster_wizard.network.title',
        render: function() {
            this.$el.html(this.template());
            this.$('.control-group').append(this.renderControls({})).i18n();
            this.composePaneBindings();
            return this;
        }
    });

    clusterWizardPanes.Storage = views.WizardPane.extend({
        constructorName: 'Storage',
        template: _.template(storagePaneTemplate),
        title: 'dialog.create_cluster_wizard.storage.title',
        render: function() {
            this.$el.html(this.template());
            this.$('.control-group .cinder h5').after(this.renderControls({
                hasDescription: false,
                additionalAttribute: 'cinder'
            }));
            this.$('.control-group .glance h5').after(this.renderControls({
                hasDescription: false,
                additionalAttribute: 'glance'
            }));
            this.$el.i18n();
            this.composePaneBindings();
            return this;
        }
    });

    clusterWizardPanes.AdditionalServices = views.WizardPane.extend({
        constructorName: 'AdditionalServices',
        title: 'dialog.create_cluster_wizard.additional.title',
        render: function() {
            this.$el.html(this.template());
            this.$('.control-group').append(this.renderControls({
                hasDescription: true,
                additionalAttribute: 'services'
            })).i18n();
            this.composePaneBindings();
            return this;
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
