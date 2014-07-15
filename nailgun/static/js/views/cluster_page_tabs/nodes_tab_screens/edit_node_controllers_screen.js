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
    'text!templates/cluster/edit_node_controllers.html'
],
function(utils, models, EditNodeScreen, EditNodeControllersScreenTemplate) {
    'use strict';
    var EditNodeControllersScreen;

    EditNodeControllersScreen = EditNodeScreen.extend({
        className: 'edit-node-controllers-screen',
        constructorName: 'EditNodeControllersScreen',
        screen: null,
        template: _.template(EditNodeControllersScreenTemplate),
        templateHelpers: {
            showDiskSize: utils.showDiskSize
        },
        events: {
            'click [type="checkbox"]:checked': 'checkOnTypeDisk',
            'click [type="checkbox"]:not(:checked)': 'checkOffTypeDisk',
            'click .btn-create-raid:not(:disabled)' : 'createVirtualDrive',
            'click .btn-configure-disks' : 'goToConfigurationScreen',
            'click .btn-configure-controllers' : 'goToOtherController',
            'click .btn-reset': 'resetButtonConfiguration',
            'click .btn-revert-changes': 'revertButtonChanges',
            'click .btn-apply-changes:not(:disabled)': 'applyChanges',
            'click .btn-return:not(:disabled)': 'returnToNodeList',
            'click .btn-load-defaults': 'loadDefaultsButton'
        },
        resetButtonConfiguration: function() {
            var lengthVD = this.controller.virtual_drives.length;
            if (lengthVD) {
                var dialogCreateRaid = new dialogViews.ConfirmsChangesDialog({message: 'Are you sure you want to confirm? You may lose your data.', dispatcher: this.eventConfirmReset});
                this.registerSubView(dialogCreateRaid).render();
            } else {
                this.resetConfiguration();
            }
        },
        revertButtonChanges: function() {
            var dialogCreateRaid = new dialogViews.ConfirmsChangesDialog({message: 'All changes will be cancelled. Are you sure?', dispatcher: this.eventConfirmRevert});
            this.registerSubView(dialogCreateRaid).render();
        },
        loadDefaultsButton: function() {
            var lengthVD = this.controller.virtual_drives.length;
            if (lengthVD) {
                var dialogCreateRaid = new dialogViews.ConfirmsChangesDialog({message: 'Are you sure you want to confirm? You may lose your data.', dispatcher: this.eventConfirmDefault});
                this.registerSubView(dialogCreateRaid).render();
            } else {
                this.loadDefaults();
            }
        },
        resetConfiguration: function() {
            this.updateButtonsState(false);
            if (this.controller == null) {
                return;
            }
            var lengthVD = this.controller.virtual_drives.length;
            if (lengthVD > 0) {
                for(var i=0; i<lengthVD; i++) {
                    this.controller.virtual_drives.pop();
                }
            }
            _.each(this.controller.physical_drives, function(pd){
                pd.drive_group = null;
                pd.state = "unconfigured_good";
            });
            this.controller.tasks = [];
            this.render();
        },
        loadDefaults: function() {
            this.updateButtonsState(false);
            if (this.controller == null) {
                return;
            }
            var self = this;
            var url = '';
            this.nodes.each(function(node){
                if (node.get('checked')) {
                    url = _.result(node, 'url') + '/raid/defaults';
                }
            })
            $.ajax({
                type: "GET",
                url: url,
                success: function(data){
                    var dialogGoodState = new dialogViews.GoodStateDialog({message: 'Configuration has been loaded'});
                    self.registerSubView(dialogGoodState).render();
                    self.resetConfiguration();
                    _.each(data.raids, function(task){
                        if (task.action == 'create_nytrocache') {
                            task.raid_lvl = 'NytroCache' + task.raid_lvl;
                        }
                        if (task.action == 'create_cachecade') {
                            task.raid_lvl = 'CacheCade' + task.raid_lvl;
                        }
                        if (self.controller.controller_id == task.ctrl_id) {
                            self.controller.tasks.push(task);
                            self.dispatcher.trigger("CloseView");
                        }
                    })
                },
                failure: function(errMsg) {
                    utils.showErrorDialog({title: "Configuration has not been loaded"});
                }
            });
        },
        applyChanges: function(e) {
            this.updateButtonsState(true);
            var url = '';
            this.nodes.each(function(node){
                if (node.get('checked')) {
                    url = _.result(node, 'url') + '/raid/';
                }
            })
            var tasks = [];
            var self = this;
            var controllerID = this.controller.controller_id;
            _.each(this.controllers, function(controller){
                if (controller.controller_id != controllerID)
                    controller.tasks = self.tasksFromController(controller);
                if (controller.tasks.length) {
                    _.each(controller.tasks, function(task){
                        tasks.push(task);
                    })
                }
            })
            _.each(tasks, function(task) {
                if (task.action == 'create_nytrocache') {
                    if (task.raid_lvl.toString().indexOf('NytroCache') + 1)
                        task.raid_lvl = parseInt(task.raid_lvl.split('NytroCache')[1], 10);
                }
                if (task.action == 'create_cachecade') {
                    if (task.raid_lvl.toString().indexOf('CacheCade') + 1)
                        task.raid_lvl = parseInt(task.raid_lvl.split('CacheCade')[1], 10);
                }
            })
            var data = {
                'raid_model': this.controller.vendor,
                'raids': tasks
            };
            $.ajax({
                type: "PUT",
                url: url,
                data: JSON.stringify(data),
                contentType: "application/json; charset=utf-8",
                dataType: "json",
                success: _.bind(function(data){
                    this.startApply();
                }, this),
                statusCode: {
                    404: function() {
                        utils.showErrorDialog({title: "Page not found", message: msg});
                    }
                },
                failure: function(errMsg) {
                    alert(errMsg);
                }
            });
            //this.controller.tasks = [];
        },
        startApply: function() {
            var task = new models.Task();
            var url = '';
            var ID = null;
            this.nodes.each(function(node){
                if (node.get('checked')) {
                    url = _.result(node, 'url') + '/raid/apply/';
                    ID = node.get('id');
                }
            })
            var options = {
                method: 'PUT',
                url: url
            };
            task.save({}, options)
                .fail(_.bind(function() {
                    utils.showErrorDialog({title: 'Fail'});
                }, this))
                .always(_.bind(function() {
                    this.model.get('tasks').fetch({data: {cluster_id: null, node: ID}})
                        .done(_.bind(this.scheduleUpdate, this))
                        .fail(function() {
                            utils.showErrorDialog({title: "Task didn't created"});
                        });
                }, this));
        },
        scheduleUpdate: function() {
            var self = this;
            var IDnode = null;
            this.nodes.each(function(node){
                if (node.get('checked')) {
                    IDnode = node.get('id');
                }
            })
            var raidTask = this.model.get('tasks').filter(function(task) {return task.get('node') == IDnode && task.get('name') == 'raid'})[0];
            if (raidTask.get('status') == 'running') {
                this.$('.progress-bar').attr('style', 'display: block');
                this.$('.raid-window').attr('style', 'display: none');
                this.registerDeferred($.timeout(this.updateInterval).done(_.bind(this.update, this)));
            } else {
                if (raidTask.get('status') == 'ready') {
                    this.$('.progress-bar').attr('style', 'display: none');
                    this.$('.raid-window').attr('style', 'display: block');
                    var dialogGoodState = new dialogViews.GoodStateDialog({message: 'Storage configuration task has been applied successfully'});
                    this.registerSubView(dialogGoodState).render();
                    this.model.fetch()
                        .done(function(){
                            self.nodes = self.model.get('nodes');
                            var nodeID = null;
                            _.each((document.location.href).split(':'), function(id){
                                if (parseInt(id, 10) != NaN) {
                                    nodeID = parseInt(id, 10);
                                }
                            });
                            self.nodes.each(function(node){
                                if (node.id == nodeID)
                                    node.set({checked: true});
                            });

                            self.render();
                        })
                } else {
                    this.$('.progress-bar').attr('style', 'display: none');
                    this.$('.raid-window').attr('style', 'display: block');
                    var msg = raidTask.get('message');
                    utils.showErrorDialog({title: "Task's status is error", message: msg});
                }
            }
        },
        update: function() {
            var task = this.model.task('raid', 'running');
            if (task) {
                this.registerDeferred(task.fetch().always(_.bind(this.scheduleUpdate, this)));
            }
        },
        returnToNodeList: function() {
            if (this.controller.tasks.length) {
                this.tab.page.discardSettingsChanges({cb: _.bind(this.goToNodeList, this)});
            } else {
                this.goToNodeList();
            }
        },
        updateInfo: function(e) {
            this.updateButtonsState(false);
            this.Raid = {
                ctrl_id: this.controller.controller_id,
                drive: [],
                type: '',
                model: ''
            };
            if (this.controller.tasks.length) {
                var task = this.controller.tasks[this.controller.tasks.length-1];
                var model = this.parseModelController(this.controller.model);
                if (task.action == 'add_hotspare') {
                    _.each(this.controller.physical_drives, function(pd) {
                        if (pd.enclosure == task.eid) {
                            _.each(task.phys_devices, function(slot) {
                                if (pd.slot == slot) {
                                    pd.state = 'global_hot_spare';
                                    pd.new = true;
                                }
                            });
                        }
                    });
                } else if (model == 'nwd') {
                    _.each(this.controller.physical_drives, function(pd) {
                        pd.drive_group = task.raid_idx;
                        pd.state = 'N/A';
                    });
                    var overprovision = '';
                    try {
                        overprovision = task.options.overprovision;
                    } catch(e) {}
                    var vd = {
                        "access": "rw",
                        "consistent": "N/A",
                        "drive_group": task.raid_idx,
                        "raid_level": overprovision,
                        "size": "N/A",
                        "state": "new",
                        "virtual_drive": task.raid_idx,
                        "write_cache": "N/A"
                    };
                    this.controller.virtual_drives.push(vd);
                } else {
                    _.each(this.controller.physical_drives, function(pd) {
                        if (pd.enclosure == task.eid) {
                            _.each(task.phys_devices, function(slot) {
                                if (pd.slot == slot) {
                                    if (pd.drive_group != null) {
                                        //
                                    } else {
                                        pd.drive_group = task.raid_idx;
                                        pd.state = 'N/A';
                                    }
                                }
                            });
                        }
                    });
                    var write_cache = '';
                    try {
                        write_cache = task.options.write_cache;
                    } catch(e) {}
                    var vd = {
                        "name": task.raid_name,
                        "access": "rw",
                        "consistent": "N/A",
                        "drive_group": task.raid_idx,
                        "raid_level": task.raid_lvl,
                        "size": "N/A",
                        "state": "new",
                        "virtual_drive": task.raid_idx,
                        "write_cache": write_cache
                    };
                    this.controller.virtual_drives.push(vd);
                }
            }
            this.render();
        },
        revertChanges: function(e) {
            if (this.active == null)
                return;
            this.updateButtonsState(true);
            var self = this;
            _.each(this.controllers, function(cntrlr){
                if (cntrlr.controller_id == self.active)
                    cntrlr.checked = true;
            });
            this.updateController();
            this.render();
        },
        checkOnTypeDisk: function(e) {
            this.$('.btn-create-raid').attr('disabled', false);
            var currentType = $(e.target).data('id');
            this.Raid.type = currentType;
            this.Raid.drive.push({enclosure: $(e.target).data('enclosure'), slot: $(e.target).data('slot')});
            var allCheckBox = document.getElementsByTagName('input');
            for(var i=0; i<allCheckBox.length; i++) {
                if (currentType != $(allCheckBox[i]).data('id')) {
                    allCheckBox[i].disabled = true;
                };
            };
        },
        parseModelController: function(model) {
            model = model.toLowerCase();
            var result = ''
            if (model.indexOf('nytro megaraid') + 1) {
                result = 'nmr';
            } else if (model.indexOf('megaraid') + 1) {
                result = 'lmr';
            } else if (model.indexOf('nytro warpdrive') + 1) {
                result = 'nwd';
            } else {
                result = 'lsh'
            }
            return result;
        },
        checkOffTypeDisk: function(e) {
            var eid = $(e.target).data('enclosure');
            var slot = $(e.target).data('slot');
            var currentType = $(e.target).data('id');
            var allCheckBox = document.getElementsByTagName('input');
            var count = 0;
            for (var d=0; d<this.Raid.drive.length; d++) {
                if (this.Raid.drive[d].enclosure == eid && this.Raid.drive[d].slot == slot) {
                    this.Raid.drive.splice(d, 1);
                    break;
                }
            }
            for(var i=0; i<allCheckBox.length; i++) {
                if (currentType == $(allCheckBox[i]).data('id') && allCheckBox[i].checked) {
                    count++;
                };
            };
            if (count == 0) {
                this.$('.btn-create-raid').attr('disabled', true);
                this.Raid.type = '';
                for(var i=0; i<allCheckBox.length; i++) {
                    allCheckBox[i].disabled = false;
                };
            };
        },
        createVirtualDrive: function() {
            this.$('.btn-create-raid').attr('disabled', true);
            this.Raid.ctrl_id = this.controller.controller_id;
            this.Raid.model = this.parseModelController(this.controller.model);
            var dialogCreateRaid = new dialogViews.CreateRaidDialog({raid: this.Raid, controller: this.controller, dis: this.dispatcher});
            this.registerSubView(dialogCreateRaid).render();
            this.Raid = {
                ctrl_id: null,
                drive: [],
                type: '',
                model: ''
            };
            this.render();
        },
        goToOtherController: function(e) {
            var selectedNodesIds = _.pluck(this.nodes.where({checked: true}), 'id').join(',');
            var controllerID = parseInt($(e.target).data('id'), 10);
            if (this.active != controllerID) {
                if (controllerID >= 0) {
                    var controllers = this.controllers;
                    _.each(controllers, function(controller) {
                        if (controller.controller_id == controllerID) controller.checked = true;
                    });
                };
                this.updateController();
                this.render();
                app.navigate('#cluster/' + this.nodes.at(0).get('cluster') + '/nodes/' + $(e.currentTarget).data('action') + '/' + utils.serializeTabOptions({nodes: selectedNodesIds}), {trigger: true});
            }
        },
        goToConfigurationScreen: function(e) {
            var selectedNodesIds = _.pluck(this.nodes.where({checked: true}), 'id').join(',');
            app.navigate('#cluster/' + this.nodes.at(0).get('cluster') + '/nodes/' + $(e.currentTarget).data('action') + '/' + utils.serializeTabOptions({nodes: selectedNodesIds}), {trigger: true});
        },
        tasksFromController: function(controller) {
            var tasks = [];
            var ID = controller.controller_id;
            if (controller.virtual_drives) {
                var maxID = -1;
                _.each(controller.virtual_drives, function(vd) {
                    ID = vd.drive_group;
                    if (maxID <= ID)
                        maxID = ID + 1;
                    var drives = [];
                    var eid = null;
                    _.each(controller.physical_drives, function(pd) {
                        if (pd.drive_group == ID) {
                            drives.push(pd.slot);
                            if (pd.enclosure)
                                eid = pd.enclosure;
                        }
                    })
                    var task = null;
                    if (eid == null) {
                        task = {
                            'action': "create_nwd",
                            'raid_idx': ID,
                            'ctrl_id': controller.controller_id,
                            'options': {
                                'overprovision': ""
                            }
                        };
                    } else if (vd.raid_level.indexOf('NytroCache') + 1){
                        task = {
                            'action': "create_nytrocache",
                            'raid_idx': ID,
                            'raid_lvl': vd.raid_level.split('NytroCache')[1],
                            'ctrl_id': controller.controller_id,
                            'phys_devices': drives,
                            'eid': eid,
                            'options': {
                                'write_cache': vd.write_cache
                            }
                        };
                    } else if (vd.raid_level.indexOf('CacheCade') + 1){
                        task = {
                            'action': "create_cachecade",
                            'raid_idx': ID,
                            'raid_lvl': vd.raid_level.split('CacheCade')[1],
                            'ctrl_id': controller.controller_id,
                            'phys_devices': drives,
                            'eid': eid,
                            'options': {
                                'write_cache': vd.write_cache
                            }
                        };
                    } else {
                        task = {
                            'raid_name': vd.name,
                            'action': "create",
                            'phys_devices': drives,
                            'eid': eid,
                            'raid_idx': ID,
                            'ctrl_id': controller.controller_id,
                            'raid_lvl': vd.raid_level,
                            'options': {
                                'write_cache': vd.write_cache,
                                'strip_size': 128,
                                'ssd_caching': vd.ssd_caching_active == null ? false : true
                            }
                        };
                    }
                    tasks.push(task);
                })
                _.each(controller.physical_drives, function(pd) {
                    var ghs = null;
                    var drv = [];
                    if (pd.state == 'global_hot_spare') {
                        drv.push(pd.slot);
                        ghs = {
                            'action': "add_hotspare",
                            'raid_idx': maxID,
                            'ctrl_id': controller.controller_id,
                            'phys_devices': drv,
                            'eid': pd.enclosure,
                            'options': {
                                'dgs': []
                            }
                        };
                        maxID++;
                        tasks.push(ghs);
                    }
                })
            }
            return tasks;
        },
        updateButtonsState: function(state) {
            this.applyButton.set('disabled', state);
            this.cancelButton.set('disabled', state);
        },
        updateController: function() {
            var controller = null;
            var active = null;
            var self = this;
            _.each(this.controllers, function(cntrlr){
                if (cntrlr.checked) {
                    cntrlr.checked = false;
                    active = cntrlr.controller_id;
                    controller = cntrlr;
                };
            });
            if (controller == null) {
                //this.render();
            } else {
                this.model.get('nodes').fetch()
                    .done(function(){
                        self.nodes = self.model.get('nodes');
                        var nodeID = null;
                        _.each((document.location.href).split(':'), function(id){
                            if (parseInt(id, 10) != NaN) {
                                nodeID = parseInt(id, 10);
                            }
                        });
                        self.nodes.each(function(node){
                            if (node.id == nodeID) {
                                node.set({checked: true});
                                self.controllers = node.get('meta').raid.controllers;
                            }
                        });

                        _.each(self.controllers, function(cntrlr){
                            if (active == cntrlr.controller_id) {
                                controller = cntrlr;
                                return false;
                            }
                        })
                        var ID = controller.controller_id;
                        self.controller = controller;
                        self.Raid.ctrl_id = ID;
                        self.active = active;
                        self.updateButtonsState(true);
                        self.controller.tasks = self.tasksFromController(self.controller);
                        self.render();
                    })
            }
        },
        initialize: function(options) {
            _.defaults(this, options);
            this.dispatcher = _.clone(Backbone.Events);
            this.eventConfirmReset = _.clone(Backbone.Events);
            this.eventConfirmDefault = _.clone(Backbone.Events);
            this.eventConfirmRevert = _.clone(Backbone.Events);
            this.error = null;

            var nodeID = null;
            _.each((document.location.href).split(':'), function(id){
                if (parseInt(id, 10) != NaN) {
                    nodeID = parseInt(id, 10);
                }
            });
            this.nodes = this.model.get('nodes');
            var IDcluster = this.nodes.at(0).get('cluster');
            this.tasks = this.model.get('tasks');
            this.nodes.each(function(node){
                if (node.id == nodeID)
                    node.set({checked: true});
            });
            this.nodes = new models.Nodes(this.nodes.where({checked: true}));
            this.Raid = {
                ctrl_id: null,
                drive: [],
                type: '',
                model: ''
            };
            this.active = null;

            this.loadButton = new Backbone.Model({disabled: false});
            this.cancelButton = new Backbone.Model({disabled: true});
            this.applyButton = new Backbone.Model({disabled: true});

            this.dispatcher.on('CloseView', this.updateInfo, this);
            this.eventConfirmReset.on('StillApply', this.resetConfiguration, this);
            this.eventConfirmDefault.on('StillApply', this.loadDefaults, this);
            this.eventConfirmRevert.on('StillApply', this.revertChanges, this);
            this.controllers = [];
            this.controller = "";

            if (this.nodes.length > 0) {
                this.controllers = this.nodes.at(0).get('meta').raid.controllers;
            }
            this.updateController();
        },
        setupControllerButtonsBindings: function() {
            var bindings = {attributes: [{name: 'disabled', observe: 'disabled'}]};
            this.stickit(this.loadButton, {'.btn-defaults': bindings});
            this.stickit(this.cancelButton, {'.btn-revert-changes': bindings});
            this.stickit(this.applyButton, {'.btn-apply': bindings});
        },
        render: function() {
            this.$el.html(this.template(_.extend({
                nodes: this.nodes,
                controllers: this.controllers,
                controller: this.controller,
                active: this.active
            }, this.templateHelpers))).i18n();
            this.setupControllerButtonsBindings();
            try {
                if (this.parseModelController(this.controller.model) == 'nwd' && this.controller.virtual_drives.length == 0)
                    this.$('.btn-create-raid').attr('disabled', false);
            } catch(e) {}
            return this;
        }
    });

    return EditNodeControllersScreen;
});
