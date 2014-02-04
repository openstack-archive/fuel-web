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
    var panesModel = new models.WizardPaneModel();
    panesModel.prepareModel(wizardConfig);

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
            this.activePaneIndex = 0;
            this.maxAvailablePaneIndex = _.keys(wizardConfig).length;
        },
        beforeClusterCreation: function() {
            this.handleBinds(true, this.cluster);
            return $.Deferred().resolve();
        },
        beforeSettingsSaving: function(settings) {
            this.handleBinds(false, settings);
            return $.Deferred().resolve();
        },
        handleBinds: function(isCluster, model) {
            _.each(wizardConfig, _.bind(function(configAttribute, configKey) {
                _.each(_.pluck(configAttribute, 'bind'), _.bind(function(bind, bindIndex) {
                     if (!_.isUndefined(bind) && !_.isPlainObject(bind)) {
                        if (bind.split(':')[0] == 'cluster' && isCluster) {
                            model.set(bind.split(':')[1], panesModel.get(configKey + "." + _.keys(configAttribute)[bindIndex]));
                        }
                        if (bind.split(':')[0] == 'settings' && !isCluster) {
                            model.set(bind.split(':')[1], panesModel.get(configKey + "." + _.keys(configAttribute)[bindIndex]));
                        }
                     }
                     else if (!_.compact(_.pluck(configAttribute, 'bind')).length && _.pluck(_.pluck(configAttribute, 'values')[0], 'bind').length) {
                         _.each(_.pluck(configAttribute, 'values')[0], _.bind(function(value, valueIndex) {
                             if (value.data == panesModel.get(configKey + "." + _.keys(configAttribute)[0])) {
                                 _.each(value.bind, _.bind(function(bind) {
                                    if (_.keys(bind)[0].split(':')[0] == 'cluster' && isCluster) {
                                        model.set(_.keys(bind)[0].split(':')[1], _.values(bind)[0]);
                                    }
                                    if (_.keys(bind)[0].split(':')[0] == 'settings' && !isCluster) {
                                        model.set(_.keys(bind)[0].split(':')[1], _.values(bind)[0]);
                                    }
                                 }, this));
                             }
                         }, this));
                     }
                }, this));
            }, this));
        },
        onInputKeydown: function(e) {
            if (e.which == 13) {
                e.preventDefault();
                this.nextPane();
            }
        },
        nextPane: function() {
            this.activePaneIndex += 1;
            this.renderProperPane();
        },
        onStepClick: function(e) {
            var paneIndex = parseInt($(e.currentTarget).data('pane'), 10);
            this.goToPane(paneIndex);
        },
        renderProperPane: function() {
             var newView,
                 success = true;
             switch (this.activePaneIndex) {
                case 0:
                    newView = new clusterWizardPanes.NameAndRelease();
                    break;
                 case 1:
                    newView = new clusterWizardPanes.Mode();
                    success = this.isClusterCreationPossible();
                    break;
                case 2:
                    newView = new clusterWizardPanes.Compute();
                    break;
                case 3:
                    newView = new clusterWizardPanes.Network();
                    break;
                case 4:
                    newView = new clusterWizardPanes.Storage();
                    break;
                case 5:
                    newView = new clusterWizardPanes.AdditionalServices();
                    break;
                case 6:
                    newView = new clusterWizardPanes.Ready();
                    break;
            }
            var totalSteps = _.keys(wizardConfig).length;
            if (success) {
                this.$('.pane-content').html('');
                this.$('.prev-pane-btn').prop('disabled', !this.activePaneIndex);
                this.$('.next-pane-btn').toggle(this.activePaneIndex + 1 != totalSteps);
                this.$('.finish-btn').toggle(this.activePaneIndex + 1 == totalSteps);
                this.$('.wizard-footer .btn-success:visible').focus();
                this.$('.pane-content').append(newView.render().el);
            }
        },
         isClusterCreationPossible: function() {
            var success = true;
            var name = panesModel.get('NameAndRelease.name');
            var release = panesModel.get('NameAndRelease.release').id;
            this.cluster = new models.Cluster();
            this.cluster.on('invalid', function(model, error) {
                success = false;
                _.each(error, function(message, field) {
                    this.$('*[name=' + field + ']').closest('.control-group').addClass('error').find('.help-inline').text(message);
                }, this);
            }, this);
            if (this.collection.findWhere({name: name})) {
                this.cluster.trigger('invalid', this.cluster, {name: $.t('dialog.create_cluster_wizard.nameandrelease.existing_environment', {name: name})});
            }
            success = success && this.cluster.set({
                name: name,
                release: release
            }, {validate: true});
            return success;
        },
        goToPane: function(index) {
            this.maxAvailablePaneIndex = _.max([this.maxAvailablePaneIndex, this.activePaneIndex, index]);
            this.activePaneIndex = index;
            this.renderProperPane();
        },
        prevPane: function() {
            this.goToPane(this.activePaneIndex - 1);
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
                        var settings = new models.Settings();
                        settings.url = _.result(cluster, 'url') + '/attributes';
                        settings.fetch()
                            .then(_.bind(function() {
                                return $.when.apply($, this.beforeSettingsSaving(settings));
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
            this.tearDownRegisteredSubViews();
             if (_.isNull(this.activePaneIndex)) {
                this.activePaneIndex = 0;
             }
            this.constructor.__super__.render.call(this, _.extend({
                panesTitles: _.keys(wizardConfig),
                currentStep: this.activePaneIndex,
                maxAvailableStep: this.maxAvailablePaneIndex
            }, this.templateHelpers));
            this.$('.wizard-footer .btn-success:visible').focus();
            this.renderProperPane();
            return this;
        }
    });

    views.WizardPane = Backbone.View.extend({
        template: _.template(commonWizardTemplate),
        constructorName: 'WizardPane',
        initialize: function(options) {
            _.defaults(this, options);
        },

        renderConfigurablePane: function(warning, paneName, labelClasses, descriptionClasses, controlClasses, customLayout, descriptionForMode) {
            var currentConfig = wizardConfig[this.constructorName];
            if (this.constructorName == 'AdditionalServices') {
                this.$el.html(this.template({
                    warningMessage: '',
                    type: false,
                    pane: false,
                    values: currentConfig,
                    value: false,
                    label_classes: '',
                    description_classes: '',
                    control_classes: '',
                    customLayout: false,
                    description_mode: false
                })).i18n();
            }
            else {
                _.each(currentConfig, _.bind(function(configurableAttribute, configurableKey) {
                        this.$el.html(this.template(_.defaults(configurableAttribute, {
                            warningMessage: warning,
                            values: false,
                            value: false,
                            pane: paneName || configurableKey,
                            label_classes: labelClasses || '',
                            description_classes: descriptionClasses || '',
                            control_classes: controlClasses || '',
                            customLayout: (_.isUndefined(customLayout)) ? false : customLayout,
                            description_mode: (_.isUndefined(descriptionForMode)) ? false : descriptionForMode
                        }))).i18n();
                }, this));
            }
            this.stickit(panesModel);
            return this;
        },

        render: function() {
            this.$el.html(this.template()).i18n();
            return this;
        }
    });

    clusterWizardPanes.NameAndRelease = views.WizardPane.extend({
        constructorName: 'NameAndRelease',
        title:'dialog.create_cluster_wizard.nameandrelease.title',
        template: _.template(clusterNameAndReleasePaneTemplate),
        events: {
            'keydown input': 'onInputKeydown'
        },
        bindings: {
            'select[name=release]': {
                observe: 'NameAndRelease.release__operating_system',
                selectOptions: {
                    collection: function() {
                        return this.releases.map(function(release) {
                            return {
                                value: release.get('operating_system'),
                                label: release.get('name') + ' (' + release.get('version') + ')'
                            };
                        });
                    }
                },
                onGet: function(value, options) {
                    var currentValue;
                    if (options.view.releases.length) {
                        currentValue = _.isNull(value) ? "CentOS" : value;
                        var currentRelease = options.view.releases.where({'operating_system': currentValue})[0];
                        var roles = currentRelease.get('roles');
                        panesModel.set('NameAndRelease.release__roles', roles);
                        panesModel.set('NameAndRelease.release', currentRelease);
                    }
                    return currentValue;
                }
            },
            'input[name=name]': {
                observe: 'NameAndRelease.name'
            }
        },

        onInputKeydown: function(e) {
            this.$('.control-group.error').removeClass('error');
            this.$('.help-inline').html('');
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.releases = new models.Releases();
            this.releases.fetch();
            this.releases.on('sync', this.render, this);
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
            this.$el.html(this.template()).i18n();
            if (this.releases.length) {
                this.stickit(panesModel);
            }
            return this;
        }
    });

    clusterWizardPanes.Mode = views.WizardPane.extend({
        constructorName: 'Mode',
        title: 'dialog.create_cluster_wizard.mode.title',
        bindings: {
            'input[name=mode]': {
                observe: 'Mode.mode',
                onSet: function(value, options) {
                    var description = panesModel.get('NameAndRelease.release').get('modes_metadata')[value].description;
                    $('.mode-description').text(description);
                    return value;
                }
            }
        },
        render: function() {
            var description = panesModel.get('NameAndRelease.release').get('modes_metadata').multinode.description;
            return this.renderConfigurablePane(false, 'mode', 'setting', 'openstack-sub-title', 'row-fluid mode-control-group', 'mode', description);
        }
    });

    clusterWizardPanes.Compute = views.WizardPane.extend({
        constructorName: 'Compute',
        title: 'dialog.create_cluster_wizard.compute.title',
        bindings: {
           'input[name=hypervisor]': {
               observe: 'Compute.hypervisor'
           }
        },
        render: function() {
            return this.renderConfigurablePane(false);
        }
    });

    clusterWizardPanes.Network = views.WizardPane.extend({
        constructorName: 'Network',
        title: 'dialog.create_cluster_wizard.network.title',
        bindings: {
            'input[name=manager]': {
                observe: 'Network.manager'
            }
        },
        render: function() {
            return this.renderConfigurablePane(false);
        }
    });

    clusterWizardPanes.Storage = views.WizardPane.extend({
        constructorName: 'Storage',
        title: 'dialog.create_cluster_wizard.storage.title',
        bindings: {
           'input[name=cinder]': {
               observe: 'Storage.cinder'
           },
           'input[name=glance]': {
               observe: 'Storage.glance'
           }
        },
        render: function() {
            return this.renderConfigurablePane(false, null, null, null, 'row-fluid', 'storage');
        }
    });

    clusterWizardPanes.AdditionalServices = views.WizardPane.extend({
        constructorName: 'AdditionalServices',
        title: 'dialog.create_cluster_wizard.additionalservices.title',
        bindings: {
            'input[name=murano]': {
                observe: 'AdditionalServices.murano',
                onGet: function(value) {
                    return value;
                },
                onSet: function(value) {
                    return value;
                }
            },
            'input[name=sahara]': {
                observe: 'AdditionalServices.sahara',
                onGet: function(value) {
                    return value;
                },
                onSet: function(value) {
                    return value;
                }
            },
            'input[name=ceilometer]': {
                observe: 'AdditionalServices.ceilometer',
                onGet: function(value) {
                    return value;
                },
                onSet: function(value) {
                    return value;
                }
            }
        },
        render: function() {
            return this.renderConfigurablePane(false);
        }
    });

    clusterWizardPanes.Ready = views.WizardPane.extend({
        constructorName: 'Ready',
        title: 'dialog.create_cluster_wizard.ready.title',
        template: _.template(clusterReadyPaneTemplate)
    });

    return views;
});
