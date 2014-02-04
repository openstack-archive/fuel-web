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
    'text!templates/dialogs/create_cluster_wizard/ready.html',
    'text!js/wizard.json'
],
function(require, utils, models, dialogs, createClusterWizardTemplate, clusterNameAndReleasePaneTemplate, commonWizardTemplate, clusterReadyPaneTemplate, wizardInfo) {
    'use strict';

    var views = {};

    var wizardConfig = JSON.parse(wizardInfo);

    var clusterWizardPanes = {};

    views.CreateClusterWizard = dialogs.Dialog.extend({
        className: 'modal fade create-cluster-modal',
        template: _.template(createClusterWizardTemplate),
        templateHelpers: _.pick(utils, 'floor'),
        modalOptions: {backdrop: 'static'},
        events: {
            'keydown input': 'onInputKeydown',
            'click .next-pane-btn': 'nextPane',
            'click .prev-pane-btn': 'prevPane',
            'click .wizard-step.available': 'onStepClick',
            'click .finish-btn': 'createCluster'
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.activePaneIndex = null;
            this.maxAvaialblePaneIndex = 0;
            this.panes = [];
            _.each(this.panesConstructors, function(Pane) {
                var pane = new Pane({wizard: this});
                this.registerSubView(pane);
                this.panes.push(pane);
                pane.render();
            }, this);
        },
        onInputKeydown: function(e) {
            if (e.which == 13) {
                e.preventDefault();
                this.nextPane();
            }
        },
        onStepClick: function(e) {
            var paneIndex = parseInt($(e.currentTarget).data('pane'), 10);
            this.activePane().processPaneData().done(_.bind(function() {
                this.goToPane(paneIndex);
            }, this));
        },
        findPane: function(PaneConstructor) {
            return _.find(this.panes, function(pane) {
                return pane instanceof PaneConstructor;
            });
        },
        activePane: function() {
            return this.panes[this.activePaneIndex];
        },
        goToPane: function(index) {
            this.maxAvaialblePaneIndex = _.max([this.maxAvaialblePaneIndex, this.activePaneIndex, index]);
            this.activePaneIndex = index;
            this.render();
        },
        nextPane: function() {
            this.activePane().processPaneData().done(_.bind(function() {
                this.goToPane(this.activePaneIndex + 1);
            }, this));
        },
        prevPane: function() {
            this.goToPane(this.activePaneIndex - 1);
        },
        createCluster: function() {
            var cluster = this.findPane(clusterWizardPanes.NameAndRelease).cluster;
            _.invoke(this.panes, 'beforeClusterCreation', cluster);
            var deferred = cluster.save();
            if (deferred) {
                this.$('.wizard-footer button').prop('disabled', true);
                deferred
                    .done(_.bind(function() {
                        this.collection.add(cluster);
                        var settings = new models.Settings();
                        settings.url = _.result(cluster, 'url') + '/attributes';
                        settings.fetch()
                            .then(_.bind(function() {
                                return $.when.apply($, _.invoke(this.panes, 'beforeSettingsSaving', settings));
                            }, this))
                            .then(_.bind(function() {
                                return settings.save();
                            }, this))
                            .done(_.bind(function() {
                                this.$el.modal('hide');
                            }, this))
                            .fail(_.bind(function() {
                                this.displayErrorMessage({message: $.t('dialog.create_cluster_wizard.environment_configuration_failed')});
                            }, this));
                    }, this))
                    .fail(_.bind(function(response) {
                        if (response.status == 409) {
                            this.$('.wizard-footer button').prop('disabled', false);
                            this.goToPane(0);
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
            if (_.isNull(this.activePaneIndex)) {
                this.activePaneIndex = 0;
            }
            var pane = this.activePane();
            var currentStep = this.activePaneIndex + 1;
            var maxAvailableStep = this.maxAvaialblePaneIndex + 1;
            var totalSteps = this.panes.length;
            this.constructor.__super__.render.call(this, _.extend({
                panes: this.panes,
                currentStep: currentStep,
                totalSteps: totalSteps,
                maxAvailableStep: maxAvailableStep
            }, this.templateHelpers));
            this.$('.pane-content').append(pane.el);
            this.$('.prev-pane-btn').prop('disabled', !this.activePaneIndex);
            this.$('.next-pane-btn').toggle(currentStep != totalSteps);
            this.$('.finish-btn').toggle(currentStep == totalSteps);
            this.$('.wizard-footer .btn-success:visible').focus();
            return this;
        }
    });

    views.WizardPane = Backbone.View.extend({
        template: _.template(commonWizardTemplate),
        constructorName: 'WizardPane',
        configurableOptions: {},
        model: new models.WizardPaneModel(wizardConfig),
        initialize: function(options) {
            _.defaults(this, options);
            this.initializeModels();
        },
        processPaneData: function() {
            return $.Deferred().resolve();
        },
        beforeClusterCreation: function(cluster) {
            return $.Deferred().resolve();
        },
        beforeSettingsSaving: function(cluster) {
//            TODO: deal with BIND here
            var bindingOptions = _.pluck(this.configurableOptions, 'bind');
             if (bindingOptions.length) {
                 _.each(bindingOptions, _.bind(function(bind) {
                     if (_.isPlainObject(bind, bindKey)) {

                     }
                     else if(_.isArray(bind)) {

                     }
                     else {

                     }
                 }, this));
             }
            return $.Deferred().resolve();
        },
        renderConfigurablePane: function(paneName, labelClasses, descriptionClasses, controlClasses, customLayout) {
            _.each(this.currentConfig.toJSON(), _.bind(function(configurableAttribute, configurableKey) {
                if (configurableKey != 'attributesToTrack') {
                    this.$el.html(this.template(_.defaults(configurableAttribute, {
                        warningMessage: false,
                        values: false,
                        value: false,
                        pane: paneName || configurableKey,
                        label_classes: labelClasses || '',
                        description_classes: descriptionClasses || '',
                        control_classes: controlClasses || '',
                        customLayout: (_.isUndefined(customLayout)) ? false : customLayout
                    }))).i18n();
                }
            }, this));
            return this;
        },
        render: function() {
            this.$el.html(this.template()).i18n();
            return this;
        },
        getPaneAttributes: function(key) {
            return wizardConfig[key];
        },
        checkForLimitations: function() {
              if (!_.isUndefined(this.currentConfig.get('attributesToTrack'))) {
                var stringifiedValues = this.currentConfig.stringifyKeys(this.currentConfig.get('attributesToTrack'));
                var attributeToTrack = stringifiedValues[0];
                var valueToTrack = stringifiedValues[1];
                if (this.model.get(attributeToTrack) == valueToTrack) {
                    return true;
                }
                return false;
            }
        },
        initializeModels: function() {
            this.configurableOptions = this.getPaneAttributes(this.constructorName);
            this.currentConfig = new models.WizardPaneModel(this.configurableOptions);
            this.currentConfig.prepareModel();
            if (!_.isUndefined(this.currentConfig.get('attributesToTrack'))) {
                var stringifiedValues = this.currentConfig.stringifyKeys(this.currentConfig.get('attributesToTrack'));
                var attributesToTrack = stringifiedValues[0];
                var valuesToTrack = stringifiedValues[1];
                this.model.on('change:' + attributesToTrack, _.bind(function() {this.render()}, this));
            }
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
            if (success && (!this.previousRelease || this.previousRelease.id != this.release.id)) {
                this.previousRelease = this.release;
            }
            return $.Deferred()[success ? 'resolve' : 'reject']();
        },
        createCluster: function() {
            var success = true;
            var name = $.trim(this.$('input[name=name]').val());
            var release = parseInt(this.$('select[name=release]').val(), 10);
            this.cluster = new models.Cluster();
            this.cluster.on('invalid', function(model, error) {
                success = false;
                _.each(error, function(message, field) {
                    this.$('*[name=' + field + ']').closest('.control-group').addClass('error').find('.help-inline').text(message);
                }, this);
            }, this);
            if (this.wizard.collection.findWhere({name: name})) {
                this.cluster.trigger('invalid', this.cluster, {name: $.t('dialog.create_cluster_wizard.name_release.existing_environment', {name: name})});
            }
            success = success && this.cluster.set({
                name: name,
                release: release
            }, {validate: true});
            return success;
        },
        onInputKeydown: function(e) {
            this.$('.control-group.error').removeClass('error');
            this.$('.help-inline').html('');
        },
        renderReleases: function(e) {
            var input = this.$('select[name=release]');
            input.html('');
            this.releases.each(function(release) {
                input.append($('<option/>').attr('value', release.id).text(release.get('name') + ' (' + release.get('version') + ')'));
            });
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.releases = new models.Releases();
            this.releases.fetch();
            this.releases.on('sync', this.renderReleases, this);
            this.redHatAccount = new models.RedHatAccount();
            this.redHatAccount.absent = false;
            this.redHatAccount.deferred = this.redHatAccount.fetch();
            this.redHatAccount.deferred
                .fail(_.bind(function(response) {
                    if (response.status == 404) {
                        this.redHatAccount.absent = true;
                    }
                }, this))
                .always(_.bind(this.render, this));
            this.initializeModels();
        },
        render: function() {
//            this.tearDownRegisteredSubViews();
            this.$el.html(this.template()).i18n();
            this.stickit(this.releases, this.bindings);
            this.renderReleases();
            return this;
        }
    });

    clusterWizardPanes.Mode = views.WizardPane.extend({
        constructorName: 'Mode',
        title: 'dialog.create_cluster_wizard.mode.title',
        events: {
            'change input[name=mode]': 'toggleTypes'
        },
        toggleTypes: function() {
            var release = this.wizard.findPane(clusterWizardPanes.NameAndRelease).release;
            var mode = this.$('input[name=mode]:checked').val();
            var description = '';
            try {
                description = release.get('modes_metadata')[mode].description;
            } catch (ignore) {}
            this.$('.mode-description').text(description);
        },
        render: function() {
            return this.renderConfigurablePane('mode', 'setting', 'openstack-sub-title', 'row-fluid mode-control-group', 'mode');
        }
    });

    clusterWizardPanes.Compute = views.WizardPane.extend({
        constructorName: 'Compute',
        title: 'dialog.create_cluster_wizard.compute.title',
        render: function() {
            return this.renderConfigurablePane();
        }
    });

    clusterWizardPanes.Network = views.WizardPane.extend({
        constructorName: 'Network',
        title: 'dialog.create_cluster_wizard.network.title',
        render: function() {
            if (this.checkForLimitations()) {
//                TODO: handle warnings/disablings
                return this.renderConfigurablePane();
            }
            return this.renderConfigurablePane();
        }
    });

    clusterWizardPanes.Storage = views.WizardPane.extend({
        constructorName: 'Storage',
        title: 'dialog.create_cluster_wizard.storage.title',
        render: function() {
              if (this.checkForLimitations()) {
//                TODO: handle warnings/disablings
//                return this.renderConfigurablePane();
            }
            return this.renderConfigurablePane(null, null, null, 'row-fluid', 'storage');
        }
    });

    clusterWizardPanes.AdditionalServices = views.WizardPane.extend({
        constructorName: 'AdditionalServices',
        title: 'dialog.create_cluster_wizard.additional.title',
        render: function() {
             if (this.checkForLimitations()) {
//                TODO: handle warnings/disablings
//                return this.renderConfigurablePane();
            }
            return this.renderConfigurablePane();
        }
    });

    clusterWizardPanes.Ready = views.WizardPane.extend({
        constructorName: 'Ready',
        title: 'dialog.create_cluster_wizard.ready.title',
        template: _.template(clusterReadyPaneTemplate)
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
