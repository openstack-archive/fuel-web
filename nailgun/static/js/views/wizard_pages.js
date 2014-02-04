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
    'text!templates/dialogs/create_cluster_wizard/mode.html',
    'text!templates/dialogs/create_cluster_wizard/compute.html',
    'text!templates/dialogs/create_cluster_wizard/network.html',
    'text!templates/dialogs/create_cluster_wizard/storage.html',
    'text!templates/dialogs/create_cluster_wizard/additional.html',
    'text!templates/dialogs/create_cluster_wizard/ready.html',
    'text!templates/dialogs/rhel_license.html',
    'text!js/wizard.json'
],
function(require, utils, models, dialogs, createClusterWizardTemplate, clusterNameAndReleasePaneTemplate, clusterModePaneTemplate, clusterComputePaneTemplate, clusterNetworkPaneTemplate, clusterStoragePaneTemplate, clusterAdditionalServicesPaneTemplate, clusterReadyPaneTemplate, rhelCredentialsDialogTemplate, wizardInfo) {
    'use strict';

    var views = {};

    var wizardConfigJSON = JSON.parse(wizardInfo);
    var mainWizardModel = new models.WizardPages();

    mainWizardModel.set('wizardPages', new Backbone.Collection(wizardConfigJSON.wizard_setup));

    var rhelCredentialsMixin = {
        renderRhelCredentialsForm: function(options) {
            var commonViews = require('views/common'); // avoid circular dependencies
            this.rhelCredentialsForm = new commonViews.RhelCredentialsForm(_.extend({dialog: this}, options));
            this.registerSubView(this.rhelCredentialsForm);
            this.$('.credentials').html('').append(this.rhelCredentialsForm.render().el).i18n();
        }
    };

    var clusterWizardPanes = {};

    views.CreateClusterWizard = dialogs.Dialog.extend({
        className: 'modal fade create-cluster-modal',
        template: _.template(createClusterWizardTemplate),
        templateHelpers: _.pick(utils, 'floor'),
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
        updateMaxAvaialblePaneIndex: function() {
            var newIndex = this.maxAvaialblePaneIndex;
            _.each(this.activePane().dependentPanes(), function(pane) {
                newIndex = _.min([newIndex, _.indexOf(this.panesConstructors, pane.constructor) - 1]);
            }, this);
            if (newIndex < this.maxAvaialblePaneIndex) {
                this.activePane().$el.detach();
                this.maxAvaialblePaneIndex = newIndex;
                this.render();
            }
        },
        goToPane: function(index) {
            this.activePane().$el.detach();
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
            var cluster = this.findPane(clusterWizardPanes.ClusterNameAndReleasePane).cluster;
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
                                this.displayErrorMessage({message: 'Your OpenStack environment has been created, but configuration failed. You can configure it manually.'});
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
        initialize: function(options) {
            _.defaults(this, options);
        },
        processPaneData: function() {
            return $.Deferred().resolve();
        },
        beforeClusterCreation: function(cluster) {
            return $.Deferred().resolve();
        },
        beforeSettingsSaving: function(cluster) {
            return $.Deferred().resolve();
        },
        dependentPanes: function() {
            return _.filter(this.wizard.subViews, function(pane) {
                return pane instanceof views.WizardPane && _.contains(pane.deps, this.constructor);
            }, this);
        },
        render: function() {
            this.$el.html(this.template()).i18n();
            return this;
        },
        getPaneAttributes: function(key) {
            return _.first(mainWizardModel.get('wizardPages').where({'key': key})).get('attributes');
        },
        isDisabledDueToAttributeTypeAndName: function(pluginCollection) {
            var disabledDueToAttribute = [];
            pluginCollection.each(_.bind(function(element) {
                var pluginConflicts = element.get('restrictions').conflicts;
                _.each(pluginConflicts, function(conflictJSON) {
                    var wizardPanel = this.wizard.findPane(clusterWizardPanes[conflictJSON.panelName]);
                    if (_.isUndefined(wizardPanel[conflictJSON.attributeName]) || _.isUndefined(conflictJSON.attributeType)) return;
                    disabledDueToAttribute.push(wizardPanel[conflictJSON.attributeName].get(conflictJSON.attributeType) == conflictJSON.value);
                    }, this);
            }, this));
            return _.filter(disabledDueToAttribute).length;
        },
        isDisabledDueToAttributeName: function(pluginCollection) {
           var disabledDueToType = [];
           pluginCollection.each(_.bind(function(element) {
               var pluginConflicts = element.get('restrictions').conflicts;
               _.each(pluginConflicts, function(conflictJSON) {
                   var wizardPanel = this.wizard.findPane(clusterWizardPanes[conflictJSON.panelName]);
                   if (_.isUndefined(wizardPanel[conflictJSON.attributeName])) return;
                   disabledDueToType.push(wizardPanel[conflictJSON.attributeName] == conflictJSON.value);  // no Murano for Nova Network
               }, this);
           }, this));
           return _.filter(disabledDueToType).length;
        },
        hasNeededByAttributeName: function(pluginCollection) {
           var hasNeededAttributes = [];
           pluginCollection.each(_.bind(function(element) {
               var pluginDepends = element.get('restrictions').depends;
               _.each(pluginDepends, function(dependsJSON) {
                   var wizardPanel = this.wizard.findPane(clusterWizardPanes[dependsJSON.panelName]);
                   if (_.isUndefined(wizardPanel[dependsJSON.attributeName].get(dependsJSON.attributeType)) || _.isUndefined(dependsJSON.attributeType)) return;
                   hasNeededAttributes.push(_.contains(wizardPanel[dependsJSON.attributeName].get(dependsJSON.attributeType), dependsJSON.value));
               }, this);
           }, this));
           return _.filter(hasNeededAttributes).length;
        }
    });

    clusterWizardPanes.ClusterNameAndReleasePane = views.WizardPane.extend(_.extend({
        title:'dialog.create_cluster_wizard.name_release.title',
        template: _.template(clusterNameAndReleasePaneTemplate),
        events: {
            'keydown input': 'onInputKeydown',
            'change select[name=release]': 'onReleaseChange'
        },
        processPaneData: function() {
            var success = this.createCluster();
            if (success && this.rhelCredentialsFormVisible()) {
                success = this.rhelCredentialsForm.setCredentials();
                if (success) {
                    this.rhelCredentialsForm.saveCredentials();
                    this.rhelCredentialsForm.visible = false;
                    this.redHatAccount.absent = false;
                    this.updateReleaseParameters();
                }
            }
            if (success && (!this.previousRelease || this.previousRelease.id != this.release.id)) {
                this.previousRelease = this.release;
                _.invoke(this.dependentPanes(), 'render');
            }
            return $.Deferred()[success ? 'resolve' : 'reject']();
        },
        createCluster: function() {
            this.$('.control-group').removeClass('error').find('.help-inline').text('');
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
                this.cluster.trigger('invalid', this.cluster, {name: 'Environment with name "' + name + '" already exists'});
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
        onReleaseChange: function() {
            this.updateReleaseParameters();
            this.wizard.updateMaxAvaialblePaneIndex();
        },
        updateReleaseParameters: function() {
            if (this.releases.length) {
                var releaseId = parseInt(this.$('select[name=release]').val(), 10);
                this.release = this.releases.get(releaseId);
                this.$('.release-description').text(this.release.get('description'));
                this.$('.rhel-license').toggle(this.rhelCredentialsFormVisible());
                this.rhelCredentialsForm.render();
            }
        },
        renderReleases: function(e) {
            var input = this.$('select[name=release]');
            input.html('');
            this.releases.each(function(release) {
                input.append($('<option/>').attr('value', release.id).text(release.get('name') + ' (' + release.get('version') + ')'));
            });
            this.updateReleaseParameters();
        },
        rhelCredentialsFormVisible: function() {
            return this.redHatAccount.absent && this.release.get('state') == 'not_available';
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
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.$el.html(this.template()).i18n();
            this.renderReleases();
            this.renderRhelCredentialsForm({
                redHatAccount: this.redHatAccount,
                visible: _.bind(this.rhelCredentialsFormVisible, this)
            });
            return this;
        }
    }, rhelCredentialsMixin));

    clusterWizardPanes.ClusterModePane = views.WizardPane.extend({
        title: 'dialog.create_cluster_wizard.mode.title',
        deps: [clusterWizardPanes.ClusterNameAndReleasePane],
        template: _.template(clusterModePaneTemplate),
        events: {
            'change input[name=mode]': 'toggleTypes'
        },
        toggleTypes: function() {
            var release = this.wizard.findPane(clusterWizardPanes.ClusterNameAndReleasePane).release;
            var mode = this.$('input[name=mode]:checked').val();
            var description = '';
            try {
                description = release.get('modes_metadata')[mode].description;
            } catch (ignore) {}
            this.$('.mode-description').text(description);
        },
        beforeClusterCreation: function(cluster) {
            cluster.set({mode: this.$('input[name=mode]:checked').val()});
            return $.Deferred().resolve();
        },
        render: function() {
            var availableModes = models.Cluster.prototype.availableModes();
            this.$el.html(this.template({availableModes: availableModes}));
            this.$('input[name=mode]:first').prop('checked', true).trigger('change');
            return this;
        }
    });

    clusterWizardPanes.ClusterComputePane = views.WizardPane.extend({
        title: 'dialog.create_cluster_wizard.compute.title',
        template: _.template(clusterComputePaneTemplate),
        beforeSettingsSaving: function(settings) {
            try {
                settings.get('editable').common.libvirt_type.value = this.$('input[name=hypervisor]:checked').val();
            } catch (e) {
                return $.Deferred().reject();
            }
            return $.Deferred().resolve();
        },
        render: function() {
            this.$el.html(this.template());
            this.$('input[name=hypervisor][value=qemu]').prop('checked', true);
            return this;
        }
    });

    clusterWizardPanes.ClusterNetworkPane = views.WizardPane.extend({
        title: 'dialog.create_cluster_wizard.network.title',
        deps: [clusterWizardPanes.ClusterNameAndReleasePane],
        template: _.template(clusterNetworkPaneTemplate),
        events: {
            'change input[name=manager]': 'onManagerChange'
        },
        onManagerChange: function() {
            this.wizard.updateMaxAvaialblePaneIndex();
        },
        processPaneData: function() {
            this.manager = this.$('input[name=manager]:checked').val();
            if (!this.previousManager || this.previousManager != this.manager) {
                this.previousManager = this.manager;
                _.invoke(this.dependentPanes(), 'render');
            }
            return $.Deferred().resolve();
        },
        beforeClusterCreation: function(cluster) {
            if (this.manager == 'nova-network') {
                cluster.set({net_provider: 'nova_network'});
            } else {
                cluster.set({net_provider: 'neutron'});
                if (this.manager == 'neutron-gre') {
                    cluster.set({net_segment_type: 'gre'});
                } else if (this.manager == 'neutron-vlan') {
                    cluster.set({net_segment_type: 'vlan'});
                }
            }
            return $.Deferred().resolve();
        },
        render: function() {
            var release = this.wizard.findPane(clusterWizardPanes.ClusterNameAndReleasePane).release;
            var paneAttributes = this.getPaneAttributes('network');
            var pluginCollection = new Backbone.Collection(paneAttributes.plugins);
            var disabledDueToRelease = this.isDisabledDueToAttributeTypeAndName(pluginCollection);
            var managers = ['nova-network'];
            var descriptionsKeys = ['nova-network'],
                descriptionsValues = [$.t("dialog.create_cluster_wizard.network.nova_network")];
            pluginCollection.each(function(elem) {
                managers.push(elem.get('key'));
                descriptionsKeys.push(elem.get('key'));
                descriptionsValues.push($.t(elem.get('label')));
            });
            var descriptions = _.zipObject(descriptionsKeys, descriptionsValues);
            this.$el.html(this.template({
                disabledDueToRelease: disabledDueToRelease,
                release: release,
                managers: managers,
                descriptions: descriptions,
                warningMessage: _.first(pluginCollection.first().get('restrictions').conflicts).warning
            })).i18n();
            if (disabledDueToRelease) {
                this.$('input[value^=neutron]').prop('disabled', true);
            }
            this.$('input[name=manager]:first').prop('checked', true);
            return this;
        }
    });

    clusterWizardPanes.ClusterStoragePane = views.WizardPane.extend({
        title: 'dialog.create_cluster_wizard.storage.title',
        deps: [clusterWizardPanes.ClusterNameAndReleasePane],
        template: _.template(clusterStoragePaneTemplate),
        beforeSettingsSaving: function(settings) {
            try {
                var storageSettings = settings.get('editable').storage;
                if (storageSettings) {
                    if (this.$('input[name=cinder]:checked').val() == 'ceph' && storageSettings.volumes_ceph) {
                        storageSettings.volumes_ceph.value = true;
                    } else if (storageSettings.volumes_lvm) {
                        storageSettings.volumes_lvm.value = true;
                    }
                    if (this.$('input[name=glance]:checked').val() == 'ceph' && storageSettings.images_ceph) {
                        storageSettings.images_ceph.value = true;
                    }
                }
            } catch (e) {
                return $.Deferred().reject();
            }
            return $.Deferred().resolve();
        },
        render: function() {
            var release = this.wizard.findPane(clusterWizardPanes.ClusterNameAndReleasePane).release;
            var paneAttributes = this.getPaneAttributes('storage_backends');
            var pluginCollection = new Backbone.Collection(paneAttributes.plugins);
            var disabled = !release || !this.hasNeededByAttributeName(pluginCollection);
            this.$el.html(this.template({
                disabled: disabled,
                release: release,
                warningMessage: _.first(pluginCollection.first().get('restrictions').depends).warning
            })).i18n();
            if (disabled) {
                this.$('input[value=ceph]').prop('disabled', true);
            }
            this.$('input[name=cinder]:first, input[name=glance]:first').prop('checked', true);
            return this;
        }
    });

    clusterWizardPanes.ClusterAdditionalServicesPane = views.WizardPane.extend({
        title: 'dialog.create_cluster_wizard.additional.title',
        deps: [clusterWizardPanes.ClusterNameAndReleasePane, clusterWizardPanes.ClusterNetworkPane],
        template: _.template(clusterAdditionalServicesPaneTemplate),
        beforeSettingsSaving: function(settings) {
            try {
                var additionalServices = settings.get('editable').additional_components;
                if (additionalServices) {
                    additionalServices.savanna.value = this.$('input[name=savanna]').is(':checked');
                    additionalServices.murano.value = this.$('input[name=murano]').is(':checked');
                    additionalServices.ceilometer.value = this.$('input[name=ceilometer]').is(':checked');
                }
            } catch (e) {
                return $.Deferred().reject();
            }
            return $.Deferred().resolve();
        },
        render: function() {
            var paneAttributes = this.getPaneAttributes('additional_services');
            var pluginCollection = new Backbone.Collection(paneAttributes.plugins);
            var release = this.wizard.findPane(clusterWizardPanes.ClusterNameAndReleasePane).release;
            var disabledDueToRelease = this.isDisabledDueToAttributeTypeAndName(pluginCollection);
            var disabledDueToNetworkMode = this.isDisabledDueToAttributeName(pluginCollection);
            var services = [
                {
                    name: 'savanna',
                    label: $.t("dialog.create_cluster_wizard.additional.install_savanna"),
                    description:  $.t("dialog.create_cluster_wizard.additional.install_savanna_description")
                },{
                    name: pluginCollection.first().get('key'),
                    label: $.t(pluginCollection.first().get('label')),
                    description: $.t(pluginCollection.first().get('description'))
                },{
                    name: 'ceilometer',
                    label: $.t("dialog.create_cluster_wizard.additional.install_ceilometer"),
                    description: $.t("dialog.create_cluster_wizard.additional.install_ceilometer_description")
                  }
            ];
            this.$el.html(this.template({
                disabledDueToRelease: disabledDueToRelease,
                disabledDueToNetworkMode: disabledDueToNetworkMode,
                release: release,
                services: services,
                warning: $.t(_.first(pluginCollection.first().get('restrictions').conflicts).warning)
            })).i18n();
            if (disabledDueToRelease) {
                this.$('input[type=checkbox]').prop('disabled', true);
            } else if (disabledDueToNetworkMode) {
                this.$('input[name=murano]').prop('disabled', true);
            }
            return this;
        }
    });

    clusterWizardPanes.ClusterReadyPane = views.WizardPane.extend({
        title: 'dialog.create_cluster_wizard.ready.title',
        template: _.template(clusterReadyPaneTemplate)
    });

    views.CreateClusterWizard.prototype.panesConstructors = [
        clusterWizardPanes.ClusterNameAndReleasePane,
        clusterWizardPanes.ClusterModePane,
        clusterWizardPanes.ClusterComputePane,
        clusterWizardPanes.ClusterNetworkPane,
        clusterWizardPanes.ClusterStoragePane,
        clusterWizardPanes.ClusterAdditionalServicesPane,
        clusterWizardPanes.ClusterReadyPane
    ];

    views.RhelCredentialsDialog = dialogs.Dialog.extend(_.extend({
        template: _.template(rhelCredentialsDialogTemplate),
        events: {
            'click .btn-os-download': 'submitForm',
            'keydown input': 'onInputKeydown'
        },
        submitForm: function() {
            if (this.rhelCredentialsForm.setCredentials()) {
                this.$('.btn-os-download').attr('disabled', true);
                var task = this.rhelCredentialsForm.saveCredentials();
                if (task.deferred) {
                    task.deferred
                        .done(_.bind(function(response) {
                            this.release.fetch();
                            app.page.update();
                            this.$el.modal('hide');
                        }, this))
                        .fail(_.bind(this.displayError, this));
                } else {
                    this.$el.modal('hide');
                }
            }
        },
        onInputKeydown: function(e) {
            if (e.which == 13) {
                this.submitForm();
            }
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.redHatAccount = new models.RedHatAccount();
            this.redHatAccount.deferred = this.redHatAccount.fetch();
            this.redHatAccount.deferred.always(_.bind(this.render, this));
        },
        render: function() {
            this.tearDownRegisteredSubViews();
            this.constructor.__super__.render.call(this);
            this.renderRhelCredentialsForm({redHatAccount: this.redHatAccount});
            return this;
        }
    }, rhelCredentialsMixin));

    return views;
});
