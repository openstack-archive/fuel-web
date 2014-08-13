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
    'utils',
    'models',
    'views/cluster_page_tabs/nodes_tab_screens/edit_node_screen',
    'text!templates/cluster/edit_node_disks.html',
    'text!templates/cluster/node_disk.html',
    'text!templates/cluster/volume_style.html'
],
function(utils, models, EditNodeScreen, editNodeDisksScreenTemplate, nodeDisksTemplate, volumeStylesTemplate) {
    'use strict';
    var EditNodeDisksScreen, NodeDisk;

    EditNodeDisksScreen = EditNodeScreen.extend({
        className: 'edit-node-disks-screen',
        constructorName: 'EditNodeDisksScreen',
        template: _.template(editNodeDisksScreenTemplate),
        events: {
            'click .btn-defaults': 'loadDefaults',
            'click .btn-revert-changes': 'revertChanges',
            'click .btn-apply:not(:disabled)': 'applyChanges',
            'click .btn-return:not(:disabled)': 'returnToNodeList'
        },
        hasChanges: function() {
            var volumes = _.pluck(this.disks.toJSON(), 'volumes');
            return !this.nodes.reduce(function(result, node) {
                return result && _.isEqual(volumes, _.pluck(node.disks.toJSON(), 'volumes'));
            }, true);
        },
        hasValidationErrors: function() {
            var result = false;
            this.disks.each(function(disk) {result = result || disk.validationError || _.some(disk.get('volumes').models, 'validationError');}, this);
            return result;
        },
        isLocked: function() {
            var nodesAvailableForChanges = this.nodes.filter(function(node) {
                return node.get('pending_addition') || (node.get('status') == 'error' && node.get('error_type') == 'provision');
            });
            return !nodesAvailableForChanges.length || this.constructor.__super__.isLocked.apply(this);
        },
        checkForChanges: function() {
            this.updateButtonsState(this.isLocked());
            this.applyChangesButton.set('disabled', this.isLocked() || !this.hasChanges() || this.hasValidationErrors());
            this.cancelChangesButton.set('disabled', this.isLocked() || (!this.hasChanges() && !this.hasValidationErrors()));
        },
        loadDefaults: function() {
            this.disableControls(true);
            this.disks.fetch({url: _.result(this.nodes.at(0), 'url') + '/disks/defaults/'})
                .fail(_.bind(function() {
                    utils.showErrorDialog({
                        title: $.t('cluster_page.nodes_tab.configure_disks.configuration_error.title'),
                        message: $.t('cluster_page.nodes_tab.configure_disks.configuration_error.load_defaults_warning')
                    });
                }, this));
        },
        revertChanges: function() {
            this.disks.reset(_.cloneDeep(this.nodes.at(0).disks.toJSON()), {parse: true});
        },
        applyChanges: function() {
            if (this.hasValidationErrors()) {
                return (new $.Deferred()).reject();
            }
            this.disableControls(true);
            return $.when.apply($, this.nodes.map(function(node) {
                    node.disks.each(function(disk, index) {
                        disk.set({volumes: new models.Volumes(this.disks.at(index).get('volumes').toJSON())});
                    }, this);
                    return Backbone.sync('update', node.disks, {url: _.result(node, 'url') + '/disks'});
                }, this))
                .done(_.bind(function() {
                    this.model.fetch();
                    this.render();
                }, this))
                .fail(_.bind(function(response) {
                    this.checkForChanges();
                    utils.showErrorDialog({
                        title: $.t('cluster_page.nodes_tab.configure_disks.configuration_error.title'),
                        message: utils.getResponseText(response) || $.t('cluster_page.nodes_tab.configure_disks.configuration_error.saving_warning')
                    });
                }, this));
        },
        mapVolumesColors: function() {
            this.volumesColors = {};
            var colors = [
                ['#23a85e', '#1d8a4d'],
                ['#3582ce', '#2b6ba9'],
                ['#eea616', '#c38812'],
                ['#1cbbb4', '#189f99'],
                ['#9e0b0f', '#870a0d'],
                ['#8f50ca', '#7a44ac'],
                ['#1fa0e3', '#1b88c1'],
                ['#85c329', '#71a623'],
                ['#7d4900', '#6b3e00']
            ];
            this.volumes.each(function(volume, index) {
                this.volumesColors[volume.get('name')] = colors[index];
            }, this);
        },
        initialize: function(options) {
            this.constructor.__super__.initialize.apply(this, arguments);
            if (this.nodes.length) {
                this.model.on('change:status', this.revertChanges, this);
                this.volumes = new models.Volumes([], {url: _.result(this.nodes.at(0), 'url') + '/volumes'});
                this.loading = $.when.apply($, this.nodes.map(function(node) {
                        node.disks = new models.Disks();
                        return node.disks.fetch({url: _.result(node, 'url') + '/disks'});
                    }, this).concat(this.volumes.fetch()))
                    .done(_.bind(function() {
                        this.disks = new models.Disks(_.cloneDeep(this.nodes.at(0).disks.toJSON()), {parse: true});
                        this.disks.on('sync', this.render, this);
                        this.disks.on('reset', this.render, this);
                        this.disks.on('error', this.checkForChanges, this);
                        this.mapVolumesColors();
                        this.render();
                    }, this))
                    .fail(_.bind(this.goToNodeList, this));
            } else {
                this.goToNodeList();
            }
            this.initButtons();
        },
        getDiskMetaData: function(disk) {
            var result;
            var disksMetaData = this.nodes.at(0).get('meta').disks;
            // try to find disk metadata by matching "extra" field
            // if at least one entry presents both in disk and metadata entry,
            // this metadata entry is for our disk
            var extra = disk.get('extra') || [];
            result = _.find(disksMetaData, function(diskMetaData) {
                if (_.isArray(diskMetaData.extra)) {
                    return _.intersection(diskMetaData.extra, extra).length;
                }
                return false;
            }, this);

            // if matching "extra" fields doesn't work, try to search by disk id
            if (!result) {
                result = _.find(disksMetaData, {disk: disk.id});
            }

            return result;
        },
        renderDisks: function() {
            this.tearDownRegisteredSubViews();
            this.$('.node-disks').html('');
            this.disks.each(function(disk) {
                var nodeDisk = new NodeDisk({
                    disk: disk,
                    diskMetaData: this.getDiskMetaData(disk),
                    screen: this
                });
                this.registerSubView(nodeDisk);
                this.$('.node-disks').append(nodeDisk.render().el);
            }, this);
        },
        render: function() {
            this.$el.html(this.template({
                nodes: this.nodes,
                locked: this.isLocked()
            })).i18n();
            if (this.loading && this.loading.state() != 'pending') {
                this.renderDisks();
                this.checkForChanges();
            }
            this.setupButtonsBindings();
            return this;
        }
    });

    NodeDisk = Backbone.View.extend({
        template: _.template(nodeDisksTemplate),
        volumeStylesTemplate: _.template(volumeStylesTemplate),
        templateHelpers: {
            sortEntryProperties: utils.sortEntryProperties,
            showDiskSize: utils.showDiskSize
        },
        events: {
            'click .toggle-volume': 'toggleEditDiskForm',
            'click .close-btn': 'deleteVolume',
            'click .use-all-allowed': 'useAllAllowedSpace'
        },
        diskFormBindings: {
            '.disk-form': {
                observe: 'visible',
                visible: true,
                visibleFn: function($el, isVisible, options) {
                    $el.collapse(isVisible ? 'show' : 'hide');
                }
            }
        },
        toggleEditDiskForm: function(e) {
            this.diskForm.set({visible: !this.diskForm.get('visible')});
        },
        getVolumeMinimum: function(name) {
            return this.screen.volumes.findWhere({name: name}).get('min_size');
        },
        checkForGroupsDeletionAvailability: function() {
            this.disk.get('volumes').each(function(volume) {
                var name = volume.get('name');
                this.$('.disk-visual .' + name + ' .close-btn').toggle(!this.screen.isLocked() && this.diskForm.get('visible') && volume.getMinimalSize(this.getVolumeMinimum(name)) <= 0);
            }, this);
        },
        updateDisk: function() {
            this.$('.disk-visual').removeClass('invalid');
            this.$('input').removeClass('error').parents('.volume-group').next().text('');
            this.$('.volume-group-error-message.common').text('');
            this.disk.get('volumes').each(function(volume) {
                volume.set({size: volume.get('size')}, {validate: true, minimum: this.getVolumeMinimum(volume.get('name'))});
            }, this); // volumes validation (minimum)
            this.disk.set({volumes: this.disk.get('volumes')}, {validate: true}); // disk validation (maximum)
            this.renderVisualGraph();
        },
        updateDisks: function(e) {
            this.updateDisk();
            _.invoke(_.omit(this.screen.subViews, this.cid), 'updateDisk', this);
            this.screen.checkForChanges();
        },
        deleteVolume: function(e) {
            var volumeName = this.$(e.currentTarget).parents('.volume-group').data('volume');
            var volume = this.disk.get('volumes').findWhere({name: volumeName});
            volume.set({size: 0});
        },
        useAllAllowedSpace: function(e) {
            var volumeName = this.$(e.currentTarget).parents('.volume-group').data('volume');
            var volume = this.disk.get('volumes').findWhere({name: volumeName});
            volume.set({size: _.max([0, this.disk.getUnallocatedSpace({skip: volumeName})])});
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.diskForm = new Backbone.Model({visible: false});
            this.diskForm.on('change:visible', this.checkForGroupsDeletionAvailability, this);
            this.disk.on('invalid', function(model, error) {
                this.$('.disk-visual').addClass('invalid');
                this.$('input').addClass('error');
                this.$('.volume-group-error-message.common').text(error);
            }, this);
            this.disk.get('volumes').each(function(volume) {
                volume.on('change:size', this.updateDisks, this);
                volume.on('change:size', function() {_.invoke(this.screen.subViews, 'checkForGroupsDeletionAvailability', this);}, this);
                volume.on('invalid', function(model, error) {
                    this.$('.disk-visual').addClass('invalid');
                    this.$('input[name=' + volume.get('name') + ']').addClass('error').parents('.volume-group').next().text(error);
                }, this);
            }, this);
        },
        renderVolume: function(name, width, size) {
            this.$('.disk-visual .' + name)
                .toggleClass('hidden-titles', width < 6)
                .css('width', width + '%')
                .find('.volume-group-size').text(utils.showDiskSize(size, 2));
        },
        renderVisualGraph: function() {
            if (!this.disk.get('volumes').some('validationError') && this.disk.isValid()) {
                var unallocatedWidth = 100;
                this.disk.get('volumes').each(function(volume) {
                    var width = this.disk.get('size') ? utils.floor(volume.get('size') / this.disk.get('size') * 100, 2) : 0;
                    unallocatedWidth -= width;
                    this.renderVolume(volume.get('name'), width, volume.get('size'));
                }, this);
                this.renderVolume('unallocated', unallocatedWidth, this.disk.getUnallocatedSpace());
            }
        },
        applyColors: function() {
            this.disk.get('volumes').each(function(volume) {
                var name = volume.get('name');
                var colors = this.screen.volumesColors[name];
                this.$('.disk-visual .' + name + ', .volume-group-box-flag.' + name).attr('style', this.volumeStylesTemplate({startColor: _.first(colors), endColor: _.last(colors)}));
            }, this);
        },
        setupVolumesBindings: function() {
            this.disk.get('volumes').each(function(volume) {
                var bindings = {};
                bindings['input[name=' + volume.get('name') + ']'] = {
                    events: ['keyup'],
                    observe: 'size',
                    getVal: function($el) {
                        return Number($el.autoNumeric('get'));
                    },
                    update: function($el, value) {
                        $el.autoNumeric('set', value);
                    }
                };
                this.stickit(volume, bindings);
            }, this);
        },
        render: function() {
            this.$el.html(this.template(_.extend({
                diskMetaData: this.diskMetaData,
                disk: this.disk,
                volumes: this.screen.volumes,
                locked: this.screen.isLocked()
            }, this.templateHelpers))).i18n();
            this.$('.disk-form').collapse({toggle: false});
            this.applyColors();
            this.renderVisualGraph();
            this.$('input').autoNumeric('init', {mDec: 0});
            this.stickit(this.diskForm, this.diskFormBindings);
            this.setupVolumesBindings();
            return this;
        }
    });

    return EditNodeDisksScreen;
});
