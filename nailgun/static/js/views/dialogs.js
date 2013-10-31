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
    'text!templates/dialogs/simple_message.html',
    'text!templates/dialogs/create_cluster_wizard.html',
    'text!templates/dialogs/create_cluster_wizard/name_and_release.html',
    'text!templates/dialogs/create_cluster_wizard/mode.html',
    'text!templates/dialogs/create_cluster_wizard/compute.html',
    'text!templates/dialogs/create_cluster_wizard/network.html',
    'text!templates/dialogs/create_cluster_wizard/storage.html',
    'text!templates/dialogs/create_cluster_wizard/additional.html',
    'text!templates/dialogs/create_cluster_wizard/ready.html',
    'text!templates/dialogs/rhel_license.html',
    'text!templates/dialogs/discard_changes.html',
    'text!templates/dialogs/display_changes.html',
    'text!templates/dialogs/remove_cluster.html',
    'text!templates/dialogs/error_message.html',
    'text!templates/dialogs/show_node.html',
    'text!templates/dialogs/dismiss_settings.html',
    'text!templates/dialogs/delete_nodes.html'
],
function(require, utils, models, simpleMessageTemplate, createClusterWizardTemplate, clusterNameAndReleasePaneTemplate, clusterModePaneTemplate, clusterComputePaneTemplate, clusterNetworkPaneTemplate, clusterStoragePaneTemplate, clusterAdditionalServicesPaneTemplate, clusterReadyPaneTemplate, rhelCredentialsDialogTemplate, discardChangesDialogTemplate, displayChangesDialogTemplate, removeClusterDialogTemplate, errorMessageTemplate, showNodeInfoTemplate, discardSettingsChangesTemplate, deleteNodesTemplate) {
    'use strict';

    var views = {};

    views.Dialog = Backbone.View.extend({
        className: 'modal fade',
        template: _.template(simpleMessageTemplate),
        errorMessageTemplate: _.template(errorMessageTemplate),
        modalBound: false,
        beforeTearDown: function() {
            this.$el.modal('hide');
        },
        displayError: function() {
            var logsLink;
            try {
                if (app.page.model.constructor == models.Cluster) {
                    var options = {type: 'local', source: 'api', level: 'error'};
                    logsLink = '#cluster/' + app.page.model.id + '/logs/' + utils.serializeTabOptions(options);
                }
            } catch(e) {}
            this.$('.modal-body').removeClass().addClass('modal-body');
            this.$('.modal-body').html(views.Dialog.prototype.errorMessageTemplate({logsLink: logsLink}));
        },
        displayErrorMessage: function(options) {
            this.displayError();
            if (options.message) {
                this.$('.text-error').text(options.message);
            }
        },
        initialize: function(options) {
            _.defaults(this, options);
        },
        render: function(options) {
            this.$el.attr('tabindex', -1);
            this.$el.html(this.template(options));
            if (!this.modalBound) {
                this.$el.on('hidden', _.bind(this.tearDown, this));
                this.$el.on('shown', _.bind(function() {
                    this.$('[autofocus]:first').focus();
                }, this));
                this.$el.modal();
                this.modalBound = true;
            }
            return this;
        }
    });

    var rhelCredentialsMixin = {
        renderRhelCredentialsForm: function(options) {
            var commonViews = require('views/common'); // avoid circular dependencies
            this.rhelCredentialsForm = new commonViews.RhelCredentialsForm(_.extend({dialog: this}, options));
            this.registerSubView(this.rhelCredentialsForm);
            this.$('.credentials').html('').append(this.rhelCredentialsForm.render().el).i18n();
        }
    };

    var clusterWizardPanes = {};

    views.CreateClusterWizard = views.Dialog.extend({
        className: 'modal fade create-cluster-modal',
        template: _.template(createClusterWizardTemplate),
        templateHelpers: _.pick(utils, 'floor'),
        events: {
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
            return (new $.Deferred()).resolve();
        },
        beforeClusterCreation: function(cluster) {
            return (new $.Deferred()).resolve();
        },
        beforeSettingsSaving: function(cluster) {
            return (new $.Deferred()).resolve();
        },
        render: function() {
            this.$el.html(this.template());
            return this;
        }
    });

    clusterWizardPanes.ClusterNameAndReleasePane = views.WizardPane.extend(_.extend({
        title: 'Name and Release',
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
                var releaseDependentPanes = _.filter(this.wizard.subViews, function(pane) {
                    return pane instanceof views.WizardPane && pane.releaseDependent;
                });
                _.invoke(releaseDependentPanes, 'render');
            }
            var deferred = new $.Deferred();
            return deferred[success ? 'resolve' : 'reject']();
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
            if (e.which == 13) {
                e.preventDefault();
                this.wizard.nextPane();
            }
        },
        onReleaseChange: function() {
            this.updateReleaseParameters();
            this.$el.detach();
            this.wizard.maxAvaialblePaneIndex = 0;
            this.wizard.render();
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
            this.$el.html(this.template());
            this.renderReleases();
            this.renderRhelCredentialsForm({
                redHatAccount: this.redHatAccount,
                visible: _.bind(this.rhelCredentialsFormVisible, this)
            });
            return this;
        }
    }, rhelCredentialsMixin));

    clusterWizardPanes.ClusterModePane = views.WizardPane.extend({
        title: 'Deployment Mode',
        releaseDependent: true,
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
            } catch(e) {}
            this.$('.mode-description').text(description);
        },
        beforeClusterCreation: function(cluster) {
            cluster.set({mode: this.$('input[name=mode]:checked').val()});
            return (new $.Deferred()).resolve();
        },
        render: function() {
            var availableModes = models.Cluster.prototype.availableModes();
            this.$el.html(this.template({availableModes: availableModes}));
            this.$('input[name=mode]:first').prop('checked', true).trigger('change');
            return this;
        }
    });

    clusterWizardPanes.ClusterComputePane = views.WizardPane.extend({
        title: 'Compute',
        template: _.template(clusterComputePaneTemplate),
        beforeSettingsSaving: function(settings) {
            try {
                settings.get('editable').common.libvirt_type.value = this.$('input[name=hypervisor]:checked').val();
            } catch(e) {
                return (new $.Deferred()).reject();
            }
            return (new $.Deferred()).resolve();
        },
        render: function() {
            this.$el.html(this.template());
            this.$('input[name=hypervisor][value=qemu]').prop('checked', true);
            return this;
        }
    });

    clusterWizardPanes.ClusterNetworkPane = views.WizardPane.extend({
        title: 'Network',
        releaseDependent: true,
        template: _.template(clusterNetworkPaneTemplate),
        beforeClusterCreation: function(cluster) {
            var manager = this.$('input[name=manager]:checked').val();
            if (manager == 'nova-network') {
                cluster.set({net_provider: 'nova_network'});
            } else {
                cluster.set({net_provider: 'neutron'});
                if (manager == 'neutron-gre') {
                    cluster.set({net_segment_type: 'gre'});
                } else if (manager == 'neutron-vlan') {
                    cluster.set({net_segment_type: 'vlan'});
                }
            }
            return (new $.Deferred()).resolve();
        },
        render: function() {
            var release = this.wizard.findPane(clusterWizardPanes.ClusterNameAndReleasePane).release;
            var disabled = !release || release.get('operating_system') == 'RHEL'; // no Neutron for RHOS for now
            this.$el.html(this.template({disabled: disabled, release: release}));
            if (disabled) {
                this.$('input[value^=neutron]').prop('disabled', true);
            }
            this.$('input[name=manager]:first').prop('checked', true);
            return this;
        }
    });

    clusterWizardPanes.ClusterStoragePane = views.WizardPane.extend({
        title: 'Storage Backends',
        releaseDependent: true,
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
            } catch(e) {
                return (new $.Deferred()).reject();
            }
            return (new $.Deferred()).resolve();
        },
        render: function() {
            var release = this.wizard.findPane(clusterWizardPanes.ClusterNameAndReleasePane).release;
            var disabled = !release || !_.contains(release.get('roles'), 'ceph-osd'); //FIXME: we should probably check for presence of actual settings instead
            this.$el.html(this.template({disabled: disabled, release: release}));
            if (disabled) {
                this.$('input[value=ceph]').prop('disabled', true);
            }
            this.$('input[name=cinder]:first, input[name=glance]:first').prop('checked', true);
            return this;
        }
    });

    clusterWizardPanes.ClusterAdditionalServicesPane = views.WizardPane.extend({
        title: 'Additional Services',
        releaseDependent: true,
        template: _.template(clusterAdditionalServicesPaneTemplate),
        beforeSettingsSaving: function(settings) {
            try {
                var additionalServices = settings.get('editable').additional_components;
                if (additionalServices) {
                    additionalServices.savanna.value = this.$('input[name=savanna]').is(':checked');
                    additionalServices.murano.value = this.$('input[name=murano]').is(':checked');
                    additionalServices.heat.value = this.$('input[name=murano]').is(':checked');
                }
            } catch(e) {
                return (new $.Deferred()).reject();
            }
            return (new $.Deferred()).resolve();
        },
        render: function() {
            var release = this.wizard.findPane(clusterWizardPanes.ClusterNameAndReleasePane).release;
            var disabled = !release || release.get('operating_system') == 'RHEL'; // no Savanna & Murano for RHOS for now
            this.$el.html(this.template({disabled: disabled, release: release}));
            if (disabled) {
                this.$('input[type=checkbox]').prop('disabled', true);
            }
            return this;
        }
    });

    clusterWizardPanes.ClusterReadyPane = views.WizardPane.extend({
        title: 'Finish',
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

    views.RhelCredentialsDialog = views.Dialog.extend(_.extend({
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
            this.$el.i18n();
            return this;
        }
    }, rhelCredentialsMixin));

    views.DiscardChangesDialog = views.Dialog.extend({
        template: _.template(discardChangesDialogTemplate),
        events: {
            'click .discard-btn:not(.disabled)': 'discardChanges'
        },
        discardChanges: function() {
            this.$('.discard-btn').addClass('disabled');
            var pendingNodes = this.model.get('nodes').filter(function(node) {
                return node.get('pending_addition') || node.get('pending_deletion') || node.get('pending_roles').length;
            });
            var nodes = new models.Nodes(pendingNodes);
            nodes.each(function(node) {
                node.set({pending_roles: []}, {silent: true});
                if (node.get('pending_addition')) {
                    node.set({
                        cluster_id: null,
                        pending_addition: false
                    }, {silent: true});
                } else {
                    node.set({pending_deletion: false}, {silent: true});
                }
            });
            nodes.toJSON = function() {
                return this.map(function(node) {
                    return _.pick(node.attributes, 'id', 'cluster_id', 'pending_addition', 'pending_deletion', 'pending_roles');
                });
            };
            Backbone.sync('update', nodes)
                .done(_.bind(function() {
                    this.$el.modal('hide');
                    this.model.get('nodes').fetch({data: {cluster_id: this.model.id}});
                    // we set node flags silently, so trigger resize event to redraw node list
                    this.model.get('nodes').trigger('resize');
                    app.navbar.refresh();
                }, this))
                .fail(_.bind(this.displayError, this));
        },
        render: function() {
            this.constructor.__super__.render.call(this, {cluster: this.model});
            return this;
        }
    });

    views.DisplayChangesDialog = views.Dialog.extend({
        template: _.template(displayChangesDialogTemplate),
        events: {
            'click .start-deployment-btn:not(.disabled)': 'deployCluster'
        },
        deployCluster: function() {
            this.$('.start-deployment-btn').addClass('disabled');
            var task = new models.Task();
            task.save({}, {url: _.result(this.model, 'url') + '/changes', type: 'PUT'})
                .done(_.bind(function() {
                    this.$el.modal('hide');
                    app.page.deploymentStarted();
                }, this))
                .fail(_.bind(this.displayError, this));
        },
        render: function() {
            this.constructor.__super__.render.call(this, {
                cluster: this.model,
                size: this.model.get('mode') == 'ha_compact' ? 3 : 1
            });
            return this;
        }
    });

    views.RemoveClusterDialog = views.Dialog.extend({
        template: _.template(removeClusterDialogTemplate),
        events: {
            'click .remove-cluster-btn:not(.disabled)': 'removeCluster'
        },
        removeCluster: function() {
            this.$('.remove-cluster-btn').addClass('disabled');
            this.model.destroy({wait: true})
                .done(_.bind(function() {
                    this.$el.modal('hide');
                    app.navbar.refresh();
                    app.navigate('#clusters', {trigger: true});
                }, this))
                .fail(_.bind(this.displayError, this));
        },
        render: function() {
            this.constructor.__super__.render.call(this, {cluster: this.model});
            return this;
        }
    });

    views.ShowNodeInfoDialog = views.Dialog.extend({
        template: _.template(showNodeInfoTemplate),
        templateHelpers: {
            showPropertyName: function(propertyName) {
                return propertyName.replace(/_/g, ' ');
            },
            showPropertyValue: function(group, name, value) {
                try {
                    if (group == 'memory' && (name == 'total' || name == 'maximum_capacity' || name == 'size')) {
                        value = utils.showMemorySize(value);
                    } else if (group == 'disks' && name == 'size') {
                        value = utils.showDiskSize(value);
                    } else if (name == 'size') {
                        value = utils.showSize(value);
                    } else if (name == 'frequency') {
                        value = utils.showFrequency(value);
                    } else if (name == 'max_speed' || name == 'current_speed') {
                        value = utils.showBandwidth(value);
                    }
                } catch (e) {}
                return value;
            },
            showSummary: function(meta, group) {
                var summary = '';
                try {
                    if (group == 'system') {
                        summary = (meta.system.manufacturer || '') + ' ' + (meta.system.product || '');
                    } else if (group == 'memory') {
                        if (_.isArray(meta.memory.devices) && meta.memory.devices.length) {
                            var sizes = _.groupBy(_.pluck(meta.memory.devices, 'size'), utils.showMemorySize);
                            summary = _.map(_.keys(sizes).sort(), function(size) {return sizes[size].length + ' x ' + size;}).join(', ');
                            summary += ', ' + utils.showMemorySize(meta.memory.total) + ' total';
                        } else {
                            summary = utils.showMemorySize(meta.memory.total) + ' total';
                        }
                    } else if (group == 'disks') {
                        summary = meta.disks.length + ' drive';
                        summary += meta.disks.length == 1 ? ', ' : 's, ';
                        summary += utils.showDiskSize(_.reduce(_.pluck(meta.disks, 'size'), function(sum, n) {return sum + n;}, 0)) + ' total';
                    } else if (group == 'cpu') {
                        var frequencies = _.groupBy(_.pluck(meta.cpu.spec, 'frequency'), utils.showFrequency);
                        summary = _.map(_.keys(frequencies).sort(), function(frequency) {return frequencies[frequency].length + ' x ' + frequency;}).join(', ');
                    } else if (group == 'interfaces') {
                        var bandwidths = _.groupBy(_.pluck(meta.interfaces, 'current_speed'), utils.showBandwidth);
                        summary = _.map(_.keys(bandwidths).sort(), function(bandwidth) {return bandwidths[bandwidth].length + ' x ' + bandwidth;}).join(', ');
                    }
                } catch (e) {}
                return summary;
            },
            sortEntryProperties: function(entry) {
                var properties = _.keys(entry);
                if (_.has(entry, 'name')) {
                    properties = ['name'].concat(_.keys(_.omit(entry, 'name')));
                }
                return properties;
            }
        },
        events: {
            'click .accordion-heading': 'toggle',
            'click .btn-edit-disks': 'goToDisksConfiguration',
            'click .btn-edit-networks': 'goToInterfacesConfiguration',
            'click .btn-node-console': 'goToSSHConsole'
        },
        toggle: function(e) {
            $(e.currentTarget).siblings('.accordion-body').collapse('toggle');
        },
        goToDisksConfiguration: function() {
            app.navigate('#cluster/' + this.node.get('cluster') + '/nodes/disks/' + utils.serializeTabOptions({nodes: this.node.id}), {trigger: true});
        },
        goToInterfacesConfiguration: function() {
            app.navigate('#cluster/' + this.node.get('cluster') + '/nodes/interfaces/' + utils.serializeTabOptions({nodes: this.node.id}), {trigger: true});
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.node.on('sync', this.render, this);
        },
        goToSSHConsole: function () {
            window.open('http://' + window.location.hostname + ':2443/?' + $.param({
                ssh: 'ssh://root@' + this.node.get('ip'),
                location: this.node.get('ip').replace(/\./g, '')
            }), '_blank');
        },
        render: function() {
            this.constructor.__super__.render.call(this, _.extend({
                node: this.node,
                locked: !app.page.tab || app.page.tab.model.task('deploy', 'running')
            }, this.templateHelpers));
            this.$('.accordion-body').collapse({
                parent: this.$('.accordion'),
                toggle: false
            }).on('show', function(e) {
                $(e.currentTarget).siblings('.accordion-heading').find('i').removeClass('icon-expand').addClass('icon-collapse');
            }).on('hide', function(e) {
                $(e.currentTarget).siblings('.accordion-heading').find('i').removeClass('icon-collapse').addClass('icon-expand');
            }).on('hidden', function(e) {
                e.stopPropagation();
            });
            return this;
        }
    });

    views.DiscardSettingsChangesDialog = views.Dialog.extend({
        template: _.template(discardSettingsChangesTemplate),
        defaultMessage: 'Settings were modified but not saved. Do you want to discard your changes and leave the page?',
        verificationMessage: 'Network verification is in progress. You should save changes or stay on the tab.',
        events: {
            'click .proceed-btn': 'proceed'
        },
        proceed: function() {
            this.$el.modal('hide');
            app.page.removeFinishedTasks().always(_.bind(this.cb, this));
        },
        render: function() {
            if (this.verification) {
                this.message = this.verificationMessage;
            }
            this.constructor.__super__.render.call(this, {
                message: this.message || this.defaultMessage,
                verification: this.verification || false
            });
            return this;
        }
    });

    views.DeleteNodesDialog = views.Dialog.extend({
        template: _.template(deleteNodesTemplate),
        events: {
            'click .btn-delete': 'deleteNodes'
        },
        deleteNodes: function() {
            if (this.nodes.cluster) {
                this.$('.btn-delete').prop('disabled', true);
                this.nodes.each(function(node) {
                    if (!node.get('pending_deletion')) {
                        if (node.get('pending_addition')) {
                            node.set({
                                cluster_id: null,
                                pending_addition: false,
                                pending_roles: []
                            });
                        } else{
                            node.set({pending_deletion: true});
                        }
                    }
                }, this);
                this.nodes.toJSON = function(options) {
                    return this.map(function(node) {
                        return _.pick(node.attributes, 'id', 'cluster_id', 'pending_roles', 'pending_addition', 'pending_deletion');
                    });
                };
                var deferred = this.nodes.sync('update', this.nodes)
                    .done(_.bind(function() {
                        this.$el.modal('hide');
                        app.page.tab.model.fetch();
                        app.page.tab.screen.nodes.fetch();
                        app.page.tab.screen.updateBatchActionsButtons();
                        app.navbar.refresh();
                        app.page.removeFinishedTasks();
                    }, this))
                    .fail(_.bind(this.displayError, this));
                }
        },
        render: function() {
            this.constructor.__super__.render.call(this, {nodes: this.nodes});
            return this;
        }
    });

    return views;
});
