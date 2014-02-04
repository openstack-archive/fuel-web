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
        cluster: new models.Cluster(),
        settings: new models.Settings(),
        model: new models.WizardPaneModel(wizardConfig),
        initialize: function(options) {
            _.defaults(this, options);
            this.initializeModels();
        },
        processPaneData: function() {
//            hacks here - FIXME
            switch (this.constructorName) {
                case 'NameAndRelease':
                    if (_.isUndefined(this.model.get('NameAndRelease.release__roles'))) {
                        this.model.set('NameAndRelease.release__roles', this.releases.first().get('roles'));
                    }
                    if (_.isUndefined(this.model.get('NameAndRelease.release__operating_system'))) {
                        this.model.set('NameAndRelease.release__operating_system', 0);
                    }
                    break;
                case 'Mode':
                    if (_.isUndefined(this.model.get('Mode.mode.value'))) {
                        this.model.set('Mode.mode.value', 'multinode');
                    }
                    break;
                case 'Compute':
                    if (_.isUndefined(this.model.get('Compute.hypervisor.value'))) {
                        this.model.set('Compute.hypervisor.value', 'qemu');
                    }
                    break;
                case 'Network':
                    if (_.isObject(this.model.get('Network.manager'))) {
                        this.model.set('Network.manager', _.where($('input[name=manager]'), {checked: true})[0].value);
                    }
                    break;
                case 'Storage':
                    if (_.isUndefined(this.model.get('Storage.cinder.value'))) {
                        this.model.set('Storage.cinder.value', _.where($('input[name=cinder]'), {checked: true})[0].value);
                    }
                    if (_.isUndefined(this.model.get('Storage.glance.value'))) {
                        this.model.set('Storage.glance.value', _.where($('input[name=glance]'), {checked: true})[0].value);
                    }
                    break;
            }
            var binds = _.pluck(this.currentConfig.toJSON(), 'bind');
            if (_.compact(binds).length) {
                _.each(binds, _.bind(function(bind) {
                     if (_.isPlainObject(bind)) {
                         this.handleBind(_.values(bind)[0]);
                     }
                     else if (!_.isUndefined(bind)) {
                        this.handleBind(bind);
                     }
                }, this));
            }
            else {
                switch (this.constructorName) {
                    case 'Network':
                        _.each(_.pluck(this.currentConfig.toJSON(), 'values')[0], _.bind(function(configValue) {
                            if (configValue.data == this.model.get('Network.manager')) {
                                _.each(configValue.bind, _.bind(function(valueToBind) {
                                    var attributeString = _.keys(valueToBind)[0];
                                    this.cluster.set(attributeString.split(':')[1], _.values(valueToBind)[0]);
                                }, this));
                            }
                        }, this));
                        break;
                    case 'Storage':
                        _.each(this.currentConfig.get('cinder.values'), _.bind(function(valueConfig) {
                            if (this.model.get('Storage.cinder.value') ==  valueConfig.data) {
                                 _.each(valueConfig.bind, _.bind(function(valueToBind) {
                                     var attributeString = _.keys(valueToBind)[0];
                                     this.settings.set(attributeString.split(':')[1],  _.values(valueToBind)[0]);
                                }, this));
                            }
                        }, this));
                         _.each(this.currentConfig.get('glance.values'), _.bind(function(valueConfig) {
                            if (this.model.get('Storage.glance.value') ==  valueConfig.data) {
                                 _.each(valueConfig.bind, _.bind(function(valueToBind) {
                                     var attributeString = _.keys(valueToBind)[0];
                                     this.settings.set(attributeString.split(':')[1], _.values(valueToBind)[0]);
                                }, this));
                            }
                        }, this));
                        break;
                    case 'AdditionalServices':
                        _.each(this.currentConfig.get('services.values'), _.bind(function(serviceValue) {
                            _.each(_.values(this.model.get('AdditionalServices.addons')), _.bind(function(addon) {
                                 if (addon ==  serviceValue.data) {
                                     this.settings.set(serviceValue.bind.split(':')[1], true);
                                 }
                             }, this));
                        }, this));
                        break;
                }
            }
            return $.Deferred().resolve();
        },
        handleBind: function(bindString) {
            var bindingKey = bindString.split(':')[0];
            var bindingValue = bindString.split(':')[1];
            if(bindingKey == 'cluster') {
                switch (bindingValue) {
                    case 'name':
                        this.cluster.set(bindingValue, this.model.get('NameAndRelease.name.value'));
                        break;
                    case 'release':
                        this.cluster.set(bindingValue, this.model.get('NameAndRelease.release__operating_system'));
                        break;
                    case 'mode':
                        this.cluster.set(bindingValue, this.model.get('Mode.mode'));
                        break;
                }
            }
            if(bindString.split(':')[0] == 'settings') {
               this.settings.set(bindingValue, this.model.get('Compute.hypervisor.value'));
            }
        },
        beforeClusterCreation: function(cluster) {
            return $.Deferred().resolve();
        },
        beforeSettingsSaving: function(settings) {
            return $.Deferred().resolve();
        },
        renderConfigurablePane: function(warning, paneName, labelClasses, descriptionClasses, controlClasses, customLayout) {
            _.each(this.currentConfig.toJSON(), _.bind(function(configurableAttribute, configurableKey) {
                if (configurableKey != 'attributesToTrack') {
                    this.$el.html(this.template(_.defaults(configurableAttribute, {
                        warningMessage: warning,
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
            this.stickit(this.model, this.bindings);
            return this;
        },

        render: function() {
            this.$el.html(this.template()).i18n();
            return this;
        },
        getPaneAttributes: function(key) {
            return wizardConfig[key];
        },
        hasLimitations: function() {
              var result = false;
              if (!_.isUndefined(this.currentConfig.get('attributesToTrack'))) {
                  var stringifiedValues = this.currentConfig.stringifyKeys(this.currentConfig.get('attributesToTrack'));
                  var attributesToTrack = _.reject(stringifiedValues, function(value, key) {
                      return  key % 2 != 0;
                  });
                  var valuesToTrack = _.reject(stringifiedValues, function(value, key) {
                      return  key % 2 == 0;
                  });
                  _.each(attributesToTrack, _.bind(function(attribute, index) {
                      if (_.contains(attribute, 'roles')) {
                          if (!_.contains(this.model.get(attribute), valuesToTrack[index]) && _.compact(this.model.get(attribute)).length) {
                              result = true;
                          }
                      } else {
                          if (this.model.get(attribute) == valuesToTrack[index]) {
                              result = true;
                          }
                      }
                  }, this));
                  return result;
            }
        },
        initializeModels: function() {
            this.configurableOptions = this.getPaneAttributes(this.constructorName);
            this.currentConfig = new models.WizardPaneModel(this.configurableOptions);
            this.currentConfig.prepareModel();
            if (!_.isUndefined(this.currentConfig.get('attributesToTrack'))) {
                var stringifiedValues = this.currentConfig.stringifyKeys(this.currentConfig.get('attributesToTrack'));
                var attributesToTrack = _.reject(stringifiedValues, function(value, key) {
                    return  key % 2 != 0;
                });
                _.each(attributesToTrack, _.bind(function(attribute) {
                    this.model.on('change:' + attribute, _.bind(function() {
                        this.render();
                    }, this));
                }, this));

            }

        },
        getRestrictedOS: function() {
            var releaseIndex = this.currentConfig.get('attributesToTrack.NameAndRelease.release__operating_system');
            if (this.wizard.panes[0].releases.length) {
                return this.wizard.panes[0].releases.where({'id': parseInt(releaseIndex)})[0].get('name');
            }
        },
        getCurrentRelease: function() {
            return this.wizard.panes[0].releases.at(this.model.get('NameAndRelease.release__operating_system'));
        }
    });

    clusterWizardPanes.NameAndRelease = views.WizardPane.extend({
        constructorName: 'NameAndRelease',
        title:'dialog.create_cluster_wizard.name_release.title',
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
                                value: release.id,
                                label: release.get('name') + ' (' + release.get('version') + ')'
                            };
                        });
                    }
                },
                onSet: function(value, options) {
                    var roles = options.view.releases.where({'id': parseInt(value)})[0].get('roles');
                    options.view.model.set('NameAndRelease.release__roles', roles);
                    return value;
                }
            },
            'input[name=name]': {
                observe: 'NameAndRelease.name.value'
            }
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
            this.model.clear();
            this.initializeModels();
        },
        render: function() {
            this.$el.html(this.template()).i18n();
            if (this.releases.length) {
                this.stickit();
            }
            return this;
        }
    });

    clusterWizardPanes.Mode = views.WizardPane.extend({
        constructorName: 'Mode',
        title: 'dialog.create_cluster_wizard.mode.title',
        bindings: {
            'input[name=mode]': {
                observe: 'Mode.mode.value',
                onSet: function(value, options) {
                    var release = options.view.getCurrentRelease();
                    var description = release.get('modes_metadata')[value].description;
                    $('.mode-description').text(description);
                    return value;
                }
            }
        },
        render: function() {
            return this.renderConfigurablePane(false, 'mode', 'setting', 'openstack-sub-title', 'row-fluid mode-control-group', 'mode');
        }
    });

    clusterWizardPanes.Compute = views.WizardPane.extend({
        constructorName: 'Compute',
        title: 'dialog.create_cluster_wizard.compute.title',
        bindings: {
           'input[name=hypervisor]': {
               observe: 'Compute.hypervisor.value'
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
            },
            'input[value*=neutron]': {
                 attributes: [{
                    name: 'disabled',
                    observe: 'NameAndRelease.release__operating_system',
                     onGet: function(value, options) {
                        return (value == 2);
                    }
                }]
            }
        },
        render: function() {
            if (this.hasLimitations()) {
                var warnings = this.currentConfig.getWarnings(_.compact(_.pluck(this.currentConfig.toJSON(), 'values'))[0]),
                    preparedWarnings = [];
                _.each(warnings, _.bind(function(warn) {
                    preparedWarnings.push($.t(warn, {releaseName: this.getRestrictedOS()}));
                }, this));
                return this.renderConfigurablePane(preparedWarnings);
            }
            return this.renderConfigurablePane(false);
        }
    });

    clusterWizardPanes.Storage = views.WizardPane.extend({
        constructorName: 'Storage',
        title: 'dialog.create_cluster_wizard.storage.title',
        bindings: {
           'input[value=ceph]': {
               attributes: [{
                   name: 'disabled',
                   observe: 'NameAndRelease.release__roles',
                   onGet: function(value) {
                       return !_.contains(value, 'ceph-osd');
                   }
               }]
           },
           'input[name=cinder]': {
               observe: 'Storage.cinder.value'
           },
           'input[name=glance]': {
               observe: 'Storage.glance.value'
           }
        },
        render: function() {
            if (this.hasLimitations()) {
                var warnings = this.currentConfig.getWarnings(_.compact(_.pluck(this.currentConfig.toJSON(), 'values'))[0]),
                preparedWarnings = [];
                _.each(warnings, _.bind(function(warn) {
                    preparedWarnings.push($.t(warn, {releaseName: "RHOS 3.0 for RHEL 6.4"}));
                    }, this));
                return this.renderConfigurablePane(preparedWarnings, null, null, null, 'row-fluid', 'storage');
            }
            return this.renderConfigurablePane(false, null, null, null, 'row-fluid', 'storage');
        }
    });

    clusterWizardPanes.AdditionalServices = views.WizardPane.extend({
        constructorName: 'AdditionalServices',
        title: 'dialog.create_cluster_wizard.additional.title',
        bindings: {
            'input[value=murano]': {
                observe: 'AdditionalServices.addons.murano',
                attributes: [{
                   name: 'disabled',
                   observe: ["Network.manager", "NameAndRelease.release__operating_system"],
                    onGet: function(values, options) {
                        var result = _.map(values, function(value) {
                            return value == 'nova-network' || value == 2;
                        });
                        return _.compact(result.length);
                    }
               }]
            },
            'input[value=sahara]': {
                observe: 'AdditionalServices.addons.sahara',
                attributes: [{
                   name: 'disabled',
                   observe: "NameAndRelease.release__operating_system",
                    onGet: function(value, options) {
                        return (value == 2);
                    }
               }]
            },
            'input[value=ceilometer]': {
                observe: 'AdditionalServices.addons.ceilometer',
                attributes: [{
                   name: 'disabled',
                   observe: "NameAndRelease.release__operating_system",
                    onGet: function(value, options) {
                        return (value == 2);
                    }
               }]
            }
        },
        render: function() {
            if (this.hasLimitations()) {
                var warnings = this.currentConfig.getWarnings(_.compact(_.pluck(this.currentConfig.toJSON(), 'values'))[0]),
                    preparedWarnings = [];
                var networkWarning = _.compact(_.map(warnings, function(warn) {if(_.contains(warn, 'network')) {return warn}}))[0];
                var osWarning = _.without(warnings, networkWarning);
                    // allowing only one warning
                    if (this.model.get('NameAndRelease.release__operating_system') == 2) {
                        preparedWarnings.push($.t(osWarning, {releaseName: this.getRestrictedOS()}));
                    }
                    else {
                        preparedWarnings.push($.t(networkWarning, {releaseName: this.getRestrictedOS()}));
                    }
                return this.renderConfigurablePane(preparedWarnings);
            }
            return this.renderConfigurablePane(false);
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
