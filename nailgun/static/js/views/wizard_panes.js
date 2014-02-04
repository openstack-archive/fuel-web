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
    'text!templates/dialogs/create_cluster_wizard/warning.html',
    'text!templates/dialogs/create_cluster_wizard/radio_template.html',
    'text!templates/dialogs/create_cluster_wizard/checkbox_template.html',
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
function(require, utils, models, dialogs, warningTemplate, radioTemplate, checkBoxTemplate, createClusterWizardTemplate, clusterNameAndReleasePaneTemplate, clusterModePaneTemplate, clusterComputePaneTemplate, clusterNetworkPaneTemplate, clusterStoragePaneTemplate, clusterAdditionalServicesPaneTemplate, clusterReadyPaneTemplate, rhelCredentialsDialogTemplate, wizardInfo) {
    'use strict';

    var views = {};

    var wizardConfig = JSON.parse(wizardInfo);

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
        configurableOptions: {},
        attributesToTrack: [],
        stackedKeys: [],
        trackedValues: [],
        configKey: null,
        globalModel: new Backbone.Model(wizardConfig),
        restrictionsModel: new Backbone.Model(),
        warningMessages: [],
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
        renderRadioControl: function(options) {
            var template = _.template(radioTemplate);
            return template(options);
        },
        renderCheckboxControl: function(options) {
            var template = _.template(checkBoxTemplate);
            return template(options);
        },
        getPaneAttributes: function(key) {
            if (!_.isNull(key)) {
                return wizardConfig[key].attributes;
            }
        },
        composeModelAttributeString: function(config) {
            _.each(_.keys(config), _.bind(function(configKey) {
                if (_.isPlainObject(config[configKey])) {
                    this.stackedKeys.push(configKey);
                    this.composeModelAttributeString(config[configKey]);
                    this.stackedKeys.pop();
                }
                else {
                    this.attributesToTrack.push((this.stackedKeys.length > 0) ? this.stackedKeys.join('__') + '__' + configKey : configKey);
                    this.trackedValues.push(config[configKey]);
                }
            }, this));
        },
        composeModelRestrictions: function() {
            this.configurableOptions = this.getPaneAttributes(this.configKey);
            if (!_.isUndefined(this.configurableOptions)) {
                _.each(this.configurableOptions.plugins, _.bind(function(plugin) {
                    _.each(plugin.restrictions.conflicts, _.bind(function(conflict, index) {
                        this.composeModelAttributeString(conflict.conflictingAttribute);
                        this.getWarningMessage(conflict);
                    }, this));
                    _.each(plugin.restrictions.depends, _.bind(function(depend, index) {
                        this.composeModelAttributeString(depend.dependantAttribute);
                        this.getWarningMessage(depend);
                    }, this));
                    this.restrictionsModel.set(_.zipObject(this.attributesToTrack, this.trackedValues));
                }, this));
            }
        },
        getWarningMessage: function(attributes) {
            this.warningMessages.push(attributes.warning);
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
                this.restrictionsModel.set({
                    release__operating_system: this.release.get('operating_system'),
                    release__roles: this.release.get('roles')
                });
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
            this.$el.html(this.template());
            _.each(availableModes, _.bind(function(mode) {
                this.$('.mode-control-group .span5').append(this.renderRadioControl(
                    {
                       pane: 'mode',
                       value: mode,
                       label: $.t('cluster.mode.' + mode),
                       label_classes: 'setting',
                       description_classes: 'openstack-sub-title',
                       description: false
                    }
                ));
            }, this));
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
            var hypervisors = ['kvm', 'qemu'];
            var descriptions = {
                kvm: $.t('dialog.create_cluster_wizard.compute.kvm_description'),
                qemu: $.t('dialog.create_cluster_wizard.compute.qemu_description')
            };
             _.each(hypervisors, _.bind(function(hypervisor) {
                this.$('.control-group').append(this.renderRadioControl(
                    {
                       pane: 'hypervisor',
                       value: hypervisor,
                       label: $.t(hypervisor),
                       label_classes: '',
                       description_classes: '',
                       description: descriptions[hypervisor]
                    }
                ));
            }, this));

            this.$('input[name=hypervisor][value=qemu]').prop('checked', true);
            return this;
        }
    });

    clusterWizardPanes.ClusterNetworkPane = views.WizardPane.extend({
        title: 'dialog.create_cluster_wizard.network.title',
        configKey: 'network',
        deps: [clusterWizardPanes.ClusterNameAndReleasePane],
        template: _.template(clusterNetworkPaneTemplate),
        events: {
            'change input[name=manager]': 'onManagerChange'
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.trackedValues = [];
            this.attributesToTrack = [];
            this.warningMessages = [];
            this.restrictionsModel.clear();
            this.composeModelRestrictions();
        },
        onManagerChange: function() {
            this.wizard.updateMaxAvaialblePaneIndex();
        },
        processPaneData: function() {
            this.manager = this.$('input[name=manager]:checked').val();
            this.restrictionsModel.set({
                manager: this.manager
            });
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
            var disabled = false;
            _.each(this.attributesToTrack, _.bind(function(attribute) {
                _.each(this.trackedValues, _.bind(function(value) {
                    if (this.restrictionsModel.get(attribute) == value) {
                        disabled = true;
                    }
                }, this));
            }, this));
            var release = this.wizard.findPane(clusterWizardPanes.ClusterNameAndReleasePane).release;
            var pluginCollection = new Backbone.Collection(this.configurableOptions.plugins);
            var managers = ['nova-network'];
            var descriptionsKeys = ['nova-network'],
                descriptionsValues = ["dialog.create_cluster_wizard.network.nova_network"];
            pluginCollection.each(function(elem) {
                managers.push(elem.get('key'));
                descriptionsKeys.push(elem.get('key'));
                descriptionsValues.push(elem.get('label'));
            });
            var descriptions = _.zipObject(descriptionsKeys, descriptionsValues);
            this.$el.html(this.template({
                disabledDueToRelease: disabled,
                release: release
            })).i18n();
            _.each(managers, _.bind(function(manager) {
                this.$('.control-group').append(this.renderRadioControl(
                    {
                       pane: 'manager',
                       value: manager,
                       label: $.t(descriptions[manager]),
                       label_classes: '',
                       description_classes: '',
                       description: false
                    }
                ));
            }, this));
            if (disabled && release) {
                _.each(_.filter(_.uniq(this.warningMessages)), _.bind(function(message) {
                     this.$('.form-horizontal').before(_.template(warningTemplate)( {
                        warningMessage: $.t(message,  { releaseName: release.get('name')})
                    }));
                }, this));
            }
            if (disabled) {
                this.$('input[value^=neutron]').prop('disabled', true);
            }
            this.$('input[name=manager]:first').prop('checked', true);
            return this;
        }
    });

    clusterWizardPanes.ClusterStoragePane = views.WizardPane.extend({
        title: 'dialog.create_cluster_wizard.storage.title',
        configKey: 'storage_backends',
        deps: [clusterWizardPanes.ClusterNameAndReleasePane],
        template: _.template(clusterStoragePaneTemplate),
        initialize: function(options) {
            _.defaults(this, options);
            this.trackedValues = [];
            this.attributesToTrack = [];
            this.restrictionsModel.clear();
            this.composeModelRestrictions();
        },
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
            var disabled = false;
            _.each(this.attributesToTrack, _.bind(function(attribute) {
                _.each(this.trackedValues, _.bind(function(value) {
                    if (!_.contains(this.restrictionsModel.get(attribute), value)) {
                        disabled = true;
                    }
                }, this));
            }, this));
            var release = this.wizard.findPane(clusterWizardPanes.ClusterNameAndReleasePane).release;
            this.configurableOptions = this.getPaneAttributes('storage_backends');
            var pluginCollection = new Backbone.Collection(this.configurableOptions.plugins);
            this.$el.html(this.template({
                disabled: disabled,
                release: release,
                warningMessage: _.first(pluginCollection.first().get('restrictions').depends).warning
            })).i18n();
            _.each(['cinder', 'glance'], _.bind(function(image) {
                _.each(['ceph', 'default'], _.bind(function(backend) {
                    this.$('h5[data-i18n="dialog.create_cluster_wizard.storage.' + image + '"]').after(this.renderRadioControl(
                        {
                           pane: image,
                           value: backend,
                           label: $.t('dialog.create_cluster_wizard.storage.' + backend),
                           label_classes: '',
                           description_classes: '',
                           description: false
                        }
                    ));
                }, this));
            }, this));
            if (disabled && release) {
                 _.each(_.filter(_.uniq(this.warningMessages)), _.bind(function(message) {
                     this.$('.form-horizontal').before(_.template(warningTemplate)( {
                        warningMessage: _.isUndefined(release) ? '' :$.t(message,  { releaseName: release.get('name')})
                    }));
                }, this));
            }
            if (disabled) {
                this.$('input[value=ceph]').prop('disabled', true);
            }
            this.$('input[name=cinder]:enabled:first, input[name=glance]:enabled:first').prop('checked', true);
            return this;
        }
    });

    clusterWizardPanes.ClusterAdditionalServicesPane = views.WizardPane.extend({
        title: 'dialog.create_cluster_wizard.additional.title',
        configKey: 'additional_services',
        deps: [clusterWizardPanes.ClusterNameAndReleasePane, clusterWizardPanes.ClusterNetworkPane],
        template: _.template(clusterAdditionalServicesPaneTemplate),
        initialize: function(options) {
            _.defaults(this, options);
            this.trackedValues = [];
            this.attributesToTrack = [];
            this.warningMessages = [];
            this.restrictionsModel.clear();
            this.composeModelRestrictions();
        },
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
            var disabled = {};
            _.each(this.attributesToTrack, _.bind(function(attribute, attributeIndex) {
                _.each(this.trackedValues, _.bind(function(value, valueAttribute) {
                    if (attributeIndex == valueAttribute) {
                        if (this.restrictionsModel.get(attribute) == value) {
                           disabled[attribute] = true;
                        }
                    }
                }, this));
            }, this));
            this.configurableOptions = this.getPaneAttributes('additional_services');
            var pluginCollection = new Backbone.Collection(this.configurableOptions.plugins);
            var release = this.wizard.findPane(clusterWizardPanes.ClusterNameAndReleasePane).release;
            var disabledDueToRelease = disabled.release__operating_system;
            var disabledDueToNetworkMode = disabled.manager;
            var services = [
                {
                    name: 'savanna',
                    label: $.t('dialog.create_cluster_wizard.additional.install_savanna'),
                    description:  $.t('dialog.create_cluster_wizard.additional.install_savanna_description')
                },{
                    name: pluginCollection.first().get('key'),
                    label: $.t(pluginCollection.first().get('label')),
                    description: $.t(pluginCollection.first().get('description'))
                },{
                    name: 'ceilometer',
                    label: $.t('dialog.create_cluster_wizard.additional.install_ceilometer'),
                    description: $.t('dialog.create_cluster_wizard.additional.install_ceilometer_description')
                  }
            ];
            this.$el.html(this.template({
                disabledDueToRelease: disabledDueToRelease,
                disabledDueToNetworkMode: disabledDueToNetworkMode,
                release: release,
                warning: $.t(_.first(pluginCollection.first().get('restrictions').conflicts).warning)
            })).i18n();
            _.each(services, _.bind(function(service) {
                 this.$('.control-group').append(this.renderCheckboxControl(
                    {
                       pane: service.name,
                       label: $.t(service.label),
                       description: service.description
                    }
                ));
            }, this));

            var releaseWarning = _.find(_.filter(_.uniq(this.warningMessages)), function(msg) {
                return msg.indexOf('release') > 0;
            });
            var networkWarning = _.find(_.filter(_.uniq(this.warningMessages)), function(msg) {
                return msg.indexOf('network') > 0;
            });
            if (disabledDueToRelease && release) {
                 this.$('.form-horizontal').before(_.template(warningTemplate)( {
                        warningMessage: $.t(releaseWarning,  { releaseName: release.get('name')})
                 }));
            } else if (disabledDueToNetworkMode) {
                 this.$('.form-horizontal').before(_.template(warningTemplate)( {
                        warningMessage: $.t(networkWarning)
                 }));
            }
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

    return views;
});
