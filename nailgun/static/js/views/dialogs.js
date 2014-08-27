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
    'view_mixins',
    'text!templates/dialogs/base_dialog.html',
    'text!templates/dialogs/discard_changes.html',
    'text!templates/dialogs/display_changes.html',
    'text!templates/dialogs/remove_cluster.html',
    'text!templates/dialogs/stop_deployment.html',
    'text!templates/dialogs/reset_environment.html',
    'text!templates/dialogs/update_environment.html',
    'text!templates/dialogs/show_node.html',
    'text!templates/dialogs/dismiss_settings.html',
    'text!templates/dialogs/delete_nodes.html',
    'text!templates/dialogs/change_password.html'
],
function(require, utils, models, viewMixins, baseDialogTemplate, discardChangesDialogTemplate, displayChangesDialogTemplate, removeClusterDialogTemplate, stopDeploymentDialogTemplate, resetEnvironmentDialogTemplate, updateEnvironmentDialogTemplate, showNodeInfoTemplate, discardSettingsChangesTemplate, deleteNodesTemplate, changePasswordTemplate) {
    'use strict';

    var views = {};

    views.Dialog = Backbone.View.extend({
        className: 'modal fade',
        template: _.template(baseDialogTemplate),
        modalBound: false,
        beforeTearDown: function() {
            this.unstickit();
            this.$el.modal('hide');
        },
        displayError: function(options) {
            var logsLink;
            var cluster = app.page.model;
            if (!options.hideLogsLink && cluster && cluster.constructor == models.Cluster) {
                var logOptions = {type: 'local', source: 'api', level: 'error'};
                logsLink = '#cluster/' + cluster.id + '/logs/' + utils.serializeTabOptions(logOptions);
            }
            var dialogOptions = _.defaults(options, {
                error: true,
                title: $.t('dialog.error_dialog.title'),
                message: $.t('dialog.error_dialog.warning'),
                logsLink: logsLink
            });
            this.$el.removeClass().addClass('modal').html(views.Dialog.prototype.template(dialogOptions)).i18n();
        },
        initialize: function(options) {
            _.defaults(this, options);
        },
        render: function(options) {
            this.$el.attr('tabindex', -1);
            if (options && options.error) {
                this.displayError(options);
            } else {
                var templateOptions = _.extend({title: '', message: '', error: false, logsLink: ''}, options);
                this.$el.html(this.template(templateOptions)).i18n();
            }
            if (!this.modalBound) {
                this.$el.on('hidden', _.bind(this.tearDown, this));
                this.$el.on('shown', _.bind(function() {
                    this.$('[autofocus]:first').focus();
                }, this));
                this.$el.modal(_.extend({}, this.modalOptions));
                this.modalBound = true;
            }
            return this;
        }
    });

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
            this.$('.btn').addClass('disabled');
            app.page.removeFinishedDeploymentTasks();
            var task = new models.Task();
            task.save({}, {url: _.result(this.model, 'url') + '/changes', type: 'PUT'})
                .done(_.bind(function() {
                    this.$el.modal('hide');
                    app.page.deploymentTaskStarted();
                }, this))
                .fail(_.bind(this.displayError, this));
        },
        render: function() {
            this.constructor.__super__.render.call(this, {
                cluster: this.model,
                size: 1
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

    views.StopDeploymentDialog = views.Dialog.extend({
        template: _.template(stopDeploymentDialogTemplate),
        events: {
            'click .stop-deployment-btn:not(:disabled)': 'stopDeployment'
        },
        stopDeployment: function() {
            this.$('.stop-deployment-btn').attr('disabled', true);
            var task = new models.Task();
            task.save({}, {url: _.result(this.model, 'url') + '/stop_deployment', type: 'PUT'})
                .done(_.bind(function() {
                    this.$el.modal('hide');
                    app.page.deploymentTaskStarted();
                }, this))
                .fail(_.bind(function(response) {
                    this.displayError({
                        title: $.t('dialog.stop_deployment.stop_deployment_error.title'),
                        message: utils.getResponseText(response) || $.t('dialog.stop_deployment.stop_deployment_error.stop_deployment_warning')
                    });
                }, this));
        },
        render: function() {
            this.constructor.__super__.render.call(this, {cluster: this.model});
            return this;
        }
    });

    views.ResetEnvironmentDialog = views.Dialog.extend({
        template: _.template(resetEnvironmentDialogTemplate),
        events: {
            'click .reset-environment-btn:not(:disabled)': 'resetEnvironment'
        },
        resetEnvironment: function() {
            this.$('.reset-environment-btn').attr('disabled', true);
            app.page.removeFinishedDeploymentTasks();
            var task = new models.Task();
            task.save({}, {url: _.result(this.model, 'url') + '/reset', type: 'PUT'})
                .done(_.bind(function() {
                    this.$el.modal('hide');
                    app.page.deploymentTaskStarted();
                }, this))
                .fail(_.bind(this.displayError, this));
        }
    });

    views.UpdateEnvironmentDialog = views.Dialog.extend({
        template: _.template(updateEnvironmentDialogTemplate),
        events: {
            'click .update-environment-btn:not(:disabled)': 'updateEnvironment'
        },
        updateEnvironment: function() {
            this.$('.update-environment-btn').attr('disabled', true);
            var deferred = this.model.save({
                pending_release_id: this.action == 'update' ? this.model.get('pending_release_id') : this.model.get('release_id')
            }, {patch: true, wait: true});
            if (deferred) {
                deferred.done(_.bind(function() {
                    app.page.removeFinishedDeploymentTasks();
                    var task = new models.Task();
                    task.save({}, {url: _.result(this.model, 'url') + '/update', type: 'PUT'})
                        .done(_.bind(function() {
                            this.$el.modal('hide');
                            app.page.deploymentTaskStarted();
                        }, this))
                        .fail(_.bind(this.displayError, this));
                }, this))
                .fail(_.bind(this.displayError, this));
            }
        },
        render: function() {
            this.constructor.__super__.render.call(this, {cluster: this.model, action: this.action, isDowngrade: this.isDowngrade});
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
                } catch (ignore) {}
                return (_.isEmpty(value) && (value !== 0)) ? '\u00A0' : value;
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
                            summary += ', ' + utils.showMemorySize(meta.memory.total) + ' ' + $.t('dialog.show_node.total');
                        } else {
                            summary = utils.showMemorySize(meta.memory.total) + ' ' + $.t('dialog.show_node.total');
                        }
                    } else if (group == 'disks') {
                        summary = meta.disks.length + ' ';
                        summary += $.t('dialog.show_node.drive', {count: meta.disks.length});
                        summary += ', ' + utils.showDiskSize(_.reduce(_.pluck(meta.disks, 'size'), function(sum, n) {return sum + n;}, 0)) + ' ' + $.t('dialog.show_node.total');
                    } else if (group == 'cpu') {
                        var frequencies = _.groupBy(_.pluck(meta.cpu.spec, 'frequency'), utils.showFrequency);
                        summary = _.map(_.keys(frequencies).sort(), function(frequency) {return frequencies[frequency].length + ' x ' + frequency;}).join(', ');
                    } else if (group == 'interfaces') {
                        var bandwidths = _.groupBy(_.pluck(meta.interfaces, 'current_speed'), utils.showBandwidth);
                        summary = _.map(_.keys(bandwidths).sort(), function(bandwidth) {return bandwidths[bandwidth].length + ' x ' + bandwidth;}).join(', ');
                    }
                } catch (ignore) {}
                return summary;
            },
            sortEntryProperties: utils.sortEntryProperties
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
            this.constructor.__super__.render.call(this, _.extend({node: this.node}, this.templateHelpers));
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
        events: {
            'click .proceed-btn': 'proceed'
        },
        proceed: function() {
            this.$el.modal('hide');
            app.page.removeFinishedNetworkTasks().always(_.bind(this.cb, this));
        },
        render: function() {
            if (this.verification) {
                this.message = $.t('dialog.dismiss_settings.verify_message');
            }
            this.constructor.__super__.render.call(this, {
                message: this.message || $.t('dialog.dismiss_settings.default_message'),
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
                this.nodes.sync('update', this.nodes)
                    .done(_.bind(function() {
                        this.$el.modal('hide');
                        app.page.tab.model.fetch();
                        app.page.tab.screen.nodes.fetch();
                        _.invoke(app.page.tab.screen.nodes.where({checked: true}), 'set', {checked: false});
                        app.page.tab.screen.updateBatchActionsButtons();
                        app.navbar.refresh();
                        app.page.removeFinishedNetworkTasks();
                    }, this))
                    .fail(_.bind(function() {
                        utils.showErrorDialog({
                            title: $.t('cluster_page.nodes_tab.node_deletion_error.title'),
                            message: $.t('cluster_page.nodes_tab.node_deletion_error.node_deletion_warning')
                        });
                    }, this));
            }
        },
        render: function() {
            this.constructor.__super__.render.call(this, {nodes: this.nodes});
            return this;
        }
    });

    views.ChangePasswordDialog = views.Dialog.extend({
        template: _.template(changePasswordTemplate),
        mixins: [viewMixins.toggleablePassword],
        events: {
            'click .btn-change-password': 'changePassword',
            'keyup input': 'onPasswordChange',
            'keydown': 'onKeydown'
        },
        changePassword: function() {
            var currentPassword = this.$('[name=current_password]').val(),
                newPassword = this.$('[name=new_password]').val(),
                confirmedPassword= this.$('[name=confirm_new_password]').val();
            if (currentPassword && (newPassword == confirmedPassword)) {
                app.keystoneClient.changePassword(currentPassword, newPassword)
                    .done(_.bind(function() {
                        app.user.set({password: app.keystoneClient.password});
                        this.$el.modal('hide');
                    }, this))
                    .fail(_.bind(function() {
                        this.$('[name=current_password]').focus().addClass('error').parent().siblings('.validation-error').show();
                    }, this));
            }
        },
        onPasswordChange: function(e) {
            this.$(e.currentTarget).removeClass('error').parent().siblings('.validation-error').hide();
            var newPassword = this.$('[name=new_password]'),
                confirmedPassword = this.$('[name=confirm_new_password]');
            confirmedPassword.removeClass('error').parent().siblings('.validation-error').hide();
            if (newPassword.val() != confirmedPassword.val()) {
                confirmedPassword.addClass('error').parent().siblings('.validation-error').show();
            }
            var disabled = (!_.all(_.invoke(_.map(this.$('input'), $), 'val')) || this.$('.validation-error').is(':visible'));
            _.defer(_.bind(function() {
                this.$('.btn-change-password').attr('disabled', disabled);
            }, this));
        },
        onKeydown: function(e) {
            if (e.which == 13) {
                e.preventDefault();
                this.changePassword();
            }
        }
    });

    return views;
});
