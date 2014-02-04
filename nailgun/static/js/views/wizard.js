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
    'text!js/wizard.json'
],
function(require, utils, models, dialogs, createClusterWizardTemplate, clusterNameAndReleasePaneTemplate, commonWizardTemplate, modePaneTemplate, storagePaneTemplate, clusterReadyPaneTemplate, controlTemplate, wizardInfo) {
    'use strict';

    var views = {};

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
        composeStickitBindings: function() {
              var bindings = {};
            _.each(_.keys(this.wizardConfig), _.bind(function(paneConstructor, paneIndex) {
                bindings['.wizard-step[data-pane=' + paneIndex +']'] = {
                    attributes: [{
                        name: 'class',
                        observe: paneConstructor
                    }]
                };
            }, this));
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
                visible: function(value, options) {
                    return value != (_.keys(this.wizardConfig).length - 1);
                },
                observe: 'activePaneIndex'
            };
            bindings['.finish-btn'] = {
                visible: function(value, options) {
                    return value == (_.keys(this.wizardConfig).length - 1);
                },
                observe: 'activePaneIndex'
            };
            this.stickit(this.panesModel, bindings);
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.wizardConfig = JSON.parse(wizardInfo);
            // having 3 states - 'available', 'current' and 'unavailable'
            // FIXME: statuses will be set in restrictions handlings
            this.panesModel = new Backbone.Model({
                "activePaneIndex": 0,
                "NameAndRelease": 'current',
                "Mode": 'unavailable',
                "Compute": 'unavailable',
                "Network": 'unavailable',
                "Storage": 'unavailable',
                "AdditionalServices": 'unavailable',
                "Ready": 'unavailable'
            });
            this.settings = new models.Settings();
            this.maxAvailablePaneIndex = _.keys(this.wizardConfig).length;
            this.panesModel.on('change:activePaneIndex', this.handlePaneIndexChange, this);
            this.model = new models.WizardModel();
            this.model.prepareModel(this.wizardConfig);
        },
        handlePaneIndexChange: function() {
            var activeIndex = this.panesModel.get('activePaneIndex');
            var activePane = this.panesConstructors[activeIndex];
            this.renderPane(activePane, activeIndex);
            //FIXME: set unavailable where neccessary

        },
        beforeClusterCreation: function() {
            var success = this.processBinds('cluster');
            return $.Deferred()[success ? 'resolve' : 'reject']();
        },
        beforeSettingsSaving: function(settings) {
            var success = this.processBinds('settings');
            return $.Deferred()[success ? 'resolve' : 'reject']();
        },
        processBinds: function(prefixToProcess) {
            var modelsToUse = {};
            var result = false;
            switch(prefixToProcess) {
                case 'settings':
                    modelsToUse = {settings: this.settings};
                    break;
                case 'cluster':
                    modelsToUse = {cluster: this.cluster};
                    break;
            }
            _.each(this.wizardConfig, _.bind(function(configAttribute, configKey) {
                try {
                    _.each(_.pluck(configAttribute, 'bind'), _.bind(function(bind, bindIndex) {
                        if (!_.isUndefined(bind) && !_.isPlainObject(bind)) {
                            if (bind.split(':')[0] == prefixToProcess) {
                                utils.parseModelPath(bind, modelsToUse).set(this.model.get(configKey + "." + _.keys(configAttribute)[bindIndex]));
                            }
                        }
                        else if (!_.compact(_.pluck(configAttribute, 'bind')).length && _.pluck(_.pluck(configAttribute, 'values')[0], 'bind').length) {
                            _.each(_.pluck(configAttribute, 'values')[0], _.bind(function(value, valueIndex) {
                                if (value.data == this.model.get(configKey + "." + _.keys(configAttribute)[0])) {
                                    _.each(value.bind, _.bind(function(bind) {
                                        if (_.keys(bind)[0].split(':')[0] == prefixToProcess) {
                                            utils.parseModelPath(_.keys(bind)[0], modelsToUse).set(_.values(bind)[0]);
                                        }
                                    }, this));
                                 }
                             }, this));
                         }
                    }, this));
                    result = true;
                } catch (ignore) {}
            }, this));
            return result;
        },
        onInputKeydown: function(e) {
            if (e.which == 13) {
                e.preventDefault();
                this.nextPane();
            }
        },
        nextPane: function() {
            var activeIndex = this.panesModel.get('activePaneIndex');
            var ActivePane = this.panesConstructors[activeIndex];
            var activePaneInstance  = new ActivePane({wizard: this});
            activePaneInstance.processPaneData().done(_.bind(function() {
                 this.panesModel.set('activePaneIndex', activeIndex + 1);
            }, this));
        },
        onStepClick: function(e) {
            var paneIndex = parseInt($(e.currentTarget).data('pane'), 10);
            this.panesModel.set('activePaneIndex', paneIndex);
        },
        renderPane: function(Pane, paneIndex) {
            var newView = new Pane({wizard: this});
            this.registerSubView(newView);
            paneIndex = paneIndex || 0;
            _.each(_.keys(this.wizardConfig), _.bind(function(paneName, paneNameIndex) {
                if (paneIndex > paneNameIndex) {
                    this.panesModel.set(paneName, 'available');
                }
                if (paneIndex < paneNameIndex) {
                    this.panesModel.set(paneName, 'unavailable');
                }
            }, this));
            this.panesModel.set(newView.constructorName, 'current');
            this.$('.pane-content').html('');
            this.$('.wizard-footer .btn-success:visible').focus();
            this.$('.pane-content').append(newView.render().el);
        },
        prevPane: function() {
           this.panesModel.set('activePaneIndex', this.panesModel.get('activePaneIndex') - 1);
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
                            .then(_.bind(function() {
                                return this.beforeSettingsSaving();
                            }, this))
                            .then(_.bind(function() {
                                return this.settings.save();
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
            this.tearDownRegisteredSubViews();
             if (_.isNull(this.activePaneIndex)) {
                this.activePaneIndex = 0;
             }
            var panesTitles = [];
            _.each(this.panesConstructors, _.bind(function(PaneConstructor) {
                panesTitles.push(PaneConstructor.prototype.title);
            }, this));
            this.constructor.__super__.render.call(this, _.extend({
                panesTitles: panesTitles,
                currentStep: this.panesModel.get('activePaneIndex'),
                maxAvailableStep: this.maxAvailablePaneIndex
            }, this.templateHelpers));
            this.$('.wizard-footer .btn-success:visible').focus();
            this.renderPane(this.panesConstructors[0]);
            this.composeStickitBindings();
            return this;
        }
    });

    views.WizardPane = Backbone.View.extend({
        template: _.template(commonWizardTemplate),
        constructorName: 'WizardPane',
        initialize: function(options) {
            _.defaults(this, options);
        },
        renderControls: function(labelClasses, descriptionClasses, hasDescription, additionalAttribute) {
            var controlsHtml = '';
            var controlTpl = _.template(controlTemplate);
             _.each(this.wizard.wizardConfig[this.constructorName], _.bind(function(configurableAttribute, configurableKey) {
                 if (configurableAttribute.type == 'checkbox') {
                     controlsHtml += (controlTpl(_.extend(configurableAttribute, {
                                pane: configurableKey,
                                label_classes: labelClasses || '',
                                descriptionClasses: descriptionClasses || '',
                                label: configurableAttribute.label,
                                hasDescription: _.isUndefined(hasDescription) ? false : hasDescription ,
                                description: configurableAttribute.description || ''
                            })));
                 }
                 else {
                     _.each(configurableAttribute.values, _.bind(function(value, valueIndex) {
                         var shouldBeAdded = true;
                         if (!_.isUndefined(additionalAttribute)) {
                             if(configurableKey != additionalAttribute) {
                                 shouldBeAdded = false;
                             }
                         }
                         if (shouldBeAdded) {
                            controlsHtml += (controlTpl(_.extend(configurableAttribute, {
                                value: value.data,
                                pane: configurableKey,
                                label_classes: labelClasses || '',
                                descriptionClasses: descriptionClasses || '',
                                label: value.label,
                                hasDescription: _.isUndefined(hasDescription) ? false : hasDescription ,
                                description: value.description || ''
                            })));
                         }
                     }, this));
                 }
            }, this));
            return controlsHtml;
        },
        composePaneBindings: function() {
            var bindings = {};
            _.each(this.wizard.wizardConfig, _.bind(function(paneAttribute, paneName) {
                if (paneName == this.constructorName) {
                    _.each(paneAttribute, _.bind(function(bindingAttribute, bindingKey) {
                        bindings['input[name=' + bindingKey + ']'] = {
                            observe: paneName + '.' + bindingKey
                        };
                        if(bindingAttribute.type == 'checkbox') {
                            bindings['input[name=' + bindingKey + ']'] = {
                                observe:  paneName + '.' + bindingKey
                            };
                        }
                    }, this));
                }
            }, this));
            this.stickit(this.wizard.model, bindings);
        },
        processPaneData: function() {
            return $.Deferred().resolve();
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
                    }
                    return currentValue;
                }
            },
            'input[name=name]': {
                observe: 'NameAndRelease.name'
            }
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
        initialize: function(options) {
            _.defaults(this, options);
            this.releases = new models.Releases();
            this.releases.fetch();
            this.releases.on('sync', this.render, this);
            this.wizard.model.on('change:NameAndRelease.release__operating_system', this.handleReleaseChange, this);

        },
        handleReleaseChange: function(model, value) {
            if (this.releases.length) {
                var currentRelease = this.releases.where({'operating_system': value})[0];
                var roles = currentRelease.get('roles');
                this.wizard.model.set('NameAndRelease.release__roles', roles);
                this.wizard.model.set('NameAndRelease.release', currentRelease);
                this.$('.release-description').text(this.wizard.model.get('NameAndRelease.release').get('description'));
            }
        },
        render: function() {
            this.$el.html(this.template()).i18n();
            if (this.releases.length) {
                var firstRelease = this.releases.first();
                this.stickit(this.wizard.model);
                this.wizard.model.set({
                    "NameAndRelease.release__operating_system": firstRelease.get('operating_system'),
                    "NameAndRelease.release__roles": firstRelease.get('roles'),
                    "NameAndRelease.release": firstRelease
                });
            }
            return this;
        }
    });

    clusterWizardPanes.Mode = views.WizardPane.extend({
        constructorName: 'Mode',
        template: _.template(modePaneTemplate),
        title: 'dialog.create_cluster_wizard.mode.title',
        handleModeChange: function(model, value) {
             var description = this.wizard.model.get('NameAndRelease.release').get('modes_metadata')[value].description;
             $('.mode-description').text(description);
        },
        render: function() {
            this.$el.html(this.template({}));
            var description = this.wizard.model.get('NameAndRelease.release').get('modes_metadata').multinode.description;
            this.$('.mode-control-group .mode-description').text(description);
            this.$('.mode-control-group .span5').append(this.renderControls('setting', 'openstack-sub-title')).i18n();
            this.composePaneBindings();
            this.wizard.model.on('change:Mode.mode', this.handleModeChange, this);
            return this;
        }
    });

    clusterWizardPanes.Compute = views.WizardPane.extend({
        constructorName: 'Compute',
        title: 'dialog.create_cluster_wizard.compute.title',
        render: function() {
             this.$el.html(this.template({
                formClass: 'compute-step'
            }));
            this.$('.control-group').append(this.renderControls('', '', true)).i18n();
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
            this.$('.control-group').append(this.renderControls()).i18n();
            this.composePaneBindings();
            return this;
        }
    });

    clusterWizardPanes.Storage = views.WizardPane.extend({
        constructorName: 'Storage',
        template: _.template(storagePaneTemplate),
        title: 'dialog.create_cluster_wizard.storage.title',
        render: function() {
            this.$el.html(this.template({}));
            this.$('.control-group .cinder h5').after(this.renderControls('', '', false, 'cinder'));
            this.$('.control-group .glance h5').after(this.renderControls('', '', false, 'glance'));
            this.$el.i18n();
            this.composePaneBindings();
            return this;
        }
    });

    clusterWizardPanes.AdditionalServices = views.WizardPane.extend({
        constructorName: 'AdditionalServices',
        title: 'dialog.create_cluster_wizard.additional.title',
        events: {
            'change input[type=checkbox]': 'checkedStateChange'
        },
        checkedStateChange: function(e) {
            var target =   $(e.currentTarget);
            this.wizard.model.set(this.constructorName + '.' + target.attr('name'), target.is(':checked'));
        },
        render: function() {
            this.$el.html(this.template({}));
            this.$('.control-group').append(this.renderControls('', '', true, 'services')).i18n();
            this.composePaneBindings();
            return this;
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
